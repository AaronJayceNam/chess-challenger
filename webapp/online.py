"""Online multiplayer: WebSocket matchmaking + move relay.

Design principles:
  * The SERVER is the single authority — every move is validated with
    python-chess and the resulting state (fen, legal-move map, san history,
    game-over) is broadcast to both players. Clients never need chess logic.
  * The SERVER also owns RATING: each player's rating is resolved from their
    auth token at match start (never trusted from the client), and the Elo
    change is computed + persisted here on game end. The client only displays
    the before/after/delta the server sends in the "end" message.
  * Two ways to match: a quick-match queue, and 4-letter invite codes for
    playing a specific friend.
  * In-memory state guarded by an asyncio.Lock — fine for the single-process
    deployments we use (uvicorn single worker, locally and on Render).
  * A disconnect mid-game forfeits the game to the opponent.

Wire protocol (JSON messages):
  client -> server:
    {type:"quick",  name, token}          join the quick-match queue
    {type:"create", name, token}          create an invite room -> {type:"room", code}
    {type:"join",   name, token, code}    join a friend's room
    {type:"cancel"}                leave queue / close my room
    {type:"move",   uci}           play a move
    {type:"resign"}                resign the game
    {type:"ping"}                  keepalive -> {type:"pong"}
  server -> client:
    {type:"waiting"}                                queued, looking for opponent
    {type:"room", code}                             invite code created
    {type:"start", color:"w"|"b", opponent, state}  game begins
    {type:"state", lastUci, state}                  after every move
    {type:"end", result:"1-0"|"0-1"|"1/2-1/2", reason, rating?}
    {type:"error", message}
  In "end", `rating` (when present) is this player's {before, after, delta}.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import time

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# no 0/O/1/I to keep codes easy to read aloud
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# 10 minutes per player; env-overridable so tests can use a tiny clock.
CLOCK_START = float(os.environ.get("CC_CLOCK_SECS", "600"))


def _new_code(taken) -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        if code not in taken:
            return code


async def _send(ws: WebSocket, payload: dict) -> None:
    """Send, ignoring failures (peer may have vanished mid-broadcast)."""
    try:
        await ws.send_json(payload)
    except Exception:
        pass


class Game:
    def __init__(self, w_ws: WebSocket, w_name: str, b_ws: WebSocket, b_name: str,
                 w_uid: str | None = None, b_uid: str | None = None):
        self.board = chess.Board()
        self.moves: list[str] = []
        self.san: list[str] = []
        self.ws = {chess.WHITE: w_ws, chess.BLACK: b_ws}
        self.names = {chess.WHITE: w_name, chess.BLACK: b_name}
        # account ids (None for a guest) — used for server-authoritative rating.
        self.uids = {chess.WHITE: w_uid, chess.BLACK: b_uid}
        self.rated_done = False        # ensure the Elo change is applied at most once
        self.over = False
        # chess clock: each side gets CLOCK_START seconds; only the side to
        # move's clock runs. turn_started marks when the current turn began.
        self.clock = {chess.WHITE: CLOCK_START, chess.BLACK: CLOCK_START}
        self.turn_started = time.monotonic()
        self.draw_offer_by = None   # colour with a pending draw offer (expires on a move)

    def remaining(self) -> tuple[float, float]:
        """(white, black) seconds left, including the running turn's elapsed."""
        rw, rb = self.clock[chess.WHITE], self.clock[chess.BLACK]
        if not self.over:
            elapsed = time.monotonic() - self.turn_started
            if self.board.turn == chess.WHITE:
                rw -= elapsed
            else:
                rb -= elapsed
        return max(0.0, rw), max(0.0, rb)

    def color_of(self, ws: WebSocket):
        if self.ws[chess.WHITE] is ws:
            return chess.WHITE
        if self.ws[chess.BLACK] is ws:
            return chess.BLACK
        return None

    def opponent_ws(self, ws: WebSocket):
        return self.ws[chess.BLACK] if self.ws[chess.WHITE] is ws else self.ws[chess.WHITE]


class Lobby:
    def __init__(self, legal_state, rating_hooks: dict | None = None):
        self._legal_state = legal_state   # server.py's board -> state dict
        # optional server-authoritative rating hooks (from auth.py):
        #   resolve(token) -> (uid, rating) | None
        #   apply(uid_w, uid_b, result) -> {'white':{before,after,delta}, 'black':{...}} | None
        self._resolve = (rating_hooks or {}).get("resolve")
        self._apply = (rating_hooks or {}).get("apply")
        self.lock = asyncio.Lock()
        # queue entries / rooms values are (ws, name, rating, uid)
        self.queue: list[tuple[WebSocket, str, int, str | None]] = []
        self.rooms: dict[str, tuple[WebSocket, str, int, str | None]] = {}
        self.games: dict[WebSocket, Game] = {}
        self._sweeper: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    def _state(self, game: Game) -> dict:
        st = self._legal_state(game.board)
        st["san"] = list(game.san)
        st["moves"] = list(game.moves)
        rw, rb = game.remaining()
        st["clockW"] = round(rw, 1)
        st["clockB"] = round(rb, 1)
        return st

    async def _finish(self, game: Game, result: str, reason: str) -> None:
        """End a game: persist the server-authoritative Elo change exactly once
        and send each player their {before, after, delta} in the end message."""
        info = None
        if self._apply is not None and not game.rated_done:
            game.rated_done = True
            try:
                info = self._apply(game.uids[chess.WHITE], game.uids[chess.BLACK], result)
            except Exception:
                info = None
        for c in (chess.WHITE, chess.BLACK):
            end = {"type": "end", "result": result, "reason": reason}
            if info:
                end["rating"] = info["white"] if c == chess.WHITE else info["black"]
            await _send(game.ws[c], end)

    async def _start_game(self, a, b) -> None:
        """a/b are (ws, name, rating, uid); colors are assigned randomly."""
        if secrets.randbelow(2):
            a, b = b, a
        game = Game(a[0], a[1], b[0], b[1], a[3], b[3])
        self.games[a[0]] = game
        self.games[b[0]] = game
        game.turn_started = time.monotonic()
        if self._sweeper is None or self._sweeper.done():
            self._sweeper = asyncio.create_task(self._sweep_clocks())
        st = self._state(game)
        await _send(a[0], {"type": "start", "color": "w", "opponent": b[1],
                           "opponentRating": b[2], "state": st})
        await _send(b[0], {"type": "start", "color": "b", "opponent": a[1],
                           "opponentRating": a[2], "state": st})

    def _drop_from_lobby(self, ws: WebSocket) -> None:
        self.queue = [e for e in self.queue if e[0] is not ws]
        self.rooms = {c: e for c, e in self.rooms.items() if e[0] is not ws}

    def _cleanup_game(self, game: Game) -> None:
        for w in (game.ws[chess.WHITE], game.ws[chess.BLACK]):
            if self.games.get(w) is game:
                self.games.pop(w, None)

    # ------------------------------------------------------------------ #
    async def quick(self, ws: WebSocket, name: str, rating: int, uid: str | None = None) -> None:
        async with self.lock:
            if ws in self.games:
                return await _send(ws, {"type": "error", "message": "이미 대국 중입니다."})
            self._drop_from_lobby(ws)          # re-queue cleanly
            if self.queue:
                other = self.queue.pop(0)
                return await self._start_game(other, (ws, name, rating, uid))
            self.queue.append((ws, name, rating, uid))
        await _send(ws, {"type": "waiting"})

    async def create(self, ws: WebSocket, name: str, rating: int, uid: str | None = None) -> None:
        async with self.lock:
            if ws in self.games:
                return await _send(ws, {"type": "error", "message": "이미 대국 중입니다."})
            self._drop_from_lobby(ws)
            code = _new_code(self.rooms)
            self.rooms[code] = (ws, name, rating, uid)
        await _send(ws, {"type": "room", "code": code})

    async def join(self, ws: WebSocket, code: str, name: str, rating: int, uid: str | None = None) -> None:
        async with self.lock:
            if ws in self.games:
                return await _send(ws, {"type": "error", "message": "이미 대국 중입니다."})
            owner = self.rooms.pop(code, None)
            if owner is None:
                return await _send(ws, {"type": "error", "message": "그 코드의 방이 없습니다. 코드를 확인하세요."})
            if owner[0] is ws:
                self.rooms[code] = owner       # can't join your own room
                return await _send(ws, {"type": "error", "message": "자기 방에는 참가할 수 없습니다."})
            self._drop_from_lobby(ws)
            await self._start_game(owner, (ws, name, rating, uid))

    async def cancel(self, ws: WebSocket) -> None:
        async with self.lock:
            self._drop_from_lobby(ws)
        await _send(ws, {"type": "cancelled"})

    # ------------------------------------------------------------------ #
    async def move(self, ws: WebSocket, uci: str) -> None:
        st = None
        result = None                  # set only when the flag falls before this move
        end_result = end_reason = None
        async with self.lock:
            game = self.games.get(ws)
            if game is None or game.over:
                return await _send(ws, {"type": "error", "message": "진행 중인 대국이 없습니다."})
            color = game.color_of(ws)
            if game.board.turn != color:
                return await _send(ws, {"type": "error", "message": "상대 차례입니다."})
            try:
                mv = chess.Move.from_uci(uci)
            except ValueError:
                return await _send(ws, {"type": "error", "message": "잘못된 수 표기입니다."})
            if mv not in game.board.legal_moves:
                return await _send(ws, {"type": "error", "message": "둘 수 없는 수입니다."})
            # clock: charge the mover for their thinking time; a move that
            # arrives after the flag fell loses on time instead of counting.
            now = time.monotonic()
            left = game.clock[color] - (now - game.turn_started)
            if left <= 0:
                game.clock[color] = 0.0
                game.over = True
                self._cleanup_game(game)
                result = "0-1" if color == chess.WHITE else "1-0"
            else:
                game.clock[color] = left
                game.turn_started = now
                game.draw_offer_by = None   # a move withdraws any pending draw offer
                game.san.append(game.board.san(mv))
                game.board.push(mv)
                game.moves.append(uci)
                st = self._state(game)
                if st["gameOver"]:
                    game.over = True
                    self._cleanup_game(game)
                    end_result = st["result"]
                    end_reason = "checkmate" if game.board.is_checkmate() else "draw"
        # flag fell before the move: end on time, no state broadcast
        if st is None:
            return await self._finish(game, result, "timeout")
        payload = {"type": "state", "lastUci": uci, "state": st}
        for c in (chess.WHITE, chess.BLACK):
            await _send(game.ws[c], payload)
        if end_result is not None:
            await self._finish(game, end_result, end_reason)

    async def resign(self, ws: WebSocket) -> None:
        async with self.lock:
            game = self.games.get(ws)
            if game is None or game.over:
                return
            color = game.color_of(ws)
            game.over = True
            self._cleanup_game(game)
        result = "0-1" if color == chess.WHITE else "1-0"
        await self._finish(game, result, "resign")

    async def _sweep_clocks(self) -> None:
        """End games on the clock: if the side to move runs out of time and
        never moves, they lose. Runs once per second while games exist."""
        while True:
            await asyncio.sleep(1.0)
            ended: list[tuple[Game, str]] = []
            async with self.lock:
                for game in set(self.games.values()):
                    if game.over:
                        continue
                    rw, rb = game.remaining()
                    loser = None
                    if game.board.turn == chess.WHITE and rw <= 0:
                        loser = chess.WHITE
                    elif game.board.turn == chess.BLACK and rb <= 0:
                        loser = chess.BLACK
                    if loser is not None:
                        game.over = True
                        self._cleanup_game(game)
                        ended.append((game, "0-1" if loser == chess.WHITE else "1-0"))
                if not self.games and not ended:
                    break                      # idle — stop; restarted on next game
            for game, result in ended:
                await self._finish(game, result, "timeout")

    async def draw_offer(self, ws: WebSocket) -> None:
        agree = False
        other = None
        async with self.lock:
            game = self.games.get(ws)
            if game is None or game.over:
                return
            color = game.color_of(ws)
            # if the opponent already offered, this offer completes the agreement
            if game.draw_offer_by is not None and game.draw_offer_by != color:
                agree = True
            else:
                game.draw_offer_by = color
                other = game.opponent_ws(ws)
        if agree:
            await self._agree_draw(game)
        elif other is not None:
            await _send(other, {"type": "draw_offered"})

    async def draw_accept(self, ws: WebSocket) -> None:
        game = None
        async with self.lock:
            g = self.games.get(ws)
            if g is None or g.over:
                return
            color = g.color_of(ws)
            if g.draw_offer_by is None or g.draw_offer_by == color:
                return   # must be the OTHER side's offer to accept
            game = g
        await self._agree_draw(game)

    async def _agree_draw(self, game: Game) -> None:
        async with self.lock:
            if game.over:
                return
            game.over = True
            self._cleanup_game(game)
        await self._finish(game, "1/2-1/2", "agreement")

    async def draw_decline(self, ws: WebSocket) -> None:
        async with self.lock:
            game = self.games.get(ws)
            if game is None or game.over or game.draw_offer_by is None:
                return
            game.draw_offer_by = None
            other = game.opponent_ws(ws)
        await _send(other, {"type": "draw_declined"})

    async def chat(self, ws: WebSocket, text: str) -> None:
        text = text.strip()[:300]
        if not text:
            return
        async with self.lock:
            game = self.games.get(ws)
            if game is None:
                return
            other = game.opponent_ws(ws)
        await _send(other, {"type": "chat", "text": text})

    async def disconnect(self, ws: WebSocket) -> None:
        game = None
        result = None
        async with self.lock:
            self._drop_from_lobby(ws)
            g = self.games.get(ws)
            if g is not None:
                color = g.color_of(ws)
                self._cleanup_game(g)
                if not g.over:
                    g.over = True
                    game = g
                    # the player who left loses to their opponent
                    result = "1-0" if color == chess.BLACK else "0-1"
        if game is not None:
            await self._finish(game, result, "forfeit")


def register_online(app: FastAPI, legal_state, rating_hooks: dict | None = None) -> Lobby:
    lobby = Lobby(legal_state, rating_hooks)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):  # noqa: ANN001
        await ws.accept()
        try:
            while True:
                try:
                    msg = await ws.receive_json()
                except WebSocketDisconnect:
                    raise
                except Exception:
                    continue               # malformed frame — ignore
                t = msg.get("type")
                name = str(msg.get("name") or "플레이어")[:20].strip() or "플레이어"
                # rating is DISPLAY-ONLY from the client; for logged-in players the
                # server overrides it (and learns their account id) from the token.
                try:
                    rating = max(0, min(4000, int(msg.get("rating") or 400)))
                except (TypeError, ValueError):
                    rating = 400
                uid = None
                if t in ("quick", "create", "join") and lobby._resolve:
                    resolved = lobby._resolve(str(msg.get("token") or ""))
                    if resolved is not None:
                        uid, rating = resolved
                if t == "ping":
                    await _send(ws, {"type": "pong"})
                elif t == "quick":
                    await lobby.quick(ws, name, rating, uid)
                elif t == "create":
                    await lobby.create(ws, name, rating, uid)
                elif t == "join":
                    await lobby.join(ws, str(msg.get("code") or "").strip().upper(), name, rating, uid)
                elif t == "cancel":
                    await lobby.cancel(ws)
                elif t == "move":
                    await lobby.move(ws, str(msg.get("uci") or ""))
                elif t == "resign":
                    await lobby.resign(ws)
                elif t == "draw_offer":
                    await lobby.draw_offer(ws)
                elif t == "draw_accept":
                    await lobby.draw_accept(ws)
                elif t == "draw_decline":
                    await lobby.draw_decline(ws)
                elif t == "chat":
                    await lobby.chat(ws, str(msg.get("text") or ""))
        except WebSocketDisconnect:
            await lobby.disconnect(ws)
        except Exception:
            await lobby.disconnect(ws)

    return lobby

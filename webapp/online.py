"""Online multiplayer: WebSocket matchmaking + move relay.

Design principles:
  * The SERVER is the single authority — every move is validated with
    python-chess and the resulting state (fen, legal-move map, san history,
    game-over) is broadcast to both players. Clients never need chess logic.
  * Two ways to match: a quick-match queue, and 4-letter invite codes for
    playing a specific friend.
  * In-memory state guarded by an asyncio.Lock — fine for the single-process
    deployments we use (uvicorn single worker, locally and on Render).
  * A disconnect mid-game forfeits the game to the opponent.

Wire protocol (JSON messages):
  client -> server:
    {type:"quick",  name}          join the quick-match queue
    {type:"create", name}          create an invite room -> {type:"room", code}
    {type:"join",   name, code}    join a friend's room
    {type:"cancel"}                leave queue / close my room
    {type:"move",   uci}           play a move
    {type:"resign"}                resign the game
    {type:"ping"}                  keepalive -> {type:"pong"}
  server -> client:
    {type:"waiting"}                                queued, looking for opponent
    {type:"room", code}                             invite code created
    {type:"start", color:"w"|"b", opponent, state}  game begins
    {type:"state", lastUci, state}                  after every move
    {type:"end", result:"1-0"|"0-1"|"1/2-1/2", reason}
    {type:"error", message}
"""
from __future__ import annotations

import asyncio
import secrets

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# no 0/O/1/I to keep codes easy to read aloud
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


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
    def __init__(self, w_ws: WebSocket, w_name: str, b_ws: WebSocket, b_name: str):
        self.board = chess.Board()
        self.moves: list[str] = []
        self.san: list[str] = []
        self.ws = {chess.WHITE: w_ws, chess.BLACK: b_ws}
        self.names = {chess.WHITE: w_name, chess.BLACK: b_name}
        self.over = False

    def color_of(self, ws: WebSocket):
        if self.ws[chess.WHITE] is ws:
            return chess.WHITE
        if self.ws[chess.BLACK] is ws:
            return chess.BLACK
        return None

    def opponent_ws(self, ws: WebSocket):
        return self.ws[chess.BLACK] if self.ws[chess.WHITE] is ws else self.ws[chess.WHITE]


class Lobby:
    def __init__(self, legal_state):
        self._legal_state = legal_state   # server.py's board -> state dict
        self.lock = asyncio.Lock()
        # queue entries / rooms values are (ws, name, rating)
        self.queue: list[tuple[WebSocket, str, int]] = []
        self.rooms: dict[str, tuple[WebSocket, str, int]] = {}
        self.games: dict[WebSocket, Game] = {}

    # ------------------------------------------------------------------ #
    def _state(self, game: Game) -> dict:
        st = self._legal_state(game.board)
        st["san"] = list(game.san)
        st["moves"] = list(game.moves)
        return st

    async def _start_game(self, a, b) -> None:
        """a/b are (ws, name, rating); colors are assigned randomly."""
        if secrets.randbelow(2):
            a, b = b, a
        game = Game(a[0], a[1], b[0], b[1])
        self.games[a[0]] = game
        self.games[b[0]] = game
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
    async def quick(self, ws: WebSocket, name: str, rating: int) -> None:
        async with self.lock:
            if ws in self.games:
                return await _send(ws, {"type": "error", "message": "이미 대국 중입니다."})
            self._drop_from_lobby(ws)          # re-queue cleanly
            if self.queue:
                other = self.queue.pop(0)
                return await self._start_game(other, (ws, name, rating))
            self.queue.append((ws, name, rating))
        await _send(ws, {"type": "waiting"})

    async def create(self, ws: WebSocket, name: str, rating: int) -> None:
        async with self.lock:
            if ws in self.games:
                return await _send(ws, {"type": "error", "message": "이미 대국 중입니다."})
            self._drop_from_lobby(ws)
            code = _new_code(self.rooms)
            self.rooms[code] = (ws, name, rating)
        await _send(ws, {"type": "room", "code": code})

    async def join(self, ws: WebSocket, code: str, name: str, rating: int) -> None:
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
            await self._start_game(owner, (ws, name, rating))

    async def cancel(self, ws: WebSocket) -> None:
        async with self.lock:
            self._drop_from_lobby(ws)
        await _send(ws, {"type": "cancelled"})

    # ------------------------------------------------------------------ #
    async def move(self, ws: WebSocket, uci: str) -> None:
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
            game.san.append(game.board.san(mv))
            game.board.push(mv)
            game.moves.append(uci)
            st = self._state(game)
            ended = st["gameOver"]
            if ended:
                game.over = True
                self._cleanup_game(game)
        payload = {"type": "state", "lastUci": uci, "state": st}
        for c in (chess.WHITE, chess.BLACK):
            await _send(game.ws[c], payload)
        if ended:
            reason = "checkmate" if game.board.is_checkmate() else "draw"
            end = {"type": "end", "result": st["result"], "reason": reason}
            for c in (chess.WHITE, chess.BLACK):
                await _send(game.ws[c], end)

    async def resign(self, ws: WebSocket) -> None:
        async with self.lock:
            game = self.games.get(ws)
            if game is None or game.over:
                return
            color = game.color_of(ws)
            game.over = True
            self._cleanup_game(game)
        result = "0-1" if color == chess.WHITE else "1-0"
        end = {"type": "end", "result": result, "reason": "resign"}
        for c in (chess.WHITE, chess.BLACK):
            await _send(game.ws[c], end)

    async def disconnect(self, ws: WebSocket) -> None:
        other = None
        result = None
        async with self.lock:
            self._drop_from_lobby(ws)
            game = self.games.get(ws)
            if game is not None:
                self._cleanup_game(game)
                if not game.over:
                    game.over = True
                    other = game.opponent_ws(ws)
                    result = "1-0" if game.ws[chess.WHITE] is other else "0-1"
        if other is not None:
            await _send(other, {"type": "end", "result": result, "reason": "forfeit"})


def register_online(app: FastAPI, legal_state) -> Lobby:
    lobby = Lobby(legal_state)

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
                try:
                    rating = max(0, min(4000, int(msg.get("rating") or 1200)))
                except (TypeError, ValueError):
                    rating = 1200
                if t == "ping":
                    await _send(ws, {"type": "pong"})
                elif t == "quick":
                    await lobby.quick(ws, name, rating)
                elif t == "create":
                    await lobby.create(ws, name, rating)
                elif t == "join":
                    await lobby.join(ws, str(msg.get("code") or "").strip().upper(), name, rating)
                elif t == "cancel":
                    await lobby.cancel(ws)
                elif t == "move":
                    await lobby.move(ws, str(msg.get("uci") or ""))
                elif t == "resign":
                    await lobby.resign(ws)
        except WebSocketDisconnect:
            await lobby.disconnect(ws)
        except Exception:
            await lobby.disconnect(ws)

    return lobby

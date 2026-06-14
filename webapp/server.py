"""FastAPI backend for Chess Coach Studio.

Features:
  1. Record (play moves on a board) or upload/paste a PGN, then get an engine
     "AI" evaluation of every move played.
  2. Review that evaluation visually (board, eval bar, eval graph, annotated
     move list, engine best-move arrows).
  3. Teach: annotate the recorded line with per-move explanations and
     arrows/highlights, and export a standalone shareable study HTML.

python-chess is the SINGLE source of move legality (`/api/legal`); the browser
never needs its own chess engine, so the whole thing runs offline.

Run:  uvicorn webapp.server:app   (the desktop launcher sets CC_OPEN_BROWSER=1
so the server opens the browser itself once it is ready).
"""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

# Bound how many heavy analyses run at once so a small cloud instance is not
# overwhelmed. Configurable via env (set to 1 on tiny hosts).
_ANALYZE_SEM = threading.Semaphore(int(os.environ.get("CC_MAX_CONCURRENT", "2")))

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chess_coach.config import EngineConfig
from chess_coach.engine import Engine
from chess_coach.analyze import analyze_game_parallel, read_first_game
from chess_coach.visualize import build_view_data, render_study_html
from chess_coach import coach as coach_mod

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # When launched from the desktop shortcut, open the app in the browser as
    # soon as the server is ready (so the user sees the board, not just a console).
    if os.environ.get("CC_OPEN_BROWSER") == "1":
        import threading
        import webbrowser
        port = os.environ.get("PORT", "8000")
        url = f"http://127.0.0.1:{port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    yield


app = FastAPI(title="Chess Challenger", lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class LegalRequest(BaseModel):
    moves: list[str] = []           # UCI moves played so far


class AnalyzeRequest(BaseModel):
    pgn: Optional[str] = None
    moves: Optional[list[str]] = None
    white: str = "White"
    black: str = "Black"
    depth: int = 16
    movetime: Optional[int] = None    # ms per position (preferred; predictable speed)
    coach: bool = False


class AiMoveRequest(BaseModel):
    moves: list[str] = []
    level: int = 5


class PuzzleMoveRequest(BaseModel):
    fen: str
    move: str           # UCI
    mateIn: int         # remaining moves-to-mate target (White to move)


class StudyRequest(BaseModel):
    moves: list[str] = []
    comments: dict[str, str] = {}                 # index ("0".."N") -> text
    shapes: dict[str, dict] = {}                  # index -> {arrows:[[a,b]], circles:[sq]}
    white: str = "White"
    black: str = "Black"
    title: str = "체스 설명 (Chess Study)"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _replay(moves: list[str]) -> chess.Board:
    board = chess.Board()
    for i, u in enumerate(moves):
        try:
            mv = chess.Move.from_uci(u)
        except ValueError:
            raise HTTPException(400, f"잘못된 수 표기: {u} (#{i+1})")
        if mv not in board.legal_moves:
            raise HTTPException(400, f"불법 수: {u} (#{i+1})")
        board.push(mv)
    return board


def _legal_state(board: chess.Board) -> dict:
    legal: dict[str, list[str]] = {}
    for mv in board.legal_moves:
        src = chess.square_name(mv.from_square)
        dst = chess.square_name(mv.to_square)
        legal.setdefault(src, [])
        if dst not in legal[src]:
            legal[src].append(dst)
    over = board.is_game_over(claim_draw=True)
    return {
        "ok": True,
        "fen": board.fen(),
        "turn": "w" if board.turn == chess.WHITE else "b",
        "legal": legal,
        "check": board.is_check(),
        "gameOver": over,
        "result": board.result(claim_draw=True) if over else "*",
        "fullmove": board.fullmove_number,
    }


def _san_history(moves: list[str]) -> list[str]:
    san: list[str] = []
    b = chess.Board()
    for u in moves:
        mv = chess.Move.from_uci(u)
        san.append(b.san(mv))
        b.push(mv)
    return san


def _game_from_moves(moves: list[str], white: str, black: str) -> chess.pgn.Game:
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Chess Coach Studio"
    game.headers["White"] = white or "White"
    game.headers["Black"] = black or "Black"
    node = game
    for u in moves:
        mv = chess.Move.from_uci(u)
        if mv not in board.legal_moves:
            raise HTTPException(400, f"불법 수: {u}")
        node = node.add_variation(mv)
        board.push(mv)
    game.headers["Result"] = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "*"
    return game


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/health")
def health():
    cfg = EngineConfig()
    return {
        "stockfish": bool(cfg.path),
        "stockfishPath": cfg.path,
        "coaching": coach_mod.coaching_available(),
    }


@app.post("/api/legal")
def legal(req: LegalRequest):
    """Validate the moves so far and return the legal-move map for the position."""
    board = _replay(req.moves)
    state = _legal_state(board)
    state["san"] = _san_history(req.moves)
    return state


class FenRequest(BaseModel):
    fen: str


@app.post("/api/legal_fen")
def legal_fen(req: FenRequest):
    """Legal-move map for an arbitrary FEN (used by the puzzle board)."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(400, "잘못된 FEN")
    return _legal_state(board)


@app.post("/api/ai_move")
def ai_move(req: AiMoveRequest):
    """Have the engine play one reply at the given difficulty (1-10).

    Returns the reply move plus the legal-move state AFTER the reply (or move=None
    if the game is already over).
    """
    cfg = EngineConfig()
    if not cfg.path:
        raise HTTPException(500, "Stockfish 바이너리를 찾을 수 없습니다.")
    cfg.threads = 2
    cfg.hash_mb = 64
    cfg.multipv = 1

    board = _replay(req.moves)
    moves = list(req.moves)
    reply_uci = None
    reply_san = None
    if not board.is_game_over(claim_draw=True):
        with Engine(cfg) as eng:
            mv = eng.play(board, req.level)
        if mv is not None:
            reply_san = board.san(mv)
            board.push(mv)
            reply_uci = mv.uci()
            moves.append(reply_uci)

    state = _legal_state(board)
    state["move"] = reply_uci
    state["sanMove"] = reply_san
    state["san"] = _san_history(moves)
    return state


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    cfg = EngineConfig()
    if not cfg.path:
        raise HTTPException(500, "Stockfish 바이너리를 찾을 수 없습니다. STOCKFISH_PATH 설정 필요.")
    # Spread the work over a pool of engines so a full game finishes in a few
    # seconds instead of minutes. Size the pool to the CPU; a per-move time
    # budget keeps wall-clock predictable.
    cfg.multipv = 2          # enables "only good move" detection in explanations
    if req.movetime:
        cfg.movetime_ms = max(50, min(3000, req.movetime))
        cfg.depth = None
    else:
        cfg.depth = max(6, min(24, req.depth))
        cfg.movetime_ms = None

    # Pool size / engine resources are env-configurable so the same image runs
    # on a 12-core dev box and a 1-vCPU cloud instance (set CC_WORKERS=2,
    # CC_ENGINE_THREADS=1, CC_ENGINE_HASH_MB=32 on tiny hosts).
    total = os.cpu_count() or 4
    workers = int(os.environ.get("CC_WORKERS", max(2, min(6, total // 2))))
    cfg.threads = int(os.environ.get("CC_ENGINE_THREADS", max(1, total // max(1, workers))))
    cfg.hash_mb = int(os.environ.get("CC_ENGINE_HASH_MB", 128))   # per engine

    if req.pgn and req.pgn.strip():
        game = read_first_game(req.pgn)
        if game is None or not list(game.mainline_moves()):
            raise HTTPException(400, "PGN에서 유효한 게임을 찾지 못했습니다.")
    elif req.moves:
        game = _game_from_moves(req.moves, req.white, req.black)
        if not list(game.mainline_moves()):
            raise HTTPException(400, "분석할 수가 없습니다. 먼저 수를 두거나 PGN을 입력하세요.")
    else:
        raise HTTPException(400, "pgn 또는 moves 중 하나는 필요합니다.")

    with _ANALYZE_SEM:                       # bound concurrent heavy analyses
        engines = [Engine(cfg) for _ in range(workers)]
        for e in engines:
            e.open()
        try:
            ga = analyze_game_parallel(game, engines)
        finally:
            for e in engines:
                e.close()
    view = build_view_data(game, ga)

    if req.coach:
        view["coach"] = coach_mod.generate_coaching(view)
    else:
        view["coach"] = {"available": coach_mod.coaching_available()}
    return JSONResponse(view)


@app.post("/api/puzzle_move")
def puzzle_move(req: PuzzleMoveRequest):
    """Verify a move in a mate-in-N puzzle and, if correct, play the best defense.

    The move is correct if it delivers mate (when 1 left) or keeps a forced mate
    in the remaining number of moves. On a correct non-final move the engine
    plays the defender's best (longest) reply and returns the new position.
    """
    cfg = EngineConfig()
    if not cfg.path:
        raise HTTPException(500, "Stockfish 바이너리를 찾을 수 없습니다.")
    cfg.threads = 2
    cfg.hash_mb = 64
    cfg.multipv = 1
    cfg.depth = 22
    cfg.movetime_ms = None

    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(400, "잘못된 FEN")
    try:
        mv = chess.Move.from_uci(req.move)
    except ValueError:
        raise HTTPException(400, "잘못된 수")
    if mv not in board.legal_moves:
        return {"ok": True, "correct": False, "reason": "illegal"}

    user_san = board.san(mv)
    board.push(mv)
    user_fen = board.fen()
    if board.is_checkmate():
        return {"ok": True, "correct": True, "solved": True,
                "userSan": user_san, "userFen": user_fen, "fen": user_fen}

    # Defender to move: must be getting mated in (mateIn - 1).
    target = max(0, req.mateIn - 1)
    with Engine(cfg) as eng:
        pe = eng.evaluate(board)
    ok = (pe.mate is not None and pe.mate < 0 and 1 <= (-pe.mate) <= target)
    if not ok:
        return {"ok": True, "correct": False, "userSan": user_san}

    # Correct — play the defender's best (longest) reply.
    reply = pe.best_move
    reply_san = board.san(reply) if reply else None
    if reply is not None:
        board.push(reply)
    return {
        "ok": True, "correct": True, "solved": False,
        "userSan": user_san, "userFen": user_fen,
        "replyUci": reply.uci() if reply else None,
        "replySan": reply_san, "fen": board.fen(),
        "mateIn": req.mateIn - 1, "check": board.is_check(),
    }


@app.post("/api/study_html", response_class=PlainTextResponse)
def study_html(req: StudyRequest):
    """Bake the annotated line into a standalone, shareable HTML document."""
    _replay(req.moves)  # validate
    html = render_study_html(
        moves=req.moves,
        comments=req.comments,
        shapes=req.shapes,
        white=req.white,
        black=req.black,
        title=req.title,
    )
    return PlainTextResponse(html, media_type="text/html; charset=utf-8")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port)

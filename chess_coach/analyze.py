"""Game analysis pipeline: PGN -> per-move engine evaluation -> CPL -> class.

Sign convention
---------------
* Engine scores are taken from the side-to-move's POV (relative).
* CPL is always computed from the MOVER's POV (best - played, clamped >= 0).
* For display / eval graphs we also expose a White-POV centipawn number.

Efficiency
----------
A game with N plies has N+1 distinct positions. Each position is evaluated
exactly once; the "after" eval of ply i is the same board as the "before" eval
of ply i+1, so we reuse it (with a sign flip) instead of re-querying the engine.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field, asdict
from typing import Optional

import chess
import chess.pgn

from .config import EngineConfig, ClassifyConfig
from .engine import Engine, PositionEval
from .winprob import win_prob_from_score, move_accuracy
from .classify import classify_move, Classification


@dataclass
class MoveAnalysis:
    ply: int                       # 1-based half-move index
    move_number: int               # full-move number
    color: str                     # "white" | "black"
    san: str
    uci: str
    fen_before: str

    # engine numbers (eval AFTER the move, White POV — for eval bars/graphs)
    eval_cp: Optional[int]
    eval_mate: Optional[int]

    best_move_san: Optional[str]
    best_move_uci: Optional[str]
    pv: list[str]

    cpl: int                       # centipawn loss, mover POV
    win_prob_before: float         # mover POV, 0..100
    win_prob_after: float          # mover POV, 0..100
    accuracy: float                # this move, 0..100

    classification: str
    symbol: str
    missed_win: bool
    is_best: bool

    # move facts (python-chess, for grounded natural-language explanations)
    is_capture: bool = False
    is_castle: bool = False
    is_promotion: bool = False
    gives_check: bool = False
    is_mate: bool = False
    best_is_capture: bool = False
    best_is_check: bool = False
    captured_piece: Optional[str] = None     # Korean name of piece this move captured
    reply_san: Optional[str] = None          # opponent's best reply after this move
    reply_captures: Optional[str] = None      # Korean name of piece that reply would win
    only_move: bool = False                  # best move and clearly the only good one
    piece_moved: Optional[str] = None        # Korean name of the piece that moved
    develops: bool = False                   # an opening developing move (N/B off back rank)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SideStats:
    color: str
    moves: int = 0
    acpl: float = 0.0
    accuracy: float = 0.0
    counts: dict = field(default_factory=dict)   # classification -> n


@dataclass
class GameAnalysis:
    headers: dict
    engine: dict                   # reproducibility fingerprint
    moves: list[MoveAnalysis]
    white: SideStats
    black: SideStats
    result: str

    def to_dict(self) -> dict:
        return {
            "headers": self.headers,
            "engine": self.engine,
            "result": self.result,
            "white": asdict(self.white),
            "black": asdict(self.black),
            "moves": [m.to_dict() for m in self.moves],
        }


_KOR_PIECE = {
    chess.PAWN: "폰", chess.KNIGHT: "나이트", chess.BISHOP: "비숍",
    chess.ROOK: "룩", chess.QUEEN: "퀸", chess.KING: "킹",
}


def _captured_name(board: chess.Board, mv: chess.Move) -> Optional[str]:
    """Korean name of the piece captured by `mv` on `board` (None if not a capture)."""
    if not board.is_capture(mv):
        return None
    if board.is_en_passant(mv):
        return "폰"
    pc = board.piece_at(mv.to_square)
    return _KOR_PIECE.get(pc.piece_type) if pc else None


_PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def _material_pov(board: chess.Board, mover_is_white: bool) -> int:
    """Total material from the mover's point of view (positive = mover ahead)."""
    s = 0
    for pt, v in _PIECE_VALUE.items():
        s += v * (len(board.pieces(pt, chess.WHITE)) - len(board.pieces(pt, chess.BLACK)))
    return s if mover_is_white else -s


def _mp_signed(entry: dict, mate_value: int = 100_000) -> int:
    """Signed centipawns for a multipv entry (mover POV)."""
    if entry.get("mate") is not None:
        m = entry["mate"]
        base = mate_value - abs(m) * 100
        return base if m > 0 else -base
    return entry.get("cp") or 0


def _white_pov(pe: PositionEval, turn: bool) -> tuple[Optional[int], Optional[int]]:
    """Convert a mover-POV (cp, mate) to White's POV given whose turn it is."""
    sign = 1 if turn == chess.WHITE else -1
    cp = None if pe.cp is None else sign * pe.cp
    mate = None if pe.mate is None else sign * pe.mate
    return cp, mate


def build_boards(game: chess.pgn.Game) -> list[chess.Board]:
    """The N+1 distinct positions of the game (start + after each ply)."""
    board = game.board()
    boards = [board.copy()]
    for mv in game.mainline_moves():
        board.push(mv)
        boards.append(board.copy())
    return boards


def evaluate_boards_parallel(boards: list[chess.Board], engines: list[Engine]) -> list[PositionEval]:
    """Evaluate every position once, spread across a pool of engines.

    Each engine is used by at most one worker at a time (one-engine-per-thread
    via a queue), so the separate Stockfish subprocesses run concurrently. With
    a per-move time budget, wall-clock ~= ceil(positions / engines) * movetime.
    """
    import queue
    from concurrent.futures import ThreadPoolExecutor

    if len(engines) == 1:
        return [engines[0].evaluate(b) for b in boards]

    pool: "queue.Queue[Engine]" = queue.Queue()
    for e in engines:
        pool.put(e)
    results: list[PositionEval | None] = [None] * len(boards)

    def work(idx_board):
        idx, b = idx_board
        eng = pool.get()
        try:
            results[idx] = eng.evaluate(b)
        finally:
            pool.put(eng)

    with ThreadPoolExecutor(max_workers=len(engines)) as ex:
        list(ex.map(work, list(enumerate(boards))))
    return [r for r in results]  # type: ignore[return-value]


def analyze_game(
    game: chess.pgn.Game,
    engine: Engine,
    classify_cfg: ClassifyConfig | None = None,
) -> GameAnalysis:
    boards = build_boards(game)
    evals = [engine.evaluate(b) for b in boards]
    return _assemble(game, boards, evals, engine.config.describe(), classify_cfg)


def analyze_game_parallel(
    game: chess.pgn.Game,
    engines: list[Engine],
    classify_cfg: ClassifyConfig | None = None,
) -> GameAnalysis:
    """Same as analyze_game but spreads position evaluation over an engine pool."""
    boards = build_boards(game)
    evals = evaluate_boards_parallel(boards, engines)
    desc = engines[0].config.describe()
    desc["workers"] = len(engines)
    return _assemble(game, boards, evals, desc, classify_cfg)


def _assemble(
    game: chess.pgn.Game,
    boards: list[chess.Board],
    evals: list[PositionEval],
    engine_desc: dict,
    classify_cfg: ClassifyConfig | None = None,
) -> GameAnalysis:
    classify_cfg = classify_cfg or ClassifyConfig()
    moves = list(game.mainline_moves())

    # Walk the moves, deriving CPL / win% / class from adjacent evals.
    analyses: list[MoveAnalysis] = []
    replay = game.board()

    for i, mv in enumerate(moves):
        before_board = boards[i]
        mover_is_white = before_board.turn == chess.WHITE

        eval_before = evals[i]          # mover POV at position i
        eval_after = evals[i + 1]       # OPPONENT POV at position i+1

        # mover-POV signed centipawns, capped so mate scores don't explode ACPL
        cp_before = eval_before.capped_cp()
        cp_after = -eval_after.capped_cp()           # flip to mover POV
        cpl = max(0, cp_before - cp_after)

        win_before = win_prob_from_score(eval_before.cp, eval_before.mate)
        win_after = 100.0 - win_prob_from_score(eval_after.cp, eval_after.mate)

        is_best = (eval_before.best_move is not None and mv == eval_before.best_move)
        cls: Classification = classify_move(
            cpl=cpl,
            win_before=win_before,
            win_after=win_after,
            is_best=is_best,
            cfg=classify_cfg,
        )

        # eval AFTER the move, White POV (for graphs / eval bar)
        w_cp, w_mate = _white_pov(eval_after, boards[i + 1].turn)

        # move facts (computed on the position before the move was played)
        is_capture = before_board.is_capture(mv)
        is_castle = before_board.is_castling(mv)
        is_promotion = mv.promotion is not None
        gives_check = before_board.gives_check(mv)
        is_mate = boards[i + 1].is_checkmate()
        best_mv = eval_before.best_move
        best_is_capture = bool(best_mv and before_board.is_capture(best_mv))
        best_is_check = bool(best_mv and before_board.gives_check(best_mv))

        captured_piece = _captured_name(before_board, mv)
        moved_pt = before_board.piece_type_at(mv.from_square)
        piece_moved = _KOR_PIECE.get(moved_pt) if moved_pt else None
        develops = (
            moved_pt in (chess.KNIGHT, chess.BISHOP)
            and chess.square_rank(mv.from_square) in (0, 7)
            and before_board.fullmove_number <= 12
            and not is_capture
        )

        # opponent's best reply (the position after the move was already evaluated)
        after_board = boards[i + 1]
        reply_mv = eval_after.best_move
        reply_san = eval_after.best_move_san
        reply_captures = _captured_name(after_board, reply_mv) if reply_mv else None

        # "only good move": this move is best and the 2nd choice is much worse
        only_move = False
        mp = eval_before.multipv
        if is_best and len(mp) >= 2:
            gap = _mp_signed(mp[0]) - _mp_signed(mp[1])
            only_move = gap >= 130   # ~1.3 pawns / points

        # Upgrade a best move to Great (완벽) or Brilliant (놀라움).
        #   Brilliant = a sound sacrifice: best move that nets away >= a minor
        #               piece (after the opponent's best reply) yet stays winning.
        #   Great     = the single only-good move in the position.
        if is_best and cls.label in ("Best", "Excellent"):
            sac = 0
            try:
                if reply_mv is not None:
                    _ab = after_board.copy(stack=False)
                    _ab.push(reply_mv)
                    sac = _material_pov(before_board, mover_is_white) - _material_pov(_ab, mover_is_white)
            except Exception:
                sac = 0
            if sac >= 2 and win_after >= 55.0:
                cls = Classification("Brilliant", "!!", cls.missed_win)
            elif only_move:
                cls = Classification("Great", "!", cls.missed_win)

        san = replay.san(mv)
        replay.push(mv)

        analyses.append(MoveAnalysis(
            ply=i + 1,
            move_number=before_board.fullmove_number,
            color="white" if mover_is_white else "black",
            san=san,
            uci=mv.uci(),
            fen_before=before_board.fen(),
            eval_cp=w_cp,
            eval_mate=w_mate,
            best_move_san=eval_before.best_move_san,
            best_move_uci=eval_before.best_move.uci() if eval_before.best_move else None,
            pv=eval_before.pv,
            cpl=cpl,
            win_prob_before=round(win_before, 2),
            win_prob_after=round(win_after, 2),
            accuracy=round(move_accuracy(win_before, win_after), 1),
            classification=cls.label,
            symbol=cls.symbol,
            missed_win=cls.missed_win,
            is_best=is_best,
            is_capture=is_capture,
            is_castle=is_castle,
            is_promotion=is_promotion,
            gives_check=gives_check,
            is_mate=is_mate,
            best_is_capture=best_is_capture,
            best_is_check=best_is_check,
            captured_piece=captured_piece,
            reply_san=reply_san,
            reply_captures=reply_captures,
            only_move=only_move,
            piece_moved=piece_moved,
            develops=develops,
        ))

    white = _aggregate(analyses, "white")
    black = _aggregate(analyses, "black")

    return GameAnalysis(
        headers=dict(game.headers),
        engine=engine_desc,
        moves=analyses,
        white=white,
        black=black,
        result=game.headers.get("Result", "*"),
    )


def _aggregate(moves: list[MoveAnalysis], color: str) -> SideStats:
    side = [m for m in moves if m.color == color]
    stats = SideStats(color=color, moves=len(side))
    if not side:
        return stats
    stats.acpl = round(sum(m.cpl for m in side) / len(side), 1)
    stats.accuracy = round(sum(m.accuracy for m in side) / len(side), 1)
    counts: dict[str, int] = {}
    for m in side:
        counts[m.classification] = counts.get(m.classification, 0) + 1
    stats.counts = counts
    return stats


# --------------------------------------------------------------------------- #
# PGN helpers
# --------------------------------------------------------------------------- #
def read_first_game(pgn_text: str) -> Optional[chess.pgn.Game]:
    return chess.pgn.read_game(io.StringIO(pgn_text))


def read_game_from_file(path: str) -> Optional[chess.pgn.Game]:
    with open(path, "r", encoding="utf-8") as fh:
        return chess.pgn.read_game(fh)

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


def _white_pov(pe: PositionEval, turn: bool) -> tuple[Optional[int], Optional[int]]:
    """Convert a mover-POV (cp, mate) to White's POV given whose turn it is."""
    sign = 1 if turn == chess.WHITE else -1
    cp = None if pe.cp is None else sign * pe.cp
    mate = None if pe.mate is None else sign * pe.mate
    return cp, mate


def analyze_game(
    game: chess.pgn.Game,
    engine: Engine,
    classify_cfg: ClassifyConfig | None = None,
) -> GameAnalysis:
    classify_cfg = classify_cfg or ClassifyConfig()

    board = game.board()
    moves = list(game.mainline_moves())

    # 1) Collect the N+1 positions and evaluate each exactly once.
    boards: list[chess.Board] = [board.copy()]
    for mv in moves:
        board.push(mv)
        boards.append(board.copy())

    evals: list[PositionEval] = [engine.evaluate(b) for b in boards]

    # 2) Walk the moves, deriving CPL / win% / class from adjacent evals.
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
        ))

    white = _aggregate(analyses, "white")
    black = _aggregate(analyses, "black")

    return GameAnalysis(
        headers=dict(game.headers),
        engine=engine.config.describe(),
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

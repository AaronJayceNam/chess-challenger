"""Stockfish UCI wrapper.

This is the ONLY source of evaluations, best moves and PVs in the whole system.
Everything is returned from the side-to-move's point of view (relative score),
so the pipeline never has to juggle White/Black sign conventions per ply.
"""
from __future__ import annotations

import os
import random
import subprocess
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine


# 10-step difficulty ladder. The low levels are deliberately very weak: most of
# their moves are picked completely at random (a beginner can win easily), and
# the random share drops in big steps so the gap between levels is large. The
# engine's own strength (UCI_Elo, floored at 1320 by Stockfish) only starts to
# matter from the middle of the ladder, reaching full strength at level 10.
#   rand = probability of playing a uniformly random legal move this turn
#   elo  = UCI_Elo when the engine does move (None = full strength)
_LADDER = {
    1:  {"rand": 0.85, "elo": 1320},
    2:  {"rand": 0.70, "elo": 1320},
    3:  {"rand": 0.55, "elo": 1320},
    4:  {"rand": 0.40, "elo": 1320},
    5:  {"rand": 0.27, "elo": 1350},
    6:  {"rand": 0.15, "elo": 1450},
    7:  {"rand": 0.06, "elo": 1600},
    8:  {"rand": 0.00, "elo": 1850},
    9:  {"rand": 0.00, "elo": 2200},
    10: {"rand": 0.00, "elo": None},
}
_MAX_LEVEL = 10


def _no_window_popen_args() -> dict:
    """On Windows, launch the Stockfish console subprocess without flashing a
    console window each time (this otherwise appears on every AI move/analysis)."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}

from .config import EngineConfig


@dataclass
class PositionEval:
    """Engine verdict for one position, from the side-to-move's POV."""
    cp: Optional[int]            # centipawns, mover POV (None if mate score)
    mate: Optional[int]          # mate-in-N, mover POV (None if cp score)
    best_move: Optional[chess.Move]
    best_move_san: Optional[str]
    pv: list[str]                # principal variation, SAN
    pv_uci: list[str]            # principal variation, UCI
    multipv: list[dict]          # top-N candidate lines (when multipv > 1)

    def signed_cp(self, mate_value: int = 100_000) -> int:
        """Collapse to a single signed centipawn number for arithmetic.

        Mate scores map to a large magnitude that still preserves "mate sooner is
        better": mate in 1 > mate in 5. Use this for ordering/comparisons.
        """
        if self.mate is not None:
            base = mate_value - abs(self.mate) * 100
            return base if self.mate > 0 else -base
        return self.cp if self.cp is not None else 0

    def capped_cp(self, cap: int = 1000) -> int:
        """Signed centipawns clamped to +/- cap, for CPL/ACPL arithmetic.

        Once a side is up ~10 pawns the position is already won; raw mate scores
        (~100000) otherwise explode the centipawn-loss average. Mate maps to the
        cap. (Lichess uses the same 1000cp ceiling for ACPL.)
        """
        if self.mate is not None:
            return cap if self.mate > 0 else -cap
        if self.cp is None:
            return 0
        return max(-cap, min(cap, self.cp))


class Engine:
    """Context-managed Stockfish session."""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        if not self.config.path:
            raise FileNotFoundError(
                "Stockfish binary not found. Set STOCKFISH_PATH in your .env or "
                "install Stockfish (see README)."
            )
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "Engine":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        self._engine = chess.engine.SimpleEngine.popen_uci(
            self.config.path, **_no_window_popen_args())
        opts = {}
        if self.config.threads:
            opts["Threads"] = self.config.threads
        if self.config.hash_mb:
            opts["Hash"] = self.config.hash_mb
        if opts:
            self._engine.configure(opts)

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    # ------------------------------------------------------------------ #
    def _limit(self) -> chess.engine.Limit:
        if self.config.movetime_ms:
            return chess.engine.Limit(time=self.config.movetime_ms / 1000.0)
        return chess.engine.Limit(depth=self.config.depth or 18)

    def play(self, board: chess.Board, level: int, style: str = None) -> Optional[chess.Move]:
        """Pick a move at difficulty `level` (1=weakest .. 10=hardest).

        See `_LADDER`: low levels mostly play random moves (very beginner-
        friendly, with large gaps between levels), higher levels tighten toward
        full engine strength at level 10.

        `style` (optional) makes the engine play a famous-player persona at full
        strength — see _play_styled. Only used in AI matches.
        """
        assert self._engine is not None, "Engine not opened"
        level = max(1, min(_MAX_LEVEL, level))
        if style and style != "default":
            return self._play_styled(board, style)
        cfg = _LADDER[level]
        # weakest levels: often just blunder a random legal move
        if cfg["rand"] and random.random() < cfg["rand"]:
            moves = list(board.legal_moves)
            if moves:
                return random.choice(moves)
        try:
            if cfg["elo"] is not None:
                self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": cfg["elo"]})
            else:
                self._engine.configure({"UCI_LimitStrength": False})
        except chess.engine.EngineError:
            pass  # option unsupported -> just play full strength
        movetime = 1200 if cfg["elo"] is None else 160
        result = self._engine.play(board, chess.engine.Limit(time=movetime / 1000.0))
        return result.move

    def _play_styled(self, board: chess.Board, style: str) -> Optional[chess.Move]:
        """Play a strong move biased toward a famous player's style.

        Get several near-best candidate moves (multipv) and pick among the ones
        within an acceptable centipawn loss, biased by persona:
          tal        — attacking/sacrificial (captures, checks, giving up material)
          fischer    — the objective best (classical precision)
          carlsen    — solid & practical, leans to quiet safe moves
          petrosian  — defensive/prophylactic, prefers quiet non-captures
        """
        try:
            self._engine.configure({"UCI_LimitStrength": False})
        except chess.engine.EngineError:
            pass
        window = 90 if style == "tal" else 45 if style in ("carlsen", "petrosian") else 20
        info = self._engine.analyse(board, chess.engine.Limit(time=0.5), multipv=6)
        if isinstance(info, dict):
            info = [info]
        scored = []
        for it in info:
            pv = it.get("pv") or []
            if not pv:
                continue
            sc = it["score"].relative.score(mate_score=100000)
            scored.append((pv[0], sc if sc is not None else -100000))
        if not scored:
            return self._engine.play(board, chess.engine.Limit(time=0.4)).move
        best = scored[0][1]
        cands = [mv for mv, sc in scored if best - sc <= window] or [scored[0][0]]

        def is_sac(mv):
            b2 = board.copy(stack=False); b2.push(mv)
            # a quiet move into a square the opponent attacks = offering material
            return board.is_capture(mv) is False and b2.is_attacked_by(not board.turn, mv.to_square)

        if style == "tal":
            cands.sort(key=lambda m: (board.is_capture(m) or board.gives_check(m) or is_sac(m)), reverse=True)
        elif style in ("carlsen", "petrosian"):
            cands.sort(key=lambda m: (not board.is_capture(m)) and (not board.gives_check(m)), reverse=True)
        # fischer / default: keep best-first order
        return cands[0]

    def evaluate(self, board: chess.Board) -> PositionEval:
        """Analyse a position. Returns a mover-POV PositionEval.

        Terminal positions (checkmate / stalemate / draw) are handled without
        calling the engine so we never feed it a game-over board.
        """
        assert self._engine is not None, "Engine not opened"

        if board.is_checkmate():
            # Side to move is mated: a forced loss "in 0".
            return PositionEval(cp=None, mate=0, best_move=None, best_move_san=None,
                                pv=[], pv_uci=[], multipv=[])
        if board.is_stalemate() or board.is_insufficient_material() or \
                board.is_seventyfive_moves() or board.is_fivefold_repetition():
            return PositionEval(cp=0, mate=None, best_move=None, best_move_san=None,
                                pv=[], pv_uci=[], multipv=[])

        multipv_n = max(1, self.config.multipv)
        infos = self._engine.analyse(board, self._limit(), multipv=multipv_n)
        if isinstance(infos, dict):  # multipv=1 returns a single InfoDict
            infos = [infos]

        top = infos[0]
        score = top["score"].relative  # mover POV
        cp = score.score()             # int or None
        mate = score.mate()            # int or None

        pv_moves = top.get("pv", []) or []
        best_move = pv_moves[0] if pv_moves else None

        pv_san = _variation_to_san(board, pv_moves)
        pv_uci = [m.uci() for m in pv_moves]

        candidates = []
        for info in infos:
            s = info["score"].relative
            line = info.get("pv", []) or []
            candidates.append({
                "cp": s.score(),
                "mate": s.mate(),
                "move": line[0].uci() if line else None,
                "move_san": board.san(line[0]) if line else None,
                "pv": _variation_to_san(board, line),
            })

        return PositionEval(
            cp=cp,
            mate=mate,
            best_move=best_move,
            best_move_san=board.san(best_move) if best_move else None,
            pv=pv_san,
            pv_uci=pv_uci,
            multipv=candidates,
        )


def _variation_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    """Render a UCI move list as SAN by replaying on a board copy."""
    san: list[str] = []
    b = board.copy(stack=False)
    for mv in moves:
        try:
            san.append(b.san(mv))
            b.push(mv)
        except (ValueError, AssertionError):
            break
    return san

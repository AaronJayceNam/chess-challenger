"""Stockfish UCI wrapper.

This is the ONLY source of evaluations, best moves and PVs in the whole system.
Everything is returned from the side-to-move's point of view (relative score),
so the pipeline never has to juggle White/Black sign conventions per ply.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine


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

    def play(self, board: chess.Board, level: int) -> Optional[chess.Move]:
        """Pick a move at difficulty `level` (1=weakest .. 10=full strength).

        Levels 1-9 cap the engine with UCI_LimitStrength/UCI_Elo (≈1320..2700);
        level 10 plays at full strength. A small per-level time budget keeps the
        reply snappy for interactive play.
        """
        assert self._engine is not None, "Engine not opened"
        level = max(1, min(10, level))
        try:
            if level >= 10:
                self._engine.configure({"UCI_LimitStrength": False})
            else:
                elo = int(round(1320 + (level - 1) / 8 * (2700 - 1320)))
                self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
        except chess.engine.EngineError:
            pass  # option unsupported -> just play full strength
        limit = chess.engine.Limit(time=(120 + level * 40) / 1000.0)
        result = self._engine.play(board, limit)
        return result.move

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

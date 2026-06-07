"""Centipawn <-> win-probability <-> accuracy conversions.

These are well-known community approximations (Lichess / Chess.com style), NOT
official numbers. They are isolated here so thresholds and formulae can be tuned
without touching the analysis pipeline.
"""
from __future__ import annotations

import math

# Beyond this, the sigmoid is saturated; clamp to keep numbers sane.
_CP_CLAMP = 2000


def win_prob_from_cp(cp: float) -> float:
    """Win probability (0..100) for the side to move, given centipawns from that
    side's point of view.

    Lichess-style logistic:  Win% = 50 + 50 * (2/(1+exp(-0.00368208*cp)) - 1)
    """
    cp = max(-_CP_CLAMP, min(_CP_CLAMP, cp))
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def win_prob_from_score(cp: int | None, mate: int | None) -> float:
    """Win probability (0..100, mover POV) from a possibly-mate score.

    `cp` and `mate` are mutually exclusive: exactly one is non-None, both taken
    from the mover's point of view (positive = good for mover).
    """
    if mate is not None:
        # Mate for us -> certain win; mate against us -> certain loss.
        return 100.0 if mate > 0 else 0.0
    if cp is None:
        return 50.0
    return win_prob_from_cp(cp)


def move_accuracy(win_before: float, win_after: float) -> float:
    """Per-move accuracy (0..100) from the mover's win% before/after the move.

    Chess.com-style approximation:
        accuracy = 103.1668 * exp(-0.04354 * (winBefore - winAfter)) - 3.1669
    A move that does not lose win probability scores ~100.
    """
    drop = max(0.0, win_before - win_after)
    acc = 103.1668 * math.exp(-0.04354 * drop) - 3.1669
    return max(0.0, min(100.0, acc))

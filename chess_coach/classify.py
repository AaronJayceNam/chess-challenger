"""Move classification.

Primary signal is win-probability drop (more meaningful than raw centipawns when
the position is already winning/losing); centipawn-loss bands provide the fine
gradations (Best / Excellent / Good). Great/Brilliant/Book detection arrives in
M2 — they need sacrifice + tactic context that M1 doesn't compute yet.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import ClassifyConfig


# NAG-ish symbols used in the move list.
SYMBOLS = {
    "Brilliant": "!!",
    "Great": "!",
    "Best": "",
    "Excellent": "",
    "Good": "",
    "Inaccuracy": "?!",
    "Mistake": "?",
    "Blunder": "??",
}


@dataclass
class Classification:
    label: str
    symbol: str
    missed_win: bool = False


def classify_move(
    *,
    cpl: int,
    win_before: float,
    win_after: float,
    is_best: bool,
    cfg: ClassifyConfig | None = None,
) -> Classification:
    """Classify a single move from the mover's perspective.

    cpl        centipawn loss (>= 0), best - played.
    win_before mover win% before the move.
    win_after  mover win% after the move.
    is_best    whether the played move equalled the engine's first choice.
    """
    cfg = cfg or ClassifyConfig()
    drop = max(0.0, win_before - win_after)

    # "Missed win": was clearly winning, threw most of it away.
    missed_win = win_before >= 80.0 and win_after < 50.0

    if is_best or cpl <= cfg.best_cp:
        label = "Best"
    elif drop >= cfg.blunder_wp or cpl >= cfg.blunder_cp:
        label = "Blunder"
    elif drop >= cfg.mistake_wp or cpl >= cfg.mistake_cp:
        label = "Mistake"
    elif drop >= cfg.inaccuracy_wp or cpl >= cfg.inaccuracy_cp:
        label = "Inaccuracy"
    elif cpl <= cfg.excellent_cp:
        label = "Excellent"
    else:
        label = "Good"

    return Classification(label=label, symbol=SYMBOLS[label], missed_win=missed_win)

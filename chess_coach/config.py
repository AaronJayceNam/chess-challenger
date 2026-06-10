"""Configuration & Stockfish auto-detection.

All knobs live here so analysis is reproducible: the engine settings and
classification thresholds used for a report are explicit and recorded.
"""
from __future__ import annotations

import os
import shutil
import glob
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional
    pass


# --------------------------------------------------------------------------- #
# Stockfish discovery
# --------------------------------------------------------------------------- #
def _candidate_stockfish_paths() -> list[str]:
    paths: list[str] = []

    # 1. Explicit override
    env = os.environ.get("STOCKFISH_PATH")
    if env:
        paths.append(env)

    # 2. On PATH (covers Homebrew, apt, manual installs)
    for name in ("stockfish", "stockfish.exe"):
        found = shutil.which(name)
        if found:
            paths.append(found)

    # 3. winget package dir (Windows)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pattern = os.path.join(
            local, "Microsoft", "WinGet", "Packages",
            "Stockfish.Stockfish_*", "stockfish", "stockfish-*.exe",
        )
        paths.extend(sorted(glob.glob(pattern)))

    # 4. Common Homebrew / Linux locations (Debian's apt package installs to
    #    /usr/games/stockfish — used by the Docker image)
    paths += [
        "/usr/games/stockfish",
        "/opt/homebrew/bin/stockfish",
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
    ]

    # 5. Project-local ./engines/
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths.extend(sorted(glob.glob(os.path.join(here, "engines", "stockfish*"))))

    return paths


def find_stockfish() -> Optional[str]:
    for p in _candidate_stockfish_paths():
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
        # On Windows os.access X_OK is lenient; accept any existing .exe
        if p and os.path.isfile(p) and p.lower().endswith(".exe"):
            return p
    return None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _opt_int_env(name: str) -> Optional[int]:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Engine settings
# --------------------------------------------------------------------------- #
@dataclass
class EngineConfig:
    path: Optional[str] = field(default_factory=find_stockfish)
    depth: Optional[int] = field(default_factory=lambda: _int_env("ENGINE_DEPTH", 18))
    movetime_ms: Optional[int] = field(default_factory=lambda: _opt_int_env("ENGINE_MOVETIME_MS"))
    threads: int = field(default_factory=lambda: _int_env("ENGINE_THREADS", 1))
    hash_mb: int = field(default_factory=lambda: _int_env("ENGINE_HASH_MB", 128))
    multipv: int = field(default_factory=lambda: _int_env("ENGINE_MULTIPV", 1))

    def describe(self) -> dict:
        """Reproducibility fingerprint stored alongside reports."""
        d = asdict(self)
        d["engine"] = "stockfish"
        return d


# --------------------------------------------------------------------------- #
# Classification thresholds (tunable; not official — see README)
# --------------------------------------------------------------------------- #
@dataclass
class ClassifyConfig:
    # centipawn-loss bands (mover POV), used for the fine gradations
    excellent_cp: int = 20
    good_cp: int = 50
    inaccuracy_cp: int = 100
    mistake_cp: int = 200      # >= mistake_cp .. < blunder_cp  => mistake
    blunder_cp: int = 300      # >= blunder_cp                  => blunder (cp fallback)

    # win-probability-drop bands (0..100 scale, mover POV). PRIMARY classifier.
    inaccuracy_wp: float = 10.0
    mistake_wp: float = 20.0
    blunder_wp: float = 30.0

    # a move is "best" if its CPL is within this slack of 0
    best_cp: int = 10


DEFAULT_ENGINE = EngineConfig
DEFAULT_CLASSIFY = ClassifyConfig

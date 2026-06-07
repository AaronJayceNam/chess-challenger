# chess-coach

Record/import chess games and get **engine-accurate analysis + AI coaching**.

> **Core design principle — "Engine for numbers, LLM for words."**
> Every evaluation, best move, principal variation and centipawn-loss number
> comes **only** from the Stockfish engine. The LLM layer (added in M3) merely
> narrates the engine's structured output — it never invents evaluations or
> variations. All moves are validated for legality with `python-chess`.

## Roadmap / milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| **M1** | Scaffold + python-chess PGN parsing + Stockfish integration; CLI prints per-move eval / CPL / classification | ✅ **done** |
| M2 | Feature detection (tactics, pawn structure, opening ID) | planned |
| M3 | LLM coaching report (structured prompt → JSON report) | planned |
| M4 | Web UI (board, eval graph, annotated movelist, comment panel) | planned |
| M5 | Live recording mode + PGN import + online import | planned |
| M6 | Storage, game library, export (annotated PGN, PDF/HTML) | planned |
| M7 | Syzygy tablebases, repertoire tracking, multi-game trends | stretch |

## M1 — what works now

A reproducible analysis pipeline:

1. Parse a PGN game (`python-chess`).
2. Evaluate every position once with Stockfish (each position evaluated a single
   time and reused for the before/after of adjacent plies — `N+1` engine calls).
3. Per move, compute (from the **mover's** point of view):
   - evaluation (centipawns or mate-in-N),
   - best move + principal variation (SAN),
   - **centipawn loss (CPL)** = best − played, clamped at 0,
   - win-probability before/after (Lichess-style logistic),
   - per-move accuracy (Chess.com-style approximation),
   - a **classification** (Best / Excellent / Good / Inaccuracy `?!` / Mistake `?`
     / Blunder `??`), plus a *missed-win* flag.
4. Aggregate per side: ACPL, accuracy %, classification counts.

Classification is driven primarily by **win-probability change** (more meaningful
than raw centipawns when a side is already winning/losing); centipawn-loss bands
give the fine gradations. Thresholds live in `chess_coach/config.py` and are
**tunable** — the accuracy/win% formulae are community approximations, *not*
official Lichess/Chess.com values.

## Setup

### 1. Python 3.11+
This repo was bootstrapped on Windows with Python 3.12.

```powershell
# from the project root
py -m venv .venv               # or: <python> -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`.)

### 2. Stockfish
The app auto-detects Stockfish on your PATH, in the winget package dir, in
common Homebrew/Linux locations, and in `./engines/`. Install it:

- **Windows:** `winget install Stockfish.Stockfish`
- **macOS:** `brew install stockfish`
- **Linux:** `apt install stockfish` (or download a build)

If auto-detect fails, set the path explicitly:

```powershell
# .env  (copy from .env.example)
STOCKFISH_PATH=C:\path\to\stockfish.exe
```
…or pass `--stockfish C:\path\to\stockfish.exe` on the CLI.

### 3. (M3+) Anthropic API
Coaching reports use the official `anthropic` SDK. Set `ANTHROPIC_API_KEY` as an
environment variable (never hard-code it). Model IDs are injected via config —
find the latest at <https://docs.claude.com>. Not needed for M1.

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m chess_coach.cli data\sample.pgn
```

Useful flags:

```
python -m chess_coach.cli data\sample.pgn --depth 20
python -m chess_coach.cli data\sample.pgn --movetime 500
python -m chess_coach.cli data\sample.pgn --json out\report.json
python -m chess_coach.cli mygame.pgn --stockfish C:\path\to\stockfish.exe
```

The bundled `data/sample.pgn` is Morphy's 1858 "Opera Game".

## Tests

```powershell
python -m pytest -q
```

Pure-function tests (win%, accuracy, classification, mate ordering) always run.
Engine-backed tests run at low depth and are auto-skipped if no Stockfish binary
is found.

## Project layout

```
chess-coach/
├── chess_coach/
│   ├── config.py     # engine + classification settings, Stockfish auto-detect
│   ├── engine.py     # Stockfish UCI wrapper (the ONLY source of evals)
│   ├── winprob.py    # cp <-> win% <-> accuracy conversions
│   ├── classify.py   # move classification (win%-primary, cp gradations)
│   ├── analyze.py    # PGN -> per-move analysis pipeline + aggregates
│   └── cli.py        # M1 command-line entry point
├── tests/test_analysis.py
├── data/sample.pgn
├── requirements.txt
└── .env.example
```

## Sign / scoring conventions

- Engine scores are read from the **side-to-move's** POV (relative).
- **CPL is always mover-POV** (best − played, clamped ≥ 0).
- For eval bars/graphs each move also stores a **White-POV** centipawn number.
- Draws (3-fold, 50/75-move, insufficient material), stalemate and mate are
  handled without querying the engine on a finished position.
- Engine depth/movetime/threads/hash are recorded in every report for
  reproducibility.

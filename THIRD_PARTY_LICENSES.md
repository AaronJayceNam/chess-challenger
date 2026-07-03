# Third-party components & licenses

This project (Chess Challenger) is distributed under the **GNU General Public
License v3.0** (see `LICENSE`) because it uses the GPL-3.0 components below.

## Stockfish (chess engine)
- **License:** GNU General Public License v3.0
- **Copyright:** The Stockfish developers (see AUTHORS in the Stockfish repo)
- **Source code:** https://github.com/official-stockfish/Stockfish
- **How it is used here:** Chess Challenger runs Stockfish as a **separate
  process** and communicates with it over the standard **UCI protocol**
  (stdin/stdout). Stockfish is **used unmodified**:
  - Docker / server deployment: the Debian `stockfish` package
    (`apt-get install stockfish`; the corresponding source is available with
    `apt-get source stockfish` on the same Debian release, and upstream at the
    URL above).
  - Local desktop use: the official binary installed by the user via
    `winget install Stockfish.Stockfish`.
- Because Stockfish is not modified, there are **no changes to publish**; the
  pointer above is the complete corresponding source for the exact binary.

## python-chess (chess library)
- **License:** GNU General Public License v3.0
- **Copyright:** Niklas Fiekas and contributors
- **Source code:** https://github.com/niklasf/python-chess
- **How it is used here:** imported as a Python library (board model, move
  legality, PGN, SVG rendering, and the UCI engine interface used to talk to
  Stockfish). Used unmodified (installed from PyPI: `pip install chess`).

## Note
Chess Challenger's own source code is public at
https://github.com/AaronJayceNam/chess-challenger and is provided under GPL-3.0,
satisfying the requirement to make corresponding source available.

"""chess_coach — engine-driven chess game analysis.

Design principle: "Engine for numbers, LLM for words."
All evaluations, best moves, PVs and centipawn-loss numbers come ONLY from the
Stockfish UCI engine. The LLM layer (added in M3) merely narrates engine output.
"""

__version__ = "0.1.0"

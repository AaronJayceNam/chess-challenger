"""Command-line entry point for M1.

Usage:
    python -m chess_coach.cli data/sample.pgn
    python -m chess_coach.cli data/sample.pgn --depth 20
    python -m chess_coach.cli data/sample.pgn --json out/report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .config import EngineConfig, ClassifyConfig
from .engine import Engine
from .analyze import analyze_game, read_game_from_file, GameAnalysis


def _fmt_eval(cp, mate) -> str:
    if mate is not None:
        return f"#{mate:+d}".replace("+", "+").replace("#-", "#-")
    if cp is None:
        return "—"
    return f"{cp/100:+.2f}"


def _print_report(ga: GameAnalysis) -> None:
    h = ga.headers
    white = h.get("White", "White")
    black = h.get("Black", "Black")
    print(f"\n=== {white} vs {black}  ({ga.result}) ===")
    eco = h.get("ECO")
    opening = h.get("Opening")
    if eco or opening:
        print(f"    {eco or ''} {opening or ''}".rstrip())
    eng = ga.engine
    budget = f"depth {eng['depth']}" if eng.get("depth") and not eng.get("movetime_ms") \
        else f"movetime {eng['movetime_ms']}ms"
    print(f"    engine: {eng['engine']}  {budget}  "
          f"threads={eng['threads']} hash={eng['hash_mb']}MB multipv={eng['multipv']}")
    print()

    # header
    print(f"{'#':>4} {'move':<8} {'eval':>7} {'CPL':>5} {'win%':>11}  "
          f"{'class':<11} best")
    print("-" * 78)
    for m in ga.moves:
        num = f"{m.move_number}." if m.color == "white" else f"{m.move_number}..."
        move_cell = f"{m.san}{m.symbol}"
        win = f"{m.win_prob_before:5.1f}->{m.win_prob_after:5.1f}"
        flag = " *MISSED WIN*" if m.missed_win else ""
        best = "" if m.is_best else f"{m.best_move_san or ''}"
        print(f"{num:>4} {move_cell:<8} {_fmt_eval(m.eval_cp, m.eval_mate):>7} "
              f"{m.cpl:>5} {win:>11}  {m.classification:<11} {best}{flag}")

    print("-" * 78)
    _print_side(ga, "White", ga.white)
    _print_side(ga, "Black", ga.black)


def _print_side(ga: GameAnalysis, name: str, stats) -> None:
    order = ["Best", "Excellent", "Good", "Inaccuracy", "Mistake", "Blunder"]
    counts = " ".join(f"{k}:{stats.counts.get(k, 0)}" for k in order if stats.counts.get(k))
    print(f"{name:<6}  ACPL {stats.acpl:>6.1f}   Accuracy {stats.accuracy:>5.1f}%   {counts}")


def build_engine_config(args) -> EngineConfig:
    cfg = EngineConfig()
    if args.stockfish:
        cfg.path = args.stockfish
    if args.depth is not None:
        cfg.depth = args.depth
        cfg.movetime_ms = None
    if args.movetime is not None:
        cfg.movetime_ms = args.movetime
        cfg.depth = None
    if args.threads is not None:
        cfg.threads = args.threads
    if args.multipv is not None:
        cfg.multipv = args.multipv
    return cfg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Engine-driven chess game analysis (M1).")
    p.add_argument("pgn", help="path to a PGN file (first game is analysed)")
    p.add_argument("--stockfish", help="path to Stockfish binary (overrides auto-detect)")
    p.add_argument("--depth", type=int, help="engine search depth")
    p.add_argument("--movetime", type=int, help="engine movetime in ms (overrides depth)")
    p.add_argument("--threads", type=int, help="engine threads")
    p.add_argument("--multipv", type=int, help="number of candidate lines to store")
    p.add_argument("--json", help="also write the full analysis as JSON to this path")
    args = p.parse_args(argv)

    cfg = build_engine_config(args)
    if not cfg.path:
        print("ERROR: Stockfish not found. Set STOCKFISH_PATH or pass --stockfish.",
              file=sys.stderr)
        return 2

    game = read_game_from_file(args.pgn)
    if game is None:
        print(f"ERROR: no game found in {args.pgn}", file=sys.stderr)
        return 2

    with Engine(cfg) as engine:
        ga = analyze_game(game, engine)

    _print_report(ga)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(ga.to_dict(), fh, indent=2, ensure_ascii=False)
        print(f"\nWrote JSON report -> {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

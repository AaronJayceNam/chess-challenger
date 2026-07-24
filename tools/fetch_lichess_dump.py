"""Build a big, themed puzzle set from the official Lichess puzzle database dump.

Why a dump and not the API: the live API rate-limits/blocks server IPs. The CSV
dump (https://database.lichess.org, CC0) is a single file — no blocking. We
STREAM-decompress it and stop as soon as our per-theme quotas fill, so we only
pull a fraction of the 300 MB file.

Output: webapp/static/puzzles.json in the app's format:
  {theme, fen, mateIn:0, solution:[uci...], solutionSan:[san...], cat, id, level}

Constraints that keep puzzles usable in the existing UI (fixed white-at-bottom
board, sequential per-category unlock, client-side line check):
  * Solver plays WHITE  → after the setup move (Moves[0]) it is White to move.
  * Short lines (<= 5 plies) and a beginner-friendly rating band.
  * Each category sorted easy→hard (Lichess rating ascending).
"""
import csv
import io
import json
import os
import sys
import urllib.request

import chess
import zstandard

URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "webapp", "static", "puzzles.json")

RATING_MIN, RATING_MAX = 600, 1600
MAX_PLIES = 5            # <= 5 half-moves in the solution (approachable)
COLLECT_PER = 220        # gather this many per theme, then sort + trim
KEEP_PER = 80            # keep this many per theme in the final set
ROW_CAP = 1_500_000      # hard stop on rows scanned (safety)

# (our theme key, cat index, predicate over the Lichess Themes string)
CATS = [
    ("mate",       0, lambda th: "mateIn1" in th or "mateIn2" in th),
    ("fork",       1, lambda th: "fork" in th),
    ("pin",        2, lambda th: "pin" in th),
    ("skewer",     3, lambda th: "skewer" in th),
    ("discovered", 4, lambda th: "discoveredAttack" in th),
    ("hanging",    5, lambda th: "hangingPiece" in th),
]


def build_puzzle(fen, moves, theme, cat):
    """Return a puzzle dict, or None if the row can't be used."""
    try:
        board = chess.Board(fen)
    except Exception:
        return None
    if not moves:
        return None
    try:
        setup = chess.Move.from_uci(moves[0])
    except Exception:
        return None
    if setup not in board.legal_moves:
        return None
    board.push(setup)                 # position the solver actually faces
    if board.turn != chess.WHITE:      # keep solver = White (board orientation)
        return None
    base_fen = board.fen()
    sol = moves[1:]
    if not (1 <= len(sol) <= MAX_PLIES):
        return None
    # replay the line to validate every move + collect SAN
    sans, bb = [], board.copy()
    for u in sol:
        try:
            m = chess.Move.from_uci(u)
        except Exception:
            return None
        if m not in bb.legal_moves:
            return None
        sans.append(bb.san(m))
        bb.push(m)
    return {"theme": theme, "fen": base_fen, "mateIn": 0,
            "solution": sol, "solutionSan": sans, "cat": cat}


def main():
    buckets = {c[0]: [] for c in CATS}          # theme -> list[(rating, puzzle)]
    quotas_full = set()
    scanned = kept = 0

    req = urllib.request.Request(URL, headers={"User-Agent": "Matevio-tools/1.0"})
    print(f"streaming {URL}", flush=True)
    resp = urllib.request.urlopen(req, timeout=90)
    dctx = zstandard.ZstdDecompressor()
    reader = dctx.stream_reader(resp)
    text = io.TextIOWrapper(reader, encoding="utf-8", newline="")
    rows = csv.reader(text)

    try:
        for row in rows:
            if len(row) < 8:
                continue
            if row[0] == "PuzzleId":            # header
                continue
            scanned += 1
            if scanned % 100_000 == 0:
                have = {k: len(v) for k, v in buckets.items()}
                print(f"  scanned {scanned:,}  kept {kept}  {have}", flush=True)
            if scanned > ROW_CAP:
                break
            try:
                rating = int(row[3])
            except ValueError:
                continue
            if not (RATING_MIN <= rating <= RATING_MAX):
                continue
            themes = row[7]
            # assign to the FIRST matching category (priority = list order)
            for theme, cat, pred in CATS:
                if theme in quotas_full:
                    continue
                if not pred(themes):
                    continue
                pz = build_puzzle(row[1], row[2].split(), theme, cat)
                if pz is None:
                    break
                buckets[theme].append((rating, pz))
                kept += 1
                if len(buckets[theme]) >= COLLECT_PER:
                    quotas_full.add(theme)
                break
            if len(quotas_full) == len(CATS):
                print("  all quotas full - stopping early", flush=True)
                break
    finally:
        try:
            resp.close()
        except Exception:
            pass

    # sort each theme easy→hard, trim to KEEP_PER, then flatten in category order
    out = []
    for theme, cat, _ in CATS:
        items = sorted(buckets[theme], key=lambda t: t[0])[:KEEP_PER]
        out.extend(p for _, p in items)
    for i, p in enumerate(out):
        p["id"] = i + 1
        p["level"] = i + 1

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    counts = Counter(p["theme"] for p in out)
    print(f"\nSCANNED {scanned:,}  TOTAL {len(out)}  {dict(counts)}")
    print("wrote", OUT)
    if len(out) < 20:
        sys.exit("too few puzzles — aborting")


if __name__ == "__main__":
    main()

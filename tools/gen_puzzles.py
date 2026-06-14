"""Generate Stockfish-verified checkmate puzzles.

Produces webapp/static/puzzles.json with 100 puzzles:
  levels 1-25   : mate in 1
  levels 26-50  : mate in 2
  levels 51-75  : mate in 3
  levels 76-100 : mate in 4

Each puzzle is a legal position where White (side to move) has a forced mate in
exactly N, confirmed by Stockfish. Run:  python tools/gen_puzzles.py
"""
from __future__ import annotations

import json
import os
import random
import sys

import chess
import chess.engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chess_coach.config import EngineConfig  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "webapp", "static", "puzzles.json")
PT = {"Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT, "P": chess.PAWN}

# material profiles (white attacker pieces, black defender pieces) — varied so
# mates land at different depths. Richer profiles tend to give longer mates.
PROFILES = [
    (["Q"], []), (["Q"], ["P"]), (["Q"], ["P", "P"]),
    (["R", "R"], []), (["R", "R"], ["P"]), (["R", "R"], ["P", "P"]),
    (["Q", "B"], ["P"]), (["Q", "N"], ["P"]), (["Q", "B"], ["P", "P"]),
    (["Q", "R"], ["P", "P"]), (["Q", "R"], ["R", "P"]),
    (["R", "B"], ["P"]), (["R", "N"], ["P"]), (["B", "B"], ["P"]),
    (["Q"], ["R"]), (["Q"], ["B", "P"]), (["Q", "N"], ["P", "P"]),
    (["R", "R", "B"], ["P", "P", "P"]), (["Q", "R"], ["B", "P", "P"]),
]


def rand_square(used, pawn=False):
    while True:
        s = random.randint(0, 63)
        if s in used:
            continue
        if pawn and chess.square_rank(s) in (0, 7):
            continue
        return s


def make_position(white_pieces, black_pieces):
    for _ in range(300):
        board = chess.Board(None)
        used = set()
        wk = rand_square(used); used.add(wk)
        bk = rand_square(used)
        if chess.square_distance(wk, bk) <= 1:
            continue
        used.add(bk)
        board.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
        for p in white_pieces:
            s = rand_square(used, p == "P"); used.add(s)
            board.set_piece_at(s, chess.Piece(PT[p], chess.WHITE))
        for p in black_pieces:
            s = rand_square(used, p == "P"); used.add(s)
            board.set_piece_at(s, chess.Piece(PT[p], chess.BLACK))
        board.turn = chess.WHITE
        if not board.is_valid():
            continue
        if board.is_check() or board.is_game_over():
            continue
        return board
    return None


def variation_san(board, pv):
    out, b = [], board.copy(stack=False)
    for mv in pv:
        try:
            out.append(b.san(mv)); b.push(mv)
        except Exception:
            break
    return out


def harvest(board, m, pv, buckets, need, seen):
    """From one forced-mate line, record mate-in-1..4 positions from its tail."""
    if len(pv) < 2 * m - 1:
        return 0
    added = 0
    for d in range(1, 5):
        if d > m or len(buckets[d]) >= need[d]:
            continue
        offset = 2 * (m - d)
        b = board.copy(stack=False)
        for mv in pv[:offset]:
            b.push(mv)
        if b.turn != chess.WHITE or b.is_game_over():
            continue
        fen = b.fen()
        if fen in seen:
            continue
        sol = pv[offset:offset + 2 * d - 1]
        seen.add(fen)
        buckets[d].append({
            "fen": fen, "mateIn": d,
            "solution": [x.uci() for x in sol],
            "solutionSan": variation_san(b, sol),
        })
        added += 1
    return added


def main():
    cfg = EngineConfig()
    if not cfg.path:
        print("Stockfish not found"); return
    need = {1: 25, 2: 25, 3: 25, 4: 25}
    buckets = {1: [], 2: [], 3: [], 4: []}
    seen = set()
    # Time limit so non-mate positions don't eat a full deep search; sparse
    # positions still find (and prove) short mates well within this budget.
    limit = chess.engine.Limit(time=0.6)

    eng = chess.engine.SimpleEngine.popen_uci(cfg.path)
    eng.configure({"Threads": max(2, (os.cpu_count() or 4) - 1), "Hash": 256})
    attempts = 0
    try:
        while any(len(buckets[n]) < need[n] for n in need):
            attempts += 1
            if attempts > 20000:
                break
            profile = random.choice(PROFILES)
            board = make_position(profile[0], profile[1])
            if board is None:
                continue
            info = eng.analyse(board, limit)
            score = info["score"].relative
            if not score.is_mate():
                continue
            m = score.mate()
            if m is None or m < 1 or m > 12:
                continue
            pv = info.get("pv", []) or []
            if harvest(board, m, pv, buckets, need, seen):
                done = sum(len(buckets[n]) for n in need)
                print(f"progress {done}/100  (m1={len(buckets[1])} m2={len(buckets[2])} "
                      f"m3={len(buckets[3])} m4={len(buckets[4])})  attempts={attempts}",
                      flush=True)
    finally:
        eng.quit()

    # assemble 100 puzzles in level order
    puzzles, level = [], 1
    for n in (1, 2, 3, 4):
        for p in buckets[n][:need[n]]:
            puzzles.append({"id": level, "level": level, **p})
            level += 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(puzzles, f, ensure_ascii=False)
    print(f"WROTE {len(puzzles)} puzzles -> {OUT}  (attempts={attempts})")


if __name__ == "__main__":
    main()

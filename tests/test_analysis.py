"""Unit + integration tests for the M1 analysis core."""
import io

import chess
import chess.pgn
import pytest

from chess_coach.winprob import win_prob_from_cp, win_prob_from_score, move_accuracy
from chess_coach.classify import classify_move
from chess_coach.config import EngineConfig, ClassifyConfig
from chess_coach.engine import Engine, PositionEval


# --------------------------------------------------------------------------- #
# Pure functions (no engine needed)
# --------------------------------------------------------------------------- #
def test_win_prob_midpoint_and_monotonic():
    assert win_prob_from_cp(0) == pytest.approx(50.0, abs=1e-6)
    assert win_prob_from_cp(300) > 60.0
    assert win_prob_from_cp(-300) < 40.0
    # symmetric around 50
    assert win_prob_from_cp(200) + win_prob_from_cp(-200) == pytest.approx(100.0, abs=1e-6)


def test_win_prob_from_mate():
    assert win_prob_from_score(None, 3) == 100.0
    assert win_prob_from_score(None, -3) == 0.0
    assert win_prob_from_score(50, None) == pytest.approx(win_prob_from_cp(50))


def test_move_accuracy_bounds():
    assert move_accuracy(60, 60) == pytest.approx(100.0, abs=0.5)   # no loss -> ~100
    assert move_accuracy(90, 10) < 20.0                             # huge loss -> low
    assert 0.0 <= move_accuracy(50, 0) <= 100.0


def test_signed_cp_mate_ordering():
    near = PositionEval(cp=None, mate=1, best_move=None, best_move_san=None,
                        pv=[], pv_uci=[], multipv=[])
    far = PositionEval(cp=None, mate=5, best_move=None, best_move_san=None,
                       pv=[], pv_uci=[], multipv=[])
    assert near.signed_cp() > far.signed_cp() > 0          # mate sooner is better
    lose = PositionEval(cp=None, mate=-2, best_move=None, best_move_san=None,
                        pv=[], pv_uci=[], multipv=[])
    assert lose.signed_cp() < 0


def test_capped_cp_bounds_mate_and_clamps():
    mate = PositionEval(cp=None, mate=2, best_move=None, best_move_san=None,
                        pv=[], pv_uci=[], multipv=[])
    assert mate.capped_cp(1000) == 1000          # mate -> cap, not 100000
    big = PositionEval(cp=5000, mate=None, best_move=None, best_move_san=None,
                       pv=[], pv_uci=[], multipv=[])
    assert big.capped_cp(1000) == 1000           # huge cp clamped
    assert big.capped_cp(1000) - (-1000) == 2000  # worst-case CPL is bounded


def test_classify_bands():
    cfg = ClassifyConfig()
    # engine's own move
    assert classify_move(cpl=0, win_before=55, win_after=55, is_best=True, cfg=cfg).label == "Best"
    # big win-prob drop -> blunder
    c = classify_move(cpl=400, win_before=70, win_after=30, is_best=False, cfg=cfg)
    assert c.label == "Blunder" and c.symbol == "??"
    # mistake band
    assert classify_move(cpl=150, win_before=60, win_after=38, is_best=False, cfg=cfg).label == "Mistake"
    # inaccuracy band
    assert classify_move(cpl=70, win_before=55, win_after=43, is_best=False, cfg=cfg).label == "Inaccuracy"
    # small loss, good move
    assert classify_move(cpl=30, win_before=55, win_after=53, is_best=False, cfg=cfg).label == "Good"


def test_classify_missed_win():
    c = classify_move(cpl=600, win_before=92, win_after=40, is_best=False)
    assert c.missed_win is True


# --------------------------------------------------------------------------- #
# Engine integration (skipped if Stockfish is not installed)
# --------------------------------------------------------------------------- #
def _engine_available() -> bool:
    return EngineConfig().path is not None


requires_engine = pytest.mark.skipif(not _engine_available(),
                                      reason="Stockfish binary not found")


@requires_engine
def test_engine_evaluates_startpos():
    cfg = EngineConfig()
    cfg.depth = 8
    cfg.movetime_ms = None
    with Engine(cfg) as eng:
        pe = eng.evaluate(chess.Board())
    assert pe.best_move is not None
    assert pe.best_move_san  # SAN rendered
    # opening eval is roughly balanced (small White edge)
    assert pe.cp is not None and -100 < pe.cp < 150


@requires_engine
def test_engine_detects_mate_in_one():
    # Black to move is checkmated after ...?? -> use a back-rank style mate.
    # Position: White to move, Rd8 is mate (Opera-game final motif simplified).
    board = chess.Board("3k4/8/8/8/8/8/8/3RK3 w - - 0 1")
    cfg = EngineConfig()
    cfg.depth = 6
    cfg.movetime_ms = None
    with Engine(cfg) as eng:
        pe = eng.evaluate(board)
    # KR vs K is a forced win for White.
    assert pe.signed_cp() > 0


@requires_engine
def test_pipeline_on_short_game():
    from chess_coach.analyze import analyze_game
    pgn = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0"
    game = chess.pgn.read_game(io.StringIO(pgn))
    cfg = EngineConfig()
    cfg.depth = 8
    cfg.movetime_ms = None
    with Engine(cfg) as eng:
        ga = analyze_game(game, eng)
    assert len(ga.moves) == 7
    for m in ga.moves:
        assert m.cpl >= 0
        assert 0.0 <= m.accuracy <= 100.0
        assert 0.0 <= m.win_prob_before <= 100.0
    # The mate move itself should be classified Best (it ends the game).
    assert ga.moves[-1].san.startswith("Qxf7")

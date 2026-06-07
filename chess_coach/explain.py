"""Plain-language, point-based move explanations (Korean).

Written for chess players with zero computer knowledge:
  * No engine jargon — never says "centipawn/cp", "win %", "evaluation".
  * Material gain/loss is expressed in PIECE POINTS (퀸 9, 룩 5, 나이트·비숍 3, 폰 1).
  * When a move is called best/good, it gives the REASON in detail but within
    ~3 short sentences.

Every statement is grounded only in facts the engine / python-chess established
(best move, principal variation, captured piece, opponent's best reply, "only
good move" detection, forced mate, material swing), so nothing is invented.

Korean particles: move names are written in algebraic notation (e4, Nf3, O-O),
whose final sound is unpredictable, so sentences are phrased to attach particles
to a Korean noun (e.g. "{san} 수가") rather than directly to the notation. Piece
names are a fixed set, so their object particle (을/를) is chosen correctly.
"""
from __future__ import annotations

from .analyze import MoveAnalysis

KOR_SIDE = {"white": "백", "black": "흑"}
# object particle (을/를) for each piece noun
_OBJ = {"폰": "을", "비숍": "을", "룩": "을", "퀸": "을", "킹": "을", "나이트": "를"}
_CENTER = {"d4", "e4", "d5", "e5"}


def _obj(piece: str) -> str:
    return f"{piece}{_OBJ.get(piece, '을')}"


# --------------------------------------------------------------------------- #
# Material in points (100 engine-units = 1 point = 1 pawn)
# --------------------------------------------------------------------------- #
def _piece_equiv(points: float) -> str:
    if points >= 8.0:
        return "퀸 하나"
    if points >= 4.5:
        return "룩 하나"
    if points >= 2.5:
        return "비숍·나이트 하나"
    if points >= 1.5:
        return "폰 두세 개"
    return "폰 하나"


def _loss_phrase(cpl: int) -> str | None:
    """e.g. '약 3점(비숍·나이트 하나)' — None if the loss is negligible."""
    p = cpl / 100.0
    if p < 0.5:
        return None
    return f"약 {p:.0f}점({_piece_equiv(p)})" if p >= 1.5 else f"약 {p:.1f}점"


def _mover_eval(m: MoveAnalysis) -> tuple[float | None, int | None]:
    """Position value after the move, in points, from the MOVER's side."""
    sign = 1 if m.color == "white" else -1
    if m.eval_mate is not None:
        return None, sign * m.eval_mate
    if m.eval_cp is None:
        return 0.0, None
    return sign * m.eval_cp / 100.0, None


# --------------------------------------------------------------------------- #
# Reasons for strong moves
# --------------------------------------------------------------------------- #
def _why_good(m: MoveAnalysis) -> str:
    if m.only_move:
        return "다른 수는 모두 좋지 않아, 이 국면을 지키는 사실상 유일한 정답입니다"
    if m.is_castle:
        return "킹을 안전한 곳으로 피신시키고 룩을 싸움에 끌어들이는 수입니다"
    if m.captured_piece:
        return f"상대의 {_obj(m.captured_piece)} 잡아 이득을 챙기는 수입니다"
    if m.gives_check:
        return "상대 킹을 직접 노려 주도권을 잡는 수입니다"
    if m.is_promotion:
        return "폰을 퀸으로 승격시켜 전력을 크게 키우는 수입니다"
    if m.develops:
        return f"{_obj(m.piece_moved or '기물')} 좋은 자리로 전개해 빠르게 싸울 준비를 하는 수입니다"
    to_sq = m.uci[2:4] if m.uci and len(m.uci) >= 4 else ""
    if m.piece_moved == "폰" and to_sq in _CENTER:
        return "중앙을 차지해 공간을 넓히는 수입니다"
    if m.piece_moved and m.piece_moved != "폰":
        return f"{_obj(m.piece_moved)} 더 좋은 자리로 옮겨 활동성을 높이는 수입니다"
    return "진영을 안정적으로 정비하는 수입니다"


def _better_alt(m: MoveAnalysis) -> str:
    if not m.best_move_san:
        return ""
    b = m.best_move_san
    if m.best_is_capture:
        return f"대신 {b} 수로 상대 기물을 잡는 편이 훨씬 좋았습니다."
    if m.best_is_check:
        return f"대신 {b} 수로 체크를 거는 편이 더 좋았습니다."
    return f"대신 {b} 수가 더 좋았습니다."


# --------------------------------------------------------------------------- #
def explain_move(m: MoveAnalysis) -> str:
    side = KOR_SIDE.get(m.color, "")
    name = f"{side}의 {m.san}"

    if m.is_mate:
        return f"{name}, 외통(체크메이트)! 게임을 끝내는 가장 좋은 수입니다."

    # --- strong moves: best / excellent ---
    if m.is_best or m.classification in ("Best", "Excellent"):
        head = (f"{name}, 이 국면에서 가장 좋은 수입니다."
                if (m.is_best or m.classification == "Best")
                else f"{name}, 최선에 아주 가까운 좋은 수입니다.")
        return f"{head} {_why_good(m)}."

    if m.classification == "Good":
        alt = _better_alt(m)
        return f"{name}, 둘 만한 무난한 수입니다. {alt}".strip()

    # --- weak moves: inaccuracy / mistake / blunder ---
    label = {
        "Inaccuracy": "조금 아쉬운 수",
        "Mistake": "실수",
        "Blunder": "큰 실수(블런더)",
    }.get(m.classification, "아쉬운 수")
    parts = [f"{name}, {label}입니다."]

    _, mate = _mover_eval(m)
    forced_mate_against = mate is not None and mate < 0

    if forced_mate_against:
        # the position is now a forced mate against the mover
        parts.append("이 수 다음에는 외통(메이트)을 피하기 어려워집니다.")
    else:
        if m.reply_captures:
            parts.append(
                f"이 수 다음 상대가 {m.reply_san} 수로 {_obj(m.reply_captures)} 잡을 수 있습니다.")
        loss = _loss_phrase(m.cpl)
        if loss:
            parts.append(f"{loss}만큼 손해를 보는 셈입니다.")

    if m.missed_win and len(parts) < 3:
        parts.append("이기던 흐름을 놓쳤습니다.")

    alt = _better_alt(m)
    if alt and len(parts) < 3:
        parts.append(alt)

    return " ".join(parts[:3])

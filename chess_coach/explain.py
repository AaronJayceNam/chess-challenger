"""Engine-grounded natural-language move explanations (Korean).

This is the "AI explanation" of each move. Following the project principle
"Engine for numbers, LLM for words", every sentence here is derived ONLY from
facts the engine / python-chess already established (classification, centipawn
loss, win-probability change, the engine's best move and principal variation,
and concrete move facts like capture/check/castle/promotion). Nothing is
invented, so the explanations are accurate without needing an LLM. If an
ANTHROPIC_API_KEY is configured, a richer whole-game LLM coaching pass is still
available separately (see coach.py).
"""
from __future__ import annotations

from .analyze import MoveAnalysis


def _action_phrase(m: MoveAnalysis) -> str:
    """What the move concretely does (mate > check > castle > promo > capture)."""
    if m.is_mate:
        return "체크메이트로 게임을 끝냅니다"
    if m.is_castle:
        return "캐슬링으로 킹을 안전하게 합니다"
    if m.is_promotion and m.gives_check:
        return "폰을 승격시키며 체크를 겁니다"
    if m.is_promotion:
        return "폰을 승격시킵니다"
    if m.is_capture and m.gives_check:
        return "기물을 잡으며 체크를 겁니다"
    if m.gives_check:
        return "상대 킹을 체크합니다"
    if m.is_capture:
        return "기물을 잡습니다"
    return ""


def _best_hint(m: MoveAnalysis) -> str:
    """A specific pointer to the engine's recommended move, if the move wasn't best."""
    if m.is_best or not m.best_move_san:
        return ""
    extra = ""
    if m.best_is_capture:
        extra = f" {m.best_move_san}로 기물을 잡는 수가 더 강했습니다."
    elif m.best_is_check:
        extra = f" {m.best_move_san}로 체크를 거는 수가 강했습니다."
    else:
        extra = f" 엔진은 {m.best_move_san}을(를) 추천합니다."
    pv = " ".join(m.pv[:6])
    if pv:
        extra += f" (최선 변화: {pv})"
    return extra


def explain_move(m: MoveAnalysis) -> str:
    """Return a 1–3 sentence Korean explanation of one move, from engine facts."""
    side = "백" if m.color == "white" else "흑"
    wb, wa = m.win_prob_before, m.win_prob_after
    action = _action_phrase(m)
    act_clause = f" 이 수는 {action}." if action else ""

    if m.is_best or m.classification == "Best":
        head = f"{side}의 {m.san}은(는) 이 국면에서 가장 정확한 수입니다."
        if m.is_mate:
            return f"{side}의 {m.san}: 체크메이트! 게임을 끝내는 최선의 수입니다."
        tail = ""
        if wa >= 80:
            tail = " 우세를 굳히는 흐름입니다."
        elif wa <= 20:
            tail = " 어려운 국면에서 최선의 버팀수입니다."
        return head + act_clause + tail

    if m.classification == "Excellent":
        return (f"{side}의 {m.san}은(는) 거의 최선에 가까운 좋은 수입니다 "
                f"(약 {m.cpl}cp 손해).{act_clause}")

    if m.classification == "Good":
        return (f"{side}의 {m.san}은(는) 무난한 수입니다 (약 {m.cpl}cp 손해).{act_clause}"
                + _best_hint(m))

    # Inaccuracy / Mistake / Blunder
    label = {"Inaccuracy": "부정확한 수(?!)",
             "Mistake": "실수(?)",
             "Blunder": "블런더(??)"}.get(m.classification, m.classification)
    head = (f"{side}의 {m.san}은(는) {label}입니다. "
            f"승률이 {wb:.0f}%에서 {wa:.0f}%로 떨어졌습니다 (약 {m.cpl}cp 손해).")
    missed = " 이기던 국면을 놓쳤습니다." if m.missed_win else ""
    mate_against = ""
    if wa <= 1 and m.classification == "Blunder":
        mate_against = " 이후 상대에게 강한 공격/메이트를 허용합니다."
    return head + missed + _best_hint(m) + mate_against

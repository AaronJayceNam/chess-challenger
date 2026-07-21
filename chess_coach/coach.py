"""Optional LLM coaching layer (a preview of M3).

Strictly follows the project principle "Engine for numbers, LLM for words": the
model receives ONLY the engine's structured output (evals, CPL, classifications,
best moves, PVs) and is told never to invent evaluations or variations. If no
ANTHROPIC_API_KEY is configured, coaching is gracefully unavailable and the rest
of the app works on engine evaluation alone.
"""
from __future__ import annotations

import os
import json
from typing import Optional


SYSTEM_PROMPT = (
    "당신은 따뜻하고 구체적인 체스 코치(FM/IM 수준)입니다. "
    "입력으로 받는 모든 평가 수치(centipawn/mate), centipawn loss(CPL), 최선수, "
    "주 변화(PV)는 Stockfish 엔진이 계산한 사실입니다. "
    "절대 평가 수치나 변화를 새로 지어내지 마십시오. 변화를 제시할 때는 반드시 "
    "전달된 엔진 PV/최선수만 사용하고, 수와 칸은 SAN으로 표기하십시오. "
    "한국어로, 격려하면서도 구체적으로 코칭하세요."
)


def coaching_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _key_moments(view: dict, limit: int = 6) -> list[dict]:
    moves = view.get("moves", [])
    ranked = sorted(
        (m for m in moves if not m.get("isBest")),
        key=lambda m: m.get("cpl", 0),
        reverse=True,
    )
    out = []
    for m in ranked[:limit]:
        out.append({
            "ply": m["ply"],
            "move": f"{m['moveNumber']}{'.' if m['color']=='white' else '...'} {m['san']}{m['symbol']}",
            "side": m["color"],
            "classification": m["classification"],
            "cpl": m["cpl"],
            "winBefore": m["winBefore"],
            "winAfter": m["winAfter"],
            "engineBest": m.get("best"),
            "pv": (m.get("pv") or [])[:6],
        })
    return out


def build_payload(view: dict) -> dict:
    """Compact, engine-only JSON handed to the model."""
    return {
        "title": view.get("title"),
        "result": view.get("result"),
        "opening": view.get("opening"),
        "engine": view.get("engLine"),
        "accuracy": {
            "white": view["white"]["accuracy"],
            "black": view["black"]["accuracy"],
        },
        "acpl": {"white": view["white"]["acpl"], "black": view["black"]["acpl"]},
        "classificationCounts": {
            "white": view["white"]["counts"],
            "black": view["black"]["counts"],
        },
        "keyMoments": _key_moments(view),
    }


def generate_coaching(view: dict, model: Optional[str] = None) -> dict:
    """Return {available, text|message}. Never raises into the request path."""
    if not coaching_available():
        return {
            "available": False,
            "message": "LLM 코칭은 ANTHROPIC_API_KEY 환경변수를 설정하면 활성화됩니다. "
                       "(엔진 평가는 키 없이도 모두 동작합니다.)",
        }
    try:
        import anthropic

        # Default to the low-cost Haiku model (the engine already did the hard
        # analysis; the LLM only writes it up). Override with ANTHROPIC_MODEL,
        # e.g. "claude-sonnet-5" for richer prose.
        model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        client = anthropic.Anthropic()
        payload = build_payload(view)
        user = (
            "아래는 한 체스 게임에 대한 엔진 분석 데이터(JSON)입니다. "
            "이 데이터만 근거로, 다음 섹션의 한국어 코칭 리포트를 작성하세요: "
            "1) 한 줄 요약 + 양측 정확도, 2) 결정적 순간(전달된 keyMoments의 최선수/PV 인용), "
            "3) 반복되는 약점, 4) 다음에 무엇을 공부하면 좋을지 구체적 제안.\n\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
        )
        msg = client.messages.create(
            model=model,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return {"available": True, "text": text, "model": model}
    except Exception as e:  # never break the analysis response
        return {"available": False, "message": f"코칭 생성 중 오류: {e}"}

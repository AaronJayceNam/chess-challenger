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


# The report language follows the user's app language.
_LANG_NAME = {
    "ko": "Korean (한국어)",
    "en": "English",
    "ja": "Japanese (日本語)",
    "zh": "Simplified Chinese (简体中文)",
    "es": "Spanish (Español)",
}

_SYSTEM_BASE = (
    "You are a warm, specific chess coach (FM/IM level). Every evaluation number "
    "(centipawn/mate), centipawn loss (CPL), best move, and principal variation "
    "(PV) you receive was computed by the Stockfish engine and is fact. NEVER "
    "invent evaluations or variations. When you show a line, use ONLY the engine "
    "PV/best move provided, and write moves and squares in SAN. Be encouraging "
    "but concrete."
)


def _system_for(lang: str) -> str:
    name = _LANG_NAME.get(lang, _LANG_NAME["ko"])
    return _SYSTEM_BASE + f" Write the ENTIRE coaching report in {name}."


# Back-compat: some callers/tests import SYSTEM_PROMPT.
SYSTEM_PROMPT = _system_for("ko")


def coaching_available() -> bool:
    # Any one of these enables coaching. Gemini & Groq both have free tiers.
    return bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )


def _http_json(url: str, payload: dict, headers: dict, timeout: int = 30) -> dict:
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _gen_gemini(system: str, user: str) -> tuple[str, str]:
    """Google Gemini (free tier). Returns (text, model)."""
    key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    data = _http_json(url, {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 1400, "temperature": 0.6},
    }, headers={})
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts), f"gemini:{model}"


def _gen_groq(system: str, user: str) -> tuple[str, str]:
    """Groq (free tier, OpenAI-compatible). Returns (text, model)."""
    key = os.environ.get("GROQ_API_KEY", "")
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    data = _http_json("https://api.groq.com/openai/v1/chat/completions", {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": 1400, "temperature": 0.6,
    }, headers={"Authorization": f"Bearer {key}"})
    return data["choices"][0]["message"]["content"], f"groq:{model}"


def _gen_anthropic(system: str, user: str) -> tuple[str, str]:
    import anthropic
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model, max_tokens=1200, system=system,
        messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, model


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


def generate_coaching(view: dict, lang: str = "ko") -> dict:
    """Return {available, text|message}. Never raises into the request path.

    Provider priority: Gemini → Groq → Anthropic (first with a key wins). Gemini
    and Groq both have free tiers. The report is written in `lang` (the user's
    app language: ko/en/ja/zh/es).
    """
    if not coaching_available():
        return {
            "available": False,
            "message": "LLM 코칭은 GEMINI_API_KEY(무료) 또는 GROQ_API_KEY(무료), "
                       "ANTHROPIC_API_KEY 중 하나를 설정하면 활성화됩니다. "
                       "(엔진 평가는 키 없이도 모두 동작합니다.)",
        }
    system = _system_for(lang)
    lang_name = _LANG_NAME.get(lang, _LANG_NAME["ko"])
    payload = build_payload(view)
    user = (
        "Below is engine-analysis data (JSON) for one chess game. Using ONLY this "
        "data, write a coaching report with these sections: 1) one-line summary + "
        "both sides' accuracy, 2) decisive moments (cite the engine best move/PV "
        "from keyMoments), 3) recurring weaknesses, 4) concrete suggestions on what "
        f"to study next. Write the whole report in {lang_name}.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )
    try:
        if os.environ.get("GEMINI_API_KEY"):
            text, used = _gen_gemini(system, user)
        elif os.environ.get("GROQ_API_KEY"):
            text, used = _gen_groq(system, user)
        else:
            text, used = _gen_anthropic(system, user)
        return {"available": True, "text": text, "model": used}
    except Exception as e:  # never break the analysis response
        return {"available": False, "message": f"코칭 생성 중 오류: {e}"}

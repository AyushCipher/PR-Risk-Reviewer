from __future__ import annotations

import json
import os
from typing import TypedDict

from app.services.heuristics import Flag

_MODEL_NAME = "gemini-1.5-flash"
_VALID_SEVERITIES = {"low", "medium", "high"}

_PROMPT_TEMPLATE = """You are reviewing one flagged change from a pull request diff.
Flag category: {tag}
Why it was flagged (deterministic rule): {matched_reason}
Relevant diff excerpt:
{hunk}

Based only on the information above, respond with a single JSON object with
exactly these two keys:
- "severity": one of "low", "medium", "high"
- "explanation": one or two sentences, specific to this exact change, no
  generic advice, no restating the rule name

Respond with JSON only, no markdown fences, no extra text.
"""


class Explanation(TypedDict):
    severity: str
    explanation: str


def _configure_client():
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)
    return genai


def _build_prompt(flag: Flag) -> str:
    return _PROMPT_TEMPLATE.format(
        tag=flag["tag"],
        matched_reason=flag["matched_reason"],
        hunk=flag["hunk"] or "(no diff content available)",
    )


def _parse_response(text: str) -> Explanation:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned)
    severity = str(data.get("severity", "")).lower()
    if severity not in _VALID_SEVERITIES:
        severity = "medium"
    explanation = str(data.get("explanation", "")).strip()
    return {"severity": severity, "explanation": explanation}


def _fallback_explanation(flag: Flag) -> Explanation:
    return {"severity": "medium", "explanation": flag["matched_reason"]}


def explain_flag(flag: Flag, model=None) -> Explanation:
    try:
        if model is None:
            genai = _configure_client()
            model = genai.GenerativeModel(_MODEL_NAME)
        prompt = _build_prompt(flag)
        response = model.generate_content(prompt)
        return _parse_response(response.text)
    except Exception:
        return _fallback_explanation(flag)


def explain_flags(flags: list[Flag]) -> list[Explanation]:
    if not flags:
        return []

    model = None
    try:
        genai = _configure_client()
        model = genai.GenerativeModel(_MODEL_NAME)
    except Exception:
        model = None

    results = []
    for flag in flags:
        if model is None:
            results.append(_fallback_explanation(flag))
        else:
            results.append(explain_flag(flag, model=model))
    return results

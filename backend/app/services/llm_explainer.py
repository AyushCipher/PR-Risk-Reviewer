from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

from app.services.heuristics import Flag

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-3.6-flash"
_EMBEDDING_MODEL = "models/embedding-001"
_VALID_SEVERITIES = {"low", "medium", "high"}
_MAX_WORKERS = 5

# ── Gemini Function Calling tool declaration ──────────────────────────────────
# The LLM is forced to call this tool — it cannot respond with free text.
# This eliminates the fragile json.loads / markdown-fence cleanup entirely.
_CLASSIFY_RISK_TOOL = {
    "name": "classify_risk",
    "description": (
        "Classify the risk severity of a single flagged change in a pull request diff "
        "and provide a concise explanation and a concrete remediation suggestion."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Risk severity of this specific change.",
            },
            "explanation": {
                "type": "string",
                "description": (
                    "One or two sentences specific to this exact change. "
                    "Do not restate the rule name or give generic advice."
                ),
            },
            "suggested_fix": {
                "type": "string",
                "description": (
                    "One concrete, actionable remediation step for this flag "
                    "(e.g. 'Move the token to an environment variable'). "
                    "Do not give generic security advice."
                ),
            },
        },
        "required": ["severity", "explanation", "suggested_fix"],
    },
}

_PROMPT_TEMPLATE = """\
You are reviewing one flagged change from a pull request diff.
Flag category: {tag}
Why it was flagged (deterministic rule): {matched_reason}
{rag_section}
Relevant diff excerpt:
{hunk}

Call the classify_risk tool with your assessment.
"""

_RAG_SECTION_TEMPLATE = (
    "Broader codebase context (semantically retrieved chunks from the same file — "
    "use this to understand how the flagged code fits into the wider codebase):\n"
    "{context}\n"
)


class Explanation(TypedDict):
    severity: str
    explanation: str
    suggested_fix: str


def _configure_client():
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)
    return genai


def _build_prompt(flag: Flag, rag_context: str = "") -> str:
    rag_section = (
        _RAG_SECTION_TEMPLATE.format(context=rag_context)
        if rag_context
        else ""
    )
    return _PROMPT_TEMPLATE.format(
        tag=flag["tag"],
        matched_reason=flag["matched_reason"],
        hunk=flag["hunk"] or "(no diff content available)",
        rag_section=rag_section,
    )


def _fallback_explanation(flag: Flag) -> Explanation:
    return {
        "severity": "medium",
        "explanation": flag["matched_reason"],
        "suggested_fix": "Review this change manually before merging.",
    }


def _parse_function_call(response) -> Explanation:
    """
    Extract the classify_risk tool call arguments from a Gemini response.
    Using Function Calling means the model is constrained to return structured
    JSON — no markdown fences, no free text to clean up.
    """
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.function_call and part.function_call.name == "classify_risk":
                args = dict(part.function_call.args)
                severity = str(args.get("severity", "")).lower()
                if severity not in _VALID_SEVERITIES:
                    severity = "medium"
                return {
                    "severity": severity,
                    "explanation": str(args.get("explanation", "")).strip(),
                    "suggested_fix": str(args.get("suggested_fix", "")).strip(),
                }
    raise ValueError("No classify_risk function call found in response")


def explain_flag(flag: Flag, model=None, rag_context: str = "") -> Explanation:
    """
    Explain a single flag using Gemini Function Calling.
    If rag_context is provided (retrieved via the RAG pipeline), it is injected
    into the prompt to give the LLM broader understanding of the codebase.
    """
    try:
        if model is None:
            genai = _configure_client()
            model = genai.GenerativeModel(
                _MODEL_NAME,
                tools=[{"function_declarations": [_CLASSIFY_RISK_TOOL]}],
                tool_config={"function_calling_config": {"mode": "ANY"}},
            )
        prompt = _build_prompt(flag, rag_context=rag_context)
        response = model.generate_content(prompt)
        return _parse_function_call(response)
    except Exception:
        logger.exception("LLM explanation failed for flag %r; using fallback", flag.get("tag"))
        return _fallback_explanation(flag)


def explain_flags(flags: list[Flag]) -> list[Explanation]:
    """Explain all flags concurrently using a thread pool. No RAG context (used by legacy endpoint)."""
    if not flags:
        return []

    model = None
    try:
        genai = _configure_client()
        model = genai.GenerativeModel(
            _MODEL_NAME,
            tools=[{"function_declarations": [_CLASSIFY_RISK_TOOL]}],
            tool_config={"function_calling_config": {"mode": "ANY"}},
        )
    except Exception:
        logger.warning("Could not configure Gemini client; using fallback explanations")
        return [_fallback_explanation(flag) for flag in flags]

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(flags))) as executor:
        return list(executor.map(lambda flag: explain_flag(flag, model=model), flags))


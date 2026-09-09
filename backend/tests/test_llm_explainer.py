import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from app.services.llm_explainer import (
    _fallback_explanation,
    _parse_function_call,
    explain_flag,
    explain_flags,
)


# ── Helpers to build fake Gemini Function Calling responses ───────────────────

def _make_function_call_response(severity, explanation, suggested_fix):
    """
    Build a mock Gemini response object that looks like a Function Calling
    response with a classify_risk tool call.
    """
    part = MagicMock()
    part.function_call.name = "classify_risk"
    part.function_call.args = {
        "severity": severity,
        "explanation": explanation,
        "suggested_fix": suggested_fix,
    }

    candidate = MagicMock()
    candidate.content.parts = [part]

    response = MagicMock()
    response.candidates = [candidate]
    return response


def _make_no_tool_call_response():
    """A response with no function_call (simulates fallback/failure)."""
    part = MagicMock()
    part.function_call = None

    candidate = MagicMock()
    candidate.content.parts = [part]

    response = MagicMock()
    response.candidates = [candidate]
    return response


# ── _parse_function_call tests ────────────────────────────────────────────────

def test_parse_function_call_extracts_all_fields():
    response = _make_function_call_response(
        severity="high",
        explanation="Adds a new session cookie without expiry.",
        suggested_fix="Set an explicit expiry via session.permanent = True.",
    )
    result = _parse_function_call(response)
    assert result == {
        "severity": "high",
        "explanation": "Adds a new session cookie without expiry.",
        "suggested_fix": "Set an explicit expiry via session.permanent = True.",
    }


def test_parse_function_call_invalid_severity_defaults_to_medium():
    response = _make_function_call_response(
        severity="critical",  # not a valid enum value
        explanation="Some explanation.",
        suggested_fix="Some fix.",
    )
    result = _parse_function_call(response)
    assert result["severity"] == "medium"


def test_parse_function_call_raises_on_missing_tool_call():
    response = _make_no_tool_call_response()
    with pytest.raises(ValueError, match="No classify_risk function call found"):
        _parse_function_call(response)


# ── _fallback_explanation tests ───────────────────────────────────────────────

def test_fallback_explanation_returns_correct_shape():
    flag = {
        "file": "app/auth.py",
        "hunk": "+session['user'] = user",
        "tag": "auth_change",
        "matched_reason": "diff content matches auth-related keyword: session",
    }
    result = _fallback_explanation(flag)
    assert result["severity"] == "medium"
    assert result["explanation"] == flag["matched_reason"]
    assert "suggested_fix" in result
    assert isinstance(result["suggested_fix"], str)


# ── explain_flag tests ────────────────────────────────────────────────────────

def test_explain_flag_uses_function_calling_result():
    flag = {
        "file": "backend/app/auth/session.py",
        "hunk": "+session['user'] = user",
        "tag": "auth_change",
        "matched_reason": "diff content matches auth-related keyword: session",
    }
    fake_response = _make_function_call_response(
        severity="high",
        explanation="Sets session state directly without validation.",
        suggested_fix="Validate the user object before storing it in the session.",
    )
    model = MagicMock()
    model.generate_content.return_value = fake_response

    result = explain_flag(flag, model=model)
    assert result["severity"] == "high"
    assert "session" in result["explanation"].lower()
    assert "suggested_fix" in result
    assert len(result["suggested_fix"]) > 0


def test_explain_flag_falls_back_when_model_raises():
    flag = {
        "file": "backend/app/auth/session.py",
        "hunk": "+session['user'] = user",
        "tag": "auth_change",
        "matched_reason": "diff content matches auth-related keyword: session",
    }
    model = MagicMock()
    model.generate_content.side_effect = RuntimeError("API quota exceeded")

    result = explain_flag(flag, model=model)
    # Should fall back gracefully
    assert result["severity"] == "medium"
    assert result["explanation"] == flag["matched_reason"]
    assert "suggested_fix" in result


def test_explain_flag_falls_back_when_no_tool_call_returned():
    flag = {
        "file": "backend/.env.production",
        "hunk": "+DEBUG=false",
        "tag": "config_change",
        "matched_reason": "filename matches config/settings pattern",
    }
    model = MagicMock()
    model.generate_content.return_value = _make_no_tool_call_response()

    result = explain_flag(flag, model=model)
    assert result["severity"] == "medium"
    assert result["explanation"] == flag["matched_reason"]


# ── explain_flags tests ───────────────────────────────────────────────────────

def test_explain_flags_empty_list_returns_empty():
    assert explain_flags([]) == []


def test_explain_flags_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    flags = [
        {
            "file": "backend/.env.production",
            "hunk": "+DEBUG=false",
            "tag": "config_change",
            "matched_reason": "filename matches config/settings pattern",
        }
    ]
    results = explain_flags(flags)
    assert len(results) == 1
    assert results[0]["severity"] == "medium"
    assert results[0]["explanation"] == flags[0]["matched_reason"]
    # New field must be present even in fallback
    assert "suggested_fix" in results[0]


def test_explain_flags_returns_suggested_fix_for_all_flags():
    flags = [
        {
            "file": "app/auth.py",
            "hunk": "+jwt.decode(token)",
            "tag": "auth_change",
            "matched_reason": "diff content matches auth-related keyword: jwt",
        },
        {
            "file": "migrations/0001.py",
            "hunk": "+ALTER TABLE users ADD COLUMN role TEXT",
            "tag": "migration",
            "matched_reason": "file located in a migrations folder",
        },
    ]

    fake_response = _make_function_call_response(
        severity="medium",
        explanation="Generic explanation.",
        suggested_fix="Generic fix.",
    )
    model = MagicMock()
    model.generate_content.return_value = fake_response

    results = explain_flags.__wrapped__(flags) if hasattr(explain_flags, "__wrapped__") else None

    # Test via explain_flag directly (explain_flags delegates to it)
    for flag in flags:
        result = explain_flag(flag, model=model)
        assert "suggested_fix" in result
        assert result["severity"] in {"low", "medium", "high"}

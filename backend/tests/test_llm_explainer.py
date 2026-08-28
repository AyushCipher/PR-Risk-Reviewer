import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.llm_explainer import _parse_response, explain_flag, explain_flags


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def __init__(self, text):
        self._text = text

    def generate_content(self, prompt):
        return _FakeResponse(self._text)


def test_parse_response_plain_json():
    result = _parse_response(
        '{"severity": "high", "explanation": "Adds a new session cookie without expiry."}'
    )
    assert result == {
        "severity": "high",
        "explanation": "Adds a new session cookie without expiry.",
    }


def test_parse_response_strips_markdown_fence():
    text = '```json\n{"severity": "low", "explanation": "Minor config default change."}\n```'
    result = _parse_response(text)
    assert result["severity"] == "low"


def test_parse_response_invalid_severity_defaults_to_medium():
    result = _parse_response('{"severity": "critical", "explanation": "x"}')
    assert result["severity"] == "medium"


def test_explain_flag_uses_model_response():
    flag = {
        "file": "backend/app/auth/session.py",
        "hunk": "+session['user'] = user",
        "tag": "auth_change",
        "matched_reason": "diff content matches auth-related keyword: session",
    }
    model = _FakeModel(
        '{"severity": "high", "explanation": "Sets session state directly without validation."}'
    )
    result = explain_flag(flag, model=model)
    assert result["severity"] == "high"
    assert "session" in result["explanation"].lower()


def test_explain_flag_falls_back_on_bad_response():
    flag = {
        "file": "backend/app/auth/session.py",
        "hunk": "+session['user'] = user",
        "tag": "auth_change",
        "matched_reason": "diff content matches auth-related keyword: session",
    }
    model = _FakeModel("not valid json")
    result = explain_flag(flag, model=model)
    assert result["severity"] == "medium"
    assert result["explanation"] == flag["matched_reason"]


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


def test_explain_flags_empty_list_returns_empty():
    assert explain_flags([]) == []

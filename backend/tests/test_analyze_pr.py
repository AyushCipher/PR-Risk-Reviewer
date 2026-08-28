import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_analyze_pr_returns_expected_shape(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr", params={"url": "https://github.com/octocat/hello-world/pull/42"}
        )
    assert response.status_code == 200

    body = response.json()
    assert body["pr_url"] == "https://github.com/octocat/hello-world/pull/42"
    assert isinstance(body["overall_risk_score"], int)
    assert isinstance(body["flags"], list)
    assert len(body["flags"]) > 0

    for flag in body["flags"]:
        assert set(flag.keys()) == {
            "file",
            "tag",
            "severity",
            "explanation",
            "matched_reason",
            "hunk_excerpt",
        }
        assert flag["severity"] in {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_analyze_pr_flags_auth_migration_and_secret(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr", params={"url": "https://github.com/octocat/hello-world/pull/1"}
        )
    tags = {flag["tag"] for flag in response.json()["flags"]}
    assert "auth_change" in tags
    assert "migration" in tags
    assert "hardcoded_secret" in tags


@pytest.mark.asyncio
async def test_analyze_pr_rejects_malformed_url(client):
    async with client:
        response = await client.get("/analyze-pr", params={"url": "not-a-github-url"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_pr_risk_score_capped_at_100(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr", params={"url": "https://github.com/octocat/hello-world/pull/2"}
        )
    assert response.json()["overall_risk_score"] <= 100

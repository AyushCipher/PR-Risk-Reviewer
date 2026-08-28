import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

import app.routers.analyze_pr as analyze_pr_module
from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


_SYNTHETIC_PR_DATA = {
    "pr_url": "https://github.com/example-org/example-repo/pull/7",
    "repo": "example-org/example-repo",
    "pr_number": 7,
    "title": "Synthetic PR for aggregation tests",
    "files": [
        {
            "filename": "backend/app/services/auth_middleware.py",
            "status": "modified",
            "patch": (
                "@@ -10,6 +10,12 @@\n"
                "+def authenticate(request):\n"
                "+    token = request.headers.get('Authorization')\n"
                "+    session['user'] = decode_token(token)\n"
                "+    return session['user']\n"
            ),
            "additions": 12,
            "deletions": 0,
        },
        {
            "filename": "backend/migrations/0012_add_role_column.py",
            "status": "added",
            "patch": "@@ -0,0 +1,3 @@\n+def upgrade():\n+    op.execute('ALTER TABLE users ADD COLUMN role TEXT')\n",
            "additions": 3,
            "deletions": 0,
        },
        {
            "filename": ".env.production",
            "status": "modified",
            "patch": "@@ -1,2 +1,3 @@\n+STRIPE_SECRET_KEY=example_placeholder_not_a_real_key_00000\n",
            "additions": 1,
            "deletions": 0,
        },
    ],
}


# --- Aggregation logic tests: fetcher mocked out, fast and deterministic ---


@pytest.mark.asyncio
async def test_analyze_pr_returns_expected_shape(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(analyze_pr_module, "fetch_pr_data", lambda url: _SYNTHETIC_PR_DATA)

    async with client:
        response = await client.get("/analyze-pr", params={"url": _SYNTHETIC_PR_DATA["pr_url"]})
    assert response.status_code == 200

    body = response.json()
    assert body["pr_url"] == _SYNTHETIC_PR_DATA["pr_url"]
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
    monkeypatch.setattr(analyze_pr_module, "fetch_pr_data", lambda url: _SYNTHETIC_PR_DATA)

    async with client:
        response = await client.get("/analyze-pr", params={"url": _SYNTHETIC_PR_DATA["pr_url"]})
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
    monkeypatch.setattr(analyze_pr_module, "fetch_pr_data", lambda url: _SYNTHETIC_PR_DATA)

    async with client:
        response = await client.get("/analyze-pr", params={"url": _SYNTHETIC_PR_DATA["pr_url"]})
    assert response.json()["overall_risk_score"] <= 100


# --- End-to-end tests against real, small, public GitHub PRs ---


@pytest.mark.asyncio
async def test_analyze_pr_end_to_end_real_pr_with_added_file(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr",
            params={"url": "https://github.com/octocat/Hello-World/pull/11023"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["pr_url"] == "https://github.com/octocat/Hello-World/pull/11023"
    assert isinstance(body["overall_risk_score"], int)
    assert isinstance(body["flags"], list)


@pytest.mark.asyncio
async def test_analyze_pr_end_to_end_real_pr_with_modified_file(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr",
            params={"url": "https://github.com/octocat/Spoon-Knife/pull/41111"},
        )
    assert response.status_code == 200
    assert isinstance(response.json()["flags"], list)


@pytest.mark.asyncio
async def test_analyze_pr_end_to_end_real_pr_with_no_file_changes(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client:
        response = await client.get(
            "/analyze-pr",
            params={"url": "https://github.com/octocat/Hello-World/pull/11005"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["flags"] == []
    assert body["overall_risk_score"] == 0


@pytest.mark.asyncio
async def test_analyze_pr_end_to_end_nonexistent_pr_returns_404(client):
    async with client:
        response = await client.get(
            "/analyze-pr",
            params={"url": "https://github.com/octocat/Hello-World/pull/999999"},
        )
    assert response.status_code == 404

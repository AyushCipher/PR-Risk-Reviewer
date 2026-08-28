import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest
from fastapi import FastAPI

from app.routers.fetch_pr import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_fetch_pr_endpoint_returns_real_pr_shape(client):
    async with client:
        response = await client.get(
            "/fetch-pr", params={"url": "https://github.com/octocat/Hello-World/pull/11023"}
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"pr_url", "repo", "pr_number", "title", "files"}
    assert body["repo"] == "octocat/Hello-World"
    assert body["pr_number"] == 11023
    assert len(body["files"]) == 1
    assert set(body["files"][0].keys()) == {
        "filename",
        "status",
        "patch",
        "additions",
        "deletions",
    }


@pytest.mark.asyncio
async def test_fetch_pr_endpoint_malformed_url_returns_400(client):
    async with client:
        response = await client.get("/fetch-pr", params={"url": "not-a-url"})
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_fetch_pr_endpoint_not_found_returns_404(client):
    async with client:
        response = await client.get(
            "/fetch-pr",
            params={"url": "https://github.com/octocat/Hello-World/pull/999999"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_fetch_pr_endpoint_accepts_optional_token_header(client):
    async with client:
        response = await client.get(
            "/fetch-pr",
            params={"url": "https://github.com/octocat/Hello-World/pull/11023"},
            headers={"X-GitHub-Token": "not-a-real-token-but-should-not-crash"},
        )
    # A bad token on a public repo/PR still resolves fine via public access rules
    # for this endpoint, or GitHub rejects the token explicitly - either way the
    # request must not raise an unhandled error.
    assert response.status_code in (200, 401)

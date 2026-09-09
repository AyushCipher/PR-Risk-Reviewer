import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import httpx
from fastapi import FastAPI
from app.routers.webhook import router as webhook_router
from app.routers.traces import router as traces_router
from app.services.cache import cache_pr_data, get_cached_pr_data, invalidate_pr_cache
from app.models import User, Analysis, LLMTrace
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test DB (SQLite in-memory for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()
app.include_router(webhook_router)
app.include_router(traces_router)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ── Cache Unit Tests ─────────────────────────────────────────────────────────

@patch("app.services.cache._get_redis")
def test_cache_pr_data_and_get(mock_get_redis):
    fake_redis = MagicMock()
    mock_get_redis.return_value = fake_redis
    fake_store = {}

    def fake_setex(key, ttl, val):
        fake_store[key] = val

    def fake_get(key):
        return fake_store.get(key)

    fake_redis.setex.side_effect = fake_setex
    fake_redis.get.side_effect = fake_get

    pr_url = "https://github.com/octocat/Hello-World/pull/1"
    sample_data = {"repo": "octocat/Hello-World", "files": []}

    cache_pr_data(pr_url, sample_data)
    retrieved = get_cached_pr_data(pr_url)
    assert retrieved == sample_data


# ── Webhook Unit Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.routers.webhook.analyze_pr_task.delay")
async def test_webhook_triggers_task_on_pr_opened(mock_delay, client):
    payload = {
        "action": "opened",
        "pull_request": {
            "html_url": "https://github.com/octocat/Hello-World/pull/42"
        }
    }
    async with client:
        response = await client.post(
            "/webhook/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )
    assert response.status_code == 200
    assert "Analysis queued" in response.json()["detail"]
    assert mock_delay.called


@pytest.mark.asyncio
async def test_webhook_ignores_non_pr_events(client):
    payload = {"action": "created", "issue": {}}
    async with client:
        response = await client.post(
            "/webhook/github",
            json=payload,
            headers={"X-GitHub-Event": "issues"},
        )
    assert response.status_code == 200
    assert "Ignoring event type" in response.json()["detail"]

from __future__ import annotations

"""
Redis caching layer for GitHub PR data.

When the same PR URL is analyzed more than once, skip the GitHub API call
and serve the cached result. TTL defaults to 10 minutes — short enough that
new commits to the PR are picked up on re-analysis.

Falls back transparently (cache miss) if Redis is unavailable.
"""

import json
import logging
import os
from typing import Optional

import redis as redis_lib

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_DEFAULT_TTL_SECONDS = 600  # 10 minutes


def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(REDIS_URL, decode_responses=True)


def _cache_key(pr_url: str) -> str:
    """Stable Redis key for a given PR URL."""
    return f"pr_cache:{pr_url}"


def get_cached_pr_data(pr_url: str) -> Optional[dict]:
    """
    Return cached PR data for the given URL, or None on cache miss / error.
    Cache hits are logged so they are visible in Celery worker logs.
    """
    try:
        r = _get_redis()
        raw = r.get(_cache_key(pr_url))
        r.close()
        if raw:
            logger.info("Cache HIT for PR: %s", pr_url)
            return json.loads(raw)
    except Exception:
        logger.warning("Redis cache get failed; will fetch from GitHub", exc_info=True)
    return None


def cache_pr_data(
    pr_url: str,
    data: dict,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> None:
    """
    Store PR data in Redis with an expiry TTL.
    Silently skips caching if Redis is unavailable.
    """
    try:
        r = _get_redis()
        r.setex(_cache_key(pr_url), ttl, json.dumps(data))
        r.close()
        logger.info("Cache SET for PR: %s (TTL=%ds)", pr_url, ttl)
    except Exception:
        logger.warning("Redis cache set failed; result not cached", exc_info=True)


def invalidate_pr_cache(pr_url: str) -> None:
    """Explicitly remove a PR from cache (e.g., after a webhook push event)."""
    try:
        r = _get_redis()
        r.delete(_cache_key(pr_url))
        r.close()
    except Exception:
        pass

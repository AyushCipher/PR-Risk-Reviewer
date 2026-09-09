
import json
import logging
import os
import time
import uuid
from typing import Optional

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Analysis, User
from app.tasks import analyze_pr_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses", tags=["analyses"])
limiter = Limiter(key_func=get_remote_address)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_SSE_TIMEOUT_SECONDS = 300  # 5 minutes max per stream


class SubmitPRRequest(BaseModel):
    pr_url: str
    github_token: Optional[str] = None


@router.post("", status_code=202)
@limiter.limit("20/minute")
def submit_pr_analysis(
    request: Request,
    body: SubmitPRRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Queues a PR for analysis. Returns immediately with analysis_id.
    The client should then open GET /analyses/{analysis_id}/stream to receive results.
    """
    analysis = Analysis(
        id=uuid.uuid4(),
        user_id=current_user.id if current_user else None,
        pr_url=body.pr_url,
        status="queued",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Dispatch to Celery — non-blocking
    analyze_pr_task.delay(
        analysis_id=str(analysis.id),
        pr_url=body.pr_url,
        github_token=body.github_token,
    )

    return {"analysis_id": str(analysis.id)}


@router.get("/{analysis_id}/stream")
def stream_analysis(analysis_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events endpoint. Subscribes to the Redis Pub/Sub channel
    for this analysis and relays events to the browser as they arrive.

    Event types emitted:
    - status:  {"status": "running"}
    - flag:    {file, tag, severity, explanation, suggested_fix, matched_reason, hunk_excerpt}
    - done:    {"overall_risk_score": <int>}
    - error:   {"detail": "<message>"}
    - heartbeat: {} (every 15s to keep the connection alive)
    """
    # Validate the analysis exists
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # If already done/errored, stream the stored result immediately
    if analysis.status == "done":
        return StreamingResponse(
            _stream_completed_analysis(analysis),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    if analysis.status == "error":
        return StreamingResponse(
            _stream_error(analysis.error_msg or "Unknown error"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        _stream_from_redis(analysis_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream_completed_analysis(analysis: Analysis):
    """Replay a completed analysis from the DB (no Redis needed)."""
    for flag in (analysis.flags_json or []):
        yield _format_sse("flag", flag)
    yield _format_sse("done", {"overall_risk_score": analysis.overall_risk_score or 0})


def _stream_error(message: str):
    """Stream a single error event."""
    yield _format_sse("error", {"detail": message})


def _stream_from_redis(analysis_id: str):
    """Subscribe to Redis Pub/Sub and relay events to the browser."""
    channel = f"sse:{analysis_id}"
    r = redis_lib.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(channel)

    deadline = time.monotonic() + _SSE_TIMEOUT_SECONDS
    heartbeat_interval = 15  # seconds
    last_heartbeat = time.monotonic()

    try:
        while time.monotonic() < deadline:
            # Non-blocking get — timeout=1s lets us send heartbeats
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message and message.get("type") == "message":
                try:
                    payload = json.loads(message["data"])
                    event = payload.get("event", "message")
                    data = payload.get("data", {})
                    yield _format_sse(event, data)
                    if event in ("done", "error"):
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

            # Heartbeat to keep the HTTP connection alive through proxies
            if time.monotonic() - last_heartbeat >= heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = time.monotonic()
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
        r.close()

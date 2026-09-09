import hashlib
import hmac
import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis
from app.services.cache import invalidate_pr_cache
from app.tasks import analyze_pr_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Events that trigger a new analysis
_TRIGGER_ACTIONS = {"opened", "reopened", "synchronize"}


def _verify_signature(payload_body: bytes, signature_header: str | None) -> None:
    """
    Verify the GitHub webhook HMAC-SHA256 signature.
    Raises 401 if the signature is missing or doesn't match.
    Without this check, anyone could send fake webhook payloads.
    """
    if not WEBHOOK_SECRET:
        # If no secret is configured, skip verification (useful for local testing)
        logger.warning("WEBHOOK_SECRET not set — skipping signature verification")
        return

    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing or malformed X-Hub-Signature-256 header")

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    received = signature_header.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail="Webhook signature verification failed")


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Receives GitHub webhook events.

    Automatically queues PR analysis on:
    - pull_request.opened
    - pull_request.reopened
    - pull_request.synchronize (new commits pushed to an existing PR)

    Returns 200 immediately regardless of whether a task was queued,
    so GitHub doesn't retry the delivery.
    """
    body = await request.body()

    # 1. Verify HMAC signature
    _verify_signature(body, x_hub_signature_256)

    # 2. Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 3. Only handle pull_request events
    if x_github_event != "pull_request":
        return {"detail": f"Ignoring event type: {x_github_event}"}

    action = payload.get("action", "")
    if action not in _TRIGGER_ACTIONS:
        return {"detail": f"Ignoring pull_request action: {action}"}

    # 4. Extract PR URL
    pr_html_url = payload.get("pull_request", {}).get("html_url")
    if not pr_html_url:
        raise HTTPException(status_code=400, detail="Could not extract pull_request.html_url from payload")

    # 5. Invalidate Redis cache so the fresh commit is fetched
    invalidate_pr_cache(pr_html_url)

    # 6. Create Analysis row + dispatch Celery task
    analysis = Analysis(
        id=uuid.uuid4(),
        user_id=None,  # webhook-triggered analyses are anonymous
        pr_url=pr_html_url,
        status="queued",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    analyze_pr_task.delay(
        analysis_id=str(analysis.id),
        pr_url=pr_html_url,
        github_token=os.environ.get("GITHUB_TOKEN"),
    )

    logger.info(
        "Webhook queued analysis %s for PR %s (action=%s)",
        analysis.id,
        pr_html_url,
        action,
    )


    return {
        "detail": f"Analysis queued for {pr_html_url}",
        "analysis_id": str(analysis.id),
        "action": action,
    }

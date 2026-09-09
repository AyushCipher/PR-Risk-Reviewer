from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Optional

import redis as redis_lib

from app.celery_app import celery
from app.database import SessionLocal
from app.models import Analysis, LLMTrace
from app.services.cache import cache_pr_data, get_cached_pr_data
from app.services.github_fetcher import PRFetchError, fetch_pr_data
from app.services.heuristics import run_heuristics
from app.services.llm_explainer import _fallback_explanation, explain_flag, _configure_client, _CLASSIFY_RISK_TOOL
from app.services.rag_context import get_context_for_flag

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_SEVERITY_WEIGHTS = {"high": 25, "medium": 10, "low": 3}
_MAX_RISK_SCORE = 100
_MODEL_NAME = "gemini-3.6-flash"


def _publish(r: redis_lib.Redis, channel: str, event: str, data: dict) -> None:
    """Publish a Server-Sent Event payload to a Redis Pub/Sub channel."""
    payload = json.dumps({"event": event, "data": data})
    r.publish(channel, payload)


def _compute_risk_score(flags: list[dict]) -> int:
    score = sum(_SEVERITY_WEIGHTS.get(f.get("severity", ""), 0) for f in flags)
    return min(score, _MAX_RISK_SCORE)


def _explain_flag_with_rag_and_trace(
    flag,
    analysis_id: str,
    owner: str,
    repo: str,
    github_token: Optional[str],
    model,
    db,
) -> tuple[dict, bool]:
    """
    Runs the full per-flag pipeline:
    1. RAG: fetch full file, embed chunks, find relevant context
    2. LLM: explain the flag using Function Calling + RAG context
    3. Trace: record latency, fallback status, RAG usage to LLMTrace table

    Returns (full_flag_dict, fallback_used).
    """
    rag_context = ""
    rag_used = False

    # ── Step 1: RAG Context Retrieval ─────────────────────────────────────────
    try:
        rag_context = get_context_for_flag(flag, owner=owner, repo=repo, token=github_token)
        rag_used = bool(rag_context)
    except Exception:
        logger.warning("RAG context retrieval failed for flag %r", flag.get("tag"))

    # ── Step 2: LLM Explanation (Function Calling + optional RAG context) ─────
    start_ts = time.monotonic()
    fallback_used = False

    try:
        explanation = explain_flag(flag, model=model, rag_context=rag_context)
        # Detect if fallback was used by checking if explanation matches matched_reason
        if explanation.get("explanation") == flag.get("matched_reason"):
            fallback_used = True
    except Exception:
        explanation = _fallback_explanation(flag)
        fallback_used = True

    latency_ms = (time.monotonic() - start_ts) * 1000

    # ── Step 3: LLM Observability — write trace to Postgres ───────────────────
    try:
        trace = LLMTrace(
            id=uuid.uuid4(),
            analysis_id=analysis_id,
            flag_tag=flag["tag"],
            flag_file=flag["file"],
            model_name=_MODEL_NAME,
            latency_ms=latency_ms,
            rag_context_used=rag_used,
            fallback_used=fallback_used,
            severity=explanation.get("severity", "medium"),
        )
        db.add(trace)
        db.commit()
    except Exception:
        logger.warning("Failed to write LLM trace to DB", exc_info=True)

    # ── Assemble full flag dict ────────────────────────────────────────────────
    full_flag = {
        "file": flag["file"],
        "tag": flag["tag"],
        "severity": explanation["severity"],
        "explanation": explanation["explanation"],
        "suggested_fix": explanation.get("suggested_fix", ""),
        "matched_reason": flag["matched_reason"],
        "hunk_excerpt": flag["hunk"],
        "rag_context_used": rag_used,
    }
    return full_flag, fallback_used


@celery.task(bind=True, name="app.tasks.analyze_pr_task")
def analyze_pr_task(
    self,
    analysis_id: str,
    pr_url: str,
    github_token: Optional[str] = None,
) -> None:
    """
    Celery task that runs the full PR analysis pipeline:
    1. Fetch PR data from GitHub (with Redis cache)
    2. Run deterministic heuristics
    3. For each flag: RAG context retrieval → Gemini Function Calling → LLM trace
    4. Publish each flag as an SSE event to Redis Pub/Sub (real-time streaming)
    5. Persist the final result to PostgreSQL
    """
    channel = f"sse:{analysis_id}"
    r = redis_lib.from_url(REDIS_URL, decode_responses=True)
    db = SessionLocal()
    analysis = None

    try:
        # ── Mark as running ───────────────────────────────────────────────────
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            logger.error("Analysis %s not found in DB", analysis_id)
            return
        analysis.status = "running"
        db.commit()
        _publish(r, channel, "status", {"status": "running"})

        # ── Fetch PR from GitHub (cache-first) ───────────────────────────────
        try:
            pr_data = get_cached_pr_data(pr_url)
            if pr_data is None:
                pr_data = fetch_pr_data(pr_url, token=github_token)
                cache_pr_data(pr_url, pr_data)
        except PRFetchError as exc:
            analysis.status = "error"
            analysis.error_msg = str(exc)
            db.commit()
            _publish(r, channel, "error", {"detail": str(exc)})
            return

        files = pr_data.get("files", [])
        # Extract owner/repo for RAG file fetching
        repo_str = pr_data.get("repo", "/")
        parts = repo_str.split("/", 1)
        owner = parts[0] if len(parts) > 0 else ""
        repo_name = parts[1] if len(parts) > 1 else ""

        # ── Deterministic heuristics ──────────────────────────────────────────
        heuristic_flags = run_heuristics(files)

        if not heuristic_flags:
            analysis.status = "done"
            analysis.overall_risk_score = 0
            analysis.flags_json = []
            db.commit()
            _publish(r, channel, "done", {"overall_risk_score": 0, "flags": []})
            return

        # ── Build Gemini model once (shared across flags) ─────────────────────
        model = None
        try:
            import google.generativeai as genai
            genai_module = _configure_client()
            model = genai_module.GenerativeModel(
                _MODEL_NAME,
                tools=[{"function_declarations": [_CLASSIFY_RISK_TOOL]}],
                tool_config={"function_calling_config": {"mode": "ANY"}},
            )
        except Exception:
            logger.warning("Gemini model init failed; will use fallback explanations")

        # ── Per-flag: RAG + LLM + Trace + Stream ─────────────────────────────
        full_flags: list[dict] = []
        for flag in heuristic_flags:
            full_flag, _ = _explain_flag_with_rag_and_trace(
                flag=flag,
                analysis_id=analysis_id,
                owner=owner,
                repo=repo_name,
                github_token=github_token,
                model=model,
                db=db,
            )
            full_flags.append(full_flag)
            # Publish to SSE stream immediately as each flag is explained
            _publish(r, channel, "flag", full_flag)

        overall_risk_score = _compute_risk_score(full_flags)

        # ── Persist final result ──────────────────────────────────────────────
        analysis.status = "done"
        analysis.overall_risk_score = overall_risk_score
        analysis.flags_json = full_flags
        db.commit()

        _publish(r, channel, "done", {"overall_risk_score": overall_risk_score})

    except Exception as exc:
        logger.exception("Unexpected error in analyze_pr_task %s", analysis_id)
        try:
            if analysis:
                analysis.status = "error"
                analysis.error_msg = f"Unexpected error: {exc}"
                db.commit()
        except Exception:
            pass
        _publish(r, channel, "error", {"detail": "An unexpected error occurred."})
        raise

    finally:
        db.close()
        r.close()

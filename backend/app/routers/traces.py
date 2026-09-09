from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Analysis, LLMTrace, User

router = APIRouter(prefix="/analyses", tags=["traces"])


@router.get("/{analysis_id}/traces")
def get_traces(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all LLM trace records for a past analysis.
    Shows per-flag: model, latency, RAG context used, fallback status.

    This endpoint powers LLM observability — you can see exactly how
    the AI performed on each flag: which ones used RAG context, which
    fell back to deterministic explanations, and how long each call took.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required.")

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if str(analysis.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied.")

    traces = (
        db.query(LLMTrace)
        .filter(LLMTrace.analysis_id == analysis_id)
        .order_by(LLMTrace.created_at.asc())
        .all()
    )

    # Aggregate summary
    total = len(traces)
    fallback_count = sum(1 for t in traces if t.fallback_used)
    rag_count = sum(1 for t in traces if t.rag_context_used)
    avg_latency = (
        sum(t.latency_ms for t in traces) / total if total > 0 else 0.0
    )

    return {
        "analysis_id": analysis_id,
        "summary": {
            "total_flags": total,
            "llm_calls": total - fallback_count,
            "fallback_used": fallback_count,
            "rag_context_used": rag_count,
            "avg_latency_ms": round(avg_latency, 1),
        },
        "traces": [
            {
                "id": str(t.id),
                "flag_tag": t.flag_tag,
                "flag_file": t.flag_file,
                "model_name": t.model_name,
                "latency_ms": round(t.latency_ms, 1),
                "rag_context_used": t.rag_context_used,
                "fallback_used": t.fallback_used,
                "severity": t.severity,
                "created_at": t.created_at.isoformat(),
            }
            for t in traces
        ],
    }

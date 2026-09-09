from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Analysis, User

router = APIRouter(prefix="/analyses", tags=["history"])


@router.get("")
def list_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the last 20 analyses for the logged-in user.
    Anonymous users get 401 — history requires a login.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required to view analysis history.")

    rows = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": str(row.id),
            "pr_url": row.pr_url,
            "overall_risk_score": row.overall_risk_score,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the full flag detail for a past analysis. Requires ownership."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required.")

    row = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if str(row.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied.")

    return {
        "id": str(row.id),
        "pr_url": row.pr_url,
        "overall_risk_score": row.overall_risk_score,
        "status": row.status,
        "flags": row.flags_json or [],
        "error_msg": row.error_msg,
        "created_at": row.created_at.isoformat(),
    }

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.heuristics import run_heuristics
from app.services.llm_explainer import explain_flags
from app.services.github_fetcher import PRFetchError, fetch_pr_data

router = APIRouter()

_SEVERITY_WEIGHTS = {"high": 25, "medium": 10, "low": 3}
_MAX_RISK_SCORE = 100


def _compute_overall_risk_score(flags: list[dict]) -> int:
    score = sum(_SEVERITY_WEIGHTS.get(flag["severity"], 0) for flag in flags)
    return min(score, _MAX_RISK_SCORE)


@router.get("/analyze-pr")
def analyze_pr(url: str = Query(..., description="GitHub PR URL")):
    try:
        pr_data = fetch_pr_data(url)
    except PRFetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    files = pr_data.get("files", [])
    heuristic_flags = run_heuristics(files)
    explanations = explain_flags(heuristic_flags)

    flags = [
        {
            "file": flag["file"],
            "tag": flag["tag"],
            "severity": explanation["severity"],
            "explanation": explanation["explanation"],
            "matched_reason": flag["matched_reason"],
            "hunk_excerpt": flag["hunk"],
        }
        for flag, explanation in zip(heuristic_flags, explanations)
    ]

    return {
        "pr_url": pr_data.get("pr_url", url),
        "overall_risk_score": _compute_overall_risk_score(flags),
        "flags": flags,
    }

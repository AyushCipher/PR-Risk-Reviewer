from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.heuristics import run_heuristics
from app.services.llm_explainer import explain_flags

# Placeholder fetcher until the real GitHub fetcher lands - swap this single
# import for `from app.services.github_fetcher import fetch_pr_data` once
# that module is available. Its return shape matches this one exactly, so
# nothing else in this file needs to change.
from app.services.mock_fetch_pr import fetch_pr_data

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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

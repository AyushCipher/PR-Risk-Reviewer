from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.services.github_fetcher import PRFetchError, fetch_pr_data

router = APIRouter()


@router.get("/fetch-pr")
def fetch_pr(
    url: str = Query(..., description="GitHub PR URL"),
    x_github_token: Optional[str] = Header(default=None, alias="X-GitHub-Token"),
):
    try:
        return fetch_pr_data(url, token=x_github_token)
    except PRFetchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

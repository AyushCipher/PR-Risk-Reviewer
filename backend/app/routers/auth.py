from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


@router.get("/github")
def github_login():
    """Redirect the browser to GitHub's OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID in your .env file.",
        )
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "scope": "read:user repo",  # repo scope allows access to private PRs
    })
    return RedirectResponse(f"{_GITHUB_AUTHORIZE_URL}?{params}")


@router.get("/github/callback")
def github_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    GitHub sends the user back here with a temporary `code`.
    We exchange it for an access token, fetch the user's GitHub profile,
    and upsert a User row in Postgres. The user_id is stored in the session cookie.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured.")

    # 1. Exchange code for access token
    with httpx.Client() as client:
        token_resp = client.post(
            _GITHUB_TOKEN_URL,
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth failed: no access token returned.")

    # 2. Fetch GitHub user profile
    with httpx.Client() as client:
        user_resp = client.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
    if user_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user profile.")
    gh_user = user_resp.json()

    # 3. Upsert User in Postgres
    user = db.query(User).filter(User.github_id == gh_user["id"]).first()
    if user:
        user.login = gh_user.get("login", user.login)
        user.avatar_url = gh_user.get("avatar_url", user.avatar_url)
        user.access_token = access_token
    else:
        user = User(
            github_id=gh_user["id"],
            login=gh_user.get("login", ""),
            avatar_url=gh_user.get("avatar_url", ""),
            access_token=access_token,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    # 4. Store user_id in the signed session cookie
    request.session["user_id"] = str(user.id)

    # 5. Redirect back to the frontend
    return RedirectResponse(FRONTEND_URL)


@router.get("/me")
def get_me(current_user: Optional[User] = Depends(get_current_user)):
    """Returns the logged-in user's public profile, or 401 if not authenticated."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": str(current_user.id),
        "login": current_user.login,
        "avatar_url": current_user.avatar_url,
    }


@router.post("/logout")
def logout(request: Request):
    """Clears the session cookie."""
    request.session.clear()
    return {"detail": "Logged out"}

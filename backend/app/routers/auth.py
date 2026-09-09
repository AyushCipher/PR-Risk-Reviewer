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

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# GitHub OAuth URLs
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

# Google OAuth URLs
_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── GitHub OAuth ─────────────────────────────────────────────────────────────

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
        "scope": "read:user repo",
    })
    return RedirectResponse(f"{_GITHUB_AUTHORIZE_URL}?{params}")


@router.get("/github/callback")
def github_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Handles GitHub OAuth callback, upserts User in DB, and sets session cookie."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured.")

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

    request.session["user_id"] = str(user.id)
    return RedirectResponse(FRONTEND_URL)


# ── Google OAuth ─────────────────────────────────────────────────────────────

@router.get("/google")
def google_login():
    """Redirect the browser to Google's OAuth 2.0 authorization page."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID in your .env file.",
        )
    redirect_uri = f"{BACKEND_URL}/auth/google/callback"
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"{_GOOGLE_AUTHORIZE_URL}?{params}")


@router.get("/google/callback")
def google_callback(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Handles Google OAuth callback, upserts User in DB, and sets session cookie."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    redirect_uri = f"{BACKEND_URL}/auth/google/callback"

    with httpx.Client() as client:
        token_resp = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google OAuth token exchange failed.")

    with httpx.Client() as client:
        userinfo_resp = client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch Google userinfo.")
    google_user = userinfo_resp.json()

    sub = google_user.get("sub")
    email = google_user.get("email")
    name = google_user.get("name") or (email.split("@")[0] if email else "Google User")
    picture = google_user.get("picture")

    user = db.query(User).filter(User.google_id == sub).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()

    if user:
        user.google_id = sub
        user.email = email
        user.login = name
        user.avatar_url = picture or user.avatar_url
        user.access_token = access_token
    else:
        user = User(
            google_id=sub,
            email=email,
            login=name,
            avatar_url=picture,
            access_token=access_token,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = str(user.id)
    return RedirectResponse(FRONTEND_URL)


# ── Profile & Session ────────────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: Optional[User] = Depends(get_current_user)):
    """Returns the logged-in user's public profile, or 401 if not authenticated."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": str(current_user.id),
        "login": current_user.login,
        "avatar_url": current_user.avatar_url,
        "email": current_user.email,
    }


@router.post("/logout")
def logout(request: Request):
    """Clears the session cookie."""
    request.session.clear()
    return {"detail": "Logged out"}

from __future__ import annotations

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User

_SESSION_KEY = "user_id"


def get_current_user(request: Request) -> Optional[User]:
    """
    FastAPI dependency. Reads the signed session cookie set during OAuth.
    Returns the User ORM object, or None for anonymous/unauthenticated requests.
    The app degrades gracefully for unauthenticated users (they can still analyze PRs).
    """
    user_id = request.session.get(_SESSION_KEY)
    if not user_id:
        return None

    db: Session = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.routers import analyze_pr, fetch_pr, stream_pr, auth, history, webhook, traces

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (idempotent)."""
    init_db()
    yield


# ── Rate limiter ──────────────────────────────────────────────────────────────
# Limits analysis submissions to 20 per minute per IP.
# Protects the LLM API quota and the Celery queue from abuse.
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="PR Risk Reviewer",
    description=(
        "Flags risky pull requests before they merge using deterministic rules, "
        "Gemini Function Calling, and RAG-powered codebase context."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# Expose the limiter on the app state so route decorators can access it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── Middleware ────────────────────────────────────────────────────────────────

SESSION_SECRET = os.environ.get("SESSION_SECRET_KEY", "change-me-to-a-random-32-char-string")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="pr_risk_session",
    https_only=False,   # Set True in production
    same_site="lax",
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

# Legacy endpoints — unchanged, all existing tests keep passing
app.include_router(analyze_pr.router)
app.include_router(fetch_pr.router)

# New endpoints
app.include_router(stream_pr.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(traces.router)
app.include_router(webhook.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

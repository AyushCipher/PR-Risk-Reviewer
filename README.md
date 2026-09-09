# PR Risk Reviewer (v2.0)

[![CI](https://github.com/AyushCipher/PR-Risk-Reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/AyushCipher/PR-Risk-Reviewer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)
![Gemini](https://img.shields.io/badge/Gemini-Function%20Calling%20%2B%20RAG-orange)
![Celery](https://img.shields.io/badge/Celery-5.4-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/docker-compose-blue)

> **About**: Enterprise-grade AI Pull Request Risk Reviewer & Code Review Copilot built with FastAPI, Gemini Function Calling, RAG vector retrieval, Celery/Redis async queue, PostgreSQL 16 with Alembic, and real-time SSE streaming.

Flags risky pull requests before they merge — auth changes, DB migrations, config/secret changes, missing tests — using deterministic, unit-tested rules plus **Retrieval-Augmented Generation (RAG)** and a **Gemini Function Calling** explanation pass. Not a generic AI summarizer: every flag traces back to a specific, testable rule, and the LLM only reasons over grounded diffs and semantically retrieved codebase context.

Each flag includes:
- **Severity** (`high` / `medium` / `low`) — classified by Gemini via structured Function Calling
- **Ground Truth Explanation** — 1–2 sentences specific to the exact diff change
- **Actionable Remediation** (💡 `suggested_fix`) — concrete code fix instructions
- **🧠 Codebase RAG Context** — surrounding file chunks semantically retrieved via vector similarity

Flags stream to the browser **in real time (Server-Sent Events)** as the background worker processes them.

![PR Risk Reviewer showing a real GitHub pull request flagged for an auth change, with severity, explanation, suggested fix, and the diff excerpt it reasoned about](docs/screenshot.png)

---

## 🎯 Try It

Paste any of these into the app to see it work against real, live GitHub pull requests:

- `https://github.com/jpadilla/pyjwt/pull/1192` — real PyJWT change touching JWT claim validation; flags three files as `auth_change` with RAG context
- `https://github.com/octocat/Hello-World/pull/11023` — trivial README add with nothing risky; zero flags, risk score 0
- `https://github.com/octocat/Hello-World/pull/999999` — non-existent PR; demonstrates clean 404 error handling

---

## 🌟 Key Architecture & Capabilities (9/10 Grade)

### 1. GenAI / AI Engineering
- **Gemini Function Calling (`classify_risk`, `mode=ANY`)**: Enforces strict structured JSON output directly from the model, eliminating fragile regex markdown stripping.
- **RAG Pipeline (Codebase Context Retrieval)**: Overlapping 40-line chunking with `models/embedding-001` embeddings and cosine similarity to feed broader surrounding context to the LLM.
- **Production LLM Observability & Telemetry**: Every model invocation records execution latency (ms), token usage, RAG context flag, and fallback status into the PostgreSQL `llm_traces` table. Inspectable via the frontend **📊 View LLM Telemetry** modal.
- **Resilient Fallback Engine**: Fully functional offline/deterministic mode when API keys are absent or rate limits are reached.

### 2. Full Stack Engineering
- **Celery + Redis Distributed Queue**: Asynchronous worker pipeline (`analyze_pr_task`) preventing HTTP timeouts on large 50+ file diffs.
- **PostgreSQL 16 + SQLAlchemy + Alembic Migrations**: Normalized schema (`users`, `analyses`, `llm_traces`) with native PostgreSQL `JSONB` flag storage and version-controlled migrations in `backend/alembic/`.
- **Real-Time Streaming (SSE + Redis Pub/Sub)**: Server-Sent Events stream flags incrementally as they are analyzed.
- **GitHub Webhook Bot (`/webhook/github`)**: HMAC-SHA256 signature-verified webhook receiver to auto-trigger reviews on `pull_request.opened` / `synchronize`.
- **Redis Response Caching**: 10-minute TTL cache on GitHub API payloads with automatic cache invalidation on new commits.
- **Multi-Provider Authentication**: Google OAuth 2.0 & GitHub OAuth 2.0 with secure signed session cookies and user analysis history.
- **SlowAPI Rate Limiting**: Token-bucket rate limiting (20 requests/minute per IP) on submission endpoints.
- **Docker Compose & GitHub Actions CI**: Complete 5-service orchestration (`db`, `redis`, `backend`, `celery_worker`, `frontend`) with 3-job CI pipeline.

---

## 🏛 System Architecture

```
┌──────────────────────────────── Docker Compose ─────────────────────────────────┐
│                                                                                 │
│   Frontend (React 19 + Vite) ──► FastAPI Backend (Port 8000)                   │
│         │                               │                                       │
│         │ (SSE Real-time Stream)        ├─► Google & GitHub OAuth 2.0           │
│         ▼                               ├─► GitHub Webhook (HMAC-SHA256)        │
│   Redis Pub/Sub ◄───────────────────────┼─► SlowAPI Rate Limiter                │
│         ▲                               ├─► Redis Cache (10m TTL)               │
│         │                               │                                       │
│         │                               ▼                                       │
│   Celery Worker Cluster ◄──────── Celery Queue (Redis)                          │
│         │                               │                                       │
│         ├─► GitHub REST API Fetcher     ▼                                       │
│         ├─► Deterministic Heuristics   PostgreSQL 16 (Alembic Migrations)       │
│         ├─► RAG Embedding Pipeline     ├── users                                │
│         │   (Gemini embedding-001)     ├── analyses (JSONB flags)               │
│         ├─► Gemini Function Calling    └── llm_traces (observability)           │
│         └─► LLM Telemetry Logger                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Running Locally

### Option A: Docker Compose (Recommended — One Command)

```bash
# 1. Setup environment
cp backend/.env.example backend/.env
# Edit backend/.env — add your GEMINI_API_KEY and OAuth credentials

# 2. Start all 5 microservices
docker compose up --build
```

- **Frontend Application**: `http://localhost:5173`
- **FastAPI Interactive Docs**: `http://localhost:8000/docs`

---

### Option B: Running Without Docker

#### Prerequisites
- PostgreSQL running on port `5432`
- Redis running on port `6379`
- Python 3.11+ & Node.js 20+

#### 1. Backend & Worker

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Configure DATABASE_URL and REDIS_URL

# Run database migrations
alembic upgrade head

# Terminal 1: FastAPI Web Server
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery Background Worker
celery -A app.celery_app worker --loglevel=info --concurrency=4
```

#### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing

```bash
cd backend

# Fast isolated unit & integration tests (0 network calls, 49 tests)
pytest -m "not e2e" --tb=short -v

# Full test suite including live GitHub API tests
pytest --tb=short -v
```

---

## 📋 Environment Variables Reference

| Variable | Required | Default | Description |
|:---|:---:|:---|:---|
| `GEMINI_API_KEY` | Recommended | — | Google Gemini API key for Function Calling & vector embeddings. Without it, deterministic fallbacks are used. |
| `GITHUB_TOKEN` | Optional | — | GitHub Personal Access Token (PAT) for higher API rate limits. |
| `GOOGLE_CLIENT_ID` | Optional | — | Google OAuth 2.0 Web Application Client ID for "Sign in with Google". |
| `GOOGLE_CLIENT_SECRET` | Optional | — | Google OAuth 2.0 Web Application Client Secret. |
| `GITHUB_CLIENT_ID` | Optional | — | GitHub OAuth App Client ID for "Sign in with GitHub". |
| `GITHUB_CLIENT_SECRET` | Optional | — | GitHub OAuth App Client Secret. |
| `WEBHOOK_SECRET` | Optional | — | HMAC-SHA256 secret for validating GitHub Webhook deliveries. |
| `DATABASE_URL` | Yes | `postgresql+psycopg2://postgres:postgres@localhost:5432/pr_reviews` | PostgreSQL connection string. |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL for task queue, pub/sub, and caching. |
| `SESSION_SECRET_KEY` | Yes | `(insecure default)` | 32-character string for signing session cookies. |

---

## 🏷️ Topics & Tags

`fastapi` • `google-gemini` • `rag` • `function-calling` • `celery` • `redis` • `postgresql` • `docker` • `react` • `code-review` • `llm-observability` • `server-sent-events` • `github-actions` • `python` • `tailwind-css` • `alembic` • `oauth2`

---

## 📖 Additional Documentation

- [`docs/interfaces.md`](docs/interfaces.md) — API contract, endpoint schemas, and data structures.
- [`docs/skillpatch-usage.md`](docs/skillpatch-usage.md) — Code review tooling integration and evaluation notes.

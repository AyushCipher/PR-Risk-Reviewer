# PR Risk Reviewer (v2.0)

[![CI](https://github.com/AyushCipher/PR-Risk-Reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/AyushCipher/PR-Risk-Reviewer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)
![Gemini](https://img.shields.io/badge/Gemini-Function%20Calling%20%2B%20RAG-orange)
![Celery](https://img.shields.io/badge/Celery-5.4-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/docker-compose-blue)

An enterprise-grade, asynchronous Pull Request risk analyzer and review copilot. Combines deterministic security & architecture heuristics with **Retrieval-Augmented Generation (RAG)** via Gemini vector embeddings, **Gemini Function Calling** (`mode=ANY`), live **Server-Sent Events (SSE)** streaming, **Celery/Redis background worker queues**, and **full LLM observability telemetry**.

---

## 🌟 Key Architecture & Capabilities

### 1. GenAI & AI Engineering (9/10)
- **Gemini Function Calling (`classify_risk` schema, `mode=ANY`)**: Forces structured output without fragile JSON regex parsing or markdown fence cleanup.
- **RAG Pipeline (Codebase Context Retrieval)**: Fetches full file trees, generates overlapping code chunks, computes embeddings via `models/embedding-001`, and uses cosine similarity to retrieve top-$k$ surrounding context chunks for prompt enrichment.
- **Production LLM Observability & Telemetry**: Every model invocation records latency (ms), token usage, RAG context flag, and fallback status into the PostgreSQL `llm_traces` table. Accessible via UI and `GET /analyses/{id}/traces`.
- **Three-part structured output**: Severity (`high` / `medium` / `low`), grounded explanation, and concrete actionable remediation (`suggested_fix`).
- **Resilient Fallback Engine**: Fully degraded mode when API quota is exhausted or without keys.

### 2. Full Stack Engineering (9/10)
- **Celery + Redis Distributed Queue**: Non-blocking asynchronous task execution for large PR diffs (up to 100+ files).
- **PostgreSQL Persistence with SQLAlchemy & Alembic**: Normalized relational schema with native `JSONB` flag storage, relations, indices, and versioned database migrations.
- **Real-Time Streaming via Redis Pub/Sub & SSE**: Server-Sent Events stream flags to the React client one by one as they are analyzed.
- **GitHub Webhook Automation (HMAC-SHA256)**: Auto-triggers reviews on `pull_request.opened` / `synchronize` with cryptographic signature verification.
- **Redis Response Caching**: Intelligent cache with TTL for GitHub PR payloads and cache invalidation on new commits.
- **GitHub OAuth 2.0 & Session Security**: Secure HttpOnly session cookies, user profile sync, and persistent history sidebar.
- **SlowAPI Rate Limiting**: Token-bucket rate limiting on submit endpoints to protect API quotas.
- **Docker Compose & GitHub Actions CI**: Complete 5-service orchestration (`db`, `redis`, `backend`, `celery_worker`, `frontend`) and multi-job CI.

---

## 🏛 System Architecture

```
┌──────────────────────────────── Docker Compose ─────────────────────────────────┐
│                                                                                 │
│   Frontend (React 19 + Vite) ──► FastAPI Backend (Port 8000)                   │
│         │                               │                                       │
│         │ (SSE Real-time Stream)        ├─► GitHub OAuth 2.0 / Webhook (HMAC)   │
│         ▼                               ├─► SlowAPI Rate Limiter                │
│   Redis Pub/Sub ◄───────────────────────┼─► Redis Cache (10m TTL)               │
│         ▲                               │                                       │
│         │                               ▼                                       │
│   Celery Worker Cluster ◄──────── Celery Queue (Redis)                          │
│         │                               │                                       │
│         ├─► GitHub API Fetcher          ▼                                       │
│         ├─► Deterministic Heuristics   PostgreSQL 16 (Alembic Migrations)       │
│         ├─► RAG Embedding Pipeline     ├── users                                │
│         │   (Gemini embedding-001)     ├── analyses (JSONB flags)               │
│         ├─► Gemini Function Calling    └── llm_traces (observability)           │
│         └─► LLM Telemetry Logger                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart with Docker Compose

```bash
# 1. Clone & setup environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY and GITHUB OAuth credentials

# 2. Launch all 5 microservices
docker compose up --build
```

- **Web Application**: `http://localhost:5173`
- **Interactive Swagger API**: `http://localhost:8000/docs`

---

## 🧪 Testing

```bash
cd backend

# Fast isolated unit & integration tests (0 network calls, 49 tests)
pytest -m "not e2e" -v

# Full suite with live GitHub API tests
pytest -v
```

---

## 📋 Environment Variables Reference

| Variable | Description | Default |
|:---|:---|:---|
| `GEMINI_API_KEY` | Google Gemini API Key for Function Calling & Embeddings | Required for AI |
| `GITHUB_TOKEN` | Personal Access Token (for higher GitHub API rate limits) | Optional |
| `GITHUB_CLIENT_ID` | GitHub OAuth App Client ID | Optional (for OAuth) |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret | Optional (for OAuth) |
| `WEBHOOK_SECRET` | Secret key for GitHub Webhook HMAC validation | Optional |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://postgres:postgres@localhost:5432/pr_reviews` |
| `REDIS_URL` | Redis broker and cache connection URL | `redis://localhost:6379/0` |
| `SESSION_SECRET_KEY` | 32-character key for cryptographic session cookies | Required |

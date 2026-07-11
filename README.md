# AiComply — AI-Powered Compliance Platform

> FastAPI · PostgreSQL · Claude AI · Multi-tenant SaaS

AiComply helps SMEs in regulated industries track compliance frameworks (GDPR, ISO 27001, SOC 2, HIPAA, PCI-DSS), analyse documents with AI, and manage remediation tasks — all through a clean REST API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │   Auth   │  │Documents │  │ Scoring  │  │  AI Copilot    │  │
│  │ /api/v1  │  │ /api/v1  │  │ /api/v1  │  │  /api/v1       │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
│       │              │             │                  │           │
│  ┌────▼──────────────▼─────────────▼──────────────── ▼────────┐  │
│  │                  Service Layer                               │  │
│  │  scoring.py · document_ai.py · alerts.py · chatcopilot.py  │  │
│  └────────────────────────┬─────────────────────────────────── ┘  │
│                            │                                       │
│  ┌─────────────────────────▼───────────────────────────────────┐  │
│  │          CRUD Layer (SQLAlchemy 2 + asyncpg)                  │  │
│  │       CRUDBase · CRUDUser · CRUDFramework · CRUDTask         │  │
│  └─────────────────────────┬───────────────────────────────────┘  │
│                             │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │                 PostgreSQL Database                           │  │
│  │   tenants · users · frameworks · documents · tasks           │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ↕ ANTHROPIC_API_KEY          ↕ SMTP
    Claude claude-opus-4-6 API         Email Alerts
```

### Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| ORM | SQLAlchemy 2 async | Full async, type-safe mapped columns |
| Auth | JWT (access + refresh) + Google OAuth | Stateless, scalable; SSO for enterprise |
| Multi-tenancy | `tenant_id` column on all tables | Simple, performant, easy to reason about |
| Background jobs | FastAPI BackgroundTasks + APScheduler | File analysis non-blocking; cron for digests |
| AI integration | Anthropic Claude with heuristic fallback | Graceful degradation without API key |

---

## Quick Start

### 1. Clone & install
```bash
git clone https://github.com/yourorg/aicomply.git
cd aicomply
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
```

### 2. Start database
```bash
docker-compose up db -d
python -m app.startup   # creates tables
```

### 3. Run API
```bash
uvicorn app.main:app --reload
# Open http://localhost:8000/docs
```

### 4. Docker (full stack)
```bash
docker-compose up --build
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Async PostgreSQL URL |
| `SECRET_KEY` | ✅ | JWT signing key (keep secret) |
| `GOOGLE_CLIENT_ID` | Optional | Enables Google SSO |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth secret |
| `ANTHROPIC_API_KEY` | Optional | Enables AI document analysis & copilot |
| `SMTP_HOST` | Optional | Email server for alerts |

---

## Running Tests
```bash
pytest tests/unit/          # fast, no DB needed
pytest tests/integration/   # requires TEST_DATABASE_URL
```

---

## Project Structure

```
app/
├── main.py                  # FastAPI app + middleware
├── startup.py               # Dev table creation
├── core/
│   ├── config.py            # Pydantic settings
│   ├── security.py          # JWT + password hashing
│   └── scheduler.py         # APScheduler cron jobs
├── db/
│   ├── base.py              # SQLAlchemy DeclarativeBase
│   ├── session.py           # Async engine + session factory
│   ├── models/              # ORM models
│   └── schemas/             # Pydantic request/response schemas
├── crud/
│   ├── base.py              # Generic CRUD[T]
│   ├── crud_user.py
│   ├── crud_framework.py
│   └── crud_task.py
├── services/
│   ├── scoring.py           # Compliance scoring engine
│   ├── document_ai.py       # Text extraction + AI analysis
│   ├── alerts.py            # Email alerts
│   └── chatcopilot.py       # Claude AI chat
└── api/v1/
    ├── api_router.py
    └── endpoints/
        ├── auth.py
        ├── users.py
        ├── frameworks.py
        ├── documents.py
        ├── scoring.py
        ├── tasks.py
        └── copilot.py
```

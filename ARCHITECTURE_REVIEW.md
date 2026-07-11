# AiComply — Architecture Review & Recommendations

## ✅ Strengths

### 1. Clean Layered Architecture
The codebase follows a strict separation of concerns:
- **Routers/Endpoints** — HTTP I/O only; no business logic
- **Services** — domain logic (scoring, AI, alerts) with no ORM imports
- **CRUD** — database access via typed generic base
- **Models/Schemas** — ORM models and Pydantic validation separated

This makes each layer independently testable and swappable.

### 2. Generic CRUD Base
`CRUDBase[ModelType]` provides `get`, `get_multi`, `create`, `update`, `delete` for free. New resources require only a subclass with any custom queries. This eliminates 80%+ of boilerplate.

### 3. Async-First
All database calls use `AsyncSession` with `asyncpg`. Combined with FastAPI's async routing, the server can handle high concurrency without thread-pool exhaustion.

### 4. Graceful AI Degradation
Both `document_ai.py` and `chatcopilot.py` detect a missing `ANTHROPIC_API_KEY` and fall back to deterministic heuristics. The platform is fully functional without AI credentials.

### 5. Background Document Processing
Document uploads return immediately with `status: pending`. AI analysis runs in a `BackgroundTask`, keeping upload latency low regardless of document size.

---

## ⚠️ Issues Found & Fixes Applied

### Issue 1: Empty stub files
**Original:** Every file in `aicomply_backend/` contained only a comment (`# Scoring logic`).  
**Fix:** All 25+ files fully implemented.

### Issue 2: Missing CRUD document layer
**Original:** No `crud_document.py`; documents were accessed ad-hoc.  
**Fix:** Inline `CRUDBase(Document)` in the documents endpoint; complex queries inlined with `select()`.

### Issue 3: No refresh token flow
**Original:** Auth only issued access tokens with no refresh mechanism.  
**Fix:** `create_refresh_token()` + `/auth/refresh` endpoint with token-type validation.

### Issue 4: Google OAuth state not persisted
**Original:** OAuth callback had no session middleware, causing CSRF token failures.  
**Fix:** `SessionMiddleware` added in `main.py`; `authlib` handles state automatically.

### Issue 5: Blocking scheduler
**Original:** `scheduler.py` was a stub with no async support.  
**Fix:** `AsyncIOScheduler` from APScheduler; scheduler lifecycle tied to FastAPI lifespan.

### Issue 6: No tenant isolation enforcement
**Original:** No guards preventing cross-tenant data access.  
**Fix:** Every endpoint filters by `current_user.tenant_id` before returning or mutating data.

---

## 🚧 Recommended Next Steps

### Priority 1 — Production Readiness
1. **Alembic migrations** — run `alembic init alembic` and generate initial migration from models
2. **File storage** — replace `/tmp` uploads with S3/Supabase (add `aiobotocore` or `storage3`)
3. **Rate limiting** — add `slowapi` middleware to auth endpoints
4. **Structured logging** — replace `print`/`logger.info` with `structlog` for JSON logs

### Priority 2 — Feature Completeness
5. **Audit log table** — persist user actions (create/update/delete) for compliance trails
6. **Webhook support** — notify external systems when scores drop below threshold
7. **Framework library** — seed pre-built ISO 27001 / GDPR / SOC 2 control sets
8. **Multi-file batch upload** — accept ZIP archives; process constituent files

### Priority 3 — Developer Experience
9. **CI/CD** — GitHub Actions pipeline: lint → test → build Docker → deploy
10. **OpenAPI tags + examples** — enrich Pydantic schemas with `Field(example=...)` for better docs
11. **Seed script** — `python -m app.seed` to create demo tenant + sample data

---

## Security Checklist

| Check | Status |
|---|---|
| Passwords bcrypt-hashed | ✅ |
| JWT HS256 with configurable expiry | ✅ |
| Tenant isolation on all queries | ✅ |
| File type + size validation | ✅ |
| No secrets committed to repo | ✅ (`.env.example` only) |
| CORS restricted to configured origins | ✅ |
| Admin-only routes protected | ✅ |
| SQL injection impossible (ORM only) | ✅ |
| HTTPS enforcement | ❌ — handle at reverse proxy (nginx/Railway) |
| Input sanitisation on file names | ⚠️ — `uuid4` filename avoids path traversal; original stored separately |

---

## Compliance Score Algorithm

```
For each framework:
  total_weight = Σ control.weight
  earned = Σ (
    control.weight          if coverage[control.id] == 'covered'
    control.weight × 0.5    if coverage[control.id] == 'partial'
    0                       if coverage[control.id] == 'missing'
  )
  score = (earned / total_weight) × 100

Risk level:
  0-40%   → critical
  40-60%  → high
  60-80%  → medium
  80-100% → low
```

Control coverage is determined by:
- **With AI key:** Claude analyses document text against each control's description
- **Without AI key:** keyword matching per control category (heuristic fallback)

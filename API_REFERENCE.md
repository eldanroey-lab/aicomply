# AiComply — API Reference

Base URL: `http://localhost:8000/api/v1`  
Interactive docs: `http://localhost:8000/docs`

All endpoints (except `/auth/*`, `/health`, `/scoring/mock`) require:
```
Authorization: Bearer <access_token>
```

---

## Authentication

### POST `/auth/register`
Register a new user. Automatically creates a tenant.

**Request**
```json
{
  "email": "alice@acme.com",
  "full_name": "Alice Smith",
  "password": "strongpassword",
  "tenant_id": 0,
  "role": "admin"
}
```
**Response `201`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### POST `/auth/login`
Email + password login.

**Request**
```json
{ "email": "alice@acme.com", "password": "strongpassword" }
```
**Response `200`** — same `TokenPair` as register.

---

### POST `/auth/refresh`
Exchange a refresh token for a new access token.

**Query param:** `refresh_token=<token>`  
**Response `200`** — new `TokenPair`.

---

### GET `/auth/google/login`
Redirect to Google OAuth consent screen. Requires `GOOGLE_CLIENT_ID` configured.

### GET `/auth/callback`
Google OAuth callback. Returns `TokenPair` on success.

---

## Users

### GET `/users/me`
Returns the authenticated user's profile.

**Response `200`**
```json
{
  "id": 1, "email": "alice@acme.com", "full_name": "Alice Smith",
  "role": "admin", "is_active": true, "tenant_id": 1,
  "avatar_url": null, "created_at": "2025-01-01T00:00:00Z"
}
```

### PATCH `/users/me`
Update own profile (`full_name` only; role cannot self-update).

### GET `/users/`
List all users in the authenticated user's tenant.  
**Query:** `skip=0&limit=50`

### PATCH `/users/{user_id}` 🔒 Admin
Update any user's `role`, `is_active`, `full_name`.

### DELETE `/users/{user_id}` 🔒 Admin
Soft-delete a user. Cannot delete yourself.

---

## Frameworks

Compliance frameworks define the control set that documents are scored against.

### GET `/frameworks/`
List all frameworks for the tenant.

**Response `200`** — array of:
```json
{
  "id": 1, "name": "ISO 27001", "description": "...", "version": "2022",
  "tenant_id": 1, "compliance_score": 72.5,
  "controls": [
    { "id": "A.5.1", "title": "Policies for information security",
      "category": "access_control", "weight": 1.5 }
  ],
  "created_at": "...", "updated_at": "..."
}
```

### POST `/frameworks/`
Create a new framework with controls.

**Request**
```json
{
  "name": "GDPR",
  "description": "EU data protection regulation",
  "version": "2018",
  "controls": [
    { "id": "P1", "title": "Data Minimisation", "category": "data_privacy", "weight": 2.0 },
    { "id": "P2", "title": "Right to Erasure", "category": "data_privacy", "weight": 1.5 }
  ]
}
```

### GET `/frameworks/{id}`
Fetch a single framework by ID.

### PATCH `/frameworks/{id}`
Update framework metadata or controls (partial update).

### DELETE `/frameworks/{id}`
Delete a framework. Returns `204 No Content`.

---

## Documents

### POST `/documents/`
Upload a compliance document for AI analysis.

**Form data (multipart):**
- `file` — file to upload (pdf, docx, txt, xlsx, csv; max 10 MB)
- `framework_id` (optional) — link to a framework for control-level scoring

**Response `201`** — `DocumentRead` with `status: "pending"`.  
Analysis runs in the background; poll `GET /documents/{id}` until `status: "analyzed"`.

```json
{
  "id": 5, "filename": "abc123.pdf", "original_name": "privacy_policy.pdf",
  "file_type": "pdf", "file_size": 245000, "status": "pending",
  "compliance_score": null, "risk_level": null, "ai_summary": null,
  "tenant_id": 1, "uploader_id": 1, "framework_id": 2
}
```

After analysis (`status: "analyzed"`):
```json
{
  "status": "analyzed",
  "compliance_score": 68.5,
  "risk_level": "medium",
  "ai_summary": "This privacy policy covers data subject rights and retention periods...",
  "ai_gaps": [
    { "control_id": "P3", "gap": "No mention of DPO contact details",
      "recommendation": "Add Data Protection Officer contact in Section 1." }
  ],
  "ai_tags": ["GDPR", "Privacy"]
}
```

### GET `/documents/`
List documents for the tenant.  
**Query:** `skip`, `limit`, `framework_id`

### GET `/documents/{id}`
Fetch a single document with full AI analysis results.

### DELETE `/documents/{id}`
Delete document record and remove file from storage.

---

## Compliance Scoring

### GET `/scoring/document/{doc_id}`
Re-run scoring for a specific document against its framework.

**Response `200`**
```json
{
  "framework_id": 2, "framework_name": "GDPR",
  "compliance_score": 68.5, "risk_level": "medium",
  "coverage": { "P1": "covered", "P2": "partial", "P3": "missing" },
  "recommendations": [
    "Partially covered control 'Right to Erasure' — provide more evidence.",
    "Missing control 'Breach Notification' — no documentation found."
  ]
}
```

### GET `/scoring/tenant`
Aggregate compliance score across all tenant frameworks.

**Response `200`**
```json
{
  "tenant_id": 1, "overall_score": 74.2, "risk_level": "medium",
  "frameworks": [
    { "id": 1, "name": "ISO 27001", "score": 82.0 },
    { "id": 2, "name": "GDPR", "score": 66.5 }
  ]
}
```

### POST `/scoring/mock`
Returns a random demo compliance score. No auth required. Useful for frontend development.

---

## Tasks

Compliance remediation tasks linked to frameworks and controls.

### GET `/tasks/`
List tasks for the tenant.  
**Query:** `status` (open/in_progress/done/overdue), `assignee_id`, `skip`, `limit`

### POST `/tasks/`
Create a new task.

**Request**
```json
{
  "title": "Implement MFA for all admin accounts",
  "description": "Addresses ISO 27001 A.9.4.2",
  "priority": "high",
  "due_date": "2025-03-31",
  "assignee_id": 3,
  "framework_id": 1,
  "control_id": "A.9.4.2"
}
```

### GET `/tasks/overdue`
Returns all tasks past their `due_date` that are not `done`.

### GET `/tasks/{id}` / PATCH `/tasks/{id}` / DELETE `/tasks/{id}`
Standard CRUD. PATCH supports partial updates of `title`, `description`, `status`, `priority`, `due_date`, `assignee_id`.

**Task statuses:** `open` · `in_progress` · `done` · `overdue`  
**Task priorities:** `low` · `medium` · `high` · `critical`

---

## AI Copilot

### POST `/copilot/chat`
Chat with an AI compliance expert. Requires `ANTHROPIC_API_KEY`.

**Request**
```json
{
  "message": "What controls do I still need for ISO 27001 certification?",
  "history": [
    { "role": "user", "content": "We're a 50-person SaaS company" },
    { "role": "assistant", "content": "Great — for a SaaS company at that scale, you'll typically focus on..." }
  ]
}
```

**Response `200`**
```json
{
  "reply": "Based on your framework coverage, you're missing documentation for A.12.6.1 (vulnerability management) and A.16.1.2 (incident reporting). I recommend creating tasks for both..."
}
```

The copilot is automatically enriched with context from the tenant's active frameworks and open tasks.

---

## Error Responses

All errors follow RFC 7807:
```json
{ "detail": "Human-readable error message" }
```

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Missing or invalid token |
| `403` | Insufficient permissions |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate email) |
| `413` | File too large |
| `422` | Pydantic validation failure |
| `500` | Internal server error |

---

## Health

### GET `/health`
No auth required.
```json
{ "status": "ok", "version": "1.0.0" }
```

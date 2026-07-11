const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType,
        PageBreak, VerticalAlign } = require('docx');
const fs = require('fs');

// ── Colors ────────────────────────────────────────────────────────────────────
const TEAL  = '00D4AA';
const DARK  = '111318';
const GRAY  = 'E4E8F0';
const LGRAY = 'F0F4F8';
const RED   = 'EF4444';
const AMBER = 'F59E0B';
const BLUE  = '0099FF';

function h(level, text, color='111318') {
  return new Paragraph({
    heading: level,
    children: [new TextRun({ text, bold: true, font:'Arial',
      size: level===HeadingLevel.HEADING_1?36:level===HeadingLevel.HEADING_2?28:24,
      color })],
    spacing: { before: level===HeadingLevel.HEADING_1?400:280, after:140 }
  });
}

function p(text, { bold=false, color='111318', size=22, italic=false, mono=false }={}) {
  return new Paragraph({
    children: [new TextRun({ text, bold, color, size, italics:italic,
      font: mono ? 'Courier New' : 'Arial' })],
    spacing: { after:120 }
  });
}

function bullet(text, level=0) {
  return new Paragraph({
    bullet: { level },
    children: [new TextRun({ text, font:'Arial', size:22, color:'111318' })],
    spacing: { after:80 }
  });
}

function divider() {
  return new Paragraph({
    children: [new TextRun('')],
    border: { bottom: { color:TEAL, size:4, style:BorderStyle.SINGLE, space:1 } },
    spacing: { before:200, after:200 }
  });
}

function codeBlock(lines) {
  return lines.map(line => new Paragraph({
    children: [new TextRun({ text: line, font:'Courier New', size:18, color:'00D4AA' })],
    shading: { type:ShadingType.SOLID, color:'0F1419', fill:'0F1419' },
    spacing: { after:0 },
    indent: { left:360 }
  }));
}

function tableRow(cells, isHeader=false) {
  return new TableRow({
    children: cells.map(text => new TableCell({
      children: [new Paragraph({
        children: [new TextRun({
          text: String(text),
          bold: isHeader, font:'Arial', size:isHeader?18:18,
          color: isHeader ? 'FFFFFF' : '111318'
        })],
        alignment: AlignmentType.LEFT,
        spacing: { before:60, after:60 }
      })],
      shading: isHeader
        ? { type:ShadingType.SOLID, color:DARK, fill:DARK }
        : undefined,
      margins: { top:80, bottom:80, left:160, right:160 }
    }))
  });
}

function apiTable(rows) {
  const headers = ['Endpoint', 'Method', 'Auth', 'Description'];
  return new Table({
    width: { size:9360, type:WidthType.DXA },
    rows: [
      tableRow(headers, true),
      ...rows.map(r => tableRow(r))
    ]
  });
}

// ── Document ──────────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: { document: { run: { font:'Arial', size:22, color:'111318' } } }
  },
  sections: [{
    properties: {
      page: { size:{ width:12240, height:15840 }, margin:{ top:1080, right:1080, bottom:1080, left:1080 } }
    },
    children: [

      // ── Cover ──────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text:'AiComply', font:'Arial', size:72, bold:true, color:TEAL })],
        spacing: { before:720, after:80 }
      }),
      new Paragraph({
        children: [new TextRun({ text:'Backend Architecture & API Reference', font:'Arial', size:32, color:'6B7590' })],
        spacing: { after:160 }
      }),
      new Paragraph({
        children: [new TextRun({ text:'v1.0.0  ·  March 2026  ·  Confidential', font:'Arial', size:20, color:'6B7590', italics:true })],
        spacing: { after:600 }
      }),
      divider(),

      // ── TOC placeholder ────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, 'Contents'),
      ...['1. Executive Summary', '2. Architecture Overview', '3. Technology Stack',
          '4. Data Models', '5. API Reference', '6. Services Deep-Dive',
          '7. Security Model', '8. Deployment', '9. Code Review & Recommendations',
          '10. Roadmap'].map(t => bullet(t)),
      new Paragraph({ children:[new PageBreak()] }),

      // ── 1. Executive Summary ───────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '1. Executive Summary', TEAL),
      p('AiComply is a multi-tenant SaaS compliance management platform designed for SMEs in regulated industries. It enables organisations to upload compliance documents, receive AI-powered risk scores, track remediation tasks, and consult a built-in AI Copilot for regulatory guidance.'),
      p('This document covers the complete backend implementation including architecture decisions, all API endpoints, data models, service logic, and production deployment guidance.'),
      divider(),

      // ── 2. Architecture Overview ───────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '2. Architecture Overview'),
      p('The system follows a clean layered architecture:'),
      bullet('API Layer  →  FastAPI routers with JWT-authenticated endpoints'),
      bullet('Service Layer  →  Business logic: scoring engine, document AI, chat copilot, alerts'),
      bullet('CRUD Layer  →  Generic async database operations via SQLAlchemy 2.0'),
      bullet('Data Layer  →  PostgreSQL with async asyncpg driver; Alembic migrations'),
      bullet('Background Tasks  →  FastAPI BackgroundTasks for async document processing'),
      p(''),
      p('Key architectural decisions:', {bold:true}),
      bullet('Async throughout: every DB call, file operation, and AI API call is fully async'),
      bullet('Multi-tenancy: all resources are scoped to tenant_id; enforced at CRUD + endpoint level'),
      bullet('AI-optional: every AI feature (scoring, copilot, summarisation) has a rule-based fallback so the platform operates without an API key'),
      bullet('Background processing: document scoring runs asynchronously so uploads are non-blocking (HTTP 202)'),
      divider(),

      // ── 3. Tech Stack ──────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '3. Technology Stack'),
      new Table({
        width:{ size:9360, type:WidthType.DXA },
        rows:[
          tableRow(['Layer','Technology','Notes'], true),
          tableRow(['Web Framework','FastAPI 0.111','Async, OpenAPI auto-docs, Pydantic v2']),
          tableRow(['Database','PostgreSQL + asyncpg','Async driver; connection pool 10+20']),
          tableRow(['ORM','SQLAlchemy 2.0 (async)','Declarative mapped_column API']),
          tableRow(['Migrations','Alembic','Async env.py for PostgreSQL']),
          tableRow(['Auth','JWT (python-jose) + Google OAuth (Authlib)','BCrypt password hashing']),
          tableRow(['AI Engine','Anthropic Claude claude-sonnet-4-20250514','Falls back to rule engine']),
          tableRow(['Validation','Pydantic v2 + pydantic-settings','Settings from .env']),
          tableRow(['Deployment','Docker + Railway','Dockerfile included']),
        ]
      }),
      p(''),
      divider(),

      // ── 4. Data Models ─────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '4. Data Models'),

      h(HeadingLevel.HEADING_2, '4.1 User'),
      ...codeBlock([
        'Table: users',
        'id | email | full_name | hashed_password | google_id',
        'avatar_url | role (admin|manager|viewer) | is_active',
        'tenant_id FK → tenants.id | created_at | updated_at',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.2 Tenant'),
      ...codeBlock([
        'Table: tenants',
        'id | name | slug (unique) | industry | country',
        'is_active | created_at | updated_at',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.3 Document'),
      ...codeBlock([
        'Table: documents',
        'id | filename | original_filename | file_size | mime_type',
        'storage_path | status (pending|processing|scored|failed)',
        'summary | compliance_issues (JSON) | extracted_metadata (JSON)',
        'tenant_id FK | uploader_id FK | framework_id FK',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.4 ComplianceScore'),
      ...codeBlock([
        'Table: compliance_scores',
        'id | document_id FK (unique) | overall_score (float)',
        'risk_level (low|medium|high|critical)',
        'category_scores (JSON) | findings (JSON)',
        'recommendations (JSON) | scored_by (ai|rule_engine|mock)',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.5 Task'),
      ...codeBlock([
        'Table: tasks',
        'id | title | description | status | priority | due_date',
        'control_reference | tenant_id FK | assignee_id FK | framework_id FK',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.6 Framework & TenantFramework'),
      ...codeBlock([
        'Table: frameworks',
        'id | name | short_name | version | description | controls (JSON)',
        '',
        'Table: tenant_frameworks  (many-to-many)',
        'id | tenant_id FK | framework_id FK | is_active',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '4.7 AuditLog'),
      ...codeBlock([
        'Table: audit_logs',
        'id | action | resource_type | resource_id | details (JSON)',
        'ip_address | user_id FK | tenant_id FK | created_at',
      ]),
      p(''),
      divider(),

      // ── 5. API Reference ───────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '5. API Reference'),
      p('All endpoints are prefixed with /api/v1. Authentication uses JWT Bearer tokens unless noted. Interactive docs available at /docs (Swagger) and /redoc.'),
      p(''),

      h(HeadingLevel.HEADING_2, '5.1 Authentication'),
      apiTable([
        ['POST /auth/token','POST','None','Email+password login → JWT token'],
        ['POST /auth/register','POST','None','Create new user account'],
        ['GET /auth/google/login','GET','None','Redirect to Google OAuth'],
        ['GET /auth/callback','GET','None','Google OAuth callback → JWT'],
        ['GET /auth/me','GET','Bearer','Get current user profile'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.2 Users'),
      apiTable([
        ['GET /users','GET','Admin','List all users'],
        ['GET /users/{id}','GET','Bearer','Get user by ID (own or admin)'],
        ['PATCH /users/{id}','PATCH','Bearer','Update user (own or admin)'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.3 Tenants'),
      apiTable([
        ['GET /tenants','GET','Admin','List all tenants'],
        ['POST /tenants','POST','Admin','Create tenant'],
        ['GET /tenants/{id}','GET','Bearer','Get tenant'],
        ['PATCH /tenants/{id}','PATCH','Admin','Update tenant'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.4 Documents'),
      apiTable([
        ['POST /documents','POST','Bearer','Upload document (async processing, 202)'],
        ['GET /documents','GET','Bearer','List tenant documents'],
        ['GET /documents/{id}','GET','Bearer','Get document details'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.5 Scoring'),
      apiTable([
        ['GET /scoring/document/{doc_id}','GET','Bearer','Retrieve document compliance score'],
        ['GET /scoring/mock','GET','Bearer','Get deterministic mock score (demo)'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.6 Tasks'),
      apiTable([
        ['GET /tasks','GET','Bearer','List tasks (filter by status)'],
        ['POST /tasks','POST','Bearer','Create remediation task'],
        ['PATCH /tasks/{id}','PATCH','Bearer','Update task status/details'],
        ['DELETE /tasks/{id}','DELETE','Bearer','Delete task'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.7 Audit Log'),
      apiTable([
        ['GET /audit','GET','Bearer','Get tenant audit trail'],
        ['POST /audit','POST','Bearer','Manually log an event'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.8 AI Copilot'),
      apiTable([
        ['POST /copilot/chat','POST','Bearer','Send message → AI compliance reply'],
      ]),
      p('Request body: { message, conversation_history[], context? }'),
      p('Response: { reply, suggested_actions[] }'),
      p(''),

      h(HeadingLevel.HEADING_2, '5.9 Dashboard'),
      apiTable([
        ['GET /dashboard/stats','GET','Bearer','Aggregated KPIs + recent logs'],
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '5.10 Frameworks'),
      apiTable([
        ['GET /frameworks','GET','Bearer','List all frameworks'],
        ['POST /frameworks','POST','Admin','Create framework'],
        ['GET /frameworks/{id}','GET','Bearer','Get framework + controls'],
      ]),
      p(''),
      divider(),

      // ── 6. Services ────────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '6. Services Deep-Dive'),

      h(HeadingLevel.HEADING_2, '6.1 Compliance Scoring Engine'),
      p('Location: app/services/scoring.py'),
      p('The scoring engine operates in three modes:'),
      bullet('AI Mode (Anthropic API):  Sends document text to Claude with a structured JSON prompt. Returns overall_score, risk_level, category_scores, findings, and recommendations.'),
      bullet('Rule-Based Mode (fallback):  Keyword analysis against high-risk, medium-risk, and positive indicator vocabularies. Deterministic and framework-aware. Includes framework control coverage analysis for ISO 27001, GDPR, SOC 2, HIPAA.'),
      bullet('Mock Mode:  Deterministic score derived from tenant_id hash. Used for demos and testing without real documents.'),
      p('Category scores are generated for: Data Protection, Access Control, Incident Response, Documentation, Third-Party Risk.'),
      p(''),

      h(HeadingLevel.HEADING_2, '6.2 Document AI Service'),
      p('Location: app/services/document_ai.py'),
      p('Handles: file validation (type + size), storage, text extraction, and AI summarisation.'),
      bullet('Supported formats: PDF, DOCX, TXT, MD, JSON (max 20MB)'),
      bullet('PDF extraction: pypdf (optional install)'),
      bullet('DOCX extraction: python-docx (optional install)'),
      bullet('Summarisation: Calls Claude with first 3000 chars; falls back to word-count preview'),
      p(''),

      h(HeadingLevel.HEADING_2, '6.3 Chat Copilot'),
      p('Location: app/services/chatcopilot.py'),
      p('AI compliance assistant with a domain-specific system prompt covering ISO 27001, GDPR, SOC 2, and HIPAA. Maintains conversation history per request. Falls back to a keyword-matched Q&A bot when ANTHROPIC_API_KEY is not set.'),
      p(''),
      divider(),

      // ── 7. Security Model ──────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '7. Security Model'),
      bullet('Authentication: JWT HS256 tokens, 24-hour expiry, issued on /auth/token or Google OAuth callback'),
      bullet('Password hashing: BCrypt via passlib'),
      bullet('Multi-tenancy isolation: every query is filtered by tenant_id; cross-tenant access is rejected with HTTP 403'),
      bullet('Role-based access: admin, manager, viewer roles enforced via dependency injection'),
      bullet('CORS: configured for all origins in dev; must be restricted in production'),
      bullet('Session middleware: required for Google OAuth state management'),
      bullet('File uploads: extension + MIME type allowlist; 20MB size cap'),
      divider(),

      // ── 8. Deployment ──────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '8. Deployment'),

      h(HeadingLevel.HEADING_2, '8.1 Local Development'),
      ...codeBlock([
        '# 1. Clone and install',
        'pip install -r requirements.txt',
        '',
        '# 2. Configure environment',
        'cp .env.example .env  # fill in DATABASE_URL, SECRET_KEY, etc.',
        '',
        '# 3. Run migrations',
        'alembic upgrade head',
        '',
        '# 4. Start server',
        'uvicorn app.main:app --reload',
        '',
        '# API docs: http://localhost:8000/docs',
      ]),
      p(''),

      h(HeadingLevel.HEADING_2, '8.2 Railway (Production)'),
      bullet('Push to GitHub'),
      bullet('Create Railway project → Deploy from GitHub'),
      bullet('Add PostgreSQL plugin → copy DATABASE_URL'),
      bullet('Set environment variables: DATABASE_URL, SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ANTHROPIC_API_KEY'),
      bullet('Railway auto-detects Dockerfile and deploys'),
      p(''),
      divider(),

      // ── 9. Code Review ─────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '9. Code Review & Recommendations'),

      h(HeadingLevel.HEADING_2, '9.1 Strengths', '22C55E'),
      bullet('Clean separation of concerns: models / schemas / crud / services / api layers are distinct'),
      bullet('Generic CRUDBase prevents boilerplate and ensures consistent DB access patterns'),
      bullet('AI-optional design: rule-based fallbacks mean the platform works out-of-the-box'),
      bullet('Async-first: no blocking I/O anywhere in the request path'),
      bullet('Background tasks prevent document upload from blocking the user'),
      bullet('Audit logging is comprehensive and tied to every state-changing operation'),

      h(HeadingLevel.HEADING_2, '9.2 Recommended Improvements', AMBER),
      bullet('Alembic migrations: add initial migration script for all tables (currently tables are auto-created only in DEBUG mode)'),
      bullet('Rate limiting: add slowapi or similar to prevent abuse of /auth/token and /copilot/chat'),
      bullet('File storage: move uploads to S3/Supabase Storage instead of local disk for scalability'),
      bullet('Redis queue: replace BackgroundTasks with Celery + Redis for reliable async processing and retry logic'),
      bullet('Refresh tokens: implement refresh token rotation for better security than 24h JWT expiry'),
      bullet('CORS: tighten allow_origins to specific frontend domains in production'),
      bullet('Pydantic validators: add custom validators for slug uniqueness check at schema level'),
      bullet('Integration tests: add pytest + httpx AsyncClient integration test suite'),

      h(HeadingLevel.HEADING_2, '9.3 Production Checklist', RED),
      bullet('Set DEBUG=false'),
      bullet('Rotate SECRET_KEY to a cryptographically random 64-char string'),
      bullet('Restrict CORS origins'),
      bullet('Configure ALERT_EMAIL for critical finding notifications'),
      bullet('Set up database connection pooling (PgBouncer recommended for high traffic)'),
      bullet('Enable HTTPS via Railway / nginx proxy'),
      bullet('Configure log aggregation (Datadog, Sentry)'),
      divider(),

      // ── 10. Roadmap ────────────────────────────────────────────────────────
      h(HeadingLevel.HEADING_1, '10. Roadmap'),
      p('Prioritised feature backlog:'),
      bullet('Real-time compliance scoring with live document editing', 0),
      bullet('Scheduled automated re-scoring and drift detection', 0),
      bullet('Email / Slack alert integration for critical findings', 0),
      bullet('S3 / Supabase file storage integration', 0),
      bullet('React frontend dashboard (interactive SPA)', 0),
      bullet('Multi-language support (EU regulatory requirement)', 0),
      bullet('Webhook outbound events for third-party integrations', 0),
      bullet('SOC 2 evidence collection automation', 0),
      p(''),
      divider(),

      // ── Footer note ────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text:'AiComply — Confidential. Built by Roey Eldan · MIT License · 2026', font:'Arial', size:18, color:'6B7590', italics:true })],
        alignment: AlignmentType.CENTER,
        spacing: { before:360 }
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('/home/claude/aicomply_full/AiComply_Architecture_API_Reference.docx', buf);
  console.log('Done');
});

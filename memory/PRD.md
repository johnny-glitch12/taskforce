# Task Force AI - Product Requirements Document

## Original Problem Statement
Build "Task Force AI" — a tactical, enterprise-grade AI agent execution economy platform. Features: Landing Page, The Exchange (marketplace), Task Force Academy, "The Armory" split-pane IDE with "Command Prompt" (LLM chat) and "Node Coding" (visual graph). Full-stack FastAPI/React with Supabase, Stripe, Gemini LLM integration.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Framer Motion, Shadcn UI, ThemeProvider (light/dark)
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler, RestrictedPython
- **Database**: MongoDB (users, waitlist, agents, creators, workflows, n8n_templates, user_workflows, workflow_runs) + Supabase (agent_logs, security_events, published_agents)
- **Payments**: Stripe via emergentintegrations (test mode)
- **LLM**: Gemini 2.5 Flash via Emergent LLM Key
- **Execution Engine**: Native Python — RestrictedPython sandbox + SSRF-protected httpx (NO n8n runtime; n8n abandoned for licensing/security)
- **Design System**: Tactical Cyan (#22d3ee) + Terminal Green (#10b981), JetBrains Mono/Rajdhani/Inter, hard-edge borders, deep matte black

## Global Glossary
- Company: Task Force AI
- IDE: The Armory (was Nova Studio)
- Chat Builder: Command Prompt
- Marketplace: The Exchange
- Education: Task Force Academy
- Template Catalog: Template Armory
- Entity: TASK FORCE AI DEVELOPMENT SERVICES L.L.C.

## All Implemented Features

### Phase 29 (May 27, 2026) — Backlog Cleanup II: Encryption + Pydantic + Pagination + Job Module
- **BYOK encryption at rest** (`lib/byok_crypto.py`): Fernet (AES-128-CBC+HMAC) with SHA-256-derived key from `BYOK_MASTER_KEY` env. Stored with `enc:v1:` prefix for migration. Legacy plaintext rows pass through transparently. Handler decrypts on use.
- **Pydantic models** in `routes/workflow_executor.py`: `BYOKCreate` (Literal service whitelist, `min_length=1 max_length=4096`, `extra: Dict`) and `SaveCanvasRequest` (`min_length=1` + custom non-whitespace validator). Validation errors now return 422 with structured field-level detail.
- **Pagination + projection on runs**: `GET /api/workflows/{id}/runs?skip=X&limit=Y` returns `{runs, total, limit, skip}`. `node_results` stripped (lean). `limit` clamped 1-100. NEW `GET /api/workflows/{id}/runs/{run_id}` returns full run with `node_results`.
- **Async job extraction** (`lib/workflow_jobs.py`): `schedule_async_job()` + `_run_async_job()` + `mark_stale_jobs_failed(db, max_age_seconds=600)`. Backend `@on_event("startup")` now sweeps orphaned `queued`/`running` jobs >10min old → marks `failed` with reason `worker_restart`.
- **Stripe payments extraction** (`routes/stripe_payments.py`): `/payments/checkout`, `/payments/status/{id}`, `/webhook/stripe` moved from server.py (~165 lines). Webhook still triggers subscription activation via `routes.subscriptions.TIERS`.
- **Bulk template ingestion**: 291 templates from `enescingoz/awesome-n8n-templates` (was 19). Round-robin across 20 categories.
- **Scheduler guards**: `scheduler.start()` wrapped with `if not scheduler.running` (eliminates pre-existing duplicate-startup race). `scheduler.shutdown()` mirrored guard.
- **Tests**: iteration_29 → **89/89 backend tests pass** (33+31+25 across 3 test files), 0 production bugs. Auto-update 2 prior tests to match Pydantic 422 contract change.

### Phase 28 (May 27, 2026) — Full Backlog Cleanup + BYOK + Async Runtime
- **P2 — Deep-merge PATCH**: `/api/workflows/{id}/nodes/{node_id}` now recursively merges nested dicts (e.g., patching `headers.Authorization` preserves `headers.X-Other`). 50KB payload cap.
- **P2 — `studio_workflow_id` validation**: `POST /api/workflows/save` requires non-empty studio_workflow_id (prevents duplicate stub inserts on retry).
- **P3 — BYOK action handlers**: `lib/workflow_handlers.py` adds real Slack (incoming webhook), SendGrid (Bearer + from_email), Gmail (OAuth access token) handlers. Action node now dispatches by `data.service`. Stored in new `db.byok_credentials` collection. Endpoints: `GET/POST /api/workflows/credentials`, `DELETE /api/workflows/credentials/{service}`. Service whitelist: `slack|sendgrid|gmail`. api_key masked on GET. New `/credentials` page in frontend (`CredentialsVault.jsx`).
- **P3 — Refactor**: Extracted all node handlers from `routes/workflow_executor.py` → `lib/workflow_handlers.py` (~280 lines). Executor router is now thin and route-ordered (specific paths before catch-all `/workflows/{id}`).
- **P3 — Template direct-execute logging**: `POST /api/workflows/templates/{id}/execute` now persists to `db.workflow_runs` with `source="template"` and returns `run_id`. Also added `GET /api/workflows/{id}/runs` (paginated, owner-scoped).
- **P3 — Async runtime (lightweight)**: `POST /api/workflows/{id}/dispatch` returns `job_id` immediately, fires `asyncio.create_task` background worker, transitions `queued→running→succeeded` in `db.workflow_jobs`. `GET /api/workflows/jobs/{job_id}` polls status. Compute-credit gate enforced on enqueue. Single-worker only (v1 — Celery/Redis for HA later).
- **P3 — server.py split**: 5 auth routes (`/auth/register|login|me|forgot-password|reset-password`) extracted to `routes/auth.py` using lazy-import pattern (~120 lines saved from server.py).
- **Bug fix (caught by testing-agent)**: `_load_byok` used `if not db` against motor's `AsyncIOMotorDatabase`, which raises `NotImplementedError`. Changed to `if db is None or not user_id`. Without this fix every BYOK action node would have crashed with "Database objects do not implement truth value testing".
- **Tests**: iteration_28 → **64/64 backend tests pass (33 regression + 31 new)**. Routes/handlers/auth refactor verified end-to-end.

### Phase 27 (May 27, 2026) — Browse → Fork → Tweak → Run UI Loop
- **Save & Fork hook** (`POST /api/workflows/save`): Idempotent upsert keyed by (user_id, studio_workflow_id). Save button on canvas now auto-forks the loaded template into `user_workflows`, returns the runtime workflow_id used by Execute. Validates 50-node cap and array shape; rejects with 400 on schema violations.
- **Node config editor** (`components/NodeConfigPanel.jsx`): Right-side panel opens when user selects a canvas node. Per-type fields:
  - http_request: URL, Method, Headers (JSON)
  - llm: Prompt, Temperature (engine fixed to platform Gemini 2.5 Flash)
  - condition: Python expression with INPUT context
  - transform: Sandboxed Python code (RESULT = ...)
  - webhook: Outbound URL + Method
  - trigger: Source select (manual/schedule/webhook/email/crm)
  - action/database: v1 stub notice
  - Raw JSON details for any extra field
  - Saves via `PATCH /api/workflows/{id}/nodes/{node_id}` (shallow-merge of data dict)
- **EXECUTE button + TraceViewer**: New EXECUTE button in canvas header (disabled when empty/executing). Wired to `POST /api/workflows/{id}/execute`. Bottom slide-up TraceViewer shows topological step-by-step trace: status icons, node type, label, log, branch flag, duration_ms per node, plus final_output JSON block.
- **End-to-end loop verified**: SAVE → PATCH → EXECUTE actually runs the PATCHed code (testing-agent iteration_27 confirms RESULT=INPUT*3 produces 15 not 10 from prior code).
- **Sandbox security maintained**: RestrictedPython compile + SIGALRM 30s timeout + blocked imports (os/sys/subprocess/socket/etc) + SSRF validation on all outbound HTTP + ephemeral KEYS wipe + 50-node hard cap.
- **Tests**: testing-agent iteration_27 33/33 pass (11 new + 22 regression).

### Phase 26 (May 27, 2026) — Native Workflow Execution Engine (replaces n8n)
- ABANDONED n8n proxy/iframe (licensing + multi-tenancy security risk). Deleted routes/n8n_proxy.py and components/ArmoryEditor.jsx.
- **Translator** (`lib/n8n_translator.py`): Maps 60+ n8n node types to 8 native canonical types (trigger/llm/condition/action/http_request/webhook/database/transform). Heuristic fallbacks for unknown types. Preserves positions, edges, and source params.
- **Ingestion script** (`scripts/ingest_templates.py`): Walks local clone of github.com/enescingoz/awesome-n8n-templates, round-robin samples across 20 categories, upserts into MongoDB n8n_templates with source_hash idempotency. Ingested 19 templates v1.
- **Native executor** (`routes/workflow_executor.py`): Topological-sort DAG walker. Live node handlers: trigger, http_request (SSRF-protected via lib/executor_security), condition (sandboxed eval), transform (RestrictedPython via lib/workflow_sandbox), llm (Gemini 2.5 Flash via Emergent LLM Key — platform-managed, NO BYOK in v1), webhook (inbound stub + outbound POST). Stubs: action, database (v1 pass-through). 50-node hard cap, cycle detection, compute-credit gated at dispatch.
- **API**:
  - GET /api/workflows/engine/status — engine + supported nodes + template count
  - GET /api/workflows/templates — list catalog (category filter, limit)
  - GET /api/workflows/templates/{id} — single template
  - POST /api/workflows/templates/{id}/fork — copy to user_workflows
  - POST /api/workflows/templates/{id}/execute — direct template run (compute-gated)
  - GET/DELETE /api/workflows/{id} — user workflow CRUD with isolation
  - POST /api/workflows/{id}/execute — run DAG (returns success/run_id/node_results/final_output/duration_ms)
- **Frontend** (`components/WorkflowTemplatesGrid.jsx`): Sidebar in The Armory's Workflows tab. Search + category pills + 19 template cards. Click loads translated nodes/edges into the native React Flow canvas (Studio.jsx loadTemplateIntoCanvas). Restored CanvasPane for node mode.
- **Tests**: `tests/test_n8n_translator.py` (5/5 pass), `tests/test_workflow_executor.py` (6/6 pass), testing-agent backend iteration_26 (22/22 pass after KeyError fix).

### Phase 25 — n8n White-Label (DEPRECATED & REMOVED in Phase 26)

### Phase 24 — Compute Credits Kill Switch
- Middleware: check_compute_credits before every agent/workflow execute
- Tier limits: Recruit=100/mo, Cadet=500/mo, Operator=2000/mo, Admin=unlimited
- Returns 200 OK with {allowed:false, error:COMPUTE_LIMIT_REACHED, used, limit, tier, upgrade_url} (k8s strips 403 bodies — do NOT change to 403)
- Monthly rollover via YYYY-MM in compute_usage collection

### Phase 23 — Stripe Subscriptions + Referrals
- POST /api/subscriptions/checkout (Cadet $19 / Operator $99)
- GET /api/subscriptions/status, POST cancel, POST activate, webhook auto-activate
- Referral codes TF-XXXXXX, $10 credit on signup, applied at checkout

### Phase 22 — Overwatch Admin Dashboard
- /overwatch (admin-only): KPIs, Revenue Split chart, Top Categories donut, Live Execution Feed, KILL AGENT override (NOTE: KPI/feed data MOCKED)

### Phase 20-21 — Tactical Rebrand
- Full A-Z: Nova AI → Task Force AI. Studio → The Armory. Marketplace → The Exchange.
- Tactical cyan/green design tokens, framer-motion landing, hero video
- Light/dark theme toggle with system auto-detect
- 4-tier pricing matrix (Recruit/Cadet/Operator/Command)

### Authentication & Core
- JWT auth (login/register/forgot/reset)
- The Armory IDE: draggable node canvas, JSON manifest output, Command Prompt → Gemini, Supabase Realtime terminal, Compliance Linter, workflow CRUD with auto-save
- Publish Agent Manifests to Supabase + Creator Dashboard + Version Control
- Security: Semantic Firewall, Rate Limiting, SSRF Protection, /security audit dashboard
- CSDROP Private Portal with 2FA + QR sync

## Key Routes
- / — Home, /pricing, /exchange, /academy, /armory, /overwatch, /security, /dashboard, /creator
- API: /api/workflows/* (NEW), /api/run-agent, /api/subscriptions/*, /api/referrals/*, /api/published-agents/*, /api/webhook/stripe

## Credentials
- Admin: admin@nova.ai / admin123 (unlimited compute)
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Free Test: freeuser@test.com / test123 (recruit, 100/100 used)

## Key DB Schema
- users (Mongo): email, password_hash, tier (recruit/cadet/operator), compute_used
- subscriptions (Mongo): Stripe IDs + statuses
- n8n_templates (Mongo): source_hash (unique), name, category, description, nodes[], edges[], node_count, complexity, trust_score
- user_workflows (Mongo): id, user_id, name, nodes, edges, source_template
- workflow_runs (Mongo): id, user_id, workflow_id, source, success, duration_ms, node_results[]
- workflow_jobs (Mongo): id, user_id, workflow_id, status (queued/running/succeeded/failed), result, run_id, created_at, finished_at
- byok_credentials (Mongo): user_id, service (slack/sendgrid/gmail), api_key (plaintext v1), extra, created_at, updated_at
- compute_usage (Mongo): user_id + period (YYYY-MM) + count

## Prioritized Backlog
- **P2**: KMS-managed BYOK key (currently env-bound; rotate to AWS KMS / GCP KMS / Vault)
- **P3**: Consolidate duplicate `@app.on_event("startup")` functions in server.py
- **P3**: CSDROP routes extraction (28 routes) — **deprioritized per user**
- **P3**: Pydantic models for `PATCH /nodes/{node_id}` (still uses request.json()→400 instead of 422)
- **P3**: Celery + Redis HA async runtime (replaces in-process asyncio worker)
- **P3**: Real-time websocket feed for Overwatch live execution table
- **P3**: Token-refresh OAuth flow for Gmail BYOK (currently manual access-token refresh)

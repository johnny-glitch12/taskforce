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

### Phase 32 (Feb, 2026) — Lego Edges + AI Bot Builder (Gemini 2.5 Pro)
**P0 — User-reported polish (5 fixes):**
- **Lego-style edge routing** (`Studio.jsx` ~line 393): Replaced cubic-bezier center→center with orthogonal right-port → vertical-elbow → left-port path. Edges now wrap around blocks instead of slicing through them. Active edges glow cyan (#22d3ee) with arrowhead.
- **Markdown asterisk strip**: `sanitize()` helper in ChatPane strips `**bold**` / `__under__` / backticks from assistant messages. `cleanLabel()` mirrors the same on node `label` + `sub` fields. No more visual `**` clutter on canvas or in chat.
- **DB pollution purge**: Wiped 72 `TEST_*` workflows + 2 orphan runs from MongoDB (79→7 legitimate workflows). Added permanent filter on `GET /api/workflows` excluding `name~/^TEST_/i` so future test fixtures never leak into the user-facing list.
- **Firewall tuning** (`lib/firewall.py`): Rewrote AUDIT_SYSTEM_PROMPT to explicitly whitelist build-bot intents ("build a bot that posts to my Instagram", "build a calculator") as SAFE. UNSAFE now strictly requires prompt-injection patterns, secrets exfil, malware generation. Verified: legitimate Instagram bot prompt → SAFE; `ignore previous instructions` → UNSAFE.
- **Import-from-Exchange rewire** (`MyWorkflowsGrid.jsx`): Modal now pulls from `/api/exchange/listings` (real community-published bots) instead of the raw 291-template n8n catalog. Click → `POST /api/exchange/listings/{id}/fork` clones ONLY that one listing into `user_workflows` with `forked_from_listing` + `forked_from_creator` lineage for 80/20 revenue attribution. New backend route in `routes/exchange.py`.

**P1 — Major feature: AI Bot Builder (Gemini 2.5 Pro)**
- **NEW `POST /api/armory/build-bot`** (`routes/armory_builder.py`): Natural-language prompt → Gemini 2.5 Pro → structured JSON `{name, description, files:[{path, content, language}], manifest:{nodes, edges}}`. Defensive normalizer strips markdown, blocks `..`/absolute paths, caps files@20 / nodes@50 / content@200KB. 502 if LLM returns empty package.
- **GitHub-style project lifecycle** — all stateless, MongoDB-only (`bot_projects` collection):
  - `GET /api/armory/bot-projects` — list user's projects (lean, no commit_history)
  - `GET /api/armory/bot-projects/{id}` — full project with commit_history
  - `POST /api/armory/bot-projects/{id}/commit` — version+=1, push commit_history entry
  - `PATCH /api/armory/bot-projects/{id}/files` — in-place file content update
  - `POST /api/armory/bot-projects/{id}/fork` — intentionally public (GitHub model); clones with `forked_from` + `forked_from_creator` for revenue lineage
  - `DELETE /api/armory/bot-projects/{id}`
- **Frontend `BotProjectPanel.jsx`** (`@monaco-editor/react` added): Slides in from canvas right when a bot project is active. File tree (left, color-coded by extension) + Monaco code editor with vs-dark theme + Save / COMMIT (with version bump) / FORK / History buttons. Dirty-state indicator (●) per file.
- **Chat trigger** (`Studio.jsx` `handleChatSend`): Regex `/^(build|create|make|generate|design)\s+(me\s+)?(a|an|the)?/i` short-circuits the chatbot and routes straight to `/api/armory/build-bot`. Auto-renders generated nodes on canvas + flips into node mode + opens BotProjectPanel.
- **Tests**: iter32 → **163/163 backend tests pass** (18 new + 145 regression). Zero production bugs. Real Gemini 2.5 Pro call cached via module-scoped fixture to bound cost (~$0.003/run).

### Phase 30 (May 27, 2026) — UX Cleanup + Backlog Closure
- **The Armory restructured**: Removed the templates-grid sidebar that was polluting the canvas. New `MyWorkflowsGrid.jsx` shows the user's OWN runtime workflows in the left rail. Templates moved to an "IMPORT FROM EXCHANGE" modal triggered by an explicit button. Vibe/Workflows toggle remains prominent center-top. Mode-toggle uses `data-testid="vibe-mode-btn"` and `node-mode-btn`.
- **Edge routing fix**: Connections now run right-edge → left-edge with cubic-bezier ports. Lines never pierce node bodies (replaces center-to-center routing). Subtle drop-shadow glow on active edges.
- **Marketplace emptied**: `db.agents` + `db.creators` deleted (was 6 mock agents, 5 mock creators). Auto-seed gated with `if False` so restarts don't repopulate. Marketplace shows "No agents found. Try a different search or category." — ready for real listings.
- **PATCH 422 contract**: `routes/workflow_executor.py` adds `NodePatchRequest` Pydantic model with `data: Dict[str, Any]` validator that rejects non-dict + 50KB cap. All PATCH validation errors now return 422 (not 400).
- **BYOK KMS abstraction** (`lib/byok_crypto.py`): Provider-pluggable encryption via `BYOK_KMS_PROVIDER` env var. v1 implements `local` (Fernet); stubs for `aws|gcp|vault` raise with clear migration guidance. New `GET /api/workflows/credentials/_provider` (admin-only) exposes diagnostics.
- **Gmail OAuth refresh-token flow** (`lib/gmail_oauth.py`): `POST /credentials/gmail/exchange` (code + redirect_uri → stores access+refresh tokens encrypted) and `POST /credentials/gmail/refresh`. Action handler auto-refreshes when `expires_at` is in the past. Returns 503 (not 500) when `GOOGLE_CLIENT_ID/SECRET` env vars are unset.
- **Server.py consolidation**: Removed the pre-existing duplicate `@app.on_event("startup")` + `@app.on_event("shutdown")` blocks. Single startup + single shutdown. `scheduler.start()` + `scheduler.shutdown()` both guarded with `if (not) scheduler.running`.
- **Auth hardening** (bug found by testing-agent iteration_30): `UserCreate`, `UserLogin`, `ForgotPasswordRequest`, `ResetPasswordRequest` now use `EmailStr` + `Field(min_length=8, max_length=128)` for passwords. Previously `/api/auth/register` accepted empty email + password and returned a valid JWT (HIGH severity). routes/auth.py re-defined as standalone Pydantic models so FastAPI auto-422s before reaching the handler.
- **Stripe**: User has sandbox keys but screenshots truncated them. Kept existing `STRIPE_API_KEY=sk_test_emergent`. Swap in `backend/.env` whenever real keys are available; no code change needed.
- **Skipped per infra**: Celery + Redis (no Redis container available — in-process asyncio worker stays for v1). Real-time websocket Overwatch feed (deprioritized).
- **Tests**: iteration_30 → **116/116 backend tests pass** (33+31+25+27), 0 production bugs after auth hardening.

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
- exchange_listings (Mongo): id, user_id, creator_email, name, description, category, tags, rent_price, buy_price, video_url, photo_urls, nodes_snapshot, edges_snapshot, status (draft/published/delisted), deploy_count, trust_score, created_at, updated_at
- bot_projects (Mongo): id, user_id, creator_email, name, description, language, prompt, files[{path,content,language}], nodes, edges, forked_from, forked_from_creator, commit_history[{commit_id,message,author,files,nodes,edges,created_at}], version, created_at, updated_at
- compute_usage (Mongo): user_id + period (YYYY-MM) + count

## Prioritized Backlog
- **P2**: Real KMS integration (`aws|gcp|vault`) for `BYOK_KMS_PROVIDER` (stubs in place)
- **P2**: Real-time Overwatch execution feed via WebSocket (currently polled)
- **P3**: Celery + Redis HA async runtime (needs Redis container; in-process asyncio worker stays for v1)
- **P3**: CSDROP routes extraction — **deprioritized per user**
- **P3**: Split routes/workflow_executor.py (~700 lines) — move Gmail OAuth + provider diagnostics into routes/gmail_oauth.py
- **P3**: Rate-limit auth endpoints (brute-force protection)
- **P3**: Provision real Stripe sandbox keys (user has them, just need full strings)

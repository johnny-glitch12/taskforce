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

### Phase 59 (Feb 2026) — Viral Share + Resend Emails + Security Hardening (Prompts 13, 17 + Share)

**🟢 Share Button — viral loop for hosted mini-apps**
- New `POST /api/apps/{slug}/share {is_public: bool}` toggles a project's `is_public` flag.
- `GET /api/apps/{slug}/render` loads anonymously when public (HTML shell + Babel + JSX renders without auth).
- `POST /api/apps/{slug}/run`:
  - Private app + non-owner → **403** "Not your app."
  - Public app + non-owner JWT → **200** runs in sandbox, debits the **OWNER's wallet** (creator absorbs viral cost), `app_runs.caller_id` captures the visitor for analytics.
  - Public app + anonymous visitor → **401** "Sign in to run this app." → drives viral signups.
- **AppViewer Share panel** (`data-testid='app-viewer-share-toggle'`): Public/Private toggle, readonly URL + Copy button, readonly `<iframe>` embed snippet + Copy button, Twitter + LinkedIn share-intent links (only when public). Iframe sandbox tightened to `allow-scripts allow-same-origin` (no `allow-forms`, no popups, no top-navigation).

**🟢 Prompt 13 — Resend Transactional Emails**
- New `backend/utils/email_service.py` — 6 templates, all dark-themed inline-CSS matching the TaskForce brand:
  - `send_welcome_email`        — fired on `/api/auth/register`
  - `send_waitlist_email`       — fired on `/api/waitlist`
  - `send_password_reset_email` — fired on `/api/auth/forgot-password`; `reset_token` is now OMITTED from the response body when `EMAIL_ENABLED=true` (no in-band leak).
  - `send_submission_received_email` — fired in `/api/bounties/{id}/submit` to the poster.
  - `send_bounty_awarded_email`     — fired in `/api/bounties/{id}/award` to the winner.
  - `send_tier_upgrade_email`        — fired in the Stripe `checkout.session.completed` subscription branch.
- All sends are **fire-and-forget** via `asyncio.create_task` — the user-facing action ALWAYS returns 200 even when Resend is down.
- Synchronous Resend SDK wrapped in `loop.run_in_executor` so it never blocks FastAPI's event loop.
- Domain `taskforce.run` needs SPF/DKIM DNS verification in the Resend dashboard before mails leave the spam folder; until then, every send returns `{success: False, error: '...domain not verified...'}` and we log a warning (auth flows still succeed).
- `RESEND_API_KEY`, `EMAIL_FROM`, `PLATFORM_URL` added to `backend/.env`. `resend==2.30.1` and `bleach==6.3.0` added to requirements.

**🟢 Prompt 17 — Security Audit + Hardening Pass**
- New `backend/lib/security_middleware.py` — `SecurityHeadersMiddleware` stamps every response with: `X-Content-Type-Options=nosniff`, `X-Frame-Options=DENY` (global) or `SAMEORIGIN` (iframe render only), `Strict-Transport-Security`, `Permissions-Policy=camera=(), microphone=(), geolocation=(), payment=()`, `Referrer-Policy=strict-origin-when-cross-origin`, `X-XSS-Protection=1; mode=block`.
- **CSP on /api/apps/*/render only** — allows `'unsafe-inline' 'unsafe-eval'` for script-src (Babel-standalone), restricts to `unpkg.com` + `cdn.tailwindcss.com`, `connect-src 'self'` (mini-app can ONLY call back into Task Force API).
- **Global exception handler** — catches every unhandled `Exception` and returns `{error: 'INTERNAL_ERROR', message: 'Something went wrong. Please try again.'}` — NEVER leaks stack traces. Separate handler for `bson.errors.InvalidId` → clean 400.
- **Rate limits** added: `/api/vibe/chat` 30/min, `/api/vibe/generate` 5/min, `/api/apps/{id}/run` 60/min (in addition to existing auth-route limits).
- New `backend/lib/sanitize.py` — `sanitize_text`, `sanitize_html`, `sanitize_url`, `sanitize_user_response` utilities (bleach-backed when available, regex fallback otherwise). Available for future input-validation hardening.
- **Audit findings (no fixes needed)** — codebase already had strong baselines from prior phases:
  - ✅ Zero hardcoded secrets in source (all in `.env`, `.gitignore`'d).
  - ✅ `JWT_SECRET` is 43 chars, bcrypt for passwords, role hardcoded to `"user"` on register.
  - ✅ Rate-limited auth endpoints (login=10/60s, register=5/600s, forgot=3/600s, IP anti-abuse cap).
  - ✅ Every user-scoped query filters by `user_id` — IDOR-clean (sampled 20+ routes).
  - ✅ Stripe webhook signature verified by `emergentintegrations.StripeCheckout.handle_webhook()`.
  - ✅ Credit-debit guards (`amount > 0` enforced in `lib/credit_wallet.py`).
  - ✅ Zero `dangerouslySetInnerHTML` in frontend (React auto-escapes everywhere).
  - ✅ BYOK keys encrypted at rest via Fernet+KMS, never returned to frontend.
  - ✅ Pydantic validation on all request bodies.
  - ✅ `UserResponse` Pydantic model returned (not raw user dict) → no password_hash/IP leak.

**Verified (iter59)**:
- **18/20 backend pytest pass** (`/app/backend/tests/test_iter59_share_security_emails.py`) — the 2 skips were anti-abuse rate limit on the CI runner's IP, not product bugs.
- **Frontend Playwright pass** — all 8 share-panel testids present, sandbox locked, Toast confirmation observed, Twitter+LinkedIn share links surfaced only when public.
- **Main-agent live tests**: anon-on-public 401, public+non-owner 200 (owner debited), private+non-owner 403, security headers verified via `curl -I`, CSP on `/render` only, email module fires welcome+waitlist+forgot+ all returning `domain not verified` (expected, DNS pending).
- **Post-test polish**: cleaned the `reset_token: null` field from forgot-password prod response, hardened anon-public-app to 401 (signup wall — viral loop).


### Phase 58 (Feb 2026) — Emergent-Quality 5-Stage Code Gen Pipeline + Hosted Agent Mini-Apps (Prompts 15 & 16)

Two massive specs merged into one tight MVP slice — see git for full file map.

**Prompt 15 — 5-Stage Multi-Agent Pipeline**
- New `backend/prompts/code_gen_prompts.py` — strict JSON prompts for **Architect → Planner → Builder → Reviewer → Polisher → UI Builder** (6 stages, UI Builder only fires when the Architect flags `has_ui=true`).
- New `backend/lib/code_gen_pipeline.py` (~440 lines) — `run_build_pipeline()` orchestrator. **Cheap stages** (Architect/Planner/Reviewer/Polisher) hardcoded to `gemini-2.5-flash` for ~80% cheaper non-builder calls. **Builder + UI Builder** use the user's chosen model. Each stage **debits credits POST-call** via `lib/smart_credits.debit_actual_usage` so a failed LLM call doesn't burn the user's wallet. Progress + parsed outputs persisted to `vibe_sessions.build_progress[]` + `vibe_sessions.build_context.{stage}`.
- **AST validation** — `validate_all_files()` runs `ast.parse` + import-resolution against `requirements.txt` + Python stdlib on every `.py` file. **When AST is clean, the Reviewer stage is SKIPPED entirely** (saves a credit + ~5–15s latency).
- **PipelinePaused exception** — when `check_can_afford` returns insolvent mid-pipeline, the orchestrator catches it and writes `build_status='paused'`, `build_paused_stage`, `build_paused_reason` to the session. The frontend's chat thread surfaces a yellow "Out of credits at X" banner with **Top Up Credits** (→ `/credits`) + **Resume Build** buttons.
- **Resume flow** — `POST /api/vibe/resume-build/{session_id}` (404 if unknown, 409 if not paused, 402 if still broke) re-dispatches the same Celery task with `resume=True`. Completed stages are skipped via `build_context` cache → user only pays for the remaining ones.
- **Celery integration** — new `tfai.vibe_build` Celery task in `lib/celery_app.py` makes the entire pipeline non-blocking. `POST /api/vibe/generate` now returns `{status: 'queued', session_id, task_id, poll_url}` in <3s. New `GET /api/vibe/build-status/{session_id}` is the polling endpoint — returns `progress[]` (per-stage status + credits_used + duration_ms), plus `paused` info when applicable, plus the full `project` when complete. Inline fallback when `CELERY_BROKER_URL` is unset (dev). **Legacy** `POST /api/vibe/generate-legacy` preserved for callers that still want the single-call flow.
- **Smart Model Routing**: cheap stages always Flash (saves margin); Builder uses user choice. Net cost for a complex flagship build is roughly `(4 × flash) + (1 × user-model) + (optional 1 × user-model ui-builder)` ≈ the user's `build_cost` plus ~2-3cr overhead. Transparent — debit happens per stage, visible in the chat progress card.

**Prompt 16 — Hosted Agent Mini-Apps (Single-File React via Babel CDN)**
- New `backend/routes/apps.py` — all endpoints prefixed `/api`:
  - `GET /my-apps` — listing of the user's UI-enabled projects, each with `id`, `slug`, `manifest`, `run_count`.
  - `GET /apps/{slug}` (auth, owner-only) — full app metadata including `frontend.app_jsx`.
  - `GET /apps/{slug}/render` — HTML iframe shell (NO auth — token comes via `?token=` query param). Embeds Tailwind CDN, React 18 UMD, Babel-standalone, the AI-generated `App.jsx`, and a `window.tfApi.run(input)` bridge. Config is **JSON-encoded into a `<script id="tf-cfg" type="application/json">`** tag (NOT string-replaced into the JS body) so any sentinel-like sequences in the AI-generated JSX can't collide with the shell.
  - `POST /apps/{id}/run` — exec'es the agent's `main.py run(input)` function in a curated SAFE_BUILTINS sandbox (includes `__build_class__` so `class` defs work). Owner-only. Debits 1cr per run (smart_credits `agent_run` action). Logs to new `app_runs` collection.
  - `GET /apps/{id}/runs` — last 25 runs for the owner.
  - `POST /apps/{id}/redesign` (body `{prompt}`) — re-runs the UI Builder stage with a "modify this current App.jsx" prompt. Updates `bot_projects.frontend.{app_jsx, manifest}`. Debits the UI Builder credits.
- **`bot_projects` schema** extended: new `frontend: {app_jsx, manifest}`, `has_ui: bool`, `app_slug: string` fields. New `app_runs` collection (`{id, app_id, user_id, input, output, success, error, duration_ms, credits_used, created_at}`).
- **Frontend** new pages: `pages/MyApps.jsx` (responsive grid w/ launch cards) + `pages/AppViewer.jsx` (header w/ My Apps back / app name / slug / Preview|Runs tabs / Refresh / Redesign button + textarea row, sandboxed iframe pointing to `/api/apps/{slug}/render?token=...`, runs history table on the Runs tab). New routes `/my-apps` + `/apps/:slug` (both `ProtectedRoute`). Navbar dropdown gets a new accent **"My Apps"** entry with `Layers` icon.
- **Frontend Armory build flow** now polls `/api/vibe/build-status/{sid}` every 1.5s. A new `build_progress` message type in `components/armory/ChatMessage.jsx` renders a strip of `stage-chip-{stage}` chips (Architect / Planner / Builder / Reviewer / Polisher / UI Builder) with per-stage status, credits, and duration. On success the placeholder is replaced with the legacy `CodeGenerationCard` plus an **"Open Mini App"** cyan button when the build has UI. On pause, an amber banner with **Top Up Credits** + **Resume Build** appears.
- **EconomicsDashboard runtime chip** — fetches `/api/admin/runtime/status` (owner-only) and renders `RUNTIME: CELERY · Redis Xms · KMS: local` chip (`data-testid='runtime-health-chip'`) right under the page description.

**Verified (iter58)**:
- **24/24 backend pytest pass** (`/app/backend/tests/test_iter58_vibe_pipeline_apps.py`) — pipeline progression, /my-apps, /apps/{slug}, /apps/{slug}/render, /apps/{id}/run (sandboxed Text Capitalizer end-to-end: input `"hello world"` → output `{capitalized_text: "HELLO WORLD"}`), /apps/{id}/runs, /apps/{id}/redesign, /vibe/resume-build gates, /admin/runtime/status owner gate. Zero critical, zero minor issues. Regressions on `/vibe/chat`, `/vibe/sessions`, `/vibe/models`, `/vibe/recommend-model` all pass.
- **Frontend live screenshot-verified** by main agent: `/my-apps` grid + AI-built Text Capitalizer app rendering inside the iframe with full Tailwind styling + EconomicsDashboard runtime chip visible.
- **Hardening fix** applied post-test based on code-review note: replaced naive `__TOKEN__` string substitution with a JSON-encoded `<script id="tf-cfg">` tag (defence against AI-generated JSX sequences accidentally matching our shell sentinels). Verified iframe + run still work post-fix.


### Phase 57 (Feb 2026) — Backlog Sweep: Margin-aware Auto-Pick · Real-token defensive hook · Celery+Redis HA · KMS adapters · Test-path fix

Cleared every item from the Phase 56 backlog in one pass.

- **(a) Iter56 test path fix** — `/api/vault/keys` → `/api/workflows/credentials` (body now `{service, api_key}`); also checks `byok_credentials` collection for `enc:` prefix to verify ciphertext-at-rest. Probe call hits `/workflows/credentials/openai/test`.
- **(b) Real-provider token defensive hook** — `credit_calculator.extract_real_usage(resp)` probes 3 known shapes (OpenAI `prompt_tokens/completion_tokens`, Anthropic `input_tokens/output_tokens`, Gemini `prompt_token_count/candidates_token_count`) on the LlmChat response. When found → returns provider truth; when not → falls back to tiktoken. `token_source: 'provider'|'estimate'` now lands in every dynamic-billed ledger row so we can audit estimator drift once emergentintegrations exposes usage.
- **(c) Margin-aware Auto-Pick** — `/vibe/recommend-model` post-processes the LLM pick via `_apply_margin_bias()`. When `complexity=='simple'` AND the LLM picked a flagship model (gemini-2.5-pro / gpt-4o / claude-sonnet), it auto-downshifts to the cheap sibling on the same provider (flash / 4o-mini / haiku). The reason string is annotated with `(auto-downshift: ...)` so users see why. No-op on medium/complex tasks. Verified: simple "capitalize a string" → flash kept; complex multi-tenant CRM → claude-sonnet kept.
- **(d) Celery + Redis HA async runtime** — `lib/celery_app.py` (160 lines). Three new supervisor services in `/etc/supervisor/conf.d/supervisord_celery.conf` (redis-server, celery-worker --concurrency=2, celery-beat). 4 periodic tasks registered: `tfai.hosting_expire` (crontab 0min), `tfai.bounty_expire` (5min), `tfai.scheduled_runs_tick` (300s interval), `tfai.supernova_eval` (crontab 00:30 UTC). Per-task fresh motor client via `_task_db()` to avoid "event loop is closed" cross-task bleed. `server.py` startup hook auto-detects `CELERY_BROKER_URL` and skips APScheduler `add_job` calls (jobs delegated to celery beat); APScheduler still starts as a no-op fallback. New `GET /api/admin/runtime/status` (owner-only) reports active runtime, broker URL, live Redis ping latency, KMS provider. **Verified live**: 3 manual `.delay()` dispatches return clean `{flipped:0, processed:0, dispatched:0}` results; backend reports `runtime.active='celery'` with 0ms broker latency.
- **(e) KMS adapter rewrite** — `lib/byok_crypto.py` (now 215 lines, full concrete implementations replacing the prior stubs):
  - **`local`** (default): Fernet derived from `BYOK_MASTER_KEY`. Format `enc:v1:<fernet>`.
  - **`aws`**: boto3 KMS `Encrypt`/`Decrypt` via `AWS_KMS_KEY_ID` + `AWS_REGION`. Format `enc:aws-v1:<b64-blob>`.
  - **`gcp`**: google-cloud-kms via `GCP_PROJECT_ID` + `GCP_KMS_LOCATION` + `GCP_KMS_KEYRING` + `GCP_KMS_KEY`. Format `enc:gcp-v1:<b64>`.
  - **`vault`**: hvac Transit engine via `VAULT_ADDR` + `VAULT_TOKEN` + `VAULT_TRANSIT_KEY`. Format `enc:vault-v1:<vault-cipher>`.
  - **Rotation-safe** by design — `decrypt_key()` dispatches on the ciphertext version prefix, NOT the active provider env var. So a database mid-rotation (some rows on local, some on aws) decrypts seamlessly. `provider_info()` reports `active_provider` + `supported` + `rotation_safe: true`.
  - Lazy SDK imports — boto3/google-cloud-kms/hvac are only imported when their provider is selected, keeping the local-dev install zero-dep.

**Verified (manual smoke)**: All 5 features tested live. Lint clean (ruff + eslint). Backend restarted twice, supervisor reports `redis RUNNING · celery-worker RUNNING · celery-beat RUNNING`. Existing iter57 dynamic-billing regression still passes (tasks unchanged, only metadata field added).


### Phase 56 (Feb 2026) — Smart Dynamic Credit System + Economics Dashboard + Pricing Overhaul (Prompt 14)

**Switch from flat-rate pre-pay credits → usage-based post-pay billing on real LLM token counts.**

- **`lib/credit_calculator.py`** — Token-based pricing engine. `MODEL_COSTS` per-million-token map (Gemini Flash $0.30in/$2.50out, Pro $1/$10, GPT-4o $2.50/$10, 4o-Mini $0.15/$0.60, Claude Sonnet $3/$15, Haiku $1/$5). `PLATFORM_MARGIN=2.5×` (60% gross margin). `CREDIT_VALUE_USD=$0.01`. `MIN_CREDITS` floor per action (vibe_chat=1, build_bot=2, etc.). `AVERAGE_TOKENS` per action used by `estimate_range(model, action)` for pricing tooltips. tiktoken (cl100k_base) cross-provider proxy via `estimate_tokens()` + `estimate_tokens_for_call()`.
- **`lib/smart_credits.py`** — Two-step billing flow: `check_can_afford(db, user, model, action)` pre-flight estimate; `debit_actual_usage(db, user, model, action, input_tokens, output_tokens, key_source, ref)` post-call atomic debit with rich ledger metadata patching (find_one_and_update with `sort=[(created_at,-1)]` to patch the just-inserted row). **BYOK discount lever**: when `key_source=='byok'`, charges only `MIN_CREDITS[action]` and records `api_cost_usd=0` so economics dashboard shows we paid nothing.
- **`routes/vibe_coding.py`** — `_call_platform_llm()` signature changed from `→ str` to `→ {text, input_tokens, output_tokens, model}`. All 3 routes (`/vibe/chat`, `/vibe/generate`, `/vibe/recommend-model`) swapped flat `wallet_debit` → `smart_credits.debit_actual_usage`. Response payloads now include `input_tokens`, `output_tokens`, `cost_breakdown:{api_cost_usd, revenue_usd, model, key_source}`. Session message rows persist tokens too for replay UI.
- **`routes/armory_builder.py`** — `_generate_with_gemini()` now returns `{bot, input_tokens, output_tokens, model}`. `build_bot` debits dynamically; response includes `credits_used, cost_breakdown`.
- **NEW `routes/credits_economics.py`**:
  - **`POST /api/credits/estimate`** (auth) — `{}` → full pricing matrix (6 models × 4 actions = 24 rows with low/typical/high/byok_cost/api_cost/revenue) + `model_costs` + `min_credits` + `platform_margin`. `{model, action}` → single row. Unknown model/action → 400.
  - **`GET /api/admin/economics?days=N`** (owner-only) — `{window: {total_revenue_usd, total_api_cost_usd, gross_margin_usd, gross_margin_pct, calls, tokens, active_users}, lifetime:{}, per_model:[], by_key_source:{platform:{}, byok:{}}, top_spenders:[20], daily:[]}`. Aggregates via 6 mongo pipelines over `credit_transactions.metadata.*` fields. Dev admin (role=admin, is_owner=false) → 403 `OWNER_ONLY`.
- **`server.py`** — `UserResponse.is_owner: bool` added; mounted `credits_economics_router`.
- **`routes/auth.py`** — `/auth/login` + `/auth/me` responses now carry `is_owner`.
- **`pages/Pricing.jsx`** — Overhauled: tier grid (kept) + **ModelCostMatrix** (per-model × per-action typical-with-range cells + purple BYOK column, pulled from `/credits/estimate`) + **top-up packs strip** (4 packs $5/$19/$79/$299) + **BYOK panel** (purple gradient card, "60–95% savings", deep-link to `/credentials`) + trust bar.
- **NEW `pages/EconomicsDashboard.jsx`** @ `/admin/economics` (owner-only via `OwnerGate`) — 4 stat cards (Revenue/Cost/Margin/Users), lifetime strip, per-model breakdown table with revenue-share progress bars, platform-vs-BYOK split panel, top-20 spenders, daily revenue-vs-cost bars. 7d/30d/90d/1y window toggle.
- **`App.js`** — `isOwner` context value + `OwnerGate` component + `/admin/economics` route.
- **`components/Navbar.jsx`** — "Economics" menu entry visible only to owners.
- **`components/armory/ChatMessage.jsx`** — `CreditMeta` extended: now optionally renders `tokens (in→out)` and a purple **BYOK** badge when `key_source==='byok'`. Backward-compatible: missing fields = legacy compact display.

**Verified (iter57)**: **16/17 backend tests PASS · 100% frontend PASS**. 1 backend test SKIP (BYOK runtime debit — fake `sk-test-xxx` key 502s at OpenAI before reaching debit; key-resolution path verified via AuthenticationError trace). Race-safe atomic debit confirmed via 5 concurrent /vibe/chat calls. Ledger metadata writes verified. Owner gate verified: admin@nova.ai (200) vs benjamin@taskforce.ai (403 OWNER_ONLY).


### Phase 55 (Feb 2026) — P3 Carryover Sweep (Armory 404 toast · Demo listings · Reviews moderation · Schedule circuit breaker · Earnings CSV streaming)

- **Armory project-404 toast** (`pages/Armory.jsx` `loadProject`) — when a session points to a deleted/foreign project the load no longer silently fails. Now surfaces "Build artifact no longer exists. Start a new conversation to rebuild." for 404 and "Couldn't load build (XX)" for other failures, clears the preview state instead of leaving a stale right panel.
- **Demo Exchange listings seed** — new `routes/admin_seeds.py` with `POST /api/admin/seed-demo-listings` (admin-only, idempotent via `_seed_id`) inserting two production-quality demo agents:
  1. **Triage-3 · Email Support Pilot** — 4-node email triage agent ($29/mo · $199 own · trust 92 · 47 deploys)
  2. **FastQual · Inbound Lead Qualifier** — 5-node Typeform→GPT→HubSpot→Slack lead scorer ($49/mo · $349 own · trust 89 · 23 deploys)
  Each carries full description (markdown), tags, avatar color, snapshot of nodes+edges so the `/listing/:id` Flow tab is non-empty. Companion `DELETE /api/admin/seed-demo-listings` for clean teardown. Companion **bug-fix** in `pages/Marketplace.jsx` — listings were mapping `name → shortTitle` only, but `AgentCard` reads `agent.title` → titles were silently blank. Now mapped to both `title` AND `shortTitle`.
- **Reviews moderation (shadow-hide)** — `routes/reviews.py`:
  - `POST /api/exchange/reviews/{id}/hide` (admin-only) toggles `hidden: bool`, stamps `hidden_by/at/reason`. Recomputes the listing's `aggregates` so hidden reviews stop counting toward star average + count + histogram.
  - `GET /api/exchange/listings/{id}/reviews/all` (admin-only) moderation view surfacing ALL reviews including hidden.
  - Public `GET /api/exchange/listings/{id}/reviews` and `_refresh_aggregates` now filter `hidden: {$ne: true}` everywhere.
  - Hidden reviews remain in the DB (audit trail), so the author still sees their review in `my-review` (with the hidden flag).
- **Schedule circuit breaker** — `routes/schedules.py` `tick_scheduled_runs`:
  - New `schedule.consecutive_failures` counter — increments on `success=False` or exception, resets to 0 on success.
  - `CIRCUIT_BREAKER_THRESHOLD = 3` — once tripped, the schedule auto-disables and records `last_disabled_reason="circuit_breaker"`.
  - Distinct from the existing `limit_reached` reason so the FE can show a different toast/copy when applicable.
- **Earnings CSV streaming** — `routes/creator_earnings.py`:
  - Switched `/api/creator/earnings/export.csv` from a buffered `Response` (capped at 1000 rows) to `StreamingResponse` with an async generator iterating two motor cursors (`creator_revenue_ledger` + `bounties` for awarded wins) and yielding CSV rows on the fly. No row cap.
  - Added `Cache-Control: no-store` + `X-Accel-Buffering: no` headers so proxies don't buffer the response.
  - Order is "grouped by source (Stripe payouts then bounty wins), newest-first within each group" — a small UX trade-off vs. a cross-source merge, but makes the CSV more useful for tax/bookkeeping.

**Verified manually** (curl + screenshots):
- Seed inserts 2 demo listings; non-admin → 403; second invocation → `inserted:0, skipped:2`.
- `/marketplace` renders cards with names "Triage-3 · Email Support Pilot" + "FastQual · Inbound Lead Qualifier" — confirmed via screenshot.
- `/listing/{id}` shows full description, pricing, and Reviews panel with histogram.
- CSV export GET returns `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename=earnings_…csv`, `Cache-Control: no-store`.
- All 4 routes/*.py modules pass ruff with zero warnings.


### Phase 54 (Feb 2026) — The Armory Redesign (Prompt 11)

Complete UI redesign of `/armory` — replaced legacy 1371-line `Studio.jsx` debug-style node editor with a premium 3-panel chat-based builder (Cursor/Linear quality). Old Studio kept reachable via `/armory/workflows/:projectId` for power users. See git diff iter50 for the full 9-component breakdown (SessionSidebar, ModelPicker, ChatPanel, ChatMessage, CodeGenerationCard, EmptyState, AgentPreview, AgentActionBar, Armory.jsx orchestrator + scoped Armory.css design tokens). New backend endpoint `POST /api/armory/bot-projects/{id}/test-run` reuses `execute_workflow_dag`. Custom inline-SVG flow preview (no new deps). Footer hidden on `/armory*`. ModelPicker correctly splits Platform vs Your Keys via `byok_service`. **Verified iter50: 8/8 new backend + 100% frontend Playwright PASS.**




Complete UI redesign of `/armory` — replaced legacy 1371-line `Studio.jsx` debug-style node editor with a premium 3-panel chat-based builder (Cursor/Linear quality). Old Studio kept reachable via `/armory/workflows/:projectId` for power users.

**New layout** (`pages/Armory.jsx` orchestrator + scoped CSS tokens in `pages/Armory.css`):
- **SessionSidebar (240px, collapsible to 48px)** — search input, `+ New Build` cyan CTA, sessions grouped by Today / Yesterday / This Week / Older with active-row cyan left-border, hover-reveal delete, sticky **ModelPicker** at bottom (Platform group + Your Keys group split by `byok_service` field, with build-cost chip), credits card showing `subscription / monthly` + `+top-up`.
- **ChatPanel (flex-grow)** — header with session title + status pill (`Draft/Building/Ready/Deployed`) + Open in Workflows escape hatch. Scrollable thread with new bubble system: user messages right-aligned (cyan avatar, dark surface), assistant messages left-aligned with bot avatar (no bubble — just text), error messages with red-left-border card, build results as a special **CodeGenerationCard** ("✅ Generated: Bot · 5 files · 4 nodes · 1.2s + [View Code] [Open in Workflows]"). Auto-grow textarea (1–6 lines) with Cmd/Ctrl-Enter to chat, Chat + Generate Code buttons in toolbar showing live credit cost.
- **EmptyState** — "What do you want to build?" hero + 4 prompt suggestion cards (Customer Support / Data Pipeline / Slack Daily Summary / Lead Qualifier) — click to prefill the input.
- **AgentPreview (380px, slides in when project exists)** — header card with agent icon + name + version + Draft/Ready/Deployed pill + Trust Score chip. Three tabs:
  - **Files**: vs-dark Monaco editor with file tabs, JetBrains Mono 12px.
  - **Flow**: custom inline-SVG mini graph (cyan triggers · purple LLM · amber conditions · green actions) with grid backdrop + arrow markers — zero new deps (React Flow not in package.json so I wrote a 90-line layout component).
  - **Config**: project meta + last 5 commits.
- **AgentActionBar (bottom of preview)** — Test Run (amber, calls new `POST /armory/bot-projects/{id}/test-run`) · Deploy (cyan primary, opens DirectPublishModal) · Publish (purple) · Export (downloads `.tfagent.json` blob client-side). Inline pass/fail result panel with first 280 chars of output.

**Backend addition**:
- `POST /api/armory/bot-projects/{id}/test-run` (16 lines, in `routes/armory_builder.py`) — reuses `routes/workflow_executor.execute_workflow_dag`, gated by `lib/compute_credits.check_compute_credits` + `increment_compute_usage`. Returns `{success, run_id, duration_ms, output, error, node_results}`. Empty-node project → 400, non-owner → 404, cap-hit → standard credit-gate dict.

**Design tokens** (scoped under `.armory-shell` so the rest of the app's `--bg-card` etc. is unaffected):
- Dark default: `#0A0A0A` bg · `#111` panels · `#1A1A1A` cards · `#2A2A2A` borders · `#00E5CC` accent · `#F3F4F6` text. Light-mode override via `html.light .armory-shell` (kept code blocks dark per editor convention). Fonts: Inter 14px body, JetBrains Mono 13px code, Rajdhani 500 for headings, mono 11px uppercase 1px letter-spacing for nav labels. Animations: 150ms fade-in on new messages, 1.4s pulse on "Generating…" indicator. Responsive: < 1100px → preview becomes bottom sheet; < 800px → sidebar fixed-overlay.

**App.js + Navbar wiring**:
- `/armory` route: was `AdminGate(Studio)` private-beta gated → now `ProtectedRoute(Armory)` open to all auth'd users.
- `/armory/workflows/:projectId` route: `AdminGate(Studio)` for the "Open in Workflows" CTA.
- Removed `soon: true` flag from the navbar's Armory link.
- Footer hidden when on `/armory*` so the chat layout consumes full viewport.

**Verified (iter50)**: **8/8 new backend tests + 100% frontend Playwright PASS**. Test agent found and fixed 1 CRITICAL backend import bug (compute-credit helper imported from wrong module — now `from lib.compute_credits import ...`). 1 cosmetic deviation flagged (single Platform group instead of two) → main agent fixed by switching ModelPicker grouping criterion to `byok_service`. Final smoke confirms both PLATFORM + YOUR KEYS groups now render correctly. Existing regression (iter46+47+48+49 = 37/39 + 27/27 P2) intact.


### Phase 53 (Feb 2026) — 5-Feature P2 Batch (Build-in-Armory · Schedules · Reviews · Earnings · Public API)

**P2-1: Build-in-Armory round-trip**
- `pages/VibeBuildPage.jsx` reads `sessionStorage('tfai_bounty_prefill')` on mount and renders a cyan **bounty context banner** (`data-testid='bounty-prefill-banner'`) with the bounty title + Target icon. The first prompt textarea is auto-prefilled with a templated "Build me an agent for the bounty …" message including the spec body (capped at 1200 chars).
- After a successful Vibe build (`lastBuild` set on `build` mode success), the banner reveals a green **"Submit to bounty"** CTA (`data-testid='submit-to-bounty-cta'`) that clears the sessionStorage and navigates to `/bounties/<id>?submit=1`.
- `pages/BountyDetail.jsx` now reads `?submit=1` and auto-opens the SubmitToBountyModal for non-poster users on `status='open'` bounties; the param is stripped on open to keep refresh idempotent.

**P2-2: Scheduled executions (4 preset intervals)**
- New `routes/schedules.py`: `GET/PUT /api/deployments/{id}/schedule` with 4 hardcoded presets (`hourly` 60min · `6h` 360min · `daily` 1440min · `weekly` 10080min). Persisted on `user_bot_deployments.schedule = {enabled, preset, interval_minutes, next_run_at, last_run_at, last_run_id, last_run_success}`.
- **APScheduler tick** (`tick_scheduled_runs`) runs every 5 minutes via `server.py` — scans `schedule.enabled=true AND schedule.next_run_at<=now`, dispatches via `run_deployment_real(trigger='schedule')`, bumps `next_run_at` forward by `interval_minutes`. Per-month run-cap enforced — when hit, the schedule auto-disables with `last_disabled_reason='limit_reached'`.
- `pages/MyDeployments.jsx` gains a 4th **"Schedule" tab** (`Calendar` icon) per deployment card: enable/disable checkbox, 4 preset buttons (`sched-preset-{id}-{preset}`), live next-run timestamp + last-run status pill.

**P2-3: Reviews & ratings**
- New `routes/reviews.py` mounted under `/api/exchange`: `GET /listings/{id}/reviews` (public, paginated + aggregate + 1-5 star histogram), `POST /listings/{id}/reviews` (5-star + 10–1500-char comment, one per user per listing, self-review 403'd, duplicate 409'd), `DELETE /reviews/{id}` (author or admin only), `POST /reviews/{id}/reply` (listing owner only, one-time reply, second attempt 409'd), `GET /listings/{id}/reviews/my-review` (for FE state).
- Aggregates denormalised onto `exchange_listings.aggregates.{reviews_count, reviews_avg}` for fast card-grid sort. Star histogram computed live for the detail page.
- New `components/ReviewsPanel.jsx` (~330 LoC) — reusable widget with aggregate header card (big avg + 5-row histogram bars), star picker submit form, "my review" summary chip, owner reply UI (collapsed → textarea), threaded reply rendering with cyan accent border.
- New `pages/ListingDetail.jsx` at `/listing/:id` route — replaces the broken legacy `/agent/:id` flow for real Exchange listings. Header card with avatar/name/bounty-winner badge/pricing + the ReviewsPanel below. Marketplace cards now link to `/listing/:id`.

**P2-4: Creator earnings dashboard**
- New `routes/creator_earnings.py`: `GET /api/creator/earnings/summary?days=N` returns rolled-up `{window:{usd_total, stripe_usd, cash_bounty_usd, credit_bounty_total, deploy_runs, …}, lifetime:{usd_total, stripe_usd, cash_bounty_usd, credit_bounty_total}}`. Sources: `creator_revenue_ledger` (Stripe 80% take-home), `bounties` (cash + credit wins), `deployment_runs` (listing exec counts).
- `GET /api/creator/earnings/ledger?limit=N&skip=M` — combined chronological feed of every earning event (kind=`exchange_payout` · `bounty_won` · `bounty_won_credits`), newest-first.
- `GET /api/creator/earnings/export.csv` — text/csv with attachment Content-Disposition, full ledger up to 1000 rows.
- New `pages/CreatorEarnings.jsx` at `/earnings` — 3 big stat cards (lifetime USD/credits/runs in window), 4 mini stats, window toggle 7/30/90/365 days, CSV export button, scrollable ledger table with kind-coded icons (Trophy for bounty wins, ArrowDownRight for Stripe payouts).

**P2-5: Public API + keys**
- New `routes/public_api.py`:
  - **Key management (JWT)**: `POST /api/keys` mints `tfai_<64hex>` (stores SHA256 hash only, plaintext returned ONCE), `GET /api/keys` (lists without hashes/plaintext), `DELETE /api/keys/{id}` revokes.
  - **Public endpoints (X-API-Key)**: `POST /api/public/v1/deployments/{id}/run` (body `{input: {…}}`) returns `{run_id, success, duration_ms, output, error, started_at, finished_at}` via `run_deployment_real(trigger='api')`; `GET /api/public/v1/deployments/{id}/runs?limit=N&skip=M` returns run history.
  - **Rate limit**: 60 req/min per key, in-process sliding window via `collections.deque` (Redis HA is a documented future ENH). Returns 429 with `retry_after_seconds` on excess. Per-call `last_used_at` + `call_count` bumps.
  - **Auth errors**: 401 `MISSING_API_KEY` (no header) · 401 `INVALID_API_KEY` (unknown/revoked) · 404 `DEPLOYMENT_NOT_FOUND` (cross-tenant) · 429 `RUN_LIMIT_REACHED` (monthly cap).
- New `pages/ApiKeys.jsx` at `/keys` (renamed from `/api-keys` — that path collided with the `/api/*` ingress rule). Mint form, fresh-key reveal card with copy button + "saved it" dismiss, list of active keys with prefix + call count + last_used, revoke button, Quick Start curl docs.

**Routing + Nav additions** (`App.js` + `Navbar.jsx`):
- New routes: `/earnings`, `/keys`, `/listing/:id`.
- New dropdown menu items: **Earnings** (`TrendingUp` icon) + **API Keys** (`Key` icon).
- Marketplace agent cards updated to link to `/listing/:id` (was `/agent/:id`).

**Verified (iter49)**: **27/27 NEW backend tests PASS (schedules 6/6, reviews 7/7, earnings 4/4, api keys 4/4, public API 6/6 incl. 429 rate-limit)**. Regression: 37/39 (the 2 fails are the parked iter48 Stripe Connect platform-enablement op-item, unrelated). Frontend Playwright: all 5 features render cleanly with full data-testid coverage. Zero defects, zero critical issues.


### Phase 52 (Feb 2026) — Cash Bounties via Stripe Connect (Prompt 9 P2)

- **`routes/bounties.py` cash branch** in `create_bounty`: when `reward_type='cash'`, validates `cash_amount_usd` ∈ [$10, $10,000] + requires `origin_url`, creates the bounty doc with `status='pending_payment'` + `escrow_status='pending'`, mints a Stripe Checkout Session via `emergentintegrations.payments.stripe.checkout` (USD, success_url=/payment/success?type=bounty), and inserts a parallel `payment_transactions` row of `type='bounty'` so the existing webhook + status poller plumbing picks it up. Returns `{bounty, checkout_url, session_id}` for the frontend redirect.
- **`POST /api/bounties/{id}/activate`** — frontend polls this after the Stripe redirect. Verifies poster identity, confirms the linked `payment_transactions.payment_status == 'paid'`, retrieves the `charge_id` via `stripe.checkout.Session.retrieve(expand=['payment_intent'])`, and flips the bounty to `status='open'` + `escrow_status='held'` with the persisted `stripe_charge_id` + `stripe_payment_intent_id`. Idempotent (returns `{already_active: true}` on re-call). 402 if payment not confirmed; 403 if not the poster.
- **`routes/stripe_connect.py`** (NEW, ~300 lines) — full Stripe Connect Express integration using the raw `stripe` SDK 14.4.1 (emergentintegrations only handles one-shot Checkouts):
  - `GET  /api/stripe-connect/account` — live-refreshes the connected account from Stripe each call, returns projected `{stripe_account_id, charges_enabled, payouts_enabled, details_submitted, requirements_currently_due, ready_for_payout}`.
  - `POST /api/stripe-connect/onboard` — idempotent `stripe.Account.create(type='express')` + persists `connect_accounts` row + mints a fresh `stripe.AccountLink` for hosted onboarding.
  - `POST /api/stripe-connect/refresh-link` — semantic alias used by FE for resume-incomplete flows.
  - `POST /api/stripe-connect/dashboard-link` — mints an Express dashboard login link for fully-onboarded creators (409 otherwise).
  - `POST /api/stripe-connect/refresh-status` — forces a live pull from Stripe (used by FE after onboarding redirects with `?stripe_return=1`).
  - Helpers consumed by `routes/bounties.py`: `get_account_for_user`, `is_ready_for_payout`, `create_transfer(amount_usd, destination, source_charge, transfer_group, metadata)`, `refund_charge(charge_id, reason, metadata)`.
- **Cash award path** (`award_bounty`): if `reward_type='cash'`, looks up the winner's `connect_accounts` row, returns 409 `WINNER_PAYOUTS_NOT_READY` with onboarding URL if they haven't completed onboarding, otherwise calls `stripe.Transfer.create` with `source_transaction=stripe_charge_id` (Separate Charges and Transfers pattern). Persists `stripe_transfer_id` on the bounty. Notifications include `reward_type` so toasts can render `$X.XX` vs `+X credits`.
- **Cash cancel + janitor path**: `cancel_bounty` calls `refund_charge(stripe_charge_id)` for `status='open'` cash bounties; pending_payment cash bounties simply flip to cancelled without a Stripe call (nothing was ever charged). `expire_lapsed_bounties` mirrors the same logic — auto-refunds via `refund_charge` for held cash escrow past grace period.
- **`GET /api/payments/status/{session_id}`** extended — now returns `type` + `bounty_id` so the success page can dispatch to the right activation route.
- **Stripe webhook** (`routes/stripe_payments.py`) — recognizes `tx.type='bounty'` and logs the confirmation; row provisioning still defers to the manual `/activate` call from the success page (mirrors hosting pattern for clear UX confirmation).
- **Stats aggregation** — `GET /api/bounties` stats now split into `credits_paid_out` (int credits) AND `cash_paid_out` (float USD) using `$cond` branches on `reward_type`.
- **Public feed gating** — `pending_payment` bounties are now excluded from the public `/api/bounties` listing (still visible to the poster via `/api/bounties/my-posted`) so funded-but-not-paid bounties don't pollute the marketplace.
- **Frontend `pages/Payouts.jsx`** wired at `/payouts` (ProtectedRoute) + nav menu link in the user dropdown (`Banknote` icon). Renders 3 states:
  - **No account**: cyan "Set up payouts" CTA → `POST /onboard` → redirects to Stripe.
  - **Partial**: amber "Finish onboarding" card with status chips (Identity/Charges/Payouts) + `requirements_currently_due` list.
  - **Ready**: green "Payouts ready" card + "Stripe Dashboard" external link button.
  - Auto-detects `?stripe_return=1` to live-refresh after returning from Stripe.
  - Friendly toast when the platform Stripe account hasn't enabled Connect (points to dashboard.stripe.com/connect).
- **Frontend `components/PostBountyModal.jsx`** — replaced the disabled "Cash · soon" pill with a real Credits/Cash toggle (`data-testid='reward-type-toggle'` + `reward-type-credits` + `reward-type-cash`). Cash mode shows a green USD input (`data-testid='bounty-cash-input'`, default $50, min $10, max $10,000), info text about Stripe escrow + 100% pass-through, link to `/payouts` for creator setup, and a green "Continue to Stripe →" submit button. On submit, browser is redirected to the Stripe Checkout URL.
- **Frontend `pages/PaymentSuccess.jsx`** — new `?type=bounty` branch with a Target icon, "Bounty Funded" success card, "$X.XX held in Stripe escrow" subtitle, "View bounty" + "All Bounties" CTAs. Calls `POST /api/bounties/{id}/activate` after the payment poll lands on `paid`. Error/expired states use "Back to Bounties" CTA when `type=bounty` (vs default "Back to Marketplace").
- **Frontend `pages/BountyBoard.jsx`** + **`pages/BountyDetail.jsx`** — exported a `fmtReward(b)` helper that returns `{value, unit, color}` based on `reward_type`. Cards + detail header now render `$X.XX USD` in green for cash and `X cr` in cyan for credits. BountyBoard adds a 4th stat tile "Cash paid out" (`data-testid='stat-cash-paid'`). Award + Cancel confirms in BountyDetail switch wording based on reward_type. SubmissionRow's Award button label is now dynamic: "Award $XX.XX" for cash, "Award X cr" for credits. WINNER_PAYOUTS_NOT_READY (409) surfaces a clear toast pointing the user to `/payouts`.
- **Verified (iter48)**: **13/13 code-controllable backend tests pass + 24/24 regression = 37/37 testable green**. Frontend Playwright covered Payouts page, navbar entry, 4-stat bounty grid, PostBountyModal cash toggle + cash input + "Continue to Stripe →" button, real Stripe Checkout URL captured (cs_test_...), PaymentSuccess `?type=bounty` error branch shows "Back to Bounties". 2 tests in the report fail on `stripe.Account.create` because the platform Stripe account behind `STRIPE_API_KEY` hasn't been registered as a Connect platform on the Stripe dashboard — **NOT a code defect**, fix is a one-time operational step at https://dashboard.stripe.com/connect by the platform owner. All other Stripe Connect endpoint logic (account-status projection, idempotency, refresh, dashboard link, transfer + refund helpers) is verified by unit-level tests and code review.

### Phase 51 (Feb 2026) — Notifications Bell + Bounty Winner Badge (Bounty Loop Polish)
- **`routes/notifications.py`** (new) — 4 endpoints:
  - `GET /api/notifications?limit&unread_only` — paginated list of the authed user's notifications + unread count, newest-first.
  - `GET /api/notifications/unread-count` — lightweight `{unread: int}` for the bell badge poller (30s interval).
  - `POST /api/notifications/{id}/read` — flip `read=true` + `read_at`. Cross-user access returns 404 (no enumeration leak).
  - `POST /api/notifications/mark-all-read` — bulk flip all unread for the user.
- **Frontend `components/NotificationBell.jsx`** (new) — bell icon in the navbar to the left of UserMenu. Cyan unread-count badge overlays when `unread > 0`. Click toggles a dropdown with: header showing "NOTIFICATIONS" + "X NEW" chip + "Mark all read" link, scrollable list of up to 20 rows (icon by kind: Trophy for `bounty_won`, Target for `bounty_submission_new`, XCircle for `bounty_lost`), per-row relative time + cyan unread dot. Rows wrap in React Router `<Link>` when payload carries `bounty_id` — auto-navigate to `/bounties/{id}` on click. Click also marks the row read (opacity drops 100% → 55%, dot disappears). Click-outside closes via `mousedown` listener.
- **`pages/Marketplace.jsx`** — listings map now forwards `bountyWinner`, `bountyTitle`, `bountyId`. `AgentCard` renders a gold gradient "BOUNTY WINNER" Trophy chip (lower-left of media area, with cyan glow box-shadow) when `agent.bountyWinner` is true. `title` attribute shows the bounty title on hover. `data-testid=bounty-winner-badge-{agent.id}` for QA.
- **Verified (iter47)**: **8/8 new + 79 regression = 87/87 backend tests green**. Frontend Playwright covered: bell renders, unread badge appears with correct count, dropdown opens with header + rows + Mark-all-read link, row click navigates to /bounties/{id} AND flips read state, click-outside closes, marketplace badge renders only when listing carries `bounty_winner=true`. Zero bugs. Code-review notes (non-blocking): 30s polling acceptable for current scale (SSE upgrade path noted), fire-and-forget `_emit_notification` carries minor GC risk under heavy concurrency.

### Phase 50 (Feb 2026) — The Bounty Board (Prompt 9)
- **New `routes/bounties.py`** (~656 lines) — demand-side marketplace endpoints:
  - `POST /api/bounties` — create with full Pydantic validation (title 8-120, description 20-10000, reward >= 50cr, deadline 3-30 days, category enum, max_submissions 1-50). Debits reward via `credit_wallet.debit(action="bounty_escrow", cost_override=reward_amount)` BEFORE inserting so a failed debit can't orphan a bounty. Returns 402 `INSUFFICIENT_CREDITS` for insolvent posters.
  - `GET /api/bounties` (public, no auth) — paginated list with category/status filters, 4 sort modes (newest, highest_reward, ending_soon, most_submissions), and aggregate stats: active, awarded_count, credits_paid_out. Hides cancelled rows from the public feed by default.
  - `GET /api/bounties/{id}` — single fetch with `is_poster` + `my_submission` flags pre-computed for the UI. Routes `my-posted` and `my-submissions` are declared BEFORE this path-param route so FastAPI matches them correctly.
  - `GET /api/bounties/my-posted` + `my-submissions` — author dashboard data; my-submissions hydrates each row with its parent bounty.
  - `PUT /api/bounties/{id}` — poster can extend deadline + bump max_submissions any time pre-award. Description edits LOCKED (409) once submissions land — anti-bait-and-switch.
  - `POST /api/bounties/{id}/cancel` — refunds escrow in full, marks `status='cancelled'`, `escrow_status='refunded'`. Blocked (409) if any submissions exist; let it run its course at that point.
  - `POST /api/bounties/{id}/submit` — creator submits an Exchange listing OR external agent. Ownership-verified via `_verify_agent_belongs_to_creator` (403 if they don't own it), self-submission blocked (403), duplicates blocked (409), max_submissions cap enforced (409).
  - `GET /api/bounties/{id}/submissions` — POSTER (and admin) see ALL submissions; non-poster non-submitter only see `{submissions: [], total: count}`. Submitter sees just their own row.
  - `POST /api/bounties/{id}/award` — releases escrow via `credit_wallet.credit(winner, ..., source="bounty_award")`. Marks the winning sub `winner`, other subs `rejected`, the bounty `awarded` + `escrow_released`. If the winning agent is an Exchange listing, tags it with `bounty_winner: true`, `bounty_winner_id`, `bounty_winner_title`, and increments `bounty_wins` for social proof. Bumps poster counters (`bounties_posted`, `credits_paid_out_total`) and winner counters (`bounty_wins`, `credits_won_total`).
  - In-app **notifications** scaffolding — `_emit_notification` inserts to `notifications` collection on submit/win/lose with `asyncio.create_task` (fire-and-forget; bell UI deferred). Toast surfacing handled frontend-side via `sonner`.
- **APScheduler `bounty_expire` job** registered in `server.py` startup at 1-hour interval. Calls `expire_lapsed_bounties(db)` which (1) flips open bounties past deadline to `in_review` (poster has 7-day grace window to award) and (2) flips `in_review` bounties past `deadline + 7d` to `expired` and AUTO-REFUNDS the escrow back to the poster's wallet.
- **Frontend** (3 new files + 1 update):
  - `pages/BountyBoard.jsx` — list page with 3 stat tiles (active / awarded / credits paid out), category filter pills, status filter pills, sort dropdown, responsive 3-col card grid. Cards show status pill, reward (big cyan), deadline countdown (orange when <24h), submission count, urgency badge.
  - `pages/BountyDetail.jsx` — header card with status/category/reward/countdown, 2/3-1/3 description+spec grid, submissions section. Poster sees all submissions with Award buttons; non-poster sees their own submission or count only. Winners get a "Winner" badge; losers fade out.
  - `components/PostBountyModal.jsx` — full form with all required fields, live wallet-balance display, "Cash · soon" disabled tab (per scope choice), 8 category options, 17 integration toggle chips, escrow warning in sticky footer.
  - `components/SubmitToBountyModal.jsx` — 3-tab picker (Exchange listing / External agent / Build in Armory). Build tab redirects to `/build` with bounty context persisted to `sessionStorage('tfai_bounty_prefill')` so a future Vibe Coding integration can read it. Pitch textarea with min-20 validation.
- **Routing**: `/bounties` (public, no auth — same lock pattern as Exchange) + `/bounties/:id` (ProtectedRoute). "Bounty Board" link added to main nav center links between THE EXCHANGE and THE ARMORY.
- **Verified (iter46)**: **16/16 new bounty tests + 63/63 regression = 79/79 backend green**. Frontend Playwright: page renders, navbar entry visible, PostBountyModal opens with all fields. Zero bugs. Test-agent code-review flags (none blocking): bounties.py at 656 lines near refactor threshold; notifications collection has no read endpoints yet; award/cancel routes aren't transactional (acceptable for credit-only MVP).

### Phase 49 (Feb 2026) — Hosting Quota Enforcement + Lapsed-Subscription Janitor
- **`routes/exchange.py` — `_enforce_publish_quota(db, user, listing_id)` helper** runs on every draft→published transition. Imports `routes.hosting.can_publish` + `increment_agents`. Non-admin users without a sub get HTTP 402 `{error: NO_HOSTING_PLAN, upgrade_url: /hosting}`; over-cap users get HTTP 403 `{error: agent_cap, tier, agents_used, max_agents, upgrade_url}`. Admin users bypass the cap (still counter-bumped for ops visibility).
- **`_release_publish_quota(db, user_id, listing_id)` helper** decrements + pulls listing_id on the reverse transition (published→draft / delisted) and on DELETE. Best-effort with silent except — never blocks the delete.
- **Wired into 3 transition points**:
  - `PUT /api/exchange/listings/{id}` — when `status` field is patched and differs from current status.
  - `POST /api/exchange/listings/{id}/upload` — quota check moved to the TOP of the handler before writing media to disk (fixes the orphan-media risk flagged by iter45 testing agent). Auto-promote branch at the bottom now just flips status since quota was already enforced.
  - `DELETE /api/exchange/listings/{id}` — releases slot before file/row deletion.
- **New helpers in `routes/hosting.py`**:
  - `decrement_agents(db, creator_id, listing_id)` — idempotent reverse of `increment_agents`. Clamps `agents_used` to 0 and `$pull`s from `agents_published`. No-op if listing_id isn't in the set.
  - `expire_lapsed_subscriptions(db)` — flips `cancelled` rows whose `current_period_end` is in the past to `status='expired'` with `expired_at` timestamp. Also flips `active` rows past period_end (defensive — Stripe one-month checkouts don't auto-renew, so this catches forgotten renewals). Returns total flipped count.
- **APScheduler job `hosting_expire`** registered in `server.py` startup at 1-hour interval. Runs `expire_lapsed_subscriptions(db)` and logs the count when non-zero. Coexists with the existing daily `supernova_eval` job.
- **Expired subscriptions === no subscription** for `can_publish` purposes (`get_active_subscription` only matches `status='active'`), so published-cap enforcement engages automatically once the janitor flips a row to expired.
- **Verified (iter45)**: **9/9 enforcement+janitor tests + 54/54 regression (iter42-44) = 63/63 backend green**. Coverage: no-sub 402, under-cap success + counter bump, at-cap 403, delete releases slot, delist releases slot, expired sub blocks publish, janitor flips 2 rows + leaves future-period row untouched, decrement_agents idempotency, admin bypass + counter still bumps, scheduler job registered. Testing subagent flagged orphan-media on quota-blocked upload (now FIXED by moving the check to the top of upload_media).

### Phase 48 (Feb 2026) — Hosting Subscription Tiers (Prompt 7 Part 3)
- **New `routes/hosting.py`** (~430 lines) — full CRUD for the creator-side hosting subscription system, separate from the existing user-tier subscriptions (recruit/cadet/operator/...).
  - **4-tier catalogue** in `HOSTING_TIERS`: Starter $9 (1 agent, 1k runs, 10s runtime), Pro $29 (3 agents, 10k runs, 30s, **highlighted as Most Popular**), Growth $99 (10 agents, 50k runs, 60s + SLA), Scale $299 (unlimited agents = `max_agents:0`, 250k runs).
  - **Routes**: `GET /hosting/tiers` (public catalogue), `GET /hosting/me` (current sub or null), `GET /hosting/usage` (counters + caps + pct utilisation), `POST /hosting/checkout` (Stripe sandbox one-month checkout), `POST /hosting/activate` (idempotent post-payment provisioning), `POST /hosting/cancel` (flips status to cancelled, retains access until period_end).
  - **Pydantic regex** `^(starter|pro|growth|scale)$` rejects unknown tiers with 422 — server-side pricing is the source of truth, frontend can never inject custom amounts.
  - **Idempotent activate** — second call returns `{already_active: true, subscription: <same row>}`. Concurrent checkouts at the same tier 409.
  - **`hosting_subscriptions` collection schema**: id, creator_id, creator_email, tier, status (active/cancelled/superseded/expired), stripe_session_id, payment_id, amount, current_period_start, current_period_end (today + 30 days), executions_used, agents_used, agents_published[], created_at, updated_at, cancelled_at.
  - **Exported helpers**: `can_publish(db, creator_id)` (allowed/agent_cap/no_subscription), `increment_executions(db, creator_id, by)` (atomic `$inc` on the active sub), `increment_agents(db, creator_id, listing_id)` (also `$addToSet` to agents_published).
- **`routes/stripe_payments.py` webhook extended** — `tx.type == "hosting"` branch logs the paid event but defers row provisioning to the manual `/hosting/activate` call from the success page (cleaner UX confirmation step, mirrors how subscription tiers are activated).
- **`routes/external_agents.py:506-516`** — every successful external agent run best-effort `await increment_executions(db, user_id, by=1)`, wrapped in try/except so missing hosting subscriptions never break the run path.
- **Frontend `pages/HostingPlans.jsx`** (new) — Creator Hosting page at `/hosting`: 4-tier responsive grid with distinct accent colors (slate/cyan/purple/amber), "Most Popular" badge on Pro, "Current" badge on the active tier, `∞` glyph for Scale's unlimited agents, per-card Subscribe CTAs that hand off to Stripe sandbox, active-plan banner with live usage stats + Cancel link, no-plan banner shown when sub is null.
- **Frontend `pages/PaymentSuccess.jsx` extended** — reads `?type=hosting` query param, calls `POST /api/hosting/activate` after the payment poll confirms `paid`, renders a tailored "Hosting Plan Activated" card with tier label + renewal date + two CTAs (Hosting Dashboard / Creator Dashboard). Existing one-shot agent rent/buy flow unchanged.
- **Navbar dropdown extended** — added "Hosting Plans" menu item with `Server` icon, placed under "External Agents". Route registered at `App.js:/hosting` wrapped in `ProtectedRoute`.
- **Verified live (iter44)**: **56/56 backend tests pass** (15 new hosting + 10 part2 regression + 29 iter42 regression + 2 promo regression). Frontend Playwright covered hosting page render, tier grid, MOST POPULAR badge, Stripe sandbox redirect (URL captured `cs_test_...`), navbar entry, promo redeem on `/credits`. End-to-end checkout→mark-paid→activate→usage→cancel flow self-verified via direct mongo + curl after the test agent ran. Zero product bugs found.

### Phase 47 (Feb 2026) — External Agent Pip Venv Runtime (Prompt 7 Part 2)
- **New `lib/external_agent_runtime.py`** — manages the full lifecycle of validated `.tfagent` packages beyond storage:
  - `install_agent(db, package_id, allowed_packages)` — extracts the stored zip blob into `/app/data/agent_venvs/{id}/code/`, regenerates `requirements.txt` from `manifest.dependencies` while RE-VALIDATING each line against `ALLOWED_PACKAGES` (defence in depth), creates an isolated venv via `python -m venv`, runs `pip install -r requirements.txt` with a 240s cap, and drops the `_runner.py` harness next to it. Updates Mongo: `install_status: ready`, `execution_ready: true`, `install_log`, `install_deps_pinned`, `installed_at`.
  - `run_agent(package_id, entry_path, entry_fn, input, env, keys, timeout, memory_mb)` — async wrapper that offloads to a thread. Spawns the venv python via `subprocess.Popen` in its own session group with `preexec_fn` setting `RLIMIT_AS` (memory) + `RLIMIT_CPU` and a minimal `PATH/HOME/PYTHONUNBUFFERED` env. Wallclock timeout via `communicate(timeout=N)` + `os.killpg(SIGKILL)`. Parses the `___TFAI_RESULT___` sentinel for the structured result.
  - `uninstall_agent(package_id)` — best-effort cleanup of the on-disk venv + extracted code on package delete.
  - Hard caps: 60s max wallclock, 512MB max memory, package_id regex `^[a-f0-9]{8,64}$`.
- **New `lib/agent_runner_harness.py`** — dependency-free subprocess entry point. Reads JSON payload from stdin, uses `inspect.signature` to invoke `run(input, env=..., keys=...)` with whatever subset of kwargs the agent's function actually accepts (so plain `def run(input):` works AND `def run(input, env, keys):` works AND `async def run(input):` works). Adds the agent's `code/` dir to `sys.path` so sibling-file imports resolve. Emits `___TFAI_RESULT___` + JSON sentinel on stdout — never raises into the calling Python process.
- **New endpoints** in `routes/external_agents.py`:
  - `POST /api/external-agents/packages/{id}/install` — fire-and-forget `asyncio.create_task(install_agent)`. Idempotent: returns `{queued: false, install_status: 'ready'}` if already installed.
  - `GET  /api/external-agents/packages/{id}/install-status` — `{install_status, execution_ready, install_log_tail, install_error, deps_pinned}` for polling.
  - `POST /api/external-agents/packages/{id}/run` — `can_afford` precheck (returns 402 with `INSUFFICIENT_CREDITS` if broke), 409 if `execution_ready=false`, dispatches `run_agent`, persists a row to `external_agent_runs` (id, package_id, started/finished, duration_ms, success, status, input, result, output, stderr, error, trace, exit_code, credits_spent), debits 2cr via `credit_wallet.debit("external_agent_run", ref=run_id)`, increments `usage.run_count/failures/last_run_at`.
  - `GET  /api/external-agents/packages/{id}/runs?limit=25` — recent run history sorted descending.
- **Frontend `pages/ExternalAgents.jsx`** (new, ~580 lines, kept under split-soon limit) — upload zone (drag-and-drop + click) → upload toast → package list. Per-row: chevron-expand toggle, status pill (NOT INSTALLED / INSTALLING / READY / FAILED with auto 3s polling while installing), Install / Run / Delete actions. Expanded view: tabbed Run (JSON textarea + inline JSON validation + Run button "Cost: 2 credits" label + Success/Failed result block with duration), Logs (pip install tail + install error), Runs (sortable history), Manifest (pretty-printed JSON + pinned-deps chips). Native `window.confirm` on delete.
- **Wired into App.js + Navbar**: `/external-agents` route under `ProtectedRoute`, "External Agents" menu item with `Package` icon in the user dropdown.
- **One bug found & fixed in dev**: `credit_wallet.can_afford()` returns key `allowed` (not `can_afford`) — fixed the route check.
- **Verified live (iter43)**: 39/39 backend tests pass (10 new Part 2 + 29 iter42 regression). Includes the critical real-pip-install of `python-slugify` followed by an actual runtime import + slugify call returning `{slug: "hello-world-2026"}`. 2-second manifest timeout test confirms subprocess kill within ~3s wallclock. Frontend Playwright verified: upload → list → install → poll-to-ready → expand → run → see result → runs tab populated → delete with native-confirm. No bugs found.

### Phase 46 (Feb, 2026) — Smart Model Auto-Pick
- **`POST /api/vibe/recommend-model`** — 1cr Gemini Flash classifier. Returns `{model, label, build_cost, reason, complexity: simple|medium|complex, credits_used, balance_remaining}`.
- Picks one of the 6 catalogue models based on task complexity (simple text transforms → Flash/Mini/Haiku; complex multi-step research → Pro/Sonnet/4o; classification → Mini/Haiku).
- Pydantic `Field(min_length=3, max_length=4000)` for the prompt → 422 on invalid input. 402 short-circuits insufficient-credit users BEFORE the LLM call so they don't burn tokens.
- Defensive fallback: if the LLM output can't be parsed, returns `{model: gemini-2.5-flash, reason: 'Fast and cheap — good fit for most tasks.', complexity: medium}` — the endpoint never 500s.
- `credit_transactions.ref = "recommend:<picked_model_id>"` for analytics distinguishability.
- **Frontend**: `AUTO · 1cr` button (data-testid `vibe-auto-pick`) in the top bar, disabled when input is empty with helpful title. Inline hint banner (data-testid `auto-pick-hint`) shows uppercase complexity tag + AI reason. Auto-dismisses after 12s via `useEffect` cleanup (handles unmount safely). Loading spinner replaces the icon while the request is in flight.
- **Verified live**: iter41 — backend 12/12 + frontend 100%. Main agent smoke-tested 3 prompts via curl: simple text → Flash, complex research → Pro, classification → Mini. Picks were sensible across all 3.


- **Every model works for every user immediately.** Removed the 402 `BYOK_REQUIRED` gate from `/vibe/chat` and `/vibe/generate`. All 6 models (Gemini Flash/Pro, GPT-4o/Mini, Claude Sonnet/Haiku) front their call through the Emergent Universal Key by default — same key already handled Gemini, also routes OpenAI + Anthropic.
- **Silent BYOK override** (`_resolve_api_key`): if the user has a stored credential in `byok_credentials` for the model's provider (openai or anthropic), the decrypted key fronts the call and `key_source="byok"` lands in the response. Otherwise platform key + `key_source="platform"`. Corrupted ciphertext falls through silently — never blocks the user.
- **Model ID decoupling**: user-facing IDs (`claude-sonnet`, `claude-haiku`, etc.) stay stable in the API contract while internal `api_model` field maps to versioned provider IDs (`claude-sonnet-4-5-20250929`, `claude-haiku-4-5-20251001`). Fixed the prior bug where `claude-sonnet` was sent verbatim and rejected by Anthropic.
- **`using_byok` flag** on `GET /api/vibe/models` per model when the user has the provider's key — surfaces in the UI as a small green "✓ YOUR KEY" badge.
- **Frontend ModelPicker simplified**: removed `disabled`, lock icon, "Add key in Vault →" CTA, reduced opacity, and `cursor:not-allowed`. Every card is now plain selectable. Only addition: the BYOK badge.
- **Verified live**: iter40 — backend 12/12 pytest pass, frontend 100%. All 6 models return non-empty chat responses with `key_source="platform"`. After saving a fake openai BYOK key, resolution flips to `key_source="byok"` for gpt-4o/4o-mini; UI displays "YOUR KEY" badge on those two cards only.


- **New `/build` page (`VibeBuildPage.jsx`)** — Emergent-style chat-driven bot builder. Split layout: 60% chat panel left + 42% generated-file preview right (Monaco read-only with tabs). Collapsible session sidebar shows past builds; click to resume. Suggestion chips for empty state. Multiline textarea with Enter-to-send and Shift+Enter newline.
- **6-model picker** — Gemini 2.5 Flash (3cr build) + Gemini 2.5 Pro (5cr) on the platform (Emergent LLM Key); GPT-4o (5cr), GPT-4o Mini (2cr), Claude Sonnet (5cr), Claude Haiku (2cr) gated by BYOK with Lock icon + "Add key in Vault →" CTA. Per-model cards show speed/quality badges + chat-cost + build-cost.
- **Backend `routes/vibe_coding.py`** — `MODELS` registry as single source of truth. Routes: `GET /vibe/models` (with availability flags per user's BYOK keys), `GET/DELETE /vibe/sessions[/:id]`, `POST /vibe/chat` (1cr per AI reply), `POST /vibe/generate` (per-model build_cost). Wallet debit happens AFTER successful LLM call — failed calls don't charge. BYOK gate returns 402 `{error: BYOK_REQUIRED, service, vault_url}`.
- **Per-model pricing wired end-to-end**: extended `lib/credit_wallet.py:debit()` + `can_afford()` with new `cost_override: int | None` param. `/vibe/generate` passes `MODELS[req.model]["build_cost"]` so Flash users get charged 3cr (not 5), Mini/Haiku users get charged 2cr.
- **60s timeout fix**: old code replayed conversation history by calling `LlmChat.send_message()` once per prior turn — N round-trips, easily hitting the K8s ingress 60s cap. New `_call_platform_llm` collapses history into a single composite user message (`"CONVERSATION SO FAR:\n<transcript>\n\n--- NEW USER MESSAGE ---\n..."`). Verified: chat 3s, generate 30s end-to-end.
- **Robust JSON parser**: `_extract_json()` now walks balanced braces with string-aware bracket counting, strips markdown ```json fences, uses `strict=False` to permit raw newlines/tabs inside string values (essential when files contain Python source code with newlines).
- **Generated code lands in `bot_projects`**: each successful `/vibe/generate` upserts the project (creates on first build, appends a commit_history entry on iteration). `bot_projects.source = "vibe"` flag distinguishes it from the older `/armory/build-bot` route. Session's `project_id` field links the two collections. Reuses existing commit/fork/history endpoints unchanged.
- **`vibe_sessions` collection schema**: id, user_id, title (auto from first message ≤80c), model, messages[] (role, content, timestamp, type, credits_used, model), project_id (linked when first build succeeds), total_credits_used, status, created_at, updated_at.
- **Navbar**: new "BUILD" link with `Sparkles` icon + cyan-accent text + "NEW" badge, placed first in `CENTER_LINKS_PUBLIC` and `CENTER_LINKS_ADMIN`. Visible to both unauth and auth users (when unauth, the site lock still funnels them to ComingSoonLanding first — by design).
- **Verified live**: iter39 — 15/18 backend pytest first run; both flagged issues (per-model pricing + 60s timeout) fixed and re-verified live (Flash: 3cr / 30s end-to-end, files+nodes parsed correctly). Frontend 95% pass on first run.


- **50-credit signup bonus**: every new account gets `topup_credits=50` (never expires) on registration — enough for ~10 chat messages or ~10 workflow runs to experience the product. Signup ledger entry `kind="signup_bonus", pool="topup", note="+50 welcome bonus"` with `metadata.ip` recorded.
- **IP tracking** on every register + login. `registration_ip` (immutable, set on register) + `last_login_ip` + `last_login_at` (updated each login). Resolved from `X-Forwarded-For` (Kubernetes ingress) first IP, falls back to `X-Real-IP`, then socket peer.
- **Anti-abuse cap**: `MAX_ACCOUNTS_PER_IP_24H = 3`. 4th register from same IP within 24h → HTTP 429 with detail `"Too many accounts created from your network. Try again in 24 hours."` Cutoff uses ISO-string `$gte` (lexicographically sortable). Verified end-to-end with `X-Forwarded-For: 203.0.113.99` — 3 success + 1 rejected.
- **Admin Overwatch** — 2 new endpoints in `server.py`:
  - `GET /api/admin/ip-abuse?min_accounts=3` (admin-only) → `{groups: [{ip, count, accounts: [...] }], banned_ips: [...], policy}` — accounts grouped by `registration_ip` with co-traveller detection (any IP touched by a banned user appears in `banned_ips`)
  - `POST /api/admin/ip-abuse/action` with `{user_id, action: flag|unflag|ban|unban}` — toggles `flagged_for_abuse` and `banned` booleans on user docs. Pydantic `Field(pattern=...)` rejects unknown actions with 422.
- **`vibe_chat` cost 0 → 1**: every AI chat message now debits 1 credit (was free). Frontend label `"AI chat (vibe)" → "AI chat message"`.
- **MongoDB indexes**: `users.registration_ip` + `users.last_login_ip` added (non-unique).
- **`ensure_indexes()` refactor**: extracted all `create_index` calls out of `seed_database()` (which early-returns on already-seeded DBs) into an unconditional standalone async function called from the startup hook. New indexes now picked up on every existing deployment without re-seed. Verified: `users` index list = `['_id', 'email', 'id', 'registration_ip', 'last_login_ip']`.
- **Verified live**: iter38 — backend 10/11 pytest pass on first run, the only fail (index gap on seeded DBs) was the iter38 finding which is now fixed by `ensure_indexes()` extraction. Frontend label update verified statically.


- **Full rewrite of `lib/credit_wallet.py`**: split single `credit_balance` into two pools on the user doc:
  - `subscription_credits` — monthly allocation, **resets each billing cycle**
  - `subscription_credits_max` — current tier's allocation (for UI ring + reset target)
  - `topup_credits` — purchased credits, **never expire**
  - `credit_reset_date` — ISO timestamp of next monthly reset
- **Deduction priority**: subscription pool consumed first, then topup. Atomic conditional `find_one_and_update` with both `$gte` guards + auto-retry on race conditions. Verified: bb9 split `2 sub + 3 topup` correctly when sub had 2 left.
- **Action costs expanded 3 → 7**: `vibe_chat=0`, `build_bot=5`, `workflow_run=1`, `bot_deploy=0`, `agent_run=1`, `external_agent_run=2`, `publish_listing=0`. Free actions (`cost=0`) log a `virtual=false` ledger entry but no balance change.
- **`reset_subscription(db, user, tier, days)` function**: sets `subscription_credits = subscription_credits_max = TIER_MONTHLY_GRANT[tier]`, bumps `credit_reset_date`, leaves `topup_credits` UNTOUCHED. Appends a `subscription_reset` ledger entry. Wired into the Stripe webhook for `tx.type=="subscription"`.
- **`credit(db, user, amount, source, pool="topup")` extended with `pool` param**: defaults to "topup" (promos, top-up packs, admin grants). `"subscription"` is reserved for `reset_subscription`. All ledger entries record `pool` field.
- **Legacy migration**: first read of any user with old `credit_balance` and no `subscription_credits` auto-splits — `min(balance, allocation) → sub`, remainder → topup, unsets the legacy field. Idempotent (won't re-run).
- **Admin bypass**: returns `1e9` for both pools + `unlimited=true`. Admin debits log a `virtual=true` ledger entry without changing balances.
- **Stripe webhook extended** (`routes/stripe_payments.py:154-205`): on `paid` event,
  - `tx.type=="subscription"` → calls `reset_subscription(tier=tx.tier)` to grant the new tier's monthly allocation
  - `tx.type=="credit_topup"` → calls `credit(pool="topup")` to add the pack's credits
  - Both paths are idempotent via the `activated` flag on `payment_transactions`.
- **Top-up checkout now persists `payment_transactions` row** so the webhook can find it (`type="credit_topup"`, `credits`, `activated=false`).
- **Frontend `Credits.jsx` full rewrite**:
  - `CircularRing` component for the subscription pool (SVG progress ring, color flips to rose at <10% with low-credit-warning banner)
  - `TopupPoolCard` with amber accent + "Never expire" subtitle + ∞ icon
  - Combined total bar below the two cards
  - 7-row `ActionCostsList` with friendly labels and "free" / "N cr" coloring
  - "How it works" inline callout explaining sub-first deduction
  - Top-up pack tiles now show per-credit cost (`$0.025/credit` etc) below the headline credits
  - Transaction rows annotated with pool breakdown — debits show `sub −2 · top −3`, credits show `→ topup`
- **Verified live**: iter37 — backend 10/11 pytest pass (1 fail is unrelated LLM-budget exhaustion blocking `/armory/build-bot`); frontend 100% pass (all 12 testids render correctly for admin); legacy migration + reset preservation of topup + promo→topup + Stripe webhook imports all verified.


- **Pre-launch gate**: entire site now hidden behind authentication when `REACT_APP_SITE_LOCKED=true`. Unauthenticated visitors see ONLY a dark cyber `ComingSoonLanding.jsx` page on every route except the auth flows.
- **`AppShell` reorg** (`App.js`): 3-state decision tree
  - locked + unauth + non-auth route → `ComingSoonLanding` (no Navbar, no Footer)
  - locked + unauth + auth route (`/login`, `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`) → focused Login (no Navbar/Footer, catch-all to `/login`)
  - else → normal full app shell
- **`ComingSoonLanding.jsx`**: dark `#0A0A0A` background + radial cyan grid pattern + masked vignette + "Something Big Is **Deploying.**" hero (Rajdhani 7xl), eyebrow chip with pulse dot ("AUTONOMOUS AGENT INFRASTRUCTURE"), email input + "JOIN WAITLIST →" cyan CTA, success state with checkmark + emerald glow, live `operatives enlisted` counter pulled from `GET /api/waitlist/count`, "SIGN IN" header link, minimal copyright + Twitter/Discord/GitHub footer icons.
- **Inline email validation**: regex check short-circuits before the API call — invalid emails show inline error without firing a network request.
- **Env toggle**: `REACT_APP_SITE_LOCKED=true` (default). Flip to `false` + restart frontend to open the site to the public. No code change needed.
- **Backend**: `/api/waitlist` (POST idempotent by email) and `/api/waitlist/count` (public) endpoints pre-existed from older phases — verified clean and reused.
- **5 auth route aliases added** (`/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`) — all render the existing multi-mode `Login.jsx` so future deep-links work.
- **Verified live**: iter36 — 100% pass (10/10 backend pytest + 13/13 frontend gating checks). Counter went 6→7 after a real waitlist submit during E2E; no leak path found for underlying pages; admin login still flows correctly through to `/armory` with full Navbar + Footer.

### Phase 40 (Feb, 2026) — Usage Monitor + Dark Mode Sweep + AdminGate Fix
- **AdminGate P0 fix** (`App.js:43-49`): Removed the `if (!user) return <Navigate to="/login">` redirect. Both unauthenticated AND non-admin authenticated users now see the `ComingSoon` page when visiting `/armory`, `/studio`, `/academy` — matches spec. `/deployments` added as an alias route → `/my-deployments`.
- **Usage Monitor analytics dashboard** — new `/my-deployments/:id/monitor` route + `UsageMonitor.jsx` page:
  - 4 KPI cards: Total Runs, Success Rate (color-coded healthy/watch/at-risk), P95 Latency (with P50/P99 subtitle), Credits Spent
  - 30-day daily execution volume bar chart (success cyan + failed rose, stacked) with hover tooltips
  - Monthly quota progress bar with near-limit warning
  - Latency distribution panel (avg/min/max/P99)
  - Recent errors strip (last 5 failures)
  - Execution log table with paginated runs (status pill, trigger, duration, credits, timestamp)
  - LIVE polling toggle (5s interval), Refresh, and Run Now buttons in header
  - "Open Full Analytics" link added from each MyDeployments deployment card
- **3 new backend endpoints** (`routes/credits_and_more.py`):
  - `POST /api/deployments/{id}/run` — now also persists a `deployment_runs` doc per execution (simulated duration_ms 180-2400ms + success 95% baseline until real engine is wired). Returns `{allowed, run_count, limit, run_id, duration_ms, success}`.
  - `GET /api/deployments/{id}/runs?limit=&skip=` — paginated execution log, capped 1-200, owner-scoped (404 cross-user)
  - `GET /api/deployments/{id}/analytics?days=` — aggregates: totals (runs, successes, failures, success_rate, credits_spent), latency_ms (avg/p50/p95/p99/min/max nearest-rank percentiles), daily 30-day histogram (zero-days filled), monthly_quota (used/limit/remaining), recent_errors (max 5). days clamped 1-90.
- **Dark mode sweep**:
  - `Footer.jsx`: replaced hardcoded `bg-black` + `text-zinc-*` with theme-aware `t-bg-sub` / `t-text-sub` / `t-text-mute` / `t-text-dim` + CSS var borders. No more pure-black bleed in light mode.
  - `Login.jsx`: 4 CTAs (login/signup/forgot/reset) changed from `bg-cyan-400 text-white` (poor contrast) → `bg-cyan-400 text-black font-bold` + proper cyan shadow color.
  - `Marketplace.jsx`: active category pill + "Most Deployed" badge now use `text-black font-bold` on cyan.
  - 7 additional pages auto-patched via sed (Dashboard, Academy, SecurityDashboard, AgentDetail, PaymentSuccess, Studio, CreatorDashboard) — all `bg-cyan-400 text-white` and `bg-emerald-*-text-white` → `text-black font-bold`.
- **Verified live**: iter35 testing agent — backend 11/11 new + 4/4 regression pass; frontend 100% (all 14 UsageMonitor testids + theme computed-style checks pass). AdminGate P0 re-verified — unauth `/armory` shows ComingSoon, no /login redirect.


- **Credit wallet** (`/app/backend/lib/credit_wallet.py`, NEW): Emergent-style balance system replaces the old monthly per-tier counter. `credit_balance` field on user doc, atomic `find_one_and_update` debits in `wallet.debit()`, immutable ledger in `credit_transactions`. Action costs: build_bot=5, workflow_run=1, bot_deploy=0. Admin role bypass returns balance=10⁹ (rendered as ∞). Tier monthly grants: free/recruit=50, cadet=500, operator=2000, pro=10000.
- **Armory build-bot now debits credits**: `armory_builder.build_bot` swapped from `check_compute_credits` to `wallet_can_afford("build_bot")` (returns 402 INSUFFICIENT_CREDITS on empty wallet) → `wallet_debit("build_bot")` on success. Ledger entry written with `ref=project_id`.
- **Top-up packs + Stripe** (`routes/credits_and_more.py`): 4 one-time packs (Starter $5/200cr, Builder $19/1000cr, Operator $79/5000cr, Agency $299/25000cr). `POST /api/credits/topup/checkout` mints a Stripe session, `POST /api/credits/topup/poll/{session_id}` is the idempotent success-page handler that grants credits after Stripe confirms `payment_status=paid`.
- **Promo codes**: Admin-only mint/list/disable (`POST/GET/DELETE /api/promo/codes`). Two kinds — `credits` (mint N credits on redeem) and `discount_pct` (apply at top-up checkout). One redemption per user per code enforced via `credit_transactions` lookup.
- **Newsletter**: `POST /api/newsletter/subscribe` (public, dedupe via email upsert), `GET /api/newsletter/subscribers` (admin), `DELETE /api/newsletter/unsubscribe`. `NewsletterWidget.jsx` lives in the footer of every page.
- **Delivery / Deployments system** (`user_bot_deployments` collection): 
  - `POST /api/deployments/free` — instant provision for `rent_price==0 && buy_price==0` listings
  - `POST /api/deployments/checkout` + `/poll/{session_id}` — Stripe one-time payment flow for paid listings (creator gets 80% via `creator_revenue_ledger`, platform 20%)
  - `POST /api/deployments/{id}/upgrade` + `/upgrade-poll` — rent→buy upgrade via Stripe delta
  - `GET /api/deployments/me`, `GET /:id`, `PATCH /:id` (customize name + vars + files + nodes/edges), `POST /:id/run` (usage counter, gated by per-deployment monthly limit)
- **MyDeployments page** (`pages/MyDeployments.jsx`): Card grid with Monitor/Customize/Upgrade tabs per deployment. Live usage bar with near-limit red warning, Run Now button, editable name + env vars, upgrade-to-buy CTA. Avatar inherits listing's icon+color+url with glow border.
- **Credits page** (`pages/Credits.jsx`): Balance card (∞ for admins), action costs sidebar, promo code input, 4 top-up pack tiles, recent transactions ledger.
- **Admin gating**: `<AdminGate>` wrapper in `App.js`. `/armory`, `/studio`, `/academy` all gated. Non-admins land on `ComingSoon.jsx` with lock icon + waitlist hint. Navbar `CENTER_LINKS_PUBLIC` vs `CENTER_LINKS_ADMIN` branch shows SOON badges to non-admins on Armory/Leaderboard/Academy; admin-only access has the full set unlocked.
- **Verified live**: Backend smoke run pass on all 4 new surfaces (credits/me, promo mint+redeem, newsletter subscribe+list, deploy free+checkout+patch+run). Screenshots confirm ComingSoon page renders for non-admins on `/armory`, Credits page renders with ∞ balance + all 4 packs + promo input + ledger for admin.

### Phase 38 (Jun, 2026) — Custom Photo Avatars for Direct Publish
- **Custom photo upload slot** as the first tile of the Bot Avatar picker in `DirectPublishModal` Step 1: dashed-border upload tile with `UPLOAD` label that swaps to the local image preview (via `URL.createObjectURL`) with a `🗑` remove button. When active, the 12 lucide icons dim to 45% opacity to signal they are overridden, and a "Custom photo active · color tints accents only" hint appears.
- **Live preview card** now renders the uploaded image inside the floating avatar tile (replacing the icon) so creators see exactly how the listing will look before publishing.
- **Persistence wiring**: on `createListing` (Step 2 → Step 3 transition), the file is uploaded via `POST /api/exchange/listings/{id}/upload` with `kind=avatar` immediately after the listing is created, and the listing is re-fetched so subsequent steps see the persisted `avatar_url`.
- **Backend**:
  - `routes/exchange.py` upload endpoint extended — `kind="avatar"` accepted (image/jpeg, image/png, image/webp) with a **2 MB cap** (smaller than the 10 MB photo cap). Prior avatar file is auto-deleted on replacement.
  - `DirectPublishRequest` gets optional `avatar_url` field; persisted on the listing alongside `avatar_icon` + `avatar_color`.
- **Verified live**:
  - Backend smoke: create → upload kind=avatar → listing has `avatar_url` set → URL serves the image → oversized (2.15MB) PNG correctly rejected with `"File exceeds 2MB limit."`
  - Frontend screenshot: custom photo slot first, icons dimmed, photo renders in preview card with purple border + glow
  - Lint + ruff clean

### Phase 37 (Jun, 2026) — DirectPublish "Live Preview" UX Overhaul (cyber-luxury)
- **Two-column live-preview layout** (DirectPublishModal Step 1): left = form, right = sticky `LivePreviewCard` that updates in real-time as the creator types. Modal width grew to `max-w-6xl` on Step 1 (other steps stay `max-w-3xl`).
- **4 new marketplace metadata fields**:
  - **Bot Avatar**: 12 lucide icons (Bot, Zap, Rocket, Brain, Sparkles, Shield, ShoppingBag, Mail, MessageCircle, Database, Code, Globe) + 8-color palette. Selected color propagates as a CSS `--glow` variable to every active field and the preview card border/header.
  - **Required Integrations**: badge multi-select chip grid covering all 15 BYOK services. Selected chips render with avatar-color glow + ✓ icon.
  - **Trigger Type**: 3-tile segmented control (Manual / Webhook / Schedule) with icon + sub-label.
  - **Core Engine**: 4-tile segmented control (Gemini Flash / Gemini Pro / OpenAI BYOK / Claude BYOK) with descriptors.
- **Cyber-luxury aesthetic**:
  - New `.cy-input` class — glassmorphism (rgba 0.02 bg + backdrop-blur 6px), focus state glows in the avatar color via `box-shadow: 0 0 0 1px var(--glow), 0 0 18px var(--glow)`.
  - Pricing inputs use JetBrains Mono with letter-spacing for the "tech-finance" look; **live 80% take-home calc** renders below each price (`$0.40 to you · /run`).
  - Live Preview Card has a radial-gradient header in the avatar color, floating square avatar tile with avatar-color glow ring, formatted category breadcrumb, trigger+engine chips, integration badges (cap 6, overflow `+N`), monospace pricing row, disabled `DEPLOY` button styled in the avatar color.
- **Backend extended** (`routes/exchange.py`): `DirectPublishRequest` gains `avatar_icon`, `avatar_color`, `required_integrations[]`, `trigger_type` (manual|webhook|schedule pattern-validated), `engine` (gemini-flash|gemini-pro|byok-openai|byok-claude pattern-validated). All 5 persisted on `exchange_listings` doc.
- **Verified live**: POST /api/exchange/listings/direct with full payload returns status='draft' + all new fields echoed back; validation 422s on invalid trigger_type and short name. Screenshot confirms full UI renders correctly with purple Rocket avatar propagating glow to all active controls.
- Ruff + eslint all green.

### Phase 36 (Feb, 2026) — BYOK "Test Connection" Probes
- **15 sanity-probe handlers** (`/app/backend/lib/byok_probes.py`, NEW): One read-only API call per service to verify a stored credential is alive without writing data / charging / sending messages — Slack (POST empty payload, expects 400 'no_text'), SendGrid (`/v3/user/profile`), Gmail (`/users/me/profile`), Telegram (`/getMe`), Discord (`GET webhook`), Stripe (`/v1/balance`), Notion (`/users/me`), Google Sheets (`/oauth2/v1/tokeninfo`), Twilio (`/Accounts/{sid}.json`), GitHub (`/user`), OpenAI (`/v1/models`), Anthropic (1-token `/v1/messages` probe with claude-haiku), Instagram (`/me?fields=username`), Postgres (`SELECT version()` via asyncpg), MongoDB (`server_info()` via motor). Each returns `{ok, status_code, detail, latency_ms}`.
- **NEW endpoint `POST /api/workflows/credentials/{service}/test`**: looks up the encrypted credential, decrypts, calls the matching probe, persists `last_probe` (ok/status_code/detail/latency_ms/checked_at) onto the credential doc, and returns the result.
- **`GET /api/workflows/credentials`** now surfaces `last_probe` so the UI can render the LIVE/DEAD/UNTESTED badge without a second roundtrip.
- **`CredentialsVault.jsx` rebuilt**:
  - Per-row **TEST** button (cyan ⚡ icon) → on-click probe with toast and badge refresh
  - **LIVE / DEAD / UNTESTED** status pill beside the service name, tooltip showing probe detail + latency + checked_at
  - Service hint catalog expanded from 3 → 15 entries with exact API key formats (DSN for Postgres, OAuth scope for Sheets, etc.)
  - Subtitle now reads "15 SERVICES" and lists them in the help text.
- **UX polish**: Slack/Discord probes pre-check the URL starts with `https://` for a clearer error than the SSRF guard message.
- **Verified live**: All 12 new probes return precise actionable errors when given fake credentials (`Stripe: Invalid API Key`, `Notion: API token is invalid`, `GitHub: Bad credentials`, `Postgres: Connection failed: invalid DSN`, etc.); ruff + eslint all green.

### Phase 35 (Feb, 2026) — 10 Real Integration Handlers + Exchange Direct-Upload
- **10 real per-service handlers** (`/app/backend/lib/integration_handlers.py`, NEW): Instagram (post/DM via Graph v19), Stripe (charge/refund/subscription/customer), Telegram (sendMessage), Discord (webhook with SSRF guard), Notion (create/update/query, Notion-Version 2022-06-28), Google Sheets (values:append OAuth), Twilio SMS (Messages.json basic auth), GitHub (create_issue/comment/PR/list), OpenAI BYOK chat (gpt-5.4 default), Claude BYOK messages (claude-sonnet-4-6 default), Postgres asyncpg (SELECT-only unless allow_write=true), MongoDB motor (find/insert/update).
- **Dispatcher rewire**: `workflow_handlers.handle_action` now branches by `data.service`; `handle_database` routes postgres/mongodb; `handle_llm` routes by `data.provider` with platform-Gemini fallback. Old "skipped / not_executed_v1=True" pass-through behavior is gone for the 12 wired services — they now return real `ok` or descriptive `error` status.
- **BYOK whitelist expanded** in `routes/workflow_executor.py` and `SUPPORTED_BYOK_SERVICES` from 3 → 15 services. Each accepts POST /api/workflows/credentials with optional `extra` dict (e.g. Twilio `extra: {account_sid, from_number}`, Instagram `extra: {ig_user_id}`).
- **Exchange direct-upload**: NEW endpoint `POST /api/exchange/listings/direct` creates a `bot_projects` record + `exchange_listings` record in a single shot, returning both ids. Accepts files[]/nodes[]/edges[] alongside meta+pricing. Path-traversal sanitization silently drops `..`/absolute paths. Status starts as draft; existing media-upload + auto-promote pipeline still applies.
- **DirectPublishModal.jsx** (NEW): 3-step UI for direct upload from Marketplace — (1) meta+pricing, (2) editable code files with VS-Code-style tabs + "drop from disk" ingest, (3) demo video + photos. Marketplace.jsx gains a `Publish Your Bot` CTA (visible to authenticated users only).
- **Tests**: iter35 → **65/65 backend tests pass** (36 new in `tests/test_workflow_iter35.py` + 29 regression). Zero critical bugs. Verified dispatcher behavior change, BYOK encrypted roundtrip on all 12 new services, path-traversal silent drop, postgres SELECT-only safety, SSRF guard on Discord.

### Phase 34 (Feb, 2026) — 245-Node Catalog · Variable Bot Complexity · BETA Badge · Leaderboard
- **Stripe sandbox keys live**: real `sk_test_51TbehB...` + `pk_test_51TbehB...` written to `backend/.env`. Replaced `sk_test_emergent` placeholder. Verified via `dotenv_values` lookup; supervisor restart applied (shell env var unset to defeat stale override).
- **Variable bot complexity** (`routes/armory_builder.py` BUILDER_SYSTEM_PROMPT): Removed hard-coded "exactly 3 nodes". New scaling rule — simple utility = 3-5 nodes, standard automation = 5-8, multi-service = 8-12, complex multi-branch = 12-25. Bot output now ships up to 7 source files (main.py + handlers.py + utils.py + config.py + requirements.txt + .env.example + README.md) instead of 3. Explicit instruction to include validation, error handling, logging, branching nodes.
- **Catalog expanded 127 → 245**: added Cohere, Mistral, Perplexity, Groq, HuggingFace, Together, Replicate, fal.ai, Runway, Pika, Stability, DeepL, Mailchimp, Klaviyo, ConvertKit, ActiveCampaign, MS Teams, Signal, LINE, WeChat, KakaoTalk, Confluence, Coda, Evernote, OneNote, Todoist, Calendly, Outlook, Miro, Figma, Loom, Copper, Freshdesk, Help Scout, Drift, Front, Close, Apollo, Mastodon, Bluesky, Twitch, Snapchat, Magento, PrestaShop, Gumroad, Paddle, Amazon SP-API, eBay, ClickHouse, Elasticsearch, Pinecone, Qdrant, Weaviate, Chroma, Neo4j, SQLite, Cloudflare, Vercel, Netlify, Heroku, Render, Fly.io, Sentry, Better Stack, Statuspage, Opsgenie, New Relic, CircleCI, GitHub Actions, Terraform, Wise, Plaid, Alchemy, Etherscan, CoinGecko, Dropbox, OneDrive, Box, MEGA, ImageKit, Cloudinary, GA4, Mixpanel, Amplitude, Segment, PostHog, Hotjar, Kafka, RabbitMQ, NATS, AWS SNS, AWS SQS, GCP Pub/Sub, MQTT, Auth0, Clerk, Supabase Auth, 1Password, Bitwarden, Vault, AWS Secrets Manager, SetMultiple, Sort, Deduplicate, Aggregate, SplitInBatches, JSONPath, JMESPath, RenameKeys, Error Handler, Try/Catch, Stop. Search placeholder dynamically reads "Search 245 nodes...".
- **BETA badge** in Navbar next to TaskForce logo (cyan-bordered `BETA` pill).
- **Leaderboard page** (`pages/Leaderboard.jsx`): Coming-soon page with 3 feature tiles (Bots Compiled / Forks Earned / Revenue Share) + placeholder operator scoreboard at 45% opacity. Nav link includes amber "SOON" badge. Route wired at `/leaderboard`.

### Phase 33 (Feb, 2026) — Node Catalog Expansion + Tabbed Code Editor
- **127-node catalog** (`frontend/src/data/nodeCatalog.js`): Expanded from 8 generic types to 127 named integrations across 13 categories (Triggers, Core, AI/LLM, Communication, Productivity, CRM & Sales, Social, E-commerce, Database, Cloud & DevOps, Payments, Files & Storage, Utility). Each catalog entry maps to one of the 8 canonical executor types under the hood (`trigger/llm/condition/action/http_request/webhook/database/transform`) plus a `service` slug so per-service handlers can branch later. Add Node menu redesigned as 420×460 panel with category sidebar + live search filter (filters by label/service/desc/category).
- **Tabbed BotProjectPanel** (`components/BotProjectPanel.jsx`): Replaced left file-tree with VS Code-style horizontal tab bar. One tab per OPEN file (close × per tab, dirty-indicator dot). `+` button opens the full file list as a dropdown — click any file to spawn a new tab. New "minimize" button collapses panel to a 28px vertical strip showing the project name; click strip to re-expand. Monaco editor still drives the code editing.
- **Verified live**: "build me a URL shortener bot" → Gemini 2.5 Pro returns UrlShortener with main.py + requirements.txt + README.md, 3 canvas nodes wired with Lego edges, main.py opens as the active tab.

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

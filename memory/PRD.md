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

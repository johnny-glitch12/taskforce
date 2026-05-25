# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern AI Agent Economy platform "Nova AI" with dark mode aesthetic, Landing Page, Marketplace, Academy, "Nova Studio" IDE (Vibe/Node modes), User Dashboard with sandboxed agent execution, and Private Client Portals. Full FastAPI/MongoDB backend with JWT auth, Stripe payments, RestrictedPython sandboxing, and client isolation.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Shadcn UI, Context API
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler, RestrictedPython
- **Database**: MongoDB (users, waitlist, agents, creators, reviews, workflows, password_resets, payment_transactions, user_agents, agent_executions, csdrop_executions)
- **Payments**: Stripe via emergentintegrations (test mode)
- **Sandbox**: RestrictedPython v8 + signal timeout + import whitelist

## All Implemented Features

### Core Platform
- Home page with waitlist CTA + social proof counter
- Marketplace with search, category pills, trending agents, faceted search API
- Agent Detail pages with live demo + Stripe Rent/Buy checkout
- Creator Profile pages
- Academy placeholder
- Premium dark-mode purple aesthetic with glassmorphism

### Authentication & Auth
- JWT authentication (login, register, forgot-password, reset-password)
- Role-based access: admin, user, client
- Client-specific auth guards (client_id isolation)
- Auto-redirect by role (csdrop → /dashboard/csdrop)

### Nova Studio IDE
- Draggable n8n-style node canvas with pan/zoom (0.3x–2.5x)
- 8 node types: trigger, llm, condition, action, http_request, webhook, database, transform
- Vibe Mode chat (pattern-matching simulator)
- Code pane with JSON output + Compliance Linter (trust score 0-100)
- Workflow CRUD with auto-save (2s debounce)
- Full mobile optimization (3-tab toggle on iPhone)

### User Dashboard
- Agent deployment with code editor, env vars, trigger selection
- 3 starter templates (Echo Bot, Data Cruncher, JSON Transformer)
- Manual execution with JSON input + result display
- Webhook triggers (unique URL per agent)
- Execution history with logs
- Tier system: Free (3 agents), Pro (unlimited)

### Stripe Payments
- Checkout session creation for Agent Rent/Buy
- Payment status polling + webhook handling
- Payment Success page

### Phase 6 - CSDROP Private Client Portal
1. Client Authentication: admin@csdrop.com / nova_csdrop_2026, role=client, client_id=csdrop, tier=pro
2. Client Isolation: get_csdrop_user auth guard blocks ALL non-csdrop users (403)
3. Custom Branding: Deep Indigo (#6366f1) + Cyan (#06b6d4) theme
4. Code Execution Panel: Python editor with sandboxed execution (RestrictedPython)
5. Sovereign Bot Controls: Launch/Stop sovereign.py via subprocess
6. CSDROP Agent CRUD: Create (limit 10), delete, run agents — all isolated
7. Execution History: Separate csdrop_executions collection

### Phase 7 - Environment Manager
1. Health Check API (GET /api/csdrop/health)
2. Auto-Repair API (POST /api/admin/repair)
3. Repair Status API (GET /api/admin/repair-status)
4. Pre-Flight Check on bot launch
5. Frontend System Health Panel

### Phase 8 - Live Satellite Feed
1. Bot Screenshot Capture to /app/backend/static/live_stream.jpg
2. Image Endpoint (GET /api/csdrop/live-feed/image)
3. Feed Status Endpoint (GET /api/csdrop/live-feed)
4. Frontend Live Satellite Feed Panel with auto-refresh

### Phase 9 - Remote Session Sync / QR Login
1. sovereign.py --login mode: QR code capture for Discord headless login
2. Sync Session API (POST /api/csdrop/sync-session)
3. Sync Status API (GET /api/csdrop/sync-status)
4. Sync Stop API (POST /api/csdrop/sync-stop)
5. QR Image Endpoint (GET /api/csdrop/sync-qr)
6. Frontend Sync Modal with live QR, countdown, and auto-close on success

### Phase 10 - Bot Path Hardening & Debug Mode
1. Absolute pathing in sovereign.py (BOT_DIR = Path(__file__).resolve().parent)
2. headless=True fix for server environments
3. Boot diagnostics and database pulse check
4. Demo mode (--demo flag) for testing
5. Cycle error handling + CLI arg parsing

### Phase 11 - Manual Credential Bridge with 2FA (Complete - April 6, 2026)
1. **Backend Endpoints**: POST /api/csdrop/manual-login (spawns sovereign.py --manual, writes creds to manual_creds.json), POST /api/csdrop/submit-2fa (writes code to 2fa_signal.txt)
2. **sovereign.py --manual mode**: Reads email/password from manual_creds.json, types into Discord, detects 2FA challenges, polls 2fa_signal.txt for code, submits verification, saves session on success
3. **Sync Status Enhancement**: GET /api/csdrop/sync-status now returns needs_2fa, login_failed fields + status values: idle, syncing, 2fa_required, success, timeout, login_failed
4. **Frontend SyncSessionModal**: Extracted from CsdropDashboard.jsx into separate SyncSessionModal.jsx. Two tabs: "QR Code" (original) and "Manual Login" (new). Manual tab features email/password form, password visibility toggle, security note, 2FA code input (numeric only, 4-8 digits), polling at 2s for challenge detection, auto-close on success.
5. **Component Extraction**: CsdropDashboard.jsx reduced from 1048 → 786 lines by extracting SyncSessionModal into its own file.

### Phase 12 - Bot Strike Hardening (Complete - April 6, 2026)
1. **Scope Bug Fix**: Fixed `page` → `self.page` in PredatorEngine error-handling blocks (was causing NameError crashes during screenshot capture)
2. **URL Verification**: `human_search_and_click()` now verifies `/channels/` is in the URL after search to confirm the bot actually landed on a DM page
3. **Robust Selectors**: Updated textbox selector from `div[role="textbox"]` to `[role="textbox"], [aria-label*="Message"]` using Playwright Locator API across hammer_check, hook_strike, and _verify_message_sent
4. **Pre-Strike Sidebar Wait**: Added `wait_for_selector('div[class*="searchBar"], a[aria-label="Direct Messages"]')` before each strike to ensure Discord UI is loaded
5. **Error Recovery**: New `_dismiss_modals()` helper presses Escape twice to close stuck User Profile popups. Called after every failed search, failed strike, and between successful targets

### Phase 13 - Cycle Timeout Diagnostics (Complete - April 6, 2026)
1. **Snapshot on Cycle Error**: `PlaywrightTimeout` is caught separately from generic exceptions. On timeout, immediately saves screenshot to `/app/backend/static/cycle_timeout_debug.jpg`. Generic exceptions also capture a screenshot.
2. **Network Monitoring**: After `page.goto()`, logs the HTTP status code and status text (e.g., `[DEBUG] Discord Load Status: 200 OK`). If status >= 400, saves screenshot and skips cycle.
3. **Increased Timeout + Console Listener**: Discord load timeout increased from 45s to 60s. Added `page.on("console")` listener that prints all `error` and `warning` console messages from Discord's JS.
4. **Proxy Health Test**: Before each cycle, uses `requests.get` through the proxy to `httpbin.org/ip` (15s timeout). Logs external IP on success. On failure, logs `[ERROR] Proxy connection failed`, skips the cycle, and waits 60s.
5. **Timeout Screenshot Endpoint**: `GET /api/csdrop/cycle-timeout` serves the saved timeout screenshot (no auth, for `<img src>` usage).

## Testing Status
- Iteration 15: 100% backend (14/14), 100% frontend (Manual Credential Bridge + regression)
- Iteration 14: 100% backend (8/8), 100% frontend (Ghost Striking fixes + all regression)
- Iteration 13: 100% backend (14/14), 100% frontend (Real-Time Log Stream)
- Iteration 12: 100% backend (19/19), 100% frontend (Session Sync)
- Test files: /app/test_reports/iteration_1.json through iteration_15.json

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Stripe: sk_test_emergent (test mode)

## Known Mocks
- Studio Vibe chat: pattern matcher (not real LLM)
- Stripe: test/sandbox mode
- Pro upgrade button: UI only

### Phase 14 - Vibe Chat → Real Agent Execution (nidoai Architecture) (Complete - May 25, 2026)
1. **Agent Execution Engine** (`/app/backend/routes/agent.py`): Created `POST /api/run-agent` endpoint matching nidoai's `route.ts` pattern — validates input, creates `agent_logs` document, fires background worker, returns `{success, logId}`
2. **Agent Worker** (replaces nidoai's Inngest `agentWorker.ts`): Gemini orchestration via Emergent LLM key (`gemini-2.5-flash`), runs as FastAPI BackgroundTask, writes timestamped entries to `terminal_history` array, status transitions: queued → processing → success/failed
3. **Polling Endpoint** (`GET /api/agent-logs/{logId}`): Replaces nidoai's Supabase Realtime `useAgentTerminal` hook with 1.5s polling — returns full execution log including status, terminal_history, output_result
4. **Frontend ChatPane Rewrite**: Wired Submit button to POST /api/run-agent, added "Agent Thinking..." badge, "Agent executing..." bubble, disabled input during processing, auto-renders response on completion
5. **Agent Terminal UI**: Embedded terminal in chat pane with color-coded logs (green=success, red=error, purple=processing, blue=init), status dot indicator, auto-scroll
6. **Architecture Note**: Used MongoDB `agent_logs` collection (Supabase PostgreSQL was unreachable). Data model matches nidoai schema exactly — swappable when Supabase credentials are available

## Key API Endpoints (Updated)
- POST /api/run-agent — Start agent execution (returns logId)
- GET /api/agent-logs/{logId} — Poll execution status + terminal history
- POST /api/csdrop/manual-login — Start manual Discord login with email/password
- POST /api/csdrop/submit-2fa — Submit 2FA/verification code to bot
- GET /api/csdrop/sync-status — Poll sync status (includes needs_2fa, login_failed)
- POST /api/csdrop/sync-session — Start QR code sync
- POST /api/csdrop/sync-stop — Cancel sync process
- GET /api/csdrop/sync-qr — Serve QR screenshot
- GET /api/csdrop/health — Check bot dependencies
- POST /api/admin/repair — Trigger background repair
- GET /api/csdrop/live-feed — Feed status
- GET /api/csdrop/live-feed/image — Raw screenshot

## Prioritized Backlog
- **P1**: Academy course content
- **P1**: Real LLM integration for Studio Vibe Mode
- **P2**: Hosted execution runtime (Celery + Redis)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control
- **P3**: Pro tier Stripe subscription
- **P3**: Refactor server.py into modular routers

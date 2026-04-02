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

### Phase 6 - CSDROP Private Client Portal (Complete - March 26, 2026)
1. **Client Authentication**: admin@csdrop.com / nova_csdrop_2026, role=client, client_id=csdrop, tier=pro
2. **Client Isolation**: get_csdrop_user auth guard blocks ALL non-csdrop users (403)
3. **Custom Branding**: Deep Indigo (#6366f1) + Cyan (#06b6d4) theme, NOT purple
4. **Code Execution Panel**: Python editor with sandboxed execution (RestrictedPython), INPUT/ENV/RESULT interface, 30s timeout
5. **Sovereign Bot Controls**: Launch/Stop sovereign.py via subprocess, Promo Link + Batch Size config, Live Logs terminal with 2s polling
6. **CSDROP Agent CRUD**: Create (limit 10), delete, run agents — all isolated to csdrop user
7. **Execution History**: Separate csdrop_executions collection, timestamped logs

### Phase 7 - Environment Manager (Complete - March 26, 2026)
1. **Health Check API** (`GET /api/csdrop/health`): Verifies playwright, playwright_stealth, RestrictedPython modules + Chromium browser. Returns `ready` boolean + `python_path` (sys.executable)
2. **Auto-Repair API** (`POST /api/admin/repair`): Runs `pip install -r requirements.txt` + `playwright install chromium` via FastAPI BackgroundTasks. Non-blocking, 2-3 min runtime.
3. **Repair Status API** (`GET /api/admin/repair-status`): Polls background repair progress and logs
4. **Pre-Flight Check**: `/api/csdrop/launch` rejects bot start if dependencies missing
5. **sys.executable Fix**: Bot launcher uses `sys.executable` instead of hardcoded `python3` for venv compatibility
6. **Startup Auto-Repair**: On server boot, checks all deps + chromium. If anything is missing, auto-triggers repair in a background thread — dashboard is green before any client logs in.
7. **Frontend System Health Panel**: Shows green/red indicators for all 4 deps + "Repair Environment" button when unhealthy
8. **UI Safety**: Launch button replaced with "Env Not Ready" warning when deps missing
9. **Bot-specific requirements.txt** at `/app/backend/clients/csdrop/requirements.txt` (includes setuptools<82 pin)
10. **sovereign.py Stealth Fix**: Changed `from playwright_stealth import Stealth` → `stealth_async` (function-based API matches installed library version)

### Phase 8 - Live Satellite Feed (Complete - March 26, 2026)
1. **Bot Screenshot Capture**: `sovereign.py` saves JPEG screenshots to `/app/backend/static/live_stream.jpg` at 5+ key action points (after stealth init, after each scan, after each strike, after lurking)
2. **Image Endpoint** (`GET /api/csdrop/live-feed/image`): Serves the latest screenshot as JPEG with no-cache headers. No auth required (for `<img src>` usage). Returns 404 if no screenshot exists.
3. **Feed Status Endpoint** (`GET /api/csdrop/live-feed`): Returns `{available, bot_running, last_updated}`. Requires CSDROP auth.
4. **Frontend Live Satellite Feed Panel**: Rendered in the Sovereign Bot tab. Auto-refreshes image every 5 seconds when bot is running. Shows REC indicator + scanline overlay when active. Shows placeholder with Monitor icon when bot is off.
5. **Static Files Mount**: FastAPI serves `/static/` directory for the screenshot files.

### Phase 9 - Remote Session Sync / QR Login (Complete - March 26, 2026)
1. **sovereign.py `--login` Mode**: `login_mode()` function opens Discord login page in headless Chromium, captures QR code screenshots every 2 seconds to `/app/backend/static/qr_sync.jpg`, waits for URL change to `/channels` (successful scan), saves `context.storage_state()` as `discord_session.json`. 2-minute timeout auto-kills.
2. **Sync Session API** (`POST /api/csdrop/sync-session`): Spawns sovereign.py with `--login` flag. Requires CSDROP auth. Rejects if bot is running or sync already in progress. Pre-flight check for playwright.
3. **Sync Status API** (`GET /api/csdrop/sync-status`): Returns `{status, qr_available, logs, session_exists, session_last_updated}`. Status values: idle, syncing, success, timeout, finished.
4. **Sync Stop API** (`POST /api/csdrop/sync-stop`): Kills sync process, cleans up QR file. Requires CSDROP auth.
5. **QR Image Endpoint** (`GET /api/csdrop/sync-qr`): Serves QR screenshot as JPEG with no-cache headers. No auth (for `<img src>` usage).
6. **Frontend Sync Modal**: "Sync Session" button in Sovereign Bot tab opens a full-screen modal with: live QR code display (refreshes every 2s), LIVE indicator + countdown timer, sync logs, Cancel/Start/Done buttons, success/timeout state screens with appropriate messaging.
7. **Bug Fix (March 26)**: Fixed screenshot path (`Path(__file__).parent.parent` → absolute `/app/backend/static`), added `flush=True` for real-time log streaming, added loading spinner UI with phase indicators ("Starting Chromium" → "Loading Discord" → "Rendering QR").

### Phase 10 - Bot Path Hardening & Debug Mode (Complete - April 2, 2026)
1. **Absolute Pathing**: All paths in sovereign.py now use `BOT_DIR = Path(__file__).resolve().parent` for DB, session, and screenshots. No more relative paths.
2. **headless=True Fix**: Changed `headless=False` → `headless=True` in the main loop. The bot was crashing on headless servers because there's no display.
3. **Boot Diagnostics**: On startup, bot prints full path verification (DB exists, session exists, screenshot dir exists), database target breakdown by status, promo link, and batch size.
4. **Database Pulse Check**: Before each strike, bot logs `[DEBUG] Database Found. Pending targets in queue: {count}`. If count is 0, prints `[!] CRITICAL: Database is empty. Scrape targets before starting strike.` and aborts.
5. **Demo Mode** (`--demo` flag): If the database is empty, run with `--demo` to send one test message to a hardcoded Discord ID, proving Playwright hands are working.
6. **Cycle Error Handling**: Added try/except around each cycle so one failure doesn't crash the infinite loop.
7. **CLI Arg Parsing**: Bot properly parses promo link and batch size from sys.argv, compatible with the server.py Popen call.

## Testing Status
- Iteration 14: 100% backend (8/8), 100% frontend (Ghost Striking fixes + all regression)
- Iteration 13: 100% backend (14/14), 100% frontend (Real-Time Log Stream)
- Iteration 12: 100% backend (19/19), 100% frontend (Session Sync)
- Test files: /app/test_reports/iteration_1.json through iteration_14.json

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Stripe: sk_test_emergent (test mode)

## Known Mocks
- Studio Vibe chat: pattern matcher (not real LLM)
- Stripe: test/sandbox mode
- Pro upgrade button: UI only

## Key API Endpoints (Environment Manager + Live Feed)
- `GET /api/csdrop/health` — Check all bot dependencies (any Bearer token)
- `POST /api/admin/repair` — Trigger background dependency installation (no auth)
- `GET /api/admin/repair-status` — Poll repair progress and logs (no auth)
- `GET /api/csdrop/live-feed` — Feed status: available, bot_running, last_updated (csdrop auth)
- `GET /api/csdrop/live-feed/image` — Raw JPEG screenshot, no-cache headers (no auth)

## Prioritized Backlog
- **P1**: Real LLM integration for Studio Vibe Mode
- **P1**: Academy course content
- **P2**: Hosted execution runtime (Celery + Redis)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control
- **P3**: Pro tier Stripe subscription
- **P3**: Refactor server.py into modular routers

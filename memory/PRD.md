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
6. **Startup Health Check**: Server logs dependency status on boot with warnings for missing modules
7. **Frontend System Health Panel**: Shows green/red indicators for all 4 deps + "Repair Environment" button when unhealthy
8. **UI Safety**: Launch button replaced with "Env Not Ready" warning when deps missing
9. **Bot-specific requirements.txt** at `/app/backend/clients/csdrop/requirements.txt`

## Testing Status
- Iteration 10: 100% backend (12/12), 100% frontend (all Environment Manager flows)
- Iteration 9: 100% backend (26/26), 100% frontend (all CSDROP + main app flows)
- Test files: /app/test_reports/iteration_1.json through iteration_10.json

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Stripe: sk_test_emergent (test mode)

## Known Mocks
- Studio Vibe chat: pattern matcher (not real LLM)
- Stripe: test/sandbox mode
- Pro upgrade button: UI only

## Key API Endpoints (Environment Manager)
- `GET /api/csdrop/health` — Check all bot dependencies (any Bearer token)
- `POST /api/admin/repair` — Trigger background dependency installation (no auth)
- `GET /api/admin/repair-status` — Poll repair progress and logs (no auth)

## Prioritized Backlog
- **P1**: Real LLM integration for Studio Vibe Mode
- **P1**: Academy course content
- **P2**: Hosted execution runtime (Celery + Redis)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control
- **P3**: Pro tier Stripe subscription
- **P3**: Refactor server.py into modular routers

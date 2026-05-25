# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern AI Agent Economy platform "Nova AI" with dark mode aesthetic, Landing Page, Marketplace, Academy, "Nova Studio" IDE (Vibe/Node modes), User Dashboard with sandboxed agent execution, and Private Client Portals. Full FastAPI/MongoDB backend with JWT auth, Stripe payments, RestrictedPython sandboxing, and client isolation.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Shadcn UI, Context API, ThemeProvider (light/dark)
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler, RestrictedPython
- **Database**: MongoDB (users, waitlist, agents, creators, reviews, workflows, password_resets, payment_transactions, user_agents, agent_executions, csdrop_executions) + Supabase (agent_logs, security_events)
- **Payments**: Stripe via emergentintegrations (test mode)
- **Sandbox**: RestrictedPython v8 + signal timeout + import whitelist
- **LLM**: Gemini 2.5 Flash via Emergent LLM Key

## All Implemented Features

### Core Platform
- Home page with waitlist CTA + social proof counter
- Marketplace with search, category pills, trending agents, faceted search API, creator spotlight cards
- Agent Detail pages with live demo + Stripe Rent/Buy checkout
- Creator Profile pages
- Academy with interactive course cards (4 courses), video placeholders, code playground
- Premium dark-mode purple aesthetic with glassmorphism

### Global Theme System (Phase 16 - May 25, 2026)
- Light/Dark mode toggle with auto-detect from system preference
- ThemeProvider context in `/app/frontend/src/lib/theme.js`
- CSS variables for all theme tokens in App.css (--bg-primary, --text-primary, --border, etc.)
- Theme utility classes: t-bg, t-text, t-text-sub, t-text-mute, t-card, t-input, t-border, t-orb
- Toggle button in Navbar (Sun/Moon icons) with localStorage persistence
- Applied across: Home, Academy, Marketplace, Login, Dashboard, SecurityDashboard, Footer, Navbar

### Security Audit Dashboard (Phase 16 - May 25, 2026)
- `security_events` Supabase table logs all firewall verdicts
- `log_security_event()` called from agent route after every firewall audit
- `GET /api/security/stats` - Aggregated counts (total, safe, suspicious, unsafe, blocked) - Admin only
- `GET /api/security/events` - Event list with verdict filter, 200 max limit - Admin only
- SecurityDashboard UI at `/security` route: stat boxes, filter pills, expandable event rows
- Admin-only nav link in Navbar

### Authentication & Auth
- JWT authentication (login, register, forgot-password, reset-password)
- Role-based access: admin, user, client
- Client-specific auth guards (client_id isolation)
- Auto-redirect by role (csdrop -> /dashboard/csdrop)

### Nova Studio IDE
- Draggable n8n-style node canvas with pan/zoom (0.3x-2.5x)
- 8 node types: trigger, llm, condition, action, http_request, webhook, database, transform
- Vibe Mode chat connected to Gemini 2.5 Flash via Emergent LLM key
- Live Agent Terminal with Supabase Realtime streaming
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

### CSDROP Private Client Portal (Phase 6-13)
- Client Authentication with client_id isolation
- Custom Branding (Deep Indigo + Cyan theme)
- Sovereign Bot Controls (Launch/Stop)
- Manual Login with 2FA support
- Live Satellite Feed with auto-refresh
- QR Code Sync for Discord headless login
- Cycle Timeout Diagnostics with Proxy Health Testing
- Bot Strike Hardening (5 bug fixes)

### Agent Execution Engine (Phase 14)
- Supabase-backed agent_logs with Realtime streaming
- Gemini 2.5 Flash LLM via Emergent LLM Key
- useAgentTerminal hook for live terminal updates
- Background task worker with timestamped history

### Security Hardening (Phase 15)
- Semantic Firewall (Gemini Flash prompt auditing)
- Rate Limiting (5 req/min per user)
- Concurrent Execution Cap (1 active per user)
- SSRF Protection (blocks private IPs, dangerous ports, DNS rebinding)
- Gate Order: Rate Limit -> Concurrent Cap -> Firewall -> Execute

## Testing Status
- Iteration 19: 100% backend (7/7 security), 100% frontend (all theme/UI flows verified)
- Iteration 15-18: 100% on all previous features
- Test files: /app/test_reports/iteration_1.json through iteration_19.json

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Stripe: sk_test_emergent (test mode)

## Key API Endpoints
- POST /api/run-agent — Start agent execution (returns logId)
- GET /api/agent-logs/{logId} — Poll execution status + terminal history
- GET /api/security/stats — Aggregated security stats (admin only)
- GET /api/security/events — Security event list with filters (admin only)
- POST /api/csdrop/manual-login — Start manual Discord login
- POST /api/csdrop/submit-2fa — Submit 2FA code
- GET /api/csdrop/sync-status — Poll sync status
- GET /api/csdrop/health — Bot health check

## Prioritized Backlog
- **P1**: Save Node Coding manifest JSON to Supabase agents table
- **P2**: Creator dashboard with advanced analytics
- **P2**: Agent version control system
- **P3**: Hosted execution runtime (Celery + Redis)
- **P3**: Pro tier Stripe subscription
- **P3**: Refactor server.py into modular routers (Auth, CSDROP, Stripe)

## Known Mocks
- Node Coding JSON output saving (currently only displays in UI, needs to save to DB)
- Stripe: test/sandbox mode
- Pro upgrade button: UI only

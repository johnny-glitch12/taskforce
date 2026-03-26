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

## Testing Status
- Iteration 9: 100% backend (26/26), 100% frontend (all CSDROP + main app flows)
- Test files: /app/test_reports/iteration_1.json through iteration_9.json

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026
- Stripe: sk_test_emergent (test mode)

## Known Mocks
- Studio Vibe chat: pattern matcher (not real LLM)
- Stripe: test/sandbox mode
- Pro upgrade button: UI only
- Sovereign bot: requires playwright (not in sandbox env)

## Prioritized Backlog
- **P1**: Real LLM integration for Studio Vibe Mode
- **P1**: Academy course content
- **P2**: Hosted execution runtime (Celery + Redis)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control
- **P3**: Pro tier Stripe subscription

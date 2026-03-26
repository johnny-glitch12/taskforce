# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern, minimalistic, and highly responsive web application for "Nova AI" — an AI Agent Economy platform. Features include dark mode aesthetic (pitch-black backgrounds, white text, neon violet/electric purple accents), a Landing Page with waitlist CTA, Marketplace for Agent Cards, Academy, and "Nova Studio" split-pane IDE (Vibe Mode chat + Node Mode visual builder). Full FastAPI/MongoDB backend with real JWT auth.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Shadcn UI, Context API
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler
- **Database**: MongoDB (collections: users, waitlist, agents, creators, reviews, workflows, password_resets, payment_transactions)
- **Payments**: Stripe via emergentintegrations library (test mode)

## What's Been Implemented

### Phase 1 - UI Foundation (Complete)
- Home page with hero, waitlist CTA, gradient orbs, waitlist counter social proof
- Marketplace with search, category pills, trending agents, creator spotlight
- Agent Detail pages with live demo modal, Stripe Rent/Buy checkout
- Creator Profile pages with portfolio grid
- Academy placeholder
- Premium dark-mode purple aesthetic with glassmorphism

### Phase 2 - Backend Foundation (Complete)
- FastAPI server with JWT authentication (login, register, forgot-password, reset-password)
- MongoDB seeding (6 agents, 5 creators, reviews, waitlist entries)
- Full CRUD for all entities
- Compliance Linter Engine (POST /api/linter/scan)
- Marketplace Search Engine (GET /api/agents/search) with faceted search
- Supernova Engine (APScheduler cron)
- Agent Export (POST /api/agents/{id}/export)

### Phase 3 - Full-Stack Features (Complete - March 26, 2026)
1. User Registration — Signup UI + POST /api/auth/register
2. Password Reset — Full flow with token generation and validation
3. Waitlist Counter — GET /api/waitlist/count + Home page social proof
4. Nova Studio Backend — Full CRUD for workflows, auto-save with 2s debounce
5. Compliance Linter — Detects API key exposure, prompt injection, blacklisted domains, PII risks
6. Marketplace Search — Faceted search with aggregation pipeline, creator data lookup
7. Agent Export — Standardized workflow JSON for n8n/LangChain
8. Supernova Engine — 24h cron evaluates creators for badge eligibility

### Phase 4 - Canvas Overhaul + Mobile + Stripe (Complete - March 26, 2026)
1. **Draggable Node Canvas** — Mouse/touch drag to reposition nodes freely, pan canvas by dragging background, scroll-wheel zoom (0.3x-2.5x), zoom in/out/reset buttons, 8 node types (trigger, llm, condition, action, http_request, webhook, database, transform), auto-connect edges, connection dots on hover, SVG bezier curve edges
2. **Full Mobile Optimization** — Studio: 3-tab mode toggle (Vibe/Node/Code) on mobile with single pane display; All pages: responsive grids, stacked layouts, touch-friendly; Navbar: hamburger menu
3. **Stripe Payment Integration** — Real Stripe checkout for Agent Rent/Buy, payment_transactions collection, checkout session creation, status polling, webhook handling, Payment Success page with polling UI

## Testing Status
- Iteration 7: 100% backend (30/30 tests), 100% frontend (all flows)
- Test files: /app/test_reports/iteration_1.json through iteration_7.json

## Known Mocks
- Studio Vibe Mode chat uses a local pattern-matching simulator (not real LLM)
- Stripe uses test key (sk_test_emergent) — real checkout sessions but sandbox mode

## Credentials
- Admin: admin@nova.ai / admin123
- Stripe: sk_test_emergent (test mode)

## Prioritized Backlog
- **P1**: Real LLM integration for Studio Vibe Mode (GPT-5.2/Claude)
- **P1**: Academy course content
- **P2**: Hosted execution runtime (Celery + Redis for async agent runs)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control

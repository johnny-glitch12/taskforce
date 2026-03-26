# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern, minimalistic, and highly responsive web application for "Nova AI" — an AI Agent Economy platform. Features include dark mode aesthetic (pitch-black backgrounds, white text, neon violet/electric purple accents), a Landing Page with waitlist CTA, Marketplace for Agent Cards, Academy, and "Nova Studio" split-pane IDE (Vibe Mode chat + Node Mode visual builder). Requires FastAPI/MongoDB backend with real JWT auth.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Shadcn UI, Context API
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler
- **Database**: MongoDB (collections: users, waitlist, agents, creators, reviews, workflows, password_resets)

## What's Been Implemented

### Phase 1 - UI Foundation (Complete)
- Home page with hero, waitlist CTA, gradient orbs
- Marketplace with search, category pills, trending agents
- Agent Detail pages with live demo modal
- Creator Profile pages
- Academy placeholder
- Nova Studio IDE with Vibe/Node mode toggle
- Premium dark-mode purple aesthetic with glassmorphism

### Phase 2 - Backend Foundation (Complete)
- FastAPI server with JWT authentication
- MongoDB seeding (6 agents, 5 creators, reviews)
- User login, token validation, protected routes
- Marketplace API wiring (real data from MongoDB)

### Phase 3 - Full-Stack Features (Complete - March 26, 2026)
1. **User Registration** — Signup form UI + POST /api/auth/register. Any user can register and access Studio.
2. **Password Reset Flow** — POST /api/auth/forgot-password generates reset token, POST /api/auth/reset-password validates and updates. Full UI with token display (demo mode).
3. **Waitlist Counter** — GET /api/waitlist/count public endpoint + "X on the waitlist" social proof badge on Home hero.
4. **Nova Studio Backend Wiring** — Full CRUD for workflows (create, list, get, update, delete). Auto-save with 2s debounce. Workflow selector dropdown. Chat messages persist. Nodes/edges persist. Code JSON auto-generated.
5. **Compliance Linter Engine** — POST /api/linter/scan detects: exposed API keys, prompt injection vulnerabilities, blacklisted domains, unencrypted HTTP endpoints, PII transmission risks, orphan nodes. Returns trust score (0-100), status (certified/flagged/rejected), detailed flags.
6. **Marketplace Search Engine** — GET /api/agents/search with faceted search: text query, category filter, min trust score, sort options (trending/price/newest/rating/trust), pagination with offset/limit. Aggregation pipeline with creator data lookup.
7. **Agent Export** — POST /api/agents/{id}/export returns standardized workflow JSON for n8n/LangChain import.
8. **Supernova Engine** — APScheduler cron (24h interval) evaluates creators: total_deploys >= 500, avg_rating >= 4.7, avg_trust >= 90, total_reviews >= 50. Auto-awards is_supernova badge.

## Testing Status
- Iteration 6: 100% backend (32/32 tests), 100% frontend
- Test file: /app/backend/tests/test_nova_api.py

## Known Mocks
- Studio Vibe Mode chat uses a local pattern-matching simulator (generateAssistantResponse), NOT a real LLM. Responds to keywords like "refund", "sales", "escalation", "api" to auto-create nodes.

## Credentials
- Admin: admin@nova.ai / admin123
- Test user: test@example.com / newpassword123

## Prioritized Backlog
- **P1**: Academy course content (placeholder exists)
- **P2**: Stripe payment integration for Rent/Buy buttons
- **P2**: Real LLM integration for Studio Vibe Mode chat
- **P3**: Hosted execution runtime (Celery + Redis for async agent execution)

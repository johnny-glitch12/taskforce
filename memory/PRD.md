# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern, minimalistic web app for "Nova AI" — an AI Agent Economy platform. Dark mode aesthetic with purple accents, Landing Page with waitlist, Marketplace, Academy, "Nova Studio" IDE with Vibe/Node modes, User Dashboard with sandboxed agent execution. Full FastAPI/MongoDB backend with JWT auth, Stripe payments, and RestrictedPython sandboxing.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Shadcn UI, Context API
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler, RestrictedPython
- **Database**: MongoDB (collections: users, waitlist, agents, creators, reviews, workflows, password_resets, payment_transactions, user_agents, agent_executions)
- **Payments**: Stripe via emergentintegrations (test mode)
- **Sandbox**: RestrictedPython v8 + signal timeout + import whitelist

## What's Been Implemented

### Phase 1 - UI Foundation (Complete)
- Home, Marketplace, Agent Detail, Creator Profile, Academy, Studio IDE
- Premium dark-mode purple aesthetic with glassmorphism

### Phase 2 - Backend Foundation (Complete)
- FastAPI with JWT auth, MongoDB seeding, Marketplace API, Compliance Linter

### Phase 3 - Full-Stack Features (Complete)
- Registration, Password Reset, Waitlist Counter, Studio Backend, Search Engine, Agent Export, Supernova Engine

### Phase 4 - Canvas + Mobile + Stripe (Complete)
- Draggable n8n-style node canvas with pan/zoom
- Full mobile/iPhone optimization across all pages
- Stripe checkout for Agent Rent/Buy

### Phase 5 - Dashboard & Sandboxed Execution (Complete - March 26, 2026)
1. **User Dashboard** — /dashboard page showing agent count/limit progress bar, total runs, purchased agents, tier badge
2. **Custom Agent Deployment** — Modal with name, description, Python code editor, env vars (key/value), trigger type (manual/webhook/both), 3 starter templates
3. **RestrictedPython Sandbox** — Executes user code in locked environment:
   - Whitelisted imports only: json, math, re, datetime, collections, random, string, hashlib, base64
   - Blocked: os, sys, subprocess, socket, shutil + 30 more dangerous modules
   - Blocked patterns: eval, exec, open, __import__, getattr, setattr, delattr, globals, locals
   - Import validation at creation time AND runtime (double-layer security)
   - 30s timeout via SIGALRM, 50K char output limit
   - INPUT dict receives trigger payload, ENV dict receives configured env vars, RESULT variable returns output
   - print() captured via RestrictedPython PrintCollector factory
4. **Manual Execution** — Run button opens modal with JSON input, shows success/error/output/RESULT
5. **Webhook Triggers** — Each agent gets unique webhook URL (POST /api/webhook/agent/{key}), callable from Zapier/Discord/external apps
6. **Execution History** — Logs per agent showing trigger type, success, duration, result, timestamp
7. **Tier System** — Free: 3 agents, Pro: unlimited. Purple upgrade banner at limit.
8. **Agent Lifecycle** — Enable/Disable toggle, Delete, Show/Hide code

## Testing Status
- Iteration 8: 100% backend (31/31), 100% frontend
- Critical security fix: Import validation added at agent creation time

## Known Mocks
- Studio Vibe chat: pattern-matching simulator (not real LLM)
- Stripe: test key (sk_test_emergent, sandbox mode)
- Pro upgrade button: UI only

## Credentials
- Admin: admin@nova.ai / admin123
- Stripe: sk_test_emergent

## Prioritized Backlog
- **P1**: Real LLM integration for Studio Vibe Mode
- **P1**: Academy course content
- **P2**: Hosted execution runtime (Celery + Redis for async long-running agents)
- **P2**: Creator dashboard with analytics
- **P3**: Agent version control
- **P3**: Pro tier payment (Stripe subscription for unlimited agents)

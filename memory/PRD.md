# Task Force AI - Product Requirements Document

## Original Problem Statement
Build "Task Force AI" — a tactical, enterprise-grade AI agent execution economy platform. Features: Landing Page, The Exchange (marketplace), Task Force Academy, "The Armory" split-pane IDE with "Command Prompt" (LLM chat) and "Node Coding" (visual graph). Full-stack FastAPI/React with Supabase, Stripe, Gemini LLM integration.

## Architecture
- **Frontend**: React SPA, React Router, Tailwind CSS, Framer Motion, Shadcn UI, ThemeProvider (light/dark)
- **Backend**: FastAPI, Passlib/Bcrypt, python-jose (JWT), Motor (async MongoDB), APScheduler, RestrictedPython
- **Database**: MongoDB (users, waitlist, agents, creators, workflows, etc.) + Supabase (agent_logs, security_events, published_agents)
- **Payments**: Stripe via emergentintegrations (test mode, no crypto integration)
- **LLM**: Gemini 2.5 Flash via Emergent LLM Key
- **Design System**: Tactical Cyan (#22d3ee) + Terminal Green (#10b981), JetBrains Mono/Rajdhani/Inter fonts, hard-edge borders (rounded-sm), deep matte black backgrounds

## Global Glossary
- Company: Task Force AI
- IDE: The Armory (was Nova Studio)
- Chat Builder: Command Prompt (was Vibe Coder)
- Marketplace: The Exchange
- Education: Task Force Academy
- Entity: TASK FORCE AI DEVELOPMENT SERVICES L.L.C.

## All Implemented Features

### Global Rebrand (Phase 20 - May 25, 2026)
- Full A-Z text replacement: Nova AI → Task Force AI across all components
- Tactical design system: Cyan/green accents, monospace typography, hard-edge borders
- Hero: "The AI Execution Economy." with scroll-triggered framer-motion animations
- Stats bar with animated counters, Features grid (6 cards), "Three Steps to Deployment", bottom CTA
- Scan line animation, pulse rings, parallax hero scroll
- Footer: "TASK FORCE AI DEVELOPMENT SERVICES L.L.C." with Terms of Service + Enterprise Contact
- Navbar: TASKFORCE logo, uppercase mono nav links, ENLIST CTA

### Theme System
- Light/Dark mode with system auto-detect + localStorage persistence
- CSS variables for all tokens, theme-toggle (Sun/Moon) in Navbar
- Applied to all pages

### Pricing Page - Subscription Matrix
- 4 tiers: RECRUIT ($0), CADET ($19), OPERATOR ($99), COMMAND (Custom)
- OPERATOR highlighted with cyan gradient glow + "MOST POPULAR" badge
- Monthly/Annual toggle with 20% discount
- Trust bar: 256-BIT ENCRYPTION, SOC 2, 99.9% UPTIME SLA

### The Exchange (Marketplace) Economics
- Split Purchase Panel: Rent (output slider 100-10000, dynamic pricing) vs Acquire (IP acquisition)
- Payment badges: Stripe, Crypto, 80/20 Revenue Split
- Creator spotlight, category pills, trending agents

### Publish Agent Manifests to Supabase
- "Publish to Marketplace" button in Armory Code Pane
- CRUD API: POST/GET/PUT/DELETE /api/published-agents/*
- Manifest stored as JSONB in Supabase

### Creator Dashboard
- Analytics: total agents, executions, trust score, versions
- Agent rows with expandable version history
- Delete and manage published agents

### Agent Version Control
- Auto-incrementing versions on manifest updates
- version_history JSONB tracks each publish
- Full history viewable in Creator Dashboard

### Authentication
- JWT auth (login, register, forgot/reset password)
- Role-based: admin, user, client
- Login redirects to /armory

### The Armory (IDE)
- Draggable node canvas with pan/zoom
- 8 node types, JSON manifest output
- Command Prompt chat connected to Gemini
- Live Agent Terminal via Supabase Realtime
- Compliance Linter (trust score 0-100)
- Workflow CRUD with auto-save

### Security
- Semantic Firewall (Gemini prompt auditing)
- Rate Limiting, Concurrent Cap, SSRF Protection
- Security Audit Dashboard at /security (admin only)

### CSDROP Private Portal
- Client auth with isolation, sovereign bot controls
- Manual login + 2FA, QR sync, cycle diagnostics

## Key Routes
- / — Home (landing)
- /academy — Task Force Academy
- /pricing — Subscription Matrix
- /exchange — The Exchange (marketplace)
- /agent/:id — Agent Detail + Purchase Panel
- /armory — The Armory (IDE)
- /login — Auth
- /dashboard — User Dashboard
- /creator — Creator Dashboard
- /security — Security Audit (admin)

## Credentials
- Admin: admin@nova.ai / admin123
- CSDROP: admin@csdrop.com / nova_csdrop_2026

### Overwatch Admin Dashboard (Phase 22 - May 25, 2026)
- Master analytics command center at /overwatch (admin-only)
- 4 KPI cards: Daily Net Income (cyan), Active Subscriptions, Exchange Volume (20% take rate), Compute Burn Rate (red/green profit margin indicator)
- Revenue Split stacked bar chart (Subscriptions vs Exchange, 30 days via Recharts)
- Top Categories donut chart (Web3 Trackers, Lead Gen, Customer Support, Data Analysis, Code Review)
- Live Execution Feed: terminal-style table with Top 5 grossing agents, execution counts, gross yield, red KILL AGENT override buttons
- Security integration: shows audit count and blocked count from real Supabase security_events
- NOTE: KPI data is MOCKED (demo data). Live feed agent data is MOCKED. Charts use generated data.

### Hero Video (Phase 22 - May 25, 2026)
- Replaced video placeholder with actual auto-playing looping video in hero section
- Video URL: customer-assets CDN (uploaded by user)

### Stripe Subscriptions (Phase 23 - May 26, 2026)
- POST /api/subscriptions/checkout — Creates Stripe checkout for Cadet ($19) or Operator ($99)
- GET /api/subscriptions/status — Returns user's current tier (recruit/cadet/operator)
- POST /api/subscriptions/cancel — Immediately cancels and downgrades to Recruit
- POST /api/subscriptions/activate — Manual activation from payment success page
- Webhook auto-activates subscription on Stripe payment confirmation
- MongoDB: subscriptions collection with user_id, tier, status, payment tracking
- Pricing page CTAs wired to real Stripe checkout (test mode)
- Referral credit discounts applied automatically at checkout

### Referral Credit System (Phase 23 - May 26, 2026)
- GET /api/referrals/my-code — Generates unique TF-XXXXXX referral code per user
- POST /api/referrals/apply — Apply referral code, $10 credit to both referrer + referred
- GET /api/referrals/credits — List available and used credits
- Credits auto-deducted from next subscription checkout
- MongoDB: referral_codes, referrals, referral_credits collections with indexes

## Prioritized Backlog
- **P3**: Hosted execution runtime (Celery + Redis)
- **P3**: Pro tier Stripe subscription
- **P3**: Refactor server.py into modular routers (Auth, CSDROP, Stripe)

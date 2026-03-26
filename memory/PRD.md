# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern, simplistic, highly responsive web application for startup "Nova AI" with strict dark mode aesthetic. Pitch-black backgrounds, dark grey panels, white text, electric blue + neon violet accents. Routes: Home (hero + waitlist), Login (mock auth), Academy (coming soon), Marketplace (agent cards), Studio (split-pane IDE).

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Router
- **Backend**: FastAPI (minimal, health check only)
- **Database**: MongoDB (not used yet - waitlist is mock)
- **Auth**: Frontend-only mock (React Context, admin@nova.ai)

## User Personas
- **Investors**: Viewing high-fidelity UI prototype for pitch/demo
- **Admin (admin@nova.ai)**: Access to Studio IDE prototype

## Core Requirements (Static)
1. Dark mode aesthetic (bg-zinc-950, bg-zinc-900)
2. Electric blue (#00E5FF) CTAs, neon violet (#B900FF) hovers
3. Fonts: Outfit (headings), IBM Plex Sans (body), JetBrains Mono (code)
4. Routes: Home, Academy, Marketplace, Studio, Login
5. Mock auth gating Studio behind admin@nova.ai
6. Brutalist design (rounded-none, sharp edges)

## What's Been Implemented (Feb 2026)
- [x] Persistent navbar with logo, nav links, auth buttons, mobile hamburger
- [x] Home: Hero section with animated headline, waitlist CTA, background visual
- [x] Login: Mock auth card (admin@nova.ai grants Studio access)
- [x] Academy: Coming Soon placeholder
- [x] Marketplace: 3 agent cards with disabled Rent/Buy buttons
- [x] Studio: Split-pane IDE (Chat + Visual Canvas + Code Preview)
- [x] Studio canvas with 4 interactive nodes + SVG connections
- [x] Syntax-highlighted code preview with Deploy button
- [x] Minimal footer (© 2026 Nova AI + mailto link)
- [x] Toast notifications (sonner)
- [x] Full responsive design with mobile menu

## Prioritized Backlog
### P0 (Critical)
- None remaining

### P1 (Important)
- Wire up waitlist to actual MongoDB backend
- Real authentication with JWT
- Persistent auth state (localStorage/cookies)

### P2 (Nice to Have)
- Studio: actual drag-and-drop node interactions
- Studio: real-time code generation from chat
- Academy: course content/curriculum
- Marketplace: search, filter, actual purchase flow
- SEO meta tags per page

## Next Tasks
- Wire up waitlist form to MongoDB backend API
- Add real auth with JWT tokens
- Build Academy course content pages

# Nova AI - Product Requirements Document

## Original Problem Statement
Build a modern, simplistic, highly responsive web application for startup "Nova AI" with strict dark mode aesthetic.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Router
- **Backend**: FastAPI (minimal, health check only)
- **Auth**: Frontend-only mock (React Context, admin@nova.ai)

## Design System (v2 — Modernized)
- **Primary accent**: #8B5CF6 (violet-500)
- **Hover accent**: #A78BFA (violet-400)
- **Backgrounds**: zinc-950, white/[0.03] glass panels
- **Buttons**: Pill-shaped (rounded-full), glow shadows
- **Cards**: rounded-2xl, glass-morphism (backdrop-blur)
- **Borders**: white/[0.06] - white/[0.08] subtle
- **Fonts**: Outfit (headings), IBM Plex Sans (body), JetBrains Mono (code)
- **Logo**: Text-only "nova.ai" with purple dot

## What's Been Implemented (Feb 2026)
- [x] Modernized navbar (text-only logo, pill nav, glass bg)
- [x] Home: Hero with gradient-purple headline, glass input, pill CTA button
- [x] Login: Glass card, rounded inputs, pill sign-in button
- [x] Academy: Coming Soon with gradient text
- [x] Marketplace: 3 glass agent cards with rounded corners
- [x] Studio: Split-pane IDE with purple-glowing nodes + SVG connections
- [x] Minimal footer
- [x] Toast notifications (sonner, glass style)
- [x] Full responsive design
- [x] 100% test pass rate (iteration 2)

## Prioritized Backlog
### P1 - Wire up waitlist to MongoDB
### P1 - Real JWT authentication
### P2 - Studio drag-and-drop nodes
### P2 - Academy course content
### P2 - Marketplace purchase flow

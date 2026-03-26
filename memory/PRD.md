# Nova AI - PRD

## Architecture
Frontend: React 19 + Tailwind + Shadcn UI + React Router | Backend: FastAPI (health check) | Auth: Mock (admin@nova.ai)

## Routes
/ (Home), /login, /academy, /marketplace, /agent/:id, /creator/:id, /studio (protected)

## Implemented (Feb 2026)
- Home: Hero with gradient headline, waitlist CTA
- Login: Mock auth (admin@nova.ai)
- Academy: Coming Soon
- Marketplace: Search, 7 category pills, Supernova creator spotlight, trending section, upgraded agent cards (heart, ratings, trust scores, Live Demo link)
- Agent Detail: Full page with hero, stats, Rent/Buy checkout, Overview/Reviews tabs, demo video placeholder
- Live Demo: Sandboxed chat modal with agent-specific mock responses + typing indicators
- Creator Profile: Stats, bio, agent portfolio
- Studio: Vibe Mode / Node Mode toggle (chat/canvas/code)
- Emergent badge removed
- All features MOCKED (frontend only), 100% test pass rate

## Backlog
P1: Wire waitlist + marketplace to MongoDB, real JWT auth
P2: Drag-drop nodes, Academy content, actual payment checkout, real demo video embeds

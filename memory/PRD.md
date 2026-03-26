# Nova AI - PRD

## Architecture
- **Frontend**: React 19 + Tailwind + Shadcn UI + React Router
- **Backend**: FastAPI + MongoDB (Motor async) + JWT (python-jose) + bcrypt
- **Auth**: Real JWT (24h expiry), stored in localStorage, validated on mount
- **Database**: MongoDB - users, waitlist, agents, creators, reviews collections

## API Endpoints
- POST /api/auth/register - Register + return JWT
- POST /api/auth/login - Login + return JWT
- GET /api/auth/me - Get current user (protected)
- POST /api/waitlist - Add email to waitlist (stored in MongoDB)
- GET /api/waitlist - Admin-only list all waitlist entries
- GET /api/agents - List agents (search + category filter)
- GET /api/agents/:id - Agent detail
- GET /api/agents/:id/reviews - Agent reviews
- GET /api/creators - List creators
- GET /api/creators/:id - Creator + their agents

## Seeded Data
- Admin: admin@nova.ai / admin123
- 6 agents, 5 creators, 24 reviews
- Auto-seeds on startup if empty

## Implemented (Feb 2026)
- [x] Full JWT auth (register, login, me, protected routes, localStorage persistence)
- [x] Waitlist stored in MongoDB
- [x] All marketplace data from MongoDB (agents, creators, reviews)
- [x] Search + category filter via API
- [x] Agent Detail page with real data
- [x] Creator Profile with real data
- [x] Live Demo chat simulation
- [x] Studio with Vibe/Node toggle
- [x] 100% test pass rate (backend + frontend + integration)

## Backlog
P1: User registration UI, password reset flow
P2: Drag-drop nodes, Academy content, actual payment checkout, demo video embeds

# Auth Testing Notes — Playwright / Headless Browser

> Companion to `test_credentials.md`. Use this when scripting Playwright or any
> automated browser test that needs to hit a protected route.

## Token storage on the frontend

Task Force AI's React app reads the JWT from `localStorage` under the key:

```
taskforce_token
```

This is set automatically by `App.js:121` after a successful `/api/auth/login`.
Protected pages (`<ProtectedRoute>`, `<AdminGate>`, `<OwnerGate>` in `App.js`)
gate on `useAuth().user`, which is populated by `validateToken()` calling
`GET /api/auth/me` with the stored token.

## Playwright recipe — log in once, then jump straight to a protected route

```python
import os, json, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
FRONT = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# 1. Grab a token via the REST endpoint (faster than driving the login form)
r = requests.post(
    f"{BASE}/api/auth/login",
    json={"email": "test@taskforce.ai", "password": "TestPass123!"},
    timeout=10,
)
r.raise_for_status()
TOKEN = r.json()["token"]

# 2. Drive Playwright — set the token BEFORE the first navigation to a
#    protected page. Use `page.add_init_script` so the token is in place
#    on EVERY page load (including reloads triggered by SPA routing).
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1920, "height": 800})

    # Inject the token at every navigation, before any app JS runs.
    ctx.add_init_script(
        f"window.localStorage.setItem('taskforce_token', {json.dumps(TOKEN)});"
    )

    page = ctx.new_page()
    page.goto(f"{FRONT}/armory")          # protected route — should render
    page.wait_for_selector("text=Armory", timeout=10_000)
    page.screenshot(path="/tmp/armory.png", quality=20, full_page=False)
    browser.close()
```

### Async (Playwright async API)

```python
await context.add_init_script(
    f"window.localStorage.setItem('taskforce_token', {json.dumps(TOKEN)});"
)
await page.goto(f"{FRONT}/armory")
```

### Alternative — `page.evaluate` after first navigation

If you must navigate first (e.g. to land on `/login` then jump elsewhere):

```python
await page.goto(f"{FRONT}/")  # any same-origin page so localStorage is reachable
await page.evaluate("(t) => localStorage.setItem('taskforce_token', t)", TOKEN)
await page.reload()           # force the SPA to re-run validateToken()
```

## What NOT to do

- ❌ Don't fill the `/login` form in every test — it's slow and rate-limited
  to 10 attempts/min/IP. Use the REST endpoint + `add_init_script`.
- ❌ Don't store the token in cookies — the app reads `localStorage` only.
- ❌ Don't trust a token across runs — JWT_SECRET in `.env` is regenerated on a
  fresh container; old tokens 401.
- ❌ Don't hit `/api/auth/me` without the `Authorization` header — it 401s and
  the test's "I'm logged in" assertion will silently fail.

## Verifying a session is live (sanity probe)

```python
me = requests.get(f"{BASE}/api/auth/me",
                  headers={"Authorization": f"Bearer {TOKEN}"}).json()
assert me["email"] == "test@taskforce.ai"
assert me["role"] == "admin"
```

## CORS check (if a test runs in a real browser, not Playwright)

`backend/.env:CORS_ORIGINS` must include the origin the browser navigated from.
In dev that's `http://localhost:3000` + the preview emergentagent URL — both are
already in the seeded `.env`. Add any extra origin you need before running.

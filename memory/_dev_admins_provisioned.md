# Dev Admins Provisioned

_Generated 2026-06-04T00:36:15.159633+00:00_

| Name | Email | Password | Role | Owner? |
|------|-------|----------|------|--------|
| Benjamin | `benjamin@taskforce.ai` | `benjamin-J7VBJ4rL` | admin | ❌ |
| Shannon Lee | `shannon@taskforce.ai` | `shannon-gxlWbXsA` | admin | ❌ |
| Sultan Al Hashmi | `sultan@taskforce.ai` | `sultan-MuAHw6xC` | admin | ❌ |
| Salem Al Khammas | `salem@taskforce.ai` | `salem-xj6BBGou` | admin | ❌ |
| Anton Glotser | `anton@taskforce.ai` | `anton-qfMptyFp` | admin | ❌ |
| Ian Conner | `ian@taskforce.ai` | `ian-0qSyGYAb` | admin | ❌ |
| Justin | `justin@taskforce.ai` | `justin-izp9IM3z` | admin | ❌ |
| Task Force Admin | `admin@nova.ai` | `admin123` (existing) | admin | ✅ owner |

**Notes:**
- `is_owner` field added to all users (default `false`).
- `tier` field set to `dev` for the 7 above; `owner` for `admin@nova.ai`.
- All 7 devs pass every existing `role == 'admin'` gate. The platform-owner
  reserves `is_owner == true` for future security/secrets routes.

# Frontend linkage

VibeFinderAI has one shared backend and database. Both production frontends are clients of that same backend:

- `https://vibefinderai.netlify.app` — original frontend (`main`)
- `https://vfaithemed.netlify.app` — Themed.AI frontend (`Themed.AI`)
- Shared API: `https://vibefinderai.onrender.com`

## Themed.AI transport

The Themed.AI Netlify deployment uses same-origin proxy routes for `/auth/*`, `/api/*`, and `/health`, forwarding them to the shared Render backend. This keeps authentication and authenticated API requests on the same browser origin while preserving the single-backend architecture.

Do not create a second backend or database for Themed.AI.

# Themed.AI backend link

Themed.AI intentionally uses the same VibeFinderAI backend as the original frontend.

Netlify proxies `/auth/*`, `/api/*`, and `/health` to `https://vibefinderai.onrender.com` so browser requests remain same-origin.

This frontend does not get a separate backend, database, or authentication stack.

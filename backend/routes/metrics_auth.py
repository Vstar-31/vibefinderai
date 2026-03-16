# backend/routes/metrics_auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Metrics authentication — passphrase gate for the /vf-metrics dashboard.
#
# Wire up in main.py (2 lines):
#   from routes.metrics_auth import metrics_router
#   app.include_router(metrics_router)
#
# Wire up in routes/analytics_routes.py (1 import + add Depends to GET routes):
#   from routes.metrics_auth import require_metrics_token
#   ...
#   async def get_dashboard(_: None = Depends(require_metrics_token)):
#
# ENV VARS — add to Render dashboard and backend/.env:
#   METRICS_PASSPHRASE   the passphrase you type in the UI
#   METRICS_SECRET       separate random 32+ char string for signing
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import hmac
import os
import time

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from jose import JWTError, jwt

METRICS_PASSPHRASE = os.getenv("METRICS_PASSPHRASE", "")
_METRICS_SECRET    = os.getenv("METRICS_SECRET", "") or os.getenv("SECRET_KEY", "")

router = APIRouter()


@router.post("/api/metrics/auth")
async def metrics_auth(body: dict = Body(...)):
    """
    Exchange the admin passphrase for a 7-day metrics JWT.
    Passphrase lives only in the Render env var — never in the JS bundle.
    Constant-time compare + fixed 1.5s failure delay prevents brute-force.
    """
    attempt = body.get("passphrase", "")

    valid = (
        bool(METRICS_PASSPHRASE) and
        hmac.compare_digest(attempt.encode(), METRICS_PASSPHRASE.encode())
    )

    if not valid:
        await asyncio.sleep(1.5)
        raise HTTPException(status_code=401, detail="Access denied")

    exp_unix = int(time.time()) + 7 * 24 * 3600  # 7 days

    token = jwt.encode(
        {"sub": "metrics", "exp": exp_unix, "iat": int(time.time())},
        _METRICS_SECRET,
        algorithm="HS256",
    )

    return {
        "token":      token,
        "expires_at": exp_unix * 1000,  # ms for JS Date.now() comparison
    }


def require_metrics_token(authorization: str = Header(None)):
    """
    Dependency for GET /api/analytics/* read endpoints.
    POST event-logging routes stay unprotected (called by regular users).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Metrics token required")

    token = authorization[7:]
    try:
        payload = jwt.decode(token, _METRICS_SECRET, algorithms=["HS256"])
        if payload.get("sub") != "metrics":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired metrics token")

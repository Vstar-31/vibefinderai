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
import jwt
from auth_security import load_signing_key

METRICS_PASSPHRASE = os.getenv("METRICS_PASSPHRASE", "")

def _metrics_key() -> str:
    try:
        key = load_signing_key("METRICS_SECRET")
        if hmac.compare_digest(key.encode("utf-8"), os.getenv("SECRET_KEY", "").encode("utf-8")):
            raise RuntimeError("Metrics must use a separate signing key")
        return key
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Metrics authentication is not configured") from None

router = APIRouter()


@router.post("/api/metrics/auth")
async def metrics_auth(body: dict = Body(...)):
    """
    Exchange the admin passphrase for a 7-day metrics JWT.
    Passphrase lives only in the Render env var — never in the JS bundle.
    Constant-time comparison and failure delay supplement deployment rate limits.
    """
    key = _metrics_key()
    if not METRICS_PASSPHRASE:
        raise HTTPException(status_code=503, detail="Metrics authentication is not configured")
    attempt = body.get("passphrase", "")

    valid = (
        isinstance(attempt, str) and len(attempt) <= 1024 and
        hmac.compare_digest(attempt.encode(), METRICS_PASSPHRASE.encode())
    )

    if not valid:
        await asyncio.sleep(1.5)
        raise HTTPException(status_code=401, detail="Access denied")

    exp_unix = int(time.time()) + 7 * 24 * 3600  # 7 days

    token = jwt.encode(
        {"sub": "metrics", "token_use": "metrics", "exp": exp_unix, "iat": int(time.time())},
        key,
        algorithm="HS256",
    )

    return {
        "token":      token,
        "expires_at": exp_unix * 1000,  # ms for JS Date.now() comparison
    }


def require_metrics_token(authorization: str = Header(None)):
    """
    Dependency for GET /api/analytics/* read endpoints.
    This dependency is mandatory on every analytics read route.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Metrics token required")

    token = authorization[7:]
    key = _metrics_key()
    try:
        payload = jwt.decode(token, key, algorithms=["HS256"],
                             options={"require": ["exp", "sub", "token_use"]})
        if payload.get("sub") != "metrics" or payload.get("token_use") != "metrics":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=401, detail="Invalid or expired metrics token")

"""Single-use, browser-bound provider linking, shared across server workers."""
import base64
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, constr, validator

TTL_SECONDS = 600
_bearer = HTTPBearer(auto_error=False)
_opaque = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_verifier = re.compile(r"[0-9a-f]{64}\Z")


def bearer_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer authentication required", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


class LinkRequest(BaseModel):
    challenge: constr(strict=True, min_length=64, max_length=64)

    @validator("challenge")
    def hexadecimal_challenge(cls, value):
        if not _verifier.fullmatch(value):
            raise ValueError("Expected a 64-character lowercase hexadecimal challenge")
        return value


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}))):
        raise HTTPException(503, "OAuth URL configuration requires HTTPS (or loopback development)")
    return f"{parsed.scheme}://{parsed.netloc}"


def _cookie(provider: str, callback_url: str) -> tuple[str, bool]:
    _origin(callback_url)
    secure = urlsplit(callback_url).scheme == "https"
    return ("__Host-" if secure else "") + "vf_oauth_" + provider, secure


async def authorize(db, user_id: str, provider: str, challenge: str, callback_url: str):
    _origin(callback_url)
    if not urlsplit(callback_url).path.endswith("/callback"):
        raise HTTPException(503, "Invalid OAuth callback URL configuration")
    start_url = callback_url.rsplit("/", 1)[0] + "/start"
    # A signed but deleted/nonexistent user cannot start a link.
    if not await db.user.find_unique(where={"id": user_id}):
        raise HTTPException(401, "Invalid user")
    now = datetime.now(timezone.utc)
    await db.oauthlinktransaction.delete_many(where={"expiresAt": {"lte": now}})
    ticket = secrets.token_urlsafe(32)
    data = {"id": _hash(ticket), "verifierHash": challenge, "stateHash": None,
            "expiresAt": now + timedelta(seconds=TTL_SECONDS)}
    await db.oauthlinktransaction.upsert(
        where={"userId_provider": {"userId": user_id, "provider": provider}},
        data={"create": {**data, "userId": user_id, "provider": provider}, "update": data},
    )
    # Use the callback host directly even when authorize arrived via a frontend
    # reverse proxy; the browser binding cookie must live on the callback host.
    return JSONResponse({"ticket": ticket, "start_url": start_url}, headers={"Cache-Control": "no-store"})


async def start(db, request: Request, provider: str, ticket: str, verifier: str,
                frontend_url: str, callback_url: str) -> str:
    # Top-level POST establishes a first-party cookie even when cross-site fetch
    # cookies are blocked. The ticket alone never establishes browser binding.
    allowed = {_origin(frontend_url), "https://vibefinderai.netlify.app", "https://vfaithemed.netlify.app",
               "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"}
    for configured in os.getenv("FRONTEND_URL_PROD", "").split(","):
        if configured.strip():
            allowed.add(_origin(configured.strip().rstrip("/")))
    if request.headers.get("origin") not in allowed:
        raise HTTPException(403, "Untrusted OAuth start origin")
    _cookie(provider, callback_url)  # Validate before consuming the ticket.
    if not _opaque.fullmatch(ticket) or not _verifier.fullmatch(verifier):
        raise HTTPException(400, "Invalid OAuth transaction")
    state = secrets.token_urlsafe(32)
    count = await db.oauthlinktransaction.update_many(
        where={"id": _hash(ticket), "provider": provider, "verifierHash": _hash(verifier),
               "stateHash": None, "expiresAt": {"gt": datetime.now(timezone.utc)}},
        data={"stateHash": _hash(state)},
    )
    if count != 1:
        raise HTTPException(400, "Invalid or expired OAuth transaction")
    return state


def redirect_to_provider(url: str, provider: str, verifier: str, callback_url: str):
    name, secure = _cookie(provider, callback_url)
    response = RedirectResponse(url, status_code=303,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.set_cookie(name, verifier, max_age=TTL_SECONDS, secure=secure,
                        httponly=True, samesite="lax", path="/")
    return response


async def consume(db, request: Request, provider: str, state: str, callback_url: str):
    name, _ = _cookie(provider, callback_url)
    verifier = request.cookies.get(name, "")
    if not isinstance(state, str) or not _opaque.fullmatch(state) or not _verifier.fullmatch(verifier):
        raise HTTPException(400, "Invalid OAuth state")
    where = {"provider": provider, "stateHash": _hash(state), "verifierHash": _hash(verifier),
             "expiresAt": {"gt": datetime.now(timezone.utc)}}
    transaction = await db.oauthlinktransaction.find_first(where=where)
    if transaction is None:
        raise HTTPException(400, "Invalid or expired OAuth state")
    # Conditional delete is the cross-worker one-use boundary. A newer start
    # changes id, so a stale callback cannot delete its replacement transaction.
    count = await db.oauthlinktransaction.delete_many(where={**where, "id": transaction.id})
    if count != 1:
        raise HTTPException(400, "OAuth state already consumed")
    return transaction.userId, verifier


def finish(url: str, provider: str, callback_url: str):
    # Do not mutate the provider cookie here: a stale or in-flight callback must
    # not erase a newer flow's verifier. It expires after ten minutes, and the
    # consumed database transaction makes it unusable for replay immediately.
    return RedirectResponse(url, status_code=303,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

"""Shared access-token validation. No network or database work belongs here."""

import os

import jwt
from fastapi import HTTPException


def load_signing_key(name: str = "SECRET_KEY") -> str:
    secret = os.getenv(name, "")
    if not secret.strip():
        raise RuntimeError(f"{name} is missing or blank in the running service")
    if secret == "super_secret_student_budget_key_dont_leak_this":
        raise RuntimeError(f"{name} matches the public example key")
    if len(secret.strip().encode("utf-8")) < 32:
        raise RuntimeError(f"{name} must contain a private random value of at least 32 bytes")
    # Preserve the configured bytes; do not silently trim or generate a new key.
    return secret


def decode_access_token(token: str, secret_key: str) -> dict:
    try:
        claims = jwt.decode(
            token, secret_key, algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip() or subject == "metrics":
            raise jwt.InvalidTokenError("Invalid subject")
        # Existing login tokens had no purpose claim. They remain valid until
        # expiry; explicitly typed non-access tokens can never be used here.
        if claims.get("token_use", "access") != "access":
            raise jwt.InvalidTokenError("Invalid token purpose")
        return claims
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise HTTPException(
            status_code=401, detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

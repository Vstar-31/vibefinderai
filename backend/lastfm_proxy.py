"""Bounded public metadata reads for the Audiophile panel, not a general API relay."""
import asyncio
from collections import deque
from contextlib import contextmanager
import json
import logging
import os
import re
from threading import Lock
import time

import httpx
from fastapi import HTTPException, Request

logger = logging.getLogger("VibeFinderEngine.LastfmProxy")
MAX_RESPONSE_BYTES = 1024 * 1024
TOTAL_TIMEOUT_SECONDS = 12
METHODS = {
    "tag.getinfo": ("tag", set()),
    "tag.gettoptracks": ("tag", {"limit"}),
    "tag.gettopartists": ("tag", {"limit"}),
    "artist.getinfo": ("artist", {"autocorrect"}),
    "artist.getsimilar": ("artist", {"limit", "autocorrect"}),
}


class ProxyBudget:
    """Per-process sliding windows and fail-fast concurrency; never queue callers.

    Applies independently of optional SlowAPI imports. IPs come from the ASGI
    peer, not a caller-supplied forwarding header. Configure trusted proxies at
    the server edge. Multi-worker deployments need an additional shared limit.
    """
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = Lock()
        self.global_calls = deque()
        self.clients = {}
        self.active = 0

    @contextmanager
    def slot(self, client):
        with self.lock:
            now = self.clock()
            cutoff = now - 60
            while self.global_calls and self.global_calls[0] <= cutoff:
                self.global_calls.popleft()
            for key, calls in list(self.clients.items()):
                while calls and calls[0] <= cutoff:
                    calls.popleft()
                if not calls:
                    del self.clients[key]
            calls = self.clients.get(client)
            if (len(self.global_calls) >= 60 or (calls is not None and len(calls) >= 30)
                    or (calls is None and len(self.clients) >= 1024)):
                raise HTTPException(429, "Music information request limit reached", headers={"Retry-After": "60"})
            if self.active >= 3:
                raise HTTPException(429, "Music information service busy", headers={"Retry-After": "1"})
            if calls is None:
                calls = self.clients[client] = deque()
            calls.append(now)
            self.global_calls.append(now)
            self.active += 1
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1


_budget = ProxyBudget()


def validated_params(request: Request) -> dict:
    if len(request.scope.get("query_string", b"")) > 4096:
        raise HTTPException(422, "Music information query too long")
    pairs = request.query_params.multi_items()
    params = dict(pairs)
    if len(params) != len(pairs):
        raise HTTPException(422, "Duplicate query parameters are not supported")
    method = params.get("method", "").lower()
    if method not in METHODS:
        raise HTTPException(422, "Unsupported music information method")
    subject, options = METHODS[method]
    if set(params) - {"method", subject} - options:
        raise HTTPException(422, "Unsupported music information parameter")
    raw_value = params.get(subject, "")
    value = raw_value.strip()
    if not value or len(raw_value) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in raw_value):
        raise HTTPException(422, "A nonblank tag or artist of at most 200 characters is required")
    result = {"method": method, subject: value}
    if "limit" in options:
        limit = params.get("limit", "6")
        if not re.fullmatch(r"[0-9]{1,2}", limit) or not 1 <= int(limit) <= 20:
            raise HTTPException(422, "Limit must be between 1 and 20")
        result["limit"] = str(int(limit))
    if "autocorrect" in options:
        autocorrect = params.get("autocorrect", "1")
        if autocorrect not in {"0", "1"}:
            raise HTTPException(422, "Autocorrect must be 0 or 1")
        result["autocorrect"] = autocorrect
    return result


async def _read_metadata(client, params):
    async with client.stream("GET", "https://ws.audioscrobbler.com/2.0/", params=params) as response:
        if response.status_code != 200:
            raise HTTPException(502, "Music information provider unavailable")
        # Avoid decompression amplification before the streamed size check.
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise HTTPException(502, "Unsupported music information encoding")
        data = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=16384):
            if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                raise HTTPException(502, "Music information response too large")
            data.extend(chunk)
        payload = json.loads(data)
        if not isinstance(payload, dict) or "error" in payload:
            raise HTTPException(502, "Music information provider returned an error")
        return payload


async def proxy(request: Request):
    params = validated_params(request)
    key = os.getenv("LASTFM_API_KEY")
    if not key:
        raise HTTPException(503, "Music information service not configured")
    params.update(api_key=key, format="json")
    peer = request.client.host if request.client else "unknown"
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
            for attempt in range(2):
                try:
                    # Retries also consume the same finite outbound budget.
                    with _budget.slot(peer):
                        async with httpx.AsyncClient(
                            timeout=httpx.Timeout(connect=4, read=8, write=4, pool=4),
                            follow_redirects=False, headers={"Accept-Encoding": "identity"},
                        ) as client:
                            return await _read_metadata(client, params)
                except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
                    if attempt:
                        raise
                    await asyncio.sleep(0.2)
    except HTTPException:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, RecursionError) as exc:
        # Exception text/URLs and provider messages may contain credentials.
        logger.warning("Music information request failed (%s)", type(exc).__name__)
        raise HTTPException(502, "Music information provider unavailable") from None

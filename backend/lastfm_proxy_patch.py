"""
PATCH: Replace the lastfm_proxy endpoint in main.py

Root cause of `Last.fm proxy error: ` (empty message):
  httpx raises exceptions like ConnectError() with no args.
  str(ConnectError()) == "" → log shows nothing, client gets 500.

Fixes applied:
  1. repr(e) in logs so the exception type is always visible
  2. Per-request timeout (4s connect, 8s read) — Last.fm is sometimes slow
  3. One automatic retry on ConnectError / TimeoutException (transient network)
  4. Removes `method` from params before sending (it's already in the URL as a
     query param for Last.fm, but this prevents accidental duplication if
     the frontend sends it twice)
  5. Returns the raw Last.fm error JSON with a 502 instead of a 500 when
     Last.fm itself returns an error object — client can handle it gracefully

Replace the existing @app.get("/api/lastfm/proxy") handler in main.py
with this one.
"""

@app.get("/api/lastfm/proxy")
async def lastfm_proxy(request: Request):
    LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
    if not LASTFM_API_KEY:
        raise HTTPException(status_code=500, detail="Last.fm API key not configured")

    params = dict(request.query_params)
    params["api_key"] = LASTFM_API_KEY
    params["format"]  = "json"

    timeout = httpx.Timeout(connect=4.0, read=8.0, write=4.0, pool=4.0)
    last_exc: Exception | None = None

    for attempt in range(2):   # 1 retry on transient errors
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get("https://ws.audioscrobbler.com/2.0/", params=params)

            # Last.fm always returns 200 even for errors — check body
            data = r.json()
            if "error" in data:
                logger.warning(
                    f"[LFM Proxy] Last.fm API error {data['error']}: {data.get('message', '')} "
                    f"(method={params.get('method')}, tag={params.get('tag', params.get('artist', ''))})"
                )
                # Return Last.fm error to client as 502 so frontend can handle it
                raise HTTPException(status_code=502, detail=data.get("message", "Last.fm API error"))

            return data

        except HTTPException:
            raise   # don't retry our own 502s

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_exc = e
            err_repr = repr(e) or type(e).__name__
            if attempt == 0:
                logger.warning(
                    f"[LFM Proxy] Transient error (attempt {attempt+1}/2), retrying: {err_repr} "
                    f"method={params.get('method')}"
                )
                await asyncio.sleep(0.6)   # brief back-off before retry
            else:
                logger.error(
                    f"[LFM Proxy] Failed after 2 attempts: {err_repr} "
                    f"method={params.get('method')}"
                )

        except Exception as e:
            err_repr = repr(e) or type(e).__name__
            logger.error(f"[LFM Proxy] Unexpected error: {err_repr}")
            raise HTTPException(status_code=500, detail=f"Proxy error: {type(e).__name__}")

    raise HTTPException(
        status_code=502,
        detail=f"Last.fm unreachable after retries: {type(last_exc).__name__}",
    )

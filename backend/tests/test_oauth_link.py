"""Exercise the real routers and Prisma transactions; providers never leave this process."""
import asyncio
import base64
import functools
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from test_app_integration import app_client, accounts, TEST_URL

pytestmark = pytest.mark.skipif(not TEST_URL, reason="Requires disposable local PostgreSQL")
PROVIDERS = ("spotify", "lastfm", "deezer", "soundcloud", "youtube")
BASE = "https://testserver"
ORIGIN = "https://frontend.example"


def path(provider):
    return "/api/spotify" if provider == "spotify" else "/api/services/" + provider


@pytest.fixture
def configured(app_client, monkeypatch):
    from routes import spotify_routes as sp, services_routes as svc
    for module in (sp, svc):
        monkeypatch.setattr(module, "FRONTEND_URL", ORIGIN)
    monkeypatch.setattr(sp, "SPOTIFY_REDIRECT_URI", BASE + "/api/spotify/callback")
    monkeypatch.setattr(svc, "BACKEND_URL", BASE)
    for module, names in ((sp, ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")),
                           (svc, ("LASTFM_API_KEY", "LASTFM_SHARED_SECRET", "DEEZER_APP_ID",
                                  "DEEZER_APP_SECRET", "SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET",
                                  "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"))):
        for name in names:
            monkeypatch.setattr(module, name, "local-provider-fixture")
    app_client.cookies.clear()
    calls = []
    original = httpx.AsyncClient.send

    async def provider_response(client, request, *args, **kwargs):
        if request.url.host in {"127.0.0.1", "localhost", "::1"}:
            return await original(client, request, *args, **kwargs)
        calls.append(request)
        if request.url.host == "ws.audioscrobbler.com":
            data = {"session": {"name": "provider-fixture", "key": "provider-secret"}}
        elif request.url.path.endswith(("/token", "access_token.php")):
            data = {"access_token": "provider-secret", "refresh_token": "provider-refresh"}
        elif request.url.path.endswith(("/me", "/userinfo")):
            data = {"id": "provider-fixture", "sub": "provider-fixture", "display_name": "Fixture"}
        else:
            raise AssertionError("Unexpected provider request: " + request.url.host + request.url.path)
        return httpx.Response(200, json=data, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", provider_response)
    yield calls
    app_client.cookies.clear()


def begin(client, account, provider, verifier=None):
    verifier = verifier or secrets.token_hex(32)
    response = client.post(BASE + path(provider) + "/authorize", headers=account[1],
                           json={"challenge": hashlib.sha256(verifier.encode()).hexdigest()})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["start_url"] == BASE + path(provider) + "/start"
    return response.json()["ticket"], verifier


def start(client, provider, ticket, verifier, origin=ORIGIN):
    return client.post(BASE + path(provider) + "/start", data={"ticket": ticket, "verifier": verifier},
                       headers={"Origin": origin}, follow_redirects=False)


def state_from(response, provider):
    assert response.status_code == 303, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    if provider == "lastfm":
        query = parse_qs(urlsplit(query["cb"][0]).query)
    return query["state"][0]


def callback(client, provider, state, **extra):
    return client.get(BASE + path(provider) + "/callback",
                      params={"state": state, "code": "fixture-code", "token": "fixture-token", **extra},
                      follow_redirects=False)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_legitimate_link_is_opaque_browser_bound_and_single_use(app_client, accounts, configured, provider):
    import main
    import oauth_link
    ticket, verifier = begin(app_client, accounts[0], provider)
    response = start(app_client, provider, ticket, verifier)
    state = state_from(response, provider)
    assert len(state) == 43 and ticket != state
    location = response.headers["location"]
    assert accounts[0][1]["Authorization"][7:] not in location
    assert verifier not in location and ticket not in location
    assert all(flag in response.headers["set-cookie"] for flag in ("__Host-", "Secure", "HttpOnly", "SameSite=lax"))
    if provider in {"spotify", "soundcloud", "youtube"}:
        query = parse_qs(urlsplit(location).query)
        assert query["code_challenge"] == [oauth_link.pkce_challenge(verifier)]
        assert query["code_challenge_method"] == ["S256"]
    result = callback(app_client, provider, state)
    assert "connected" in result.headers["location"], result.headers
    assert "set-cookie" not in result.headers
    identity = app_client.portal.call(functools.partial(main.db.oauthidentity.find_first,
        where={"userId": accounts[0][0], "providerName": provider}))
    assert identity.accessToken == "provider-secret"
    if provider in {"spotify", "soundcloud", "youtube"}:
        exchange = next(req for req in configured if req.method == "POST")
        assert parse_qs(exchange.content.decode())["code_verifier"] == [verifier]
    first_calls = len(configured)
    assert "bad_state" in callback(app_client, provider, state).headers["location"]
    assert len(configured) == first_calls


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("attack", ["no_cookie", "wrong_cookie", "legacy_jwt", "wrong_provider", "expired"])
def test_invalid_callback_stops_before_provider_exchange(app_client, accounts, configured, provider, attack):
    import main
    ticket, verifier = begin(app_client, accounts[0], provider)
    state = state_from(start(app_client, provider, ticket, verifier), provider)
    if attack == "no_cookie":
        app_client.cookies.clear()
    elif attack == "wrong_cookie":
        app_client.cookies.clear()
        app_client.cookies.set("__Host-vf_oauth_" + provider, "0" * 64, domain="testserver.local", path="/")
    elif attack == "legacy_jwt":
        state = base64.urlsafe_b64encode(accounts[0][1]["Authorization"][7:].encode()).decode()
    elif attack == "wrong_provider":
        provider = "youtube" if provider != "youtube" else "spotify"
        app_client.cookies.set("__Host-vf_oauth_" + provider, verifier, domain="testserver.local", path="/")
    else:
        app_client.portal.call(functools.partial(main.db.oauthlinktransaction.update_many,
            where={"id": hashlib.sha256(ticket.encode()).hexdigest()},
            data={"expiresAt": datetime.now(timezone.utc) - timedelta(seconds=1)}))
    assert "bad_state" in callback(app_client, provider, state).headers["location"]
    assert configured == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_start_requires_origin_verifier_and_one_use_ticket(app_client, accounts, configured, provider):
    ticket, verifier = begin(app_client, accounts[0], provider)
    assert start(app_client, provider, ticket, verifier, "https://attacker.example").status_code == 403
    assert start(app_client, provider, ticket, verifier, "null").status_code == 403
    assert start(app_client, provider, ticket, "f" * 64).status_code == 400
    state_from(start(app_client, provider, ticket, verifier), provider)
    assert start(app_client, provider, ticket, verifier).status_code == 400
    assert app_client.get(BASE + path(provider) + "/start", params={"ticket": ticket}).status_code == 405
    assert configured == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_error_consumes_transaction_and_new_attempt_supersedes_old(app_client, accounts, configured, provider):
    old_ticket, old_verifier = begin(app_client, accounts[0], provider)
    old_state = state_from(start(app_client, provider, old_ticket, old_verifier), provider)
    ticket, verifier = begin(app_client, accounts[0], provider)
    state = state_from(start(app_client, provider, ticket, verifier), provider)
    assert "bad_state" in callback(app_client, provider, old_state).headers["location"]
    result = callback(app_client, provider, state, error="denied&injected=1")
    assert "access_denied" in result.headers["location"] and "injected" not in result.headers["location"]
    assert "bad_state" in callback(app_client, provider, state).headers["location"]
    assert configured == []


def test_concurrent_callbacks_have_exactly_one_winner(app_client, accounts, configured):
    import main
    import oauth_link
    ticket, verifier = begin(app_client, accounts[0], "spotify")
    state = state_from(start(app_client, "spotify", ticket, verifier), "spotify")
    request = Request({"type": "http", "headers": [(b"cookie", ("__Host-vf_oauth_spotify=" + verifier).encode())]})

    async def race():
        return await asyncio.gather(*(oauth_link.consume(main.db, request, "spotify", state,
                                   BASE + "/api/spotify/callback") for _ in range(8)), return_exceptions=True)

    results = app_client.portal.call(race)
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert sum(isinstance(result, HTTPException) for result in results) == 7


@pytest.mark.parametrize("provider", PROVIDERS)
def test_authorize_requires_header_identity_not_query(app_client, accounts, configured, provider):
    uri = BASE + path(provider) + "/authorize"
    body = {"challenge": "a" * 64}
    assert app_client.get(uri, params={"token": accounts[0][1]["Authorization"][7:]}).status_code == 405
    assert app_client.post(uri, params={"token": accounts[0][1]["Authorization"][7:]}, json=body).status_code == 401
    for auth in ("Bearer malformed", "Basic abc", "BearerBearer abc"):
        assert app_client.post(uri, headers={"Authorization": auth}, json=body).status_code == 401
    assert app_client.post(uri, headers=accounts[0][1], json={"challenge": "bad"}).status_code == 422
    assert configured == []


@pytest.mark.parametrize("uri", ["/api/spotify/status", "/api/services/status", "/api/spotify/search?q=test"])
def test_private_service_reads_only_accept_header(app_client, accounts, configured, uri):
    response = app_client.get(BASE + uri, params={"authorization": accounts[0][1]["Authorization"]})
    assert response.status_code == 401
    if not uri.endswith("q=test"):
        assert app_client.get(BASE + uri, headers=accounts[0][1]).status_code == 200


@pytest.mark.parametrize("provider", PROVIDERS)
def test_provider_account_cannot_be_reassigned(app_client, accounts, configured, provider):
    # First link for the owner; a different user's legitimate flow must not
    # overwrite that provider identity, even if the provider returns the same id.
    for account, expected in ((accounts[0], "connected"), (accounts[1], "db_error")):
        ticket, verifier = begin(app_client, account, provider)
        state = state_from(start(app_client, provider, ticket, verifier), provider)
        result = callback(app_client, provider, state)
        assert expected in result.headers["location"], result.headers


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173",
                                    "https://vfaithemed.netlify.app"])
def test_supported_frontend_can_start_against_https_backend(app_client, accounts, configured, origin):
    ticket, verifier = begin(app_client, accounts[0], "spotify")
    state_from(start(app_client, "spotify", ticket, verifier, origin), "spotify")


def test_proxy_authorize_returns_direct_callback_host(app_client, accounts, configured):
    # Relative frontend API paths may be reverse proxied. The top-level form
    # must bypass that proxy so the cookie is set on the provider callback host.
    response = app_client.post("https://frontend.example/api/spotify/authorize", headers=accounts[0][1],
                               json={"challenge": "a" * 64})
    assert response.status_code == 200
    assert response.json()["start_url"] == BASE + "/api/spotify/start"


@pytest.mark.parametrize("method,uri,body", [
    ("DELETE", "/api/spotify/disconnect", None),
    ("DELETE", "/api/services/lastfm/disconnect", None),
    ("POST", "/api/spotify/export-playlist", {"name": "fixture", "tracks": []}),
    ("POST", "/api/spotify/save-track", {"spotify_uri": "spotify:track:fixture"}),
    ("POST", "/api/services/lastfm/love", {"title": "fixture", "artist": "fixture"}),
    ("POST", "/api/services/lastfm/scrobble", {"title": "fixture", "artist": "fixture"}),
    ("POST", "/api/services/deezer/love", {"title": "fixture", "artist": "fixture"}),
    ("POST", "/api/services/deezer/playlist", {"name": "fixture", "tracks": []}),
    ("POST", "/api/services/soundcloud/like", {"title": "fixture", "artist": "fixture"}),
    ("POST", "/api/services/soundcloud/playlist", {"name": "fixture", "tracks": []}),
    ("POST", "/api/services/youtube/playlist", {"name": "fixture", "tracks": []}),
])
def test_private_mutations_ignore_query_credentials(app_client, accounts, configured, method, uri, body):
    response = app_client.request(method, BASE + uri, json=body,
                                  params={"authorization": accounts[0][1]["Authorization"]})
    assert response.status_code == 401, response.text
    assert configured == []


def test_transaction_rls_blocks_unprivileged_reads_and_writes(app_client, accounts, configured):
    """Requires the SQL migration, not just Prisma db push; creates a disposable role."""
    import main
    from prisma.errors import RawQueryError
    begin(app_client, accounts[0], "spotify")
    role = "oauth_security_test_" + uuid4().hex

    async def check():
        flags = await main.db.query_raw('SELECT relrowsecurity FROM pg_class WHERE oid = \'public."OAuthLinkTransaction"\'::regclass')
        assert flags[0]["relrowsecurity"] is True, "Apply the OAuth SQL migration before running integration tests"
        # RLS remains a deny boundary even if someone accidentally grants table
        # access to a browser role later. The actual migration revokes grants.
        await main.db.execute_raw(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            await main.db.execute_raw(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            await main.db.execute_raw(f'GRANT SELECT, INSERT ON "OAuthLinkTransaction" TO "{role}"')
            async with main.db.tx() as tx:
                await tx.execute_raw(f'SET LOCAL ROLE "{role}"')
                rows = await tx.query_raw('SELECT "id" FROM "OAuthLinkTransaction"')
                assert rows == []
            with pytest.raises(RawQueryError, match="row-level security"):
                async with main.db.tx() as tx:
                    await tx.execute_raw(f'SET LOCAL ROLE "{role}"')
                    await tx.execute_raw('INSERT INTO "OAuthLinkTransaction" ("id", "userId", "provider", "verifierHash", "expiresAt") VALUES ($1, $2, $3, $4, NOW())',
                                         "attacker", accounts[0][0], "spotify", "a" * 64)
        finally:
            await main.db.execute_raw(f'REVOKE ALL ON "OAuthLinkTransaction" FROM "{role}"')
            await main.db.execute_raw(f'REVOKE USAGE ON SCHEMA public FROM "{role}"')
            await main.db.execute_raw(f'DROP ROLE "{role}"')

    app_client.portal.call(check)

"""Opt-in real-app checks against an explicitly named disposable local database.

Generate Prisma and apply schema.prisma first. Set VFAI_TEST_DATABASE_URL to a
loopback PostgreSQL database named vfai_security*. Never use production data.
"""
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

TEST_URL = os.getenv("VFAI_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Requires an explicit disposable local PostgreSQL database")
KEY = "integration-test-user-key-never-use-in-production"


@pytest.fixture(scope="module")
def app_client():
    parsed = urlsplit(TEST_URL)
    assert parsed.scheme in {"postgresql", "postgres"}
    assert parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    assert parsed.path.lstrip("/").startswith("vfai_security")
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
        for key, value in {
            "PYTHON_DOTENV_DISABLED": "1", "DATABASE_URL": TEST_URL, "DIRECT_URL": TEST_URL,
            "SECRET_KEY": KEY, "METRICS_SECRET": "integration-test-metrics-key-independent-of-user-key",
            "METRICS_PASSPHRASE": "local test dashboard", "ENABLE_SEMANTIC": "false",
            "GEMINI_API_KEY": "", "LASTFM_API_KEY": "", "YOUTUBE_API_KEY": "",
            "SPOTIFY_CLIENT_ID": "", "SPOTIFY_CLIENT_SECRET": "",
            "GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "",
            "NO_PROXY": "127.0.0.1,localhost,::1",
        }.items():
            patch.setenv(key, value)
        import httpx
        original_send = httpx.AsyncClient.send

        async def local_only(client, request, *args, **kwargs):
            assert request.url.host in {"127.0.0.1", "localhost", "::1"}, "External HTTP forbidden in integration tests"
            return await original_send(client, request, *args, **kwargs)

        patch.setattr(httpx.AsyncClient, "send", local_only)
        import main
        assert main._ROUTES_AVAILABLE
        assert main._SPOTIFY_ROUTES_AVAILABLE
        assert main._SERVICES_ROUTES_AVAILABLE
        assert main._METRICS_ROUTES_AVAILABLE
        with TestClient(main.app) as client:
            yield client
        assert not main.db.is_connected()


@pytest.fixture(scope="module")
def accounts(app_client):
    users = []
    for label in ("owner", "other"):
        username = label + uuid4().hex
        response = app_client.post("/auth/register", json={
            "username": username, "email": username + "@example.invalid", "password": "local-test-password",
        })
        assert response.status_code == 201, response.text
        user_id = response.json()["user_id"]
        response = app_client.post("/auth/token", data={"username": username, "password": "local-test-password"})
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        assert jwt.decode(token, KEY, algorithms=["HS256"])["token_use"] == "access"
        users.append((user_id, {"Authorization": "Bearer " + token}, username))
    yield users
    import main
    async def cleanup():
        ids = [user[0] for user in users]
        await main.db.viberequest.delete_many(where={"userId": {"in": ids}})
        await main.db.savedplaylist.delete_many(where={"userId": {"in": ids}})
        await main.db.user.delete_many(where={"id": {"in": ids}})
    app_client.portal.call(cleanup)


def test_real_login_and_legacy_session(app_client, accounts):
    user_id, headers, username = accounts[0]
    assert app_client.get("/users/me", headers=headers).json()["id"] == user_id
    assert app_client.post("/auth/token", data={"username": username, "password": "wrong"}).status_code == 401
    legacy = jwt.encode({"sub": user_id, "exp": int(time.time()) + 300}, KEY, algorithm="HS256")
    assert app_client.get("/users/me", headers={"Authorization": "Bearer " + legacy}).status_code == 200


def test_private_playlist_ownership_and_intentional_sharing(app_client, accounts):
    owner, other = accounts[0][1], accounts[1][1]
    response = app_client.post("/api/playlist/save", headers=owner, json={
        "name": "Security integration fixture", "tracks": [
            {"title": "Fixture", "artist": "Fixture", "spotify_uri": "", "apple_uri": ""}],
    })
    assert response.status_code == 201, response.text
    playlist_id = response.json()["id"]
    path = "/api/playlist/" + playlist_id
    assert app_client.get(path, headers=owner).status_code == 200
    assert app_client.get(path, headers=other).status_code == 403
    assert app_client.patch(path, headers=other, json={"name": "not allowed"}).status_code == 403
    assert app_client.delete(path, headers=other).status_code == 403
    assert app_client.get("/api/playlist/list", headers=other).json()["total"] == 0
    shared = app_client.patch(path, headers=owner, json={"is_public": True})
    assert shared.status_code == 200, shared.text
    share_path = "/api/playlist/share/" + shared.json()["share_token"]
    assert app_client.get(share_path).status_code == 200
    assert app_client.patch(path, headers=owner, json={"is_public": False}).status_code == 200
    assert app_client.get(share_path).status_code == 404
    assert app_client.delete(path, headers=owner).status_code == 204
    assert app_client.get(path, headers=owner).status_code == 404


@pytest.mark.parametrize("path", ["/users/me", "/api/playlist/list", "/api/user/history",
    "/api/vibe/history", "/api/user/taste", "/api/analytics/dashboard", "/api/analytics/live",
    "/api/analytics/vibes", "/api/analytics/export"])
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer malformed"}])
def test_actual_private_routes_reject_invalid_identity(app_client, path, headers):
    assert app_client.get(path, headers=headers).status_code == 401


def test_metrics_is_separate_from_user_identity(app_client, accounts):
    assert app_client.get("/api/analytics/live", headers=accounts[0][1]).status_code == 401
    response = app_client.post("/api/metrics/auth", json={"passphrase": "local test dashboard"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["token"]}
    assert app_client.get("/users/me", headers=headers).status_code == 401
    for endpoint in ("live", "vibes", "dashboard", "export"):
        response = app_client.get("/api/analytics/" + endpoint, headers=headers)
        assert response.status_code == 200, response.text


def test_metrics_grouping_with_real_records(app_client, accounts):
    import functools
    import main
    suffix = uuid4().hex
    dominant = "calm-" + suffix
    secondary = "dreamy-" + suffix
    for confidence in (0.4, 0.8):
        app_client.portal.call(functools.partial(main.db.viberequest.create, data={
            "userId": accounts[0][0], "promptText": "integration fixture", "dominantVibe": dominant,
            "secondaryVibe": secondary, "confidence": confidence, "bpmRange": "60-80",
            "genres": "[]", "matchedKeywords": "[]", "returnedTracks": "[]",
        }))
    token = app_client.post("/api/metrics/auth", json={"passphrase": "local test dashboard"}).json()["token"]
    headers = {"Authorization": "Bearer " + token}
    vibes = app_client.get("/api/analytics/vibes", headers=headers)
    assert vibes.status_code == 200, vibes.text
    assert vibes.json()["dominant_vibes"][dominant] == 2
    assert vibes.json()["secondary_vibes"][secondary] == 2
    dashboard = app_client.get("/api/analytics/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text


def test_youtube_cache_cold_read_uses_versioned_identity(app_client):
    import main
    from core import youtube_cache as cache
    title, artist = "Fixture " + uuid4().hex, "Artist"
    current_key = cache._cache_key(title, artist)
    legacy_key = "yt:" + f"{title.lower()}|{artist.lower()}".replace(" ", "_")

    async def check_persistence():
        try:
            await cache.yt_cache_set(title, artist, "correct0001")
            cache._L1.pop(current_key, None)
            cache._l1_set(legacy_key, "wrong000001")
            assert await cache.yt_cache_get(title, artist) == "correct0001"
            assert await main.db.thinpoolcache.find_unique(where={"cacheKey": current_key}) is not None
        finally:
            await main.db.thinpoolcache.delete_many(where={"cacheKey": current_key})
            cache._L1.pop(current_key, None)
            cache._L1.pop(legacy_key, None)

    app_client.portal.call(check_persistence)

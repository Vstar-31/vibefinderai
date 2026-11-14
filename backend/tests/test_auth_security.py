"""Offline regressions against real JWT validation and the actual story route.

The route is loaded from its AST so importing the production database, models,
startup hooks and provider clients is unnecessary. No provider is contacted.
"""
import ast
import importlib.util
from pathlib import Path
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
import sys

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tested_auth_security", ROOT / "auth_security.py")
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)
KEY = "test-only-signing-key-never-for-production-0123456789"


def issue(**overrides):
    claims = {"sub": "user-one", "exp": int(time.time()) + 300}
    claims.update(overrides)
    return jwt.encode(claims, KEY, algorithm="HS256")


@pytest.fixture
def client():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
    names = {"VibeStoryRequest", "generate_vibe_story", "VibeRequest", "VibeResponse",
             "TrackInfo", "FeedbackRequest", "get_user_taste", "read_users_me",
             "analyze_vibe", "get_vibe_history", "submit_feedback"}
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef))
             and node.name in names]
    assert len(nodes) == len(names)
    app = FastAPI()
    namespace = dict(app=app, BaseModel=BaseModel, Depends=Depends,
                     HTTPException=HTTPException, jwt=jwt, SECRET_KEY=KEY,
                     ALGORITHM="HS256", GEMINI_API_KEY="", Prisma=object, status=status,
                     get_db=lambda: None, db=None,
                     oauth2_scheme=OAuth2PasswordBearer(tokenUrl="auth/token"),
                     decode_access_token=auth.decode_access_token)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "main.py"), "exec"), namespace)
    with TestClient(app) as test_client:
        yield test_client


STORY = {"prompt": "quiet piano", "dominant_vibe": "calm", "genres": [], "matched_keywords": []}


def test_profile_returns_only_account_fields(client, monkeypatch):
    profile = dict(id="user-one", username="listener", email="listener@example.invalid",
                   avatarUrl=None, createdAt="2026-01-01T00:00:00Z")

    async def find_unique(*, where):
        assert where == {"id": "user-one"}
        return SimpleNamespace(**profile, hashedPassword="private-test-field")

    handler = next(route.endpoint for route in client.app.routes if route.path == "/users/me")
    monkeypatch.setitem(handler.__globals__, "db", SimpleNamespace(user=SimpleNamespace(find_unique=find_unique)))
    response = client.get("/users/me", headers={"Authorization": "Bearer " + issue()})
    assert response.status_code == 200
    assert response.json() == profile


@pytest.mark.parametrize("token", [
    "not-a-jwt", issue(exp=int(time.time()) - 60), issue(sub=""), issue(sub="   "),
    jwt.encode({"sub": "user-one"}, KEY, algorithm="HS256"),
    jwt.encode({"exp": int(time.time()) + 300}, KEY, algorithm="HS256"),
    issue(token_use="metrics"), issue(sub="metrics"),
    jwt.encode({"sub": "user-one", "exp": int(time.time()) + 300}, "wrong-key", algorithm="HS256"),
])
def test_story_rejects_invalid_identity_before_missing_provider_fallback(client, token):
    assert client.post("/api/vibe/story", json=STORY,
                       headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_story_requires_bearer(client):
    assert client.post("/api/vibe/story", json=STORY).status_code == 401


@pytest.mark.parametrize("valid", [False, True])
def test_configured_provider_is_called_only_for_valid_session(client, monkeypatch, valid):
    handler = next(route.endpoint for route in client.app.routes if route.path == "/api/vibe/story")
    monkeypatch.setitem(handler.__globals__, "GEMINI_API_KEY", "test-provider-key")
    monkeypatch.setitem(handler.__globals__, "_VIBE_STORY_PROMPT", "test prompt")
    calls = []

    class FakeProvider:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append(url)
            return self

        async def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "A test story."}]}}]}

    monkeypatch.setitem(sys.modules, "aiohttp", SimpleNamespace(
        ClientTimeout=lambda **kwargs: None, ClientSession=lambda **kwargs: FakeProvider()))
    response = client.post("/api/vibe/story", json=STORY,
                           headers={"Authorization": "Bearer " + (issue() if valid else "malformed")})
    assert response.status_code == (200 if valid else 401)
    assert len(calls) == (1 if valid else 0)
    if valid:
        assert response.json() == {"story": "A test story."}


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/user/taste", None), ("GET", "/users/me", None),
    ("GET", "/api/vibe/history", None),
    ("POST", "/api/vibe/analyze", {"text": "quiet piano"}),
    ("POST", "/api/feedback", {"request_id": "unlogged", "track_title": "track",
                               "track_artist": "artist", "signal": 1, "position": 0}),
])
@pytest.mark.parametrize("token", ["malformed", issue(exp=1), issue(sub=" "),
                                    jwt.encode({"sub": "user-one"}, KEY, algorithm="HS256"),
                                    issue(token_use="metrics")])
def test_private_routes_reject_invalid_identity_before_database_work(client, method, path, body, token):
    # db=None makes accidental database access fail instead of silently passing.
    response = client.request(method, path, json=body,
                              headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.parametrize("filename", ["playlist_routes.py", "spotify_routes.py", "services_routes.py"])
@pytest.mark.parametrize("token,valid", [("malformed", False), (issue(exp=1), False),
    (issue(sub=" "), False), (jwt.encode({"sub": "user-one"}, KEY, algorithm="HS256"), False),
    (issue(token_use="metrics"), False), (issue(), True), (issue(token_use="access"), True)])
def test_router_identity_helpers_apply_same_validation(filename, token, valid):
    import asyncio
    import inspect
    path = ROOT / "routes" / filename
    if not path.exists():
        pytest.skip("Optional router is absent from the Themed.AI backend snapshot")
    nodes = [node for node in ast.parse(path.read_text(encoding="utf-8-sig")).body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_get_user_id"]
    namespace = dict(jwt=jwt, _jwt=jwt, SECRET_KEY=KEY, _SECRET_KEY=KEY,
                     ALGORITHM="HS256", _ALGORITHM="HS256", HTTPException=HTTPException,
                     decode_access_token=auth.decode_access_token)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    if valid:
        result = namespace["_get_user_id"](token)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        assert result == "user-one"
    else:
        with pytest.raises(HTTPException) as error:
            result = namespace["_get_user_id"](token)
            if inspect.isawaitable(result):
                asyncio.run(result)
        assert error.value.status_code == 401


@pytest.mark.parametrize("token", [issue(), issue(token_use="access")])
def test_valid_existing_and_new_sessions_keep_story_fallback(client, token):
    response = client.post("/api/vibe/story", json=STORY,
                           headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"story": None}


@pytest.mark.parametrize("value", [None, "", " " * 40, "short", "super_secret_student_budget_key_dont_leak_this"])
def test_invalid_signing_configuration_fails_closed(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.load_signing_key()


def test_configured_signing_bytes_are_preserved(monkeypatch):
    value = "  " + KEY + "  "
    monkeypatch.setenv("SECRET_KEY", value)
    assert auth.load_signing_key() == value


@pytest.mark.parametrize("claims", [{"sub": 42}, {"sub": []}, {"exp": None}, {"exp": "not-a-date"}, {"exp": float("inf")}])
def test_invalid_claim_types_are_unauthorized(claims):
    with pytest.raises(HTTPException) as error:
        auth.decode_access_token(issue(**claims), KEY)
    assert error.value.status_code == 401


def test_production_token_issuer_remains_compatible():
    nodes = [node for node in ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig")).body
             if isinstance(node, ast.FunctionDef) and node.name == "create_access_token"]
    assert len(nodes) == 1
    namespace = dict(jwt=jwt, SECRET_KEY=KEY, ALGORITHM="HS256", datetime=datetime, timedelta=timedelta)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "main.py", "exec"), namespace)
    result = namespace["create_access_token"]({"sub": "user-one"}, timedelta(minutes=60))
    claims = auth.decode_access_token(result, KEY)
    assert claims["sub"] == "user-one"
    assert claims["token_use"] == "access"

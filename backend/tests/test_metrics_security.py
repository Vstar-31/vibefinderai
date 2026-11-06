"""Exercise the real metrics module and analytics dependencies without a database."""
import ast
import importlib.util
from pathlib import Path
import time
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
USER_KEY = "test-only-user-signing-key-0123456789"
METRICS_KEY = "test-only-metrics-signing-key-0123456789"


@pytest.fixture
def metrics(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.setenv("SECRET_KEY", USER_KEY)
    monkeypatch.setenv("METRICS_SECRET", METRICS_KEY)
    monkeypatch.setenv("METRICS_PASSPHRASE", "test dashboard passphrase")
    spec = importlib.util.spec_from_file_location("tested_metrics", ROOT / "routes/metrics_auth.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())
    return module


@pytest.fixture
def client(metrics):
    app = FastAPI()
    app.include_router(metrics.router)

    @app.get("/protected")
    def protected(_=Depends(metrics.require_metrics_token)):
        return {"ok": True}

    # Execute the actual analytics decorators and dependency declarations; no
    # database is supplied, so unauthorized requests must stop before handlers.
    tree = ast.parse((ROOT / "routes/analytics_routes.py").read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
             and node.decorator_list]
    assert len(nodes) == 4
    namespace = {"router": APIRouter(), "Depends": Depends,
                 "require_metrics_token": metrics.require_metrics_token}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "analytics_routes.py", "exec"), namespace)
    app.include_router(namespace["router"], prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


def token(**overrides):
    claims = {"sub": "metrics", "token_use": "metrics", "exp": int(time.time()) + 300}
    claims.update(overrides)
    return jwt.encode(claims, METRICS_KEY, algorithm="HS256")


def test_correct_passphrase_issues_scoped_token_and_allows_metrics(client):
    response = client.post("/api/metrics/auth", json={"passphrase": "test dashboard passphrase"})
    assert response.status_code == 200
    result = response.json()
    claims = jwt.decode(result["token"], METRICS_KEY, algorithms=["HS256"])
    assert claims["token_use"] == claims["sub"] == "metrics"
    assert result["expires_at"] == claims["exp"] * 1000
    assert client.get("/protected", headers={"Authorization": "Bearer " + result["token"]}).status_code == 200
    from auth_security import decode_access_token
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        decode_access_token(result["token"], METRICS_KEY)
    assert error.value.status_code == 401


@pytest.mark.parametrize("attempt", [None, 123, {}, [], "wrong", "x" * 1025])
def test_invalid_passphrase_is_unauthorized(client, attempt):
    assert client.post("/api/metrics/auth", json={"passphrase": attempt}).status_code == 401


@pytest.mark.parametrize("key", [None, "", "short", USER_KEY,
                                  "super_secret_student_budget_key_dont_leak_this"])
def test_missing_weak_or_shared_key_disables_metrics(client, monkeypatch, key):
    if key is None:
        monkeypatch.delenv("METRICS_SECRET", raising=False)
    else:
        monkeypatch.setenv("METRICS_SECRET", key)
    assert client.post("/api/metrics/auth", json={"passphrase": "test dashboard passphrase"}).status_code == 503
    assert client.get("/protected", headers={"Authorization": "Bearer " + token()}).status_code == 503


def test_missing_passphrase_disables_login(client, metrics):
    metrics.METRICS_PASSPHRASE = ""
    assert client.post("/api/metrics/auth", json={"passphrase": ""}).status_code == 503


@pytest.mark.parametrize("value", ["malformed", token(exp=1), token(exp=float("inf")), token(sub="user-one"),
                                   token(token_use="access"),
                                   jwt.encode({"sub": "metrics", "token_use": "metrics"}, METRICS_KEY, algorithm="HS256"),
                                   jwt.encode({"sub": "metrics", "exp": int(time.time()) + 300}, METRICS_KEY, algorithm="HS256"),
                                   jwt.encode({"sub": "metrics", "token_use": "metrics", "exp": int(time.time()) + 300}, USER_KEY, algorithm="HS256")])
def test_invalid_or_user_signed_tokens_are_unauthorized(client, value):
    assert client.get("/protected", headers={"Authorization": "Bearer " + value}).status_code == 401


@pytest.mark.parametrize("path", ["dashboard", "live", "vibes", "export"])
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer malformed"}])
def test_every_analytics_route_requires_authentication(client, path, headers):
    assert client.get("/api/analytics/" + path, headers=headers).status_code == 401


def test_unicode_keys_are_compared_without_server_error(client, monkeypatch):
    monkeypatch.setenv("METRICS_SECRET", "独立" * 32)
    monkeypatch.setenv("SECRET_KEY", "用户" * 32)
    assert client.post("/api/metrics/auth", json={"passphrase": "test dashboard passphrase"}).status_code == 200

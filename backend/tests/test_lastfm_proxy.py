"""Real proxy handler/transport with offline provider responses; no database required."""
import ast
import asyncio
from contextlib import ExitStack
import importlib
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def proxy(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    module = importlib.import_module("lastfm_proxy")
    monkeypatch.setenv("LASTFM_API_KEY", "private-provider-fixture")
    monkeypatch.setattr(module, "_budget", module.ProxyBudget())
    calls = []
    behavior = {"status": 200, "payload": {"tag": {"name": "fixture"}}, "headers": {}}

    async def respond(request):
        calls.append(request)
        if behavior.get("failures", 0):
            behavior["failures"] -= 1
            raise httpx.ReadTimeout("offline transient failure")
        if "exception" in behavior:
            raise behavior["exception"]
        if "content" in behavior:
            return httpx.Response(behavior["status"], content=behavior["content"], headers=behavior["headers"])
        return httpx.Response(behavior["status"], json=behavior["payload"], headers=behavior["headers"])

    original_client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient",
                        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    # Exercise the actual route wrapper without importing optional snapshot DB modules.
    fn = next(node for node in ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig")).body
              if isinstance(node, ast.AsyncFunctionDef) and node.name == "lastfm_proxy")
    fn.decorator_list = []
    namespace = {"Request": Request, "public_lastfm_proxy": module.proxy}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROOT / "main.py"), "exec"), namespace)
    app = FastAPI()
    app.get("/api/lastfm/proxy")(namespace["lastfm_proxy"])
    with TestClient(app) as client:
        yield client, module, calls, behavior


@pytest.mark.parametrize("params", [
    {"method": "tag.getinfo", "tag": "chill"},
    {"method": "tag.gettoptracks", "tag": "chill", "limit": "6"},
    {"method": "tag.gettopartists", "tag": "chill", "limit": "5"},
    {"method": "artist.getinfo", "artist": "Artist", "autocorrect": "1"},
    {"method": "artist.getsimilar", "artist": "Artist", "limit": "5", "autocorrect": "1"},
    {"method": "artist.getSimilar", "artist": "音楽 & Artist", "limit": "20", "autocorrect": "0"},
])
def test_public_panel_reads_remain_available(proxy, params):
    client, module, calls, behavior = proxy
    response = client.get("/api/lastfm/proxy", params=params)
    assert response.status_code == 200, response.text
    assert response.json() == behavior["payload"]
    assert len(calls) == 1
    assert str(calls[0].url).startswith("https://ws.audioscrobbler.com/2.0/?")
    assert calls[0].url.params["api_key"] == "private-provider-fixture"
    assert calls[0].url.params["format"] == "json"
    assert calls[0].headers["accept-encoding"] == "identity"
    assert "private-provider-fixture" not in response.text


@pytest.mark.parametrize("query", [
    "method=auth.gettoken", "method=user.getrecenttracks&user=victim", "method=track.love&track=x",
    "method=tag.getinfo&tag=x&api_key=attacker", "method=tag.getinfo&tag=x&format=xml",
    "method=tag.getinfo&tag=x&callback=alert", "method=tag.getinfo&tag=x&sk=secret",
    "method=tag.getinfo&tag=x&url=http://127.0.0.1", "method=tag.getinfo&tag=x&page=999999",
    "method=tag.getinfo&tag=x&method=auth.gettoken", "method=tag.getinfo&tag=x&tag=y",
    "method=tag.getinfo", "method=tag.getinfo&tag=%20", "method=tag.getinfo&tag=%00test",
    "method=tag.getinfo&tag=%0Atest", "method=tag.getinfo&tag=" + "x" * 201,
    "method=tag.gettoptracks&tag=x&limit=999999", "method=tag.gettoptracks&tag=x&limit=21",
    "method=tag.gettoptracks&tag=x&limit=0", "method=tag.gettoptracks&tag=x&limit=-1",
    "method=tag.gettoptracks&tag=x&limit=1.0", "method=tag.gettoptracks&tag=x&limit=1e2",
    "method=artist.getinfo&artist=x&autocorrect=2", "method=tag.getinfo&tag=" + "x" * 4096,
])
def test_unsupported_operations_and_inputs_stop_before_provider(proxy, query):
    client, _, calls, _ = proxy
    assert client.get("/api/lastfm/proxy?" + query).status_code == 422
    assert calls == []


def test_client_limit_cannot_be_reset_with_forwarding_headers(proxy):
    client, _, calls, _ = proxy
    for index in range(30):
        assert client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x",
                          headers={"X-Forwarded-For": f"192.0.2.{index}"}).status_code == 200
    response = client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x", headers={"X-Forwarded-For": "203.0.113.1"})
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    assert len(calls) == 30


def test_global_budget_and_window_expiry(proxy):
    budget = proxy[1].ProxyBudget(clock=lambda: clock[0])
    clock = [100.0]
    for i in range(60):
        with budget.slot(str(i)):
            pass
    with pytest.raises(HTTPException) as error:
        with budget.slot("new-client"):
            pass
    assert error.value.status_code == 429
    clock[0] += 60
    with budget.slot("new-client"):
        pass
    assert len(budget.clients) == 1


def test_concurrency_fails_fast_and_releases_slots(proxy):
    budget = proxy[1].ProxyBudget()
    with ExitStack() as stack:
        for index in range(3):
            stack.enter_context(budget.slot(str(index)))
        with pytest.raises(HTTPException) as error:
            with budget.slot("fourth"):
                pass
        assert error.value.status_code == 429
    assert budget.active == 0
    with pytest.raises(RuntimeError):
        with budget.slot("failing"):
            raise RuntimeError("fixture")
    assert budget.active == 0


@pytest.mark.parametrize("change", [
    {"status": 302, "headers": {"Location": "https://attacker.example"}},
    {"status": 500}, {"payload": {"error": 6, "message": "private-provider-fixture"}},
    {"payload": []}, {"content": b"not JSON private-provider-fixture"},
    {"content": b"x" * (1024 * 1024 + 1)},
])
def test_bad_provider_responses_fail_closed_without_leaking_details(proxy, change, caplog):
    client, module, calls, behavior = proxy
    behavior.update(change)
    response = client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x")
    assert response.status_code == 502
    assert len(calls) == 1
    assert "private-provider-fixture" not in response.text + caplog.text
    assert module._budget.active == 0


def test_compressed_response_is_rejected_before_decoding(proxy):
    module = proxy[1]
    # Supply a streaming body, avoiding HTTPX MockTransport's eager fixture decode.
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("compressed content must not be read")
            yield b""  # pragma: no cover
    class ResponseClient:
        def stream(self, *args, **kwargs):
            class Context:
                async def __aenter__(self):
                    return httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=Body())
                async def __aexit__(self, *args):
                    pass
            return Context()
    with pytest.raises(HTTPException) as error:
        asyncio.run(module._read_metadata(ResponseClient(), {}))
    assert error.value.status_code == 502


def test_timeouts_have_one_retry_no_secret_logging_and_release_slots(proxy, caplog):
    client, module, calls, behavior = proxy
    behavior["exception"] = httpx.ReadTimeout("https://provider/?api_key=private-provider-fixture")
    response = client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x")
    assert response.status_code == 502 and len(calls) == 2
    assert "private-provider-fixture" not in response.text + caplog.text
    assert module._budget.active == 0


def test_one_transient_failure_preserves_successful_retry(proxy):
    client, module, calls, behavior = proxy
    behavior["failures"] = 1
    response = client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x")
    assert response.status_code == 200 and response.json() == behavior["payload"]
    assert len(calls) == 2 and len(module._budget.global_calls) == 2
    assert module._budget.active == 0


def test_total_deadline_cancels_trickling_provider(proxy, monkeypatch):
    client, module, calls, behavior = proxy
    monkeypatch.setattr(module, "TOTAL_TIMEOUT_SECONDS", 0.01)
    async def never_finishes(*args):
        await asyncio.sleep(10)
    monkeypatch.setattr(module, "_read_metadata", never_finishes)
    response = client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x")
    assert response.status_code == 502 and module._budget.active == 0


def test_missing_configuration_does_not_call_provider(proxy, monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY")
    client, _, calls, _ = proxy
    assert client.get("/api/lastfm/proxy?method=tag.getinfo&tag=x").status_code == 503
    assert calls == []

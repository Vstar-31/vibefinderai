"""Real router/cache tests with a mocked provider; no database or network."""
import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def youtube(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    routes = importlib.import_module("routes.services_routes")
    cache = importlib.import_module("core.youtube_cache")
    monkeypatch.setattr(cache, "_L1", {})
    monkeypatch.setattr(cache, "_db", None)
    monkeypatch.setattr(routes, "YOUTUBE_API_KEY", "test-provider-key")
    queries = []

    class Provider:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, *, params, **kwargs):
            queries.append(params["q"])
            video = "correct0001" if params["q"] == "good song artist official audio" else "wrong000001"
            return SimpleNamespace(json=lambda: {"items": [{"id": {"videoId": video},
                "snippet": {"title": "fixture", "channelTitle": "fixture",
                            "thumbnails": {"default": {"url": "https://example.invalid/image"}}}}]})

    monkeypatch.setattr(routes.httpx, "AsyncClient", Provider)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, cache, queries


def test_unrelated_query_cannot_poison_track_lookup(youtube):
    client, cache, queries = youtube
    params = {"title": "Good Song", "artist": "Artist", "q": "unrelated attacker video"}
    first = client.get("/api/services/youtube/search", params=params)
    assert first.status_code == 200
    assert first.json()["video_id"] == "correct0001"
    assert queries == ["good song artist official audio"]
    params["q"] = "Good Song Artist official audio"
    second = client.get("/api/services/youtube/search", params=params)
    assert second.json() == {"found": True, "video_id": "correct0001", "cached": True}
    assert len(queries) == 1


@pytest.mark.parametrize("first,second", [(("a|b", "c"), ("a", "b|c")),
                                         (("a_b", "c"), ("a b", "c"))])
def test_distinct_metadata_cannot_collide(youtube, first, second):
    cache = youtube[1]
    assert cache._cache_key(*first) != cache._cache_key(*second)


def test_normalized_identity_uses_same_query_and_cache(youtube):
    client, cache, queries = youtube
    assert cache._cache_key(" Good Song ", " ARTIST ") == cache._cache_key("good song", "artist")
    response = client.get("/api/services/youtube/search", params={"title": " Good Song ", "artist": " ARTIST "})
    assert response.status_code == 200
    assert response.json()["video_id"] == "correct0001"
    assert queries == ["good song artist official audio"]


def test_legacy_potentially_poisoned_cache_entries_are_not_reused(youtube):
    client, cache, queries = youtube
    cache._l1_set("yt:good_song|artist", "wrong000001")
    assert asyncio.run(cache.yt_cache_get("Good Song", "Artist")) is None


def test_free_text_search_does_not_write_shared_track_cache(youtube):
    client, cache, queries = youtube
    response = client.get("/api/services/youtube/search", params={"q": "free text search"})
    assert response.status_code == 200
    assert queries == ["free text search"]
    assert cache._L1 == {}


@pytest.mark.parametrize("params", [{}, {"q": " "}, {"title": "song", "q": "query"},
    {"title": " ", "artist": "artist", "q": "query"}, {"q": "x" * 501},
    {"title": "x" * 201, "artist": "artist", "q": "query"}])
def test_invalid_or_excessive_input_rejected_before_provider(youtube, params):
    client, cache, queries = youtube
    assert client.get("/api/services/youtube/search", params=params).status_code == 422
    assert queries == []

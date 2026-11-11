"""Exercise the public route with local database and music-provider fixtures."""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import jwt

import main


class ArtistDetectionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        artists = [
            {"name": "Electronic", "songs": "Get the Message"},
            {"name": "Calm", "songs": "Arlington Sunset"},
            {"name": "Taylor Swift", "songs": "Love Story"},
            {"name": "Drake", "songs": "Passionfruit"},
        ]
        self.database = SimpleNamespace(
            artistdirectory=SimpleNamespace(find_many=AsyncMock(return_value=[SimpleNamespace(**a) for a in artists])),
            viberequest=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id="test-request"))),
        )
        self.patches.enter_context(patch.multiple(
            main, db=self.database,
            SECRET_KEY="artist-detection-test-secret-key-only",
            ARTIST_NAME_INDEX={a["name"]: a for a in artists},
            _GEMINI_AVAILABLE=False, _SENTIMENT_AVAILABLE=False,
            _SEMANTIC_MODULE_AVAILABLE=False,
        ))
        tracks = [{"title": f"Test track {i}", "artist": f"Test artist {i}"} for i in range(5)]
        for name in ("fetch_lastfm_tracks", "fetch_lastfm_artist_tracks", "fetch_lastfm_track_search"):
            self.patches.enter_context(patch.object(main, name, AsyncMock(return_value=tracks)))
        self.patches.enter_context(patch.object(main, "fetch_itunes_preview", AsyncMock(
            return_value={"preview_url": None, "cover_art": None},
        )))
        self.patches.enter_context(patch.object(main, "filter_and_score_tracks", return_value=tracks))
        token = jwt.encode({"sub": "local-artist-test"}, main.SECRET_KEY, algorithm=main.ALGORITHM)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.addAsyncCleanup(self.client.aclose)

    async def analyze(self, **payload):
        response = await self.client.post("/api/vibe/analyze", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_gui_regression_prompt_stays_unlocked(self):
        data = await self.analyze(text="rainy night drive with mellow electronic music", track_limit=5)
        self.assertIsNone(data["detected_artist"])
        self.assertNotEqual(data["dominant_vibe"], "artist_driven")
        self.assertIsNone(self.database.viberequest.create.call_args.kwargs["data"]["detectedArtist"])

    async def test_curated_artist_and_explicit_ambiguous_artist(self):
        for prompt, expected in [("Taylor Swift", "Taylor Swift"), ("songs by Electronic", "Electronic")]:
            with self.subTest(prompt=prompt):
                data = await self.analyze(text=prompt)
                self.assertEqual(data["detected_artist"], expected)

    async def test_dismissal_skips_directory_lookup(self):
        with patch.object(main, "ARTIST_NAME_INDEX", {}):
            data = await self.analyze(text="Drake", dismiss_detected_artist=True)
        self.assertIsNone(data["detected_artist"])
        self.database.artistdirectory.find_many.assert_not_awaited()

    async def test_manual_override_wins_even_with_dismissal(self):
        data = await self.analyze(text="calm music", override_artist="Electronic", dismiss_detected_artist=True)
        self.assertEqual(data["detected_artist"], "Electronic")
        main.fetch_lastfm_artist_tracks.assert_awaited_once_with(artist="Electronic", limit=200)

    async def test_empty_index_uses_same_rules_for_database_rows(self):
        with patch.object(main, "ARTIST_NAME_INDEX", {}):
            data = await self.analyze(text="calm electronic music")
        self.assertIsNone(data["detected_artist"])
        self.database.artistdirectory.find_many.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

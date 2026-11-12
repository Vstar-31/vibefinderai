"""Sentiment enrichment must not discard stronger heuristic evidence."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from analyzers import sentiment_boost
from core.vibe_engine import analyze_vibe_algorithm


class SentimentConfidenceTests(unittest.TestCase):
    def boost(self, text, original, polarity=0.0, subjectivity=0.0):
        blob = SimpleNamespace(sentiment=SimpleNamespace(
            polarity=polarity, subjectivity=subjectivity,
        ))
        with patch.object(sentiment_boost, "_TEXTBLOB_AVAILABLE", True), patch.object(
            sentiment_boost, "TextBlob", return_value=blob, create=True,
        ):
            return sentiment_boost.apply_sentiment_boost(text, original)

    def test_live_mood_prompt_keeps_heuristic_confidence(self):
        text = "rainy night drive with mellow electronic music"
        original = analyze_vibe_algorithm(text)
        self.assertGreater(original["confidence"], 0.5)
        self.assertEqual(original["dominant_vibe"], "chill")
        self.assertEqual(self.boost(text, original), original)

    def test_weak_positive_sentiment_cannot_replace_stronger_calm_result(self):
        original = {"dominant_vibe": "calm", "confidence": 0.58,
                    "genres": ["Ambient"], "matched_keywords": ["calm"]}
        self.assertEqual(self.boost("warm and cozy", original, 0.16, 0.59), original)

    def test_low_confidence_prompt_can_still_gain_a_better_vibe(self):
        original = {"dominant_vibe": "chill", "confidence": 0.05}
        result = self.boost("an abstract description", original)
        self.assertEqual(result["dominant_vibe"], "focus")
        self.assertGreater(result["confidence"], original["confidence"])
        self.assertEqual(original, {"dominant_vibe": "chill", "confidence": 0.05})

    def test_same_vibe_can_still_improve(self):
        original = {"dominant_vibe": "focus", "confidence": 0.05}
        result = self.boost("background details", original)
        self.assertEqual(result["dominant_vibe"], "focus")
        self.assertGreater(result["confidence"], original["confidence"])

    def test_existing_scores_are_not_mutated(self):
        original = {"dominant_vibe": "happy", "confidence": 0.2,
                    "_raw_scores": {"happy": 0.1, "focus": 1.0}}
        before = deepcopy(original)
        result = self.boost("a coding session", original)
        self.assertGreater(result["confidence"], original["confidence"])
        self.assertEqual(result["dominant_vibe"], "focus")
        self.assertEqual(original, before)

    def test_high_confidence_and_unavailable_dependency_remain_unchanged(self):
        original = {"dominant_vibe": "chill", "confidence": 0.8}
        self.assertEqual(self.boost("anything", original), original)
        with patch.object(sentiment_boost, "_TEXTBLOB_AVAILABLE", False):
            self.assertIs(sentiment_boost.apply_sentiment_boost("anything", original), original)


if __name__ == "__main__":
    unittest.main()

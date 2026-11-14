import unittest
from types import SimpleNamespace

from core.artist_detection import detect_entities, normalize_for_matching


ARTISTS = [
    {"name": "Electronic", "songs": "Getting Away With It, Get the Message"},
    {"name": "Calm", "songs": "Arlington Sunset"},
    {"name": "Instrumental", "songs": ""},
    {"name": "Future", "songs": "Mask Off"},
    {"name": "Queen", "songs": "Bohemian Rhapsody"},
    {"name": "The Weeknd", "songs": "Blinding Lights, Save Your Tears"},
    {"name": "Taylor Swift", "songs": "Love Story, Blank Space"},
    {"name": "Drake", "songs": "Passionfruit"},
    {"name": "Arijit Singh", "songs": "Tum Hi Ho"},
    {"name": "A. R. Rahman", "songs": "Jai Ho"},
    {"name": "Night Drive", "songs": "Lost Highway"},
    {"name": "Love", "songs": "Alone Again Or"},
    {"name": "The Art of Noise", "songs": "Moments in Love"},
]


class ArtistDetectionTests(unittest.TestCase):
    def test_descriptions_do_not_become_artist_locks(self):
        prompts = [
            "rainy night drive with mellow electronic music",
            "calm cozy soft music",
            "instrumental focus music",
            "future bass for a night drive",
            "feeling like a queen on a night drive",
            "calm", "electronic", "instrumental", "night drive",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_entities(prompt, ARTISTS), (None, None))

    def test_clear_curated_artist_mentions_still_work(self):
        for name in ["Taylor Swift", "Drake", "Arijit Singh", "The Weeknd"]:
            with self.subTest(name=name):
                self.assertEqual(detect_entities(f"late night {name} vibes", ARTISTS)[0], name)

    def test_ambiguous_and_unlisted_names_need_explicit_intent(self):
        for prompt, name in [
            ("music by Electronic", "Electronic"),
            ("the band Electronic", "Electronic"),
            ("songs by Calm", "Calm"),
            ("Future the rapper", "Future"),
            ("play Future", "Future"),
            ("songs by Queen", "Queen"),
            ("songs by Night Drive", "Night Drive"),
            ("the band The Art of Noise", "The Art of Noise"),
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_entities(prompt, ARTISTS)[0], name)

    def test_uncurated_names_require_an_artist_cue(self):
        self.assertEqual(detect_entities("The Art of Noise", ARTISTS), (None, None))

    def test_negated_mentions_cannot_lock(self):
        for prompt in [
            "no Drake", "don't play Drake", "don't want Drake", "without music by Drake",
            "not songs by Electronic", "avoid the band Electronic",
            "not the song Blinding Lights", "never play Future",
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_entities(prompt, ARTISTS), (None, None))

    def test_negation_is_per_mention(self):
        self.assertEqual(detect_entities("no Drake, Taylor Swift please", ARTISTS)[0], "Taylor Swift")

    def test_famous_name_inside_a_word_does_not_match(self):
        self.assertEqual(detect_entities("drakes on a lake", ARTISTS), (None, None))

    def test_song_substrings_do_not_lock_an_artist(self):
        for prompt in ["save your tears for tomorrow", "blank space in my head", "lost highway at night"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_entities(prompt, ARTISTS), (None, None))

    def test_explicit_and_exact_recognized_titles_still_work(self):
        self.assertEqual(detect_entities("Blinding Lights", ARTISTS), ("The Weeknd", "blinding lights"))
        self.assertEqual(detect_entities("the song Getting Away With It", ARTISTS), ("Electronic", "getting away with it"))

    def test_artist_name_outranks_another_artists_song(self):
        rows = [{"name": "Other", "songs": "Drake"}, *ARTISTS]
        self.assertEqual(detect_entities("Drake", rows), ("Drake", None))

    def test_known_artist_and_matching_song_are_returned_together(self):
        self.assertEqual(detect_entities("The Weeknd Blinding Lights", ARTISTS), ("The Weeknd", "blinding lights"))

    def test_shared_title_does_not_choose_arbitrary_artist(self):
        rows = [*ARTISTS, {"name": "Cover Artist", "songs": "Blinding Lights"}]
        self.assertEqual(detect_entities("the song Blinding Lights", rows), (None, None))

    def test_specific_name_wins_over_contained_name_in_any_order(self):
        rows = [{"name": "Weeknd", "songs": ""}, *ARTISTS]
        for source in [rows, list(reversed(rows))]:
            self.assertEqual(detect_entities("music by The Weeknd", source)[0], "The Weeknd")

    def test_db_fallback_and_index_produce_same_answer(self):
        rows = [SimpleNamespace(**artist) for artist in ARTISTS]
        for prompt in ["music by Electronic", "calm electronic music", "Drake", "song Blinding Lights"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_entities(prompt, rows), detect_entities(prompt, ARTISTS))

    def test_normalization_preserves_accent_punctuation_and_spacing_support(self):
        self.assertEqual(normalize_for_matching("BÉYONCÉ"), "beyonce")
        self.assertEqual(normalize_for_matching("Ke$ha"), "kesha")
        self.assertEqual(detect_entities("Taylor   Swift", ARTISTS)[0], "Taylor Swift")
        self.assertEqual(detect_entities("songs by A. R. Rahman", ARTISTS)[0], "A. R. Rahman")

    def test_empty_names_and_null_songs_are_safe(self):
        rows = [{"name": "!!!", "songs": "anything"}, {"name": None}, {"name": "Drake", "songs": None}]
        self.assertEqual(detect_entities("Drake", rows), ("Drake", None))


if __name__ == "__main__":
    unittest.main()

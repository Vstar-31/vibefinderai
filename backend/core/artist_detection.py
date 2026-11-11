"""Conservative artist and song recognition for natural-language prompts."""

import re
import unicodedata

from core.vibe_engine import DIRECT_GENRE_MAP, VIBE_MAP

def normalize_for_matching(text: str) -> str:
    nfkd  = unicodedata.normalize("NFD", text)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    clean = clean.replace("$", "s")
    clean = re.sub(r'[^\w\s]', '', clean)
    return " ".join(clean.split())

COMMON_WORDS_BLACKLIST = {
    "alone","beautiful","water","time","burn","lights","independent","deep","passion",
    "holiday","eve","chicago","slow","love","night","good","bad","happy","sad","summer",
    "rain","coffee","drive","party","chill","focus","work","sleep","wake","morning",
    "midnight","fire","magic","dream","smooth","fragile","resolute","kiss","paralyzed",
    "ready","electric","bright","warm","cold","sweet","bitter","lost","found","free",
    "bound","broken","whole","still","moving","running","falling","rising","flying",
    "paris","london","tokyo","berlin","miami","california","vegas","brooklyn","texas",
    "heaven","hell","home","stay","leave","run","go","come","back","waiting","gone",
    "over","forever","again","always","never","heart","soul","mind","eyes","hands",
    "voice","tears","perfect","wonderful","amazing","dangerous","crazy","wild",
    "indian","scene","crying","peace","live","talk","terror","harvest","down","hyper",
    "wheat","confession","song","sun","and","her","main","era","self","class","numb",
    "stars","mirror","guitar","beast","chai","focus","sur","dhun","taal","bol","dil",
    "raat","din","waqt","geet","ishq","pyaar","yaad","good","bad","big","little","new",
    "old","real","true","white","black","blue","red","green","gold","silver","hot","cool",
    "raw","dark","light","high","low","city","town","road","street","window","door","room",
    "wave","beat","sound","noise","vibe","energy","mood","summer","winter","spring",
    "autumn","rain","snow","wind","live","dead","born","young","old","fast","slow",
    "loop","mix","set","jam","flow","groove","drop","bounce","blend","cut","run",
    "session","playlist","queue","ke","liye","ke liye","chahiye","thoda",
    "texture","future","p.o.p","pop","on","film","rock","sad","dance","classic","art",
    "soul","fusion","acoustic","ambient","indie","folk","jazz","house","trap","bass",
    "vocal","vocals","instrumental","electronic","calm","mellow",
    "queen","prince","tool","muse","beach house","war","air","yes",
}

# Reuse the engine's curated artist catalogue as the automatic-recognition
# list. Directory membership alone is not evidence of an intended artist.
RECOGNIZED_ARTISTS = frozenset(
    normalize_for_matching(artist)
    for vibe in VIBE_MAP.values()
    for artist in vibe.get("artists", [])
)
_VIBE_TERMS = {
    normalize_for_matching(word)
    for vibe in VIBE_MAP.values()
    for field in ("keywords", "phrases", "context", "genres")
    for word in vibe.get(field, [])
}
_VIBE_TERMS.update(normalize_for_matching(word) for word in DIRECT_GENRE_MAP)
_VIBE_TERMS.update(normalize_for_matching(word) for word in VIBE_MAP)
# Some genre aliases are artist references, including "the weeknd". Keep those
# eligible, while the explicit common-word list always wins (e.g. Future).
AMBIGUOUS_NAMES = frozenset(
    {normalize_for_matching(word) for word in COMMON_WORDS_BLACKLIST}
    | (_VIBE_TERMS - RECOGNIZED_ARTISTS)
)
_NEGATION = re.compile(
    r"\b(?:not|no|dont|nothing|avoid|except|without|skip|never|excluding)\s+"
    r"(?:(?:any|more|play|playing|want|hear|include|like|listen|to|songs?|tracks?|music|by|from|the|band|artist|singer|rapper)\s+)*$"
)
_ARTIST_CUE = re.compile(
    r"\b(?:(?:songs?|tracks?|albums?|music)\s+(?:by|from)|"
    r"(?:the\s+)?(?:band|artist|singer|rapper|composer|producer))\s+$"
)
_ARTIST_SUFFIX = re.compile(r"\s+(?:the\s+)?(?:band|artist|singer|rapper|composer|producer)\b")
_SONG_CUE = re.compile(r"\b(?:song|track|title)(?:\s+(?:called|named))?\s+$")


def _mentions(entity: str, prompt: str):
    """Match whole normalized names, preserving negation for each occurrence."""
    if entity not in prompt:
        return
    for match in re.finditer(rf"(?<!\w){re.escape(entity)}(?!\w)", prompt):
        if not _NEGATION.search(prompt[:match.start()]):
            yield match


def detect_entities(text: str, artists) -> tuple[str | None, str | None]:
    """Prefer explicit artists, then curated names, then unambiguous song titles.

    Ambiguous words require an artist cue even when their names are well known.
    Explicit overrides and dismissal are handled by the endpoint before scanning.
    Accept both the slim startup index and Prisma rows used by the DB fallback.
    """
    prompt = normalize_for_matching(text)
    artist_matches = []
    song_matches = []
    for artist in artists:
        name = artist.get("name", "") if isinstance(artist, dict) else artist.name
        songs = artist.get("songs", "") if isinstance(artist, dict) else artist.songs
        normalized = normalize_for_matching(name or "")
        if not normalized or not re.search(r"\w", normalized):
            continue

        known = normalized in RECOGNIZED_ARTISTS
        ambiguous = normalized in AMBIGUOUS_NAMES
        matched_songs = []
        for title in (songs or "").split(","):
            song = normalize_for_matching(title)
            if not song:
                continue
            mentions = list(_mentions(song, prompt))
            if mentions:
                matched_songs.append(title.strip().lower())
            if len(song) <= 3 or song in AMBIGUOUS_NAMES:
                continue
            explicit_song = any(_SONG_CUE.search(prompt[:m.start()]) for m in mentions)
            # Loose title substrings such as "I want it that way tonight" must
            # not choose an artist before a more explicit artist mention.
            if explicit_song or (known and prompt == song):
                song_matches.append((name, title.strip().lower()))

        for match in _mentions(normalized, prompt):
            before, after = prompt[:match.start()], prompt[match.end():]
            explicit = bool(_ARTIST_CUE.search(before) or _ARTIST_SUFFIX.match(after))
            if ambiguous:
                # "play Future" is an artist request; "future bass" is not.
                direct_play = known and bool(re.search(r"\bplay\s+$", before)) and not after.strip()
                if not (explicit or direct_play):
                    continue
            elif not (explicit or known):
                continue
            song = matched_songs[0] if matched_songs else None
            artist_matches.append((explicit, normalized, name, song))

    if artist_matches:
        # Explicit intent outranks incidental matches. Longer names win over
        # contained names, independent of the database's iteration order.
        artist_matches.sort(key=lambda item: (not item[0], -len(item[1]), item[1], item[2]))
        _, _, name, song = artist_matches[0]
        return name, song
    unique_songs = set(song_matches)
    if len(unique_songs) == 1:
        return next(iter(unique_songs))
    return None, None

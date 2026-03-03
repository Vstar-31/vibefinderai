from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from contextlib import asynccontextmanager
from prisma import Prisma
import urllib.parse
import json
import asyncio
import random
import re
import logging
import sys
import time
import hashlib
from core.vibe_engine import LANGUAGE_TAG_MAP
# aiohttp is the async-safe HTTP client (replaces urllib in hot paths)
# Falls back gracefully to the sync urllib path if not installed.
try:
    import aiohttp as _aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    import urllib.request  # kept only for the legacy sync fallback

# Import our modularized vibe engine
from core import vibe_engine

# Import semantic fallback ranker (gracefully degrades if model not installed)
from analyzers import semantic_search

# Import Gemini vibe analyzer for fallback enhancement
from core.gemini_vibe import GeminiVibeAnalyzer

# Load environment variables
load_dotenv()

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logger = logging.getLogger("VibeFinderEngine")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

file_handler = logging.FileHandler("vibefinder_engine.log", encoding="utf-8")
file_handler.setLevel(logging.INFO) # Detailed data flows quietly into the text file

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.WARNING) # Terminal ONLY shows warnings/errors to prevent clutter!

file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.handlers = [file_handler, stream_handler]

# ---------------------------------------------------------
# Database Initialization (Prisma)
# ---------------------------------------------------------
db = Prisma()

# ── In-memory feature indexes (populated on startup) ─────────────────────────
# Keyed by "title_lower|artist_lower" → audio feature dict
TRACK_FEATURE_INDEX: dict[str, dict] = {}
# Keyed by niche string → list of artist dicts from ArtistDirectory
ARTIST_NICHE_INDEX: dict[str, list[dict]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI. Connects to the Prisma DB 
    on startup and cleanly disconnects on shutdown.
    """
    logger.info("Initializing Supabase (Prisma) connection...")
    await db.connect()
    logger.info("Database connected successfully. Engine online.")
    
    # ── Load TrackFeatureCache into memory for fast O(1) scoring lookups ──────
    # The DB has 690+ tracks with real audio features (tempo, energy, valence,
    # moodHappy, moodSad, moodRelaxed, moodAggressive, moodParty).
    # We load them all into multiple lookup dicts:
    #   1. title_lower|artist_lower (primary key)
    #   2. isrc (fallback key for spelling mismatches across APIs)
    # filter_and_score_tracks tries primary first, then falls back to ISRC.
    try:
        _cache_rows = await db.trackfeaturecache.find_many()
        _isrc_index: dict[str, dict] = {}  # Fallback: ISRC → features
        for row in _cache_rows:
            _feat = {
                "tempo":           float(row.tempo) if row.tempo else None,
                "energy":          float(row.energy) if row.energy else None,
                "valence":         float(row.valence) if row.valence else None,
                "moodHappy":       float(row.moodHappy) if row.moodHappy else None,
                "moodSad":         float(row.moodSad) if row.moodSad else None,
                "moodRelaxed":     float(row.moodRelaxed) if row.moodRelaxed else None,
                "moodAggressive":  float(row.moodAggressive) if row.moodAggressive else None,
                "moodParty":       float(row.moodParty) if row.moodParty else None,
            }
            # Primary key: title|artist
            _key = f"{(row.title or '').strip().lower()}|{(row.artist or '').strip().lower()}"
            TRACK_FEATURE_INDEX[_key] = _feat
            # Fallback key: ISRC code (for cross-database matching when title/artist mismatch)
            if row.isrc:
                _isrc_index[row.isrc.upper()] = _feat
        # Store ISRC index as a secondary lookup in app state for use during scoring
        app.state.isrc_feature_index = _isrc_index
        logger.info(f"TrackFeatureCache loaded: {len(TRACK_FEATURE_INDEX)} tracks indexed, {len(_isrc_index)} with ISRC codes.")
    except Exception as e:
        logger.warning(f"TrackFeatureCache load failed (scoring will use heuristics only): {e}")
        app.state.isrc_feature_index = {}

    # ── Load ArtistDirectory niche→name index for DB-assisted pool building ───
    # Maps niche string → list of artist names, used to supplement Last.fm pools
    # without a cold API call when the vibe maps to a well-indexed niche.
    try:
        _artist_rows = await db.artistdirectory.find_many(
            where={"tadbTop10": {"not": None}},
        )
        for row in _artist_rows:
            _niche = (row.niche or "").strip().lower()
            if _niche:
                ARTIST_NICHE_INDEX.setdefault(_niche, []).append({
                    "name": row.name,
                    "genres": row.genres or "",
                    "mbTags": row.mbTags or "",
                    "tadbTop10": row.tadbTop10,
                })
        logger.info(f"ArtistDirectory niche index loaded: {len(ARTIST_NICHE_INDEX)} niches, "
                    f"{sum(len(v) for v in ARTIST_NICHE_INDEX.values())} total artists.")
    except Exception as e:
        logger.warning(f"ArtistDirectory index load failed (DB pool supplement disabled): {e}")

    yield
    logger.info("Engine shutting down. Disconnecting database...")
    await db.disconnect()

# Initialize core app with lifespan hook
import difflib as _difflib

# ── Rate limiting (slowapi) ──────────────────────────────────────────────────
# pip install slowapi
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(key_func=get_remote_address)
    _RATE_LIMIT_AVAILABLE = True
except ImportError:
    _RATE_LIMIT_AVAILABLE = False
    _limiter = None
    logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")

# ── Known words for typo normalization ──
_KNOWN_WORDS = [
    "happy","sad","calm","chill","dark","dreamy","ambient","romantic","heartbreak",
    "hype","intense","party","retro","soulful","focus","euphoric","cinematic",
    "industrial","tropical","indie","folk","punjabi","hindi","bollywood","bhangra",
    "desi","haryanvi","sufi","ghazal","qawwali","lofi","rap","trap","drill","rnb",
    "soul","jazz","rock","metal","pop","electronic","edm","house","techno","classical",
    "country","reggae","afrobeats","amapiano","dancehall","reggaeton","kpop","jpop",
    "vaporwave","shoegaze","acoustic","alternative","grunge","hardstyle","phonk",
    "hyperpop","gothic","darkwave","night","drive","summer","winter","rain","love",
    "dance","workout","sleep","study","meditation","guitar","bass","piano","vocal",
    "smooth","heavy","soft","hard","fast","slow","loud","quiet","warm","cold",
]

def normalize_input(text: str) -> str:
    """Restore consonant-skeleton typos (e.g. 'pujabi dace hrad' → 'punjabi dance hard')."""
    if not text or len(text.strip()) < 3:
        return text
    words = text.strip().split()
    corrected, changed = [], False
    for word in words:
        w = word.lower()
        vowel_ratio = sum(1 for c in w if c in "aeiou") / max(len(w), 1)
        if vowel_ratio < 0.2 and len(w) > 2 and w.isalpha():
            matches = _difflib.get_close_matches(w, _KNOWN_WORDS, n=1, cutoff=0.62)
            if matches:
                corrected.append(matches[0])
                changed = True
                continue
        corrected.append(word)
    result = " ".join(corrected)
    if changed:
        import logging as _log
        _log.getLogger(__name__).info(f"normalize_input: '{text}' → '{result}'")
    return result

import unicodedata

def _normalize_for_matching(text: str) -> str:
    """Strip combining accents, normalize special chars (like $ to s) so Ólafur == olafur, Travi$ == travis."""
    nfkd = unicodedata.normalize("NFD", text)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    # 🚨 BRO FIX: Bug 1 - The Travi$ Scott normalization fix
    clean = clean.replace("$", "s")
    clean = re.sub(r'[^\w\s]', '', clean) # Blast away punctuation that kills fuzzy matches
    return clean.strip()

app = FastAPI(
    title="VibeFinderAI API", 
    description="Core backend for music discovery and NLP integrations",
    lifespan=lifespan
)

# Initialize Gemini fallback enhancer
gemini_analyzer = GeminiVibeAnalyzer()

# Wire rate limiter if available
if _RATE_LIMIT_AVAILABLE:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting active via slowapi.")

# ---------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------
# Build CORS allowed origins from environment variables
def get_cors_origins():
    origins = []
    
    # Always include local dev
    origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ])
    
    # Add production frontend URL if configured
    frontend_prod = os.getenv("FRONTEND_URL_PROD")
    if frontend_prod:
        origins.append(frontend_prod)
    
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Auth & Security Configuration
# ---------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Bcrypt context - pinned for passlib compatibility
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Module-level (around line 60) ──────────────────────────────────────
COMMON_WORDS_BLACKLIST = {
    "alone", "beautiful", "water", "time", "burn", "lights",
    "independent", "deep", "passion", "holiday", "eve", "chicago",
    "slow", "love", "night", "good", "bad", "happy", "sad", "summer",
    "rain", "coffee", "drive", "party", "chill", "focus", "work",
    "sleep", "wake", "morning", "midnight", "fire", "magic", "dream",
    "smooth", "fragile", "resolute", "kiss", "paralyzed", "ready",
    "electric", "bright", "warm", "cold", "sweet", "bitter",
    "lost", "found", "free", "bound", "broken", "whole",
    "still", "moving", "running", "falling", "rising", "flying",
    # ── v5.1 additions: place names + ultra-common nouns ──
    "paris", "london", "tokyo", "berlin", "miami",
    "california", "vegas", "brooklyn", "texas", "heaven", "hell", "home",
    "stay", "leave", "run", "go", "come", "back", "waiting",
    "gone", "over", "forever", "again", "always", "never",
    "heart", "soul", "mind", "eyes", "hands", "voice", "tears",
    "perfect", "wonderful", "amazing", "dangerous", "crazy", "wild",
    # ── v9.0 Phase 2 QA additions (35+ new words from 100-prompt test) ──
    # Common English words that double as obscure artist/band names:
    "indian", "scene", "crying", "peace", "live", "talk",
    "terror", "harvest", "down", "hyper", "wheat", "confession",
    "song", "sun", "and", "her", "main", "era", "self", "class",
    "numb", "stars", "mirror", "guitar", "beast", "chai", "focus",
    # Hindi/Indian common words that get false-locked:
    "sur", "dhun", "taal", "bol", "dil", "raat", "din", "waqt",
    "geet", "ishq", "pyaar", "yaad",
    # Generic descriptive words that appear in casual prompts:
    "good", "bad", "big", "little", "new", "old", "real", "true",
    "white", "black", "blue", "red", "green", "gold", "silver",
    "hot", "cool", "raw", "dark", "light", "high", "low",
    "city", "town", "road", "street", "window", "door", "room",
    "wave", "beat", "sound", "noise", "vibe", "energy", "mood",
    "summer", "winter", "spring", "autumn", "rain", "snow", "wind",
    "live", "dead", "born", "young", "old", "fast", "slow",
}

# Tracks that appeared in 10%+ of all QA results regardless of prompt.
# These get a score penalty in the scoring engine so they don't dominate every playlist.
TRACK_BLOCKLIST: set[str] = {
    "trap queen|fetty wap",
    "circumambient|grimes",        # appears in almost every dark result
    "slow|my bloody valentine",    # leads every dreamy result
    "slowdive|slowdive",           # same pool monopoly
    "moanin'|art blakey & the jazz messengers",  # leads every soulful result
    "time moves slow|badbadnotgood",
    # v5.0 additions from QA analysis
    "4 am (adam k & soha mix)|kaskade",  # monopolizes euphoric results
    "finished symphony (deadmau5 remix)|hybrid",  # monopolizes euphoric
    "silhouettes - original radio edit|avicii",    # monopolizes euphoric
    "strobe (radio edit)|deadmau5",                # monopolizes euphoric  
    "brazil (2nd edit)|deadmau5",                  # monopolizes euphoric
    "to the hellfire|lorna shore",                 # monopolizes intense
    "you only live once|suicide silence",          # monopolizes intense
    "pray for plagues|bring me the horizon",       # monopolizes intense
    "country girl (shake it for me)|luke bryan",   # monopolizes country
    "take me home, country roads|john denver",     # monopolizes country
    "she's country|jason aldean",                  # monopolizes country
}
# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------


# ═══════════════════════════════════════════════════════════════════════════════
# VIBE_TAG_MATRIX  v6.0 — Hyper-specific Last.fm tag matrix
# Maps (dominant_vibe, language) → ordered list of Last.fm tags.
# ═══════════════════════════════════════════════════════════════════════════════
VIBE_TAG_MATRIX: dict[str, dict[str, list[str]]] = {
    "heartbreak": {
        "Hindi":      ["bollywood sad", "filmi sad", "arijit singh", "atif aslam"],
        "Punjabi":    ["punjabi sad", "b praak", "jaani", "punjabi heartbreak"],
        "English":    ["sad", "heartbreak", "indie sad", "emo"],
        "Tamil":      ["kollywood sad", "tamil sad songs", "sid sriram"],
        "Telugu":     ["tollywood sad", "telugu sad songs"],
        "Korean":     ["korean ballad", "k-pop sad", "korean indie sad"],
        "Japanese":   ["j-pop ballad", "japanese sad", "jpop sad"],
        "Spanish":    ["latin sad", "reggaeton triste", "bachata sad"],
        "Portuguese": ["mpb sad", "saudade", "fado"],
        "French":     ["chanson triste", "french sad", "french indie sad"],
        "Arabic":     ["arabic sad", "arabic ballad", "arabic heartbreak"],
        "Afrobeats":  ["afrobeats sad", "afro-soul", "afro heartbreak"],
        "Bengali":    ["bengali sad", "rabindra sangeet sad"],
        "Urdu":       ["ghazal", "urdu sad", "rahat fateh ali khan"],
        "Kannada":    ["kannada sad songs", "sandalwood sad"],
        "Malayalam":  ["malayalam sad songs", "mollywood sad"],
        "Any":        ["sad", "heartbreak"],
    },
    "romantic": {
        "Hindi":      ["bollywood romantic", "hindi love songs", "filmi romantic", "ar rahman"],
        "Punjabi":    ["punjabi romantic", "ap dhillon", "punjabi love songs"],
        "English":    ["romantic", "love songs", "rnb", "slow jams"],
        "Tamil":      ["kollywood romantic", "tamil love songs", "ar rahman tamil"],
        "Telugu":     ["tollywood romantic", "telugu love songs"],
        "Korean":     ["k-pop romantic", "korean love songs", "k-ballad"],
        "Japanese":   ["j-pop romantic", "japanese love songs", "city pop"],
        "Spanish":    ["latin romantic", "bachata", "bolero"],
        "Portuguese": ["bossa nova", "mpb romantic"],
        "French":     ["chanson romantique", "french romantic"],
        "Arabic":     ["arabic romantic", "arabic love songs"],
        "Afrobeats":  ["afrobeats romantic", "afro rnb"],
        "Bengali":    ["bengali romantic", "rabindra sangeet"],
        "Urdu":       ["ghazal romantic", "urdu love songs"],
        "Kannada":    ["kannada romantic songs"],
        "Malayalam":  ["malayalam romantic songs"],
        "Any":        ["romantic", "love songs"],
    },
    "happy": {
        "Hindi":      ["bollywood happy", "hindi upbeat", "bollywood fun", "badshah"],
        "Punjabi":    ["bhangra", "punjabi happy", "punjabi dance"],
        "English":    ["happy", "feel good", "indie pop"],
        "Tamil":      ["kollywood happy", "tamil upbeat songs"],
        "Telugu":     ["tollywood happy", "telugu upbeat songs"],
        "Korean":     ["k-pop happy", "k-pop upbeat"],
        "Japanese":   ["j-pop happy", "japanese pop upbeat"],
        "Spanish":    ["latin pop", "cumbia", "salsa"],
        "Portuguese": ["pagode", "axe", "forro"],
        "French":     ["variete francaise", "french pop happy"],
        "Arabic":     ["arabic pop happy", "arabic upbeat"],
        "Afrobeats":  ["afrobeats", "afropop", "highlife"],
        "Bengali":    ["bengali happy songs", "bengali folk"],
        "Urdu":       ["urdu happy", "qawwali upbeat"],
        "Kannada":    ["kannada happy songs"],
        "Malayalam":  ["malayalam happy songs"],
        "Any":        ["happy", "feel good"],
    },
    "party": {
        "Hindi":      ["bollywood dance", "hindi club", "hindi party", "badshah"],
        "Punjabi":    ["bhangra", "punjabi party", "desi club", "diljit dosanjh"],
        "English":    ["party", "dance pop", "club", "edm"],
        "Tamil":      ["kollywood dance", "tamil party songs"],
        "Telugu":     ["tollywood dance", "telugu party songs"],
        "Korean":     ["k-pop dance", "k-pop party"],
        "Japanese":   ["j-pop dance", "japanese club"],
        "Spanish":    ["reggaeton", "latin dance", "perreo"],
        "Portuguese": ["funk carioca", "baile funk"],
        "French":     ["french house", "french electro"],
        "Arabic":     ["arabic dance", "arabic pop party"],
        "Afrobeats":  ["afrobeats party", "amapiano"],
        "Bengali":    ["bengali dance", "bengali party songs"],
        "Urdu":       ["urdu party", "desi party"],
        "Kannada":    ["kannada dance songs"],
        "Malayalam":  ["malayalam party songs"],
        "Any":        ["party", "dance", "club"],
    },
    "hype": {
        "Hindi":      ["desi hip hop", "indian hip hop", "hindi rap", "divine"],
        "Punjabi":    ["punjabi trap", "punjabi hip hop", "karan aujla", "sidhu moosewala"],
        "English":    ["hip-hop", "trap", "rap", "drill"],
        "Tamil":      ["tamil rap", "tamil hip hop"],
        "Telugu":     ["telugu rap", "tollywood hype"],
        "Korean":     ["k-hip hop", "korean rap"],
        "Japanese":   ["japanese hip hop", "j-rap"],
        "Spanish":    ["reggaeton", "latin trap", "latin hip hop"],
        "Portuguese": ["funk carioca", "trap brasileiro"],
        "French":     ["rap francais", "french rap", "afrotrap"],
        "Arabic":     ["arabic rap", "arabic trap", "mahraganat"],
        "Afrobeats":  ["afro trap", "naija rap"],
        "Bengali":    ["bengali rap", "bangla hip hop"],
        "Urdu":       ["urdu rap", "desi rap"],
        "Kannada":    ["kannada rap"],
        "Malayalam":  ["malayalam rap"],
        "Any":        ["hip-hop", "trap", "rap"],
    },
    "calm": {
        "Hindi":      ["sufi", "ghazal", "hindi acoustic", "bollywood soft"],
        "Punjabi":    ["punjabi sufi", "punjabi acoustic", "satinder sartaaj"],
        "English":    ["calm", "acoustic", "folk", "singer-songwriter"],
        "Tamil":      ["tamil acoustic", "carnatic calm", "ar rahman soft"],
        "Telugu":     ["telugu soft songs", "carnatic"],
        "Korean":     ["k-indie", "korean folk", "korean acoustic"],
        "Japanese":   ["japanese acoustic", "j-folk", "city pop mellow"],
        "Spanish":    ["latin acoustic", "bossa nova", "flamenco acoustic"],
        "Portuguese": ["bossa nova", "mpb calm"],
        "French":     ["chanson calme", "french acoustic"],
        "Arabic":     ["arabic calm", "arabic acoustic"],
        "Afrobeats":  ["afro-soul", "afro acoustic"],
        "Bengali":    ["rabindra sangeet", "bengali acoustic", "baul"],
        "Urdu":       ["ghazal", "mehdi hassan"],
        "Kannada":    ["carnatic", "kannada soft songs"],
        "Malayalam":  ["malayalam acoustic", "carnatic malayalam"],
        "Any":        ["calm", "acoustic", "folk"],
    },
    "chill": {
        "Hindi":      ["hindi lofi", "bollywood lofi", "hindi chill"],
        "Punjabi":    ["punjabi chill", "punjabi lofi"],
        "English":    ["chill", "lofi hip hop", "chillhop"],
        "Tamil":      ["tamil lofi", "kollywood lofi"],
        "Telugu":     ["telugu lofi", "tollywood lofi"],
        "Korean":     ["k-indie chill", "korean lofi", "k-rnb"],
        "Japanese":   ["city pop", "japanese lofi", "j-chill"],
        "Spanish":    ["latin chill", "lofi latino"],
        "Portuguese": ["bossa nova chill", "mpb lofi"],
        "French":     ["french chill", "lofi french"],
        "Arabic":     ["arabic chill", "arabic lofi"],
        "Afrobeats":  ["afro chill", "alte"],
        "Bengali":    ["bengali lofi", "bengali chill"],
        "Urdu":       ["urdu chill", "sufi lofi"],
        "Kannada":    ["kannada lofi"],
        "Malayalam":  ["malayalam lofi"],
        "Any":        ["chill", "lofi", "chillhop"],
        # ── Lofi-specific mood variant ───────────────────────────────────────
        # When user explicitly says "lofi beats", "lofi hip hop" etc., secondary
        # vibe tends to be focus. We pivot tags to the precise lofi hip hop pool
        # rather than generic chill, which returns R&B/neo-soul instead.
        "Any__focus":    ["lofi hip hop", "chillhop", "jazz hop", "study beats"],
        "Any__dreamy":   ["lofi hip hop", "chillhop", "lofi"],
        "English__focus": ["lofi hip hop", "chillhop", "nujabes", "j dilla"],
    },
    "focus": {
        "Hindi":      ["hindi instrumental", "ar rahman instrumental", "indian classical"],
        "Punjabi":    ["punjabi instrumental", "tabla focus"],
        "English":    ["focus", "study", "instrumental", "ambient"],
        "Tamil":      ["carnatic instrumental", "ar rahman instrumental"],
        "Telugu":     ["carnatic instrumental", "telugu instrumental"],
        "Korean":     ["korean instrumental", "k-indie instrumental"],
        "Japanese":   ["japanese instrumental", "city pop instrumental"],
        "Spanish":    ["latin instrumental", "flamenco instrumental"],
        "Portuguese": ["bossa nova instrumental", "mpb instrumental"],
        "French":     ["french jazz instrumental", "french classical"],
        "Arabic":     ["oud instrumental", "arabic classical"],
        "Afrobeats":  ["afro instrumental"],
        "Bengali":    ["rabindra sangeet instrumental"],
        "Urdu":       ["sitar classical", "urdu instrumental"],
        "Kannada":    ["carnatic instrumental"],
        "Malayalam":  ["carnatic instrumental", "kerala percussion"],
        "Any":        ["focus", "study", "instrumental"],
    },
    "euphoric": {
        "Hindi":      ["bollywood dance", "hindi euphoric", "bollywood edm"],
        "Punjabi":    ["bhangra edm", "punjabi edm"],
        "English":    ["euphoric", "trance", "edm", "dance"],
        "Tamil":      ["kollywood dance euphoric", "tamil edm"],
        "Telugu":     ["tollywood dance euphoric"],
        "Korean":     ["k-pop euphoric", "k-edm"],
        "Japanese":   ["j-edm", "japanese trance"],
        "Spanish":    ["reggaeton euphoric", "latin edm"],
        "Portuguese": ["baile funk euphoric"],
        "French":     ["french house", "french techno"],
        "Arabic":     ["arabic edm", "mahraganat hype"],
        "Afrobeats":  ["amapiano euphoric", "afrobeats rave"],
        "Bengali":    ["bengali edm"],
        "Urdu":       ["qawwali euphoric"],
        "Kannada":    ["kannada dance euphoric"],
        "Malayalam":  ["malayalam dance euphoric"],
        "Any":        ["euphoric", "trance", "edm"],
    },
    "soulful": {
        "Hindi":      ["ghazal", "sufi", "qawwali", "nusrat fateh ali khan"],
        "Punjabi":    ["punjabi sufi", "gurdas maan", "satinder sartaaj"],
        "English":    ["soul", "neo soul", "rnb", "gospel"],
        "Tamil":      ["carnatic devotional", "sid sriram"],
        "Telugu":     ["carnatic", "sp balasubrahmanyam"],
        "Korean":     ["korean rnb", "k-rnb"],
        "Japanese":   ["japanese soul", "j-rnb"],
        "Spanish":    ["latin soul", "bolero", "trova"],
        "Portuguese": ["samba soulful", "mpb soul"],
        "French":     ["french soul", "nu soul"],
        "Arabic":     ["tarab", "arabic maqam", "arabic classical"],
        "Afrobeats":  ["afro soul", "highlife soul", "african gospel"],
        "Bengali":    ["rabindra sangeet", "nazrul sangeet", "baul"],
        "Urdu":       ["ghazal", "qawwali", "abida parveen"],
        "Kannada":    ["carnatic", "kannada devotional"],
        "Malayalam":  ["carnatic kerala", "kerala devotional"],
        "Any":        ["soul", "rnb", "gospel"],
    },
    "retro": {
        "Hindi":      ["old bollywood", "classic bollywood", "90s bollywood", "kishore kumar"],
        "Punjabi":    ["old punjabi songs", "classic bhangra"],
        "English":    ["retro", "classic rock", "80s", "70s"],
        "Tamil":      ["old kollywood", "ilayaraja"],
        "Telugu":     ["old tollywood", "sp balu"],
        "Korean":     ["korean retro", "trot"],
        "Japanese":   ["city pop", "j-pop 80s"],
        "Spanish":    ["latin retro", "cumbia clasica", "salsa clasica"],
        "Portuguese": ["mpb classica", "bossa nova vintage"],
        "French":     ["ye-ye", "chanson classique", "french 60s"],
        "Arabic":     ["arabic classics", "um kulthum"],
        "Afrobeats":  ["highlife classic", "fela kuti"],
        "Bengali":    ["classic rabindra sangeet"],
        "Urdu":       ["classic ghazal", "lata urdu"],
        "Kannada":    ["old kannada songs"],
        "Malayalam":  ["old malayalam songs", "yesudas"],
        "Any":        ["retro", "classic", "oldies"],
    },
    "dreamy": {
        "Hindi":      ["bollywood soft", "sufi dreamy", "ar rahman dreamy"],
        "Punjabi":    ["punjabi dreamy", "punjabi soft"],
        "English":    ["dream pop", "shoegaze", "ambient pop"],
        "Tamil":      ["ar rahman tamil dreamy", "kollywood dreamy"],
        "Telugu":     ["ar rahman telugu", "tollywood dreamy"],
        "Korean":     ["k-indie dreamy", "korean dream pop"],
        "Japanese":   ["city pop dreamy", "japanese dream pop"],
        "Spanish":    ["latin dreamy", "bossa nova dreamy"],
        "Portuguese": ["bossa nova", "mpb dreamy"],
        "French":     ["french dream pop", "chanson reveuse"],
        "Arabic":     ["arabic dreamy", "arabic ambient"],
        "Afrobeats":  ["afro dreamy", "alte"],
        "Bengali":    ["bengali dreamy"],
        "Urdu":       ["ghazal dreamy", "sufi soft"],
        "Kannada":    ["kannada soft dreamy"],
        "Malayalam":  ["malayalam dreamy"],
        "Any":        ["dream pop", "shoegaze"],
    },
    "cinematic": {
        "Hindi":      ["ar rahman", "bollywood cinematic", "hindi film score", "pritam"],
        "Punjabi":    ["punjabi cinematic"],
        "English":    ["cinematic", "film score", "epic", "hans zimmer"],
        "Tamil":      ["ar rahman tamil", "kollywood bgm", "harris jayaraj"],
        "Telugu":     ["mm keeravani", "tollywood bgm", "dsp bgm"],
        "Korean":     ["k-drama ost", "korean cinematic"],
        "Japanese":   ["anime ost", "joe hisaishi", "japanese film score"],
        "Spanish":    ["latin cinematic", "spanish film score"],
        "Portuguese": ["brazilian film score"],
        "French":     ["french film score", "yann tiersen"],
        "Arabic":     ["arabic cinematic", "fairuz"],
        "Afrobeats":  ["african cinematic"],
        "Bengali":    ["satyajit ray score"],
        "Urdu":       ["urdu cinematic"],
        "Kannada":    ["sandalwood bgm"],
        "Malayalam":  ["mollywood bgm", "m jayachandran"],
        "Any":        ["cinematic", "film score", "epic"],
    },
    "dark": {
        "Hindi":      ["hindi dark", "bollywood dark", "hindi noir"],
        "Punjabi":    ["punjabi dark"],
        "English":    ["dark", "darkwave", "post-punk", "goth"],
        "Tamil":      ["kollywood dark", "tamil dark songs"],
        "Telugu":     ["tollywood dark"],
        "Korean":     ["k-pop dark", "korean dark pop"],
        "Japanese":   ["japanese dark", "visual kei"],
        "Spanish":    ["latin dark", "dark flamenco"],
        "Portuguese": ["fado dark", "trap dark brasil"],
        "French":     ["french darkwave", "new wave francaise"],
        "Arabic":     ["arabic dark"],
        "Afrobeats":  ["afrotrap dark"],
        "Bengali":    ["bengali dark"],
        "Urdu":       ["dark ghazal"],
        "Kannada":    ["kannada dark"],
        "Malayalam":  ["mollywood dark"],
        "Any":        ["dark", "darkwave", "goth"],
    },
    "intense": {
        "Hindi":      ["bollywood intense", "hindi action songs", "hindi rock"],
        "Punjabi":    ["punjabi intense"],
        "English":    ["metal", "hardcore", "intense", "heavy metal"],
        "Tamil":      ["kollywood action", "anirudh action"],
        "Telugu":     ["tollywood action", "dsp action"],
        "Korean":     ["k-rock", "korean metal"],
        "Japanese":   ["jrock intense", "j-metal"],
        "Spanish":    ["latin metal", "latin rock intense"],
        "Portuguese": ["rock brasileiro", "heavy metal brasil"],
        "French":     ["metal francais"],
        "Arabic":     ["arabic rock", "arabic metal"],
        "Afrobeats":  ["naija drill"],
        "Bengali":    ["bengali rock intense"],
        "Urdu":       ["qawwali intense"],
        "Kannada":    ["kannada intense"],
        "Malayalam":  ["mollywood action"],
        "Any":        ["metal", "intense", "hardcore"],
    },
    "rock": {
        "Hindi":      ["hindi rock", "indian rock", "bollywood rock"],
        "Punjabi":    ["punjabi rock"],
        "English":    ["rock", "alternative rock", "indie rock", "classic rock"],
        "Tamil":      ["tamil rock", "kollywood rock"],
        "Telugu":     ["telugu rock"],
        "Korean":     ["k-rock", "korean rock"],
        "Japanese":   ["j-rock", "japanese rock"],
        "Spanish":    ["rock en espanol", "latin rock"],
        "Portuguese": ["rock brasileiro"],
        "French":     ["rock francais"],
        "Arabic":     ["arabic rock"],
        "Afrobeats":  ["afrorock"],
        "Bengali":    ["bangla rock"],
        "Urdu":       ["pakistani rock", "junoon"],
        "Kannada":    ["kannada rock"],
        "Malayalam":  ["malayalam rock"],
        "Any":        ["rock", "alternative rock"],
    },
    "indie_folk": {
        "Hindi":      ["indian folk", "hindi folk", "sufi folk", "rajasthani folk"],
        "Punjabi":    ["punjabi folk"],
        "English":    ["indie folk", "folk", "folk pop"],
        "Tamil":      ["tamil folk", "carnatic folk"],
        "Telugu":     ["telugu folk", "telangana folk"],
        "Korean":     ["k-folk", "korean indie folk"],
        "Japanese":   ["japanese folk", "j-folk"],
        "Spanish":    ["trova", "nueva cancion", "flamenco folk"],
        "Portuguese": ["mpb folk", "forro folk"],
        "French":     ["folk francais", "chanson folk"],
        "Arabic":     ["arabic folk", "arabic traditional"],
        "Afrobeats":  ["african folk", "highlife folk"],
        "Bengali":    ["baul", "folk bengali"],
        "Urdu":       ["lok geet", "punjabi folk urdu"],
        "Kannada":    ["kannada folk", "janapada songs"],
        "Malayalam":  ["kerala folk", "mappila songs"],
        "Any":        ["indie folk", "folk"],
    },
    "ambient": {
        "Hindi":      ["raga ambient", "sitar ambient", "indian classical ambient"],
        "Punjabi":    ["sarangi ambient"],
        "English":    ["ambient", "drone", "modern classical", "neoclassical"],
        "Tamil":      ["carnatic ambient", "ar rahman ambient"],
        "Telugu":     ["carnatic ambient"],
        "Korean":     ["korean ambient"],
        "Japanese":   ["japanese ambient", "kankyo ongaku"],
        "Spanish":    ["latin ambient", "flamenco ambient"],
        "Portuguese": ["bossa nova ambient"],
        "French":     ["french ambient"],
        "Arabic":     ["oud ambient", "maqam ambient"],
        "Afrobeats":  ["african ambient"],
        "Bengali":    ["indian classical ambient"],
        "Urdu":       ["sufi ambient"],
        "Kannada":    ["carnatic ambient"],
        "Malayalam":  ["carnatic ambient"],
        "Any":        ["ambient", "drone", "modern classical"],
    },
    "desi": {
        "Hindi":      ["bollywood", "hindi film", "desi pop"],
        "Punjabi":    ["punjabi", "bhangra", "punjabi pop"],
        "Tamil":      ["kollywood", "tamil film"],
        "Telugu":     ["tollywood", "telugu film"],
        "Bengali":    ["bengali film"],
        "Urdu":       ["urdu film", "pakistan pop"],
        "Kannada":    ["sandalwood", "kannada film"],
        "Malayalam":  ["mollywood", "malayalam film"],
        "Any":        ["bollywood", "desi"],
    },
    "punjabi": {
        "Punjabi":    ["bhangra", "punjabi pop", "desi club", "diljit dosanjh"],
        "Hindi":      ["bhangra", "punjabi pop"],
        "Any":        ["bhangra", "punjabi"],
        # ── Mood-variant overrides ───────────────────────────────────────────
        # When secondary vibe is chill/dark/dreamy/calm (e.g. "late night punjabi",
        # "chill punjabi", "soft punjabi night"), we pivot to soft/late-night tags
        # instead of party bhangra. Keyed as "Any__<secondary_vibe>".
        "Any__chill":       ["punjabi sad songs", "ap dhillon", "punjabi lofi", "punjabi chill"],
        "Any__dark":        ["punjabi sad songs", "punjabi ballad", "punjabi dark", "dard"],
        "Any__calm":        ["punjabi sad songs", "punjabi romantic", "punjabi ballad"],
        "Any__dreamy":      ["ap dhillon", "punjabi lofi", "punjabi soft", "punjabi romantic"],
        "Any__heartbreak":  ["punjabi sad songs", "b praak", "punjabi ballad", "dard"],
        "Any__romantic":    ["punjabi romantic", "ap dhillon", "punjabi love songs"],
        "Any__soulful":     ["punjabi sufi", "satinder sartaaj", "punjabi classical"],
        "Any__ambient":     ["punjabi lofi", "punjabi acoustic", "sufi punjabi"],
    },
    "punjabi_soft": {
        # FIX: Old tags ("b praak", "ap dhillon") are ARTIST names, not Last.fm tags.
        # Last.fm tag.gettoptracks returns 0 results for artist names.
        # Use real community tags that actually have track pools on Last.fm.
        "Punjabi":    ["punjabi sad songs", "punjabi romantic", "punjabi ballad", "dard"],
        "Hindi":      ["punjabi sad songs", "filmi sad", "punjabi ballad"],
        "Any":        ["punjabi sad songs", "punjabi ballad", "dard", "punjabi soft"],
    },
    "haryanvi": {
        # FIX: Expanded with real Last.fm tags that return results.
        # "ragini" is too niche (< 5 tracks). Added mainstream haryanvi tags.
        "Hindi":      ["haryanvi", "haryanvi folk songs", "haryanvi pop", "desi"],
        "Any":        ["haryanvi", "haryanvi folk songs", "desi folk"],
    },
    "hyperpop": {
        "English":    ["hyperpop", "digicore", "pc music", "bubblegum bass"],
        "Korean":     ["k-pop hyperpop"],
        "Japanese":   ["j-hyperpop"],
        "Spanish":    ["latin hyperpop"],
        "Any":        ["hyperpop", "digicore"],
    },
    "industrial": {
        "English":    ["industrial", "ebm", "dark techno", "noise"],
        "French":     ["indus francais", "ebm francais"],
        "Any":        ["industrial", "ebm", "dark techno"],
    },
    "tropical": {
        "Spanish":    ["reggaeton", "latin dance", "cumbia", "dancehall"],
        "Portuguese": ["baile funk", "pagode", "axe"],
        "English":    ["tropical", "dancehall", "reggae", "afrobeats"],
        "Afrobeats":  ["afrobeats", "amapiano", "naija pop"],
        "Any":        ["reggaeton", "afrobeats", "dancehall"],
    },
    "country": {
        "English":    ["country", "americana", "country pop", "country rock"],
        "Spanish":    ["corridos", "norteno", "ranchera"],
        "Portuguese": ["sertanejo", "country brasil"],
        "Any":        ["country", "americana"],
    },
}


def get_vibe_tags(dominant_vibe: str, language: str, fallback_tag: str, secondary_vibe: str | None = None) -> list[str]:
    """
    Return the ordered list of Last.fm tags for a vibe×language combo.
    
    When secondary_vibe is present (e.g. dominant=punjabi, secondary=chill),
    we first check for a mood-variant key like "Any__chill" in the vibe map.
    This prevents "late night punjabi" from pulling party bhangra tags when
    the secondary signal is clearly chill/dark/soft.

    Priority order:
    1. VIBE_TAG_MATRIX[vibe][language]  — most specific
    2. LANGUAGE_TAG_MAP[language][vibe] — regional language override (prevents
       Telugu/Malayalam/Tamil/Kannada falling through to generic "Any" trap/club tags)
    3. VIBE_TAG_MATRIX[vibe][Any]       — generic fallback
    4. [fallback_tag]                   — last resort
    """
    # Regional languages that should NEVER fall back to generic "Any" tags
    REGIONAL_PRIORITY = {
        "Telugu", "Tamil", "Malayalam", "Kannada", "Bengali",
        "Urdu", "Arabic", "Spanish", "Portuguese", "French",
    }

    vibe_map = VIBE_TAG_MATRIX.get(dominant_vibe, {})
    
    tags = None
    
    # 1. Try exact language + secondary mood variant (e.g. "Punjabi__chill")
    if secondary_vibe:
        mood_key_lang = f"{language}__{secondary_vibe}"
        mood_key_any  = f"Any__{secondary_vibe}"
        tags = vibe_map.get(mood_key_lang) or vibe_map.get(mood_key_any)
        if tags:
            logger.info(f"[TagMatrix] Mood variant hit: {dominant_vibe}×{language} + secondary={secondary_vibe} → {tags}")
    
    # 2. Try VIBE_TAG_MATRIX exact language match
    if not tags:
        tags = vibe_map.get(language)
    
    # 3. For regional languages: try LANGUAGE_TAG_MAP before falling to generic "Any"
    #    This ensures "hype + Telugu" → "tollywood" not "trap/phonk"
    if not tags and language in REGIONAL_PRIORITY:
        lang_map = LANGUAGE_TAG_MAP.get(language, {})
        regional_tag = lang_map.get(dominant_vibe) or lang_map.get("default")
        if regional_tag:
            tags = [regional_tag]
            logger.info(f"[TagMatrix] Regional override: {dominant_vibe}×{language} → {regional_tag}")
    
    # 4. Generic Any fallback
    if not tags:
        tags = vibe_map.get("Any") or [fallback_tag]
    
    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        tc = t.strip().lower()
        if tc not in seen:
            seen.add(tc)
            result.append(t)
    return result[:4]

# END VIBE_TAG_MATRIX ══════════════════════════════════════════════════════════

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class VibeRequest(BaseModel):
    text: str
    language: str | None = "Any"    # e.g. Any / Hindi / Punjabi / Korean / Japanese / Tamil
    artist_focus: int = 50 
    nicheness: int = 50    
    bpm_focus: int = 50
    track_limit: int = 5
    use_secondary_vibe: bool = False
    override_genre: str | None = None
    override_artist: str | None = None
    dismiss_detected_artist: bool = False  # User dismissed the artist lock tag — skip entity injection

class TrackInfo(BaseModel):
    title: str
    artist: str
    spotify_uri: str
    apple_uri: str
    preview_url: str | None = None
    cover_art: str | None = None

class VibeResponse(BaseModel):
    request_id: str           # NEW: VibeRequest row id, needed for feedback linking
    dominant_vibe: str
    confidence: float
    bpm_range: str
    genres: list[str]
    matched_keywords: list[str]
    secondary_vibe: str | None = None
    secondary_confidence: float = 0.0
    detected_artist: str | None = None
    detected_song: str | None = None
    tracks: list[TrackInfo] = []

class FeedbackRequest(BaseModel):
    """
    Sent by the frontend when a user thumbs up / thumbs down a track.
    signal:   1 = liked, -1 = skipped/disliked, 0 = played through (implicit)
    position: 1-indexed rank of the track in the returned list
    preview_seconds: how long they listened before rating (optional)
    """
    request_id: str       # VibeRequest.id from the analysis response
    track_title: str
    track_artist: str
    signal: int           # must be -1, 0, or 1
    position: int
    preview_seconds: int | None = None

# ---------------------------------------------------------
# Auth Helpers
# ---------------------------------------------------------
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password[:72])

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------
# Network Retry Helper (v2.0 — Async-safe, non-blocking)
# ---------------------------------------------------------
# CRITICAL FIX: The old version used time.sleep() inside an async app, which
# blocked the entire FastAPI event loop during retries. This version uses
# asyncio.sleep() so all concurrent requests continue while one backs off.
# ---------------------------------------------------------

async def _fetch_with_retry(url: str, label: str, timeout: int = 5, max_retries: int = 3) -> dict | None:
    """
    Async GET with exponential backoff. Never blocks the event loop.
    Delays between retries: 1s → 2s → 4s.
    Returns parsed JSON dict, or None after all retries exhausted.
    """
    if _AIOHTTP_AVAILABLE:
        for attempt in range(max_retries):
            try:
                connector = _aiohttp.TCPConnector(limit=100)
                timeout_cfg = _aiohttp.ClientTimeout(total=timeout)
                async with _aiohttp.ClientSession(
                    connector=connector,
                    headers={"User-Agent": "VibeFinderAI/2.0"},
                    timeout=timeout_cfg,
                ) as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        logger.warning(f"[Retry {attempt+1}] {label} — HTTP {resp.status}")
            except Exception as e:
                wait = 2 ** attempt
                if attempt < max_retries - 1:
                    logger.warning(f"[Retry {attempt+1}/{max_retries}] {label} — {e}. Backing off {wait}s...")
                    await asyncio.sleep(wait)  # ← non-blocking!
                else:
                    logger.error(f"{label} failed after {max_retries} attempts: {e}")
        return None
    else:
        # Graceful degradation: run sync urllib in a thread so we don't block
        import urllib.request as _urllib_req
        def _sync_fetch():
            for attempt in range(max_retries):
                try:
                    req = _urllib_req.Request(url, headers={"User-Agent": "VibeFinderAI/2.0"})
                    with _urllib_req.urlopen(req, timeout=timeout) as r:
                        return json.loads(r.read().decode())
                except Exception as e:
                    wait = 2 ** attempt
                    if attempt < max_retries - 1:
                        time.sleep(wait)
                    else:
                        logger.error(f"{label} failed after {max_retries} attempts: {e}")
            return None
        return await asyncio.to_thread(_sync_fetch)


# ---------------------------------------------------------
# Free Music Fetchers (Last.fm + iTunes) — All Async
# ---------------------------------------------------------

async def fetch_lastfm_tracks_sync(genre: str, limit: int = 200):
    """Hits the free Last.fm API to pull trending tracks by tag."""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        logger.error("LASTFM_API_KEY not set in environment. Cannot fetch tracks.")
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm genre fetch for '{genre}'")
    if data:
        tracks = data.get("tracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

async def fetch_lastfm_artist_tracks_sync(artist: str, limit: int = 200):
    """Hits the free Last.fm API to pull a SPECIFIC artist's discography."""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={urllib.parse.quote(artist)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm artist fetch for '{artist}'")
    if data:
        tracks = data.get("toptracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

async def fetch_lastfm_track_search_sync(query: str, limit: int = 100):
    """FALLBACK: Directly searches Last.fm for literal track names."""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={urllib.parse.quote(query)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm direct track search for '{query}'")
    if data:
        tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist")} for t in tracks]
    return []

async def fetch_itunes_data_sync(title: str, artist: str):
    """Silently hits the free iTunes API to grab the .m4a preview & cover art."""
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    data = await _fetch_with_retry(url, label=f"iTunes preview for '{title}' by '{artist}'", timeout=3, max_retries=2)
    if data and data.get("resultCount", 0) > 0:
        track = data["results"][0]
        return {"preview_url": track.get("previewUrl"), "cover_art": track.get("artworkUrl100")}
    return {"preview_url": None, "cover_art": None}

async def fetch_lastfm_tracks(genre: str, limit: int = 200):
    return await fetch_lastfm_tracks_sync(genre, limit)

async def fetch_lastfm_artist_tracks(artist: str, limit: int = 200):
    return await fetch_lastfm_artist_tracks_sync(artist, limit)

async def fetch_lastfm_track_search(query: str, limit: int = 100):
    return await fetch_lastfm_track_search_sync(query, limit)

async def fetch_itunes_preview(title: str, artist: str):
    return await fetch_itunes_data_sync(title, artist)

# ---------------------------------------------------------
# The Mathematical AI (Knob Scoring Engine)
# ---------------------------------------------------------
def get_base_title(title: str) -> str:
    """Strips out ' - Remix', ' (Edit)', ' feat', to get the true original track name."""
    t = title.lower()
    t = t.split(" - ")[0]
    t = t.split(" (")[0]
    t = t.split(" feat")[0]
    t = t.split(" ft")[0]
    return t.strip()

def filter_and_score_tracks(tracks: list, request: VibeRequest, vibe_data: dict, is_fallback: bool = False):
    """
    Scoring engine v2.0 — now uses real audio features from TrackFeatureCache.

    Scoring layers (highest → lowest priority):
      1. Exact song match (+100)
      2. Artist match — scaled by ARTIST knob (+0 to +80)
      3. Vibe/genre keyword match (+30/+20)
      4. BPM match:
         - If track is in TrackFeatureCache: compares real tempo to BPM knob target
         - Fallback: title-string heuristics ("remix", "acoustic", etc.)
      5. Energy/mood match from real audio features:
         - BPM knob high (>60): rewards high energy tracks
         - BPM knob low (<40): rewards low energy, high relaxed mood
         - Dominant vibe 'heartbreak'/'dark': rewards high moodSad, low moodParty
         - Dominant vibe 'party'/'euphoric': rewards high moodParty, high energy
      6. NICHENESS knob: shifts between chart-toppers (low) and deep cuts (high)
         - Low (<40): rewards tracks near top of Last.fm chart (low index)
         - High (>60): penalizes chart-toppers, rewards deep-pool tracks
      7. Anti-spam blocklist penalty
      8. Global popularity decay
    """
    prompt_lower = request.text.lower()
    dominant_vibe = vibe_data.get("dominant_vibe", "")
    
    detected_song = (vibe_data.get("detected_song") or "").lower()
    detected_artist = (vibe_data.get("detected_artist") or "").lower()
    target_genre_override = (vibe_data.get("target_genre_override") or vibe_data.get("dominant_vibe", "")).lower()

    # BPM knob → target tempo range
    # knob 0-20 = very slow (50-75 BPM), 20-40 = slow (75-95), 40-60 = mid (neutral),
    # 60-80 = fast (110-140), 80-100 = very fast (140+)
    bpm_knob = request.bpm_focus  # 0-100
    if bpm_knob <= 20:
        target_bpm_low, target_bpm_high = 50, 80
    elif bpm_knob <= 40:
        target_bpm_low, target_bpm_high = 70, 100
    elif bpm_knob <= 60:
        target_bpm_low, target_bpm_high = 85, 130  # neutral — wide range
    elif bpm_knob <= 80:
        target_bpm_low, target_bpm_high = 110, 150
    else:
        target_bpm_low, target_bpm_high = 135, 220

    # Artist knob: 0 = artist match doesn't matter, 100 = maximally prioritize artist matches
    # Scaled so knob=50 gives the old +40, knob=100 gives +80, knob=0 gives +0
    artist_weight = (request.artist_focus / 50.0) * 40  # 0 → 80

    # Nicheness knob: controls which part of the pool to prefer
    # <40: prefer top of chart (low index), >60: prefer deep cuts (high index)
    nicheness = request.nicheness  # 0-100
    pool_size = max(len(tracks), 1)

    fast_markers = ["remix", "mix", "edit", "club", "fast", "speed", "drum"]
    slow_markers = ["acoustic", "slowed", "reverb", "chill", "lofi", "ambient", "slow"]

    # Vibe → target audio profile (used when TrackFeatureCache has real data)
    _VIBE_AUDIO_PROFILE: dict[str, dict] = {
        "heartbreak":    {"valence_max": 0.45, "moodSad_min": 0.45, "energy_max": 0.65},
        "dark":          {"valence_max": 0.40, "energy_max": 0.70, "moodAggressive_min": 0.15},
        "calm":          {"energy_max": 0.45, "moodRelaxed_min": 0.40},
        "ambient":       {"energy_max": 0.35, "moodRelaxed_min": 0.50},
        "focus":         {"energy_max": 0.60, "moodRelaxed_min": 0.30},
        "chill":         {"energy_max": 0.65, "moodRelaxed_min": 0.25},
        "party":         {"moodParty_min": 0.45, "energy_min": 0.55},
        "euphoric":      {"moodParty_min": 0.40, "energy_min": 0.50, "valence_min": 0.45},
        "hype":          {"energy_min": 0.65, "moodAggressive_min": 0.20},
        "intense":       {"energy_min": 0.70, "moodAggressive_min": 0.35},
        "soulful":       {"valence_min": 0.30, "moodHappy_min": 0.25},
        "happy":         {"valence_min": 0.50, "moodHappy_min": 0.45},
        "romantic":      {"valence_min": 0.35, "moodSad_max": 0.40},
        "dreamy":        {"energy_max": 0.55, "moodRelaxed_min": 0.25},
    }
    vibe_profile = _VIBE_AUDIO_PROFILE.get(dominant_vibe, {})

    scored_tracks = []
    for i, t in enumerate(tracks):
        title = t.get("title", "").lower()
        artist = t.get("artist", "").lower()
        score = 0.0

        # Fallback mode baseline
        if is_fallback:
            score += 50

        # 1. EXACT SONG MATCH
        if detected_song and (detected_song in title or title in detected_song):
            score += 100

        # 2. ARTIST MATCH — now fully scaled by ARTIST knob
        if (detected_artist and detected_artist == artist) or artist in prompt_lower:
            score += artist_weight

        # 3. VIBE / GENRE KEYWORD MATCH
        if target_genre_override and (target_genre_override in title or target_genre_override in artist):
            score += 30
        for kw in vibe_data.get("matched_keywords", []):
            if kw.lower() in title or kw.lower() in artist:
                score += 20

        # 4+5. AUDIO FEATURE SCORING — real data from TrackFeatureCache if available
        # Primary lookup by title|artist; fallback to ISRC code for cross-database matching
        feat_key = f"{title}|{artist}"
        feat = TRACK_FEATURE_INDEX.get(feat_key)
        if not feat and t.get("isrc"):
            # ISRC fallback: high-precision track matching when title/artist spelling differs across APIs
            feat = app.state.isrc_feature_index.get(t["isrc"].upper())

        if feat:
            # ── REAL BPM SCORING ─────────────────────────────────────────────
            real_bpm = feat.get("tempo")
            if real_bpm is not None:
                if target_bpm_low <= real_bpm <= target_bpm_high:
                    # Perfect match — bonus scales with how far from neutral the knob is
                    bpm_knob_strength = abs(bpm_knob - 50) / 50.0  # 0 at center, 1 at extremes
                    score += 35 * bpm_knob_strength
                else:
                    # How far outside the window? Penalize proportionally
                    overshoot = min(abs(real_bpm - target_bpm_low), abs(real_bpm - target_bpm_high))
                    penalty = min(overshoot / 30.0, 1.0) * 20 * (abs(bpm_knob - 50) / 50.0)
                    score -= penalty

            # ── REAL ENERGY SCORING ──────────────────────────────────────────
            energy = feat.get("energy")
            if energy is not None:
                if bpm_knob > 60:
                    # High BPM knob = user wants energetic tracks
                    energy_strength = (bpm_knob - 50) / 50.0
                    score += energy * 25 * energy_strength
                elif bpm_knob < 40:
                    # Low BPM knob = user wants chill/low-energy
                    energy_strength = (50 - bpm_knob) / 50.0
                    score += (1.0 - energy) * 25 * energy_strength

            # ── VIBE MOOD PROFILE SCORING ─────────────────────────────────────
            mood_score = 0.0
            profile_hits = 0
            for feat_key_name, threshold in vibe_profile.items():
                feat_name = feat_key_name.split("_")[0] + feat_key_name[feat_key_name.index("_"):]  # "moodSad_min" → "moodSad"
                # Parse: "energy_min", "valence_max", "moodSad_min" etc.
                parts = feat_key_name.rsplit("_", 1)
                feat_name_clean = parts[0]  # "energy", "valence", "moodSad"
                direction = parts[1]        # "min" or "max"
                val = feat.get(feat_name_clean)
                if val is None:
                    continue
                if direction == "min" and val >= threshold:
                    mood_score += (val - threshold) * 30
                    profile_hits += 1
                elif direction == "max" and val <= threshold:
                    mood_score += (threshold - val) * 30
                    profile_hits += 1
                elif direction == "min" and val < threshold:
                    mood_score -= (threshold - val) * 15  # soft penalty for mismatch
                elif direction == "max" and val > threshold:
                    mood_score -= (val - threshold) * 15
            if profile_hits > 0:
                score += mood_score / max(len(vibe_profile), 1)

        else:
            # ── HEURISTIC FALLBACK (no real data) — old behaviour preserved ──
            fast_hit = any(m in title for m in fast_markers)
            slow_hit = any(m in title for m in slow_markers)
            if bpm_knob > 60:
                bpm_strength = (bpm_knob - 50) / 50.0
                if fast_hit:
                    score += 30 * bpm_strength
                elif slow_hit:
                    score -= 20 * bpm_strength
            elif bpm_knob < 40:
                bpm_strength = (50 - bpm_knob) / 50.0
                if slow_hit:
                    score += 30 * bpm_strength
                elif fast_hit:
                    score -= 20 * bpm_strength

        # REMIX EXCLUSION
        if "remix" in title or "edit" in title or "instrumental" in title:
            score -= 15

        # 6. NICHENESS KNOB — controls chart depth
        # nicheness < 40: prefer chart-toppers (low pool index = many listeners)
        # nicheness > 60: prefer deep cuts (high pool index = fewer listeners)
        # nicheness 40-60: neutral, mild global popularity bonus
        position_pct = i / pool_size  # 0.0 = top of chart, 1.0 = deepest cut
        if nicheness < 40:
            # Mainstream mode: boost tracks near top of chart
            mainstream_strength = (40 - nicheness) / 40.0
            score += (1.0 - position_pct) * 25 * mainstream_strength
        elif nicheness > 60:
            # Niche mode: boost tracks deeper in the pool
            niche_strength = (nicheness - 60) / 40.0
            score += position_pct * 25 * niche_strength
        else:
            # Neutral: mild global popularity bonus (old behavior)
            score += max(0.0, (1.0 - (i / max(pool_size, 100))) * 10.0)

        # 7. ANTI-SPAM BLOCKLIST
        track_ident_bl = f"{title}|{artist}"
        if track_ident_bl in TRACK_BLOCKLIST:
            score -= 40

        score += random.uniform(0, 1.5)
        t["score"] = round(score, 4)   # ← stamp score onto the dict before stashing
        scored_tracks.append((score, t))
        
    scored_tracks.sort(key=lambda x: x[0], reverse=True)

    # 🚨 BRO FIX: Bug 3 - Safety net for restrictive knobs
    # If the engine completely starves the pool and max score is < 15, bump it
    # so we don't return garbage that fails your Viability Criterion.
    if scored_tracks and scored_tracks[0][0] < 15.0:
        boost = 15.5 - scored_tracks[0][0]
        logger.info(f"Restrictive pool detected (max score {scored_tracks[0][0]}). Applying +{boost:.1f} safety boost.")
        scored_tracks = [(s + boost, t) for s, t in scored_tracks]
    
    # 6. DIVERSITY GUARD & STRICT DEDUPLICATION
    final_selection = []
    skipped_for_diversity = []
    artist_counts = {}
    seen_base_titles = set()
    
    # 🚨 BRO FIX: Bug 2 - Force Artist diversity collapse at limit >= 40.
    # Even if they crank the dial, we cap a single artist to ~60% of the playlist
    # or max 15 tracks, so related artists STILL get a chance to shine.
    max_artist_tracks = 2
    if request.override_artist or request.artist_focus >= 80:
        max_artist_tracks = max(2, min(int(request.track_limit * 0.60), 15))

    for _, t in scored_tracks:
        art = t.get("artist", "").lower()
        base_t = get_base_title(t.get("title", ""))
        track_ident = f"{art}|{base_t}"
        
        if track_ident in seen_base_titles:
            continue
            
        seen_base_titles.add(track_ident)
        
        # Anti-Monopoly Guard
        if artist_counts.get(art, 0) >= max_artist_tracks:
            skipped_for_diversity.append(t)
            continue 
                
        final_selection.append(t)
        artist_counts[art] = artist_counts.get(art, 0) + 1
        
        if len(final_selection) >= request.track_limit:
            break
            
    # 7. THE FALLBACK LOOP
    if len(final_selection) < request.track_limit:
        for t in skipped_for_diversity:
            final_selection.append(t)
            if len(final_selection) >= request.track_limit:
                break
                
    return final_selection

# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "VibeFinderAI API is operational."}

# ---------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Lightweight liveness probe for deployment platforms (Railway, Render, etc.).
    Returns DB connectivity status alongside uptime signal.
    """
    try:
        # Lightweight DB ping — just count a tiny table
        await db.user.count()
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check DB ping failed: {e}")
        db_status = "degraded"
    return {"status": "ok", "db": db_status, "service": "VibeFinderAI"}

# ---------------------------------------------------------
# User Taste Profile — closes the feedback loop
# ---------------------------------------------------------
@app.get("/api/user/taste")
async def get_user_taste(token: str = Depends(oauth2_scheme)):
    """
    Returns the authenticated user's taste profile derived from their
    accumulated feedback history (thumbs up/down signals).

    Used to surface personalized insights and can be fed back into
    future vibe requests as soft priors for the recommendation engine.

    Response includes:
    - top_vibes: vibes the user has rated positively most often
    - top_artists: artists the user has liked most
    - disliked_artists: artists the user has consistently downvoted
    - total_ratings: total feedback rows for this user
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        # Pull all feedback for this user
        feedbacks = await db.trackfeedback.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"},
        )

        if not feedbacks:
            return {
                "total_ratings": 0,
                "top_vibes": [],
                "top_artists": [],
                "disliked_artists": [],
                "message": "No feedback data yet — rate some tracks to build your taste profile!"
            }

        # Pull VibeRequests to get vibe context for each feedback
        vibe_request_ids = list({f.vibeRequestId for f in feedbacks if f.vibeRequestId})
        vibe_requests = {}
        if vibe_request_ids:
            rows = await db.viberequest.find_many(
                where={"id": {"in": vibe_request_ids}}
            )
            vibe_requests = {r.id: r for r in rows}

        # Tally vibe scores (liked = +1, disliked = -1, neutral = 0)
        vibe_score: dict[str, float]   = {}
        artist_score: dict[str, float] = {}

        for fb in feedbacks:
            signal = fb.signal  # 1, 0, -1
            artist = (fb.trackArtist or "").strip().lower()

            # Artist tally
            if artist:
                artist_score[artist] = artist_score.get(artist, 0.0) + signal

            # Vibe tally — look up the VibeRequest for vibe context
            if fb.vibeRequestId and fb.vibeRequestId in vibe_requests:
                vr = vibe_requests[fb.vibeRequestId]
                vibe = vr.dominantVibe or ""
                if vibe:
                    vibe_score[vibe] = vibe_score.get(vibe, 0.0) + signal

        # Sort and trim
        top_vibes = sorted(
            [(v, round(s, 1)) for v, s in vibe_score.items() if s > 0],
            key=lambda x: -x[1]
        )[:5]

        top_artists = sorted(
            [(a, round(s, 1)) for a, s in artist_score.items() if s > 0],
            key=lambda x: -x[1]
        )[:10]

        disliked_artists = sorted(
            [(a, round(s, 1)) for a, s in artist_score.items() if s < 0],
            key=lambda x: x[1]
        )[:5]

        return {
            "total_ratings": len(feedbacks),
            "top_vibes":      [{"vibe": v, "score": s} for v, s in top_vibes],
            "top_artists":    [{"artist": a, "score": s} for a, s in top_artists],
            "disliked_artists": [{"artist": a, "score": s} for a, s in disliked_artists],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/api/user/taste error: {e}")
        raise HTTPException(status_code=500, detail="Failed to build taste profile")

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    existing_user = await db.user.find_first(where={"OR": [{"email": user.email}, {"username": user.username}]})
    if existing_user: raise HTTPException(status_code=400, detail="Identity already exists")
    hashed_pwd = get_password_hash(user.password)
    new_user = await db.user.create(data={"email": user.email, "username": user.username, "hashedPassword": hashed_pwd})
    logger.info(f"New user registered: {user.username}")
    return {"message": "Success", "user_id": new_user.id}

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.user.find_unique(where={"username": form_data.username})
    if not user or not verify_password(form_data.password, user.hashedPassword):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = create_access_token(data={"sub": user.id})
    logger.info(f"User authenticated: {form_data.username}")
    return {"access_token": token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user = await db.user.find_unique(where={"id": user_id})
        return user
    except: raise HTTPException(status_code=401)

@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    """Refined analysis route with zero-results fallback logic and telemetry."""
    
    # Validate token early — prevents null user_id poisoning the DB log
    try:
        _pre_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        _pre_user_id = _pre_payload.get("sub")
        if not _pre_user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    logger.info(f"--- NEW REQUEST: Analyzing Vibe ---")
    logger.info(f"Prompt: '{request.text}' | Limit: {request.track_limit}")
    
    # 1. NLP Core Analysis
    # Normalize typos before vibe detection
    request = request.model_copy(update={"text": normalize_input(request.text)})

    vibe_data = vibe_engine.analyze_vibe_algorithm(
        text=request.text,
        artist_focus=request.artist_focus, 
        genre_focus=50,
        bpm_focus=request.bpm_focus
    )
    
    # 1.5 GEMINI FALLBACK ENHANCEMENT
    # If confidence is low, try Gemini Flash to boost accuracy on novel vibes/slang
    if gemini_analyzer.should_enhance(vibe_data, request.text):
        logger.info(f"[Gemini] Vibe confidence low ({vibe_data.get('confidence')}). Requesting enhancement...")
        vibe_data = await gemini_analyzer.enhance(
            prompt=request.text,
            language=request.language,
            heuristic_result=vibe_data
        )
        logger.info(f"[Gemini] Enhancement complete. New confidence: {vibe_data.get('confidence')}")
    
    prompt_lower = request.text.lower()
    detected_artist = request.override_artist
    detected_song = None
    
    # 2. DEEP ENTITY SCAN (Anti-Hijack Guard Added)
    # 🚨 BRO FIX: Bug 4 - Nuked the inner COMMON_WORDS_BLACKLIST duplicate that was missing v9.0 words!
    # It now correctly uses the global COMMON_WORDS_BLACKLIST defined at the top of the file.

    # v1.2 Fix #1 — Negative Intent Shield
    # If any of these tokens immediately precede a matched entity, we discard the lock.
    NEGATION_TOKENS = {"not", "no", "don't", "dont", "nothing", "avoid", "except", "without", "skip", "never"}

    def _is_negated_entity(entity: str, text: str) -> bool:
        """Returns True if a negation token immediately precedes the entity in the text."""
        pattern = rf'\b({"|".join(re.escape(n) for n in NEGATION_TOKENS)})\s+{re.escape(entity)}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    # v1.2 Fix #3 — Standalone Lock Sensitivity
    # Only allow a song-only lock (no artist match) on SHORT prompts (< 10 words).
    prompt_word_count = len(prompt_lower.split())
    
    if not detected_artist:
        try:
            db_artists = await db.artistdirectory.find_many()
            for a in db_artists:
                # 🚨 FIX: Skip DB entries with dot-placeholder names (bad data migration)
                if not a.name or not re.search(r"\w", a.name):  # skip dot/symbol-only names like "..." or "!!!"
                    continue
                artist_name = _normalize_for_matching(a.name)
                _prompt_norm = _normalize_for_matching(request.text)
                artist_pattern = rf'\b{re.escape(artist_name)}\b'
                if re.search(artist_pattern, _prompt_norm):
                    # v1.2 Fix #1: Negative Intent Shield — discard if negated
                    if _is_negated_entity(artist_name, prompt_lower):
                        logger.info(f"Entity Scanner: Negation detected before artist '{a.name}' — lock discarded.")
                        continue
                    detected_artist = a.name
                    logger.info(f"Entity Scanner Locked Artist: {detected_artist}")
                    if a.songs:
                        song_list = [s.strip().lower() for s in a.songs.split(",")]
                        for s in song_list:
                            if s and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                                # v1.2 Fix #1: Negative Intent Shield on song too
                                if _is_negated_entity(s, prompt_lower):
                                    logger.info(f"Entity Scanner: Negation detected before song '{s}' — song lock discarded.")
                                    continue
                                detected_song = s
                                logger.info(f"Entity Scanner Locked Song: {detected_song}")
                                break
                    break
                elif a.songs:
                    song_list = [s.strip().lower() for s in a.songs.split(",")]
                    for s in song_list:
                        # NEW GUARD: Only lock if the song is >3 chars AND not in the blacklist!
                        if len(s) > 3 and s not in COMMON_WORDS_BLACKLIST and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                            # v1.2 Fix #1: Negative Intent Shield
                            if _is_negated_entity(s, prompt_lower):
                                logger.info(f"Entity Scanner: Negation detected before song '{s}' — standalone lock discarded.")
                                continue
                            # v1.2 Fix #3: Standalone Lock Sensitivity — only lock on short prompts
                            if prompt_word_count >= 10:
                                logger.info(f"Entity Scanner: Long prompt ({prompt_word_count} words) — skipping standalone song lock for '{s}'.")
                                continue
                            detected_artist = a.name
                            detected_song = s
                            logger.info(f"Entity Scanner Locked Song independently: {detected_song} by {detected_artist}")
                            break
                    if detected_artist: break
        except Exception as e: 
            logger.error(f"Entity Scan Database Error: {e}")
            
    vibe_data["detected_artist"] = detected_artist
    vibe_data["detected_song"] = detected_song

    # User dismissed the artist lock tag in the UI — wipe it so it
    # doesn't influence genre resolution, pool fetch, or scoring.
    # override_artist is still respected (that's a Pro Mode explicit choice).
    if request.dismiss_detected_artist and not request.override_artist:
        if detected_artist:
            logger.info(f"User dismissed detected artist lock '{detected_artist}' — clearing from engine state.")
        detected_artist = None
        detected_song = None
        vibe_data["detected_artist"] = None
        vibe_data["detected_song"] = None

    # v1.2 FIX: If entity scanner locked an artist/song but the NLP scored
    # a legitimate vibe, don't let a 0%-confidence "neutral" overwrite it.
    # Only accept the entity lock if either:
    #   a) NLP confidence is below threshold (< 0.30), meaning NLP needs help, OR
    #   b) The entity was found alongside a genuine vibe signal (artist matched)
    # If NLP confidence is solid (≥ 0.30) and the lock was song-only (no artist
    # context in the prompt), drop the song lock to avoid "calm down → Rema" hijacks.
    if detected_song and not detected_artist and vibe_data.get("confidence", 0) >= 0.30:
        logger.info(f"Entity Scanner: Dropping standalone song lock '{detected_song}' — NLP confidence is {vibe_data.get('confidence')} (≥ 0.30), vibe signal is strong enough.")
        vibe_data["detected_song"] = None

    # 3. DYNAMIC TARGET GENRE RESOLUTION
    # Extract these early to prevent NameError scope leaks during multi-tag fetch
    _lang = (request.language or "Any").strip()
    _dominant = vibe_data.get("dominant_vibe", "")
    active_vibe_for_tags = _dominant

    if detected_artist and vibe_data.get("confidence", 0) < 0.10:
        logger.info(f"Entity lock active but NLP confidence near-zero. Forcing artist discography fetch for '{detected_artist}'.")
        vibe_data["dominant_vibe"] = "artist_driven"
        active_vibe_for_tags = "artist_driven"
        target_genre = None
    elif request.override_genre:
        target_genre = request.override_genre
        active_vibe_for_tags = "override" # Force VIBE_TAG_MATRIX to miss and strictly use fallback
        logger.info(f"Pro Mode OVERRIDE applied. Target Genre forced to: {target_genre}")
        # Also override the genres list that gets sent to the frontend — otherwise
        # the displayed genre tags still show the NLP-detected vibe's genres (P38 bug)
        vibe_data["genres"] = [request.override_genre.title()]
    elif request.use_secondary_vibe and vibe_data.get("secondary_vibe"):
        sec_vibe_name = vibe_data["secondary_vibe"]
        active_vibe_for_tags = sec_vibe_name # We pivoted!
        mapped_genres = vibe_engine.VIBE_MAP.get(sec_vibe_name, {}).get("genres", [sec_vibe_name])
        _lang_map_sec = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
        target_genre  = (
            _lang_map_sec.get(sec_vibe_name)
            or _lang_map_sec.get("default")
            or mapped_genres[0]
        )
        logger.info(f"PIVOT ACTIVE: Lang={_lang} Vibe={sec_vibe_name} Genre -> {target_genre}")
    else:
        _lang_map = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
        target_genre = (
            _lang_map.get(_dominant)
            or _lang_map.get("default")
            or vibe_data.get("genres", ["electronic"])[0]
        )
        # P56/P63/P67 guard: if CINEMATIC fired on a regional Indian/non-English language
        # but no cinematic genre is in the LANGUAGE_TAG_MAP for that lang, don't fall to
        # western orchestral — force the language default pool instead.
        REGIONAL_LANGS = {"Telugu", "Malayalam", "Kannada", "Tamil", "Marathi", "Bengali", "Assamese", "Urdu", "Punjabi"}
        if _dominant == "cinematic" and _lang in REGIONAL_LANGS:
            regional_cinematic = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {}).get("cinematic") or \
                                  vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {}).get("default")
            if regional_cinematic:
                target_genre = regional_cinematic
                logger.info(f"Cinematic Regional Guard: {_lang} → {target_genre} (blocked western orchestral)")
        logger.info(f"Standard AI Resolution: Lang={_lang} Vibe={_dominant} Genre -> {target_genre}")
        
    vibe_data["target_genre_override"] = target_genre

    # 4. SMART POOL FETCH & GRACEFUL FALLBACK
    is_fallback = False
    used_semantic = False
    
    if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
        is_fallback = True
        logger.warning(f"Engine Confidence Critical ({vibe_data.get('confidence')} < 0.25). Gemini enhancement was not enough or unavailable. Triggering Fallback Protocol to Direct Search!")
        vibe_data["dominant_vibe"] = "Direct Search" 
        vibe_data["secondary_vibe"] = "Fallback Mode"
        raw_pool = await fetch_lastfm_track_search(request.text, limit=100)
        logger.info(f"Fallback Search returned {len(raw_pool)} tracks.")

        # v8.0: 3-STAGE DIRECT SEARCH FALLBACK — fires when primary search yields 0
        if not raw_pool:
            logger.warning("Stage 1 DS: Zero results — retrying with stripped keywords.")
            # Stage 1: Strip stopwords, retry with top 4 meaningful tokens
            _STOPWORDS = {
                "a","an","the","and","or","but","for","with","at","by","of","in",
                "on","to","is","it","my","me","we","be","as","so","up","type","vibe",
                "music","songs","playlist","feel","feeling","i","need","want","give",
            }
            _tokens = [
                w for w in re.sub(r"[^\w\s]", " ", request.text.lower()).split()
                if w not in _STOPWORDS and len(w) > 2
            ]
            _stage1_query = " ".join(_tokens[:4])
            if _stage1_query:
                raw_pool = await fetch_lastfm_track_search(_stage1_query, limit=100)
                logger.info(f"Stage 1 DS retry '{_stage1_query}': {len(raw_pool)} tracks.")

        if not raw_pool:
            logger.warning("Stage 2 DS: Zero results — trying artist-guess from longest token.")
            # Stage 2: Treat longest token as a potential artist name
            _all_tokens = [
                w for w in re.sub(r"[^\w\s]", " ", request.text.lower()).split()
                if len(w) > 3
            ]
            if _all_tokens:
                _artist_guess = max(_all_tokens, key=len)
                logger.info(f"Stage 2 DS: artist guess = '{_artist_guess}'")
                raw_pool = await fetch_lastfm_artist_tracks(artist=_artist_guess, limit=100)
                logger.info(f"Stage 2 DS artist tracks: {len(raw_pool)} tracks.")

        # 🚨 BRO FIX: Bug 3 - Route through semantic search thin pool before Stage 3 safety net
        if not raw_pool:
            logger.warning("Stage 2.5 DS: Checking ThinPoolCache for known dead-ends.")
            raw_pool = await semantic_search.get_thin_pool_supplement(_lang, _dominant, db)
            if raw_pool:
                logger.info(f"Stage 2.5 DS thin pool fetched: {len(raw_pool)} tracks.")

        if not raw_pool:
            logger.warning("Stage 3 DS: Hard fallback — fetching dream pop / chillwave safety pool.")
            # Stage 3: Hard fallback — guaranteed non-empty genre pool
            _s3_results = await asyncio.gather(
                fetch_lastfm_tracks("dream pop", limit=60),
                fetch_lastfm_tracks("indie pop", limit=60),
                fetch_lastfm_tracks("chillwave", limit=60),
                return_exceptions=True,
            )
            for _r in _s3_results:
                if isinstance(_r, list):
                    raw_pool.extend(_r)
            logger.info(f"Stage 3 DS safety pool: {len(raw_pool)} tracks.")

        # v1.2 FIX: Filter out junk fallback results (podcasts, news, YouTube videos)
        # 🚨 BRO FIX: Bug 5 - Added music videos, ep remixes, drum solos
        JUNK_PATTERNS = re.compile(
            r'\b(podcast|episode|news|npr|bbc|ted talk|morning edition|'
            r'kitchen nightmares|speedrunning|let me explain|'
            r'how to make|react(?:ion)?|compilation|highlights|'
            r'sound effect|sound effects|ringtone|notification|'
            r'relaxing spa|nature music|ocean tones|spa music|'
            r'30 seconds|music box|text tones|christmas tree|'
            r'calming drone|holy drone|fire sticks|waterfowl|'
            r'bitcoin|crypto|nft|stock market|financial|'
            r'tutorial|lesson|course|lecture|audiobook|'
            r'tkm|trackmania|yu-gi-oh|master duel|nibiru|'
            r'show \d+\s*[-—]|radio show|chutneyradio|chutney radio|'
            r'internet radio|dj set|broadcast|'
            r'music video|official video|ep remix|drum solo|live performance)\b'
            r'|\.com\b|\.fm\b|\.net\b|\.org\b',
            re.IGNORECASE
        )
        raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(f"{t.get('title','')} {t.get('artist','')}")] 
        # Also filter tracks with very long title strings (usually YouTube content)
        raw_pool = [t for t in raw_pool if len(t.get('title', '')) < 120]
        # 🚨 FIX: Filter out Last.fm junk-placeholder artists like ".......", "!!!", "???", etc.
        # Catches any artist string that contains zero actual word characters (letters/digits).
        _JUNK_ARTIST = re.compile(r'^[^\w]+$')
        raw_pool = [t for t in raw_pool if t.get('artist') and not _JUNK_ARTIST.match(t.get('artist', ''))]
        logger.info(f"After junk filter: {len(raw_pool)} tracks remain.")

        # v1.3 NEW: Semantic reranking — when Last.fm keyword search gives us a
        # noisy pool, run sentence-transformer similarity to promote the tracks
        # whose identity most closely matches the user's prompt.
        if semantic_search.semantic_ready() and raw_pool:
            logger.info(f"[Semantic] Reranking {len(raw_pool)} fallback tracks by prompt similarity...")
            raw_pool = await asyncio.to_thread(
                semantic_search.rank_tracks_by_prompt, request.text, raw_pool
            )
            used_semantic = True
            logger.info(f"[Semantic] Reranking complete.")
        
    elif request.override_artist or vibe_data.get("dominant_vibe") == "artist_driven":
        artist_target = request.override_artist or detected_artist
        logger.info(f"Fetching direct discography for artist: {artist_target}")
        raw_pool = await fetch_lastfm_artist_tracks(artist=artist_target, limit=200)
    else:
        _dominant_vibe = vibe_data.get("dominant_vibe", "")
        if _dominant_vibe == "unknown" and not request.override_genre:
            is_fallback = True
            logger.info(f"Unknown vibe — direct text search: '{request.text}'")
            genre_pool = await fetch_lastfm_track_search(request.text, limit=150)
        else:
                # ── MULTI-TAG PARALLEL FETCH v6.0 ───────────────────────────
                _secondary_vibe_hint = vibe_data.get("secondary_vibe") if not request.use_secondary_vibe else None
                _vibe_tags = get_vibe_tags(active_vibe_for_tags, _lang, target_genre, secondary_vibe=_secondary_vibe_hint)
                logger.info(f"Multi-tag fetch: lang={_lang} vibe={active_vibe_for_tags} tags={_vibe_tags}")

                _per_tag_limit = max(60, 200 // len(_vibe_tags))
                _tag_results = await asyncio.gather(
                    *[fetch_lastfm_tracks(tag, limit=_per_tag_limit) for tag in _vibe_tags],
                    return_exceptions=True
                )
                genre_pool: list[dict] = []
                for _r in _tag_results:
                    if isinstance(_r, list):
                        genre_pool.extend(_r)

                # ── VIBE-ARTIST SEEDING ──────────────────────────────────────
                _seed_artists: list[str] = (
                    vibe_engine.VIBE_MAP.get(active_vibe_for_tags, {}).get("artists", [])[:3]
                )
                _seed_pool: list[dict] = []
                if _seed_artists:
                    logger.info(f"Seeding VIBE_MAP artists: {_seed_artists}")
                    _seed_results = await asyncio.gather(
                        *[fetch_lastfm_artist_tracks(a, limit=30) for a in _seed_artists],
                        return_exceptions=True
                    )
                    for _r in _seed_results:
                        if isinstance(_r, list):
                            _seed_pool.extend(_r)

                # ── DETECTED ARTIST BLEND ────────────────────────────────────
                artist_pool: list[dict] = []
                if detected_artist and request.artist_focus > 25:
                    logger.info(f"Injecting discography blend for detected artist: {detected_artist}")
                    artist_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=50)

                # ── DB ARTIST NICHE SUPPLEMENT ───────────────────────────────
                # When ARTIST knob is high (>65), the user wants artist-centric
                # diversity. Pull artists from ArtistDirectory whose niche matches
                # the current vibe's genre tags, and blend their discographies in.
                # This is additive — Last.fm is still the primary source.
                db_artist_pool: list[dict] = []
                if request.artist_focus > 65 and ARTIST_NICHE_INDEX:
                    # Map vibe → candidate niche strings in ArtistDirectory
                    _VIBE_TO_DB_NICHE: dict[str, list[str]] = {
                        "chill":         ["lastfm top rnb", "lastfm top alternative"],
                        "focus":         ["lastfm top electronic", "lastfm top ambient"],
                        "ambient":       ["lastfm top ambient", "lastfm top neo-classical"],
                        "heartbreak":    ["lastfm top soul", "lastfm top rnb", "lastfm top alternative"],
                        "hype":          ["lastfm top hip-hop", "lastfm top trap", "lastfm top rap"],
                        "party":         ["lastfm top house", "lastfm top techno", "lastfm top dancehall"],
                        "euphoric":      ["lastfm top house", "lastfm top techno"],
                        "dark":          ["lastfm top industrial", "lastfm top shoegaze"],
                        "intense":       ["lastfm top metalcore", "lastfm top deathcore", "lastfm top metal"],
                        "rock":          ["lastfm top classic rock", "lastfm top indie rock", "lastfm top alternative"],
                        "retro":         ["lastfm top classic rock", "lastfm top soul", "lastfm top jazz"],
                        "indie_folk":    ["lastfm top folk", "lastfm top americana"],
                        "dreamy":        ["lastfm top dream pop", "lastfm top shoegaze"],
                        "punjabi":       ["lastfm top punjabi", "lastfm top bhangra"],
                        "punjabi_soft":  ["lastfm top punjabi"],
                        "bollywood_sad": ["lastfm top bollywood"],
                        "desi":          ["lastfm top bollywood", "lastfm top punjabi"],
                        "soulful":       ["lastfm top soul", "lastfm top rnb"],
                        "romantic":      ["lastfm top soul", "lastfm top rnb"],
                        "cinematic":     ["lastfm top film score", "lastfm top neo-classical"],
                        "happy":         ["lastfm top pop", "lastfm top soul"],
                    }
                    target_niches = _VIBE_TO_DB_NICHE.get(_dominant_vibe, [])
                    if target_niches:
                        import random as _rand
                        db_candidates: list[dict] = []
                        for niche_key in target_niches:
                            db_candidates.extend(ARTIST_NICHE_INDEX.get(niche_key, []))
                        # Pick up to 3 random artists from DB pool to keep diversity
                        sample_size = min(3, len(db_candidates))
                        if sample_size:
                            sampled = _rand.sample(db_candidates, sample_size)
                            logger.info(
                                f"[DB Supplement] artist_focus={request.artist_focus} → "
                                f"sampling {sample_size} DB artists for vibe '{_dominant_vibe}': "
                                f"{[a['name'] for a in sampled]}"
                            )
                            _db_fetch_results = await asyncio.gather(
                                *[fetch_lastfm_artist_tracks(a["name"], limit=25) for a in sampled],
                                return_exceptions=True,
                            )
                            for _r in _db_fetch_results:
                                if isinstance(_r, list):
                                    db_artist_pool.extend(_r)
                            logger.info(f"[DB Supplement] Added {len(db_artist_pool)} tracks from DB artists.")

                # ── MERGE + DEDUPLICATE ──────────────────────────────────────
                merged_pool = genre_pool + _seed_pool + artist_pool + db_artist_pool
                seen: set[str] = set()
                raw_pool: list[dict] = []
                for t in merged_pool:
                    ident = f"{t['title'].lower()}|{t['artist'].lower()}"
                    if ident not in seen:
                        seen.add(ident)
                        raw_pool.append(t)
                logger.info(
                    f"Multi-tag pool: {len(raw_pool)} tracks "
                    f"({len(genre_pool)} tags + {len(_seed_pool)} seed + "
                    f"{len(artist_pool)} artist + {len(db_artist_pool)} db)"
                )
                # Global junk filter — catches radio shows, URLs, compilations on all paths
                # 🚨 BRO FIX: Bug 5 - expanded junk filter here too!
                _GLOBAL_JUNK = re.compile(
                    r'\b(podcast|episode|radio show|chutneyradio|internet radio|dj set|broadcast|'
                    r'show \d+\s*[-—]|compilation|highlights|tutorial|audiobook|'
                    r'music video|official video|ep remix|drum solo|live performance)\b'
                    r'|\.com\b|\.fm\b|\.net\b|\.org\b',
                    re.IGNORECASE
                )
                raw_pool = [
                    t for t in raw_pool
                    if not _GLOBAL_JUNK.search(f"{t.get('title','')} {t.get('artist','')}")
                    and len(t.get('title', '')) < 120
                ]
                # ── HEARTBREAK POOL GUARD ──────────────────────────────────────────────────
                # Heartbreak is the thinnest genre pool on Last.fm — "sad" tags return fewer
                # than 100 tracks regularly. Top up silently before scoring kicks in.
                if vibe_data.get("dominant_vibe") == "heartbreak" and len(raw_pool) < 100:
                    logger.warning(f"Heartbreak pool thin ({len(raw_pool)} tracks). Topping up...")
                    _hb_tags = ["sad indie", "breakup songs", "sad pop", "indie sad"]
                    _hb_fetches = await asyncio.gather(*[
                        fetch_lastfm_tracks(genre=tag, limit=60) for tag in _hb_tags
                    ])
                    _hb_seen = {f"{t['title'].lower()}|{t['artist'].lower()}" for t in raw_pool}
                    for _hb_track in [t for sublist in _hb_fetches for t in sublist]:
                        _hb_key = f"{_hb_track['title'].lower()}|{_hb_track['artist'].lower()}"
                        if _hb_key not in _hb_seen:
                            raw_pool.append(_hb_track)
                            _hb_seen.add(_hb_key)
                    logger.info(f"Heartbreak pool after top-up: {len(raw_pool)} tracks.")

                # ── GENERALIZED THIN POOL GUARD (v6.1) ─────────────────────────────────────
                # Vibes with historically thin Last.fm pools get artist-driven supplements.
                # Identified from 10k QA batch: punjabi_soft (0 avg), haryanvi (6 avg),
                # bollywood_sad (7 avg). The fix: inject real artist discographies when
                # the tag-based pool is critically thin.
                # 🚨 BRO FIX: Bug 7 - Added regional gaps!
                _THIN_VIBE_ARTISTS: dict[str, list[str]] = {
                    # ── Desi sub-vibes (tag-based pools are near-empty on Last.fm) ──
                    "punjabi_soft": [
                        "B Praak", "AP Dhillon", "Satinder Sartaaj", "Prabh Gill",
                        "Jassi Gill", "Ninja", "Mankirt Aulakh", "Jassie Gill"
                    ],
                    "haryanvi": [
                        "Sapna Choudhary", "Masoom Sharma", "Raju Punjabi", "Pardeep Boora",
                        "Ajay Hooda", "Amit Dhull", "Vikram Pannu", "Bhoomi Trivedi"
                    ],
                    "bollywood_sad": [
                        "Arijit Singh", "Atif Aslam", "KK", "Mohit Chauhan",
                        "Shreya Ghoshal", "Jubin Nautiyal", "Armaan Malik"
                    ],
                    "cinematic": [
                        "Anirudh Ravichander", "Devi Sri Prasad", "S.S. Thaman", "M.M. Keeravani",
                        "Ravi Basrur", "Santhosh Narayanan"
                    ],
                    "rock": [
                        "Fossils", "Cactus", "Anupam Roy", "Avial", "Agam", "The Local Train"
                    ],
                    "calm": [
                        "Agam", "K.S. Chithra", "Bombay Jayashri", "Sid Sriram", "Shankar Mahadevan"
                    ],
                    # ── Bug 7 Fix: Language × vibe compound keys for regional catalog gaps ──
                    # These are the 5 worst-performing input clusters from the QA analysis
                    # (64-85% fail rate). The issue is catalog coverage, not algorithm.
                    # Compound key format: "{Language}|{vibe}" → checked before simple vibe key.
                    "Telugu|hype": [
                        "Allu Arjun", "Devi Sri Prasad", "S. Thaman", "Ram Miriyala",
                        "Anirudh Ravichander", "Vijay Antony", "Benny Dayal"
                    ],
                    "Telugu|cinematic": [
                        "M.M. Keeravani", "Devi Sri Prasad", "S. Thaman",
                        "Mani Sharma", "Mickey J Meyer", "Anup Rubens"
                    ],
                    "Bengali|rock": [
                        "Fossils", "Cactus", "Rupam Islam", "Chandrabindoo",
                        "Bhoomi", "Lakkhichhara", "Dohar"
                    ],
                    "Bengali|indie": [
                        "Anupam Roy", "Arnob", "The Local Train",
                        "Shironamhin", "Warfaze", "Nemesis"
                    ],
                    "Bengali|soulful": [
                        "Anupam Roy", "Arnob", "Srikanta Acharya",
                        "Lopamudra Mitra", "Usha Uthup"
                    ],
                    "Any|Carnatic fusion": [
                        "Agam", "Thaikkudam Bridge", "Pineapple Express",
                        "Prasanna", "Entropy", "Varijashree Venugopal"
                    ],
                    "Tamil|ambient": [
                        "AR Rahman", "Santhosh Narayanan", "Ilaiyaraaja",
                        "Yuvan Shankar Raja", "Harris Jayaraj"
                    ],
                    "Any|non-english": [
                        "Sigur Rós", "Buena Vista Social Club", "Stromae",
                        "Seu Jorge", "Caetano Veloso", "Khruangbin",
                        "Dengue Fever", "Tinariwen", "Fatoumata Diawara"
                    ],
                }
                _dominant_vibe_check = vibe_data.get("dominant_vibe", "")
                # Bug 7 Fix: check language-specific compound key first, then fall back to simple vibe key.
                # This ensures "Bengali|rock" resolves to Fossils/Cactus, not generic western rock.
                _compound_key = f"{_lang}|{_dominant_vibe_check}"
                _thin_key = (
                    _compound_key if _compound_key in _THIN_VIBE_ARTISTS
                    else _dominant_vibe_check if _dominant_vibe_check in _THIN_VIBE_ARTISTS
                    else None
                )
                if _thin_key and len(raw_pool) < 40:
                    _supplement_artists = _THIN_VIBE_ARTISTS[_thin_key]
                    logger.warning(
                        f"Thin pool for vibe '{_dominant_vibe_check}' (key='{_thin_key}', {len(raw_pool)} tracks). "
                        f"Injecting artist discographies: {_supplement_artists[:4]}"
                    )
                    _supplement_fetches = await asyncio.gather(*[
                        fetch_lastfm_artist_tracks(a, limit=40)
                        for a in _supplement_artists
                    ], return_exceptions=True)
                    _sup_seen = {f"{t['title'].lower()}|{t['artist'].lower()}" for t in raw_pool}
                    for _result in _supplement_fetches:
                        if isinstance(_result, list):
                            for _st in _result:
                                _sk = f"{_st['title'].lower()}|{_st['artist'].lower()}"
                                if _sk not in _sup_seen:
                                    raw_pool.append(_st)
                                    _sup_seen.add(_sk)
                    logger.info(f"Thin pool after artist supplement: {len(raw_pool)} tracks.")
                
    # 🚨 ZERO RESULTS SAFETY NET 🚨
    if not raw_pool:
        logger.warning("Zero Results Triggered. Firing HTTP 404 to Frontend.")
        raise HTTPException(
            status_code=404, 
            detail="Signal lost: Zero results found. 📡 Please rephrase your query. (Note: Our acoustic engine currently processes English descriptors, specific genres, and known artists best.)"
        )
    
    # 5. MATHEMATICAL SCORING
    logger.info("Executing mathematical sorting and diversity guards...")
    best_tracks = filter_and_score_tracks(raw_pool, request, vibe_data, is_fallback=is_fallback)

    # v1.3 NEW: If semantic scores are available and we used the fallback path,
    # blend them with the heuristic scores for a final reranking pass.
    if used_semantic and best_tracks and any("semantic_score" in t for t in best_tracks):
        logger.info("[Semantic] Blending semantic + heuristic scores for final ranking...")
        best_tracks = semantic_search.blend_semantic_scores(best_tracks, semantic_weight=0.35)
        # Re-trim to track limit after blending
        best_tracks = best_tracks[:request.track_limit]
    
    if not best_tracks:
        logger.warning("Scoring eliminated all tracks. Firing HTTP 404.")
        raise HTTPException(
            status_code=404, 
            detail="Signal lost: No tracks passed the strict filters. Try lowering Nicheness or adjusting your prompt."
        )
    
    # 6. PARALLEL PREVIEW SCRAPING
    logger.info(f"Scraping Apple Music previews concurrently for top {len(best_tracks)} tracks...")
    itunes_tasks = [fetch_itunes_preview(t["title"], t["artist"]) for t in best_tracks]
    previews = await asyncio.gather(*itunes_tasks)
    
    # 7. PAYLOAD ASSEMBLY
    final_tracks = []
    for i, t in enumerate(best_tracks):
        q = urllib.parse.quote(f"{t['title']} {t['artist']}")
        final_tracks.append({
            "title": t["title"], "artist": t["artist"],
            "spotify_uri": f"spotify:search:{q}",
            "apple_uri": f"music://search?term={q}",
            "preview_url": previews[i]["preview_url"],
            "cover_art": previews[i]["cover_art"]
        })

    # 8. LOG REQUEST TO DATABASE
    # Persist the full analysis session so we can link feedback to it later.
    # Fire-and-forget — we don't block the response on a DB write.
    import json as _json
    vibe_request_id = None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        vibe_request_row = await db.viberequest.create(data={
            "userId":          user_id,
            "promptText":      request.text,
            "dominantVibe":    vibe_data.get("dominant_vibe", "neutral"),
            "secondaryVibe":   vibe_data.get("secondary_vibe"),
            "confidence":      float(vibe_data.get("confidence", 0.0)),
            "bpmRange":        str(vibe_data.get("bpm_range", "")),
            "genres":          _json.dumps(vibe_data.get("genres", [])),
            "matchedKeywords": _json.dumps(vibe_data.get("matched_keywords", [])),
            "detectedArtist":  vibe_data.get("detected_artist"),
            "detectedSong":    vibe_data.get("detected_song"),
            "artistFocus":     request.artist_focus,
            "nicheness":       request.nicheness,
            "bpmFocus":        request.bpm_focus,
            "trackLimit":      request.track_limit,
            "usedFallback":    is_fallback,
            "usedSemantic":    used_semantic,
            "returnedTracks":  _json.dumps([
                {"title": t["title"], "artist": t["artist"]} for t in final_tracks
            ]),
        })
        vibe_request_id = vibe_request_row.id
        logger.info(f"VibeRequest logged to DB: {vibe_request_id}")
    except Exception as e:
        # Non-fatal — never let a logging failure break the response
        logger.error(f"Failed to log VibeRequest to DB: {e}")
        
    vibe_data["tracks"] = final_tracks
    vibe_data["request_id"] = vibe_request_id or "unlogged"
    logger.info(f"--- SUCCESS: Returning {len(final_tracks)} tracks to client ---")
    return vibe_data


@app.post("/api/feedback", status_code=201)
async def submit_feedback(feedback: FeedbackRequest, token: str = Depends(oauth2_scheme)):
    """
    Record a user's thumbs up / thumbs down on a specific track.
    
    Called by the frontend immediately when the user clicks the feedback buttons.
    Each call is one row in TrackFeedback — lightweight and append-only.
    
    Validation:
    - signal must be -1, 0, or 1
    - request_id must reference a real VibeRequest row
    - The authenticated user must own that VibeRequest (prevents spoofing)
    """
    # Validate signal value
    if feedback.signal not in (-1, 0, 1):
        raise HTTPException(status_code=422, detail="signal must be -1, 0, or 1")

    # Decode user from token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify the VibeRequest exists and belongs to this user
    # Skip ownership check if request_id is "unlogged" (DB logging failed upstream)
    if feedback.request_id != "unlogged":
        try:
            vibe_req = await db.viberequest.find_unique(where={"id": feedback.request_id})
            if vibe_req is None:
                raise HTTPException(status_code=404, detail="VibeRequest not found")
            if vibe_req.userId != user_id:
                raise HTTPException(status_code=403, detail="Not your request")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Feedback: DB lookup error: {e}")
            raise HTTPException(status_code=500, detail="Database error")

    # Write the feedback row
    try:
        row = await db.trackfeedback.create(data={
            "vibeRequestId":  feedback.request_id if feedback.request_id != "unlogged" else None,
            "userId":         user_id,
            "trackTitle":     feedback.track_title,
            "trackArtist":    feedback.track_artist,
            "signal":         feedback.signal,
            "position":       feedback.position,
            "previewSeconds": feedback.preview_seconds,
        })
        signal_label = {1: "👍 LIKE", 0: "▶ PLAY", -1: "👎 SKIP"}.get(feedback.signal, "?")
        logger.info(
            f"Feedback logged: [{signal_label}] '{feedback.track_title}' by '{feedback.track_artist}' "
            f"(pos={feedback.position}, user={user_id[:8]}..., req={feedback.request_id[:8]}...)"
        )
        return {"status": "ok", "id": row.id}
    except Exception as e:
        logger.error(f"Feedback: write error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")
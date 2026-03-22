from fastapi import FastAPI, Depends, HTTPException, status, Request
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
import httpx
import contextlib
from core.vibe_engine import LANGUAGE_TAG_MAP

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logger = logging.getLogger("VibeFinderEngine")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

file_handler = logging.FileHandler("vibefinder_engine.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=dotenv_path)
logger.info(f"Environment variables loaded from: {dotenv_path}")

try:
    import aiohttp as _aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    import urllib.request

_HTTP_SESSION: "_aiohttp.ClientSession | None" = None

async def _get_http_session():
    global _HTTP_SESSION
    if _HTTP_SESSION is None or _HTTP_SESSION.closed:
        if _AIOHTTP_AVAILABLE:
            connector = _aiohttp.TCPConnector(
                limit=50, limit_per_host=10, keepalive_timeout=30, enable_cleanup_closed=True,
            )
            _HTTP_SESSION = _aiohttp.ClientSession(
                connector=connector, headers={"User-Agent": "VibeFinderAI/2.0"}, connector_owner=True,
            )
    return _HTTP_SESSION

LASTFM_MIN_INTERVAL_SECONDS = float(os.getenv("LASTFM_MIN_INTERVAL_SECONDS", "0.35"))
LASTFM_MAX_CONCURRENT = int(os.getenv("LASTFM_MAX_CONCURRENT", "3"))
ITUNES_MAX_CONCURRENT = int(os.getenv("ITUNES_MAX_CONCURRENT", "6"))

_LASTFM_SEMAPHORE = asyncio.Semaphore(max(1, LASTFM_MAX_CONCURRENT))
_ITUNES_SEMAPHORE = asyncio.Semaphore(max(1, ITUNES_MAX_CONCURRENT))
_LASTFM_RATE_LOCK = asyncio.Lock()
_LASTFM_NEXT_ALLOWED_AT = 0.0

async def _respect_lastfm_rate_limit() -> None:
    global _LASTFM_NEXT_ALLOWED_AT
    async with _LASTFM_RATE_LOCK:
        now = asyncio.get_running_loop().time()
        wait_for = _LASTFM_NEXT_ALLOWED_AT - now
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        now = asyncio.get_running_loop().time()
        _LASTFM_NEXT_ALLOWED_AT = now + max(0.0, LASTFM_MIN_INTERVAL_SECONDS)

from core import vibe_engine

try:
    from routes.playlist_routes import router as playlist_router, set_db as playlist_set_db
    from routes.analytics_routes import router as analytics_router, set_db as analytics_set_db
    _ROUTES_AVAILABLE = True
except ImportError as _re:
    _ROUTES_AVAILABLE = False
    import logging as _log
    _log.getLogger(__name__).warning(f"playlist/analytics routes not found: {_re}")

try:
    from routes.spotify_routes import router as spotify_router, set_db as spotify_set_db
    _SPOTIFY_ROUTES_AVAILABLE = True
except ImportError as _se:
    _SPOTIFY_ROUTES_AVAILABLE = False
    spotify_router = None

try:
    from routes.services_routes import router as services_router, set_db as services_set_db
    _SERVICES_ROUTES_AVAILABLE = True
except ImportError as _sve:
    _SERVICES_ROUTES_AVAILABLE = False
    services_router = None

try:
    from routes.metrics_auth import router as metrics_router
    _METRICS_ROUTES_AVAILABLE = True
except ImportError as _mre:
    _METRICS_ROUTES_AVAILABLE = False
    metrics_router = None
    logger.warning(f"Metrics routes not found: {_mre}")

try:
    from core.gemini_vibe import gemini_enhancer as _gemini_enhancer
    _GEMINI_AVAILABLE = bool(_gemini_enhancer)
except ImportError:
    _GEMINI_AVAILABLE = False
    _gemini_enhancer  = None

try:
    from analyzers.sentiment_boost import apply_sentiment_boost
    _SENTIMENT_AVAILABLE = True
except ImportError:
    _SENTIMENT_AVAILABLE = False
    def apply_sentiment_boost(text, vibe_data): return vibe_data

try:
    from analyzers import semantic_search
    _SEMANTIC_MODULE_AVAILABLE = True
except Exception as _sem_err:
    _SEMANTIC_MODULE_AVAILABLE = False
    logger.warning(f"[Semantic] Module unavailable: {_sem_err} — semantic fallback disabled")
    class _SemanticStub:
        def semantic_ready(self): return False
        def rank_tracks_by_prompt(self, prompt, tracks, **kw): return tracks
        def blend_semantic_scores(self, tracks, **kw): return tracks
        def get_thin_pool_supplement(self, *a, **kw): return []
    semantic_search = _SemanticStub()

# ---------------------------------------------------------
# Database
# ---------------------------------------------------------
db = Prisma()

def get_db() -> Prisma:
    return db

# ── In-memory feature indexes (populated on startup) ─────────────────────────
TRACK_FEATURE_INDEX: dict[str, dict] = {}
ARTIST_NICHE_INDEX: dict[str, list[dict]] = {}
DB_TRACK_POOL: dict[str, list[dict]] = {}
DB_SIMILAR_ARTISTS: dict[str, list[str]] = {}
# PATCH 1: O(1) artist name lookup — eliminates per-request DB full scan
# Keyed by _normalize_for_matching(name) → ArtistDirectory row
ARTIST_NAME_INDEX: dict[str, object] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Supabase (Prisma) connection...")
    await db.connect()
    logger.info("Database connected successfully. Engine online.")

    if _ROUTES_AVAILABLE:
        playlist_set_db(db)
        analytics_set_db(db)
        logger.info("Playlist and analytics routes wired to DB.")
    if _SPOTIFY_ROUTES_AVAILABLE and spotify_router:
        spotify_set_db(db, os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this"))
        logger.info("Spotify routes wired to DB.")
    if _SERVICES_ROUTES_AVAILABLE and services_router:
        services_set_db(db, os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this"))
        logger.info("Services routes wired to DB.")

    # TrackFeatureCache → TRACK_FEATURE_INDEX
    try:
        _cache_rows = await db.trackfeaturecache.find_many()
        for row in _cache_rows:
            _key = f"{(row.title or '').strip().lower()}|{(row.artist or '').strip().lower()}"
            TRACK_FEATURE_INDEX[_key] = {
                "tempo":             float(row.tempo)             if row.tempo             else None,
                "energy":            float(row.energy)            if row.energy            else None,
                "valence":           float(row.valence)           if row.valence           else None,
                "danceability":      float(row.danceability)      if row.danceability      else None,
                "acousticness":      float(row.acousticness)      if row.acousticness      else None,
                "instrumentalness":  float(row.instrumentalness)  if row.instrumentalness  else None,
                "speechiness":       float(row.speechiness)       if row.speechiness       else None,
                "moodHappy":         float(row.moodHappy)         if row.moodHappy         else None,
                "moodSad":           float(row.moodSad)           if row.moodSad           else None,
                "moodRelaxed":       float(row.moodRelaxed)       if row.moodRelaxed       else None,
                "moodAggressive":    float(row.moodAggressive)    if row.moodAggressive    else None,
                "moodParty":         float(row.moodParty)         if row.moodParty         else None,
                "moodAcoustic":      float(row.moodAcoustic)      if row.moodAcoustic      else None,
                "moodElectronic":    float(row.moodElectronic)    if row.moodElectronic    else None,
                "spotifyId":         row.spotifyId  or None,
                "isrc":              row.isrc       or None,
                "mbid":              row.mbid       or None,
            }
        logger.info(f"TrackFeatureCache loaded: {len(TRACK_FEATURE_INDEX)} tracks indexed.")
    except Exception as e:
        logger.warning(f"TrackFeatureCache load failed: {e}")

    # ArtistDirectory niche index
    try:
        _artist_rows = await db.artistdirectory.find_many(where={"tadbTop10": {"not": None}})
        for row in _artist_rows:
            _niche = (row.niche or "").strip().lower()
            if _niche:
                ARTIST_NICHE_INDEX.setdefault(_niche, []).append({
                    "name": row.name, "genres": row.genres or "",
                    "mbTags": row.mbTags or "", "tadbTop10": row.tadbTop10,
                })
        logger.info(f"ArtistDirectory niche index loaded: {len(ARTIST_NICHE_INDEX)} niches.")
    except Exception as e:
        logger.warning(f"ArtistDirectory index load failed: {e}")

    # tadbTop10 → DB_TRACK_POOL
    try:
        _all_artists = await db.artistdirectory.find_many(where={"tadbTop10": {"not": None}})
        _db_track_count = 0
        for _ar in _all_artists:
            if not _ar.tadbTop10:
                continue
            try:
                _top10 = json.loads(_ar.tadbTop10)
                _artist_key = _ar.name.strip().lower()
                _tracks = []
                for _t in _top10:
                    if isinstance(_t, dict) and _t.get("title"):
                        _tracks.append({"title": _t["title"], "artist": _ar.name})
                if _tracks:
                    DB_TRACK_POOL[_artist_key] = _tracks
                    _db_track_count += len(_tracks)
            except Exception:
                continue
        logger.info(f"DB_TRACK_POOL loaded: {len(DB_TRACK_POOL)} artists, {_db_track_count} total tracks.")
    except Exception as e:
        logger.warning(f"DB_TRACK_POOL load failed: {e}")

    # lbSimilarArtists → DB_SIMILAR_ARTISTS
    try:
        _similar_rows = await db.artistdirectory.find_many(where={"lbSimilarArtists": {"not": None}})
        for _sr in _similar_rows:
            if not _sr.lbSimilarArtists:
                continue
            try:
                _similars = json.loads(_sr.lbSimilarArtists)
                _names = [s["name"] for s in _similars if isinstance(s, dict) and s.get("name")]
                if _names:
                    DB_SIMILAR_ARTISTS[_sr.name.strip().lower()] = _names[:10]
            except Exception:
                continue
        logger.info(f"DB_SIMILAR_ARTISTS loaded: {len(DB_SIMILAR_ARTISTS)} artists indexed.")
    except Exception as e:
        logger.warning(f"DB_SIMILAR_ARTISTS load failed: {e}")

    # PATCH 2: Build ARTIST_NAME_INDEX for O(1) entity scanner lookup
    try:
        _index_artists = await db.artistdirectory.find_many()
        for _a in _index_artists:
            if not _a.name or not re.search(r"\w", _a.name):
                continue
            _norm = _normalize_for_matching(_a.name)
            ARTIST_NAME_INDEX[_norm] = _a
        logger.info(f"ARTIST_NAME_INDEX loaded: {len(ARTIST_NAME_INDEX)} artists.")
    except Exception as e:
        logger.warning(f"ARTIST_NAME_INDEX load failed (entity scanner will use DB fallback): {e}")

    yield

    logger.info("Engine shutting down. Disconnecting database...")
    await db.disconnect()
    global _HTTP_SESSION
    if _HTTP_SESSION and not _HTTP_SESSION.closed:
        await _HTTP_SESSION.close()
        logger.info("HTTP session closed.")

import difflib as _difflib

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(key_func=get_remote_address)
    _RATE_LIMIT_AVAILABLE = True
except ImportError:
    _RATE_LIMIT_AVAILABLE = False
    _limiter = None

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
    if not text or len(text.strip()) < 3:
        return text
    text = text.strip().strip('""\'"\'\'\' ')
    if not text:
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
    nfkd  = unicodedata.normalize("NFD", text)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    clean = clean.replace("$", "s")
    clean = re.sub(r'[^\w\s]', '', clean)
    return clean.strip()

app = FastAPI(title="VibeFinderAI API", description="Core backend for music discovery", lifespan=lifespan)

if _RATE_LIMIT_AVAILABLE:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def get_cors_origins():
    origins = ["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000"]
    frontend_prod = os.getenv("FRONTEND_URL_PROD") or "https://vibefinderai.netlify.app"
    if frontend_prod:
        origins.append(frontend_prod)
    return origins

app.add_middleware(
    CORSMiddleware, allow_origins=get_cors_origins(),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

if _ROUTES_AVAILABLE:
    app.include_router(playlist_router,  prefix="/api")
    app.include_router(analytics_router, prefix="/api")
if _SPOTIFY_ROUTES_AVAILABLE and spotify_router:
    app.include_router(spotify_router)
if _SERVICES_ROUTES_AVAILABLE and services_router:
    app.include_router(services_router)
if _METRICS_ROUTES_AVAILABLE and metrics_router:
    app.include_router(metrics_router)

SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    "vocal","vocals","instrumental",
}

TRACK_BLOCKLIST: set[str] = {
    "trap queen|fetty wap","circumambient|grimes","slow|my bloody valentine",
    "slowdive|slowdive","moanin'|art blakey & the jazz messengers",
    "time moves slow|badbadnotgood","4 am (adam k & soha mix)|kaskade",
    "finished symphony (deadmau5 remix)|hybrid","silhouettes - original radio edit|avicii",
    "strobe (radio edit)|deadmau5","brazil (2nd edit)|deadmau5",
    "to the hellfire|lorna shore","you only live once|suicide silence",
    "pray for plagues|bring me the horizon","country girl (shake it for me)|luke bryan",
    "take me home, country roads|john denver","she's country|jason aldean",
    "wts ottos - remix|scene","witch|scene","a warm hug|scene","moderato|scene",
    "僕の右手|scene","zuster|scene","de schaduw van het kruis|scene","planet girl|scene",
    "universal deluge|scene","revelation|scene","bioluminescence|scene","brand|scene",
    "dhvani|scene","long stones shelter|scene","thief of fire|loop","eolian|loop",
    "spinning|loop","interference|loop","fermion|loop","precession|loop",
    "cinnamon girl|loop","looking at you|loop","as if|loop",
    "the nail will burn (remastered)|loop","i'll take you there|loop",
    "crawling heart|loop","rocket usa|loop","calathea club|texture",
    "physical|dua lipa","you (ha ha ha)|charli xcx","stay away|charli xcx",
    "nuclear seasons|charli xcx","butterfly effect|travis scott","antidote|travis scott",
    "skinny love|bon iver","holocene|bon iver","bank account|21 savage",
    "redrum|21 savage","starships|nicki minaj","wokeuplikethis*|playboi carti",
    "magnolia|playboi carti","love is a losing game|amy winehouse","rehab|amy winehouse",
    "you know i'm no good|amy winehouse","loud|mac miller","donald trump|mac miller",
    "troublemaker|taio cruz","like a g6|far east movement",
    "cherry-coloured funk|cocteau twins","myth|beach house","space song|beach house",
    "so what|miles davis","solar|miles davis","feel so close|calvin harris",
    "summer|calvin harris","enter sandman|metallica","master of puppets|metallica",
    "all the things she said|t.a.t.u.","we can't stop|miley cyrus",
    "ho hey|the lumineers","i will wait|mumford & sons","all i ever wanted|basshunter",
    "promiscuous|nelly furtado","my favorite things|john coltrane",
    "i'm old fashioned - remastered 2003/rudy van gelder edition|john coltrane",
    "overkill|motörhead","ace of spades|motörhead","fast|demi lovato",
    "when you sleep|my bloody valentine","tubthumping|chumbawamba",
    "(don't fear) the reaper|blue öyster cult","the house of wolves|bring me the horizon",
    "call me maybe|carly rae jepsen","mykonos|fleet foxes",
    "white winter hymnal|fleet foxes","seek bromance - avicii vocal edit|tim berg",
    "god is a woman|ariana grande","blowin' in the wind|bob dylan",
    "only shallow|my bloody valentine","little lion man|mumford & sons",
    "happy|pharrell williams","yes|lmfao","sunset soon forgotten|iron & wine",
    "umbrella|rihanna","dragula|rob zombie","chop suey!|system of a down",
    "oroborus|gojira","before i forget|slipknot",
    "stupidisco|junior jack","stereo love|edward maya","i'm yours|jason mraz",
    "jackie and wilson|hozier",
}

LANGUAGE_ARTIST_BLOCKLIST: dict[str, set[str]] = {
    "universal": {
        "scene","loop","texture","song","p.o.p",
        "dua lipa","charli xcx","carly rae jepsen","pharrell williams",
        "lizzo","miley cyrus","taio cruz","lmfao","far east movement",
        "basshunter","nelly furtado","chumbawamba","t.a.t.u.","doja cat",
        "travis scott","playboi carti","21 savage","mac miller",
        "metallica","slipknot","gojira","bring me the horizon",
        "blue öyster cult","system of a down","rob zombie","motörhead",
        "miles davis","john coltrane",
    },
    "indie_folk_contamination": {
        "bon iver","fleet foxes","iron & wine","mumford & sons",
        "the lumineers","bob dylan","beach house","cocteau twins",
        "my bloody valentine","slowdive","hozier",
    },
    "dance_contamination": {
        "junior jack","edward maya","calvin harris","tim berg",
        "ariana grande","rihanna","nicki minaj","amy winehouse",
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# VIBE_TAG_MATRIX  v6.0
# ═══════════════════════════════════════════════════════════════════════════════
VIBE_TAG_MATRIX: dict[str, dict[str, list[str]]] = {
    "heartbreak": {
        "Hindi":      ["bollywood sad","filmi sad","arijit singh","atif aslam"],
        "Punjabi":    ["punjabi sad","b praak","jaani","punjabi heartbreak"],
        "English":    ["sad","heartbreak","indie sad","emo"],
        "Tamil":      ["kollywood sad","tamil sad songs","sid sriram"],
        "Telugu":     ["tollywood sad","telugu sad songs"],
        "Korean":     ["korean ballad","k-pop sad","korean indie sad"],
        "Japanese":   ["j-pop ballad","japanese sad","jpop sad"],
        "Spanish":    ["latin sad","reggaeton triste","bachata sad"],
        "Portuguese": ["mpb sad","saudade","fado"],
        "French":     ["chanson triste","french sad","french indie sad"],
        "Arabic":     ["arabic sad","arabic ballad","arabic heartbreak"],
        "Afrobeats":  ["afrobeats sad","afro-soul","afro heartbreak"],
        "Bengali":    ["bengali sad","rabindra sangeet sad"],
        "Urdu":       ["ghazal","urdu sad","rahat fateh ali khan"],
        "Kannada":    ["kannada sad songs","sandalwood sad"],
        "Malayalam":  ["malayalam sad songs","mollywood sad"],
        "Any":        ["sad","heartbreak"],
    },
    "romantic": {
        "Hindi":      ["bollywood romantic","hindi love songs","filmi romantic","ar rahman"],
        "Punjabi":    ["punjabi romantic","ap dhillon","punjabi love songs"],
        "English":    ["romantic","love songs","rnb","slow jams"],
        "Tamil":      ["kollywood romantic","tamil love songs","ar rahman tamil"],
        "Telugu":     ["tollywood romantic","telugu love songs"],
        "Korean":     ["k-pop romantic","korean love songs","k-ballad"],
        "Japanese":   ["j-pop romantic","japanese love songs","city pop"],
        "Spanish":    ["latin romantic","bachata","bolero"],
        "Portuguese": ["bossa nova","mpb romantic"],
        "French":     ["chanson romantique","french romantic"],
        "Arabic":     ["arabic romantic","arabic love songs"],
        "Afrobeats":  ["afrobeats romantic","afro rnb"],
        "Bengali":    ["bengali romantic","rabindra sangeet"],
        "Urdu":       ["ghazal romantic","urdu love songs"],
        "Kannada":    ["kannada romantic songs"],
        "Malayalam":  ["malayalam romantic songs"],
        "Any":        ["romantic","love songs"],
    },
    "happy": {
        "Hindi":      ["bollywood happy","hindi upbeat","bollywood fun","badshah"],
        "Punjabi":    ["bhangra","punjabi happy","punjabi dance"],
        "English":    ["happy","feel good","indie pop"],
        "Tamil":      ["kollywood happy","tamil upbeat songs"],
        "Telugu":     ["tollywood happy","telugu upbeat songs"],
        "Korean":     ["k-pop happy","k-pop upbeat"],
        "Japanese":   ["j-pop happy","japanese pop upbeat"],
        "Spanish":    ["latin pop","cumbia","salsa"],
        "Portuguese": ["pagode","axe","forro"],
        "French":     ["variete francaise","french pop happy"],
        "Arabic":     ["arabic pop happy","arabic upbeat"],
        "Afrobeats":  ["afrobeats","afropop","highlife"],
        "Bengali":    ["bengali happy songs","bengali folk"],
        "Urdu":       ["urdu happy","qawwali upbeat"],
        "Kannada":    ["kannada happy songs"],
        "Malayalam":  ["malayalam happy songs"],
        "Any":        ["happy","feel good"],
    },
    "party": {
        "Hindi":      ["bollywood dance","hindi club","hindi party","badshah"],
        "Punjabi":    ["bhangra","punjabi party","desi club","diljit dosanjh"],
        "English":    ["party","dance pop","club","edm"],
        "Tamil":      ["kollywood dance","tamil party songs"],
        "Telugu":     ["tollywood dance","telugu party songs"],
        "Korean":     ["k-pop dance","k-pop party"],
        "Japanese":   ["j-pop dance","japanese club"],
        "Spanish":    ["reggaeton","latin dance","perreo"],
        "Portuguese": ["funk carioca","baile funk"],
        "French":     ["french house","french electro"],
        "Arabic":     ["arabic dance","arabic pop party"],
        "Afrobeats":  ["afrobeats party","amapiano"],
        "Bengali":    ["bengali dance","bengali party songs"],
        "Urdu":       ["urdu party","desi party"],
        "Kannada":    ["kannada dance songs"],
        "Malayalam":  ["malayalam party songs"],
        "Any":        ["party","dance","club"],
    },
    "hype": {
        "Hindi":      ["desi hip hop","indian hip hop","hindi rap","divine"],
        "Punjabi":    ["punjabi trap","punjabi hip hop","karan aujla","sidhu moosewala"],
        "English":    ["hip-hop","trap","rap","drill"],
        "Tamil":      ["tamil rap","tamil hip hop"],
        "Telugu":     ["telugu rap","tollywood hype"],
        "Korean":     ["k-hip hop","korean rap"],
        "Japanese":   ["japanese hip hop","j-rap"],
        "Spanish":    ["reggaeton","latin trap","latin hip hop"],
        "Portuguese": ["funk carioca","trap brasileiro"],
        "French":     ["rap francais","french rap","afrotrap"],
        "Arabic":     ["arabic rap","arabic trap","mahraganat"],
        "Afrobeats":  ["afro trap","naija rap"],
        "Bengali":    ["bengali rap","bangla hip hop"],
        "Urdu":       ["urdu rap","desi rap"],
        "Kannada":    ["kannada rap"],
        "Malayalam":  ["malayalam rap"],
        "Any":        ["hip-hop","trap","rap"],
    },
    "calm": {
        "Hindi":      ["sufi","ghazal","hindi acoustic","bollywood soft"],
        "Punjabi":    ["punjabi sufi","punjabi acoustic","satinder sartaaj"],
        "English":    ["calm","acoustic","folk","singer-songwriter"],
        "Tamil":      ["tamil acoustic","carnatic calm","ar rahman soft"],
        "Telugu":     ["telugu soft songs","carnatic"],
        "Korean":     ["k-indie","korean folk","korean acoustic"],
        "Japanese":   ["japanese acoustic","j-folk","city pop mellow"],
        "Spanish":    ["latin acoustic","bossa nova","flamenco acoustic"],
        "Portuguese": ["bossa nova","mpb calm"],
        "French":     ["chanson calme","french acoustic"],
        "Arabic":     ["arabic calm","arabic acoustic"],
        "Afrobeats":  ["afro-soul","afro acoustic"],
        "Bengali":    ["rabindra sangeet","bengali acoustic","baul"],
        "Urdu":       ["ghazal","mehdi hassan"],
        "Kannada":    ["carnatic","kannada soft songs"],
        "Malayalam":  ["malayalam acoustic","carnatic malayalam"],
        "Any":        ["calm","acoustic","folk"],
    },
    "chill": {
        "Hindi":      ["hindi lofi","bollywood lofi","hindi chill"],
        "Punjabi":    ["punjabi chill","punjabi lofi"],
        "English":    ["chill","lofi hip hop","chillhop"],
        "Tamil":      ["tamil lofi","kollywood lofi"],
        "Telugu":     ["telugu lofi","tollywood lofi"],
        "Korean":     ["k-indie chill","korean lofi","k-rnb"],
        "Japanese":   ["city pop","japanese lofi","j-chill"],
        "Spanish":    ["latin chill","lofi latino"],
        "Portuguese": ["bossa nova chill","mpb lofi"],
        "French":     ["french chill","lofi french"],
        "Arabic":     ["arabic chill","arabic lofi"],
        "Afrobeats":  ["afro chill","alte"],
        "Bengali":    ["bengali lofi","bengali chill"],
        "Urdu":       ["urdu chill","sufi lofi"],
        "Kannada":    ["kannada lofi"],
        "Malayalam":  ["malayalam lofi"],
        "Any":        ["chill","lofi","chillhop"],
        "Any__focus": ["lofi hip hop","chillhop","jazz hop","study beats"],
        "Any__dreamy":["lofi hip hop","chillhop","lofi"],
        "English__focus": ["lofi hip hop","chillhop","nujabes","j dilla"],
    },
    "focus": {
        "Hindi":      ["hindi instrumental","ar rahman instrumental","indian classical"],
        "Punjabi":    ["punjabi instrumental","tabla focus"],
        "English":    ["focus","study","instrumental","ambient"],
        "Tamil":      ["carnatic instrumental","ar rahman instrumental"],
        "Telugu":     ["carnatic instrumental","telugu instrumental"],
        "Korean":     ["korean instrumental","k-indie instrumental"],
        "Japanese":   ["japanese instrumental","city pop instrumental"],
        "Spanish":    ["latin instrumental","flamenco instrumental"],
        "Portuguese": ["bossa nova instrumental","mpb instrumental"],
        "French":     ["french jazz instrumental","french classical"],
        "Arabic":     ["oud instrumental","arabic classical"],
        "Afrobeats":  ["afro instrumental"],
        "Bengali":    ["rabindra sangeet instrumental"],
        "Urdu":       ["sitar classical","urdu instrumental"],
        "Kannada":    ["carnatic instrumental"],
        "Malayalam":  ["carnatic instrumental","kerala percussion"],
        "Any":        ["focus","study","instrumental"],
    },
    "euphoric": {
        "Hindi":      ["bollywood dance","hindi euphoric","bollywood edm"],
        "Punjabi":    ["bhangra edm","punjabi edm"],
        "English":    ["euphoric","trance","edm","dance"],
        "Tamil":      ["kollywood dance euphoric","tamil edm"],
        "Telugu":     ["tollywood dance euphoric"],
        "Korean":     ["k-pop euphoric","k-edm"],
        "Japanese":   ["j-edm","japanese trance"],
        "Spanish":    ["reggaeton euphoric","latin edm"],
        "Portuguese": ["baile funk euphoric"],
        "French":     ["french house","french techno"],
        "Arabic":     ["arabic edm","mahraganat hype"],
        "Afrobeats":  ["amapiano euphoric","afrobeats rave"],
        "Bengali":    ["bengali edm"],
        "Urdu":       ["qawwali euphoric"],
        "Kannada":    ["kannada dance euphoric"],
        "Malayalam":  ["malayalam dance euphoric"],
        "Any":        ["euphoric","trance","edm"],
    },
    "soulful": {
        "Hindi":      ["ghazal","sufi","qawwali","nusrat fateh ali khan"],
        "Punjabi":    ["punjabi sufi","gurdas maan","satinder sartaaj"],
        "English":    ["soul","neo soul","rnb","gospel"],
        "Tamil":      ["carnatic devotional","sid sriram"],
        "Telugu":     ["carnatic","sp balasubrahmanyam"],
        "Korean":     ["korean rnb","k-rnb"],
        "Japanese":   ["japanese soul","j-rnb"],
        "Spanish":    ["latin soul","bolero","trova"],
        "Portuguese": ["samba soulful","mpb soul"],
        "French":     ["french soul","nu soul"],
        "Arabic":     ["tarab","arabic maqam","arabic classical"],
        "Afrobeats":  ["afro soul","highlife soul","african gospel"],
        "Bengali":    ["rabindra sangeet","nazrul sangeet","baul"],
        "Urdu":       ["ghazal","qawwali","abida parveen"],
        "Kannada":    ["carnatic","kannada devotional"],
        "Malayalam":  ["carnatic kerala","kerala devotional"],
        "Any":        ["soul","rnb","gospel"],
    },
    "retro": {
        "Hindi":      ["old bollywood","classic bollywood","90s bollywood","kishore kumar"],
        "Punjabi":    ["old punjabi songs","classic bhangra"],
        "English":    ["retro","classic rock","80s","70s"],
        "Tamil":      ["old kollywood","ilayaraja"],
        "Telugu":     ["old tollywood","sp balu"],
        "Korean":     ["korean retro","trot"],
        "Japanese":   ["city pop","j-pop 80s"],
        "Spanish":    ["latin retro","cumbia clasica","salsa clasica"],
        "Portuguese": ["mpb classica","bossa nova vintage"],
        "French":     ["ye-ye","chanson classique","french 60s"],
        "Arabic":     ["arabic classics","um kulthum"],
        "Afrobeats":  ["highlife classic","fela kuti"],
        "Bengali":    ["classic rabindra sangeet"],
        "Urdu":       ["classic ghazal","lata urdu"],
        "Kannada":    ["old kannada songs"],
        "Malayalam":  ["old malayalam songs","yesudas"],
        "Any":        ["retro","classic","oldies"],
    },
    "dreamy": {
        "Hindi":      ["bollywood soft","sufi dreamy","ar rahman dreamy"],
        "Punjabi":    ["punjabi dreamy","punjabi soft"],
        "English":    ["dream pop","shoegaze","ambient pop"],
        "Tamil":      ["ar rahman tamil dreamy","kollywood dreamy"],
        "Telugu":     ["ar rahman telugu","tollywood dreamy"],
        "Korean":     ["k-indie dreamy","korean dream pop"],
        "Japanese":   ["city pop dreamy","japanese dream pop"],
        "Spanish":    ["latin dreamy","bossa nova dreamy"],
        "Portuguese": ["bossa nova","mpb dreamy"],
        "French":     ["french dream pop","chanson reveuse"],
        "Arabic":     ["arabic dreamy","arabic ambient"],
        "Afrobeats":  ["afro dreamy","alte"],
        "Bengali":    ["bengali dreamy"],
        "Urdu":       ["ghazal dreamy","sufi soft"],
        "Kannada":    ["kannada soft dreamy"],
        "Malayalam":  ["malayalam dreamy"],
        "Any":        ["dream pop","shoegaze"],
    },
    "cinematic": {
        "Hindi":      ["ar rahman","bollywood cinematic","hindi film score","pritam"],
        "Punjabi":    ["punjabi cinematic"],
        "English":    ["cinematic","film score","epic","hans zimmer"],
        "Tamil":      ["ar rahman tamil","kollywood bgm","harris jayaraj"],
        "Telugu":     ["mm keeravani","tollywood bgm","dsp bgm"],
        "Korean":     ["k-drama ost","korean cinematic"],
        "Japanese":   ["anime ost","joe hisaishi","japanese film score"],
        "Spanish":    ["latin cinematic","spanish film score"],
        "Portuguese": ["brazilian film score"],
        "French":     ["french film score","yann tiersen"],
        "Arabic":     ["arabic cinematic","fairuz"],
        "Afrobeats":  ["african cinematic"],
        "Bengali":    ["satyajit ray score"],
        "Urdu":       ["urdu cinematic"],
        "Kannada":    ["sandalwood bgm"],
        "Malayalam":  ["mollywood bgm","m jayachandran"],
        "Any":        ["cinematic","film score","epic"],
    },
    "dark": {
        "Hindi":      ["hindi dark","bollywood dark","hindi noir"],
        "Punjabi":    ["punjabi dark"],
        "English":    ["dark","darkwave","post-punk","goth"],
        "Tamil":      ["kollywood dark","tamil dark songs"],
        "Telugu":     ["tollywood dark"],
        "Korean":     ["k-pop dark","korean dark pop"],
        "Japanese":   ["japanese dark","visual kei"],
        "Spanish":    ["latin dark","dark flamenco"],
        "Portuguese": ["fado dark","trap dark brasil"],
        "French":     ["french darkwave","new wave francaise"],
        "Arabic":     ["arabic dark"],
        "Afrobeats":  ["afrotrap dark"],
        "Bengali":    ["bengali dark"],
        "Urdu":       ["dark ghazal"],
        "Kannada":    ["kannada dark"],
        "Malayalam":  ["mollywood dark"],
        "Any":        ["dark","darkwave","goth"],
    },
    "intense": {
        "Hindi":      ["bollywood intense","hindi action songs","hindi rock"],
        "Punjabi":    ["punjabi intense"],
        "English":    ["metal","hardcore","intense","heavy metal"],
        "Tamil":      ["kollywood action","anirudh action"],
        "Telugu":     ["tollywood action","dsp action"],
        "Korean":     ["k-rock","korean metal"],
        "Japanese":   ["jrock intense","j-metal"],
        "Spanish":    ["latin metal","latin rock intense"],
        "Portuguese": ["rock brasileiro","heavy metal brasil"],
        "French":     ["metal francais"],
        "Arabic":     ["arabic rock","arabic metal"],
        "Afrobeats":  ["naija drill"],
        "Bengali":    ["bengali rock intense"],
        "Urdu":       ["qawwali intense"],
        "Kannada":    ["kannada intense"],
        "Malayalam":  ["mollywood action"],
        "Any":        ["metal","intense","hardcore"],
    },
    "rock": {
        "Hindi":      ["hindi rock","indian rock","bollywood rock"],
        "Punjabi":    ["punjabi rock"],
        "English":    ["rock","alternative rock","indie rock","classic rock"],
        "Tamil":      ["tamil rock","kollywood rock"],
        "Telugu":     ["telugu rock"],
        "Korean":     ["k-rock","korean rock"],
        "Japanese":   ["j-rock","japanese rock"],
        "Spanish":    ["rock en espanol","latin rock"],
        "Portuguese": ["rock brasileiro"],
        "French":     ["rock francais"],
        "Arabic":     ["arabic rock"],
        "Afrobeats":  ["afrorock"],
        "Bengali":    ["bangla rock"],
        "Urdu":       ["pakistani rock","junoon"],
        "Kannada":    ["kannada rock"],
        "Malayalam":  ["malayalam rock"],
        "Any":        ["rock","alternative rock"],
    },
    "indie_folk": {
        "Hindi":      ["indian folk","hindi folk","sufi folk","rajasthani folk"],
        "Punjabi":    ["punjabi folk"],
        "English":    ["indie folk","folk","folk pop"],
        "Tamil":      ["tamil folk","carnatic folk"],
        "Telugu":     ["telugu folk","telangana folk"],
        "Korean":     ["k-folk","korean indie folk"],
        "Japanese":   ["japanese folk","j-folk"],
        "Spanish":    ["trova","nueva cancion","flamenco folk"],
        "Portuguese": ["mpb folk","forro folk"],
        "French":     ["folk francais","chanson folk"],
        "Arabic":     ["arabic folk","arabic traditional"],
        "Afrobeats":  ["african folk","highlife folk"],
        "Bengali":    ["baul","folk bengali"],
        "Urdu":       ["lok geet","punjabi folk urdu"],
        "Kannada":    ["kannada folk","janapada songs"],
        "Malayalam":  ["kerala folk","mappila songs"],
        "Any":        ["indie folk","folk"],
    },
    "ambient": {
        "Hindi":      ["raga ambient","sitar ambient","indian classical ambient"],
        "Punjabi":    ["sarangi ambient"],
        "English":    ["ambient","drone","modern classical","neoclassical"],
        "Tamil":      ["carnatic ambient","ar rahman ambient"],
        "Telugu":     ["carnatic ambient"],
        "Korean":     ["korean ambient"],
        "Japanese":   ["japanese ambient","kankyo ongaku"],
        "Spanish":    ["latin ambient","flamenco ambient"],
        "Portuguese": ["bossa nova ambient"],
        "French":     ["french ambient"],
        "Arabic":     ["oud ambient","maqam ambient"],
        "Afrobeats":  ["african ambient"],
        "Bengali":    ["indian classical ambient"],
        "Urdu":       ["sufi ambient"],
        "Kannada":    ["carnatic ambient"],
        "Malayalam":  ["carnatic ambient"],
        "Any":        ["ambient","drone","modern classical"],
    },
    "desi": {
        "Hindi":      ["bollywood","hindi film","desi pop"],
        "Punjabi":    ["punjabi","bhangra","punjabi pop"],
        "Tamil":      ["kollywood","tamil film"],
        "Telugu":     ["tollywood","telugu film"],
        "Bengali":    ["bengali film"],
        "Urdu":       ["urdu film","pakistan pop"],
        "Kannada":    ["sandalwood","kannada film"],
        "Malayalam":  ["mollywood","malayalam film"],
        "Any":        ["bollywood","desi"],
    },
    "punjabi": {
        "Punjabi":      ["bhangra","punjabi pop","desi club","diljit dosanjh"],
        "Hindi":        ["bhangra","punjabi pop"],
        "Any":          ["bhangra","punjabi"],
        "Any__chill":   ["punjabi sad songs","ap dhillon","punjabi lofi","punjabi chill"],
        "Any__dark":    ["punjabi sad songs","punjabi ballad","punjabi dark","dard"],
        "Any__calm":    ["punjabi sad songs","punjabi romantic","punjabi ballad"],
        "Any__dreamy":  ["ap dhillon","punjabi lofi","punjabi soft","punjabi romantic"],
        "Any__heartbreak": ["punjabi sad songs","b praak","punjabi ballad","dard"],
        "Any__romantic":   ["punjabi romantic","ap dhillon","punjabi love songs"],
        "Any__soulful":    ["punjabi sufi","satinder sartaaj","punjabi classical"],
        "Any__ambient":    ["punjabi lofi","punjabi acoustic","sufi punjabi"],
    },
    "punjabi_soft": {
        "Punjabi":    ["punjabi sad songs","punjabi romantic","punjabi ballad","dard"],
        "Hindi":      ["punjabi sad songs","filmi sad","punjabi ballad"],
        "Any":        ["punjabi sad songs","punjabi ballad","dard","punjabi soft"],
    },
    "haryanvi": {
        "Hindi":      ["haryanvi","haryanvi folk songs","haryanvi pop","desi"],
        "Any":        ["haryanvi","haryanvi folk songs","desi folk"],
    },
    "hyperpop": {
        "English":    ["hyperpop","digicore","pc music","bubblegum bass"],
        "Korean":     ["k-pop hyperpop"],
        "Japanese":   ["j-hyperpop"],
        "Spanish":    ["latin hyperpop"],
        "Any":        ["hyperpop","digicore"],
    },
    "industrial": {
        "English":    ["industrial","ebm","dark techno","noise"],
        "French":     ["indus francais","ebm francais"],
        "Any":        ["industrial","ebm","dark techno"],
    },
    "tropical": {
        "Spanish":    ["reggaeton","latin dance","cumbia","dancehall"],
        "Portuguese": ["baile funk","pagode","axe"],
        "English":    ["tropical","dancehall","reggae","afrobeats"],
        "Afrobeats":  ["afrobeats","amapiano","naija pop"],
        "Any":        ["reggaeton","afrobeats","dancehall"],
    },
    "country": {
        "English":    ["country","americana","country pop","country rock"],
        "Spanish":    ["corridos","norteno","ranchera"],
        "Portuguese": ["sertanejo","country brasil"],
        "Any":        ["country","americana"],
    },
}

# ── VTM language patch (Vietnamese, Thai, Indonesian, etc.) ──────────────────
_VTM_PATCH: dict[str, dict[str, list[str]]] = {
    "happy": {
        "Vietnamese": ["v-pop","nhac tre","v-pop upbeat"],
        "Thai":       ["t-pop","thai pop","thai upbeat"],
        "Indonesian": ["pop indonesia","dangdut pop"],
        "Marathi":    ["marathi pop","marathi songs"],
        "Turkish":    ["türk pop","turkish pop"],
    },
    "party": {
        "Vietnamese": ["vinahouse","v-pop dance","nhac san"],
        "Thai":       ["thai edm","t-pop dance","thai club"],
        "Indonesian": ["dangdut koplo","pop indonesia dance"],
        "Marathi":    ["marathi dance","marathi party"],
        "Turkish":    ["türk dansı","turkish dance"],
    },
    "hype": {
        "Vietnamese": ["v-pop hype","vietnamese rap","viet rap"],
        "Thai":       ["thai rap","thai hip hop","t-pop hype"],
        "Indonesian": ["rap indonesia","hip hop indonesia"],
        "Marathi":    ["marathi rap","marathi hip hop"],
        "Turkish":    ["türkçe rap","turkish rap"],
    },
    "heartbreak": {
        "Vietnamese": ["v-pop buon","nhac buon","vietnamese sad"],
        "Thai":       ["thai sad songs","t-pop sad","thai heartbreak"],
        "Indonesian": ["pop indonesia sedih","lagu sedih indonesia"],
        "Marathi":    ["marathi sad songs"],
        "Turkish":    ["türk acı şarkılar","arabesk"],
    },
    "romantic": {
        "Vietnamese": ["nhac tình cảm","v-pop romantic","nhac vang"],
        "Thai":       ["thai love songs","t-pop romantic"],
        "Indonesian": ["pop romantis indonesia","lagu cinta indonesia"],
        "Marathi":    ["marathi love songs"],
        "Turkish":    ["türk aşk şarkıları","türk romantik"],
        "Urdu":       ["ghazal romantic","urdu love songs"],
    },
    "calm": {
        "Vietnamese": ["nhac thư giãn","vietnamese acoustic"],
        "Thai":       ["thai acoustic","thai calm"],
        "Indonesian": ["pop indonesia tenang","indonesian acoustic"],
        "Marathi":    ["marathi acoustic","marathi soft songs"],
        "Turkish":    ["türk akustik","türk halk müziği"],
    },
    "chill": {
        "Vietnamese": ["vietnamese lofi","v-pop chill"],
        "Thai":       ["thai lofi","t-pop chill"],
        "Indonesian": ["indonesian lofi","pop indonesia chill"],
        "Marathi":    ["marathi chill"],
        "Turkish":    ["türk lofi"],
    },
    "soulful": {
        "Vietnamese": ["nhac vang","bolero viet nam","vietnamese classic"],
        "Thai":       ["thai classic","luk thung","mor lam"],
        "Indonesian": ["dangdut classic","keroncong"],
        "Marathi":    ["marathi natya sangeet","marathi bhavgeet"],
        "Turkish":    ["türk sanat müziği","arabesk"],
    },
    "dreamy": {
        "Vietnamese": ["v-pop dreamy","vietnamese indie"],
        "Thai":       ["thai indie","t-pop dreamy"],
        "Indonesian": ["indie indonesia","pop indonesia dreamy"],
        "Marathi":    ["marathi indie"],
    },
    "indie_folk": {
        "Vietnamese": ["nhạc dân gian","vietnamese folk"],
        "Thai":       ["thai folk","t-pop indie"],
        "Indonesian": ["folk indonesia","indie pop indonesia"],
        "Marathi":    ["marathi folk","marathi lavani"],
        "Turkish":    ["türk halk müziği","türk folk"],
    },
    "focus": {
        "Vietnamese": ["vietnamese instrumental","v-pop lo-fi"],
        "Thai":       ["thai instrumental","thai study music"],
        "Indonesian": ["musik instrumental indonesia"],
        "Marathi":    ["marathi instrumental"],
    },
}

for _vibe, _lang_entries in _VTM_PATCH.items():
    if _vibe in VIBE_TAG_MATRIX:
        for _lang, _tags in _lang_entries.items():
            if _lang not in VIBE_TAG_MATRIX[_vibe]:
                VIBE_TAG_MATRIX[_vibe][_lang] = _tags
    else:
        VIBE_TAG_MATRIX[_vibe] = _lang_entries

# PATCH 5: Secondary vibe mood variants for heartbreak, chill, hype, dreamy, etc.
_SECONDARY_VIBE_PATCHES: dict[str, dict[str, list[str]]] = {
    "heartbreak": {
        "Any__dreamy":     ["slowcore","dream pop sad","shoegaze heartbreak","indie sad"],
        "Any__chill":      ["sad lofi","sad chillhop","heartbreak lofi","sad lo-fi hip hop"],
        "Any__dark":       ["dark sad","post-punk heartbreak","goth sad","darkwave sad"],
        "Any__ambient":    ["sad ambient","dark ambient sad","emotional ambient"],
        "Any__soulful":    ["sad soul","neo soul heartbreak","rnb heartbreak"],
        "Any__romantic":   ["love gone wrong","sad love songs","heartbreak ballad"],
        "Hindi__dreamy":   ["bollywood sad dreamy","sufi sad","hindi slow sad"],
        "Hindi__chill":    ["hindi sad lofi","bollywood lofi sad"],
        "Punjabi__dreamy": ["punjabi sad songs","punjabi ballad dreamy"],
        "Korean__dreamy":  ["k-pop ballad dreamy","korean indie sad"],
        "Tamil__dreamy":   ["kollywood sad ballad","tamil slow sad"],
    },
    "chill": {
        "Any__focus":      ["lofi hip hop","chillhop","jazz hop","study beats"],
        "Any__dreamy":     ["chillwave","dream pop chill","lo-fi ambient"],
        "Any__dark":       ["dark lofi","dark chillhop","late night chill dark"],
        "Any__soulful":    ["neo soul chill","rnb chill","soul chill"],
        "Any__romantic":   ["romantic lofi","chill love songs","smooth rnb"],
        "Any__heartbreak": ["sad lofi","heartbreak chill","emotional lofi"],
        "Hindi__focus":    ["hindi lofi study","bollywood lofi focus"],
        "Japanese__focus": ["japanese lofi","city pop study","j-lofi"],
        "Korean__focus":   ["k-indie chill study","korean lofi focus"],
    },
    "hype": {
        "Any__dark":       ["dark trap","phonk dark","rage dark","menacing trap"],
        "Any__intense":    ["trap metal","rage beats","aggressive trap"],
        "Any__euphoric":   ["euphoric trap","festival trap","melodic rap"],
        "Any__cinematic":  ["cinematic hip hop","epic rap","orchestral trap"],
        "Any__party":      ["party rap","club hip hop","dance rap"],
        "Hindi__dark":     ["dark desi hip hop","hindi trap dark"],
        "Punjabi__dark":   ["punjabi trap dark","dark punjabi"],
        "Tamil__dark":     ["kollywood action dark","tamil mass dark"],
    },
    "dreamy": {
        "Any__dark":       ["dark shoegaze","darkwave dreamy","witch house"],
        "Any__heartbreak": ["sad dream pop","heartbreak shoegaze","slowcore"],
        "Any__chill":      ["chillwave","dream pop chill","bedroom pop chill"],
        "Any__romantic":   ["romantic dream pop","dreamy love songs"],
        "Any__focus":      ["ambient study","dreamy instrumental","focus dream pop"],
        "Any__ambient":    ["ambient drone dreamy","ethereal ambient"],
        "Japanese__dark":  ["japanese dark dream pop","j-shoegaze dark"],
        "Korean__dark":    ["k-indie dark dreamy","korean dark indie"],
    },
    "ambient": {
        "Any__dark":       ["dark ambient","drone dark","industrial ambient"],
        "Any__focus":      ["focus ambient","study ambient","minimal ambient"],
        "Any__heartbreak": ["sad ambient","emotional ambient drone"],
        "Any__dreamy":     ["ethereal ambient","dreamy drone"],
    },
    "soulful": {
        "Any__chill":      ["soul chill","neo soul chill","late night soul"],
        "Any__romantic":   ["romantic soul","slow jam soul","love soul"],
        "Any__heartbreak": ["heartbreak soul","sad soul","blues soul"],
        "Any__dark":       ["dark soul","noir soul","soul jazz dark"],
        "Hindi__chill":    ["sufi chill","ghazal chill","hindi soul chill"],
        "English__chill":  ["neo soul chill","rnb late night"],
    },
}

for _dominant_vibe, _lang_entries in _SECONDARY_VIBE_PATCHES.items():
    if _dominant_vibe in VIBE_TAG_MATRIX:
        for _lang_key, _tags in _lang_entries.items():
            if _lang_key not in VIBE_TAG_MATRIX[_dominant_vibe]:
                VIBE_TAG_MATRIX[_dominant_vibe][_lang_key] = _tags

# PATCH 5b: Sync back to vibe_engine so batch tester reads same matrix
vibe_engine.VIBE_TAG_MATRIX = VIBE_TAG_MATRIX


def get_vibe_tags(dominant_vibe: str, language: str, fallback_tag: str, secondary_vibe: str | None = None) -> list[str]:
    REGIONAL_PRIORITY = {
        "Telugu","Tamil","Malayalam","Kannada","Bengali",
        "Urdu","Arabic","Spanish","Portuguese","French",
    }
    vibe_map = VIBE_TAG_MATRIX.get(dominant_vibe, {})
    tags = None

    if secondary_vibe:
        mood_key_lang = f"{language}__{secondary_vibe}"
        mood_key_any  = f"Any__{secondary_vibe}"
        tags = vibe_map.get(mood_key_lang) or vibe_map.get(mood_key_any)
        if tags:
            logger.info(f"[TagMatrix] Mood variant hit: {dominant_vibe}×{language} + secondary={secondary_vibe} → {tags}")

    if not tags:
        tags = vibe_map.get(language)

    if not tags and language in REGIONAL_PRIORITY:
        lang_map = LANGUAGE_TAG_MAP.get(language, {})
        regional_tag = lang_map.get(dominant_vibe) or lang_map.get("default")
        if regional_tag:
            tags = [regional_tag]
            logger.info(f"[TagMatrix] Regional override: {dominant_vibe}×{language} → {regional_tag}")

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


# ---------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class VibeRequest(BaseModel):
    text: str
    language: str | None = "Any"
    artist_focus: int = 50
    nicheness: int = 50
    bpm_focus: int = 50
    track_limit: int = 5
    use_secondary_vibe: bool = False
    override_genre: str | None = None
    override_artist: str | None = None
    excluded_tracks: list[dict] | None = None
    liked_artists: list[str] | None = None
    dismiss_detected_artist: bool = False
    refinement_of: str | None = None
    refinement_instruction: str | None = None

class TrackInfo(BaseModel):
    title: str
    artist: str
    spotify_uri: str
    apple_uri: str
    preview_url: str | None = None
    cover_art: str | None = None

class VibeResponse(BaseModel):
    request_id: str
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
    confidence_label: str = "exploring"
    vibe_story: str | None = None
    direct_genre_tag: str | None = None
    refinement_available: bool = True

class VibeStoryRequest(BaseModel):
    prompt: str
    dominant_vibe: str
    genres: list[str]
    matched_keywords: list[str]
    language: str = "Any"
    tracks: list[dict] = []
    confidence: float = 0.5

class PromptHistoryItem(BaseModel):
    id: str
    prompt: str
    dominant_vibe: str
    genres: list[str]
    confidence: float
    confidence_label: str
    track_count: int
    created_at: str

class FeedbackRequest(BaseModel):
    request_id: str
    track_title: str
    track_artist: str
    signal: int
    position: int
    preview_seconds: int | None = None


# ---------------------------------------------------------
# Auth helpers
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
# Network retry helper
# ---------------------------------------------------------
async def _fetch_with_retry(url: str, label: str, timeout: int = 5, max_retries: int = 2) -> dict | None:
    if _AIOHTTP_AVAILABLE:
        session = await _get_http_session()
        timeout_cfg = _aiohttp.ClientTimeout(total=timeout)
        label_lower = label.lower()
        is_lastfm = "last.fm" in label_lower or "lastfm" in label_lower
        is_itunes = "itunes" in label_lower

        sem = None
        if is_lastfm:
            sem = _LASTFM_SEMAPHORE
        elif is_itunes:
            sem = _ITUNES_SEMAPHORE

        for attempt in range(max_retries):
            try:
                if is_lastfm:
                    await _respect_lastfm_rate_limit()

                guard = sem if sem is not None else contextlib.nullcontext()
                async with guard:
                    async with session.get(url, timeout=timeout_cfg) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        if resp.status == 429:
                            backoff = min(4.0, 1.5 * (attempt + 1))
                            logger.warning(f"[Retry {attempt+1}/{max_retries}] {label} — HTTP 429. Backing off {backoff:.1f}s")
                            await asyncio.sleep(backoff)
                        else:
                            logger.warning(f"[Retry {attempt+1}] {label} — HTTP {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"[Retry {attempt+1}/{max_retries}] {label} — timeout after {timeout}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
            except Exception as e:
                wait = 0.5 * (2 ** attempt)
                if attempt < max_retries - 1:
                    logger.warning(f"[Retry {attempt+1}/{max_retries}] {label} — {e}. Backing off {wait:.1f}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"{label} failed after {max_retries} attempts: {e}")
        return None
    else:
        import urllib.request as _urllib_req
        def _sync_fetch():
            for attempt in range(max_retries):
                try:
                    req = _urllib_req.Request(url, headers={"User-Agent": "VibeFinderAI/2.0"})
                    with _urllib_req.urlopen(req, timeout=timeout) as r:
                        return json.loads(r.read().decode())
                except Exception as e:
                    wait = 0.5 * (2 ** attempt)
                    if attempt < max_retries - 1:
                        time.sleep(wait)
                    else:
                        logger.error(f"{label} failed after {max_retries} attempts: {e}")
            return None
        return await asyncio.to_thread(_sync_fetch)


# ---------------------------------------------------------
# Last.fm + iTunes fetchers
# ---------------------------------------------------------
import time as _time_module
_LASTFM_CACHE: dict[str, tuple[list, float]] = {}
_LASTFM_CACHE_TTL = 600

def _lastfm_cache_get(key: str) -> list | None:
    entry = _LASTFM_CACHE.get(key)
    if entry and _time_module.time() < entry[1]:
        return entry[0]
    return None

def _lastfm_cache_set(key: str, tracks: list) -> None:
    if len(_LASTFM_CACHE) > 500:
        now = _time_module.time()
        expired = [k for k, (_, exp) in _LASTFM_CACHE.items() if now >= exp]
        for k in expired:
            del _LASTFM_CACHE[k]
    _LASTFM_CACHE[key] = (tracks, _time_module.time() + _LASTFM_CACHE_TTL)

async def fetch_lastfm_tracks_sync(genre: str, limit: int = 200):
    cache_key = f"genre:{genre}:{limit}"
    cached = _lastfm_cache_get(cache_key)
    if cached is not None:
        logger.info(f"[LFM Cache HIT] genre='{genre}' ({len(cached)} tracks)")
        return cached
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm genre:'{genre}'")
    if data:
        tracks = data.get("tracks", {}).get("track", [])
        result = [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
        _lastfm_cache_set(cache_key, result)
        return result
    return []

async def fetch_lastfm_artist_tracks_sync(artist: str, limit: int = 200):
    cache_key = f"artist:{artist.lower()}:{limit}"
    cached = _lastfm_cache_get(cache_key)
    if cached is not None:
        return cached
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={urllib.parse.quote(artist)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm artist:'{artist}'")
    if data:
        tracks = data.get("toptracks", {}).get("track", [])
        result = [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
        _lastfm_cache_set(cache_key, result)
        return result
    return []

async def fetch_lastfm_track_search_sync(query: str, limit: int = 100):
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={urllib.parse.quote(query)}&api_key={api_key}&format=json&limit={limit}"
    data = await _fetch_with_retry(url, label=f"Last.fm direct track search for '{query}'")
    if data:
        tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist")} for t in tracks]
    return []

_ITUNES_CACHE: dict[str, dict] = {}
_ITUNES_CACHE_MAX = 2000

async def fetch_itunes_data_sync(title: str, artist: str):
    cache_key = f"{title.lower().strip()}|{artist.lower().strip()}"
    if cache_key in _ITUNES_CACHE:
        return _ITUNES_CACHE[cache_key]
    query = urllib.parse.quote(f"{title} {artist}")
    url   = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    data  = await _fetch_with_retry(url, label=f"iTunes:{title[:20]}", timeout=2, max_retries=1)
    result = {"preview_url": None, "cover_art": None}
    if data and data.get("resultCount", 0) > 0:
        track  = data["results"][0]
        result = {"preview_url": track.get("previewUrl"), "cover_art": track.get("artworkUrl100")}
    if len(_ITUNES_CACHE) >= _ITUNES_CACHE_MAX:
        oldest = list(_ITUNES_CACHE.keys())[:100]
        for k in oldest:
            del _ITUNES_CACHE[k]
    _ITUNES_CACHE[cache_key] = result
    return result

async def fetch_lastfm_tracks(genre: str, limit: int = 200):
    return await fetch_lastfm_tracks_sync(genre, limit)

async def fetch_lastfm_artist_tracks(artist: str, limit: int = 200):
    return await fetch_lastfm_artist_tracks_sync(artist, limit)

async def fetch_lastfm_track_search(query: str, limit: int = 100):
    return await fetch_lastfm_track_search_sync(query, limit)

async def fetch_itunes_preview(title: str, artist: str):
    return await fetch_itunes_data_sync(title, artist)


# ---------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------
def get_base_title(title: str) -> str:
    t = title.lower()
    t = t.split(" - ")[0]
    t = t.split(" (")[0]
    t = t.split(" feat")[0]
    t = t.split(" ft")[0]
    return t.strip()

def filter_and_score_tracks(tracks: list, request: VibeRequest, vibe_data: dict, is_fallback: bool = False):
    prompt_lower    = request.text.lower()
    dominant_vibe   = vibe_data.get("dominant_vibe", "")
    detected_song   = (vibe_data.get("detected_song") or "").lower()
    detected_artist = (vibe_data.get("detected_artist") or "").lower()
    target_genre_override = (vibe_data.get("target_genre_override") or vibe_data.get("dominant_vibe", "")).lower()

    bpm_knob = request.bpm_focus
    if bpm_knob <= 20:
        target_bpm_low, target_bpm_high = 50, 80
    elif bpm_knob <= 40:
        target_bpm_low, target_bpm_high = 70, 100
    elif bpm_knob <= 60:
        target_bpm_low, target_bpm_high = 85, 130
    elif bpm_knob <= 80:
        target_bpm_low, target_bpm_high = 110, 150
    else:
        target_bpm_low, target_bpm_high = 135, 220

    artist_weight = (request.artist_focus / 50.0) * 40
    nicheness     = request.nicheness
    pool_size     = max(len(tracks), 1)

    fast_markers = ["remix","mix","edit","club","fast","speed","drum"]
    slow_markers = ["acoustic","slowed","reverb","chill","lofi","ambient","slow"]

    _VIBE_AUDIO_PROFILE: dict[str, dict] = {
        "heartbreak":   {"valence_max": 0.45,"moodSad_min": 0.45,"energy_max": 0.65,"danceability_max": 0.55},
        "dark":         {"valence_max": 0.40,"energy_max": 0.70,"moodAggressive_min": 0.15,"moodElectronic_min": 0.10},
        "calm":         {"energy_max": 0.45,"moodRelaxed_min": 0.40,"acousticness_min": 0.25,"danceability_max": 0.50},
        "ambient":      {"energy_max": 0.35,"moodRelaxed_min": 0.50,"instrumentalness_min": 0.40,"speechiness_max": 0.10},
        "focus":        {"energy_max": 0.60,"moodRelaxed_min": 0.30,"instrumentalness_min": 0.30,"speechiness_max": 0.15,"danceability_max": 0.60},
        "chill":        {"energy_max": 0.65,"moodRelaxed_min": 0.25,"danceability_max": 0.70},
        "party":        {"moodParty_min": 0.45,"energy_min": 0.55,"danceability_min": 0.55},
        "euphoric":     {"moodParty_min": 0.40,"energy_min": 0.50,"valence_min": 0.45,"danceability_min": 0.45},
        "hype":         {"energy_min": 0.65,"moodAggressive_min": 0.20,"danceability_min": 0.40},
        "intense":      {"energy_min": 0.70,"moodAggressive_min": 0.35,"acousticness_max": 0.30},
        "soulful":      {"valence_min": 0.30,"moodHappy_min": 0.25,"acousticness_min": 0.20},
        "happy":        {"valence_min": 0.50,"moodHappy_min": 0.45,"danceability_min": 0.35},
        "romantic":     {"valence_min": 0.35,"moodSad_max": 0.40,"acousticness_min": 0.20,"danceability_max": 0.65},
        "dreamy":       {"energy_max": 0.55,"moodRelaxed_min": 0.25,"instrumentalness_min": 0.10},
        "indie_folk":   {"acousticness_min": 0.45,"moodAcoustic_min": 0.35,"energy_max": 0.65,"instrumentalness_max": 0.60},
        "retro":        {"acousticness_min": 0.15,"energy_max": 0.80},
        "cinematic":    {"instrumentalness_min": 0.50,"energy_min": 0.20,"speechiness_max": 0.10},
        "industrial":   {"moodElectronic_min": 0.35,"moodAggressive_min": 0.30,"acousticness_max": 0.20},
        "hyperpop":     {"moodElectronic_min": 0.40,"energy_min": 0.60,"danceability_min": 0.50},
        "tropical":     {"danceability_min": 0.50,"valence_min": 0.40,"energy_min": 0.35},
    }
    vibe_profile = _VIBE_AUDIO_PROFILE.get(dominant_vibe, {})

    _excluded_keys: set[str] = set()
    for et in (request.excluded_tracks or []):
        _excluded_keys.add(f"{(et.get('title','') or '').strip().lower()}|{(et.get('artist','') or '').strip().lower()}")

    _liked_artist_set: set[str] = {a.strip().lower() for a in (request.liked_artists or [])}

    # Speechiness junk filter using TRACK_FEATURE_INDEX
    _speechiness_filtered = []
    for _t in tracks:
        _fk   = f"{_t.get('title','').lower()}|{_t.get('artist','').lower()}"
        _feat = TRACK_FEATURE_INDEX.get(_fk)
        if _feat and _feat.get("speechiness") is not None:
            if _feat["speechiness"] > 0.65:
                continue
        _speechiness_filtered.append(_t)
    tracks = _speechiness_filtered

    scored_tracks = []
    for i, t in enumerate(tracks):
        title  = t.get("title", "").lower()
        artist = t.get("artist", "").lower()
        score  = 0.0

        if _excluded_keys and f"{title}|{artist}" in _excluded_keys:
            continue

        if is_fallback:
            score += 50

        if detected_song and (detected_song in title or title in detected_song):
            score += 100

        if (detected_artist and detected_artist == artist) or artist in prompt_lower:
            score += artist_weight

        if target_genre_override and (target_genre_override in title or target_genre_override in artist):
            score += 30
        for kw in vibe_data.get("matched_keywords", []):
            if kw.lower() in title or kw.lower() in artist:
                score += 20

        feat_key = f"{title}|{artist}"
        feat     = TRACK_FEATURE_INDEX.get(feat_key)

        if feat:
            real_bpm = feat.get("tempo")
            if real_bpm is not None:
                if target_bpm_low <= real_bpm <= target_bpm_high:
                    bpm_knob_strength = abs(bpm_knob - 50) / 50.0
                    score += 35 * bpm_knob_strength
                else:
                    overshoot = min(abs(real_bpm - target_bpm_low), abs(real_bpm - target_bpm_high))
                    penalty   = min(overshoot / 30.0, 1.0) * 20 * (abs(bpm_knob - 50) / 50.0)
                    score -= penalty

            energy = feat.get("energy")
            if energy is not None:
                if bpm_knob > 60:
                    energy_strength = (bpm_knob - 50) / 50.0
                    if bpm_knob >= 80:
                        energy_strength *= 2.0
                    score += energy * 25 * energy_strength
                    if bpm_knob >= 80 and energy < 0.45:
                        score -= (0.45 - energy) * 40 * energy_strength
                elif bpm_knob < 40:
                    energy_strength = (50 - bpm_knob) / 50.0
                    score += (1.0 - energy) * 25 * energy_strength

            # PATCH 4: removed dead variable — parse key directly
            mood_score   = 0.0
            profile_hits = 0
            for feat_key_name, threshold in vibe_profile.items():
                # Parse "energy_min", "valence_max", "moodSad_min" etc.
                parts           = feat_key_name.rsplit("_", 1)
                feat_name_clean = parts[0]
                direction       = parts[1]
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
                    mood_score -= (threshold - val) * 15
                elif direction == "max" and val > threshold:
                    mood_score -= (val - threshold) * 15
            if profile_hits > 0:
                score += mood_score / max(len(vibe_profile), 1)

        else:
            fast_hit = any(m in title for m in fast_markers)
            slow_hit = any(m in title for m in slow_markers)
            if bpm_knob > 60:
                bpm_strength = (bpm_knob - 50) / 50.0
                if fast_hit:
                    score += 30 * bpm_strength
                elif slow_hit:
                    penalty_mult = 2.0 if bpm_knob >= 80 else 1.0
                    score -= 20 * bpm_strength * penalty_mult
            elif bpm_knob < 40:
                bpm_strength = (50 - bpm_knob) / 50.0
                if slow_hit:
                    score += 30 * bpm_strength
                elif fast_hit:
                    score -= 20 * bpm_strength

        if "remix" in title or "edit" in title or "instrumental" in title:
            score -= 15

        position_pct = i / pool_size
        if nicheness < 40:
            mainstream_strength = (40 - nicheness) / 40.0
            score += (1.0 - position_pct) * 25 * mainstream_strength
        elif nicheness > 60:
            niche_strength = (nicheness - 60) / 40.0
            score += position_pct * 25 * niche_strength
        else:
            score += max(0.0, (1.0 - (i / max(pool_size, 100))) * 10.0)

        track_ident_bl = f"{title}|{artist}"
        if track_ident_bl in TRACK_BLOCKLIST:
            score -= 40

        _req_lang = getattr(request, "language", "Any") or "Any"
        if _req_lang not in ("English", "Any"):
            _genres_lower = " ".join(g.lower() for g in (vibe_data.get("genres") or []))
            if artist in LANGUAGE_ARTIST_BLOCKLIST["universal"]:
                score -= 60
            elif artist in LANGUAGE_ARTIST_BLOCKLIST["indie_folk_contamination"]:
                if any(w in _genres_lower for w in ("indie","folk","acoustic","lofi","ambient")):
                    score -= 55
            elif artist in LANGUAGE_ARTIST_BLOCKLIST["dance_contamination"]:
                if any(w in _genres_lower for w in ("dance","pop","party","funk","house","trap")):
                    score -= 55

        score += random.uniform(0, 1.5)

        if _liked_artist_set and artist in _liked_artist_set:
            score += 8.0

        t["score"] = round(score, 4)
        scored_tracks.append((score, t))

    scored_tracks.sort(key=lambda x: x[0], reverse=True)

    if scored_tracks and scored_tracks[0][0] < 15.0:
        boost = 15.5 - scored_tracks[0][0]
        logger.info(f"Restrictive pool detected (max score {scored_tracks[0][0]}). Applying +{boost:.1f} safety boost.")
        scored_tracks = [(s + boost, t) for s, t in scored_tracks]

    final_selection = []
    skipped_for_diversity = []
    artist_counts: dict = {}
    seen_base_titles: set = set()

    max_artist_tracks = 2
    if request.override_artist or request.artist_focus >= 80:
        max_artist_tracks = max(2, min(int(request.track_limit * 0.60), 15))
    hard_ceiling = max(2, int(request.track_limit * 0.40))
    max_artist_tracks = min(max_artist_tracks, hard_ceiling)

    for _, t in scored_tracks:
        art    = t.get("artist", "").lower()
        base_t = get_base_title(t.get("title", ""))
        track_ident = f"{art}|{base_t}"

        if track_ident in seen_base_titles:
            continue
        seen_base_titles.add(track_ident)

        if artist_counts.get(art, 0) >= max_artist_tracks:
            skipped_for_diversity.append(t)
            continue

        final_selection.append(t)
        artist_counts[art] = artist_counts.get(art, 0) + 1

        if len(final_selection) >= request.track_limit:
            break

    if len(final_selection) < request.track_limit:
        fallback_artist_counts = dict(artist_counts)
        for t in skipped_for_diversity:
            art = t.get("artist", "").lower()
            if fallback_artist_counts.get(art, 0) >= hard_ceiling:
                continue
            final_selection.append(t)
            fallback_artist_counts[art] = fallback_artist_counts.get(art, 0) + 1
            if len(final_selection) >= request.track_limit:
                break

    return final_selection

# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "VibeFinderAI API is operational."}

@app.get("/health")
async def health_check():
    try:
        await db.user.count()
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check DB ping failed: {e}")
        db_status = "degraded"
    import time as _t
    now = _t.time()
    lfm_live = sum(1 for _, exp in _LASTFM_CACHE.values() if now < exp)
    return {
        "status": "ok",
        "db": db_status,
        "service": "VibeFinderAI",
        "cache": {
            "lastfm_entries":   lfm_live,
            "itunes_entries":   len(_ITUNES_CACHE),
            "track_features":   len(TRACK_FEATURE_INDEX),
            "artist_niches":    len(ARTIST_NICHE_INDEX),
            "db_track_pool":    len(DB_TRACK_POOL),
            "db_similar_artists": len(DB_SIMILAR_ARTISTS),
            "artist_name_index": len(ARTIST_NAME_INDEX),
        },
        "http_session": "active" if (_HTTP_SESSION and not _HTTP_SESSION.closed) else "none",
    }

@app.get("/api/user/taste")
async def get_user_taste(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        feedbacks = await db.trackfeedback.find_many(
            where={"userId": user_id}, order={"createdAt": "desc"},
        )
        if not feedbacks:
            return {"total_ratings": 0, "top_vibes": [], "top_artists": [], "disliked_artists": [],
                    "message": "No feedback data yet — rate some tracks to build your taste profile!"}

        vibe_request_ids = list({f.vibeRequestId for f in feedbacks if f.vibeRequestId})
        vibe_requests = {}
        if vibe_request_ids:
            rows = await db.viberequest.find_many(where={"id": {"in": vibe_request_ids}})
            vibe_requests = {r.id: r for r in rows}

        vibe_score: dict[str, float]   = {}
        artist_score: dict[str, float] = {}

        for fb in feedbacks:
            signal = fb.signal
            artist = (fb.trackArtist or "").strip().lower()
            if artist:
                artist_score[artist] = artist_score.get(artist, 0.0) + signal
            if fb.vibeRequestId and fb.vibeRequestId in vibe_requests:
                vr   = vibe_requests[fb.vibeRequestId]
                vibe = vr.dominantVibe or ""
                if vibe:
                    vibe_score[vibe] = vibe_score.get(vibe, 0.0) + signal

        top_vibes    = sorted([(v, round(s, 1)) for v, s in vibe_score.items() if s > 0], key=lambda x: -x[1])[:5]
        top_artists  = sorted([(a, round(s, 1)) for a, s in artist_score.items() if s > 0], key=lambda x: -x[1])[:10]
        disliked     = sorted([(a, round(s, 1)) for a, s in artist_score.items() if s < 0], key=lambda x: x[1])[:5]

        return {
            "total_ratings":    len(feedbacks),
            "top_vibes":        [{"vibe": v, "score": s} for v, s in top_vibes],
            "top_artists":      [{"artist": a, "score": s} for a, s in top_artists],
            "disliked_artists": [{"artist": a, "score": s} for a, s in disliked],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/api/user/taste error: {e}")
        raise HTTPException(status_code=500, detail="Failed to build taste profile")

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    existing_user = await db.user.find_first(where={"OR": [{"email": user.email}, {"username": user.username}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Identity already exists")
    hashed_pwd = get_password_hash(user.password)
    new_user   = await db.user.create(data={"email": user.email, "username": user.username, "hashedPassword": hashed_pwd})
    return {"message": "Success", "user_id": new_user.id}

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.user.find_unique(where={"username": form_data.username})
    if not user or not verify_password(form_data.password, user.hashedPassword):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = create_access_token(data={"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user    = await db.user.find_unique(where={"id": user_id})
        return user
    except:
        raise HTTPException(status_code=401)


# ---------------------------------------------------------
# Main analyze endpoint
# ---------------------------------------------------------
@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    try:
        _pre_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        _pre_user_id = _pre_payload.get("sub")
        if not _pre_user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    logger.info(f"--- NEW REQUEST: '{request.text[:60]}' | Limit: {request.track_limit}")

    # Phase 9: Refinement merge
    if request.refinement_of and request.refinement_instruction:
        _merged = f"{request.refinement_of}, {request.refinement_instruction}"
        request = request.model_copy(update={"text": _merged})

    request = request.model_copy(update={"text": normalize_input(request.text)})

    vibe_data = vibe_engine.analyze_vibe_algorithm(
        text=request.text, artist_focus=request.artist_focus,
        genre_focus=50, bpm_focus=request.bpm_focus
    )

    # Gemini enhancement
    if _GEMINI_AVAILABLE and _gemini_enhancer and _gemini_enhancer.should_enhance(vibe_data, request.text):
        try:
            _enhanced = await _gemini_enhancer.enhance(request.text, request.language, vibe_data)
            if _enhanced:
                vibe_data = _enhanced
                if (not request.language or request.language == "Any") and vibe_data.get("_gemini_detected_language"):
                    request = request.model_copy(update={"language": vibe_data["_gemini_detected_language"]})
        except Exception as _ge:
            logger.warning(f"[Gemini] Enhancement skipped: {_ge}")

    # Sentiment boost
    if _SENTIMENT_AVAILABLE:
        try:
            vibe_data = apply_sentiment_boost(request.text, vibe_data)
        except Exception as _se:
            logger.warning(f"[Sentiment] Boost skipped: {_se}")

    prompt_lower      = request.text.lower()
    detected_artist   = request.override_artist
    detected_song     = None
    prompt_word_count = len(prompt_lower.split())

    NEGATION_TOKENS = {"not","no","don't","dont","nothing","avoid","except","without","skip","never"}

    def _is_negated_entity(entity: str, text: str) -> bool:
        pattern = rf'\b({"|".join(re.escape(n) for n in NEGATION_TOKENS)})\s+{re.escape(entity)}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    # PATCH 3: Entity scanner uses O(1) ARTIST_NAME_INDEX instead of db.find_many()
    if not detected_artist:
        try:
            _artist_source = list(ARTIST_NAME_INDEX.values()) if ARTIST_NAME_INDEX else []
            if not _artist_source:
                logger.warning("[EntityScanner] ARTIST_NAME_INDEX empty — falling back to DB query")
                _artist_source = await db.artistdirectory.find_many()

            _prompt_norm = _normalize_for_matching(request.text)

            for a in _artist_source:
                if not a.name or not re.search(r"\w", a.name):
                    continue
                artist_name = _normalize_for_matching(a.name)
                if len(artist_name) <= 10 and artist_name in COMMON_WORDS_BLACKLIST:
                    continue
                artist_pattern = rf'\b{re.escape(artist_name)}\b'
                if re.search(artist_pattern, _prompt_norm):
                    if _is_negated_entity(artist_name, prompt_lower):
                        continue
                    detected_artist = a.name
                    logger.info(f"Entity Scanner Locked Artist: {detected_artist}")
                    if a.songs:
                        song_list = [s.strip().lower() for s in a.songs.split(",")]
                        for s in song_list:
                            if s and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                                if _is_negated_entity(s, prompt_lower):
                                    continue
                                detected_song = s
                                logger.info(f"Entity Scanner Locked Song: {detected_song}")
                                break
                    break
                elif a.songs:
                    song_list = [s.strip().lower() for s in a.songs.split(",")]
                    for s in song_list:
                        if len(s) > 3 and s not in COMMON_WORDS_BLACKLIST and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                            if _is_negated_entity(s, prompt_lower):
                                continue
                            if prompt_word_count >= 10:
                                continue
                            detected_artist = a.name
                            detected_song   = s
                            logger.info(f"Entity Scanner Locked Song independently: {detected_song} by {detected_artist}")
                            break
                    if detected_artist:
                        break
        except Exception as e:
            logger.error(f"Entity Scan Error: {e}")

    vibe_data["detected_artist"] = detected_artist
    vibe_data["detected_song"]   = detected_song

    if request.dismiss_detected_artist and not request.override_artist:
        if detected_artist:
            logger.info(f"User dismissed detected artist lock '{detected_artist}' — clearing.")
        detected_artist = None
        detected_song   = None
        vibe_data["detected_artist"] = None
        vibe_data["detected_song"]   = None

    if detected_song and not detected_artist and vibe_data.get("confidence", 0) >= 0.30:
        vibe_data["detected_song"] = None

    # Target genre resolution
    _lang     = (request.language or "Any").strip()
    _dominant = vibe_data.get("dominant_vibe", "")
    active_vibe_for_tags = _dominant

    _direct_tag  = vibe_data.get("direct_genre_tag")
    _direct_lang = vibe_data.get("direct_genre_lang")

    # PATCH 6: Track original nicheness before boost
    _discovery_boost = int(vibe_data.get("discovery_nicheness_boost", 0))
    if _discovery_boost:
        _boosted_nicheness = min(95, request.nicheness + _discovery_boost)
        if _boosted_nicheness != request.nicheness:
            logger.info(f"[v6.0] Discovery modifier boost: nicheness {request.nicheness} → {_boosted_nicheness}")
            _original_nicheness = request.nicheness
            request = request.model_copy(update={"nicheness": _boosted_nicheness})
            vibe_data["_original_nicheness"] = _original_nicheness
            vibe_data["_boosted_nicheness"]  = _boosted_nicheness

    if _direct_tag and "bhojpuri" in _direct_tag and _lang in ("Hindi", "Any"):
        _lang = "Bhojpuri"
        request = request.model_copy(update={"language": "Bhojpuri"})

    if detected_artist and vibe_data.get("confidence", 0) < 0.10:
        vibe_data["dominant_vibe"] = "artist_driven"
        active_vibe_for_tags = "artist_driven"
        target_genre = None
    elif request.override_genre:
        target_genre = request.override_genre
        active_vibe_for_tags = "override"
        vibe_data["genres"] = [request.override_genre.title()]
    elif _direct_tag and not request.override_genre:
        _GENERIC_TAGS = {"pop","rock","folk","sad","ambient","classical","acoustic","hip-hop","soul","reggae","dance","electronic","alternative"}
        _lang_map_check = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
        _lang_override  = _lang_map_check.get(_dominant) or _lang_map_check.get("default")
        if _direct_tag in _GENERIC_TAGS and _lang not in ("English","Any") and _lang_override:
            target_genre = _lang_override
        else:
            target_genre = _direct_tag
            if _direct_lang and _lang == "Any":
                _lang = _direct_lang
                request = request.model_copy(update={"language": _direct_lang})
            vibe_data["genres"] = [_direct_tag.title()]
    elif request.use_secondary_vibe and vibe_data.get("secondary_vibe"):
        sec_vibe_name = vibe_data["secondary_vibe"]
        active_vibe_for_tags = sec_vibe_name
        mapped_genres = vibe_engine.VIBE_MAP.get(sec_vibe_name, {}).get("genres", [sec_vibe_name])
        _lang_map_sec = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
        target_genre  = _lang_map_sec.get(sec_vibe_name) or _lang_map_sec.get("default") or mapped_genres[0]
    else:
        _lang_map = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
        target_genre = _lang_map.get(_dominant) or _lang_map.get("default") or vibe_data.get("genres", ["electronic"])[0]
        REGIONAL_LANGS = {"Telugu","Malayalam","Kannada","Tamil","Marathi","Bengali","Assamese","Urdu","Punjabi"}
        if _dominant == "cinematic" and _lang in REGIONAL_LANGS:
            regional_cinematic = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {}).get("cinematic") or \
                                  vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {}).get("default")
            if regional_cinematic:
                target_genre = regional_cinematic

    vibe_data["target_genre_override"] = target_genre

    # Pool fetch
    is_fallback  = False
    used_semantic = False

    if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
        is_fallback = True
        logger.warning(f"Engine Confidence Critical ({vibe_data.get('confidence')} < 0.25). Triggering Fallback Protocol!")

        _lang_fallback_tags: dict[str, list[str]] = {
            "Japanese":   ["j-pop","city pop","japanese pop"],
            "Korean":     ["k-pop","k-indie","korean pop"],
            "Tamil":      ["kollywood","tamil pop","tamil film music"],
            "Telugu":     ["tollywood","telugu film music"],
            "Kannada":    ["kannada","sandalwood"],
            "Malayalam":  ["malayalam film music","mollywood"],
            "Hindi":      ["bollywood","hindi pop"],
            "Bengali":    ["bengali modern","bengali film songs"],
            "Punjabi":    ["punjabi pop","bhangra"],
            "Urdu":       ["ghazal","urdu pop"],
            "Arabic":     ["arabic pop","khaleeji"],
            "Spanish":    ["latin pop","reggaeton"],
            "Portuguese": ["mpb","brazilian pop"],
            "French":     ["variété française","french pop"],
            "Afrobeats":  ["afrobeats","afropop"],
        }
        _fallback_lang = _lang or "Any"
        _lang_tags = _lang_fallback_tags.get(_fallback_lang)

        if _lang_tags:
            vibe_data["dominant_vibe"] = _lang_tags[0].replace(" ", "_")
            vibe_data["secondary_vibe"] = "Fallback Mode"
            _fallback_results = await asyncio.gather(
                *[fetch_lastfm_tracks(tag, limit=80) for tag in _lang_tags], return_exceptions=True
            )
            raw_pool = []
            for _r in _fallback_results:
                if isinstance(_r, list):
                    raw_pool.extend(_r)
        else:
            vibe_data["dominant_vibe"] = "Direct Search"
            vibe_data["secondary_vibe"] = "Fallback Mode"
            raw_pool = await fetch_lastfm_track_search(request.text, limit=100)

        if not raw_pool:
            _STOPWORDS = {"a","an","the","and","or","but","for","with","at","by","of","in","on","to","is","it","my","me","we","be","as","so","up","type","vibe","music","songs","playlist","feel","feeling","i","need","want","give"}
            _tokens = [w for w in re.sub(r"[^\w\s]"," ",request.text.lower()).split() if w not in _STOPWORDS and len(w) > 2]
            _stage1_query = " ".join(_tokens[:4])
            if _stage1_query:
                raw_pool = await fetch_lastfm_track_search(_stage1_query, limit=100)

        if not raw_pool:
            _all_tokens = [w for w in re.sub(r"[^\w\s]"," ",request.text.lower()).split() if len(w) > 3]
            if _all_tokens:
                raw_pool = await fetch_lastfm_artist_tracks(artist=max(_all_tokens, key=len), limit=100)

        if not raw_pool:
            raw_pool = await semantic_search.get_thin_pool_supplement(_lang, _dominant, db)

        if not raw_pool:
            _s3_results = await asyncio.gather(
                fetch_lastfm_tracks("dream pop", limit=60),
                fetch_lastfm_tracks("indie pop", limit=60),
                fetch_lastfm_tracks("chillwave", limit=60),
                return_exceptions=True,
            )
            for _r in _s3_results:
                if isinstance(_r, list):
                    raw_pool.extend(_r)

        JUNK_PATTERNS = re.compile(
            r'\b(podcast|episode|news|npr|bbc|ted talk|morning edition|kitchen nightmares|speedrunning|'
            r'how to make|react(?:ion)?|compilation|highlights|sound effect|relaxing spa|nature music|'
            r'meditation music|music box|bitcoin|crypto|tutorial|lesson|course|lecture|audiobook|'
            r'music video|official video|ep remix|drum solo|live performance)\b|\.com\b|\.fm\b|\.net\b|\.org\b',
            re.IGNORECASE
        )
        raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(f"{t.get('title','')} {t.get('artist','')}")
                    and len(t.get('title','')) < 120]
        _JUNK_ARTIST = re.compile(r'^[^\w]+$')
        raw_pool = [t for t in raw_pool if t.get('artist') and not _JUNK_ARTIST.match(t.get('artist',''))]

        if _SEMANTIC_MODULE_AVAILABLE and semantic_search.semantic_ready() and raw_pool:
            raw_pool  = await asyncio.to_thread(semantic_search.rank_tracks_by_prompt, request.text, raw_pool)
            used_semantic = True

    elif request.override_artist or vibe_data.get("dominant_vibe") == "artist_driven":
        artist_target = request.override_artist or detected_artist
        raw_pool = await fetch_lastfm_artist_tracks(artist=artist_target, limit=200)
    else:
        _dominant_vibe = vibe_data.get("dominant_vibe", "")
        if _dominant_vibe == "unknown" and not request.override_genre:
            is_fallback = True
            genre_pool  = await fetch_lastfm_track_search(request.text, limit=150)
        else:
            # DB-first pool
            _db_first_pool: list[dict] = []
            _DB_VIBE_NICHES: dict[str, list[str]] = {
                "heartbreak":["sadboy","sad","heartbreak","emo","indie sad"],
                "chill":     ["chill","lo-fi","rnb chill","chillhop"],
                "focus":     ["lo-fi","chillhop","ambient","instrumental"],
                "ambient":   ["ambient","neo-classical","drone"],
                "hype":      ["trap","hip-hop","rap","drill"],
                "party":     ["house","techno","dancehall","party"],
                "euphoric":  ["trance","house","edm"],
                "dark":      ["darkwave","shoegaze","post-punk","goth"],
                "intense":   ["metal","metalcore","hardcore"],
                "soulful":   ["neo-soul","soul","rnb"],
                "romantic":  ["soul","rnb","slow jams"],
                "dreamy":    ["dream pop","shoegaze","indie pop"],
                "retro":     ["classic rock","oldies","retro"],
                "indie_folk":["folk","indie folk","americana"],
                "cinematic": ["film score","neo-classical","soundtrack"],
                "happy":     ["pop","indie pop","feel good"],
                "rock":      ["rock","alternative","indie rock"],
                "calm":      ["acoustic","singer-songwriter","folk"],
            }
            _target_niches_db = _DB_VIBE_NICHES.get(_dominant_vibe, [])
            if _target_niches_db and ARTIST_NICHE_INDEX and DB_TRACK_POOL:
                _db_artist_candidates: list[str] = []
                for _niche in _target_niches_db:
                    for _art_entry in ARTIST_NICHE_INDEX.get(_niche, []):
                        _db_artist_candidates.append(_art_entry["name"].lower())
                _seen_db: set[str] = set()
                for _ak in set(_db_artist_candidates):
                    for _dt in DB_TRACK_POOL.get(_ak, []):
                        _dk = f"{_dt['title'].lower()}|{_dt['artist'].lower()}"
                        if _dk not in _seen_db:
                            _seen_db.add(_dk)
                            _db_first_pool.append(_dt)

            _secondary_vibe_hint = vibe_data.get("secondary_vibe") if not request.use_secondary_vibe else None
            _vibe_tags = get_vibe_tags(active_vibe_for_tags, _lang, target_genre, secondary_vibe=_secondary_vibe_hint)
            logger.info(f"Multi-tag fetch: lang={_lang} vibe={active_vibe_for_tags} tags={_vibe_tags}")

            if len(_db_first_pool) >= 40:
                genre_pool: list[dict] = _db_first_pool
            else:
                _per_tag_limit = max(60, 200 // len(_vibe_tags))
                _tag_results = await asyncio.gather(
                    *[fetch_lastfm_tracks(tag, limit=_per_tag_limit) for tag in _vibe_tags],
                    return_exceptions=True
                )
                genre_pool = list(_db_first_pool)
                for _r in _tag_results:
                    if isinstance(_r, list):
                        genre_pool.extend(_r)

            _seed_artists: list[str] = vibe_engine.VIBE_MAP.get(active_vibe_for_tags, {}).get("artists", [])[:3]
            _seed_pool: list[dict] = []
            if _seed_artists:
                _need_lastfm_seed: list[str] = []
                for _sa in _seed_artists:
                    _sa_key = _sa.strip().lower()
                    _db_seed_tracks = DB_TRACK_POOL.get(_sa_key, [])
                    if _db_seed_tracks:
                        _seed_pool.extend(_db_seed_tracks)
                    else:
                        _need_lastfm_seed.append(_sa)
                if _need_lastfm_seed:
                    _seed_results = await asyncio.gather(
                        *[fetch_lastfm_artist_tracks(a, limit=30) for a in _need_lastfm_seed],
                        return_exceptions=True
                    )
                    for _r in _seed_results:
                        if isinstance(_r, list):
                            _seed_pool.extend(_r)

            artist_pool: list[dict] = []
            if detected_artist and request.artist_focus > 25:
                _det_key      = detected_artist.strip().lower()
                _det_db_tracks = DB_TRACK_POOL.get(_det_key, [])
                if _det_db_tracks:
                    artist_pool.extend(_det_db_tracks)
                else:
                    artist_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=50)
                if request.artist_focus > 50 and DB_SIMILAR_ARTISTS:
                    _lb_similars = DB_SIMILAR_ARTISTS.get(_det_key, [])
                    for _sim_name in _lb_similars[:3]:
                        _sim_key = _sim_name.strip().lower()
                        _sim_db  = DB_TRACK_POOL.get(_sim_key, [])
                        if _sim_db:
                            artist_pool.extend(_sim_db[:8])

            db_artist_pool: list[dict] = []
            if request.artist_focus > 65 and ARTIST_NICHE_INDEX:
                _VIBE_TO_DB_NICHE: dict[str, list[str]] = {
                    "chill":["lastfm top rnb","lastfm top alternative"],
                    "focus":["lastfm top electronic","lastfm top ambient"],
                    "ambient":["lastfm top ambient","lastfm top neo-classical"],
                    "heartbreak":["lastfm top soul","lastfm top rnb","lastfm top alternative"],
                    "hype":["lastfm top hip-hop","lastfm top trap","lastfm top rap"],
                    "party":["lastfm top house","lastfm top techno","lastfm top dancehall"],
                    "euphoric":["lastfm top house","lastfm top techno"],
                    "dark":["lastfm top industrial","lastfm top shoegaze"],
                    "intense":["lastfm top metalcore","lastfm top deathcore","lastfm top metal"],
                    "rock":["lastfm top classic rock","lastfm top indie rock","lastfm top alternative"],
                    "retro":["lastfm top classic rock","lastfm top soul","lastfm top jazz"],
                    "indie_folk":["lastfm top folk","lastfm top americana"],
                    "dreamy":["lastfm top dream pop","lastfm top shoegaze"],
                    "soulful":["lastfm top soul","lastfm top rnb"],
                    "romantic":["lastfm top soul","lastfm top rnb"],
                    "cinematic":["lastfm top film score","lastfm top neo-classical"],
                    "happy":["lastfm top pop","lastfm top soul"],
                }
                target_niches = _VIBE_TO_DB_NICHE.get(_dominant_vibe, [])
                if target_niches:
                    import random as _rand
                    db_candidates: list[dict] = []
                    for niche_key in target_niches:
                        db_candidates.extend(ARTIST_NICHE_INDEX.get(niche_key, []))
                    sample_size = min(3, len(db_candidates))
                    if sample_size:
                        sampled = _rand.sample(db_candidates, sample_size)
                        _need_lastfm_supp: list[str] = []
                        for _sa_entry in sampled:
                            _sa_key = _sa_entry["name"].strip().lower()
                            _db_supp_tracks = DB_TRACK_POOL.get(_sa_key, [])
                            if _db_supp_tracks:
                                db_artist_pool.extend(_db_supp_tracks)
                            else:
                                _need_lastfm_supp.append(_sa_entry["name"])
                        if _need_lastfm_supp:
                            _db_fetch_results = await asyncio.gather(
                                *[fetch_lastfm_artist_tracks(a, limit=25) for a in _need_lastfm_supp],
                                return_exceptions=True,
                            )
                            for _r in _db_fetch_results:
                                if isinstance(_r, list):
                                    db_artist_pool.extend(_r)

            merged_pool = genre_pool + _seed_pool + artist_pool + db_artist_pool
            seen: set[str] = set()
            raw_pool: list[dict] = []
            for t in merged_pool:
                ident = f"{t['title'].lower()}|{t['artist'].lower()}"
                if ident not in seen:
                    seen.add(ident)
                    raw_pool.append(t)

            _GLOBAL_JUNK = re.compile(
                r'\b(podcast|episode|radio show|chutneyradio|internet radio|dj set|compilation|highlights|'
                r'tutorial|audiobook|music video|official video|ep remix|drum solo|live performance)\b|\.com\b|\.fm\b',
                re.IGNORECASE
            )
            raw_pool = [t for t in raw_pool
                        if not _GLOBAL_JUNK.search(f"{t.get('title','')} {t.get('artist','')}")
                        and len(t.get('title','')) < 120]

            # Heartbreak top-up
            if vibe_data.get("dominant_vibe") == "heartbreak" and len(raw_pool) < 100:
                _hb_fetches = await asyncio.gather(*[
                    fetch_lastfm_tracks(genre=tag, limit=60)
                    for tag in ["sad indie","breakup songs","sad pop","indie sad"]
                ])
                _hb_seen = {f"{t['title'].lower()}|{t['artist'].lower()}" for t in raw_pool}
                for _hb_track in [t for sublist in _hb_fetches for t in sublist]:
                    _hb_key = f"{_hb_track['title'].lower()}|{_hb_track['artist'].lower()}"
                    if _hb_key not in _hb_seen:
                        raw_pool.append(_hb_track)
                        _hb_seen.add(_hb_key)

            # Thin pool guard
            _THIN_VIBE_ARTISTS: dict[str, list[str]] = {
                "punjabi_soft": ["B Praak","AP Dhillon","Satinder Sartaaj","Prabh Gill","Jassi Gill","Ninja","Mankirt Aulakh"],
                "haryanvi":     ["Sapna Choudhary","Masoom Sharma","Raju Punjabi","Pardeep Boora","Ajay Hooda","Renuka Panwar"],
                "bollywood_sad":["Arijit Singh","Atif Aslam","KK","Mohit Chauhan","Shreya Ghoshal","Jubin Nautiyal","Armaan Malik"],
                "Telugu|hype":  ["Allu Arjun","Devi Sri Prasad","S. Thaman","Ram Miriyala","Anirudh Ravichander"],
                "Telugu|cinematic": ["M.M. Keeravani","Devi Sri Prasad","S. Thaman","Mani Sharma"],
                "Bengali|rock": ["Fossils","Cactus","Rupam Islam","Chandrabindoo","Bhoomi"],
                "Bengali|soulful": ["Anupam Roy","Arnob","Srikanta Acharya","Lopamudra Mitra"],
            }
            _dominant_vibe_check = vibe_data.get("dominant_vibe", "")
            _compound_key = f"{_lang}|{_dominant_vibe_check}"
            _thin_key = (
                _compound_key if _compound_key in _THIN_VIBE_ARTISTS
                else _dominant_vibe_check if _dominant_vibe_check in _THIN_VIBE_ARTISTS
                else None
            )
            _thin_threshold = max(40, int(request.track_limit * 3.0))
            if _thin_key and len(raw_pool) < _thin_threshold:
                _supplement_fetches = await asyncio.gather(*[
                    fetch_lastfm_artist_tracks(a, limit=40) for a in _THIN_VIBE_ARTISTS[_thin_key]
                ], return_exceptions=True)
                _sup_seen = {f"{t['title'].lower()}|{t['artist'].lower()}" for t in raw_pool}
                for _result in _supplement_fetches:
                    if isinstance(_result, list):
                        for _st in _result:
                            _sk = f"{_st['title'].lower()}|{_st['artist'].lower()}"
                            if _sk not in _sup_seen:
                                raw_pool.append(_st)
                                _sup_seen.add(_sk)

    if not raw_pool:
        raise HTTPException(status_code=404, detail="Signal lost: Zero results found. Please rephrase your query.")

    best_tracks = filter_and_score_tracks(raw_pool, request, vibe_data, is_fallback=is_fallback)

    if used_semantic and best_tracks and any("semantic_score" in t for t in best_tracks):
        if _SEMANTIC_MODULE_AVAILABLE:
            best_tracks = semantic_search.blend_semantic_scores(best_tracks, semantic_weight=0.35)
        best_tracks = best_tracks[:request.track_limit]

    if not best_tracks:
        raise HTTPException(status_code=404, detail="Signal lost: No tracks passed filters.")

    # Preview scraping
    _itunes_needed: list[int] = []
    _previews: list[dict] = [{"preview_url": None, "cover_art": None}] * len(best_tracks)

    for _idx, _t in enumerate(best_tracks):
        _fk   = f"{_t.get('title','').strip().lower()}|{_t.get('artist','').strip().lower()}"
        _feat = TRACK_FEATURE_INDEX.get(_fk)
        if _feat and _feat.get("spotifyId"):
            _t["_spotify_id"] = _feat["spotifyId"]
        else:
            _itunes_needed.append(_idx)

    if _itunes_needed:
        _itunes_tasks   = [fetch_itunes_preview(best_tracks[i]["title"], best_tracks[i]["artist"]) for i in _itunes_needed]
        _itunes_results = await asyncio.gather(*_itunes_tasks)
        for _ii, _res in zip(_itunes_needed, _itunes_results):
            _previews[_ii] = _res

    final_tracks = []
    for i, t in enumerate(best_tracks):
        q          = urllib.parse.quote(f"{t['title']} {t['artist']}")
        _spotify_id = t.get("_spotify_id")
        final_tracks.append({
            "title":       t["title"],
            "artist":      t["artist"],
            "spotify_uri": f"spotify:track:{_spotify_id}" if _spotify_id else f"spotify:search:{q}",
            "apple_uri":   f"music://search?term={q}",
            "preview_url": _previews[i]["preview_url"],
            "cover_art":   _previews[i]["cover_art"],
        })

    # PATCH 7: Log effective nicheness to DB
    import json as _json
    vibe_request_id  = None
    _logged_nicheness = request.nicheness  # already boosted if PATCH 6 fired
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id  = payload.get("sub")
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
            "nicheness":       _logged_nicheness,
            "bpmFocus":        request.bpm_focus,
            "trackLimit":      request.track_limit,
            "usedFallback":    is_fallback,
            "usedSemantic":    used_semantic,
            "returnedTracks":  _json.dumps([{"title": t["title"], "artist": t["artist"]} for t in final_tracks]),
        })
        vibe_request_id = vibe_request_row.id
    except Exception as e:
        logger.error(f"Failed to log VibeRequest to DB: {e}")

    vibe_data["tracks"]      = final_tracks
    vibe_data["request_id"]  = vibe_request_id or "unlogged"

    _conf = float(vibe_data.get("confidence", 0.0))
    vibe_data["confidence_label"]    = "nailed it" if _conf >= 0.70 else "best guess" if _conf >= 0.50 else "exploring"
    vibe_data["direct_genre_tag"]    = vibe_data.get("direct_genre_tag") or None
    vibe_data["refinement_available"] = True
    vibe_data["vibe_story"]          = None

    logger.info(f"--- SUCCESS: Returning {len(final_tracks)} tracks ---")
    return vibe_data


# ═══════════════════════════════════════════════════════════════════════════════
# VIBE STORY
# ═══════════════════════════════════════════════════════════════════════════════
_VIBE_STORY_PROMPT = """You are VibeFinderAI's explanation engine. Write exactly 2 sentences:
1. What musical territory the user is in (name the vibe, genre, era if relevant)
2. Why these specific tracks fit — what the engine listened for
Tone: warm, knowledgeable, like a friend who knows a lot about music.
No preamble. Just 2 sentences. Under 60 words total.
Return only the 2 sentences. No quotes, no JSON, no markdown."""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

@app.post("/api/vibe/story")
async def generate_vibe_story(req: VibeStoryRequest, token: str = Depends(oauth2_scheme)):
    if not GEMINI_API_KEY:
        return {"story": None}
    top_tracks_str = ", ".join(f"{t.get('title','')}" for t in req.tracks[:3] if t.get("title"))
    user_msg = (
        f'User prompt: "{req.prompt}"\nLanguage: {req.language}\n'
        f'Vibe: {req.dominant_vibe} ({req.confidence:.0%} confidence)\n'
        f'Genres: {", ".join(req.genres[:3])}\nSignals: {", ".join(req.matched_keywords[:5])}\n'
        f'Top tracks: {top_tracks_str or "see genres"}\nWrite the 2-sentence vibe story:'
    )
    _url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": _VIBE_STORY_PROMPT}, {"text": user_msg}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 120},
    }
    try:
        import aiohttp as _aio
        async with _aio.ClientSession(timeout=_aio.ClientTimeout(total=6)) as sess:
            async with sess.post(_url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                if resp.status != 200:
                    return {"story": None}
                raw   = await resp.json()
                story = raw["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"\'')
                return {"story": story}
    except Exception as e:
        logger.warning(f"[VibeStory] {e}")
        return {"story": None}


@app.get("/api/vibe/history")
async def get_vibe_history(limit: int = 10, token: str = Depends(oauth2_scheme), db: Prisma = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        rows = await db.viberequest.find_many(
            where={"userId": user_id}, order={"createdAt": "desc"}, take=min(limit, 20),
        )
    except Exception as e:
        logger.error(f"[History] DB: {e}")
        return {"history": []}

    import json as _j
    history = []
    for row in rows:
        conf  = float(row.confidence or 0.0)
        label = "nailed it" if conf >= 0.70 else "best guess" if conf >= 0.50 else "exploring"
        try:
            genres = _j.loads(row.genres or "[]")
        except Exception:
            genres = []
        try:
            track_count = len(_j.loads(row.returnedTracks or "[]"))
        except Exception:
            track_count = 0
        history.append({
            "id":           row.id,
            "prompt":       row.promptText or "",
            "dominant_vibe": row.dominantVibe or "unknown",
            "genres":        genres[:3],
            "confidence":    round(conf, 2),
            "confidence_label": label,
            "track_count":   track_count,
            "created_at":    row.createdAt.isoformat() if row.createdAt else "",
        })
    return {"history": history}


@app.post("/api/feedback", status_code=201)
async def submit_feedback(feedback: FeedbackRequest, token: str = Depends(oauth2_scheme)):
    if feedback.signal not in (-1, 0, 1):
        raise HTTPException(status_code=422, detail="signal must be -1, 0, or 1")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

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
        logger.info(f"Feedback logged: [{signal_label}] '{feedback.track_title}' (pos={feedback.position})")
        return {"status": "ok", "id": row.id}
    except Exception as e:
        logger.error(f"Feedback: write error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")


@app.get("/api/lastfm/proxy")
async def lastfm_proxy(request: Request):
    LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
    if not LASTFM_API_KEY:
        raise HTTPException(status_code=500, detail="Last.fm API key not configured")

    params = dict(request.query_params)
    params["api_key"] = LASTFM_API_KEY
    params["format"] = "json"

    timeout = httpx.Timeout(connect=4.0, read=8.0, write=4.0, pool=4.0)
    last_exc: Exception | None = None

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get("https://ws.audioscrobbler.com/2.0/", params=params)

            # Last.fm often returns HTTP 200 even when payload is an API error.
            data = r.json()
            if "error" in data:
                logger.warning(
                    f"[LFM Proxy] Last.fm API error {data['error']}: {data.get('message', '')} "
                    f"(method={params.get('method')}, "
                    f"tag={params.get('tag', params.get('artist', ''))})"
                )
                raise HTTPException(status_code=502, detail=data.get("message", "Last.fm API error"))

            return data

        except HTTPException:
            raise

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_exc = e
            err_repr = repr(e) or type(e).__name__
            if attempt == 0:
                logger.warning(
                    f"[LFM Proxy] Transient error (attempt {attempt + 1}/2), retrying: {err_repr} "
                    f"method={params.get('method')}"
                )
                await asyncio.sleep(0.6)
            else:
                logger.error(
                    f"[LFM Proxy] Failed after 2 attempts: {err_repr} "
                    f"method={params.get('method')}"
                )

        except Exception as e:
            err_repr = repr(e) or type(e).__name__
            logger.error(f"[LFM Proxy] Unexpected error: {err_repr}")
            raise HTTPException(status_code=500, detail=f"Proxy error: {type(e).__name__}")

    raise HTTPException(
        status_code=502,
        detail=f"Last.fm unreachable after retries: {type(last_exc).__name__}",
    )

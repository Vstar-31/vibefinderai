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
import urllib.request
import urllib.parse
import json
import asyncio
import random
import re
import logging
import sys
import time

import vibe_engine
import semantic_search

load_dotenv()

logger = logging.getLogger("VibeFinderEngine")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler = logging.FileHandler("vibefinder_engine.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.handlers = [file_handler, stream_handler]

# ---------------------------------------------------------
db = Prisma()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Supabase/Prisma connection...")
    await db.connect()
    logger.info("Database connected successfully. Engine online.")
    yield
    logger.info("Engine shutting down. Disconnecting database...")
    await db.disconnect()

# ---------------------------------------------------------
app = FastAPI(title="VibeFinderAI API", description="Core backend for music discovery and NLP integrations", lifespan=lifespan)

def get_cors_origins():
    origins = []
    origins.extend(["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"])
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

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret-student-budget-key-dont-leak-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# ---------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =============================================================
# FIX 1 v6.0: MASSIVELY EXPANDED COMMON_WORDS_BLACKLIST
# Prevents single/double-word song titles that are common
# English words from hijacking abstract/visual/long prompts.
# Covers: prepositions, short verbs, adjectives, adverbs, nouns.
# =============================================================
COMMON_WORDS_BLACKLIST = {
    # --- Original v5.0 entries ---
    "alone", "beautiful", "water", "time", "burn", "lights", "independent",
    "deep", "passion", "holiday", "eve", "chicago", "slow", "love", "night",
    "good", "bad", "happy", "sad", "summer", "rain", "coffee", "drive",
    "party", "chill", "focus", "work", "sleep", "wake", "morning", "midnight",
    "fire", "magic", "dream", "smooth", "fragile", "resolute", "kiss",
    "paralyzed", "ready", "electric", "bright", "warm", "cold", "sweet",
    "bitter", "lost", "found", "free", "bound", "broken", "whole", "still",
    "moving", "running", "falling", "rising", "flying",
    # --- FIX 1: Prepositions & directional words (Lucky Daye "Over" class) ---
    "over", "under", "above", "below", "through", "around", "along",
    "across", "beside", "behind", "before", "after", "beyond", "between",
    "within", "without", "toward", "towards", "upon", "into", "onto",
    "out", "off", "away", "back", "up", "down",
    # --- FIX 1: Common short verbs (Pantera "Walk" / Young Thug "Best Friend" class) ---
    "stay", "go", "run", "walk", "fly", "fall", "rise", "leave", "come",
    "take", "give", "get", "put", "set", "let", "try", "see", "know",
    "think", "feel", "make", "want", "need", "keep", "hold", "help",
    "turn", "live", "wait", "stop", "start", "begin", "end", "play",
    "say", "tell", "ask", "show", "move", "change", "grow", "lead",
    "call", "catch", "cut", "hit", "lift", "pull", "push", "reach",
    "rest", "save", "send", "sit", "stand", "touch", "use", "win",
    # --- FIX 1: Common adjectives / adverbs ---
    "long", "short", "high", "low", "big", "small", "open", "close",
    "fast", "hard", "soft", "real", "true", "new", "old", "right",
    "wrong", "young", "wild", "always", "never", "maybe", "soon",
    "once", "again", "blue", "red", "gold", "silver", "black", "white",
    "green", "more", "here", "now", "far", "near", "only", "just",
    "even", "much", "last", "next", "same", "own", "every", "both",
    # --- FIX 1: Common nouns that dominate visual/abstract prompts ---
    "sun", "moon", "star", "sky", "sea", "land", "life", "soul", "mind",
    "heart", "world", "man", "woman", "girl", "boy", "day", "way", "air",
    "wind", "snow", "earth", "light", "dark", "home", "room", "door",
    "road", "tree", "river", "rain", "storm", "wave", "sand", "stone",
    "eye", "hand", "face", "name", "line", "side", "place", "space",
    "hour", "year", "voice", "word", "thing", "part", "end", "point",
    "body", "blood", "bone", "skin", "dust", "smoke", "ghost", "shadow",
    "mirror", "window", "floor", "wall", "crown", "cross", "church",
    "angel", "devil", "god", "king", "queen", "child", "friend", "enemy",
}

TRACK_BLOCKLIST = {
    # These get a score penalty so they don't dominate every playlist
    "trap queen|fetty wap",
    "circumambient|grimes",
    "slow|my bloody valentine",
    "slowdive|slowdive",
    "moanin|art blakey & the jazz messengers",
    "time moves slow|badbadnotgood",
    "4 am (adam k & soha mix)|kaskade",
    "finished symphony (deadmau5 remix)|hybrid",
    "silhouettes - original radio edit|avicii",
    "strobe (radio edit)|deadmau5",
    "brazil (2nd edit)|deadmau5",
    "to the hellfire|lorna shore",
    "you only live once|suicide silence",
    "pray for plagues|bring me the horizon",
    "country girl (shake it for me)|luke bryan",
    "take me home, country roads|john denver",
    "she's country|jason aldean",
}

# =============================================================
# FIX 3 v6.0: CULTURAL SUB-GENRE OVERRIDE TABLE
# When a cultural vibe wins (or is strong secondary), override
# the Last.fm genre tag to something specific instead of broad.
# Key = (dominant_vibe, secondary_vibe), Value = Last.fm tag.
# =============================================================
CULTURAL_SUBGENRE_OVERRIDE = {
    ("desi",        "punjabi"):       "bhangra",
    ("party",       "punjabi"):       "bhangra",
    ("hype",        "punjabi"):       "punjabi pop",
    ("punjabi",     "party"):         "bhangra",
    ("punjabi",     "hype"):          "punjabi pop",
    ("punjabi",     "desi"):          "bhangra",
    ("desi",        "haryanvi"):      "haryanvi",
    ("party",       "haryanvi"):      "haryanvi",
    ("haryanvi",    "party"):         "haryanvi",
    ("haryanvi",    "desi"):          "haryanvi",
    ("desi",        "bollywoodsad"):  "hindi ballad",
    ("heartbreak",  "bollywoodsad"):  "hindi ballad",
    ("bollywoodsad","heartbreak"):    "hindi ballad",
    ("bollywoodsad","desi"):          "hindi ballad",
    ("romantic",    "desi"):          "bollywood",
    ("desi",        "romantic"):      "bollywood",
    ("party",       "desi"):          "bollywood",
    ("hype",        "desi"):          "desi pop",
    ("desi",        "hype"):          "desi pop",
    ("desi",        "punjabisoft"):   "punjabi pop",
    ("punjabisoft", "desi"):          "punjabi pop",
    ("romantic",    "punjabi"):       "punjabi pop",
    ("punjabi",     "romantic"):      "punjabi pop",
    ("punjabisoft", "romantic"):      "punjabi pop",
    ("romantic",    "punjabisoft"):   "punjabi pop",
    ("desi",        "calm"):          "sufi",
    ("calm",        "desi"):          "sufi",
    ("desi",        "soulful"):       "ghazal",
    ("soulful",     "desi"):          "ghazal",
}

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
    artist_focus: int = 50
    nicheness: int = 50
    bpm_focus: int = 50
    track_limit: int = 5
    use_secondary_vibe: bool = False
    override_genre: str | None = None
    override_artist: str | None = None

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
    tracks: list[TrackInfo]

class FeedbackRequest(BaseModel):
    request_id: str
    track_title: str
    track_artist: str
    signal: int  # -1, 0, or 1
    position: int
    preview_seconds: int | None = None

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
def fetch_with_retry(url: str, label: str, timeout: int = 5, max_retries: int = 3) -> dict | None:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VibeFinderAI/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            wait = 2 ** attempt
            if attempt < max_retries - 1:
                logger.warning(f"Retry {attempt+1}/{max_retries} [{label}]: {e}. Backing off {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"[{label}] failed after {max_retries} attempts: {e}")
    return None

# ---------------------------------------------------------
def fetch_lastfm_tracks_sync(genre: str, limit: int = 200):
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    data = fetch_with_retry(url, label=f"Last.fm genre fetch for {genre}")
    if data:
        tracks = data.get("tracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

def fetch_lastfm_artist_tracks_sync(artist: str, limit: int = 200):
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={urllib.parse.quote(artist)}&api_key={api_key}&format=json&limit={limit}"
    data = fetch_with_retry(url, label=f"Last.fm artist fetch for {artist}")
    if data:
        tracks = data.get("toptracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

def fetch_lastfm_track_search_sync(query: str, limit: int = 100):
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={urllib.parse.quote(query)}&api_key={api_key}&format=json&limit={limit}"
    data = fetch_with_retry(url, label=f"Last.fm direct track search for {query}")
    if data:
        tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist")} for t in tracks]
    return []

def fetch_itunes_data_sync(title: str, artist: str):
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    data = fetch_with_retry(url, label=f"iTunes preview for {title} by {artist}", timeout=3, max_retries=2)
    if data and data.get("resultCount", 0) > 0:
        track = data["results"][0]
        return {"preview_url": track.get("previewUrl"), "cover_art": track.get("artworkUrl100")}
    return {"preview_url": None, "cover_art": None}

async def fetch_lastfm_tracks(genre: str, limit: int = 200):
    return await asyncio.to_thread(fetch_lastfm_tracks_sync, genre, limit)

async def fetch_lastfm_artist_tracks(artist: str, limit: int = 200):
    return await asyncio.to_thread(fetch_lastfm_artist_tracks_sync, artist, limit)

async def fetch_lastfm_track_search(query: str, limit: int = 100):
    return await asyncio.to_thread(fetch_lastfm_track_search_sync, query, limit)

async def fetch_itunes_preview(title: str, artist: str):
    return await asyncio.to_thread(fetch_itunes_data_sync, title, artist)

# ---------------------------------------------------------
def get_base_title(title: str) -> str:
    t = title.lower()
    t = t.split(" - ")[0]
    t = t.split("(")[0]
    t = t.split("feat")[0]
    t = t.split("ft.")[0]
    return t.strip()

JUNK_PATTERNS = re.compile(
    r"podcast|episode|news|npr|bbc|ted talk|morning edition"
    r"|kitchen nightmares|speedrunning|let me explain"
    r"|how to make|react?ion?|compilation|highlights"
    r"|sound effect|sound effects|ringtone|notification"
    r"|relaxing spa|nature music|ocean tones|spa music"
    r"|30 seconds|music box|text tone|christmas tree"
    r"|calming drone|holy drone|fire sticks|waterfowl"
    r"|bitcoin|crypto|nft|stock market|financial"
    r"|tutorial|lesson|course|lecture|audiobook"
    r"|trackmania|yu-gi-oh|master duel|nibiru",
    re.IGNORECASE
)

# ---------------------------------------------------------
def filter_and_score_tracks(tracks: list, request: "VibeRequest", vibe_data: dict, is_fallback: bool = False):
    prompt_lower = request.text.lower()
    detected_song = (vibe_data.get("detected_song") or "").lower()
    detected_artist = (vibe_data.get("detected_artist") or "").lower()
    target_genre_override = (vibe_data.get("target_genre_override") or vibe_data.get("dominant_vibe", "")).lower()
    bpm_range = vibe_data.get("bpm_range", "90-120")
    is_fast = any(x in bpm_range for x in ["120", "140", "160"])
    fast_markers = ["remix", "mix", "edit", "club", "fast", "speed", "drum"]
    slow_markers = ["acoustic", "slowed", "reverb", "chill", "lofi", "ambient", "slow"]

    scored_tracks = []
    for i, t in enumerate(tracks):
        title = t.get("title", "").lower()
        artist = t.get("artist", "").lower()
        score = 0.0

        if is_fallback:
            score += 50
        if detected_song and (detected_song in title or title in detected_song):
            score += 100
        if detected_artist and (detected_artist == artist or artist in prompt_lower):
            score += 40 * (request.artist_focus / 50.0)
        if target_genre_override in title or target_genre_override in artist:
            score += 30
        for kw in vibe_data.get("matched_keywords", []):
            if kw.lower() in title or kw.lower() in artist:
                score += 20
        markers = fast_markers if is_fast else slow_markers
        if any(m in title for m in markers):
            score += 30 * (request.bpm_focus / 50.0)
        if "remix" in title or "edit" in title or "instrumental" in title:
            score -= 15
        popularity_bias = (i / len(tracks)) * 30 if len(tracks) > 0 else 0
        nicheness_multiplier = (request.nicheness - 50) / 50.0
        score += popularity_bias * nicheness_multiplier
        global_popularity_bonus = max(0.0, (1.0 - i / max(len(tracks), 100))) * 10.0
        score += global_popularity_bonus
        track_ident_bl = f"{title}|{artist}"
        if track_ident_bl in TRACK_BLOCKLIST:
            score -= 40
        score += random.uniform(0, 1.5)
        scored_tracks.append((score, t))

    scored_tracks.sort(key=lambda x: x[0], reverse=True)

    final_selection = []
    skipped_for_diversity = []
    artist_counts = {}
    seen_base_titles = set()
    for _, t in scored_tracks:
        art = t.get("artist", "").lower()
        base_t = get_base_title(t.get("title", ""))
        track_ident = f"{art}|{base_t}"
        if track_ident in seen_base_titles:
            continue
        seen_base_titles.add(track_ident)
        if not request.override_artist and request.artist_focus < 80:
            if artist_counts.get(art, 0) >= 2:
                skipped_for_diversity.append(t)
                continue
        final_selection.append(t)
        artist_counts[art] = artist_counts.get(art, 0) + 1
        if len(final_selection) >= request.track_limit:
            break

    if len(final_selection) < request.track_limit:
        for t in skipped_for_diversity:
            final_selection.append(t)
            if len(final_selection) >= request.track_limit:
                break

    return final_selection

# ---------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "VibeFinderAI API is operational."}

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    existing_user = await db.user.find_first(where={"OR": [{"email": user.email}, {"username": user.username}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Identity already exists")
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
    except:
        raise HTTPException(status_code=401)

# =============================================================
# NEGATION TOKENS (entity scanner)
# =============================================================
NEGATION_TOKENS = ["not", "no", "don't", "dont", "nothing", "avoid", "except", "without", "skip", "never"]

def is_negated_entity(entity: str, text: str) -> bool:
    pattern = rf"({'|'.join(re.escape(n) for n in NEGATION_TOKENS)})\s+{re.escape(entity)}"
    return bool(re.search(pattern, text, re.IGNORECASE))

# =============================================================
# MAIN VIBE ANALYSIS ENDPOINT
# =============================================================
@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    """
    Refined analysis route with zero-results fallback logic and telemetry.
    v6.0: Expanded blacklist, cultural vibe trump card, cultural sub-genre override.
    """
    logger.info(f"--- NEW REQUEST: Analyzing Vibe ---")
    logger.info(f"Prompt: {request.text!r} | Limit: {request.track_limit}")

    # Decode user
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 1. NLP Core Analysis
    vibe_data = vibe_engine.analyze_vibe_algorithm(
        text=request.text,
        artist_focus=request.artist_focus,
        genre_focus=50,
        bpm_focus=request.bpm_focus
    )
    prompt_lower = request.text.lower()
    detected_artist = request.override_artist
    detected_song = None

    # 2. Entity Scanner — artist + song lock
    prompt_word_count = len(prompt_lower.split())
    if not detected_artist:
        try:
            db_artists = await db.artistDirectory.find_many()
            for a in db_artists:
                artist_name = a.name.lower()
                artist_pattern = rf"{re.escape(artist_name)}"
                if re.search(artist_pattern, prompt_lower):
                    if is_negated_entity(artist_name, prompt_lower):
                        logger.info(f"Entity Scanner: Negation detected before artist {a.name!r}, lock discarded.")
                        continue
                    detected_artist = a.name
                    logger.info(f"Entity Scanner: Locked Artist → {detected_artist!r}")
                    if a.songs:
                        song_list = [s.strip().lower() for s in a.songs.split(",")]
                        for s in song_list:
                            if s and re.search(rf"{re.escape(s)}", prompt_lower):
                                if is_negated_entity(s, prompt_lower):
                                    logger.info(f"Entity Scanner: Negation before song {s!r}, lock discarded.")
                                    continue
                                detected_song = s
                                logger.info(f"Entity Scanner: Locked Song → {detected_song!r}")
                                break
                    break
                elif a.songs:
                    # Standalone song lock — artist NOT in prompt
                    song_list = [s.strip().lower() for s in a.songs.split(",")]
                    for s in song_list:
                        if not s:
                            continue

                        # ==============================================
                        # FIX 1 v6.0: TIGHTENED STANDALONE SONG LOCK
                        # Guard 1: Must be ≥3 chars and not blacklisted
                        # Guard 2: Single-word titles NEVER lock without artist
                        # Guard 3: Long prompts (>6 words) skip standalone lock
                        # Guard 4: Drop lock if NLP confidence is strong (>0.30)
                        #          — vibe signal is clear, don't let a random
                        #            word derail it.
                        # ==============================================
                        if len(s) < 3:
                            continue
                        if s in COMMON_WORDS_BLACKLIST:
                            logger.info(f"Entity Scanner: Song {s!r} is in COMMON_WORDS_BLACKLIST, skipping.")
                            continue
                        if " " not in s and artist_name not in prompt_lower:
                            logger.info(f"Entity Scanner: Single-word song {s!r} blocked (artist not in prompt).")
                            continue
                        if prompt_word_count > 6:
                            logger.info(f"Entity Scanner: Long prompt ({prompt_word_count} words), skipping standalone lock for {s!r}.")
                            continue
                        if vibe_data.get("confidence", 0) > 0.30:
                            logger.info(f"Entity Scanner: Dropping standalone song lock {s!r} — NLP confidence {vibe_data.get('confidence'):.2f} is strong.")
                            continue
                        if not re.search(rf"{re.escape(s)}", prompt_lower):
                            continue
                        if is_negated_entity(s, prompt_lower):
                            logger.info(f"Entity Scanner: Negation before standalone song {s!r}, discarded.")
                            continue
                        detected_artist = a.name
                        detected_song = s
                        logger.info(f"Entity Scanner: Locked Song independently → {detected_song!r} by {detected_artist!r}")
                        break
                if detected_artist:
                    break
        except Exception as e:
            logger.error(f"Entity Scan Database Error: {e}")

    vibe_data["detected_artist"] = detected_artist
    vibe_data["detected_song"] = detected_song

    # Entity lock active but NLP confidence near-zero → force artist discography
    if detected_artist and vibe_data.get("confidence", 0) < 0.10:
        logger.info(f"Entity lock active but NLP confidence near-zero. Forcing artist discography fetch for {detected_artist!r}.")
        vibe_data["dominant_vibe"] = "artist-driven"

    # 3. Fallback Protocol (low confidence, no entity lock, no override)
    is_fallback = False
    used_semantic = False
    if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
        is_fallback = True
        logger.warning(f"Engine Confidence Critical: {vibe_data.get('confidence'):.2f} < 0.25. Triggering Fallback Protocol!")
        vibe_data["dominant_vibe"] = "Direct Search"
        vibe_data["secondary_vibe"] = "Fallback Mode"
        raw_pool = await fetch_lastfm_track_search(request.text, limit=100)
        logger.info(f"Fallback Search returned {len(raw_pool)} tracks.")

    # 4. SMART POOL FETCH
    else:
        # ==============================================
        # FIX 3 v6.0: CULTURAL SUB-GENRE OVERRIDE
        # Resolve a specific Last.fm tag when cultural
        # vibes are in play, so "bhangra night" actually
        # hits the bhangra pool instead of generic desi.
        # ==============================================
        _dom = vibe_data.get("dominant_vibe", "").lower()
        _sec = (vibe_data.get("secondary_vibe") or "").lower()
        _cultural_override = (
            CULTURAL_SUBGENRE_OVERRIDE.get((_dom, _sec)) or
            CULTURAL_SUBGENRE_OVERRIDE.get((_sec, _dom))
        )

        if _cultural_override and not request.override_genre:
            target_genre = _cultural_override
            logger.info(f"Cultural genre override: dom={_dom!r} sec={_sec!r} → targeting {target_genre!r}")
        elif request.override_genre:
            target_genre = request.override_genre
            logger.info(f"Pro Mode OVERRIDE applied. Target Genre forced to {target_genre!r}")
        elif request.use_secondary_vibe and vibe_data.get("secondary_vibe"):
            sec_vibe_name = vibe_data["secondary_vibe"]
            mapped_genres = vibe_engine.VIBE_MAP.get(sec_vibe_name, {}).get("genres", [sec_vibe_name])
            target_genre = mapped_genres[0]
            logger.info(f"PIVOT ACTIVE: Switched to Secondary Vibe → {target_genre!r}")
        elif vibe_data.get("dominant_vibe") == "artist-driven":
            target_genre = None
        else:
            target_genre = vibe_data.get("genres", ["electronic"])[0]
            logger.info(f"Standard AI Resolution: Dominant Genre → {target_genre!r}")

        vibe_data["target_genre_override"] = target_genre

        if vibe_data.get("dominant_vibe") == "artist-driven" or request.override_artist:
            artist_target = request.override_artist or detected_artist
            logger.info(f"Fetching direct discography for artist: {artist_target!r}")
            raw_pool = await fetch_lastfm_artist_tracks(artist_target, limit=200)
        else:
            genre_pool = await fetch_lastfm_tracks(target_genre, limit=200)
            artist_pool = []
            if detected_artist and request.artist_focus > 25:
                logger.info(f"Injecting discography blend for detected artist: {detected_artist!r}")
                artist_pool = await fetch_lastfm_artist_tracks(detected_artist, limit=50)
            seen = set()
            raw_pool = []
            for t in genre_pool + artist_pool:
                ident = f"{t['title'].lower()}|{t['artist'].lower()}"
                if ident not in seen:
                    seen.add(ident)
                    raw_pool.append(t)
            logger.info(f"Merged deduplicated pool size: {len(raw_pool)} tracks.")

    # 4b. Semantic reranking
    if semantic_search.semantic_ready and raw_pool:
        logger.info(f"Semantic Reranking: {len(raw_pool)} fallback tracks by prompt similarity...")
        raw_pool = await asyncio.get_event_loop().run_in_executor(
            None, lambda: semantic_search.rank_tracks_by_prompt(request.text, raw_pool)
        )
        used_semantic = True
        logger.info("Semantic Reranking complete.")

    # 5. Junk filter
    raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(f"{t.get('title', '')} {t.get('artist', '')}")]
    raw_pool = [t for t in raw_pool if len(t.get("title", "")) < 120]
    logger.info(f"After junk filter: {len(raw_pool)} tracks remain.")

    if not raw_pool:
        logger.warning("Zero Results Triggered. Firing HTTP 404 to Frontend.")
        raise HTTPException(
            status_code=404,
            detail="Signal lost: Zero results found. Please rephrase your query. Note: Our acoustic engine currently processes English descriptors, specific genres, and known artists best."
        )

    # 6. Mathematical Scoring
    logger.info("Executing mathematical sorting and diversity guards...")
    best_tracks = filter_and_score_tracks(raw_pool, request, vibe_data, is_fallback=is_fallback)

    # 6b. Semantic blending
    if used_semantic and best_tracks and any("semantic_score" in t for t in best_tracks):
        logger.info("Semantic Blending: semantic + heuristic scores for final ranking...")
        best_tracks = semantic_search.blend_semantic_scores(best_tracks, semantic_weight=0.35)

    best_tracks = best_tracks[:request.track_limit]

    if not best_tracks:
        logger.warning("Scoring eliminated all tracks. Firing HTTP 404.")
        raise HTTPException(
            status_code=404,
            detail="Signal lost: No tracks passed the strict filters. Try lowering Nicheness or adjusting your prompt."
        )

    # 7. Parallel iTunes preview scraping
    logger.info(f"Scraping Apple Music previews concurrently for top {len(best_tracks)} tracks...")
    itunes_tasks = [fetch_itunes_preview(t["title"], t["artist"]) for t in best_tracks]
    previews = await asyncio.gather(*itunes_tasks)

    # 8. Payload Assembly
    final_tracks = []
    for i, t in enumerate(best_tracks):
        t_title = t["title"]
        t_artist = t["artist"]
        q = urllib.parse.quote(f"{t_title} {t_artist}")
        final_tracks.append({
            "title": t_title,
            "artist": t_artist,
            "spotify_uri": f"spotify:search:{q}",
            "apple_uri": f"music:search?term={q}",
            "preview_url": previews[i]["preview_url"],
            "cover_art": previews[i]["cover_art"],
        })

    # 9. Log VibeRequest to DB (non-fatal)
    vibe_request_id = None
    try:
        vibe_request_row = await db.vibeRequest.create(data={
            "userId": user_id,
            "promptText": request.text,
            "dominantVibe": vibe_data.get("dominant_vibe", "neutral"),
            "secondaryVibe": vibe_data.get("secondary_vibe"),
            "confidence": float(vibe_data.get("confidence", 0.0)),
            "bpmRange": str(vibe_data.get("bpm_range", "")),
            "genres": json.dumps(vibe_data.get("genres", [])),
            "matchedKeywords": json.dumps(vibe_data.get("matched_keywords", [])),
            "detectedArtist": vibe_data.get("detected_artist"),
            "detectedSong": vibe_data.get("detected_song"),
            "artistFocus": request.artist_focus,
            "nicheness": request.nicheness,
            "bpmFocus": request.bpm_focus,
            "trackLimit": request.track_limit,
            "usedFallback": is_fallback,
            "usedSemantic": used_semantic,
            "returnedTracks": json.dumps([{"title": t["title"], "artist": t["artist"]} for t in final_tracks]),
        })
        vibe_request_id = vibe_request_row.id
        logger.info(f"VibeRequest logged to DB: {vibe_request_id}")
    except Exception as e:
        logger.error(f"Failed to log VibeRequest to DB: {e}")

    vibe_data["tracks"] = final_tracks
    vibe_data["request_id"] = vibe_request_id or "unlogged"
    logger.info(f"--- SUCCESS: Returning {len(final_tracks)} tracks to client ---")
    return vibe_data


@app.post("/api/feedback", status_code=201)
async def submit_feedback(feedback: FeedbackRequest, token: str = Depends(oauth2_scheme)):
    """Record a user's thumbs up/down on a specific track."""
    if feedback.signal not in [-1, 0, 1]:
        raise HTTPException(status_code=422, detail="signal must be -1, 0, or 1")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        signal_label = {1: "LIKE", 0: "PLAY", -1: "SKIP"}.get(feedback.signal, "?")
        row = await db.trackFeedback.create(data={
            "vibeRequestId": feedback.request_id if feedback.request_id != "unlogged" else None,
            "userId": user_id,
            "trackTitle": feedback.track_title,
            "trackArtist": feedback.track_artist,
            "signal": feedback.signal,
            "position": feedback.position,
            "previewSeconds": feedback.preview_seconds,
        })
        logger.info(
            f"Feedback logged: {signal_label} {feedback.track_title!r} by {feedback.track_artist!r} "
            f"[pos={feedback.position}, user={user_id[:8]}..., req={feedback.request_id[:8]}...]"
        )
        return {"status": "ok", "id": row.id}
    except Exception as e:
        logger.error(f"Feedback write error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")

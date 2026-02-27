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

# Import our modularized vibe engine
import vibe_engine

# Import semantic fallback ranker (gracefully degrades if model not installed)
import semantic_search

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI. Connects to the Prisma DB 
    on startup and cleanly disconnects on shutdown.
    """
    logger.info("Initializing Supabase (Prisma) connection...")
    await db.connect()
    logger.info("Database connected successfully. Engine online.")
    yield
    logger.info("Engine shutting down. Disconnecting database...")
    await db.disconnect()

# Initialize core app with lifespan hook
app = FastAPI(
    title="VibeFinderAI API", 
    description="Core backend for music discovery and NLP integrations",
    lifespan=lifespan
)

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

COMMON_WORDS_BLACKLIST = {
        "alone", "beautiful", "water", "time", "burn", "lights", 
        "independent", "deep", "passion", "holiday", "eve", "chicago", 
        "slow", "love", "night", "good", "bad", "happy", "sad", "summer", 
        "rain", "coffee", "drive", "party", "chill", "focus", "work", 
        "sleep", "wake", "morning", "midnight", "fire", "magic", "dream"
    }

# v1.2 — Chronic result spam protection.
# Tracks that appeared in 10%+ of all QA results regardless of prompt.
# These get a score penalty in the scoring engine so they don't dominate every playlist.
TRACK_BLOCKLIST: set[str] = {
    "trap queen|fetty wap",
    "circumambient|grimes",        # appears in almost every dark result
    "slow|my bloody valentine",    # leads every dreamy result
    "slowdive|slowdive",           # same pool monopoly
    "moanin'|art blakey & the jazz messengers",  # leads every soulful result
    "time moves slow|badbadnotgood",
}
# ---------------------------------------------------------
# Pydantic Models
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
# Network Retry Helper (v1.2 — Fix #4: Network Resilience)
# ---------------------------------------------------------
def _fetch_with_retry(url: str, label: str, timeout: int = 5, max_retries: int = 3) -> dict | None:
    """
    GETs a URL and returns parsed JSON, with exponential backoff on failure.
    Delays between retries: 1s → 2s → 4s.
    Returns None after all retries are exhausted.
    """
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            wait = 2 ** attempt  # 1s, 2s, 4s
            if attempt < max_retries - 1:
                logger.warning(f"[Retry {attempt + 1}/{max_retries}] {label} — {e}. Backing off {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"{label} failed after {max_retries} attempts: {e}")
    return None


# ---------------------------------------------------------
# Free Music Fetchers (Last.fm + iTunes)
# ---------------------------------------------------------
def fetch_lastfm_tracks_sync(genre: str, limit: int = 200):
    """Hits the free Last.fm API to pull trending tracks."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    data = _fetch_with_retry(url, label=f"Last.fm genre fetch for '{genre}'")
    if data:
        tracks = data.get("tracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

def fetch_lastfm_artist_tracks_sync(artist: str, limit: int = 200):
    """Hits the free Last.fm API to pull a SPECIFIC artist's discography."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={urllib.parse.quote(artist)}&api_key={api_key}&format=json&limit={limit}"
    data = _fetch_with_retry(url, label=f"Last.fm artist fetch for '{artist}'")
    if data:
        tracks = data.get("toptracks", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    return []

def fetch_lastfm_track_search_sync(query: str, limit: int = 100):
    """FALLBACK: Directly searches Last.fm for literal track names if AI confidence is shot."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={urllib.parse.quote(query)}&api_key={api_key}&format=json&limit={limit}"
    data = _fetch_with_retry(url, label=f"Last.fm direct track search for '{query}'")
    if data:
        tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
        return [{"title": t.get("name"), "artist": t.get("artist")} for t in tracks]
    return []

def fetch_itunes_data_sync(title: str, artist: str):
    """Silently hits the free iTunes API to grab the .m4a preview & cover art."""
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    # iTunes is low-stakes; 1 retry is enough, no need for full backoff
    data = _fetch_with_retry(url, label=f"iTunes preview for '{title}' by '{artist}'", timeout=3, max_retries=2)
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
    Refined scoring engine. Prioritizes exact matches, strips Remixes, 
    and perfectly enforces the user's Track Limit.
    """
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
        
        # In fallback mode, the tracks are already exact matches, give them a baseline boost
        if is_fallback:
            score += 50
        
        # 1. EXACT SONG MATCH
        if detected_song and (detected_song in title or title in detected_song):
            score += 100 
            
        # 2. ARTIST MATCH 
        if (detected_artist and detected_artist == artist) or artist in prompt_lower:
            score += 40 * (request.artist_focus / 50.0)
            
        # 3. VIBE / GENRE MATCH
        if target_genre_override in title or target_genre_override in artist:
            score += 30 
            
        for kw in vibe_data.get("matched_keywords", []):
            if kw.lower() in title or kw.lower() in artist:
                score += 20 
                
        # 4. BPM MATCH (Marker based)
        markers = fast_markers if is_fast else slow_markers
        if any(m in title for m in markers):
            score += 30 * (request.bpm_focus / 50.0)
            
        # REMIX EXCLUSION
        if "remix" in title or "edit" in title or "instrumental" in title:
            score -= 15
            
        # 5. PURE NICHENESS KNOB (0 to 100)
        popularity_bias = (i / len(tracks)) * 30 if len(tracks) > 0 else 0
        nicheness_multiplier = (request.nicheness - 50) / 50.0
        score += (popularity_bias * nicheness_multiplier)
        
        # v1.2 Fix #2 — English / Global Popularity Filter
        # Last.fm returns results ordered by listener count, so lower index = higher global reach.
        # We apply a mild "global popularity" bonus that decays over the first 100 results.
        # This counter-balances regional/non-English charts flooding the top without explicit request.
        global_popularity_bonus = max(0.0, (1.0 - (i / max(len(tracks), 100))) * 10.0)
        score += global_popularity_bonus
        
        # v1.2 Fix: Chronic spam penalty — tracks that appear in every request
        # get a significant downrank so the pool naturally diversifies.
        track_ident_bl = f"{title}|{artist}"
        if track_ident_bl in TRACK_BLOCKLIST:
            score -= 40
            
        score += random.uniform(0, 1.5)
        scored_tracks.append((score, t))
        
    scored_tracks.sort(key=lambda x: x[0], reverse=True)
    
    # 6. DIVERSITY GUARD & STRICT DEDUPLICATION
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
        
        # Anti-Monopoly Guard
        if not request.override_artist and request.artist_focus < 80:
            if artist_counts.get(art, 0) >= 2:
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
    
    logger.info(f"--- NEW REQUEST: Analyzing Vibe ---")
    logger.info(f"Prompt: '{request.text}' | Limit: {request.track_limit}")
    
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
    
    # 2. DEEP ENTITY SCAN (Anti-Hijack Guard Added)
    # Prevents common adjectives/nouns from triggering a standalone song lock
    COMMON_WORDS_BLACKLIST = {
        "alone", "beautiful", "water", "time", "burn", "lights", 
        "independent", "deep", "passion", "holiday", "eve", "chicago", 
        "slow", "love", "night", "good", "bad", "happy", "sad", "summer", 
        "rain", "coffee", "drive", "party", "chill", "focus", "work", 
        "sleep", "wake", "morning", "midnight", "fire", "magic", "dream"
    }

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
                artist_name = a.name.lower()
                artist_pattern = rf'\b{re.escape(artist_name)}\b'
                
                if re.search(artist_pattern, prompt_lower):
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
    # v1.2 FIX: If we have an entity lock but vibe scored neutral/0%, that means the
    # NLP had no signal beyond the entity name. Rather than serving "Lo-Fi, Ambient Pop,
    # Electronic" (the neutral fallback genres), we fetch the artist's discography
    # directly and let the scoring engine do the rest. Flag the vibe as entity-driven.
    if detected_artist and vibe_data.get("confidence", 0) < 0.10:
        logger.info(f"Entity lock active but NLP confidence near-zero. Forcing artist discography fetch for '{detected_artist}'.")
        vibe_data["dominant_vibe"] = "artist_driven"
        # Use the artist fetch path below
        target_genre = None
    elif request.override_genre:
        target_genre = request.override_genre
        logger.info(f"Pro Mode OVERRIDE applied. Target Genre forced to: {target_genre}")
    elif request.use_secondary_vibe and vibe_data.get("secondary_vibe"):
        sec_vibe_name = vibe_data["secondary_vibe"]
        mapped_genres = vibe_engine.VIBE_MAP.get(sec_vibe_name, {}).get("genres", [sec_vibe_name])
        target_genre = mapped_genres[0]
        logger.info(f"PIVOT ACTIVE: Switched to Secondary Vibe -> {target_genre}")
    else:
        target_genre = vibe_data.get("genres", ["electronic"])[0]
        logger.info(f"Standard AI Resolution: Dominant Genre -> {target_genre}")
        
    vibe_data["target_genre_override"] = target_genre

    # 4. SMART POOL FETCH & GRACEFUL FALLBACK
    is_fallback = False
    used_semantic = False
    
    if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
        is_fallback = True
        logger.warning(f"Engine Confidence Critical ({vibe_data.get('confidence')} < 0.25). Triggering Fallback Protocol!")
        vibe_data["dominant_vibe"] = "Direct Search" 
        vibe_data["secondary_vibe"] = "Fallback Mode"
        raw_pool = await fetch_lastfm_track_search(request.text, limit=100)
        logger.info(f"Fallback Search returned {len(raw_pool)} tracks.")
        
        # v1.2 FIX: Filter out junk fallback results (podcasts, news, YouTube videos)
        JUNK_PATTERNS = re.compile(
            r'\b(podcast|episode|news|npr|bbc|ted talk|morning edition|'
            r'kitchen nightmares|speedrunning|let me explain|'
            r'how to make|react(?:ion)?|compilation|highlights)\b',
            re.IGNORECASE
        )
        raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(f"{t.get('title','')} {t.get('artist','')}")]
        logger.info(f"After junk filter: {len(raw_pool)} tracks remain.")

        # v1.3 NEW: Semantic reranking — when Last.fm keyword search gives us a
        # noisy pool, run sentence-transformer similarity to promote the tracks
        # whose identity most closely matches the user's prompt.
        if semantic_search.semantic_ready() and raw_pool:
            logger.info(f"[Semantic] Reranking {len(raw_pool)} fallback tracks by prompt similarity...")
            raw_pool = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: semantic_search.rank_tracks_by_prompt(request.text, raw_pool)
            )
            used_semantic = True
            logger.info(f"[Semantic] Reranking complete.")
        
    elif request.override_artist or vibe_data.get("dominant_vibe") == "artist_driven":
        artist_target = request.override_artist or detected_artist
        logger.info(f"Fetching direct discography for artist: {artist_target}")
        raw_pool = await fetch_lastfm_artist_tracks(artist=artist_target, limit=200)
    else:
        logger.info(f"Fetching primary genre pool for: {target_genre}")
        genre_pool = await fetch_lastfm_tracks(genre=target_genre, limit=200)
        artist_pool = []
        if detected_artist and request.artist_focus > 25:
            logger.info(f"Injecting discography blend for detected artist: {detected_artist}")
            artist_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=50)
            
        merged_pool = genre_pool + artist_pool
        seen = set()
        raw_pool = []
        for t in merged_pool:
            ident = f"{t['title'].lower()}|{t['artist'].lower()}"
            if ident not in seen:
                seen.add(ident)
                raw_pool.append(t)
        logger.info(f"Merged deduplicated pool size: {len(raw_pool)} tracks.")
                
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
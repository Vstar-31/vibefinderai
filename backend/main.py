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

# Import our modularized vibe engine
import vibe_engine

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"], 
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
# Free Music Fetchers (Last.fm + iTunes)
# ---------------------------------------------------------
def fetch_lastfm_tracks_sync(genre: str, limit: int = 200):
    """Hits the free Last.fm API to pull trending tracks."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tracks = data.get("tracks", {}).get("track", [])
            return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    except Exception as e:
        logger.error(f"Last.fm genre fetch failed for '{genre}': {e}")
        return []

def fetch_lastfm_artist_tracks_sync(artist: str, limit: int = 200):
    """Hits the free Last.fm API to pull a SPECIFIC artist's discography."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.gettoptracks&artist={urllib.parse.quote(artist)}&api_key={api_key}&format=json&limit={limit}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tracks = data.get("toptracks", {}).get("track", [])
            return [{"title": t.get("name"), "artist": t.get("artist", {}).get("name")} for t in tracks]
    except Exception as e:
        logger.error(f"Last.fm artist fetch failed for '{artist}': {e}")
        return []

def fetch_lastfm_track_search_sync(query: str, limit: int = 100):
    """FALLBACK: Directly searches Last.fm for literal track names if AI confidence is shot."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={urllib.parse.quote(query)}&api_key={api_key}&format=json&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
            return [{"title": t.get("name"), "artist": t.get("artist")} for t in tracks]
    except Exception as e:
        logger.error(f"Last.fm direct track search failed for '{query}': {e}")
        return []

def fetch_itunes_data_sync(title: str, artist: str):
    """Silently hits the free iTunes API to grab the .m4a preview & cover art."""
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get("resultCount", 0) > 0:
                track = data["results"][0]
                return {
                    "preview_url": track.get("previewUrl"),
                    "cover_art": track.get("artworkUrl100")
                }
    except Exception as e: 
        logger.warning(f"iTunes API preview fetch failed for '{title}' by '{artist}': {e}")
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
    
    if not detected_artist:
        try:
            db_artists = await db.artistdirectory.find_many()
            for a in db_artists:
                artist_name = a.name.lower()
                artist_pattern = rf'\b{re.escape(artist_name)}\b'
                
                if re.search(artist_pattern, prompt_lower):
                    detected_artist = a.name
                    logger.info(f"Entity Scanner Locked Artist: {detected_artist}")
                    if a.songs:
                        song_list = [s.strip().lower() for s in a.songs.split(",")]
                        for s in song_list:
                            if s and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                                detected_song = s
                                logger.info(f"Entity Scanner Locked Song: {detected_song}")
                                break
                    break
                elif a.songs:
                    song_list = [s.strip().lower() for s in a.songs.split(",")]
                    for s in song_list:
                        # NEW GUARD: Only lock if the song is >3 chars AND not in the blacklist!
                        if len(s) > 3 and s not in COMMON_WORDS_BLACKLIST and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                            detected_artist = a.name
                            detected_song = s
                            logger.info(f"Entity Scanner Locked Song independently: {detected_song} by {detected_artist}")
                            break
                    if detected_artist: break
        except Exception as e: 
            logger.error(f"Entity Scan Database Error: {e}")
            
    vibe_data["detected_artist"] = detected_artist
    vibe_data["detected_song"] = detected_song

    # 3. DYNAMIC TARGET GENRE RESOLUTION
    if request.override_genre:
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
    
    if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
        is_fallback = True
        logger.warning(f"Engine Confidence Critical ({vibe_data.get('confidence')} < 0.25). Triggering Fallback Protocol!")
        vibe_data["dominant_vibe"] = "Direct Search" 
        vibe_data["secondary_vibe"] = "Fallback Mode"
        raw_pool = await fetch_lastfm_track_search(request.text, limit=100)
        logger.info(f"Fallback Search returned {len(raw_pool)} tracks.")
        
    elif request.override_artist:
        logger.info(f"Fetching direct discography for overridden artist: {request.override_artist}")
        raw_pool = await fetch_lastfm_artist_tracks(artist=request.override_artist, limit=200)
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
        
    vibe_data["tracks"] = final_tracks
    logger.info(f"--- SUCCESS: Returning {len(final_tracks)} tracks to client ---")
    return vibe_data
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

# Import our modularized vibe engine
import vibe_engine

# Load environment variables
load_dotenv()

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
    await db.connect()
    yield
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
    genre_focus: int = 50
    bpm_focus: int = 50

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
# The 100% Free Music Fetchers (Last.fm + iTunes)
# ---------------------------------------------------------
def fetch_lastfm_tracks_sync(genre: str, limit: int = 50):
    """Hits the free Last.fm API to pull trending tracks."""
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    
    fallback_tracks = [
        {"title": "Nightcrawler", "artist": "Travis Scott"},
        {"title": "Resonance", "artist": "HOME"},
        {"title": "Goth", "artist": "Sidewalks and Skeletons"},
        {"title": "After Hours", "artist": "The Weeknd"},
        {"title": "Genesis", "artist": "Grimes"}
    ]

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeFinderAI/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            tracks = data.get("tracks", {}).get("track", [])
            
            if not tracks:
                return fallback_tracks

            result = []
            for t in tracks:
                result.append({
                    "title": t.get("name"), 
                    "artist": t.get("artist", {}).get("name")
                })
            return result
    except Exception as e:
        print(f"Last.fm fetch failed ({e}). Returning fallback offline tracks.")
        return fallback_tracks

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
        print(f"iTunes API failed for {title}: {e}")
    
    return {"preview_url": None, "cover_art": None}

async def fetch_lastfm_tracks(genre: str, limit: int = 50):
    return await asyncio.to_thread(fetch_lastfm_tracks_sync, genre, limit)

async def fetch_itunes_preview(title: str, artist: str):
    return await asyncio.to_thread(fetch_itunes_data_sync, title, artist)

# ---------------------------------------------------------
# The Mathematical AI (Knob Scoring Engine)
# ---------------------------------------------------------
def filter_and_score_tracks(tracks: list, request: VibeRequest, vibe_data: dict, limit: int = 5):
    """
    Takes a massive pool of 50 tracks and physically scores them based on the 
    user's raw text and the precise values of the UI Knobs.
    """
    prompt_lower = request.text.lower()
    keywords = [k.lower() for k in vibe_data.get("matched_keywords", [])]
    dominant = vibe_data.get("dominant_vibe", "").lower()
    bpm_range = vibe_data.get("bpm_range", "90-120")
    
    # Identify acoustic target markers based on the NLP engine's BPM reading
    is_fast = "120" in bpm_range or "140" in bpm_range or "160" in bpm_range
    fast_markers = ["remix", "mix", "edit", "vip", "club", "bootleg", "mashup", "fast", "speed"]
    slow_markers = ["acoustic", "slowed", "reverb", "chill", "lofi", "unplugged", "ambient", "slow"]
    
    scored_tracks = []
    for i, t in enumerate(tracks):
        title = t.get("title", "").lower()
        artist = t.get("artist", "").lower()
        score = 0.0
        
        # 1. ARTIST FOCUS MATCH (Did they type the artist's name in the prompt?)
        if artist in prompt_lower or title in prompt_lower:
            # Massive boost heavily multiplied by the Artist Knob
            score += 50 * (request.artist_focus / 50.0)
            
        # 2. GENRE / VIBE MATCH (Do the track names match the vibe keywords?)
        if dominant in title or dominant in artist:
            score += 30 * (request.genre_focus / 50.0)
        for kw in keywords:
            if kw in title or kw in artist:
                score += 20 * (request.genre_focus / 50.0)
                
        # 3. BPM FOCUS MATCH (Simulate tempo via title acoustic markers)
        if request.bpm_focus > 50:
            markers = fast_markers if is_fast else slow_markers
            if any(m in title for m in markers):
                score += 40 * (request.bpm_focus / 50.0)
        
        # 4. MAINSTREAM VS NICHE SLIDER
        # High knobs = user wants deep, specific cuts. Low knobs = user wants mainstream top 10 hits.
        popularity_penalty = (i / len(tracks)) * 20 if len(tracks) > 0 else 0
        knob_avg = (request.artist_focus + request.genre_focus + request.bpm_focus) / 3.0
        
        if knob_avg > 60:
            # Reward tracks deeper in the 50-track list
            score += popularity_penalty 
        else:
            # Reward the top mainstream tracks at the top of the list
            score -= popularity_penalty
            
        # Inject microscopic random jitter so identical 0.0 scores don't yield the exact same tracks
        score += random.uniform(0, 2)
        
        scored_tracks.append((score, t))
        
    # Sort by the final mathematical score, descending!
    scored_tracks.sort(key=lambda x: x[0], reverse=True)
    
    # Slice the absolute best 5
    return [t[1] for t in scored_tracks[:limit]]


# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "VibeFinderAI API is operational."}

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    existing_user = await db.user.find_first(
        where={
            "OR": [
                {"email": user.email},
                {"username": user.username}
            ]
        }
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or username already registered")
    
    hashed_pwd = get_password_hash(user.password)
    new_user = await db.user.create(
        data={"email": user.email, "username": user.username, "hashedPassword": hashed_pwd}
    )
    return {"message": "User registered successfully", "user_id": new_user.id}

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.user.find_unique(where={"username": form_data.username})
    
    if not user or not user.hashedPassword or not verify_password(form_data.password, user.hashedPassword):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.id}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"user_id": user.id, "username": user.username, "email": user.email, "status": "authenticated"}

@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    """Routes the analyze request to NLP and pulls free music data concurrently."""
    
    # 1. NLP Engine - The knobs adjust the math inside this function!
    vibe_data = vibe_engine.analyze_vibe_algorithm(
        text=request.text,
        artist_focus=request.artist_focus,
        genre_focus=request.genre_focus,
        bpm_focus=request.bpm_focus
    )
    
    genres = vibe_data.get("genres", [])
    target_genre = genres[0] if genres else "electronic"
    
    # 2. Grab a massive pool of 50 raw tracks from Last.fm
    raw_pool = await fetch_lastfm_tracks(genre=target_genre, limit=50)
    
    # 3. Mathematically score and filter the 50 tracks down to the best 5 using the UI knobs!
    best_tracks = filter_and_score_tracks(raw_pool, request, vibe_data, limit=5)
    
    # 4. Concurrently fetch the Apple Music 30-sec previews for the WINNING tracks
    itunes_tasks = [fetch_itunes_preview(t["title"], t["artist"]) for t in best_tracks]
    itunes_results = await asyncio.gather(*itunes_tasks)
    
    # 5. Assemble the final track list with Both Options (Deep Links + iTunes Player)
    final_tracks = []
    for i, t in enumerate(best_tracks):
        search_query = urllib.parse.quote(f"{t['title']} {t['artist']}")
        final_tracks.append({
            "title": t["title"],
            "artist": t["artist"],
            "spotify_uri": f"spotify:search:{search_query}",
            "apple_uri": f"music://search?term={search_query}",
            "preview_url": itunes_results[i]["preview_url"],
            "cover_art": itunes_results[i]["cover_art"]
        })
        
    vibe_data["tracks"] = final_tracks
    return vibe_data
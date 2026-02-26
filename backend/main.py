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
    """Truncates to 72 bytes to prevent bcrypt crashes."""
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password):
    """Hashes password with 72-byte truncation safety."""
    return pwd_context.hash(password[:72])

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------
# Phase 2: Core Music APIs (Last.fm & Deep Links)
# ---------------------------------------------------------
def fetch_lastfm_tracks_sync(genre: str, limit: int = 5):
    """
    Hits the free Last.fm API to pull trending tracks for a specific genre,
    then generates the Cross-Platform URIs (Spotify Deep Links) to bypass paywalls.
    """
    # Using a fallback generic key if none is provided in .env
    api_key = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    url = f"http://ws.audioscrobbler.com/2.0/?method=tag.gettoptracks&tag={urllib.parse.quote(genre)}&api_key={api_key}&format=json&limit={limit}"
    
    fallback_tracks = [
        {"title": "Nightcrawler", "artist": "Travis Scott", "spotify_uri": "spotify:search:Nightcrawler%20Travis%20Scott", "apple_uri": "music://search?term=Nightcrawler%20Travis%20Scott"},
        {"title": "Resonance", "artist": "HOME", "spotify_uri": "spotify:search:Resonance%20HOME", "apple_uri": "music://search?term=Resonance%20HOME"},
        {"title": "Goth", "artist": "Sidewalks and Skeletons", "spotify_uri": "spotify:search:Goth%20Sidewalks%20and%20Skeletons", "apple_uri": "music://search?term=Goth%20Sidewalks%20and%20Skeletons"}
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
                title = t.get("name")
                artist = t.get("artist", {}).get("name")
                
                # The "Muscle" -> Generating exact Spotify App URIs
                search_query = urllib.parse.quote(f"{title} {artist}")
                spotify_uri = f"spotify:search:{search_query}"
                apple_uri = f"music://search?term={search_query}" # Future proofing for Phase 2 Apple Music
                
                result.append({
                    "title": title, 
                    "artist": artist, 
                    "spotify_uri": spotify_uri, 
                    "apple_uri": apple_uri
                })
            return result
    except Exception as e:
        print(f"Last.fm fetch failed ({e}). Returning fallback offline tracks.")
        return fallback_tracks

async def fetch_lastfm_tracks(genre: str, limit: int = 5):
    """Async wrapper so we don't block the FastAPI event loop."""
    return await asyncio.to_thread(fetch_lastfm_tracks_sync, genre, limit)


# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "VibeFinderAI API is operational."}

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """Registers a new user and hashes their password."""
    # Check for existing identity
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
        data={
            "email": user.email,
            "username": user.username,
            "hashedPassword": hashed_pwd
        }
    )
    return {"message": "User registered successfully", "user_id": new_user.id}

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticates user and hands back a JWT."""
    user = await db.user.find_unique(where={"username": form_data.username})
    
    if not user or not user.hashedPassword:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not verify_password(form_data.password, user.hashedPassword):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    """Fetches the current authenticated user's profile."""
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
        
    return {
        "user_id": user.id, 
        "username": user.username,
        "email": user.email,
        "status": "authenticated"
    }

@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    """Routes the analyze request to the modularized vibe engine and fetches playlist data."""
    
    # 1. Run the AI Acoustic Intelligence Engine
    vibe_data = vibe_engine.analyze_vibe_algorithm(
        text=request.text,
        artist_focus=request.artist_focus,
        genre_focus=request.genre_focus,
        bpm_focus=request.bpm_focus
    )
    
    # 2. Extract best genre for the query
    genres = vibe_data.get("genres", [])
    target_genre = genres[0] if genres else "electronic"
    
    # 3. Hit the Last.fm Brain to fetch tracks (Phase 2!)
    tracks = await fetch_lastfm_tracks(genre=target_genre, limit=5)
    
    # 4. Inject tracks into response payload
    vibe_data["tracks"] = tracks
    
    return vibe_data
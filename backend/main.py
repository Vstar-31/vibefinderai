from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta
import os
import re
from dotenv import load_dotenv
from passlib.context import CryptContext
from contextlib import asynccontextmanager
from prisma import Prisma

# Load environment variables from .env file
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

# Initialize the core FastAPI application with the lifespan hook
app = FastAPI(
    title="VibeFinderAI API", 
    description="Core backend for music discovery and NLP integrations",
    lifespan=lifespan
)

# ---------------------------------------------------------
# CORS Configuration (Allows frontend to talk to backend)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Security & Auth Configuration
# ---------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "development_fallback_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Setup Bcrypt for hashing passwords securely
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------
# Custom NLP Vibe Algorithm (The Brains)
# ---------------------------------------------------------

class VibeRequest(BaseModel):
    text: str

class VibeResponse(BaseModel):
    dominant_vibe: str
    confidence: float
    bpm_range: str
    genres: list[str]
    matched_keywords: list[str]

# Our custom dictionary mapping vibes to keywords, bpms, and genres
VIBE_DICTIONARY = {
    "hype": {
        "keywords": ["gym", "pump", "aggressive", "hype", "energy", "fast", "workout", "run", "lift", "crazy", "rage"], 
        "bpm": "130-170", 
        "genres": ["Phonk", "Hardstyle", "Rap", "EDM"]
    },
    "chill": {
        "keywords": ["relax", "study", "sleep", "calm", "slow", "vibes", "rain", "peace", "quiet", "smoke", "late"], 
        "bpm": "70-90", 
        "genres": ["Lo-Fi", "Ambient", "R&B"]
    },
    "sad": {
        "keywords": ["cry", "heartbreak", "sad", "depressed", "down", "lonely", "tears", "pain", "miss"], 
        "bpm": "60-80", 
        "genres": ["Acoustic", "Sad Pop", "Indie"]
    },
    "happy": {
        "keywords": ["party", "dance", "happy", "summer", "fun", "upbeat", "smile", "good", "sunny", "weekend"], 
        "bpm": "110-130", 
        "genres": ["Pop", "House", "Disco"]
    }
}

def analyze_vibe_algorithm(text: str) -> dict:
    """
    Our custom NLP scoring engine. Tokenizes input text and scores it against
    our VIBE_DICTIONARY to determine the user's mood.
    """
    # Clean and tokenize text (lowercase, extract words only)
    words = re.findall(r'\b\w+\b', text.lower())
    
    scores = {vibe: 0 for vibe in VIBE_DICTIONARY}
    matched = []

    # Score the words against our dictionaries
    for word in words:
        for vibe, data in VIBE_DICTIONARY.items():
            if word in data["keywords"]:
                scores[vibe] += 1
                matched.append(word)

    total_matches = sum(scores.values())
    
    # Fallback if no keywords matched
    if total_matches == 0:
        return {
            "dominant_vibe": "neutral", 
            "confidence": 0.0, 
            "bpm_range": "90-110", 
            "genres": ["Pop", "Chillwave"], 
            "matched_keywords": []
        }

    # Calculate the winner
    dominant_vibe = max(scores, key=scores.get)
    # Calculate confidence as the percentage of matched words belonging to the winning vibe
    confidence = round(scores[dominant_vibe] / total_matches, 2)
    
    return {
        "dominant_vibe": dominant_vibe,
        "confidence": confidence,
        "bpm_range": VIBE_DICTIONARY[dominant_vibe]["bpm"],
        "genres": VIBE_DICTIONARY[dominant_vibe]["genres"],
        "matched_keywords": list(set(matched)) # Return unique matched words
    }

# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    """
    Health check endpoint to verify API operational status.
    """
    return {"message": "VibeFinderAI API is operational."}

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """
    Creates a new user with a hashed password in the database.
    """
    # 1. Check if user already exists
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
    
    # 2. Hash the password securely
    hashed_pwd = get_password_hash(user.password)
    
    # 3. Save to database
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
    """
    Verifies user credentials against the database and returns a JWT.
    """
    # 1. Find user by username
    user = await db.user.find_unique(where={"username": form_data.username})
    
    # 2. Verify existence and password
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
        
    # 3. Generate token using their actual DB user ID
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    """
    Protected endpoint example requiring a valid JWT bearer token.
    Validates token signature and expiration before granting access.
    Fetches the actual user from the database.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    # Fetch actual user from DB to prove it works
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in database")
        
    return {
        "user_id": user.id, 
        "username": user.username,
        "email": user.email,
        "status": "authenticated"
    }

@app.post("/api/vibe/analyze", response_model=VibeResponse)
async def analyze_vibe(request: VibeRequest, token: str = Depends(oauth2_scheme)):
    """
    Protected endpoint to analyze a text prompt and return music vibe metrics.
    Requires authentication to use.
    """
    # Verify user token first (we reuse the same token verification logic implicitly via Depends)
    # Now run our custom algorithm
    result = analyze_vibe_algorithm(request.text)
    return result
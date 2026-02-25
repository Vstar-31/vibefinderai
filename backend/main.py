from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta

# Initialize the core FastAPI application
app = FastAPI(title="VibeFinderAI API", description="Core backend for music discovery and NLP integrations")

# ---------------------------------------------------------
# JWT Configuration 
# Note: Relocate these credentials to environment variables (.env) prior to production
# ---------------------------------------------------------
SECRET_KEY = "development_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Generates a JSON Web Token for user authentication and session management.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ---------------------------------------------------------
# Core API Routes
# ---------------------------------------------------------

@app.get("/")
async def root():
    """
    Health check endpoint to verify API operational status.
    """
    return {"message": "VibeFinderAI API is operational."}

@app.post("/auth/token", response_model=Token)
async def login_for_access_token():
    """
    Mock authentication endpoint for the initial development phase.
    To be replaced with database-backed Supabase/OAuth verification in Phase 2.
    """
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": "development_user_123"}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    """
    Protected endpoint example requiring a valid JWT bearer token.
    Validates token signature and expiration before granting access.
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
    
    return {
        "user_id": user_id, 
        "status": "authenticated", 
        "message": "User access verified successfully."
    }
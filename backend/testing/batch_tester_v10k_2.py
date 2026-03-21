#!/usr/bin/env python3
"""
batch_tester_v10k_2.py â€” VIBEFINDER AI COMPREHENSIVE ANALYSIS SUITE v2 (CURRENT)
20,000+ prompts Ã— Dynamic Track Limits Ã— ALL Pro Mode Overrides + 16 Knob Profiles
250 unique seed prompts Ã— 16 knob profiles Ã— 5 Pro Mode variations = 20,000 test cases
+ Thorough Analytics & Log Generation + Music Services Testing

FEATURES TESTED:
  âœ“ Vibe analysis engine (primary & secondary vibes)
  âœ“ All knob configurations (artist focus, BPM, nicheness)
  âœ“ Pro Mode overrides (genre forcing, artist forcing, secondary vibe pivoting)
  âœ“ Multi-language support (20+ languages)
  âœ“ Track limiting & pagination
  âœ“ Semantic search & ranking
  âœ“ YouTube retry logic (cache + exponential backoff)
  âœ“ Music service OAuth status
  âœ“ Metrics collection & analytics
  âœ“ Gemini AI auto-grading (free tier)

Run from backend folder:
    python testing/batch_tester_v10k_2.py

Outputs:
    analysis_reports/batch_report_TIMESTAMP.json - Comprehensive analysis
    qa_batch_v10k_3.log - Main engine results
    qa_batch_gemini_analysis.log - AI Grades & Summary
    qa_batch_services_status.log - Service connection tests
"""
import asyncio
import logging
import re
import os
import sys
import random
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from prisma import Prisma

# Ensure backend modules are importable regardless of current working directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# For Gemini REST API
try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

# â”€â”€ PROPER IMPORTS FOR NEW MODULAR STRUCTURE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from core import vibe_engine
from core.vibe_engine import LANGUAGE_TAG_MAP

# Lazy-loaded symbols from main.py to avoid heavy imports in FAST_PARALLEL_MODE workers.
fetch_lastfm_tracks = None
fetch_lastfm_artist_tracks = None
fetch_lastfm_track_search = None
filter_and_score_tracks = None
VibeRequest = None
COMMON_WORDS_BLACKLIST = None
TRACK_BLOCKLIST = None


def _ensure_main_symbols_loaded():
    global fetch_lastfm_tracks
    global fetch_lastfm_artist_tracks
    global fetch_lastfm_track_search
    global filter_and_score_tracks
    global VibeRequest
    global COMMON_WORDS_BLACKLIST
    global TRACK_BLOCKLIST

    if VibeRequest is not None and filter_and_score_tracks is not None:
        return

    from main import (
        fetch_lastfm_tracks as _fetch_lastfm_tracks,
        fetch_lastfm_artist_tracks as _fetch_lastfm_artist_tracks,
        fetch_lastfm_track_search as _fetch_lastfm_track_search,
        filter_and_score_tracks as _filter_and_score_tracks,
        VibeRequest as _VibeRequest,
        COMMON_WORDS_BLACKLIST as _COMMON_WORDS_BLACKLIST,
        TRACK_BLOCKLIST as _TRACK_BLOCKLIST,
    )

    fetch_lastfm_tracks = _fetch_lastfm_tracks
    fetch_lastfm_artist_tracks = _fetch_lastfm_artist_tracks
    fetch_lastfm_track_search = _fetch_lastfm_track_search
    filter_and_score_tracks = _filter_and_score_tracks
    VibeRequest = _VibeRequest
    COMMON_WORDS_BLACKLIST = _COMMON_WORDS_BLACKLIST
    TRACK_BLOCKLIST = _TRACK_BLOCKLIST

# â”€â”€ ENVIRONMENT & CONFIGURATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from dotenv import load_dotenv

# load_dotenv() with no args searches CWD — misses backend/.env when the script
# is run from the project root or testing/ subfolder. Always load from BACKEND_DIR.
_env_path = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=_env_path, override=False)
# Also try CWD .env as a secondary source (doesn't override already-set vars)
load_dotenv(override=False)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
METRICS_PASSPHRASE = os.getenv("METRICS_PASSPHRASE")

# Free tier allows 15 RPM. We sample a percentage to grade automatically.
GEMINI_SAMPLE_RATE = 0.1  # 10% of prompts will be auto-graded by AI
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

# Batch configuration
TEST_LIMIT = 20000  # Full suite
DEBUG_MODE = False  # Set to True for limited testing (100 prompts)
ANALYSIS_CONCURRENCY = int(os.getenv("BATCH_ANALYSIS_CONCURRENCY", "8"))
API_DRIVEN_MODE = True
FAST_PARALLEL_MODE = False

# Backend API configuration for real-world, full-stack evaluation.
BACKEND_BASE_URL = os.getenv("BATCH_BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
BATCH_TEST_EMAIL = os.getenv("BATCH_TEST_EMAIL", "batchbot@vibefinder.ai")
BATCH_TEST_USERNAME = os.getenv("BATCH_TEST_USERNAME", "batchbot_v2")
BATCH_TEST_PASSWORD = os.getenv("BATCH_TEST_PASSWORD", "BatchBot@123456")
BACKEND_HEALTH_WAIT_SECONDS = int(os.getenv("BACKEND_HEALTH_WAIT_SECONDS", "30"))
AUTH_RETRY_ATTEMPTS = int(os.getenv("BATCH_AUTH_RETRY_ATTEMPTS", "3"))
AUTH_RETRY_DELAY_SECONDS = float(os.getenv("BATCH_AUTH_RETRY_DELAY_SECONDS", "2.0"))

# Gemini grading setup.
# Keep inline grading disabled for long runs; run Gemini later from log JSONL.
INLINE_GEMINI_EVAL = False
GEMINI_EVAL_ALL = True
GEMINI_CONCURRENCY = 3

# â”€â”€ COMPREHENSIVE LOGGER SETUP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
logging_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs("analysis_reports", exist_ok=True)

# Main Engine Logger
main_logger = logging.getLogger("VibeFinder_Batch")
main_logger.setLevel(logging.DEBUG)
main_fh = logging.FileHandler(f"qa_batch_{logging_ts}.log", encoding="utf-8")
main_sh = logging.StreamHandler()
fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
main_fh.setFormatter(fmt)
main_sh.setFormatter(fmt)
main_logger.handlers = [main_fh, main_sh]

# Services Status Logger
services_logger = logging.getLogger("Services_Status")
services_logger.setLevel(logging.INFO)
services_fh = logging.FileHandler(f"qa_batch_services_{logging_ts}.log", encoding="utf-8")
services_fh.setFormatter(fmt)
services_logger.handlers = [services_fh]

# Metrics Logger
metrics_logger = logging.getLogger("Metrics_Collector")
metrics_logger.setLevel(logging.INFO)
metrics_fh = logging.FileHandler(f"qa_batch_metrics_{logging_ts}.log", encoding="utf-8")
metrics_fh.setFormatter(fmt)
metrics_logger.handlers = [metrics_fh]

# Gemini Analysis Logger
gemini_logger = logging.getLogger("GeminiGrader")
gemini_logger.setLevel(logging.INFO)
g_fh = logging.FileHandler(f"qa_batch_gemini_{logging_ts}.log", encoding="utf-8")
g_fh.setFormatter(fmt)
gemini_logger.handlers = [g_fh, main_sh]

async def evaluate_with_gemini(prompt_payload: dict, response_payload: dict):
    """Evaluate one prompt+response pair using Gemini and return pass/fail style output."""
    if not GEMINI_API_KEY or not _AIOHTTP_AVAILABLE:
        return None

    returned_tracks = response_payload.get("tracks", [])
    track_list_str = ", ".join([
        f"{t.get('title', '')} by {t.get('artist', '')}"
        for t in returned_tracks[:10]
    ])
    if not track_list_str:
        track_list_str = "NO_TRACKS"
    
    sys_prompt = (
        "You are a chill Gen Z audiophile from Jaipur evaluating a music recommendation engine. "
        "Judge if the returned tracks match the user intent, vibe, language, locks, and knobs."
    )

    prompt_text = prompt_payload.get("text", "")
    language = prompt_payload.get("language", "Any")
    knobs = {
        "artist_focus": prompt_payload.get("artist_focus", 50),
        "bpm_focus": prompt_payload.get("bpm_focus", 50),
        "nicheness": prompt_payload.get("nicheness", 50),
        "track_limit": prompt_payload.get("track_limit", 10),
    }

    user_prompt = f"""
    Prompt: "{prompt_text}"
    Language lock: {language}
    Knobs: {json.dumps(knobs)}
    Artist lock: {prompt_payload.get('override_artist')}
    Genre lock: {prompt_payload.get('override_genre')}
    Secondary vibe enabled: {prompt_payload.get('use_secondary_vibe', False)}
    Dismiss detected artist: {prompt_payload.get('dismiss_detected_artist', False)}

    Engine output dominant vibe: "{response_payload.get('dominant_vibe', 'unknown')}"
    Confidence: {response_payload.get('confidence', 0)}
    Secondary vibe: {response_payload.get('secondary_vibe')}
    Secondary confidence: {response_payload.get('secondary_confidence', 0)}
    Genres selected: {response_payload.get('genres', [])}
    Tracks returned ({len(returned_tracks)}): {track_list_str}

    Grade strictly and respond ONLY with valid JSON in this exact schema:
    {{
      "verdict": "PASS" | "PARTIAL" | "FAIL",
      "relevancy_score": 0-100,
      "reason": "short explanation",
      "issues": ["issue1", "issue2"],
      "improvements": ["suggestion1", "suggestion2"]
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GEMINI_URL, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text_resp = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = json.loads(text_resp)
                    if "verdict" not in parsed:
                        parsed["verdict"] = "FAIL"
                    if "relevancy_score" not in parsed:
                        parsed["relevancy_score"] = 0
                    return parsed
                elif resp.status == 429:
                    return {
                        "verdict": "FAIL",
                        "relevancy_score": 0,
                        "reason": "Rate limited",
                        "issues": ["gemini_rate_limited"],
                        "improvements": ["retry_later"],
                    }
    except Exception as e:
        return {
            "verdict": "FAIL",
            "relevancy_score": 0,
            "reason": f"Gemini failed: {str(e)}",
            "issues": ["gemini_error"],
            "improvements": ["check_api_key_or_quota"],
        }
    return None


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# KNOB PROFILES â€” 16 configurations
# (artist_focus 0-100, bpm_focus 0-100, nicheness 0-100, label)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
KNOB_PROFILES = [
    (50,  100, 50,  "default_balanced"),
    (10,  100, 50,  "artist_suppressed"),
    (90,  100, 50,  "artist_dominant"),
    (50,   30, 50,  "bpm_very_slow"),
    (50,   80, 50,  "bpm_slow_mid"),
    (50,  130, 50,  "bpm_upbeat"),
    (50,  170, 50,  "bpm_very_fast"),
    (50,  100, 10,  "mainstream_heavy"),
    (50,  100, 90,  "ultra_niche"),
    (10,   40, 80,  "niche_ambient_slow"),
    (80,  150, 20,  "mainstream_hype"),
    (70,  140, 70,  "artist_hype_niche"),
    (20,   60, 30,  "chill_mainstream"),
    (60,  110, 60,  "mid_everything"),
    (40,   90, 40,  "soft_balanced"),
    (90,  160, 90,  "max_all"),
]

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SEED PROMPTS â€” 250 Gen Z Power User Prompts (Expanded Jaipur/India/Global edition)
# Format: (text, language, default_knob_idx, override_genre, override_artist)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_SEEDS = [
    # -- Original 125 --
    ("late night drive through rain-slicked streets, Travis Scott on the radio", "English", 14, "trap", "Travis Scott"),
    ("dil toota hai, 2 baje raat, akela baitha hoon, Aditya Rikhari type", "Hindi", 1, "indie pop", "Aditya Rikhari"),
    ("full bhangra session, shaadi wali raat, Diljit Dosanjh energy", "Punjabi", 11, "bhangra", "Diljit Dosanjh"),
    ("3am coding, dark room, chai getting cold, lofi study beats", "Hindi", 12, "lofi hip hop", None),
    ("heavy gym session, phonk, beast mode activated, mass bgm vibes", "English", 10, "drift phonk", None),
    ("sufi night, rooftop old Delhi, Nusrat Fateh Ali Khan energy, ghazal", "Urdu", 14, "qawwali", "Nusrat Fateh Ali Khan"),
    ("BTS sad hours, crying at 1am, ARMY feels, kpop ballad emotional wreck", "Korean", 14, "k-pop ballad", "BTS"),
    ("solo trip to Himachal, acoustic guitar, bittersweet feelings, Sahiba", "Hindi", 13, "hindi acoustic", None),
    ("desi hip hop underground, Raftaar and Divine energy, Mumbai streets", "Hindi", 11, "desi hip hop", "Divine"),
    ("Haryanvi rap, attitude mode, success story, heavy bass drops, desi swag", "Hindi", 11, "haryanvi", "Masoom Sharma"),
    ("Tamil mass action BGM, Thalapathy Vijay movie energy, whistling moment", "Tamil", 10, "kollywood action", "Anirudh"),
    ("4am can't sleep, indie pop sad, GINI type, windows open, city sounds", "English", 14, "indie sad", "GINI"),
    ("Reels mein viral song, Instagram explore type, trending 2025 desi", "Hindi", 7, "bollywood", None),
    ("sangeet night, bhangra and bollywood mix, dholak beats, full crowd", "Punjabi", 10, "bhangra", None),
    ("dark phonk midnight workout, tunnel vision, heavy bass, menacing synths", "English", 11, "phonk", None),
    ("90s Bollywood nostalgia, Kumar Sanu, rainy evening, purani yaadein", "Hindi", 13, "old bollywood", "Kumar Sanu"),
    ("BLACKPINK type energy, girl group bops, Pink Venom vibes, dance along", "Korean", 10, "k-pop", "BLACKPINK"),
    ("sad and numb but kinda okay, November mood, Phoebe Bridgers, slow indie", "English", 14, "indie folk", "Phoebe Bridgers"),
    ("empty highway 2am, no destination, stars above, melancholy beautiful", "English", 12, "dream pop", None),
    ("lofi hip hop study, late night exam prep, cozy room, soft rain outside", "English", 12, "lofi hip hop", None),
    ("Punjabi breakup feels, tenu pata nahi si, dil tutda hai, slow sad", "Punjabi", 14, "punjabi sad", "B Praak"),
    ("Telugu mass blockbuster, Pushpa type, Allu Arjun swag, folk mass beats", "Telugu", 10, "tollywood mass", "S.S. Thaman"),
    ("bhajan clubbing vibes, tabla meets EDM, Navratri garba remix, spiritual", "Hindi", 10, "bollywood edm", None),
    ("bedroom pop, indie aesthetic, Rex Orange County type, pastel colors", "English", 13, "bedroom pop", "Rex Orange County"),
    ("Kerala rain, Malayalam film songs, ocean waves, peaceful summer vibes", "Malayalam", 14, "malayalam", None),
    ("Arijit Singh type ballad, tere bina, rainy window, emotional Bollywood", "Hindi", 14, "bollywood sad", "Arijit Singh"),
    ("Afrobeats party, Burna Boy Wizkid type, sweaty late night club", "Afrobeats", 10, "afrobeats", "Burna Boy"),
    ("Jaipur night, rooftop, chill playlist, friends laughing, no AC", "Hindi", 12, "hindi chill", None),
    ("pehli baarish, monsoon magic, petrichor, slow romantic, window mein", "Hindi", 14, "bollywood romantic", None),
    ("BGMI ranked match, solo squad, trap beats, dark room setup, focus", "English", 10, "trap", None),
    ("getting ready for night out, Dua Lipa Olivia Rodrigo vibes, hype girlie pop", "English", 10, "dance pop", "Dua Lipa"),
    ("board exam stress, 12th class, sad anxious, cram session, raat ke 2 baje", "Hindi", 9, "hindi sad", None),
    ("indie Japanese city pop, anime OST vibes, Tokyo rain, Ado type", "Japanese", 13, "city pop", "Ado"),
    ("empty highway 2am clean version, no artist named, stars, drive, beautiful", "English", 12, "ambient", None),
    ("Goa beach sunset, coconut toddy, reggae trance, feet in sand, ocean", "English", 12, "reggae", None),
    ("rave festival sunrise, trance music, sweaty crowd, spiritual high, arms up", "English", 10, "psytrance", None),
    ("coming out of depression era, finally okay, self love summer, indie happy", "English", 13, "indie pop", None),
    ("urdu poetry mood, Faiz Ahmad Faiz, dimly lit, intellectual, chai and cigarette", "Urdu", 9, "ghazal", None),
    ("Spanish romantic evening, Latin vibes, salsa nights, sangria and dancing", "Spanish", 13, "salsa", None),
    ("Rabindra Sangeet, Bengali monsoon, bhalobasa, philosophical, Tagore poetry", "Bengali", 14, "rabindra sangeet", None),
    ("post-punk existential dread, Radiohead Thom Yorke OK Computer era, dystopian", "English", 10, "post-punk", "Radiohead"),
    ("Kendrick Lamar introspective, deep rap thinking, late night city bus, bars", "English", 13, "hip-hop", "Kendrick Lamar"),
    ("The Weeknd dark RnB, neon lights hotel room, heartbreak high, 80s synth", "English", 10, "synthwave", "The Weeknd"),
    ("Bollywood item number, Badshah rap, desi club banger, shaadi floor packed", "Hindi", 10, "bollywood dance", "Badshah"),
    ("college hostel night, new friends, laughing at 3am, spontaneous, carefree", "English", 13, "indie pop", None),
    ("NewJeans Hype Boy type, cute kpop, bubbly pop, walking to class bop", "Korean", 13, "k-pop", "NewJeans"),
    ("midnight anxiety can't sleep, overthinking, soft piano, need to calm down", "Any", 9, "ambient", None),
    ("first love feeling, butterflies, Spotify crush playlist, acoustic warm, shy", "Any", 14, "acoustic pop", None),
    ("amapiano crossover desi, tabla and piano, new wave Indian club sound", "Any", 10, "amapiano", None),
    ("morning run sunrise, motivational, upbeat, headphones in, city waking up", "English", 5, "dance pop", None),
    ("Kanye West dark fantasy era, maximalist production, introspective rap", "English", 10, "hip-hop", "Kanye West"),
    ("lo-fi but make it Indian, sitar samples, tabla background, desi chill study", "Hindi", 12, "hindi lofi", None),
    ("Frank Ocean Blonde era, introspective RnB, summer grief, soft production", "English", 14, "neo soul", "Frank Ocean"),
    ("Sabrina Carpenter Espresso type, flirty pop, confidence walk, fun bops", "English", 10, "pop", "Sabrina Carpenter"),
    ("pre exam raat ki chai, anxiety, past paper, stressed student, midnight", "Hindi", 9, "hindi acoustic", None),
    ("Tamil kuthu beats, Yuvan Shankar Raja style, mass folk EDM, whistling", "Tamil", 10, "kollywood dance", "Yuvan Shankar Raja"),
    ("late night Bangalore techno underground, warehouse rave, no sleep till sunrise", "English", 10, "hard techno", None),
    ("Coldplay Yellow era, dreamy guitar, hopeful sad, soft glowing lights", "English", 13, "indie rock", "Coldplay"),
    ("KGF Rocky Bhai energy, mass BGM, power walk, goosebumps moment", "Kannada", 10, "kannada bgm", "Ravi Basrur"),
    ("Punjabi breakup, Shubh dark Punjabi, bass heavy, night out modern sound", "Punjabi", 11, "punjabi trap", "Shubh"),
    ("vibing alone on Sunday, no plans, lazy afternoon, sunlight through curtains", "Any", 12, "chillhop", None),
    ("DIVINE Mumbai street rap, gully boy energy, underground, represent", "Hindi", 11, "desi hip hop", "DIVINE"),
    ("Portuguese saudade, melancholic longing, fado vibes, ocean and nostalgia", "Portuguese", 14, "fado", None),
    ("Arabic trap, Egyptian drill, Cairo nights, dark energy, Middle Eastern bass", "Arabic", 10, "arabic trap", None),
    ("Mitski devastated, indie rock crying, emotional breakdown, loud then quiet", "English", 14, "indie rock", "Mitski"),
    ("Taylor Swift revenge era, angry empowerment pop, glow up anthem", "English", 10, "pop", "Taylor Swift"),
    ("desi wedding reception, everyone on floor, Bollywood classics 2000s, timepass", "Hindi", 7, "bollywood", None),
    ("chillhop anime aesthetic, lo-fi girl energy, cozy rainy window, study", "Japanese", 12, "lofi hip hop", None),
    ("Carnatic fusion, AR Rahman style, orchestral Indian, emotional cinematic", "Tamil", 13, "kollywood bgm", "A.R. Rahman"),
    ("sad Malayalam film scene, emotional climax, rain, crying, background score", "Malayalam", 14, "malayalam sad", None),
    ("Haryanvi folk meets hip hop, Sapna Choudhary energy, desi swag, jat vibes", "Hindi", 11, "haryanvi", "Sapna Choudhary"),
    ("Bon Iver sad beautiful, falsetto, indie folk car cry, winter isolated", "English", 14, "indie folk", "Bon Iver"),
    ("Tame Impala psychedelic, mind melting, floating in space, reverb heavy", "English", 13, "psychedelic rock", "Tame Impala"),
    ("post breakup glow up, Taylor Swift revenge, angry pop, empowerment", "English", 10, "pop", "Olivia Rodrigo"),
    ("Chill Arabic pop, khaleeji vibes, desert night, oud and beats, ambient", "Arabic", 12, "khaleeji", None),
    ("exam over relief, summer vacation, carefree, windows down, screaming bops", "English", 10, "pop punk", None),
    ("2000s Bollywood nostalgia, Udit Narayan, Shah Rukh film, slow dance scene", "Hindi", 13, "old bollywood", "Udit Narayan"),
    ("Telugu love song, AR Rahman feel, soft rain, first date nervous, beautiful", "Telugu", 14, "tollywood romantic", "A.R. Rahman"),
    ("UK drill meets desi, British Indian diaspora, London streets, grime + curry", "English", 10, "uk drill", "Central Cee"),
    ("Himesh Reshammiya era, nasal vocals, 2005 Bollywood, ringtone era nostalgia", "Hindi", 13, "bollywood", "Himesh Reshammiya"),
    ("Ibiza deep house, golden hour terrace, sipping something cold, smooth", "English", 12, "melodic house", None),
    ("Harry Styles Harry's House era, soft indie pop, summery, dancing in kitchen", "English", 13, "indie pop", "Harry Styles"),
    ("GTA at 3am, city crime vibes, old school hip hop, 2000s West Coast rap", "English", 10, "hip-hop", "Dr. Dre"),
    ("Lana Del Rey Hollywood sadcore, vintage California, glamour and grief", "English", 14, "sadcore", "Lana Del Rey"),
    ("Marathi Ganesh chaturthi, dhol taasha, loud crowd, festival energy", "Any", 10, "marathi folk", "Ajay-Atul"),
    ("AP Dhillon Punjabi RnB, smooth international sound, diaspora love song", "Punjabi", 13, "punjabi rnb", "AP Dhillon"),
    ("sunrise after all-nighter, watching sun come up, bittersweet tired beautiful", "Any", 14, "ambient", None),
    ("Carnatic meets jazz, Indian classical improvisation, sophisticated late night", "Any", 12, "carnatic jazz", None),
    ("Gully Boy full soundtrack energy, multiple desi rappers, raw streets, real", "Hindi", 11, "desi hip hop", "Naezy"),
    ("post concert high, ears ringing, emotional, grateful, favourite artist live", "English", 14, "indie pop", None),
    ("Assamese Bihu festival, folk instruments, harvest celebration, northeast joy", "Any", 10, "bihu", None),
    ("late night coding bug fixing, energy drink, intense focus, dark IDE", "English", 10, "idm", None),
    ("Bengali indie rock, Fossils or Cactus type, Kolkata, emotion and rain", "Bengali", 13, "bengali rock", "Fossils"),
    ("sad vibes only, no specific genre, just recommend me something for crying", "Any", 14, "sad", None),
    ("Woke up feeling like Ranveer Singh, hyper confident, Bollywood hero entry", "Hindi", 10, "bollywood", "Ranveer Singh"),
    ("playing something from my city's underground music scene, Delhi", "English", 12, "delhi indie", "Peter Cat Recording Co."),
    ("totally exhausted, need something that isn't English, just give me something beautiful", "Japanese", 9, "japanese ambient", None),
    ("describe VibeFinderAI itself â€” oscilloscope, neural, music discovery engine", "Any", 12, "ambient techno", None),
    ("my favorite prompt of the test â€” whichever vibe you felt worked best, try it again with higher nicheness", "Hindi", 8, "indie folk", "Prateek Kuhad"),
    ("one more thing â€” give me something I've never heard before, maximum nicheness, any language, any vibe", "Any", 8, "experimental", None),
    ("grungy 90s alt rock, seattle flannel, angst and heavy distortion", "English", 10, "grunge", "Nirvana"),
    ("hyperpop glitchcore madness, sugar rush, 200 bpm, internet brain rot", "English", 6, "hyperpop", "100 gecs"),
    ("Bhojpuri mass dance, high energy, village party, loud beats", "Hindi", 10, "bhojpuri", "Pawan Singh"),
    ("soft french cafe morning, accordion, espresso, romantic paris vibes", "French", 13, "chanson", "Edith Piaf"),
    ("cyberpunk 2077 night city drive, dark synthwave, neon lights glowing", "English", 10, "cyberpunk", "Gesaffelstein"),
    ("heavy metal gym PR, double bass pedals, screaming vocals, purely aggressive", "English", 6, "metalcore", "Bring Me The Horizon"),
    ("soft country morning, acoustic guitar on a porch, cowboy coffee, peaceful", "English", 13, "americana", "Tyler Childers"),
    ("retro 80s pop montage, training for the big fight, synth brass, euphoric", "English", 5, "80s pop", "Survivor"),
    ("midwest emo revival, twinkly guitars, screaming in a basement, nostalgic", "English", 14, "midwest emo", "American Football"),
    ("bossa nova afternoon, ipanema beach, gentle acoustic, portuguese singing", "Portuguese", 13, "bossa nova", "JoÃ£o Gilberto"),
    ("shoegaze wall of sound, looking at my pedals, fuzzy dreamy loud", "English", 13, "shoegaze", "My Bloody Valentine"),
    ("industrial techno warehouse, berlin 4am, strobe lights, dark heavy bass", "English", 10, "industrial techno", "Amelie Lens"),
    ("symphonic epic battle, dragons flying, choir swelling, huge orchestration", "Any", 10, "epic orchestral", "Hans Zimmer"),
    ("classic 70s soul, motown feel, funky bassline, smooth vocals", "English", 13, "soul", "Marvin Gaye"),
    ("latin trap bad bunny style, perreo, aggressive club vibes, puertorico", "Spanish", 11, "latin trap", "Bad Bunny"),
    ("celtic folk pub night, fiddles playing fast, drinking songs, happy", "English", 10, "celtic folk", "The Dubliners"),
    ("reggae dub chill out, kingston vibes, heavy bass slow tempo, smoke", "English", 12, "dub", "Bob Marley"),
    ("lofi house, 4 on the floor but dusty samples, deep groove, late night", "English", 12, "lofi house", "Ross From Friends"),
    ("classical piano solo, chopin nocturne vibes, raining outside, very sad", "Any", 14, "classical piano", "Chopin"),
    ("vaporwave mall music, 1995 nostalgia, pitched down diana ross, purple", "Any", 12, "vaporwave", "Macintosh Plus"),
    ("hardstyle euphoric drop, q-dance festival, 150 bpm, laser show", "English", 6, "hardstyle", "Headhunterz"),
    ("neo-soul cafe, baduizm era, smooth rhodes piano, head nodding groove", "English", 13, "neo soul", "Erykah Badu"),
    ("garage rock revival, 2001 new york city, leather jackets, raw guitars", "English", 10, "garage rock", "The Strokes"),
    ("sandalwood romantic hits, puneeth rajkumar movies, soft melody", "Kannada", 14, "kannada", "Puneeth Rajkumar"),
    ("desi lofi mashup, old bollywood vocals over hip hop beats, chillhop", "Hindi", 12, "bollywood lofi", None),
    
    # -- New 125 Seeds (Total 250) -- 
    ("patrika gate hangouts, cool evening in Jaipur, acoustic indie covers", "Hindi", 13, "indie pop", "Osho Jain"),
    ("sigma male patrick bateman phonk walk, literally me", "English", 11, "drift phonk", "Kordhell"),
    ("skibidi toilet rizz party, literal brain rot music, sped up", "English", 6, "hyperpop", "Nettspend"),
    ("sad boi hours, missed her call, slowed and reverb hindi", "Hindi", 14, "bollywood lofi", "Jubin Nautiyal"),
    ("late night long drive on nahargarh, windows down, thinking deep", "Hindi", 12, "hindi chill", "The Local Train"),
    ("punjabi gym hardstyle, lifting heavy, sidhu moosewala remix edm", "Punjabi", 10, "hardstyle", "Sidhu Moosewala"),
    ("korean indie cafe, raining outside, matcha latte, soft vocals", "Korean", 12, "k-indie", "The Black Skirts"),
    ("raw delhi underground rap, seedhe maut energy, moshpit", "Hindi", 11, "desi hip hop", "Seedhe Maut"),
    ("bhojpuri lollypop lagelu club mix, desi dj night, fully drunk", "Hindi", 10, "bhojpuri", "Pawan Singh"),
    ("tamil sad scene, anirudh heartbreak bgm, crying in the rain", "Tamil", 14, "kollywood sad", "Anirudh Ravichander"),
    ("anime opening hype, running to school, anime protagonist energy", "Japanese", 10, "j-pop", "LiSA"),
    ("late 90s shah rukh khan entry, arms wide open, pure romance", "Hindi", 13, "bollywood romantic", "Jatin-Lalit"),
    ("chill guitar on the balcony, bangalore weather, evening breeze", "English", 12, "acoustic", "Prateek Kuhad"),
    ("amapiano sunset party, south african grooves, sipping cocktails", "Afrobeats", 12, "amapiano", "Kabza De Small"),
    ("goa trance full moon party, anjuna beach, psych, mind expanding", "Any", 10, "goa trance", "Astrix"),
    ("classical sitar for studying, deep focus, indian classical morning", "Hindi", 9, "hindustani classical", "Ravi Shankar"),
    ("french house filter sweep, daft punk disco vibes, groovy bass", "French", 10, "french house", "Daft Punk"),
    ("telugu mass item song, full whistling, packed theatre, celebration", "Telugu", 10, "tollywood", "Devi Sri Prasad"),
    ("sad mallu breakup song, driving alone in kochi, rain", "Malayalam", 14, "malayalam sad", "Hesham Abdul Wahab"),
    ("indie folk harmony, autumn leaves falling, nostalgic acoustic", "English", 13, "indie folk", "The Paper Kites"),
    ("drill rap london, grim reaper, aggressive 808 slides", "English", 11, "uk drill", "Headie One"),
    ("kannada emotional climax, mother sentiment song, kgf tears", "Kannada", 14, "kannada", "Ravi Basrur"),
    ("sufi qawwali clapping, divine connection, hypnotic rhythm", "Urdu", 12, "qawwali", "Abida Parveen"),
    ("gothic post-punk, wearing all black, dancing in a dark room", "English", 10, "post-punk", "Joy Division"),
    ("synthwave drive outrun, neon grid, retrowave outrun aesthetic", "English", 10, "synthwave", "Kavinsky"),
    ("marathi lavani dance, high tempo, folk instruments, loud", "Marathi", 10, "marathi folk", "Ajay-Atul"),
    ("afrobeat fela kuti classic, brass section, political groove", "Afrobeats", 13, "afrobeat", "Fela Kuti"),
    ("spanish flamenco guitar, passionate clapping, fire dance", "Spanish", 10, "flamenco", "Paco de LucÃ­a"),
    ("brazilian funk carioca, favela party, heavy bass dirty", "Portuguese", 10, "baile funk", "MC Kevin o Chris"),
    ("old school boom bap hip hop, new york 90s, scratch dj", "English", 13, "boom bap", "Nas"),
    ("ambient drone sleep music, floating in space, no beat", "Any", 9, "drone", "Stars of the Lid"),
    ("irish pub drinking song, dropkick murphys, loud singing", "English", 10, "celtic punk", "The Pogues"),
    ("reggaeton summer anthem, bad bunny club hit, dancing sweat", "Spanish", 10, "reggaeton", "J Balvin"),
    ("lofi jazz hop, rainy cafe, saxophone, study relax", "English", 12, "jazz hop", "Nujabes"),
    ("chicago house 90s, warehouse party, piano chords, soul vocal", "English", 10, "chicago house", "Frankie Knuckles"),
    ("epic choral trailer music, two steps from hell, world ending", "Any", 10, "epic", "Thomas Bergersen"),
    ("bedroom pop diy, girl in red, softly singing, queer love", "English", 13, "bedroom pop", "girl in red"),
    ("math rock tapping, odd time signatures, complex guitar", "English", 10, "math rock", "Polyphia"),
    ("shoegaze wall of guitar fuzz, my bloody valentine, loud hazy", "English", 13, "shoegaze", "Slowdive"),
    ("kpop boy group hype, stray kids, loud aggressive choreography", "Korean", 10, "k-pop", "Stray Kids"),
    ("japanese city pop driving, mariya takeuchi, 80s tokyo night", "Japanese", 13, "city pop", "Mariya Takeuchi"),
    ("punjabi folk sad, old memories, village life, tumbi", "Punjabi", 14, "punjabi folk", "Gurdas Maan"),
    ("hindi indie pop, local train type, nostalgia road trip", "Hindi", 13, "indie pop", "When Chai Met Toast"),
    ("metalcore breakdown, open up the pit, architect style", "English", 6, "metalcore", "Architects"),
    ("country pop summer radio, luke bryan, drinking beer outside", "English", 10, "country pop", "Luke Bryan"),
    ("dubstep heavy drop, skrillex, laser show, bass face", "English", 11, "dubstep", "Skrillex"),
    ("nu disco funky bass, purple disco machine, groovy night", "English", 10, "nu disco", "Purple Disco Machine"),
    ("cumbia sonidera, dancing cumbia, accordion, latin party", "Spanish", 10, "cumbia", "Los Ãngeles Azules"),
    ("bengali rock fossils, kolkata underground, emotional shouting", "Bengali", 11, "bengali rock", "Rupam Islam"),
    ("urdu lofi poetry, sad aesthetic, moonlit balcony", "Urdu", 14, "lofi", "Ali Sethi"),
    ("assamese bihu dance, spring festival, dhol pepa", "Assamese", 10, "bihu", "Zubeen Garg"),
    ("gujarati dj song, garba night, non stop dance", "Marathi", 10, "garba", "Kirtidan Gadhvi"),
    ("nepali bihu folk, northeast melodies, sweet romantic", "Any", 13, "folk", "Papon"),
    ("slowed reverb phonk, late night street racing, dark", "English", 14, "drift phonk", "PlayaPhonk"),
    ("hyperpop 100 gecs chaotic, sugar crash, distorted bass", "English", 6, "hyperpop", "Laura Les"),
    ("glitchcore internet music, chronically online, discord call", "English", 10, "glitchcore", "glaive"),
    ("dark academia classical, cellos, dusty library, studying", "Any", 9, "classical", "Vivaldi"),
    ("cottagecore folk, hozier, running through fields", "English", 13, "indie folk", "Hozier"),
    ("royalcore orchestral, bridgerton ball, string quartet", "Any", 10, "classical crossover", "Vitamin String Quartet"),
    ("pirate tavern music, hurdy gurdy, sea shanty", "English", 10, "sea shanty", "The Longest Johns"),
    ("vaporwave mallsoft, empty mall 1998, muzak slowed", "Any", 12, "mallsoft", "çŒ« ã‚· Corp."),
    ("soviet post punk, molchat doma, cold bleak winter", "Any", 10, "russian post-punk", "Molchat Doma"),
    ("mexican corridos tumbados, peso pluma, acoustic guitar trap", "Spanish", 11, "corridos tumbados", "Peso Pluma"),
    ("jamaican dancehall bashment, whining, loud sound system", "English", 10, "dancehall", "Vybz Kartel"),
    ("nigerian alte cruise, cruise music, smooth afrobeats", "Afrobeats", 12, "alte", "Cruel Santino"),
    ("south african gqom, dark electronic dance, heavy drums", "Afrobeats", 10, "gqom", "DJ Maphorisa"),
    ("moroccan mahraganat, street wedding, auto tune loud", "Arabic", 10, "mahraganat", "Hassan Shakosh"),
    ("turkish gnawa folk, spiritual trance, desert instruments", "Arabic", 12, "gnawa", "Hamza El Din"),
    ("persian psych rock, 70s anatolian rock, funky", "Any", 10, "anatolian rock", "AltÄ±n GÃ¼n"),
    ("french rap marseille, pnl, aggressive street trap", "French", 11, "french rap", "PNL"),
    ("german techno bunker, 140bpm, dark sweat", "English", 11, "hard techno", "Klangkuenstler"),
    ("italian disco 80s, synth pop, cheesy but good", "Any", 10, "italo disco", "Giorgio Moroder"),
    ("korean trot music, ahjumma dance, upbeat old school", "Korean", 10, "trot", "Lim Young-woong"),
    ("japanese visual kei, x japan, dramatic rock goth", "Japanese", 10, "visual kei", "X Japan"),
    ("chinese vocaloid, hatsune miku, electronic pop fast", "Japanese", 6, "vocaloid", "Hatsune Miku"),
    ("thai funk 70s, groovy bass, rare vinyl find", "Any", 10, "thai funk", "Khruangbin"),
    ("indonesian bossa nova, cafe music, breezy morning", "Any", 12, "bossa nova", "Tom Jobim"),
    ("filipino harana, acoustic serenading, soft love", "Any", 14, "opm", "Ben&Ben"),
    ("malaysian dangdut, wedding dance, traditional upbeat", "Any", 10, "dangdut", "Rhoma Irama"),
    ("australian indie rock, surf trash, sun bleached guitar", "English", 10, "surf rock", "Ocean Alley"),
    ("new zealand psych, tame impala vibes, fuzzy synths", "English", 12, "psychedelic pop", "Pond"),
    ("canadian reggae, soft dub, island vibes in the cold", "English", 12, "reggae", "Magic!"),
    ("hawaiian roots reggae, ukulele, beach bonfire", "English", 12, "hawaiian reggae", "J Boog"),
    ("trinidadian lovers rock, sweet reggae, romantic slow", "English", 14, "lovers rock", "Gregory Isaacs"),
    ("cuban mariachi, trumpets, cantina drinking", "Spanish", 10, "mariachi", "Vicente FernÃ¡ndez"),
    ("argentinian ranchera, heartbreak tequila, loud crying", "Spanish", 14, "ranchera", "Christian Nodal"),
    ("colombian salsa cubana, fast footwork, brass heavy", "Spanish", 10, "salsa", "Celia Cruz"),
    ("peruvian vallenato, accordion, emotional folk", "Spanish", 10, "vallenato", "Carlos Vives"),
    ("chilean tango, dramatic romantic dance, violin", "Spanish", 14, "tango", "Astor Piazzolla"),
    ("venezuelan merengue, fast tropical, party hits", "Spanish", 10, "merengue", "Elvis Crespo"),
    ("ecuadorian reggaeton old school, don omar, gasolina", "Spanish", 10, "reggaeton", "Don Omar"),
    ("bolivian bachata, slow hip movement, guitar romantic", "Spanish", 14, "bachata", "Romeo Santos"),
    ("paraguayan chicha, psychedelic cumbia, weird synths", "Spanish", 10, "chicha", "Los Destellos"),
    ("uruguayan zamba, slow sad folk, acoustic", "Spanish", 14, "zamba", "Mercedes Sosa"),
    ("guyanese calypso, steel pan drum, carnival beach", "Any", 10, "calypso", "Mighty Sparrow"),
    ("surinamese soca, jump up festival, whistles blowing", "Any", 10, "soca", "Machel Montano"),
    ("icelandic indie pop, lorde style, soft synth", "English", 13, "indie pop", "BjÃ¶rk"),
    ("finnish ethereal wave, sigur ros, icy glacier music", "Any", 9, "ethereal wave", "Sigur RÃ³s"),
    ("swedish death metal, gothenburg sound, melodic fast", "English", 11, "melodic death metal", "In Flames"),
    ("norwegian black metal, dark forest church burning", "English", 11, "black metal", "Mayhem"),
    ("danish power metal, dragons fantasy, soaring vocals", "English", 10, "power metal", "Nightwish"),
    ("poland eurodance 90s, aqua barbie girl vibes, fun", "English", 10, "eurodance", "Aqua"),
    ("dutch trance classic, tiesto, 1999 rave, arpeggios", "English", 10, "trance", "TiÃ«sto"),
    ("belgian hardstyle bounce, jumpstyle, crazy bass", "English", 6, "jumpstyle", "Jeckyll & Hyde"),
    ("austrian gabber, hakken dance, distorted kick drum", "English", 11, "gabber", "Angerfist"),
    ("swiss classical waltz, ballroom dance, elegant strings", "Any", 9, "waltz", "Johann Strauss II"),
    ("hungarian folk punk, accordion distortion, drunk party", "Any", 10, "folk punk", "Gogol Bordello"),
    ("czech dark cabaret, gothic piano, dramatic singing", "Any", 10, "dark cabaret", "The Dresden Dolls"),
    ("slovakian ska punk, upbeat brass section, skanking", "English", 10, "ska punk", "Streetlight Manifesto"),
    ("croatian gypsy punk, balkan beats, wild violin", "Any", 10, "balkan brass", "Goran BregoviÄ‡"),
    ("serbian turbofolk, balkan club music, accordion edm", "Any", 10, "turbofolk", "Ceca"),
    ("romanian disco polo, eastern bloc 90s party", "Any", 10, "disco polo", "Akcent"),
    ("bulgarian manele, street party, synth melodies", "Any", 10, "manele", "Florin Salam"),
    ("greek arabesk, oriental pop, emotional strings", "Any", 14, "arabesk", "Ä°brahim TatlÄ±ses"),
    ("ukrainian hardbass, 200 bpm, squatting in tracksuits", "Any", 6, "hardbass", "DJ Blyatman"),
    ("lithuanian phonk drift, cowbell melody, car edit", "English", 11, "drift phonk", "Kaito Shoma"),
    ("latvian chillwave synth, neon nostalgia, slow driving", "English", 12, "chillwave", "Tycho"),
    ("estonian outrun retro, 80s arcade game, driving fast", "English", 10, "outrun", "Lazerhawk"),
    ("albanian future funk, french touch, bass slapping", "English", 10, "future funk", "Yung Bae"),
    ("macedonian trap metal, scarlxrd scream rap, distorted", "English", 11, "trap metal", "Scarlxrd"),
    ("bosnian emo rap, lil peep style, acoustic guitar trap", "English", 14, "emo rap", "Lil Peep"),
    ("montenegrin cloud rap, yung lean aesthetic, sad boy", "English", 14, "cloud rap", "Yung Lean"),
    ("slovenian plugg rnb, autumn leaves, soft beats", "English", 12, "pluggnb", "Autumn!"),
    ("kosovan jersey club bounce, bed squeak sample, tiktok dance", "English", 10, "jersey club", "Bandmanrill"),
    ("moldovan drill uk, pop smoke bass slides, aggressive", "English", 11, "uk drill", "Pop Smoke")
]

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PROMPT BUILDER â€” 250 seeds Ã— 16 knobs Ã— 5 Pro Modes = 20,000 cases
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _extra_jaipur_genz_audiophile_seeds():
    """Extra prompts in Jaipur Gen-Z Hinglish style with broad genre coverage."""
    scenes = [
        "jawahar circle late-night loop",
        "nahargarh fort sunset scene",
        "c-scheme cafe study grind",
        "hostel terrace 2am feels",
        "old jaipur walk in walled city",
        "raja park scooty ride",
        "patrika gate rainy evening",
        "college fest aftermovie energy",
        "amer road dawn drive",
        "bapu bazaar thrift run",
    ]
    moods = [
        "clean mix, no cringe remixes",
        "warm analog texture, less harsh highs",
        "bass tight but not muddy",
        "vocals upfront but chill",
        "moody but still replayable",
        "underground gems only",
        "fresh tracks not overused reels songs",
        "high-detail headphone session",
        "car speaker friendly with punch",
        "minimal atmospheric late-night",
    ]
    genre_specs = [
        ("desi hip hop", "Hindi"),
        ("punjabi rnb", "Punjabi"),
        ("qawwali fusion", "Urdu"),
        ("hindustani neo-classical", "Hindi"),
        ("sufi rock", "Hindi"),
        ("uk garage", "English"),
        ("drum and bass", "English"),
        ("afro house", "English"),
        ("future garage", "English"),
        ("jazz fusion", "Any"),
        ("indie electronica", "English"),
        ("math rock", "English"),
        ("city pop", "Japanese"),
        ("k-indie", "Korean"),
        ("baile funk", "Portuguese"),
        ("arabic trap", "Arabic"),
        ("tamil indie", "Tamil"),
        ("telugu melodic", "Telugu"),
        ("marathi indie", "Marathi"),
        ("bhojpuri folk fusion", "Hindi"),
    ]

    generated = []
    for scene in scenes:
        for mood in moods[:6]:
            for genre, language in genre_specs:
                prompt = (
                    f"bro {scene} ke liye {genre} chahiye, {mood}, "
                    "thoda niche but not random, skip generic playlist vibes"
                )
                generated.append((prompt, language, 12, genre, None))

    return generated[:220]


def build_prompts():
    prompts = []
    limits = [5, 10, 20, 50]
    limit_idx = 0
    all_seeds = _SEEDS + _extra_jaipur_genz_audiophile_seeds()

    for text, language, base_kp, ov_genre, ov_artist in all_seeds:
        for kp_idx, (af, bpm, niche, label) in enumerate(KNOB_PROFILES):
            
            # Generate 5 Pro Mode variations for EVERY knob combination
            for mode in range(5):
                use_sec = False
                dismiss = False
                genre = None
                artist = None

                if mode == 1:
                    use_sec = True
                elif mode == 2:
                    dismiss = True
                elif mode == 3 and ov_genre:
                    genre = ov_genre
                elif mode == 4 and ov_artist:
                    artist = ov_artist
                
                # Cycle through track limits
                t_limit = limits[limit_idx % 4]
                limit_idx += 1

                prompts.append({
                    "text":         text,
                    "language":     language,
                    "artist_focus": af,
                    "bpm_focus":    bpm,
                    "nicheness":    niche,
                    "knob_label":   label,
                    "track_limit":  t_limit,
                    "use_secondary_vibe": use_sec,
                    "override_genre": genre,
                    "override_artist": artist,
                    "dismiss_detected_artist": dismiss,
                    "mode_label":   f"Mode_{mode}"
                })

    rng = random.Random(42)
    rng.shuffle(prompts)
    return prompts[:20000]

PROMPTS = build_prompts()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# LOGGER SETUP
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Main Engine Logger
logger = logging.getLogger("VibeFinder_v10k_3")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("qa_batch_v10k_3.log", encoding="utf-8")
sh = logging.StreamHandler()
fmt = logging.Formatter("%(message)s")
fh.setFormatter(fmt)
sh.setFormatter(fmt)
logger.handlers = [fh, sh]

# Dedicated Gemini Analysis Logger
gemini_logger = logging.getLogger("GeminiGrader")
gemini_logger.setLevel(logging.INFO)
g_fh = logging.FileHandler("qa_batch_gemini_analysis.log", encoding="utf-8")
g_fh.setFormatter(fmt)
gemini_logger.handlers = [g_fh, sh] # Logs to its own file AND the console so you can see it

JUNK_PATTERNS = re.compile(
    r'\b(podcast|episode|news|npr|bbc|ted talk|morning edition|'
    r'kitchen nightmares|speedrunning|let me explain|'
    r'how to make|react(?:ion)?|compilation|highlights)\b',
    re.IGNORECASE
)
NEGATION_TOKENS = {"not", "no", "don't", "dont", "nothing", "avoid",
                   "except", "without", "skip", "never"}
TITLE_NOISE = re.compile(r'\s*\(Language:[^)]+\)', re.IGNORECASE)

def _is_negated_entity(entity: str, text: str) -> bool:
    pattern = rf'\b({"|".join(re.escape(n) for n in NEGATION_TOKENS)})\s+{re.escape(entity)}\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

def _clean_title(title: str) -> str:
    return TITLE_NOISE.sub("", title).strip()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SERVICE STATUS CHECKER â€” Tests OAuth Connections & API Availability
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def check_service_status():
    """Check which music services are properly configured."""
    services = {}
    
    # Check Last.fm
    services['lastfm'] = {
        'available': bool(LASTFM_API_KEY),
        'status': 'âœ… READY' if LASTFM_API_KEY else 'âŒ NO KEY',
        'endpoints': ['/api/lastfm/proxy', '/api/services/lastfm/love', '/api/services/lastfm/scrobble']
    }
    
    # Check YouTube
    services['youtube'] = {
        'available': bool(YOUTUBE_API_KEY),
        'status': 'âœ… READY' if YOUTUBE_API_KEY else 'âŒ NO KEY',
        'features': ['OAuth playlist creation', 'Video search cache (7-day TTL)', 'Exponential backoff retry (409 errors)'],
        'endpoints': ['/api/youtube/search', '/api/youtube/playlist', '/api/youtube/auth']
    }
    
    # Check environment
    services['environment'] = {
        'gemini_available': bool(GEMINI_API_KEY),
        'metrics_auth_available': bool(METRICS_PASSPHRASE),
        'database': 'Prisma (Supabase PostgreSQL)',
        'frontend_url': os.getenv('FRONTEND_URL_PROD', 'https://vibefinderai.netlify.app')
    }
    
    services_logger.info("=" * 80)
    services_logger.info("  SERVICE AVAILABILITY STATUS")
    services_logger.info("=" * 80)
    
    for service, details in services.items():
        services_logger.info(f"\n{service.upper()}:")
        for key, value in details.items():
            if isinstance(value, list):
                services_logger.info(f"  {key}:")
                for item in value:
                    services_logger.info(f"    - {item}")
            else:
                services_logger.info(f"  {key}: {value}")
    
    return services


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# METRICS COLLECTOR â€” Tracks Test statistics & Performance
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _weighting_profile(item: dict) -> dict:
    artist_focus = int(item.get("artist_focus", 50))
    bpm_focus = int(item.get("bpm_focus", 50))
    nicheness = int(item.get("nicheness", 50))
    return {
        "artist_weight": "high" if artist_focus >= 70 else "medium" if artist_focus >= 40 else "low",
        "tempo_weight": "high" if bpm_focus >= 70 or bpm_focus <= 30 else "medium",
        "discovery_weight": "niche" if nicheness >= 70 else "mainstream" if nicheness <= 30 else "balanced",
        "knob_values": {
            "artist_focus": artist_focus,
            "bpm_focus": bpm_focus,
            "nicheness": nicheness,
        },
        "locks": {
            "artist_lock": item.get("override_artist"),
            "genre_lock": item.get("override_genre"),
            "secondary_vibe_mode": bool(item.get("use_secondary_vibe", False)),
            "dismiss_detected_artist": bool(item.get("dismiss_detected_artist", False)),
        },
    }


def _build_request_payload(item: dict) -> dict:
    return {
        "text": item["text"],
        "language": item["language"],
        "artist_focus": item["artist_focus"],
        "bpm_focus": item["bpm_focus"],
        "nicheness": item["nicheness"],
        "track_limit": item["track_limit"],
        "use_secondary_vibe": item.get("use_secondary_vibe", False),
        "override_genre": item.get("override_genre"),
        "override_artist": item.get("override_artist"),
        "dismiss_detected_artist": item.get("dismiss_detected_artist", False),
    }


def _heuristic_relevance(response_payload: dict, prompt_payload: dict) -> dict:
    tracks = response_payload.get("tracks", [])
    confidence = float(response_payload.get("confidence", 0) or 0)
    score = 0
    if tracks:
        score += 55
    score += min(35, int(confidence * 35))
    if prompt_payload.get("override_artist") and tracks:
        wanted = prompt_payload["override_artist"].lower()
        if any((t.get("artist") or "").lower() == wanted for t in tracks):
            score += 10
    score = max(0, min(100, score))
    verdict = "PASS" if score >= 70 else "PARTIAL" if score >= 45 else "FAIL"
    return {
        "verdict": verdict,
        "relevancy_score": score,
        "reason": "heuristic_fallback",
        "issues": [] if tracks else ["no_tracks"],
        "improvements": ["enable_more_sources"] if not tracks else [],
    }


async def _ensure_api_token(session: "aiohttp.ClientSession") -> str:
    async def _register_user(email: str, username: str, password: str) -> int:
        payload = {"email": email, "username": username, "password": password}
        async with session.post(f"{BACKEND_BASE_URL}/auth/register", json=payload, timeout=15) as resp:
            return resp.status

    async def _get_token(username: str, password: str) -> str:
        form_data = {"username": username, "password": password}
        async with session.post(f"{BACKEND_BASE_URL}/auth/token", data=form_data, timeout=20) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Auth failed for '{username}' ({resp.status}): {body[:300]}")
            data = await resp.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError("Auth token missing in response")
            return token

    last_error = None
    for attempt in range(1, AUTH_RETRY_ATTEMPTS + 1):
        try:
            reg_status = await _register_user(BATCH_TEST_EMAIL, BATCH_TEST_USERNAME, BATCH_TEST_PASSWORD)
            if reg_status == 201:
                main_logger.info(f"[PHASE 1.6] Batch user registered: {BATCH_TEST_USERNAME}")

            return await _get_token(BATCH_TEST_USERNAME, BATCH_TEST_PASSWORD)
        except Exception as e:
            last_error = e
            main_logger.warning(f"[PHASE 1.6] Token attempt {attempt}/{AUTH_RETRY_ATTEMPTS} failed: {e}")
            if attempt < AUTH_RETRY_ATTEMPTS:
                await asyncio.sleep(AUTH_RETRY_DELAY_SECONDS)

    # Fallback: create a fresh per-run user to avoid stale-password collisions.
    suffix = datetime.now().strftime("%H%M%S")
    fallback_username = f"{BATCH_TEST_USERNAME}_{suffix}"
    fallback_email = BATCH_TEST_EMAIL.replace("@", f"+{suffix}@")
    main_logger.info(f"[PHASE 1.6] Falling back to fresh batch user: {fallback_username}")
    reg_status = await _register_user(fallback_email, fallback_username, BATCH_TEST_PASSWORD)
    if reg_status not in (200, 201):
        raise RuntimeError(f"Fallback register failed ({reg_status}); last auth error: {last_error}")
    return await _get_token(fallback_username, BATCH_TEST_PASSWORD)


async def _wait_for_backend_health(session: "aiohttp.ClientSession", max_wait_seconds: int) -> None:
    deadline = time.time() + max_wait_seconds
    last_error = "unknown"
    while time.time() < deadline:
        try:
            async with session.get(f"{BACKEND_BASE_URL}/health", timeout=6) as resp:
                if resp.status == 200:
                    main_logger.info(f"[PHASE 1.5] Backend reachable at {BACKEND_BASE_URL}")
                    return
                last_error = f"health_status_{resp.status}"
        except Exception as e:
            last_error = str(e)
        await asyncio.sleep(2)
    raise RuntimeError(
        f"Backend not reachable within {max_wait_seconds}s at {BACKEND_BASE_URL}/health; last error: {last_error}"
    )


async def _analyze_prompt_via_api(session: "aiohttp.ClientSession", token: str, payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            async with session.post(
                f"{BACKEND_BASE_URL}/api/vibe/analyze",
                json=payload,
                headers=headers,
                timeout=60,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()

                text = await resp.text()
                if resp.status >= 500 and attempt < retries:
                    await asyncio.sleep(1.0 * attempt)
                    continue

                return {
                    "error": True,
                    "status": resp.status,
                    "detail": text[:500],
                    "dominant_vibe": "unknown",
                    "confidence": 0,
                    "secondary_vibe": None,
                    "genres": [],
                    "tracks": [],
                }
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1.0 * attempt)
                continue
            return {
                "error": True,
                "status": 599,
                "detail": f"request_error: {str(e)[:350]}",
                "dominant_vibe": "unknown",
                "confidence": 0,
                "secondary_vibe": None,
                "genres": [],
                "tracks": [],
            }

    return {
        "error": True,
        "status": 598,
        "detail": "analyze_retry_exhausted",
        "dominant_vibe": "unknown",
        "confidence": 0,
        "secondary_vibe": None,
        "genres": [],
        "tracks": [],
    }


class MetricsCollector:
    def __init__(self):
        self.total_tests = 0
        self.successful_tests = 0
        self.failed_tests = 0
        self.latencies = []
        self.vibes_detected = {}
        self.languages_tested = {}
        self.errors_by_type = {}
        self.gemini_verdicts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}
        self.relevancy_scores = []
        self.primary_confidences = []
        self.secondary_confidences = []
        self.test_results = []
        self.detail_file = f"analysis_reports/prompt_level_results_{logging_ts}.jsonl"

    def record_test(self, detail: dict, latency_ms: float):
        self.total_tests += 1
        self.latencies.append(latency_ms)

        lang = detail.get("language", "Any")
        self.languages_tested[lang] = self.languages_tested.get(lang, 0) + 1

        vibe = detail.get("engine_output", {}).get("dominant_vibe", "unknown")
        self.vibes_detected[vibe] = self.vibes_detected.get(vibe, 0) + 1

        track_count = int(detail.get("engine_output", {}).get("track_count", 0) or 0)
        if track_count > 0:
            self.successful_tests += 1
        else:
            self.failed_tests += 1

        verdict = (detail.get("relevance", {}).get("verdict") or "FAIL").upper()
        if verdict not in self.gemini_verdicts:
            verdict = "FAIL"
        self.gemini_verdicts[verdict] += 1

        score = detail.get("relevance", {}).get("relevancy_score")
        if isinstance(score, (int, float)):
            self.relevancy_scores.append(float(score))

        primary_conf = detail.get("engine_output", {}).get("confidence")
        if isinstance(primary_conf, (int, float)):
            self.primary_confidences.append(float(primary_conf))

        secondary_conf = detail.get("engine_output", {}).get("secondary_confidence")
        if isinstance(secondary_conf, (int, float)):
            self.secondary_confidences.append(float(secondary_conf))

        os.makedirs("analysis_reports", exist_ok=True)
        with open(self.detail_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(detail, ensure_ascii=False) + "\n")

        if len(self.test_results) < 200:
            self.test_results.append(detail)

    def record_error(self, error_type: str):
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1

    def get_summary(self) -> dict:
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        p95_latency = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if self.latencies else 0
        p99_latency = sorted(self.latencies)[int(len(self.latencies) * 0.99)] if self.latencies else 0
        avg_rel = (sum(self.relevancy_scores) / len(self.relevancy_scores)) if self.relevancy_scores else 0
        avg_primary_conf = (
            sum(self.primary_confidences) / len(self.primary_confidences)
            if self.primary_confidences
            else 0
        )
        avg_secondary_conf = (
            sum(self.secondary_confidences) / len(self.secondary_confidences)
            if self.secondary_confidences
            else 0
        )
        p95_primary_conf = (
            sorted(self.primary_confidences)[int(len(self.primary_confidences) * 0.95)]
            if self.primary_confidences
            else 0
        )
        p95_secondary_conf = (
            sorted(self.secondary_confidences)[int(len(self.secondary_confidences) * 0.95)]
            if self.secondary_confidences
            else 0
        )

        return {
            "total_tests": self.total_tests,
            "successful": self.successful_tests,
            "failed": self.failed_tests,
            "success_rate": (self.successful_tests / self.total_tests * 100) if self.total_tests > 0 else 0,
            "avg_relevancy_score": round(avg_rel, 2),
            "gemini_verdicts": self.gemini_verdicts,
            "confidence": {
                "avg_primary": round(avg_primary_conf, 4),
                "p95_primary": round(p95_primary_conf, 4),
                "avg_secondary": round(avg_secondary_conf, 4),
                "p95_secondary": round(p95_secondary_conf, 4),
            },
            "performance": {
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "p99_latency_ms": round(p99_latency, 2),
                "max_latency_ms": round(max(self.latencies), 2) if self.latencies else 0,
                "min_latency_ms": round(min(self.latencies), 2) if self.latencies else 0,
            },
            "top_vibes": sorted(self.vibes_detected.items(), key=lambda x: x[1], reverse=True)[:20],
            "languages_tested": sorted(self.languages_tested.items(), key=lambda x: x[1], reverse=True),
            "errors_by_type": self.errors_by_type,
            "detail_file": self.detail_file,
        }

    def save_report(self, filename: str = None):
        if not filename:
            filename = f"analysis_reports/batch_analysis_{logging_ts}.json"

        report = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_prompts": self.total_tests,
                "app_version": "v2.1 (real-feature evaluation)",
                "mode": "api_driven" if API_DRIVEN_MODE else "local",
                "backend_base_url": BACKEND_BASE_URL,
                "concurrency": ANALYSIS_CONCURRENCY,
                "inline_gemini_eval": INLINE_GEMINI_EVAL,
                "gemini_eval_all": GEMINI_EVAL_ALL,
                "gemini_postprocess_script": "analyzers/gemini_log_grader.py",
            },
            "summary": self.get_summary(),
            "recent_samples": self.test_results,
        }

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return filename


metrics = MetricsCollector()


async def run_batch():
    """Run realistic batch analysis using the full backend pipeline and Gemini grading."""
    main_logger.info("=" * 100)
    main_logger.info("  VIBEFINDER AI - REAL WORLD BATCH ANALYSIS")
    main_logger.info(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main_logger.info(f"  Prompt Pool: {len(PROMPTS)}")
    main_logger.info(f"  API_DRIVEN_MODE: {API_DRIVEN_MODE}")
    main_logger.info(f"  Concurrency: {ANALYSIS_CONCURRENCY}")
    main_logger.info("=" * 100 + "\n")

    main_logger.info("[PHASE 1] Service configuration check...")
    await check_service_status()
    main_logger.info("[PHASE 1] Service check complete\n")

    total = min(TEST_LIMIT, len(PROMPTS)) if not DEBUG_MODE else min(200, len(PROMPTS))
    main_logger.info(f"[PHASE 2] Running {total} prompts with full feature payloads...\n")

    connector = aiohttp.TCPConnector(limit=max(32, ANALYSIS_CONCURRENCY * 3)) if _AIOHTTP_AVAILABLE else None
    timeout = aiohttp.ClientTimeout(total=80) if _AIOHTTP_AVAILABLE else None

    if not _AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for API-driven realistic testing")

    start_time = time.time()
    done_count = 0
    sem = asyncio.Semaphore(ANALYSIS_CONCURRENCY)
    gem_sem = asyncio.Semaphore(GEMINI_CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        token = None
        if API_DRIVEN_MODE:
            main_logger.info("[PHASE 1.5] Waiting for backend health endpoint...")
            await _wait_for_backend_health(session, BACKEND_HEALTH_WAIT_SECONDS)
            main_logger.info("[PHASE 1.6] Requesting batch auth token...")
            token = await _ensure_api_token(session)
            main_logger.info("[PHASE 1.6] Batch auth token acquired")

        async def _run_one(idx: int, item: dict):
            async with sem:
                req_payload = _build_request_payload(item)
                w_profile = _weighting_profile(item)
                t0 = time.time()

                if API_DRIVEN_MODE:
                    response_payload = await _analyze_prompt_via_api(session, token, req_payload)
                else:
                    dominant = vibe_engine.extract_dominant_vibe(req_payload["text"].lower())
                    response_payload = {
                        "dominant_vibe": dominant,
                        "confidence": 0,
                        "secondary_vibe": None,
                        "genres": [],
                        "tracks": [],
                    }

                tracks = response_payload.get("tracks", []) or []
                engine_output = {
                    "dominant_vibe": response_payload.get("dominant_vibe", "unknown"),
                    "confidence": response_payload.get("confidence", 0),
                    "secondary_vibe": response_payload.get("secondary_vibe"),
                    "secondary_confidence": response_payload.get("secondary_confidence", 0),
                    "genres": response_payload.get("genres", []),
                    "matched_keywords": response_payload.get("matched_keywords", []),
                    "detected_artist": response_payload.get("detected_artist"),
                    "detected_song": response_payload.get("detected_song"),
                    "track_count": len(tracks),
                    "tracks": tracks,
                }

                relevance = _heuristic_relevance(response_payload, req_payload)
                if INLINE_GEMINI_EVAL and GEMINI_EVAL_ALL:
                    async with gem_sem:
                        gemini_eval = await evaluate_with_gemini(req_payload, response_payload)
                    if gemini_eval:
                        relevance = gemini_eval

                latency_ms = (time.time() - t0) * 1000
                detail = {
                    "prompt_index": idx,
                    "timestamp": datetime.now().isoformat(),
                    "prompt": req_payload["text"],
                    "language": req_payload.get("language", "Any"),
                    "request_payload": req_payload,
                    "weighting": w_profile,
                    "engine_output": engine_output,
                    "relevance": relevance,
                    "latency_ms": round(latency_ms, 3),
                }
                return detail, latency_ms

        batch_size = ANALYSIS_CONCURRENCY * 4
        main_logger.info(
            f"[PHASE 2] Dispatching prompts in batches of {batch_size} with up to {ANALYSIS_CONCURRENCY} concurrent requests"
        )
        for batch_start in range(0, total, batch_size):
            batch = PROMPTS[batch_start:batch_start + batch_size]
            tasks = [
                asyncio.create_task(_run_one(batch_start + offset + 1, item))
                for offset, item in enumerate(batch)
            ]
            pending = set(tasks)
            heartbeat_tick = 0

            while pending:
                done, pending = await asyncio.wait(pending, timeout=15, return_when=asyncio.FIRST_COMPLETED)

                if not done:
                    heartbeat_tick += 1
                    main_logger.info(
                        "[HEARTBEAT] Waiting on in-flight requests | "
                        f"processed={done_count}/{total} | pending_in_batch={len(pending)} | "
                        f"batch_start={batch_start + 1}"
                    )
                    continue

                for completed in done:
                    try:
                        detail, latency_ms = await completed
                        metrics.record_test(detail, latency_ms)
                    except Exception as e:
                        metrics.record_error(type(e).__name__)
                        main_logger.error(f"Prompt failed: {e}")

                    done_count += 1
                    if done_count % 100 == 0 or done_count == total:
                        main_logger.info(
                            f"[PROGRESS] {done_count}/{total} prompts processed ({(done_count/total)*100:.1f}%)"
                        )

    duration = time.time() - start_time
    summary = metrics.get_summary()
    report_file = metrics.save_report()

    main_logger.info("\n" + "=" * 100)
    main_logger.info("  TEST SUITE SUMMARY")
    main_logger.info("=" * 100)
    main_logger.info(f"Total Tests Run      : {summary['total_tests']}")
    main_logger.info(f"Successful           : {summary['successful']} ({summary['success_rate']:.1f}%)")
    main_logger.info(f"Failed               : {summary['failed']}")
    main_logger.info(f"Average Relevancy    : {summary['avg_relevancy_score']}")
    main_logger.info(f"Gemini Verdicts      : {summary['gemini_verdicts']}")
    main_logger.info(f"Avg Primary Conf     : {summary['confidence']['avg_primary']}")
    main_logger.info(f"P95 Primary Conf     : {summary['confidence']['p95_primary']}")
    main_logger.info(f"Avg Secondary Conf   : {summary['confidence']['avg_secondary']}")
    main_logger.info(f"P95 Secondary Conf   : {summary['confidence']['p95_secondary']}")
    main_logger.info(f"Average Latency      : {summary['performance']['avg_latency_ms']}ms")
    main_logger.info(f"P95 Latency          : {summary['performance']['p95_latency_ms']}ms")
    main_logger.info(f"P99 Latency          : {summary['performance']['p99_latency_ms']}ms")
    main_logger.info(f"Detail JSONL         : {summary['detail_file']}")
    main_logger.info(f"Summary JSON         : {report_file}")
    main_logger.info(f"Total Duration       : {duration:.1f}s ({duration/60:.1f} min)")
    main_logger.info("=" * 100 + "\n")

    metrics_logger.info(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    """
    Main entry point for batch test execution.
    
    Usage:
        python testing/batch_tester_v10k_2.py

    Outputs:
        - qa_batch_<timestamp>.log - Main test results
        - qa_batch_services_<timestamp>.log - Service status
        - qa_batch_metrics_<timestamp>.log - Detailed metrics
        - qa_batch_gemini_<timestamp>.log - AI grading results
        - analysis_reports/batch_analysis_<timestamp>.json - Comprehensive report
    """
    try:
        main_logger.info("\nStarting batch test suite execution...\n")
        asyncio.run(run_batch())
        main_logger.info("Batch test completed successfully!")
        main_logger.info("Check analysis_reports/ folder for detailed reports")
    except KeyboardInterrupt:
        main_logger.warning("\nTest interrupted by user")
    except Exception as e:
        main_logger.error(f"\nBatch test failed with error: {e}", exc_info=True)

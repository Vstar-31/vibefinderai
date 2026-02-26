import re

# ---------------------------------------------------------
# THE ULTIMATE PROFOUND VIBE MAP
# ---------------------------------------------------------
# A massive multidimensional map of vibes, contexts, genres,
# and hundreds of mapped artists across the spectrum.
# ---------------------------------------------------------
VIBE_MAP = {
    "hype": {
        "keywords": ["aggressive", "pumped", "energy", "crazy", "rage", "lit", "fast", "powerful", "savage"],
        "context": ["gym", "workout", "lifting", "moshpit", "club", "pregame", "stadium"],
        "artists": ["travis scott", "21 savage", "playboi carti", "drake", "kendrick lamar", "skrillex", "asap rocky", "lil uzi vert", "yeat", "scarlxrd", "denzel curry"],
        "bpm": "130-175",
        "genres": ["Trap", "Phonk", "Hardstyle", "Rage Rap", "EDM"]
    },
    "calm": {
        "keywords": ["peaceful", "soothing", "relaxing", "tranquil", "serene", "quiet", "soft", "gentle", "light"],
        "context": ["yoga", "meditation", "spa", "sleeping", "reading", "nature", "morning"],
        "artists": ["norah jones", "enya", "sade", "jack johnson", "bon iver", "iron & wine", "sigur ros", "corinne bailey rae", "yiruma"],
        "bpm": "60-85",
        "genres": ["Ambient", "Acoustic", "Folk", "Easy Listening", "New Age"]
    },
    "intense": {
        "keywords": ["heavy", "metal", "brutal", "dark", "chaotic", "screaming", "loud", "distorted", "crushing"],
        "context": ["venting", "heavy lifting", "moshpit", "adrenaline", "chaos"],
        "artists": ["metallica", "slipknot", "gojira", "lorna shore", "deftones", "meshuggah", "bring me the horizon", "knocked loose", "slayer", "bad omens"],
        "bpm": "140-200",
        "genres": ["Deathcore", "Nu-Metal", "Thrash", "Hardcore", "Progressive Metal"]
    },
    "chill": {
        "keywords": ["mellow", "smooth", "vibey", "laid back", "floating", "cool", "drifting"],
        "context": ["smoke", "late night", "driving", "beach", "sunset", "lounge", "hanging out"],
        "artists": ["sza", "frank ocean", "mac miller", "tame impala", "khruangbin", "kali uchis", "thundercat", "erykah badu", "steve lacy", "childish gambino"],
        "bpm": "75-100",
        "genres": ["Neo-Soul", "Indie R&B", "Chillwave", "Lo-Fi Hip Hop"]
    },
    "focus": {
        "keywords": ["concentrate", "study", "work", "productive", "zen", "minimal", "deep", "instrumental"],
        "context": ["library", "coding", "reading", "office", "dark academia", "minimalism"],
        "artists": ["hans zimmer", "ludovico einaudi", "max richter", "aphex twin", "brian eno", "nils frahm", "lofi girl", "j dilla"],
        "bpm": "60-90",
        "genres": ["Modern Classical", "Ambient", "Deep House", "Instrumental Hip Hop"]
    },
    "euphoric": {
        "keywords": ["uplifting", "heavenly", "transcend", "magic", "limitless", "freedom", "glowing", "bliss"],
        "context": ["festival", "sunrise", "dreaming", "space", "flying", "high"],
        "artists": ["fred again", "odesza", "rufus du sol", "m83", "porter robinson", "flume", "bicep", "disclosure", "avicii"],
        "bpm": "120-145",
        "genres": ["Progressive House", "Future Bass", "Dream Pop", "Synthpop"]
    },
    "soulful": {
        "keywords": ["emotional", "deep", "bluesy", "jazz", "passionate", "vocal", "warm", "heart"],
        "context": ["dinner", "wine night", "rainy day", "romantic", "reflective"],
        "artists": ["miles davis", "john coltrane", "amy winehouse", "billie holiday", "leon bridges", "marvin gaye", "al green", "nina simone"],
        "bpm": "50-110",
        "genres": ["Jazz", "Blues", "Classic Soul", "Gospel"]
    },
    "retro": {
        "keywords": ["nostalgic", "vintage", "80s", "90s", "neon", "classic", "analog", "old school"],
        "context": ["arcade", "thrifting", "vinyl", "cassette", "retro gaming"],
        "artists": ["daft punk", "the weeknd", "kavinsky", "fleetwood mac", "queen", "new order", "depeche mode", "michael jackson"],
        "bpm": "100-128",
        "genres": ["Synthwave", "80s Pop", "New Wave", "Disco", "Boom Bap"]
    },
    "dreamy": {
        "keywords": ["surreal", "hazy", "ethereal", "shoegaze", "cloudy", "faded", "misty"],
        "context": ["daydreaming", "stargazing", "long walks", "escaping"],
        "artists": ["slowdive", "beach house", "cocteau twins", "mazzy star", "the xx", "men i trust", "alvvays"],
        "bpm": "70-110",
        "genres": ["Shoegaze", "Dream Pop", "Indie Rock", "Psych Rock"]
    }
}

# Scoring Weights
WEIGHT_ARTIST = 2.5   # Artists are the strongest vibe indicators
WEIGHT_KEYWORD = 1.5
WEIGHT_CONTEXT = 1.0

def analyze_vibe_algorithm(text: str) -> dict:
    """
    Advanced Weighted Vibe Analysis Engine.
    Maps input text against a massive dictionary of keywords, artists, and contexts.
    """
    clean_text = text.lower()
    # Find all words and multi-word artist names
    words = re.findall(r'\b\w+(?:\s\w+)*\b', clean_text)
    
    scores = {vibe: 0.0 for vibe in VIBE_MAP}
    matched_tokens = []

    for vibe, data in VIBE_MAP.items():
        # Check Artist Matches (Weighted Highest)
        for artist in data["artists"]:
            if artist in clean_text:
                scores[vibe] += WEIGHT_ARTIST
                matched_tokens.append(artist)
        
        # Check Keyword Matches
        for kw in data["keywords"]:
            if kw in words:
                scores[vibe] += WEIGHT_KEYWORD
                matched_tokens.append(kw)
                
        # Check Context Matches
        for ctx in data["context"]:
            if ctx in words:
                scores[vibe] += WEIGHT_CONTEXT
                matched_tokens.append(ctx)
                
    total_score = sum(scores.values())
    
    # Neutral fallback
    if total_score == 0:
        return {
            "dominant_vibe": "neutral",
            "confidence": 0.0,
            "bpm_range": "90-120",
            "genres": ["Lo-Fi", "Pop", "Ambient"],
            "matched_keywords": []
        }

    dominant_vibe = max(scores, key=scores.get)
    confidence = round(scores[dominant_vibe] / total_score, 2)
    
    # Get metadata for the result
    meta = VIBE_MAP[dominant_vibe]
    
    return {
        "dominant_vibe": dominant_vibe,
        "confidence": confidence,
        "bpm_range": meta["bpm"],
        "genres": meta["genres"],
        "matched_keywords": list(set(matched_tokens))
    }
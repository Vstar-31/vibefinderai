import re

# ---------------------------------------------------------
# THE PROFOUND VIBE DICTIONARY
# ---------------------------------------------------------
# Mapping vibes to weighted keywords, atmospheric contexts, 
# genres, and iconic artists.
# ---------------------------------------------------------
VIBE_MAP = {
    "hype": {
        "keywords": ["aggressive", "pumped", "energy", "crazy", "rage", "hardcore", "extreme", "lit"],
        "context": ["gym", "workout", "lifting", "running", "pregame", "moshpit", "club"],
        "artists": ["travis scott", "21 savage", "playboi carti", "drake", "kendrick lamar", "skrillex"],
        "bpm": "130-170",
        "genres": ["Trap", "Phonk", "Hardstyle", "Rage Rap"]
    },
    "chill": {
        "keywords": ["relax", "vibes", "calm", "smooth", "mellow", "peaceful", "quiet", "floating"],
        "context": ["smoke", "late night", "driving", "rainy", "beach", "sunset", "lounge"],
        "artists": ["sza", "frank ocean", "tame impala", "mac miller", "kali uchis", "khruangbin"],
        "bpm": "70-95",
        "genres": ["Lo-Fi", "Neo-Soul", "Indie R&B", "Chillwave"]
    },
    "sad": {
        "keywords": ["heartbreak", "melancholy", "depressed", "lonely", "tears", "pain", "empty", "shattered"],
        "context": ["night", "crying", "breakup", "staring at ceiling", "winter", "dark"],
        "artists": ["joji", "phoebe bridgers", "bon iver", "mitski", "lana del rey", "the weeknd"],
        "bpm": "60-85",
        "genres": ["Acoustic", "Ethereal", "Sad Pop", "Slowcore"]
    },
    "happy": {
        "keywords": ["fun", "smile", "sunny", "good", "upbeat", "bright", "joy", "glowing"],
        "context": ["party", "summer", "dance", "weekend", "celebration", "roadtrip", "morning"],
        "artists": ["pharrell", "dua lipa", "katy perry", "harry styles", "bruno mars"],
        "bpm": "110-130",
        "genres": ["Pop", "Disco", "Funk", "Dance Pop"]
    },
    "euphoric": {
        "keywords": ["transcend", "spiritual", "uplifting", "heavenly", "magic", "limitless", "freedom"],
        "context": ["festival", "sunrise", "dreaming", "space", "flying", "high"],
        "artists": ["fred again", "odzesza", "bicep", "rufus du sol", "m83", "porter robinson"],
        "bpm": "120-140",
        "genres": ["Melodic Techno", "Progressive House", "Dream Pop"]
    },
    "focus": {
        "keywords": ["concentrate", "study", "work", "deep", "productive", "zen", "minimal"],
        "context": ["library", "coding", "reading", "office", "dark academia", "minimalism"],
        "artists": ["hans jimmer", "ludovico einaudi", "brian eno", "max richter", "aphex twin"],
        "bpm": "60-90",
        "genres": ["Ambient", "Modern Classical", "Deep Focus", "Dark Academia"]
    },
    "retro": {
        "keywords": ["nostalgic", "vintage", "old school", "classic", "neon", "80s", "90s", "analog"],
        "context": ["arcade", "stranger things", "thrifting", "vinyl", "cassette"],
        "artists": ["the weeknd", "kavinsky", "daft punk", " Fleetwood mac", "queen"],
        "bpm": "100-125",
        "genres": ["Synthwave", "City Pop", "80s Rock", "Boom Bap"]
    }
}

# Scoring Weights
WEIGHT_ARTIST = 2.0
WEIGHT_KEYWORD = 1.5
WEIGHT_CONTEXT = 1.0

def analyze_vibe_algorithm(text: str) -> dict:
    """
    The Profound Vibe Algorithm. 
    Performs weighted token matching against a multi-dimensional vibe map.
    """
    # Normalize and tokenize input
    clean_text = text.lower()
    # Use regex to find whole words and specific phrases (like artist names)
    words = re.findall(r'\b\w+(?:\s\w+)*\b', clean_text)
    
    scores = {vibe: 0.0 for vibe in VIBE_MAP}
    matched_keywords = []

    for vibe, data in VIBE_MAP.items():
        # Check Artists (Highest Weight)
        for artist in data["artists"]:
            if artist in clean_text:
                scores[vibe] += WEIGHT_ARTIST
                matched_keywords.append(artist)
        
        # Check Mood Keywords
        for kw in data["keywords"]:
            if kw in words:
                scores[vibe] += WEIGHT_KEYWORD
                matched_keywords.append(kw)
                
        # Check Context/Genre
        for ctx in data["context"]:
            if ctx in words:
                scores[vibe] += WEIGHT_CONTEXT
                matched_keywords.append(ctx)
                
    total_score = sum(scores.values())
    
    # Fallback for neutral/unmatched input
    if total_score == 0:
        return {
            "dominant_vibe": "neutral",
            "confidence": 0.0,
            "bpm_range": "90-110",
            "genres": ["Universal Pop", "Ambient"],
            "matched_keywords": []
        }

    # Determine dominant vibe
    dominant_vibe = max(scores, key=scores.get)
    confidence = round(scores[dominant_vibe] / total_score, 2)
    
    # Extract meta data
    result = VIBE_MAP[dominant_vibe]
    
    return {
        "dominant_vibe": dominant_vibe,
        "confidence": confidence,
        "bpm_range": result["bpm"],
        "genres": result["genres"],
        "matched_keywords": list(set(matched_keywords))
    }
import re
from collections import defaultdict

# =============================================================================
#  VIBEFINDER AI — ACOUSTIC INTELLIGENCE ENGINE v4.1
#  "THE OMNISCIENT GRAND EXPANSION" EDITION
# =============================================================================
#  Architecture upgrades:
#   1. Massive Slang Dictionary — Captures Gen Z/Alpha, TikTok eras, and old-school slang.
#   2. Multi-word phrase detection — catches "main character energy", "in my bag".
#   3. Negation handling — "not happy", "don't want sad", "no chill" flip scores.
#   4. Emoji→mood mapping — 🔥😭💀🥺 all carry signal.
#   5. Valence–Arousal cross-scoring — vibes that share emotional space bleed confidence.
#   6. 18 Total Vibe Categories including new 'tropical', 'industrial', and 'desi'.
#   7. Global Artist Index — 400+ artists mapped across the spectrum.
#   8. Calibrated Confidence Math — filters out bleed noise for higher certainty.
# =============================================================================


# ─── SYNONYM / ALIAS TABLE ────────────────────────────────────────────────────
# Maps any user word or phrase to one or more canonical tokens that appear in
# VIBE_MAP keyword/context lists. Applied BEFORE scoring.
SYNONYMS: dict[str, list[str]] = {
    # ── energy / hype / aura adjacent ─────────────────────────────────────────
    "fire": ["hype", "energy"],
    "bussin": ["hype", "energy"],
    "slaps": ["hype", "energy"],
    "banger": ["hype", "energy"],
    "bop": ["hype", "energy"],
    "hits different": ["hype", "energy"],
    "slapper": ["hype"],
    "hard": ["hype", "intense"],
    "go crazy": ["hype", "intense"],
    "send it": ["hype"],
    "ripping": ["hype", "intense"],
    "cranked up": ["hype"],
    "cranked": ["hype"],
    "full send": ["hype"],
    "going off": ["hype", "party"],
    "it goes hard": ["hype"],
    "no cap": ["hype"],
    "goat": ["hype"],
    "goated": ["hype"],
    "ate": ["hype", "euphoric"],
    "ate no crumbs": ["hype", "euphoric"],
    "ate and left no crumbs": ["hype", "euphoric"],
    "slay": ["hype", "euphoric"],
    "slaying": ["hype", "euphoric"],
    "drip": ["hype"],
    "drippy": ["hype"],
    "swag": ["hype"],
    "swagged out": ["hype"],
    "nasty": ["hype", "intense"],
    "filthy": ["hype", "intense"],
    "disgusting": ["hype"],
    "stupid hard": ["hype"],
    "unhinged": ["hype", "intense", "party"],
    "chaotic": ["hype", "intense"],
    "feral": ["hype", "intense", "party"],
    "elite": ["hype"],
    "valid": ["hype", "chill"],
    "immaculate": ["hype", "euphoric"],
    "nutty": ["hype"],
    "wild": ["hype", "intense"],
    "absolutely cooking": ["hype"],
    "cooked": ["dark", "intense"],
    "gas": ["hype"],
    "rizz": ["hype", "chill"],
    "aura": ["cinematic", "hype"],
    "locked in": ["focus"],
    "in my bag": ["focus", "hype"],
    "in the zone": ["focus"],
    "grindset": ["focus"],
    "grinding": ["focus"],
    "flow state": ["focus"],
    "no thoughts head empty": ["chill", "focus"],

    # ── calm / peace adjacent ───────────────────────────────────────────────
    "cozy": ["calm", "chill"],
    "comfy": ["calm", "chill"],
    "cottagecore": ["calm", "dreamy"],
    "hygge": ["calm", "chill"],
    "wholesome": ["calm"],
    "healing era": ["calm", "soulful"],
    "in my healing era": ["calm", "soulful"],
    "healing": ["calm", "soulful"],
    "soft life": ["calm", "chill"],
    "slow living": ["calm"],
    "barefoot": ["calm"],
    "unplugged": ["calm", "focus"],
    "quiet hours": ["calm"],
    "golden hour": ["calm", "euphoric"],
    "warm": ["calm", "soulful"],
    "mellow": ["chill", "calm"],
    "lowkey": ["chill", "calm"],
    "touch grass": ["calm"],
    "breathe": ["calm"],
    "zoned out": ["chill", "dreamy"],
    "out of it": ["chill", "dreamy"],
    "baked": ["chill", "dreamy"],
    "stoned": ["chill", "dreamy"],
    "fried": ["chill"],
    "vibing": ["chill"],
    "chilling": ["chill"],
    "existing": ["chill", "calm"],
    "just existing": ["chill", "calm"],
    "pure": ["calm", "euphoric"],

    # ── sad / heartbreak adjacent ────────────────────────────────────────────
    "in my feelings": ["heartbreak", "soulful"],
    "down bad": ["heartbreak", "dark"],
    "tweaking": ["heartbreak", "intense"],
    "not okay": ["heartbreak"],
    "crying rn": ["heartbreak"],
    "big cry": ["heartbreak"],
    "sobbing": ["heartbreak"],
    "devastated": ["heartbreak"],
    "wreck": ["heartbreak"],
    "broken": ["heartbreak", "intense"],
    "shattered": ["heartbreak"],
    "gutted": ["heartbreak"],
    "heart ripped out": ["heartbreak"],
    "it's giving heartbreak": ["heartbreak"],
    "talking stage ruined me": ["heartbreak"],
    "left on read": ["heartbreak"],
    "ghosted": ["heartbreak"],
    "situationship": ["heartbreak"],
    "on sight": ["heartbreak", "intense"],
    "down so bad": ["heartbreak", "dark"],
    "crying in the club": ["heartbreak", "party"],
    "longing": ["heartbreak", "dreamy"],
    "pining": ["heartbreak", "dreamy"],
    "aching": ["heartbreak", "soulful"],
    "feels": ["heartbreak", "soulful"],
    "big feels": ["heartbreak", "soulful"],
    "emotional damage": ["heartbreak"],
    "it's not giving": ["heartbreak"],
    "rent free": ["heartbreak", "dreamy"],

    # ── dreamy / ethereal adjacent ───────────────────────────────────────────
    "ethereal": ["dreamy", "euphoric"],
    "celestial": ["dreamy", "euphoric"],
    "liminal": ["dreamy", "dark"],
    "liminal space": ["dreamy", "dark"],
    "otherworldly": ["dreamy"],
    "hazy": ["dreamy", "chill"],
    "gauzy": ["dreamy"],
    "cottagecore vibes": ["dreamy", "calm"],
    "stargazing": ["dreamy", "calm"],
    "cloud nine": ["dreamy", "euphoric"],
    "head in the clouds": ["dreamy"],
    "dissociating": ["dreamy", "dark"],
    "somewhere else": ["dreamy"],
    "out of body": ["dreamy", "dark"],
    "astral": ["dreamy", "euphoric"],
    "mystical": ["dreamy", "dark"],
    "main character": ["dreamy", "cinematic"],
    "main character energy": ["dreamy", "cinematic"],
    "main character moment": ["dreamy", "cinematic"],
    "it's giving main character": ["cinematic", "dreamy"],
    "manifesting": ["euphoric", "dreamy"],
    "delulu": ["dreamy", "heartbreak"],

    # ── euphoric / party adjacent ────────────────────────────────────────────
    "brat": ["party", "hyperpop"],
    "brat summer": ["party", "hyperpop"],
    "it's giving brat": ["party", "hyperpop"],
    "feral summer": ["party"],
    "unhinged summer": ["party"],
    "core memory": ["euphoric", "retro"],
    "living my best life": ["euphoric", "party"],
    "peak": ["euphoric"],
    "peak experience": ["euphoric"],
    "serotonin": ["euphoric", "calm"],
    "dopamine": ["euphoric", "hype"],
    "vibes only": ["euphoric", "party"],
    "good vibes only": ["euphoric"],
    "giving life": ["euphoric"],
    "giving me life": ["euphoric", "party"],
    "transcendent": ["euphoric", "cinematic"],
    "floating": ["euphoric", "dreamy"],
    "heaven": ["euphoric", "calm"],
    "heavenly": ["euphoric", "calm"],
    "bliss": ["euphoric", "calm"],
    "freeing": ["euphoric"],
    "alive": ["euphoric"],
    "turning up": ["party", "hype"],
    "turnt": ["party", "hype"],
    "getting loose": ["party"],
    "rager": ["party", "hype"],
    "going out": ["party"],
    "dancing": ["party", "euphoric"],
    "pregame": ["party", "hype"],
    "club ready": ["party"],
    "festival": ["euphoric", "party"],
    "festival season": ["euphoric", "party"],
    "rave": ["euphoric", "party"],

    # ── dark / intense adjacent ──────────────────────────────────────────────
    "dark era": ["dark", "intense"],
    "villain era": ["dark", "intense"],
    "in my villain era": ["dark", "intense"],
    "goblin mode": ["dark", "chill"],
    "doomer": ["dark"],
    "doomscrolling": ["dark"],
    "bleak": ["dark", "heartbreak"],
    "cursed": ["dark"],
    "unsettling": ["dark"],
    "eerie": ["dark", "dreamy"],
    "ominous": ["dark", "cinematic"],
    "foreboding": ["dark", "cinematic"],
    "post-apocalyptic": ["dark", "cinematic"],
    "dystopian": ["dark", "cinematic"],
    "nihilist": ["dark"],
    "edge": ["dark", "intense"],
    "edgy": ["dark", "intense"],
    "goth": ["dark"],
    "gothic": ["dark"],
    "emo": ["dark", "intense"],
    "emo era": ["dark", "intense"],
    "black parade energy": ["dark", "intense"],
    "screaming into void": ["intense", "dark"],
    "destructive": ["intense", "dark"],
    "going feral": ["intense", "dark"],
    "unraveling": ["intense", "heartbreak"],
    "void": ["dark", "dreamy"],

    # ── cinematic / epic adjacent ────────────────────────────────────────────
    "epic": ["cinematic"],
    "legendary": ["cinematic", "hype"],
    "saga": ["cinematic"],
    "lore": ["cinematic"],
    "world building": ["cinematic"],
    "training montage": ["cinematic", "hype"],
    "final boss": ["cinematic", "intense"],
    "boss battle": ["cinematic", "intense"],
    "hero": ["cinematic", "hype"],
    "hero moment": ["cinematic", "hype"],
    "character development": ["cinematic"],
    "plot twist": ["cinematic"],
    "orchestral": ["cinematic"],
    "grand": ["cinematic", "euphoric"],
    "sweeping": ["cinematic"],
    "majestic": ["cinematic"],
    "adventurous": ["cinematic", "euphoric"],

    # ── focus / study adjacent ───────────────────────────────────────────────
    "dark academia": ["focus", "dreamy"],
    "dead poets society vibes": ["focus", "dreamy"],
    "reading week": ["focus", "calm"],
    "coding session": ["focus"],
    "hyperfocus": ["focus"],
    "productive": ["focus"],
    "deep work": ["focus"],
    "clean studying": ["focus", "calm"],
    "no distractions": ["focus"],
    "brain on": ["focus"],

    # ── soulful / jazz / noir adjacent ──────────────────────────────────────────────
    "jazzy": ["soulful"],
    "bluesy": ["soulful"],
    "gospel": ["soulful"],
    "righteous": ["soulful"],
    "church": ["soulful", "calm"],
    "rnb": ["soulful", "chill"],
    "r&b": ["soulful", "chill"],
    "neo soul": ["soulful", "chill"],
    "old soul": ["soulful", "retro"],
    "timeless": ["soulful", "retro"],
    "golden era": ["soulful", "retro"],
    "classic": ["soulful", "retro"],
    "real music": ["soulful"],
    "rainy day playlist": ["heartbreak", "chill"],
    "candlelit": ["soulful", "calm"],
    "dinner party": ["soulful", "calm"],
    "wine drunk": ["soulful", "chill"],
    "whiskey sour": ["soulful", "chill"],
    "jazz club": ["soulful", "cinematic"],
    "dark jazz": ["soulful", "dark", "cinematic"],
    "noir": ["cinematic", "dark", "soulful"],

    # ── country / folk adjacent ──────────────────────────────────────────────
    "country": ["country"],
    "folk": ["country"],
    "roots": ["country", "soulful"],
    "americana": ["country"],
    "western": ["country"],
    "boots": ["country"],
    "honky tonk": ["country"],
    "cowboy": ["country"],
    "cowgirl": ["country"],
    "campfire": ["country", "calm"],
    "porch": ["country", "calm"],
    "rural": ["country"],
    "small town": ["country"],
    "heartland": ["country"],
    "twang": ["country"],
    "banjo": ["country"],
    "fiddle": ["country", "soulful"],
    "acoustic guitar": ["country", "calm", "focus"],
    "road trip": ["country", "retro"],
    "tail gate": ["country", "party"],
    "tailgate": ["country", "party"],
    "barn": ["country"],
    "summertime sadness": ["heartbreak", "country"],
    "sad country": ["heartbreak", "country"],
    
    # ── desi / bollywood adjacent ────────────────────────────────────────────
    "desi swag": ["desi", "party", "hype"],
    "bollywood vibes": ["desi"],
    "brown boy": ["desi", "hype"],
    "brown girl": ["desi"],
    "shaadi vibes": ["desi", "party"],
    "sangeet": ["desi", "party"],
    "dhol beats": ["desi", "party"],

    # ── retro / nostalgic adjacent ────────────────────────────────────────────
    "nostalgia": ["retro"],
    "throwback": ["retro"],
    "vintage": ["retro"],
    "old school": ["retro"],
    "y2k": ["retro", "hyperpop"],
    "2000s": ["retro"],
    "90s": ["retro"],
    "80s": ["retro"],
    "70s": ["retro", "soulful"],
    "cassette": ["retro"],
    "vinyl": ["retro", "soulful"],
    "record store": ["retro", "soulful"],
    "fm radio": ["retro"],
    "dial-up": ["retro"],
    "summer of 69": ["retro", "euphoric"],
    "vaporwave": ["retro", "dreamy"],
    "city pop": ["retro", "chill"],
    "city pop vibes": ["retro", "chill"],
    "japanese city pop": ["retro", "chill"],
    "driving at night": ["retro", "chill", "dark"],
    "synthwave": ["retro", "dark"],
    "outrun": ["retro", "hype"],

    # ── hyperpop / internet adjacent ─────────────────────────────────────────
    "hyperpop": ["hyperpop"],
    "glitchy": ["hyperpop", "dark"],
    "distorted": ["hyperpop", "intense"],
    "maximalist": ["hyperpop", "hype"],
    "chaotic good": ["hyperpop", "party"],
    "terminally online": ["hyperpop"],
    "internet girl": ["hyperpop", "dreamy"],
    "digicore": ["hyperpop"],
    "pc music": ["hyperpop"],
    "hypno pop": ["hyperpop"],
    "bubblegum bass": ["hyperpop"],
    "scenecore": ["hyperpop", "intense"],
    "skramz": ["intense", "hyperpop"],
    "slugga": ["hype", "hyperpop"],
    "nightcore": ["hyperpop", "hype"],
    "digital girl": ["hyperpop", "dreamy"],
    "pluggnb": ["chill", "hyperpop"],
    "rage beat": ["hype", "intense"],

    # ── emoji signals ────────────────────────────────────────────────────────
    "🔥": ["hype", "energy"],
    "💀": ["hype", "intense"],
    "😤": ["hype", "intense"],
    "🥶": ["hype"],
    "😈": ["dark", "intense"],
    "👹": ["dark", "intense"],
    "🌊": ["calm", "chill"],
    "🌿": ["calm"],
    "🕯️": ["soulful", "calm"],
    "😭": ["heartbreak"],
    "💔": ["heartbreak"],
    "🫀": ["heartbreak", "soulful"],
    "🥺": ["heartbreak", "chill"],
    "😮‍💨": ["chill", "calm"],
    "✨": ["euphoric", "dreamy"],
    "🌟": ["euphoric"],
    "🚀": ["euphoric", "hype"],
    "🌈": ["euphoric", "hyperpop"],
    "🎸": ["intense", "retro"],
    "🎷": ["soulful", "cinematic"],
    "🎺": ["soulful", "hype"],
    "🎻": ["country", "cinematic", "soulful"],
    "🌙": ["dark", "dreamy"],
    "🌌": ["dreamy", "cinematic"],
    "🌅": ["calm", "euphoric"],
    "🎪": ["party", "hyperpop"],
    "💿": ["retro", "hyperpop"],
    "📻": ["retro"],
    "🍂": ["calm", "heartbreak"],
    "🌧️": ["heartbreak", "chill"],
    "⛈️": ["intense", "dark"],
    "🤠": ["country"],
    "🏕️": ["country", "calm"],
    "🐴": ["country"],
}

# ─── NEGATION WORDS ───────────────────────────────────────────────────────────
NEGATION_TOKENS = {
    "not", "no", "never", "dont", "don't", "doesnt", "doesn't", "without",
    "zero", "none", "nothing", "neither", "nor", "hate", "avoid", "skip",
    "anti", "opposite", "except", "less", "minus", "forget",
}

# ─── VALENCE–AROUSAL BLEED TABLE ─────────────────────────────────────────────
BLEED: dict[str, dict[str, float]] = {
    "hype":       {"intense": 0.25, "party": 0.20, "euphoric": 0.15},
    "calm":       {"focus": 0.20, "chill": 0.25, "dreamy": 0.10},
    "intense":    {"hype": 0.20, "dark": 0.25},
    "chill":      {"calm": 0.20, "dreamy": 0.15, "heartbreak": 0.10},
    "focus":      {"calm": 0.15, "cinematic": 0.10},
    "euphoric":   {"party": 0.25, "hype": 0.15, "dreamy": 0.10},
    "soulful":    {"heartbreak": 0.20, "chill": 0.15, "calm": 0.10},
    "retro":      {"soulful": 0.15, "chill": 0.10, "dreamy": 0.10},
    "dreamy":     {"chill": 0.15, "heartbreak": 0.10, "dark": 0.10},
    "cinematic":  {"intense": 0.15, "euphoric": 0.15, "dreamy": 0.10},
    "dark":       {"intense": 0.20, "dreamy": 0.10},
    "heartbreak": {"soulful": 0.15, "dark": 0.10, "chill": 0.10},
    "hyperpop":   {"hype": 0.20, "party": 0.20, "euphoric": 0.10},
    "party":      {"hype": 0.25, "euphoric": 0.20, "hyperpop": 0.10},
    "country":    {"calm": 0.15, "soulful": 0.15, "retro": 0.10},
    "tropical":   {"party": 0.25, "chill": 0.15},
    "industrial": {"dark": 0.25, "intense": 0.20},
    "desi":       {"party": 0.25, "hype": 0.15, "soulful": 0.10},
}


# =============================================================================
#  THE GRAND VIBE MAP — V4.1 FULL DATASET
# =============================================================================
VIBE_MAP: dict[str, dict] = {

    "hype": {
        "keywords": [
            "aggressive", "pumped", "energy", "crazy", "rage", "lit", "fast",
            "savage", "goated", "demon", "beast", "turnt", "cranked", "hype",
            "stoked", "gas", "hard", "nasty", "filthy", "stupid hard", "elite",
            "bussin", "slaps", "banger", "fire", "drip", "ripping", "full send",
            "unstoppable", "invincible", "dominant", "crushing it", "snatched",
            "going off", "unhinged", "feral", "unreal", "absolutely wild",
            "going ham", "no days off", "grind", "warzone", "battle mode",
            "pr", "personal record", "max out", "one rep max", "swole",
            "jacked", "gains", "deadlift", "squat", "bench press", "barbell",
            "powerlifting", "bodybuilding", "marathon", "sprinting", "training",
            "pre-workout", "preworkout", "creatine",
            "moshpit", "stadium", "crowd surf", "wall of death", "headbang",
            "floor filler", "drop", "build up", "breakdown", "808",
        ],
        "phrases": [
            "go crazy", "send it", "goes hard", "it goes hard", "hits different",
            "no cap", "in my bag", "eating no crumbs", "ate and left no crumbs",
            "built different", "not built for this", "different breed",
            "on a different level", "on god", "not human", "body is ready",
        ],
        "context": [
            "gym", "workout", "lifting", "moshpit", "club", "pregame", "stadium",
            "party", "winning", "championship", "heist", "sparring", "boxing",
            "wrestling", "fighting", "competition", "tournament", "race",
            "athlete", "sports", "game day", "playoffs", "finals",
        ],
        "artists": [
            "travis scott", "21 savage", "playboi carti", "drake", "kendrick lamar",
            "asap rocky", "lil uzi vert", "yeat", "scarlxrd", "denzel curry",
            "lil baby", "gunna", "future", "baby keem", "ken carson",
            "destroy lonely", "sheck wes", "pop smoke", "fivio foreign",
            "central cee", "comethazine", "zillakami", "city morgue",
            "rowdy rebel", "king von", "polo g", "nba youngboy", "moneybagg yo",
            "42 dugg", "rod wave", "jackboy", "lil durk", "fredo bang",
            "trippie redd", "ski mask the slump god", "xxxtentacion",
            "juice wrld", "iann dior", "poorstacy", "jme", "stormzy",
            "dave", "digga d", "headie one", "m1llionz", "potter payper",
            "unknown t", "tion wayne", "russ millions", "arrdee", "yungblud",
            "slowthai", "aitch", "dutchavelli", "abra cadabra",
            "skrillex", "excision", "subtronics", "slander", "rezz", "illenium",
            "seven lions", "nghtmre", "griz", "liquid stranger", "1788-l",
            "svdden death", "meduza", "dom dolla", "fisher",
            "isoxo", "knock2", "rl grime",
            "scarlxrd", "ghostemane", "", "$uicideboy$", "pouya",
            "night lovell", "trevor daniel",
        ],
        "bpm": "130-175",
        "genres": ["Trap", "Phonk", "Hardstyle", "Rage Rap", "EDM", "UK Drill", "Bass Music"],
    },

    "calm": {
        "keywords": [
            "peaceful", "soothing", "relaxing", "tranquil", "serene", "quiet",
            "soft", "gentle", "light", "zen", "breath", "still", "pure", "safe",
            "cozy", "comfy", "warm", "wholesome", "healing", "restoring",
            "unhurried", "languid", "effortless", "undisturbed", "grounded",
            "centered", "present", "mindful", "slow", "tender", "hushed",
            "cathedral", "sacred", "infinite", "vast", "open",
            "morning", "dew", "birdsong", "forest", "rain", "drizzle",
            "cloud", "breeze", "meadow", "lullaby", "cradle", "blanket",
            "fireplace", "candle", "incense", "tea", "soup", "homemade",
            "hygge", "slow morning", "soft focus", "cottagecore",
        ],
        "phrases": [
            "touch grass", "slow down", "just breathe", "take it easy",
            "soft life", "golden hour", "slow living", "in no rush",
            "not in a hurry", "nowhere to be",
        ],
        "context": [
            "yoga", "meditation", "spa", "sleeping", "reading", "nature",
            "morning", "garden", "healing", "nap", "sunrise", "journaling",
            "stretching", "tai chi", "mindfulness", "therapy", "self care",
            "bath", "hot tub", "sauna", "retreat", "cabin", "countryside",
            "lake", "pond", "waterfall", "church", "chapel", "monastery",
        ],
        "artists": [
            "norah jones", "enya", "sade", "jack johnson", "bon iver",
            "iron & wine", "sigur ros", "corinne bailey rae", "yiruma",
            "ludovico einaudi", "debussy", "erik satie", "joe hisaishi",
            "ichiko aoba", "vashti bunyan", "nick drake", "tatsuro yamashita",
            "sufjan stevens", "jose gonzalez", "fleet foxes", "language",
            "jordi savall", "max richter", "nils frahm", "olafur arnalds",
            "dustin o'halloran", "hauschka", "hiroshi yoshimura",
            "motohiro kawashima", "midori takada", "nature sounds",
            "spa music", "lofi beats", "ambient soundscapes",
            "lana del rey", "aurora", "chelsea wolfe",
            "adrianne lenker", "big thief", "julia jacklin",
            "weyes blood", "grouper", "joni mitchell",
        ],
        "bpm": "55-80",
        "genres": ["Ambient", "Acoustic", "Folk", "Easy Listening", "New Age", "Bossa Nova", "Neoclassical"],
    },

    "intense": {
        "keywords": [
            "heavy", "metal", "brutal", "dark", "chaotic", "screaming", "loud",
            "distorted", "crushing", "angry", "hell", "pain", "fury", "anarchy",
            "doom", "shred", "headbang", "moshing", "violent", "raw", "noise",
            "screamo", "breakdown", "riff", "double bass", "blast beat",
            "growl", "guttural", "venom", "wrath", "carnage", "obliterate",
            "destruction", "war", "slaughter", "frenzy", "berserk",
            "cathartic", "primal", "visceral", "gut punch",
            "seething", "boiling", "livid", "irate", "furious",
            "uncontrollable", "spiraling", "snapping", "cracking",
        ],
        "phrases": [
            "screaming into the void", "going feral", "completely lost it",
            "end of my rope", "final straw", "over the edge",
        ],
        "context": [
            "venting", "heavy lifting", "moshpit", "adrenaline", "chaos",
            "war", "riot", "revenge", "breaking point", "rage quit",
            "car crash", "breakdown", "therapy session", "confrontation",
            "catharsis", "purge", "release",
        ],
        "artists": [
            "metallica", "slipknot", "gojira", "lorna shore", "deftones",
            "meshuggah", "bring me the horizon", "knocked loose", "slayer",
            "bad omens", "death", "cannibal corpse", "pantera", "black sabbath",
            "sepultura", "spiritbox", "polyphia", "sleep token", "code orange",
            "vein.fm", "converge", "every time i die", "bane", "harm's way",
            "power trip", "turnstile", "health", "nothing", "cult leader",
            "portrayal of guilt", "show me the body", "girls rituals",
            "drain", "speed", "scowl", "militarie gun",
            "ghostemane", "$uicideboy$", "pouya", "",
            "nine inch nails", "marilyn manson", "rob zombie",
            "white zombie", "tool", "a perfect circle", "primus",
            "system of a down", "rage against the machine", "korn", "limp bizkit",
        ],
        "bpm": "140-220",
        "genres": ["Deathcore", "Nu-Metal", "Thrash", "Hardcore", "Progressive Metal", "Industrial", "Grindcore"],
    },

    "chill": {
        "keywords": [
            "mellow", "smooth", "vibey", "laid back", "floating", "cool",
            "drifting", "stoned", "baked", "wavey", "unwind", "easy",
            "effortless", "no pressure", "sunset", "beach", "ocean",
            "salt air", "hammock", "daydream", "afternoon", "loose",
            "collected", "breeze", "lo-fi", "lofi", "samples", "dusty",
            "grainy", "warm vinyl", "tape hiss", "jazzy sample",
            "head nodding", "headphones in", "zoned out", "cruise",
            "passing time", "doing nothing", "just being", "plugg",
            "bedroom", "laptop beats", "aesthetic",
        ],
        "phrases": [
            "no thoughts head empty", "just existing", "chilling with no plans",
            "late night drive", "windows down", "city at night",
        ],
        "context": [
            "smoke", "late night", "driving", "beach", "sunset", "lounge",
            "hanging out", "lowkey", "cruising", "rooftop", "balcony",
            "after party", "coming down", "winding down", "end of the night",
            "3am", "insomnia", "can't sleep", "scrolling",
        ],
        "artists": [
            "sza", "frank ocean", "mac miller", "tame impala", "khruangbin",
            "kali uchis", "thundercat", "erykah badu", "steve lacy",
            "childish gambino", "brent faiyaz", "giveon", "daniel caesar",
            "partynextdoor", "lucky daye", "masego", "tom misch", "kaytranada",
            "si r", "jorja smith", "smino", "ravyn lenae", "amaarae",
            "arlo parks", "beabadoobee", "clairo", "rex orange county",
            "phoebe bridgers", "snoh aalegra", "abhi the nomad", "the internet",
            "blood orange", "serpentwithfeet", "rejjie snow", "odeal",
            "jones", "mahalia", "dj khalil", "raveena", "cleo sol", "joy crookes",
            "little simz", "mick jenkins", "saba", "noname", "phonte",
            "loyle carner", "knxwledge", "black milk",
        ],
        "bpm": "70-100",
        "genres": ["Neo-Soul", "Indie R&B", "Chillwave", "Lo-Fi Hip Hop", "Vaporwave", "Pluggnb"],
    },

    "focus": {
        "keywords": [
            "concentrate", "study", "work", "productive", "zen", "minimal",
            "deep", "instrumental", "locked in", "grind", "flow state", "coding",
            "hyperfocus", "deadline", "task", "output", "deliberate", "clean",
            "uncluttered", "linear", "systematic", "process", "methodical",
            "brain", "cognition", "clarity", "precision", "execution",
            "dissertation", "thesis", "research", "essay", "revising",
            "silent", "library", "headphones", "noise cancelling",
        ],
        "phrases": [
            "dark academia", "locked in mode", "in the zone", "deep work session",
            "no distractions", "monk mode", "getting shit done", "grinding hard",
        ],
        "context": [
            "library", "coding", "reading", "office", "dark academia",
            "minimalism", "deadline", "writing", "designing", "engineering",
            "math", "architecture", "law", "studying for finals",
            "all nighter", "cramming", "research", "solo work",
        ],
        "artists": [
            "hans zimmer", "max richter", "aphex twin", "brian eno", "nils frahm",
            "lofi girl", "j dilla", "boards of canada", "burial", "four tet",
            "jon hopkins", "tycho", "steve roach", "william basinski",
            "carbon based lifeforms", "bonobo", "blockhead", "nujabes",
            "j-dilla", "little dragon", "floating points", "mount kimbie",
            "james blake", "james holden", "kelly moran", "william orbit",
            "labradford", "stars of the lid", "godspeed you black emperor",
            "tortoise", "mouse on mars", "pole", "isolee", "moderat",
            "apparat", "monolake", "stephan mathieu", "caterina barbieri",
            "kali malone",
        ],
        "bpm": "60-90",
        "genres": ["Modern Classical", "Ambient", "Deep House", "Instrumental Hip Hop", "IDM", "Krautrock"],
    },

    "euphoric": {
        "keywords": [
            "uplifting", "heavenly", "transcend", "magic", "limitless",
            "freedom", "glowing", "bliss", "peak", "flying", "higher",
            "ecstasy", "love", "grateful", "abundant", "expansive",
            "radiant", "luminous", "crystalline", "infinite", "boundless",
            "soaring", "release", "surrender", "universal", "connected",
            "one with everything", "arms open", "serotonin", "tears of joy",
            "overwhelmed in the best way", "cathartic release", "overwhelmed",
        ],
        "phrases": [
            "golden hour", "cloud nine", "living my best life", "peak experience",
            "it's a vibe", "good vibes only", "vibes only", "summer feeling",
        ],
        "context": [
            "festival", "sunrise", "dreaming", "space", "flying",
            "proposal", "reunion", "vacation", "wedding", "graduation",
            "homecoming", "birth", "win", "breakthrough",
            "first love", "falling in love", "road trip with friends",
        ],
        "artists": [
            "fred again", "odesza", "rufus du sol", "m83", "porter robinson",
            "flume", "bicep", "disclosure", "avicii", "daft punk",
            "justice", "swedish house mafia", "deadmau5", "zedd", "kygo",
            "madeon", "lane 8", "ben bohmer", "above & beyond",
            "eric prydz", "max cooper", "jon hopins", "peggy gou",
            "amelie lens", "charlotte de witte", "nina kraviz",
            "aphex twin", "orbital", "the chemical brothers", "fatboy slim",
            "basement jaxx", "underworld", "leftfield", "caribou",
            "four tet", "jamie xx", "rüfüs du sol", "dj tennis",
        ],
        "bpm": "120-145",
        "genres": ["Progressive House", "Future Bass", "Dream Pop", "Synthpop", "Melodic Techno", "Trance"],
    },

    "soulful": {
        "keywords": [
            "emotional", "deep", "bluesy", "jazz", "passionate", "vocal",
            "warm", "heart", "aching", "true", "spirit", "real", "raw",
            "honesty", "confessional", "vulnerable", "authentic", "cathartic",
            "storytelling", "voice", "gospel", "church", "faith", "ritual",
            "ceremony", "invocation", "ancestral", "community", "together",
            "gathering", "weeping", "release", "groaning", "moaning",
            "crooning", "belting", "falsettos", "harmonies", "choir",
        ],
        "phrases": [
            "hits the soul", "speaks to me", "gives me chills", "in my feelings",
            "deep cut", "hidden gem", "underrated", "slept on",
        ],
        "context": [
            "dinner", "wine night", "rainy day", "romantic", "reflective",
            "heartfelt", "jazz club", "church", "candlelit", "date night",
            "late night conversation", "crying and dancing", "feeling yourself",
        ],
        "artists": [
            "miles davis", "john coltrane", "amy winehouse", "billie holiday",
            "leon bridges", "marvin gaye", "al green", "nina simone",
            "otis redding", "aretha franklin", "solange", "anderson paak",
            "cleo sol", "jordan rakei", "snarky puppy", "hiatus kaiyote",
            "brandee younger", "makaya mccraven", "terrace martin",
            "kamasi washington", "esperanza spalding", "ambrose akinmusire",
            "yazmin lacey", "joy crookes", "mahalia", "snoh aalegra",
            "ann peebles", "donny hathaway", "bill withers", "stevie wonder",
            "prince", "maxwell", "musiq soulchild", "erykah badu",
            "d'angelo", "lauryn hill", "india arie", "jill scott",
            "lalah hathaway", "angie stone", "tweet", "floetry",
            "raheem devaughn", "anthony hamilton", "jaheim",
            "lucky daye", "giveon", "eli henderson", "lola young",
        ],
        "bpm": "50-110",
        "genres": ["Jazz", "Blues", "Classic Soul", "Gospel", "Neo-Soul", "Contemporary R&B"],
    },

    "retro": {
        "keywords": [
            "nostalgic", "vintage", "80s", "90s", "neon", "classic", "analog",
            "old school", "throwback", "memory", "disco", "funky",
            "vhs", "polaroid", "film grain", "cassette", "vinyl", "fm",
            "dial", "tube amp", "warm static", "scratchy", "faded",
            "washed out", "sun bleached", "kodachrome", "sepia",
            "drive-in", "diner", "roller rink", "arcade", "mall",
            "coming of age", "prom", "summer of love", "woodstock",
            "synthesizer", "drum machine", "gated reverb",
        ],
        "phrases": [
            "core memory", "it's giving 80s", "it's giving 90s",
            "throwback thursday", "remember when", "takes me back",
        ],
        "context": [
            "arcade", "thrifting", "vinyl", "cassette", "retro gaming",
            "skating rink", "drive-in", "record store", "flea market",
            "antique shop", "old photo album", "home video", "vhs",
        ],
        "artists": [
            "kavinsky", "fleetwood mac", "queen", "new order", "depeche mode",
            "michael jackson", "abba", "bee gees", "earth wind & fire",
            "david bowie", "the cure", "talking heads", "prince", "chic",
            "hall & oates", "jackson 5", "diana ross", "the temptations",
            "four tops", "marvin gaye", "stevie wonder", "kraftwerk", 
            "tangerine dream", "giorgio moroder", "donna summer", "gloria gaynor", 
            "sylvester", "toto", "journey", "foreigner", "eagles", "steely dan", 
            "tom petty", "paul simon", "carole king", "james taylor", "carly simon", 
            "joni mitchell", "the jackson 5", "rick james", "teena marie",
            "a-ha", "tears for fears", "duran duran", "the police",
            "sting", "peter gabriel", "genesis", "phil collins",
            "lionel richie", "whitney houston", "cyndi lauper",
            "madonna", "janet jackson", "rick astley", "erasure",
            "tatsuro yamashita", "mariya takeuchi", "hiroshi sato",
            "anri", "miki matsubara",
        ],
        "bpm": "95-128",
        "genres": ["Synthwave", "80s Pop", "New Wave", "Disco", "Funk", "City Pop", "AOR"],
    },

    "dreamy": {
        "keywords": [
            "surreal", "hazy", "ethereal", "shoegaze", "cloudy", "faded",
            "misty", "otherworldly", "staring at the ceiling", "floating in space",
            "woozy", "gauzy", "underwater", "slow motion", "liminal",
            "intangible", "translucent", "weightless", "pillowy",
            "reverb", "delay", "wall of sound", "noise", "texture",
            "hazey", "blurry", "swirling", "hypnotic", "trance-like",
            "half asleep", "threshold", "between worlds",
        ],
        "phrases": [
            "staring at the ceiling", "head in the clouds", "living in a dream",
            "not of this world", "another dimension", "out of body",
            "dissolving", "becoming one with the music",
        ],
        "context": [
            "daydreaming", "stargazing", "long walks", "escaping",
            "drifting away", "midnight", "insomnia", "lucid dreaming",
            "nostalgia", "memory", "childhood", "hometown",
        ],
        "artists": [
            "slowdive", "beach house", "cocteau twins", "mazzy star", "the xx",
            "men i trust", "alvvays", "cigarettes after sex", "sweet trip",
            "my bloody valentine", "lust for youth", "the radio dept",
            "duster", "salvia palth", "angel olsen", "weyes blood",
            "Julia holter", "grouper", "julianna barwick",
            "helado negro", "tirzah", "land of talk",
            "wild nothing", "real estate", "woods", "teen daze",
            "teen suicide", "mom", "have a nice life",
            "deerhunter", "atlas sound", "sun kil moon", "mark kozelek",
            "the antlers", "mount eerie", "phil elverum",
            "adrianne lenker", "nick drake", "the caretaker", "boards of canada",
            "elysia crampton", "claire rousay",
        ],
        "bpm": "65-105",
        "genres": ["Shoegaze", "Dream Pop", "Indie Rock", "Psych Rock", "Slowcore", "Ambient Pop"],
    },

    "cinematic": {
        "keywords": [
            "epic", "grand", "orchestral", "heroic", "legendary", "majestic",
            "story", "adventure", "powerful", "vast", "main character energy",
            "sweeping", "triumphant", "tragic", "climactic", "operatic",
            "score", "soundtrack", "montage", "scene", "rising action",
            "denouement", "tension", "resolution", "emotional arc",
            "rising strings", "brass fanfare", "choir swells",
            "dramatic pause", "silence before the storm",
            "big moment", "big life moment", "life moment", "momentous",
            "goosebumps", "chills", "spine tingling", "breathtaking",
            "larger than life", "cinematic", "film score", "movie score",
        ],
        "phrases": [
            "main character energy", "main character moment",
            "feels like a movie", "training montage", "final boss",
            "hero moment", "this is my arc", "this is the climax",
            "epic orchestral", "something epic", "something orchestral",
            "big life moment", "orchestral and epic", "epic and orchestral",
            "something grand", "something cinematic", "movie moment",
        ],
        "context": [
            "final boss", "traveling", "exploring", "climax", "movie score",
            "fantasy", "sci-fi", "conquest", "space", "mythology",
            "war film", "romance film", "thriller", "heist", "documentary",
            "orchestra", "live score", "symphony", "film", "cinematic",
        ],
        "artists": [
            "hans zimmer", "john williams", "howard shore", "ennio morricone",
            "trent reznor", "atticus ross", "vangelis", "woodkid",
            "two steps from hell", "thomas bergersen", "audiomachine",
            "ramin djawadi", "bear mcreary", "hildur guðnadóttir",
            "jóhann jóhannsson", "ólafur arnalds", "max richter",
            "nils frahm", "gustavo santaolalla", "ryuichi sakamoto",
            "joe hisaishi", "yoko kanno", "hiroyuki sawano",
            "attack on titan ost", "demon slayer ost", "your name ost",
            "interstellar ost", "blade runner 2049 ost", "inception ost",
        ],
        "bpm": "65-160",
        "genres": ["Soundtrack", "Modern Classical", "Epic Orchestral", "Dark Ambient", "Neo-Classical"],
    },

    "dark": {
        "keywords": [
            "shadow", "gothic", "creepy", "evil", "ghostly", "underworld",
            "sinister", "down bad", "dystopian", "industrial", "occult",
            "ritual", "coven", "hex", "cursed", "haunted", "abandoned",
            "desolate", "empty", "void", "abyss", "oblivion", "nothing",
            "cold", "grey", "ash", "ruins", "decay", "dissolution",
            "introspection", "isolation", "alienation", "dissociation",
            "anomie", "nihilism", "absurdism", "hopeless", "heavy",
        ],
        "phrases": [
            "villain era", "in my villain era", "dark era", "goblin mode",
            "living rent free", "down so bad", "it's giving doom",
        ],
        "context": [
            "halloween", "haunted", "nightmare", "abandoned", "vampire",
            "darkroom", "underground", "forest at night", "alone",
            "isolated", "winter", "blizzard", "empty streets",
        ],
        "artists": [
            "nine inch nails", "gesaffelstein", "rezz", "perturbator",
            "the soft moon", "boy harsher", "crystal castles",
            "sidewalks and skeletons", "desire", "TR/ST",
            "lebanon hanover", "cold cave", "author & punisher",
            "zola jesus", "chelsea wolfe", "true widow", "uniform",
            "white lies", "she wants revenge", "black midi", "squid", 
            "black country new road", "idles", "shame", "jehnny beth", 
            "protomartyr", "suicide", "bauhaus", "joy division", 
            "the sisters of mercy", "the mission", "fields of the nephilim",
            "siouxsie and the banshees", "dead can dance", "this mortal coil",
        ],
        "bpm": "85-130",
        "genres": ["Darkwave", "Industrial Techno", "Witch House", "Goth", "Post-Punk", "Black Metal Adjacent"],
    },

    "heartbreak": {
        "keywords": [
            "sad", "broken", "heartbreak", "heartbroken", "devastated", "crying",
            "tears", "sobbing", "miss you", "losing you", "without you", "alone",
            "lonely", "empty", "hollow", "numb", "disconnected", "left behind",
            "dumped", "rejection", "unrequited", "one-sided", "fading",
            "letting go", "moving on", "closure", "grief", "mourning",
            "loss", "absence", "longing", "yearning", "aching", "wishing",
            "if only", "what if", "could have been", "too late", "regret",
            "guilt", "shame", "self blame", "deserved better",
        ],
        "phrases": [
            "in my feelings", "down bad", "crying rn", "not okay rn",
            "it's giving heartbreak", "ghosted me", "left on read",
            "talking stage ended", "situationship ended",
            "they moved on", "watching them with someone else",
            "still not over it", "miss them so much", "crying in the car",
            "rain on my window", "2am thoughts", "still checking their story",
            "miss someone", "miss them", "miss you", "missing you",
            "missing someone", "when you miss", "rainy sunday",
            "sad sunday", "sunday feels", "type beat sad",
        ],
        "context": [
            "breakup", "divorce", "separation", "rejected", "ghosted",
            "cheated on", "alone at night", "looking at old photos",
            "reading old messages", "their hoodie", "empty side of the bed",
            "drunk and sad", "crying in the shower", "driving and crying",
            "rainy", "drizzly", "grey day", "sunday", "late sunday",
            "melancholy", "wistful", "bittersweet", "tender sad",
        ],
        "artists": [
            "taylor swift", "olivia rodrigo", "billie eilish", "lorde",
            "lana del rey", "adele", "sam smith", "lewis capaldi",
            "james arthur", "ed sheeran", "ariana grande", "sabrina carpenter",
            "chappell roan", "gracie abrams", "phoebe bridgers",
            "frank ocean", "sza", "daniel caesar", "giveon", "brent faiyaz",
            "summer walker", "jhene aiko", "kehlani", "bryson tiller",
            "partynextdoor", "the weeknd", "miguel", "h.e.r.",
            "bon iver", "sufjan stevens", "the national", "fleet foxes",
            "son lux", "the antlers", "mount eerie", "julien baker",
            "better oblivion community center", "boygenius",
            "angel olsen", "weyes blood", "sharon van etten",
            "lucy dacus", "snail mail", "japanese breakfast",
            "illuminati hotties", "soccer mommy",
            "juice wrld", "xxxtentacion", "lil peep", "quinn xcii",
            "emo rap", "iann dior", "rod wave", "morray",
        ],
        "bpm": "60-105",
        "genres": ["Sad Pop", "Indie Folk", "Emo", "Sad R&B", "Alt-Pop", "Singer-Songwriter"],
    },

    "hyperpop": {
        "keywords": [
            "hyperpop", "glitchy", "distorted", "maximalist", "digital",
            "internet", "surreal", "chaotic", "pc music", "digicore",
            "bubblegum", "artificial", "synthetic", "robotic", "pitched up",
            "pitched down", "auto tuned", "autotune", "chopped", "screwed", 
            "plugg", "trap influenced", "hyper", "frenetic", "overwhelming",
            "sensory overload", "brash", "loud", "screaming and pop",
            "emo and edm", "deconstructed", "avant-garde pop", "bratty",
            "chaotic internet girl", "y2k revival",
        ],
        "phrases": [
            "brat summer", "it's giving hyperpop", "chaotic good energy",
            "terminally online", "internet core", "brain rot",
        ],
        "context": [
            "tiktok", "soundcloud", "discord", "twitch", "streaming",
            "gaming", "internet culture", "meme music", "ironic",
            "post-ironic", "queer spaces", "pride", "rave",
        ],
        "artists": [
            "charli xcx", "100 gecs", "sophie", "a.g. cook",
            "arca", "kim petras", "rico nasty", "dorian electra",
            "slayyyter", "jane remover", "osquinn", "glaive",
            "midwxst", "chloe moriondo", "odetari", "elyotto",
            "lil aaron", "shygirl", "blood orange",
            "oklou", "alice gas", "alice longyu gao",
            "namasenda", "cobrah", "mobilegirl",
            "juno songs", "bladee", "drain gang", "ecco2k",
            "thaiboy digital", "yung lean", "mura masa", "felicita",
            "hannah diamond", "gfoty", "lipgloss h",
            "p4rkr", "rebzyyx", "nettspend",
        ],
        "bpm": "140-175",
        "genres": ["Hyperpop", "Digicore", "PC Music", "Bubblegum Bass", "Glitchpop", "Cloud Rap"],
    },

    "party": {
        "keywords": [
            "party", "dance", "club", "rave", "dj", "speakers", "subwoofer",
            "bass", "house", "techno", "disco ball", "strobes", "laser",
            "bottle service", "vip", "drunk", "shots", "tequila",
            "champagne", "popping", "celebration", "turn up", "turnt",
            "lit", "going out", "nightclub", "afterhours", "all night",
            "sunrising at the club", "second wind", "peak hour",
            "floor filler", "anthem", "banger", "remix", "extended",
            "peak time", "banging", "bumping", "thumping",
        ],
        "phrases": [
            "brat summer", "feral summer", "going out tonight",
            "pregame started", "we're going out", "turn up season",
            "no plans just dancing", "crying in the club", "dancing on tables",
        ],
        "context": [
            "birthday", "new year", "friday night", "saturday night",
            "pregame", "afters", "rooftop", "pool party", "day party",
            "festival", "rave", "warehouse rave", "basement party",
            "house party", "club", "bar", "spring break",
        ],
        "artists": [
            "charli xcx", "doja cat", "dua lipa", "lizzo", "cardi b",
            "nicki minaj", "megan thee stallion", "beyoncé", "rihanna",
            "kesha", "lady gaga", "britney spears",
            "peggy gou", "fisher", "dom dolla", "flume", "disclosure",
            "kaytranada", "solomun", "loco dice", "adam beyer",
            "charlotte de witte", "amelie lens", "bicep",
            "the blessed madonna", "honey dijon", "kevin saunderson",
            "derrick may", "juan atkins", "larry heard",
            "calvin harris", "david guetta", "tiesto", "martin garrix",
            "afrojack", "nicky romero", "hardwell", "w&w",
            "daft punk", "justice", "cassius", "breakbot",
            "aeroplane", "poolside", "chromeo", "classixx",
        ],
        "bpm": "120-135",
        "genres": ["Dance Pop", "House", "Tech House", "Afrobeats", "Amapiano", "Dancehall", "Club"],
    },

    "country": {
        "keywords": [
            "country", "folk", "americana", "western", "southern", "rural",
            "small town", "heartland", "twang", "banjo", "fiddle", "dobro",
            "steel guitar", "pedal steel", "honky tonk", "boots", "hat",
            "cowboy", "cowgirl", "ranch", "farm", "field", "dirt road",
            "trailer", "porch", "front porch", "rocking chair", "firepit",
            "campfire", "creek", "river", "mountain", "blue ridge", "appalachian",
            "whiskey", "beer", "longneck", "tailgate", "tailgating",
            "sunday morning", "church bells", "old church", "hymn",
            "homesick", "hometown", "going home", "leaving home",
        ],
        "phrases": [
            "country vibes", "southern gothic", "yeehaw", "rootsy",
            "feels like a country song", "acoustic and honest",
        ],
        "context": [
            "road trip", "summer drive", "windows down", "back road",
            "fishing", "hunting", "farming", "camping", "hiking",
            "bonfire", "cookout", "barbecue", "state fair",
            "fourth of july", "thanksgiving", "family reunion",
        ],
        "artists": [
            "morgan wallen", "luke combs", "zach bryan", "tyler childers",
            "hardy", "eric church", "jason isbell", "margo price",
            "sturgill simpson", "chris stapleton", "kacey musgraves",
            "brandy clark", "maren morris", "lainey wilson",
            "ella langley", "cody johnson", "ryan bingham", "hayes carll",
            "john moreland", "adia victoria", "allison russell",
            "marcus king", "robert finley", "billy strings",
            "molly tuttle", "americana band", "the war on drugs",
            "johnny cash", "waylon jennings", "willie nelson", "hank williams",
            "merle haggard", "george jones", "tammy wynette", "dolly parton",
            "loretta lynn", "patsy cline", "emmylou harris", "gram parsons",
            "townes van zandt", "guy clark", "steve earle",
            "bob dylan", "neil young", "leonard cohen", "james taylor",
            "carole king", "joni mitchell", "simon & garfunkel",
            "peter paul and mary", "woody guthrie", "pete seeger",
            "sufjan stevens", "fleet foxes", "iron & wine", "bon iver",
            "the head and the heart", "the lumineers", "of monsters and men",
            "mumford & sons", "the avett brothers", "old crow medicine show",
            "the decemberists",
        ],
        "bpm": "70-120",
        "genres": ["Country", "Folk", "Americana", "Bluegrass", "Singer-Songwriter", "Southern Rock", "Alt-Country"],
    },

    "tropical": {
        "keywords": [
            "island", "beach", "summer", "caribbean", "afrobeats", "reggae", 
            "dancehall", "reggaeton", "sunny", "ocean", "waves", "paradise", 
            "palm trees", "vacation", "hot", "humidity", "tropical", "jungle", 
            "safari", "salsa", "bachata", "merengue", "rhythm", "percussion", 
            "bongo", "steel drum",
        ],
        "context": [
            "vacation", "beach party", "cruise", "island hopping", "summer break", 
            "carnival", "festival", "tanning", "swimming", "boat party",
        ],
        "artists": [
            "burna boy", "wizkid", "tems", "rema", "asake", "bad bunny", "j balvin", 
            "karol g", "rosalia", "rauw alejandro", "ozuna", "anuel aa", "daddy yankee", 
            "bob marley", "sean paul", "vybz kartel", "popcaan", "beenie man", 
            "buju banton", "shaggy", "major lazer", "machel montano", "davido", 
            "tiwa savage", "fireboy dml", "ckay", "oxlade",
        ],
        "bpm": "90-110",
        "genres": ["Afrobeats", "Reggaeton", "Dancehall", "Reggae", "Soca", "Amapiano"],
    },

    "industrial": {
        "keywords": [
            "mechanical", "gritty", "metallic", "distorted", "noise", "cyber", 
            "cyberpunk", "glitch", "static", "wires", "machine", "factory", 
            "cold", "hard", "sharp", "aggressive", "underground", "concrete", 
            "brutalist", "darkness", "echo", "reverb", "clank", "hiss",
        ],
        "context": [
            "warehouse", "factory", "underground club", "dystopian city", 
            "night drive", "hacking", "gaming", "venting", "heavy workout",
        ],
        "artists": [
            "nine inch nails", "ministry", "skinny puppy", "front 242", 
            "einstürzende neubauten", "death grips", "clipping.", "jpegmafia", 
            "health", "gesaffelstein", "boy harsher", "perturbator", "kavinsky", 
            "vessel", "blawan", "surgeon", "richie hawtin", "peste noire", 
            "ho99o9", "model/rizal",
        ],
        "bpm": "110-140",
        "genres": ["Industrial", "EBM", "Dark Techno", "Experimental Hip Hop", "Noise"],
    },
    
    "desi": {
        "keywords": [
            "bollywood", "desi", "bhangra", "dhol", "wedding", "shaadi", "sangeet", 
            "filmi", "tollywood", "kollywood", "punjabi", "tabla", "sitar", "hindustani",
            "ghazal", "qawwali", "desi pop",
        ],
        "phrases": [
            "desi swag", "brown boy", "brown girl", "bollywood vibes", "shaadi vibes",
            "desi party", "dhol beats"
        ],
        "context": [
            "indian wedding", "baraat", "mehndi", "desi club", "mumbai", "delhi", 
            "diwali", "holi", "navratri", "family gathering"
        ],
        "artists": [
            "ar rahman", "pritam", "arijit singh", "shreya ghoshal", "diljit dosanjh", 
            "badshah", "sidhu moose wala", "ap dhillon", "karan aujla", "mickey singh", 
            "guru randhawa", "anu malik", "alka yagnik", "udith narayan", "lata mangeshkar",
            "kumar sanu", "k.s. chithra", "hariharan", "sonu nigam", "shankar mahadevan",
            "shubh", "tesher", "divine", "yo yo honey singh", "ammy virk", "harrdy sandhu"
        ],
        "bpm": "90-130",
        "genres": ["Bollywood", "Desi Pop", "Bhangra", "Punjabi Pop", "Filmi"]
    }
}


# =============================================================================
#  SCORING WEIGHTS
# =============================================================================
WEIGHT_ARTIST  = 5.0   # Explicit artist mention is very strong signal
WEIGHT_PHRASE  = 4.0   # Multi-word idiomatic phrases
WEIGHT_KEYWORD = 2.5   # Single emotional descriptors
WEIGHT_CONTEXT = 1.0   # Setting / scenario mentions
WEIGHT_SYNONYM = 1.8   # Synonym expansion hits (slightly lower confidence)
NEGATION_MULT  = -0.8  # Negated match flips and slightly dampens



# =============================================================================
#  NLP HELPERS  (v4.1 — calibrated)
# =============================================================================

import functools

@functools.lru_cache(maxsize=4096)
def _wb(term: str) -> re.Pattern:
    """Return a compiled word-boundary regex for `term`."""
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")


def _tokenize(text: str) -> list[str]:
    """Lowercase + extract tokens; preserves emojis as single tokens."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002600-\U000027BF"
        "\U0001F900-\U0001F9FF"
        "\U0000FE00-\U0000FE0F"
        "\u200d"
        "]+",
        flags=re.UNICODE,
    )
    emojis = emoji_pattern.findall(text)
    words = re.findall(r"\b[\w']+\b", text.lower())
    words = [w for w in words if w.strip()]  # guard against empty tokens
    return words + emojis


def _check_negation(tokens: list[str], match_idx: int, window: int = 4) -> bool:
    """Return True if a negation word appears within `window` tokens before match_idx."""
    start = max(0, match_idx - window)
    preceding = tokens[start:match_idx]
    return any(t in NEGATION_TOKENS for t in preceding)


def _expand_synonyms(text: str) -> dict[str, int]:
    """
    Scan text for synonym phrases/words; return {canonical_token: count}.
    Longer phrases checked first. Single-word synonyms use word-boundary matching.
    """
    found: dict[str, int] = defaultdict(int)
    lower = text.lower()

    sorted_syns = sorted(SYNONYMS.keys(), key=len, reverse=True)
    for trigger in sorted_syns:
        if " " in trigger:
            hit = trigger in lower
        else:
            hit = bool(_wb(trigger).search(lower))
        if hit:
            for canonical in SYNONYMS[trigger]:
                found[canonical] += 1
    return found


def _detect_anti_vibes(text: str) -> set[str]:
    """
    Detect phrases like "no sad stuff", "not too calm", "nothing heavy".
    Returns set of vibe names to suppress after scoring.
    """
    lower = text.lower()
    anti: set[str] = set()

    ANTI_PATTERNS = [
        r"(?:no|not|nothing|avoid|skip|without|don'?t\s+want)\s+([\w\s]{2,20}?)(?:\s|$|,|\.|!)",
        r"not\s+too\s+(\w+)",
    ]
    VIBE_ALIASES: dict[str, str] = {
        "sad": "heartbreak", "sadness": "heartbreak", "depressing": "heartbreak",
        "slow": "calm", "quiet": "calm", "soft": "calm",
        "intense": "intense", "heavy": "intense", "metal": "intense",
        "hype": "hype", "aggressive": "hype",
        "dark": "dark", "creepy": "dark",
        "chill": "chill", "mellow": "chill",
        "calm": "calm", "peaceful": "calm",
        "party": "party", "club": "party",
        "dreamy": "dreamy", "ethereal": "dreamy",
        "country": "country", "folk": "country",
    }

    for pattern in ANTI_PATTERNS:
        for match in re.finditer(pattern, lower):
            word = match.group(1).strip()
            if word in VIBE_ALIASES:
                anti.add(VIBE_ALIASES[word])

    return anti


def _intensity_multiplier(text: str, match_start: int, window_chars: int = 35) -> float:
    """
    Look at the characters before a keyword match. If an intensity adverb is
    present, scale the score up or down accordingly.
    """
    INTENSIFIERS = {
        "absolutely":  1.6,
        "completely":  1.5,
        "utterly":     1.5,
        "insanely":    1.5,
        "extremely":   1.5,
        "deeply":      1.4,
        "so so":       1.4,
        "genuinely":   1.3,
        "literally":   1.3,
        "totally":     1.4,
        "not really":  0.4,
        "barely":      0.5,
        "a little":    0.7,
        "a bit":       0.7,
        "slightly":    0.7,
        "kinda":       0.75,
        "kind of":     0.75,
        "sorta":       0.75,
        "somewhat":    0.8,
        "lowkey":      0.85,
    }
    snippet = text[max(0, match_start - window_chars): match_start].lower()
    for word, mult in sorted(INTENSIFIERS.items(), key=lambda x: -len(x[0])):
        if word in snippet:
            return mult
    return 1.0


# =============================================================================
#  MAIN ANALYSIS ENGINE  (v4.1)
# =============================================================================

def analyze_vibe_algorithm(text: str, artist_focus: int = 50, genre_focus: int = 50, bpm_focus: int = 50) -> dict:
    """
    Vibe Analysis Engine v4.1 — Calibrated Edition w/ UI Priority Knobs
    """

    lower_text = text.lower()
    tokens = _tokenize(text)
    scores: dict[str, float] = defaultdict(float)
    matched_tokens: list[str] = []

    # -- Calculate dynamic multipliers based on UI Knobs (50 is baseline 1.0x) --
    art_mult = artist_focus / 50.0
    gen_mult = genre_focus / 50.0
    bpm_mult = bpm_focus / 50.0

    # ── STEP 0: ANTI-VIBE DETECTION ──────────────────────────────────────────
    anti_vibes = _detect_anti_vibes(lower_text)

    # ── STEP 1: SYNONYM EXPANSION ─────────────────────────────────────────────
    synonym_hits = _expand_synonyms(lower_text)
    for canonical, count in synonym_hits.items():
        for vibe, data in VIBE_MAP.items():
            if canonical == vibe or canonical in data.get("keywords", []) or canonical in data.get("context", []):
                scores[vibe] += (WEIGHT_SYNONYM * count * gen_mult)
                matched_tokens.append(f"~{canonical}")

    # ── STEP 2: MULTI-WORD PHRASE MATCHING ────────────────────────────────────
    for vibe, data in VIBE_MAP.items():
        for phrase in data.get("phrases", []):
            if phrase in lower_text:
                scores[vibe] += (WEIGHT_PHRASE * gen_mult)
                matched_tokens.append(phrase)

    # ── STEP 3: ARTIST MATCHING + SPAN MASKING ────────────────────────────────
    masked_text = lower_text
    for vibe, data in VIBE_MAP.items():
        for artist in data.get("artists", []):
            if not artist or not artist.strip():
                continue
            if " " in artist:
                hit = artist in masked_text
            else:
                hit = bool(_wb(artist).search(masked_text))
            if hit:
                scores[vibe] += (WEIGHT_ARTIST * art_mult)
                matched_tokens.append(artist)
                masked_text = masked_text.replace(artist, " " * len(artist), 1)

    # ── STEP 4: KEYWORD MATCHING — word-boundary safe, intensity-aware ─────────
    for vibe, data in VIBE_MAP.items():
        for kw in data.get("keywords", []):
            if not kw or not kw.strip():
                continue
            m = _wb(kw).search(masked_text)
            if m:
                kw_tokens = kw.split()
                try:
                    idx = tokens.index(kw_tokens[0])
                except ValueError:
                    idx = len(tokens)

                if _check_negation(tokens, idx):
                    scores[vibe] += (WEIGHT_KEYWORD * NEGATION_MULT * gen_mult)
                else:
                    intensity = _intensity_multiplier(lower_text, m.start())
                    scores[vibe] += (WEIGHT_KEYWORD * intensity * gen_mult)
                    matched_tokens.append(kw)

    # ── STEP 5: CONTEXT MATCHING — word-boundary safe ─────────────────────────
    for vibe, data in VIBE_MAP.items():
        for ctx in data.get("context", []):
            if not ctx or not ctx.strip():
                continue
            if " " in ctx:
                found = ctx in masked_text
                match_pos = masked_text.find(ctx)
            else:
                m2 = _wb(ctx).search(masked_text)
                found = bool(m2)
                match_pos = m2.start() if m2 else -1

            if found:
                ctx_tokens = ctx.split()
                try:
                    idx = tokens.index(ctx_tokens[0])
                except ValueError:
                    idx = len(tokens)

                if _check_negation(tokens, idx):
                    scores[vibe] += (WEIGHT_CONTEXT * NEGATION_MULT * gen_mult)
                else:
                    scores[vibe] += (WEIGHT_CONTEXT * gen_mult)
                    matched_tokens.append(ctx)
                    
    # ── EXPLICIT BPM PARSING (Tied to BPM Knob) ───────────────────────────────
    # If the user literally types a BPM (e.g., "140 bpm", "120bpm"), we use the BPM knob 
    # to aggressively boost vibes that fit that tempo.
    bpm_match = re.search(r'(\d{2,3})\s*bpm', lower_text)
    if bpm_match:
        target_bpm = int(bpm_match.group(1))
        for v, data in VIBE_MAP.items():
            bpm_str = data.get("bpm", "")
            if "-" in bpm_str:
                min_b, max_b = map(int, bpm_str.split('-'))
                if min_b <= target_bpm <= max_b:
                    scores[v] += (5.0 * bpm_mult) # Big boost if it fits the requested BPM
                    if f"{target_bpm}bpm" not in matched_tokens:
                        matched_tokens.append(f"{target_bpm}bpm")

    # ── STEP 6: APPLY ANTI-VIBE SUPPRESSION ───────────────────────────────────
    for vibe in anti_vibes:
        if vibe in scores:
            scores[vibe] = 0.0

    # ── STEP 7: VALENCE–AROUSAL BLEED ─────────────────────────────────────────
    pre_bleed = dict(scores)
    for vibe, bleed_map in BLEED.items():
        if pre_bleed.get(vibe, 0) > 0:
            for neighbor, factor in bleed_map.items():
                scores[neighbor] += pre_bleed[vibe] * factor

    # ── STEP 8: RESULT ASSEMBLY (Calibrated Math) ─────────────────────────────
    positive_scores = {v: s for v, s in scores.items() if s > 0}
    total_raw_score = sum(positive_scores.values())

    if not positive_scores or total_raw_score == 0:
        return {
            "dominant_vibe": "neutral",
            "confidence": 0.0,
            "bpm_range": "90-120",
            "genres": ["Lo-Fi", "Ambient Pop", "Electronic"],
            "matched_keywords": [],
            "secondary_vibe": None,
            "secondary_confidence": 0.0,
        }

    ranked = sorted(positive_scores.items(), key=lambda x: x[1], reverse=True)
    dominant_vibe, top_score = ranked[0]
    
    # NEW CONFIDENCE MATH: We shrink the "noise" divisor so clear winners hit 80-90%
    adjusted_total = top_score + ((total_raw_score - top_score) * 0.35)
    confidence = round(min(0.99, top_score / adjusted_total), 2)

    secondary_vibe = None
    secondary_confidence = 0.0
    if len(ranked) > 1:
        sv, ss = ranked[1]
        sc = round(min(0.99, ss / adjusted_total), 2)
        if sc >= 0.15:
            secondary_vibe = sv
            secondary_confidence = sc

    meta = VIBE_MAP[dominant_vibe]
    unique_matches = sorted(set(t for t in matched_tokens if t and t.strip()))

    return {
        "dominant_vibe": dominant_vibe,
        "confidence": confidence,
        "bpm_range": meta["bpm"],
        "genres": meta["genres"],
        "matched_keywords": unique_matches,
        "secondary_vibe": secondary_vibe,
        "secondary_confidence": secondary_confidence,
    }


if __name__ == "__main__":
    print(analyze_vibe_algorithm("Dark jazz club, trumpet, noir energy"))
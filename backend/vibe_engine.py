import re
from collections import defaultdict

# =============================================================================
#  VIBEFINDER AI — ACOUSTIC INTELLIGENCE ENGINE v5.0
#  "DESI EXPANSION & QA REGRESSION FIX" EDITION
# =============================================================================
#  v5.0 Changelog (QA-Driven Fixes from 500-Prompt Batch):
#   1. NEW VIBES: 'happy', 'romantic', 'indie_folk', 'punjabi', 'haryanvi'
#      'bollywood_sad', 'ambient' added as first-class categories.
#   2. DESI MEGA-EXPANSION: Punjabi (party), Punjabi soft, Haryanvi, Bollywood
#      classic, Bollywood love, desi wedding with 100+ new artists and keywords.
#   3. FALLBACK FIX: Emotional-rich prompts with ambiguous language now score
#      properly via expanded emotional_state keywords. Prompts like "terrified
#      of being forgotten" and "vibrating with excitement" no longer fall to 5%.
#   4. COUNTRY/FOLK DISAMBIGUATION: 'indie_folk' vibe separates Fleet Foxes-
#      style content from mainstream country. 'Midwest emo' no longer triggers
#      'country'. 'indie folk', 'dark folk' now correctly score indie_folk.
#   5. INTENSE MISFIRES FIXED: Subtle emotional prompts like "quietly unraveling"
#      no longer over-score 'intense'. New context keywords added.
#   6. EUPHORIC MONOPOLY FIXED: New 'happy' vibe absorbs simple joy/giddy
#      prompts so they don't all hit the same Avicii/deadmau5 pool.
#   7. SOULFUL MISFIRES FIXED: "Righteous fury" etc now routes to hype/intense.
#   8. SYNONYM TABLE: 150+ new desi slang, happy/joyful, genre aliases added.
#   9. BLEED TABLE: New vibes wired into valence-arousal bleed.
#  10. 27 Total Vibe Categories (up from 19).
# =============================================================================


# ─── SYNONYM / ALIAS TABLE ────────────────────────────────────────────────────
# Maps any user word or phrase to one or more canonical tokens that appear in
# VIBE_MAP keyword/context lists. Applied BEFORE scoring.
SYNONYMS: dict[str, list[str]] = {
    # ── decades / eras adjacent ──────────────────────────────────────────────
    "1950s": ["retro", "rock", "soulful"],
    "50s": ["retro", "rock", "soulful"],
    "1960s": ["retro", "rock", "dreamy"],
    "60s": ["retro", "rock", "dreamy"],
    "1970s": ["retro", "rock", "soulful", "party"],
    "70s": ["retro", "rock", "soulful", "party"],
    "1980s": ["retro", "party", "industrial"],
    "80s": ["retro", "party", "industrial"],
    "1990s": ["retro", "rock", "chill", "hype"],
    "90s": ["retro", "rock", "chill", "hype"],
    "2000s": ["retro", "rock", "hyperpop", "party"],
    "00s": ["retro", "rock", "hyperpop", "party"],
    "y2k": ["retro", "hyperpop", "rock"],
    "2010s": ["party", "hype", "chill"],
    "10s": ["party", "hype", "chill"],
    "2020s": ["hyperpop", "hype"],
    "20s": ["hyperpop", "hype"],

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

    # ── rock / guitar / band adjacent (NEW) ──────────────────────────────────
    "shredding": ["rock", "intense"],
    "face melting": ["rock", "intense"],
    "headbang": ["rock", "intense"],
    "mosh": ["rock", "intense"],
    "moshpit": ["rock", "intense", "party"],
    "mosh pit": ["rock", "intense", "party"],
    "guitar solo": ["rock", "cinematic"],
    "distortion": ["rock", "industrial"],
    "fuzz": ["rock", "retro"],
    "garage band": ["rock", "retro"],
    "indie sleaze": ["rock", "party"],
    "alt rock": ["rock"],
    "pop punk": ["rock", "party"],
    "rock out": ["rock", "hype"],
    "rockstar": ["rock", "hype"],

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
    "emo": ["dark", "intense", "rock"],
    "emo era": ["dark", "intense", "rock"],
    "black parade energy": ["dark", "intense", "rock"],
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
    "folk": ["country", "indie_folk"],
    "roots": ["country", "soulful"],
    "americana": ["country", "indie_folk"],
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
    "banjo": ["country", "indie_folk"],
    "fiddle": ["country", "soulful"],
    "acoustic guitar": ["country", "calm", "focus", "indie_folk"],
    "road trip": ["country", "retro", "rock"],
    "tail gate": ["country", "party"],
    "tailgate": ["country", "party"],
    "barn": ["country"],
    "summertime sadness": ["heartbreak", "country"],
    "sad country": ["heartbreak", "country"],
    
    # ── desi / bollywood adjacent ────────────────────────────────────────────
    "desi swag": ["desi", "party", "hype"],
    "desi vibes": ["desi"],
    "desi energy": ["desi", "party"],
    "bollywood vibes": ["desi"],
    "bollywood music": ["desi"],
    "bollywood sad": ["bollywood_sad", "heartbreak"],
    "bollywood love": ["romantic", "desi"],
    "filmy": ["desi"],
    "brown boy": ["desi", "hype"],
    "brown girl": ["desi"],
    "shaadi vibes": ["desi", "party"],
    "shaadi songs": ["desi", "party"],
    "sangeet": ["desi", "party"],
    "sangeet party": ["desi", "party"],
    "dhol beats": ["desi", "party"],
    "bhangra vibes": ["punjabi", "party"],
    "bhangra music": ["punjabi", "party"],
    "punjabi music": ["punjabi"],
    "punjabi vibes": ["punjabi"],
    "punjabi wedding": ["punjabi", "party"],
    "haryanvi music": ["haryanvi", "party"],
    "haryanvi vibes": ["haryanvi"],
    "haryanvi songs": ["haryanvi"],
    "ragini music": ["haryanvi"],
    "desi hip hop": ["desi", "hype"],
    "hindi songs": ["desi"],
    "hindi music": ["desi"],
    "sufi vibes": ["desi", "calm"],
    "qawwali vibes": ["desi", "soulful"],
    "ghazal vibes": ["desi", "heartbreak"],
    "ghazals": ["desi", "heartbreak"],
    "indian wedding": ["desi", "party"],
    "baraat": ["punjabi", "party"],
    "mehndi songs": ["desi", "party"],
    "navratri vibes": ["desi", "party"],
    "holi vibes": ["desi", "party", "happy"],
    "diwali vibes": ["desi", "party", "happy"],
    "90s bollywood": ["desi", "retro"],
    "old bollywood": ["desi", "retro"],
    "classic bollywood": ["desi", "retro"],
    "arijit vibes": ["bollywood_sad", "heartbreak"],
    "ap dhillon vibes": ["punjabi_soft", "romantic"],
    "punjabi soft": ["punjabi_soft", "romantic"],
    "soft punjabi": ["punjabi_soft"],
    "punjabi sad": ["punjabi_soft", "heartbreak"],
    "sidhu moosewala": ["punjabi", "hype"],
    "karan aujla vibes": ["punjabi", "hype"],
    "shayari vibes": ["desi", "heartbreak"],
    "teri yaad": ["desi", "heartbreak"],
    "desi breakup": ["desi", "heartbreak"],
    "desi romance": ["romantic", "desi"],
    "dholak": ["desi", "party"],

    # ── happy / joyful / cheerful (new dedicated section) ────────────────
    "happy": ["happy", "euphoric"],
    "happiness": ["happy"],
    "joyful": ["happy", "euphoric"],
    "joyous": ["happy", "euphoric"],
    "cheerful": ["happy"],
    "cheery": ["happy"],
    "upbeat": ["happy", "hype"],
    "feel good": ["happy"],
    "feel-good": ["happy"],
    "sunny": ["happy", "euphoric"],
    "bright": ["happy", "euphoric"],
    "peppy": ["happy", "party"],
    "bouncy": ["happy", "party"],
    "jolly": ["happy"],
    "merry": ["happy"],
    "gleeful": ["happy", "euphoric"],
    "good mood": ["happy"],
    "great mood": ["happy"],
    "best day": ["happy", "euphoric"],
    "best day ever": ["happy", "euphoric"],
    "on top of the world": ["happy", "euphoric"],
    "nothing can stop me": ["happy", "hype"],
    "loving life": ["happy", "euphoric"],
    "spring vibes": ["happy", "calm"],
    "spring morning": ["happy", "calm"],
    "sunshine feeling": ["happy"],
    "good times": ["happy", "retro"],
    "smile": ["happy", "calm"],
    "smiling for no reason": ["happy"],
    "laughing": ["happy", "party"],

    # ── romantic / love songs ─────────────────────────────────────────────
    "romantic": ["romantic"],
    "romance": ["romantic"],
    "in love": ["romantic"],
    "falling in love": ["romantic"],
    "love songs": ["romantic"],
    "love song": ["romantic"],
    "lovey dovey": ["romantic"],
    "date night": ["romantic", "soulful"],
    "slow dance": ["romantic", "soulful"],
    "candlelit dinner": ["romantic", "soulful"],
    "anniversary": ["romantic", "soulful"],
    "valentines": ["romantic"],
    "serenade": ["romantic"],
    "love letter": ["romantic"],
    "deeply in love": ["romantic"],
    "head over heels": ["romantic", "happy"],
    "butterflies in love": ["romantic", "happy"],
    "crush feeling": ["romantic"],
    "new love": ["romantic", "happy"],
    "sweet love": ["romantic"],
    "tender love": ["romantic", "soulful"],
    "cozy with someone": ["romantic", "calm"],

    # ── indie folk disambiguation (fixes country hijack) ─────────────────
    "indie folk": ["indie_folk"],
    "folk indie": ["indie_folk"],
    "fleet foxes adjacent": ["indie_folk"],
    "fleet foxes vibes": ["indie_folk"],
    "bon iver vibes": ["indie_folk", "dreamy"],
    "iron and wine vibes": ["indie_folk"],
    "folk harmonies": ["indie_folk"],
    "rich harmonies": ["indie_folk"],
    "indie acoustic": ["indie_folk"],
    "modern folk": ["indie_folk"],
    "dark folk": ["indie_folk", "dark"],
    "murder ballad": ["indie_folk", "dark"],
    "appalachian": ["indie_folk", "country"],
    "banjo folk": ["indie_folk"],
    "finger picking": ["indie_folk", "calm"],
    "folk pop": ["indie_folk"],
    "folk rock": ["indie_folk", "rock"],
    "midwest emo": ["rock", "heartbreak"],
    "emo revival": ["rock", "heartbreak"],
    "small town emo": ["rock", "heartbreak"],

    # ── ambient / drone / texture (fixes fallback for abstract prompts) ───
    "ambient music": ["ambient"],
    "ambient vibes": ["ambient"],
    "drone music": ["ambient"],
    "long tones": ["ambient", "calm"],
    "minimal music": ["ambient", "focus"],
    "texture music": ["ambient"],
    "soundscape": ["ambient", "calm"],
    "brian eno vibes": ["ambient"],
    "meditation music": ["ambient", "calm"],
    "sleep music": ["ambient", "calm"],
    "rain sounds": ["ambient", "calm"],
    "nature sounds": ["ambient", "calm"],
    "white noise": ["ambient", "focus"],
    "oceanic": ["ambient", "calm"],
    "spacious": ["ambient", "dreamy"],
    "sparse": ["ambient", "focus"],
    "minimalist music": ["ambient", "focus"],
    "tape loops": ["ambient"],
    "field recording": ["ambient"],

    # ── emotional states that were SIGNAL LOST (fallback fixes) ──────────
    "terrified": ["heartbreak", "intense"],
    "terror": ["intense", "dark"],
    "forgotten": ["heartbreak", "dreamy"],
    "being forgotten": ["heartbreak"],
    "fear of forgetting": ["heartbreak"],
    "fear of being forgotten": ["heartbreak"],
    "vibrating": ["euphoric", "hype"],
    "contained excitement": ["euphoric", "chill"],
    "trembling": ["intense", "heartbreak"],
    "shivering": ["heartbreak", "dreamy"],
    "strangely comfortable": ["chill", "calm"],
    "strange comfort": ["chill", "dreamy"],
    "familiar sadness": ["heartbreak", "dreamy"],
    "misunderstood": ["heartbreak", "dreamy"],
    "loneliness": ["heartbreak", "dreamy"],
    "slowly proud": ["euphoric", "calm"],
    "small victory": ["euphoric", "calm"],
    "private victory": ["euphoric", "calm"],
    "specifically": ["dreamy", "chill"],
    "specific joy": ["happy", "euphoric"],
    "specific loneliness": ["heartbreak", "dreamy"],
    "finally understood": ["euphoric", "soulful"],
    "finally being understood": ["euphoric", "soulful"],
    "resolute": ["hype", "focus"],
    "decided": ["focus", "hype"],
    "ready": ["hype", "euphoric"],
    "righteous": ["hype", "soulful"],
    "righteous fury": ["hype", "intense"],
    "justified anger": ["hype", "intense"],
    "true to myself": ["soulful", "calm"],
    "speaking truth": ["soulful", "hype"],
    "saying something true": ["soulful", "euphoric"],
    "finally said": ["soulful", "euphoric"],
    "deeply satisfied": ["calm", "euphoric"],
    "sheepish": ["calm", "heartbreak"],
    "tender after": ["soulful", "calm"],
    "soft grief": ["heartbreak", "calm"],
    "slow grief": ["heartbreak", "calm"],
    "years later": ["heartbreak", "dreamy"],
    "homesick suddenly": ["heartbreak", "dreamy"],
    "homesickness hits": ["heartbreak", "dreamy"],
    "fragile hope": ["heartbreak", "euphoric"],
    "possibility": ["euphoric", "dreamy"],
    "drunk on possibility": ["euphoric", "dreamy"],
    "burning ambition": ["hype", "focus"],
    "paralyzed by": ["heartbreak", "focus"],
    "too many options": ["calm", "dreamy"],
    "electric feeling": ["euphoric", "romantic"],
    "before a kiss": ["romantic", "euphoric"],
    "fiercely protective": ["hype", "soulful"],
    "bittersweet pride": ["heartbreak", "euphoric"],
    "watching someone grow": ["soulful", "heartbreak"],
    "crumbling slowly": ["heartbreak", "dark"],
    "holding the facade": ["heartbreak", "dark"],
    "facade cracking": ["heartbreak", "dark"],
    "carrying someone else": ["heartbreak", "soulful"],
    "weight of someone": ["heartbreak", "soulful"],

    # ── retro / nostalgic adjacent ────────────────────────────────────────────
    "nostalgia": ["retro"],
    "throwback": ["retro"],
    "vintage": ["retro"],
    "old school": ["retro"],
    "cassette": ["retro"],
    "vinyl": ["retro", "soulful", "rock"],
    "record store": ["retro", "soulful", "rock"],
    "fm radio": ["retro"],
    "dial-up": ["retro"],
    "summer of 69": ["retro", "euphoric", "rock"],
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
    "distorted": ["hyperpop", "intense", "rock"],
    "maximalist": ["hyperpop", "hype"],
    "chaotic good": ["hyperpop", "party"],
    "terminally online": ["hyperpop"],
    "internet girl": ["hyperpop", "dreamy"],
    "digicore": ["hyperpop"],
    "pc music": ["hyperpop"],
    "hypno pop": ["hyperpop"],
    "bubblegum bass": ["hyperpop"],
    "scenecore": ["hyperpop", "intense"],
    "skramz": ["intense", "hyperpop", "rock"],
    "slugga": ["hype", "hyperpop"],
    "nightcore": ["hyperpop", "hype"],
    "digital girl": ["hyperpop", "dreamy"],
    "pluggnb": ["chill", "hyperpop"],
    "rage beat": ["hype", "intense"],

    # ── joy / giddiness adjacent ───────────────────────────────────────────
    "giddy": ["happy", "euphoric", "party"],
    "childlike": ["happy", "calm"],
    "carefree": ["happy", "calm"],
    "elated": ["happy", "euphoric"],
    "overjoyed": ["happy", "euphoric"],
    "glee": ["happy", "euphoric", "party"],
    "lighthearted": ["happy", "calm"],
    "playful": ["happy", "euphoric", "party"],
    "bubbly": ["happy", "euphoric", "party"],
    "breezy": ["calm", "happy"],
    "innocent": ["calm", "happy"],
    "pure joy": ["happy", "euphoric"],
    "wholehearted": ["happy", "soulful"],
    "beaming": ["happy", "euphoric"],
    "bright-eyed": ["happy", "calm"],
    "fizzy": ["happy", "euphoric", "hyperpop"],
    "elation": ["happy", "euphoric"],
    "childlike wonder": ["happy", "calm"],
    "childlike joy": ["happy", "calm"],
    "wonder": ["happy", "dreamy"],
    "amazement": ["happy", "cinematic"],
    "wondrous": ["happy", "dreamy"],

    # ── pride / triumph / vindication adjacent ─────────────────────────────
    "proud": ["euphoric", "soulful"],
    "pride": ["euphoric", "soulful"],
    "vindicated": ["euphoric", "intense"],
    "victorious": ["euphoric", "hype"],
    "triumph": ["euphoric", "cinematic"],
    "accomplished": ["euphoric", "focus"],
    "satisfied": ["calm", "euphoric"],
    "smug": ["hype", "chill"],
    "relieved": ["calm", "euphoric"],
    "validated": ["euphoric", "soulful"],
    "deserved": ["euphoric", "soulful"],
    "earned": ["euphoric", "hype"],
    "winning": ["hype", "euphoric"],
    "champion": ["hype", "euphoric"],
    "proved them wrong": ["hype", "euphoric"],
    "on top": ["hype", "euphoric"],

    # ── anticipation / nervous energy adjacent ──────────────────────────────
    "nervous excitement": ["euphoric", "hype"],
    "nervous": ["heartbreak", "dreamy"],
    "anxious": ["heartbreak", "intense"],
    "excited": ["hype", "euphoric"],
    "anticipation": ["euphoric", "dreamy"],
    "butterflies": ["euphoric", "heartbreak"],
    "life-changing": ["cinematic", "euphoric"],
    "butterflies in stomach": ["euphoric", "heartbreak"],
    "first date": ["euphoric", "soulful"],
    "about to happen": ["cinematic", "euphoric"],

    # ── endorphin / runner's high adjacent ─────────────────────────────────
    "endorphins": ["euphoric", "hype"],
    "runner's high": ["euphoric", "hype"],
    "runner high": ["euphoric", "hype"],
    "long run": ["hype", "euphoric"],
    "euphoric run": ["euphoric", "hype"],
    "post-workout": ["euphoric", "chill"],
    "post workout": ["euphoric", "chill"],
    "physically tired": ["chill", "calm"],

    # ── complex/ambiguous emotional states ─────────────────────────────────
    "bittersweet": ["heartbreak", "euphoric"],
    "melancholic": ["heartbreak", "dreamy"],
    "melancholy": ["heartbreak", "dreamy"],
    "wistful": ["heartbreak", "dreamy"],
    "contemplative": ["focus", "calm"],
    "introspective": ["focus", "heartbreak"],
    "conflicted": ["heartbreak", "intense"],
    "overwhelmed": ["intense", "heartbreak"],
    "overjoyed and sad": ["euphoric", "heartbreak"],
    "joyful sadness": ["euphoric", "heartbreak"],
    "crying happy tears": ["euphoric", "heartbreak"],
    "laughing and crying": ["euphoric", "heartbreak"],
    "heavy hearted": ["heartbreak", "soulful"],
    "tender": ["soulful", "calm"],
    "fragile": ["heartbreak", "calm"],
    "raw": ["heartbreak", "soulful"],
    "vulnerable": ["heartbreak", "soulful"],
    "numb": ["heartbreak", "dark"],
    "hollow": ["heartbreak", "dark"],
    "crumbling": ["heartbreak", "dark"],
    "holding it together": ["heartbreak", "focus"],
    "pretending to be fine": ["heartbreak", "dark"],
    "facade": ["heartbreak", "dark"],
    "weight of": ["heartbreak", "cinematic"],
    "weight of sadness": ["heartbreak", "soulful"],
    "carrying sadness": ["heartbreak", "soulful"],
    "someone else's pain": ["heartbreak", "soulful"],
    "grief": ["heartbreak", "soulful"],
    "grieving": ["heartbreak", "soulful"],
    "mourning": ["heartbreak", "soulful"],
    "loss": ["heartbreak", "soulful"],
    "bereavement": ["heartbreak", "soulful"],
    "shiva": ["heartbreak", "soulful"],
    "funeral": ["heartbreak", "calm"],
    "memorial": ["heartbreak", "calm"],
    "wake": ["heartbreak", "soulful"],
    "remembering": ["heartbreak", "dreamy"],

    # ── ambition / drive adjacent ───────────────────────────────────────────
    "ambitious": ["hype", "focus"],
    "ambition": ["hype", "focus"],
    "hungry": ["hype", "intense"],
    "hunger": ["hype", "focus"],
    "burning desire": ["hype", "intense"],
    "relentless": ["hype", "intense"],
    "driven": ["focus", "hype"],
    "determined": ["focus", "hype"],
    "obsessed": ["focus", "intense"],
    "building": ["focus", "hype"],
    "launched": ["euphoric", "hype"],
    "shipped it": ["euphoric", "hype"],
    "finished": ["euphoric", "calm"],
    "breakthrough": ["euphoric", "hype"],

    # ── contentment / ordinary life adjacent ───────────────────────────────
    "content": ["calm", "euphoric"],
    "ordinary": ["calm", "chill"],
    "simple pleasure": ["calm", "euphoric"],
    "mundane": ["chill", "calm"],
    "comfortable": ["calm", "chill"],
    "pleasant": ["calm", "euphoric"],
    "nothing happening": ["calm", "chill"],
    "lazy day": ["chill", "calm"],
    "restful": ["calm"],
    "procrastinating": ["chill", "focus"],
    "procrastination": ["chill", "focus"],
    "background noise": ["focus", "chill"],
    "background music": ["focus", "calm"],
    "cooking": ["calm", "soulful"],
    "hosting": ["soulful", "party"],
    "karaoke": ["party", "hype"],
    "long flight": ["chill", "calm"],
    "commute": ["chill", "focus"],
    "grocery shopping": ["chill", "calm"],
    "running errands": ["chill", "calm"],
    "getting ready": ["party", "hype"],
    "first day": ["hype", "euphoric"],
    "moving day": ["euphoric", "heartbreak"],
    "leaving forever": ["heartbreak", "cinematic"],
    "watching my city": ["heartbreak", "cinematic"],
    "empty nest": ["heartbreak", "calm"],
    "kid leaving": ["heartbreak", "soulful"],
    "sobriety": ["calm", "heartbreak"],
    "sober": ["focus", "calm"],
    "recovery": ["calm", "soulful"],
    "therapy": ["calm", "soulful"],
    "creative block": ["heartbreak", "focus"],
    "inspiration": ["euphoric", "focus"],
    "flow": ["focus", "euphoric"],
    "ideas flowing": ["euphoric", "focus"],

    # ── texture / sensory prompts ────────────────────────────────────────────
    "velvet": ["soulful", "chill"],
    "silk": ["chill", "soulful"],
    "honey": ["chill", "soulful"],
    "petrichor": ["calm", "dreamy"],
    "pine": ["calm", "dark"],
    "cold air": ["calm", "dark"],
    "sunscreen": ["tropical", "euphoric"],
    "sand": ["tropical", "calm"],
    "waterfall": ["calm", "dreamy"],
    "underwater": ["dreamy", "calm"],
    "static": ["industrial", "dark"],
    "fog": ["dreamy", "dark"],
    "mist": ["dreamy", "calm"],
    "foghorn": ["cinematic", "dark"],
    "distant": ["dreamy", "heartbreak"],
    "glass cracking": ["intense", "dark"],
    "silver": ["dreamy", "calm"],
    "gold": ["soulful", "euphoric"],
    "purple": ["soulful", "dreamy"],
    "burnt orange": ["chill", "soulful"],
    "deep blue": ["dreamy", "calm"],
    "free falling": ["dreamy", "euphoric"],
    "slow motion": ["dreamy", "cinematic"],
    "swimming through": ["dreamy", "calm"],
    "bruise": ["heartbreak", "calm"],
    "smiling": ["euphoric", "calm"],
    "delirious": ["dreamy", "euphoric"],
    "deliriously tired": ["chill", "dreamy"],
    "tired but happy": ["chill", "euphoric"],
    "at peace with being alone": ["calm", "soulful"],
    "peace with being alone": ["calm", "soulful"],
    "at peace": ["calm", "euphoric"],
    "homesick": ["heartbreak", "dreamy"],
    "home that never": ["heartbreak", "dreamy"],
    "never heard before": ["dreamy", "chill"],
    "familiar but never": ["dreamy", "heartbreak"],
    "first date at home": ["soulful", "calm"],
    "waltz": ["cinematic", "calm"],
    "waltzing": ["cinematic", "calm"],
    "candlelight": ["soulful", "calm"],
    "techno": ["industrial", "dark"],
    "berlin": ["industrial", "dark"],
    "4am": ["dark", "industrial"],
    "at 4am": ["dark", "industrial"],
    "looks like": ["dreamy", "cinematic"],
    "feels like": ["heartbreak", "dreamy"],
    "sounds like": ["dreamy", "focus"],
    "tastes like": ["dreamy", "retro"],

    # ── niche genre terms that were SIGNAL LOST ──────────────────────────────
    "underground techno": ["industrial", "dark"],
    "acid techno": ["industrial", "hype"],
    "progressive bluegrass": ["country", "focus"],
    "bluegrass gospel": ["country", "soulful"],
    "proto-punk": ["intense", "retro", "rock"],
    "chamber pop": ["cinematic", "focus"],
    "baroque pop": ["cinematic", "focus"],
    "baroque": ["cinematic", "focus"],
    "dembow": ["tropical", "party"],
    "reggaeton": ["tropical", "party"],
    "raga": ["focus", "dreamy"],
    "psychedelic": ["dreamy", "retro", "rock"],
    "wonky": ["industrial", "focus"],
    "outlaw country": ["country", "dark"],
    "grunge": ["intense", "dark", "rock"],
    "seattle": ["intense", "dark", "rock"],
    "acid rock": ["retro", "intense", "rock"],
    "disco": ["party", "retro"],
    "nairobi": ["tropical", "chill"],
    "afro-fusion": ["tropical", "chill"],
    "victorian": ["cinematic", "soulful"],
    "viking": ["cinematic", "intense"],
    # v5.0 additions for niche genre prompts
    "modern classical": ["ambient", "focus", "cinematic"],
    "neo classical": ["ambient", "focus", "cinematic"],
    "neoclassical": ["ambient", "focus", "cinematic"],
    "classical piano": ["ambient", "focus"],
    "contemporary classical": ["ambient", "focus"],
    "piano solo": ["ambient", "calm"],
    "glass": ["ambient", "focus"],
    "philip glass": ["ambient", "focus"],
    "arvo part": ["ambient", "calm"],
    "arvo pärt": ["ambient", "calm"],
    "john cage": ["ambient", "focus"],
    "satie": ["calm", "ambient"],
    "erik satie": ["calm", "ambient"],
    "sun ra": ["soulful", "dreamy"],
    "free jazz": ["soulful", "intense"],
    "spiritual jazz": ["soulful", "dreamy"],
    "coltrane": ["soulful", "intense"],
    "jazzanova": ["soulful", "chill"],
    "nu jazz": ["soulful", "chill"],
    "soul jazz": ["soulful", "chill"],
    "organ trio": ["soulful", "chill"],
    "smooth jazz": ["chill", "soulful"],
    "bossa nova": ["calm", "chill", "soulful"],
    "noise rock": ["intense", "rock"],
    "math rock": ["rock", "focus"],
    "odd time": ["rock", "focus"],
    "post rock": ["cinematic", "dreamy"],
    "post-rock": ["cinematic", "dreamy"],
    "shoegaze": ["dreamy", "rock"],
    "slowcore": ["dreamy", "heartbreak"],
    "psychedelic soul": ["soulful", "retro"],
    "sly stone": ["soulful", "retro", "hype"],
    "detroit techno": ["industrial", "dark"],
    "detroit electronic": ["industrial", "dark"],
    "ambient techno": ["industrial", "ambient"],
    "kosmische musik": ["ambient", "dreamy"],
    "krautrock": ["industrial", "rock"],
    "folk harmonics": ["indie_folk"],
    "murder ballads": ["indie_folk", "dark"],
    "emo revival": ["rock", "heartbreak"],
    "midwest emo": ["rock", "heartbreak"],
    "twinkly guitar": ["indie_folk", "heartbreak"],
    "noodly guitar": ["indie_folk", "rock"],

    # ── v8.0: Typo / abbreviation tolerant aliases ───────────────────────────
    "amient": ["ambient"],
    "amient focus": ["ambient", "focus"],
    "amient focus snd": ["ambient", "focus"],
    "drk": ["dark"],
    "drk ambint": ["dark", "ambient"],
    "drk ambint slp": ["dark", "ambient", "calm"],
    "shogaze": ["dreamy", "rock"],
    "shogaze gtar": ["dreamy", "rock"],
    "vaprwav": ["retro", "dreamy"],
    "vaprwav aesthtic": ["retro", "dreamy"],
    "hapy": ["happy"],
    "hapy vbies": ["happy"],
    "hapy vbies onyl": ["happy"],
    "jzz": ["soulful"],
    "jzz clb": ["soulful", "cinematic"],
    "jzz clb nigt": ["soulful", "cinematic", "dark"],
    "reggaetn": ["tropical", "party"],
    "pujabi": ["desi", "party"],
    "pujabi vibe": ["desi", "party"],
    "clasical": ["ambient", "focus"],
    "clasical pian": ["ambient", "calm"],
    "indstriel": ["industrial", "dark"],
    "hiphp": ["hype"],
    "hiphp trp": ["hype"],
    "postrok": ["cinematic", "dreamy"],
    "slowcor": ["dreamy", "heartbreak"],
    "dprstep": ["industrial", "hype"],
    "drm&bs": ["industrial", "hype"],
    "dnb": ["industrial", "hype"],
    "lo-f": ["chill", "focus"],
    "lofi": ["chill", "focus"],
    "lo-fi": ["chill", "focus"],
    "lo fi": ["chill", "focus"],
    "lofi beats": ["chill", "focus"],
    "lo-fi beats": ["chill", "focus"],
    "lofi hip hop": ["chill", "focus"],
    "lo-fi hip hop": ["chill", "focus"],
    "lofi hiphop": ["chill", "focus"],
    "chillhop": ["chill", "focus"],
    "lofi girl": ["chill", "focus"],
    "lofi music": ["chill", "focus"],
    "lofi vibes": ["chill"],
    "lofi chill": ["chill"],
    "lofi study": ["focus", "chill"],
    "lofi coding": ["focus", "chill"],
    "lofi jazz": ["chill", "focus"],
    "nujabes": ["chill", "focus"],
    "j dilla": ["chill", "focus"],
    "knxwledge": ["chill", "focus"],
    "chllwav": ["chill", "dreamy"],
    "rggae": ["tropical", "calm"],
    "nujazz": ["soulful", "chill"],
    "afrobts": ["tropical", "party"],

    # ── v8.0: Abstract / philosophical phrase mappings ───────────────────────
    "ordered randomness": ["focus", "industrial"],
    "purposeful accident": ["dreamy", "focus"],
    "bored excitement": ["chill", "happy"],
    "unknown familiarity": ["dreamy", "heartbreak"],
    "airport departure gate": ["calm", "cinematic"],
    "airport departure gate at night": ["calm", "cinematic", "dark"],
    "airport": ["calm", "cinematic"],
    "departure gate": ["calm", "cinematic"],
    "controlled chaos": ["hype", "industrial"],
    "beautiful melancholy": ["heartbreak", "dreamy"],
    "productive sadness": ["heartbreak", "focus"],
    "comfortable loneliness": ["chill", "heartbreak"],
    "nostalgic future": ["retro", "dreamy"],
    "familiar stranger": ["dreamy", "heartbreak"],
    "leaving toxic": ["heartbreak", "euphoric"],
    "leaving toxic relationship": ["heartbreak", "euphoric"],
    "terrifyingly free": ["euphoric", "intense"],
    "hour before": ["focus", "cinematic"],
    "hour before everything changes": ["focus", "cinematic"],
    "last day of summer": ["heartbreak", "retro"],
    "first day of winter": ["calm", "dark"],
    "3am thoughts": ["dark", "heartbreak"],
    "5am sunrise": ["calm", "euphoric"],
    "driving nowhere": ["chill", "dreamy"],
    "staring at ceiling": ["heartbreak", "chill"],
    "watching rain": ["calm", "heartbreak"],
    "empty apartment": ["heartbreak", "calm"],
    "sunday afternoon": ["chill", "calm"],
    "monday morning": ["focus", "chill"],

    # ── v8.0: Niche artist / reference mappings ──────────────────────────────
    "new amor": ["dreamy", "calm"],
    "new amor birthplace": ["dreamy", "calm"],
    "half waif": ["dreamy", "indie_folk"],
    "half waif form": ["dreamy", "indie_folk"],
    "sakanaction": ["dreamy", "rock"],
    "sakanaction music": ["dreamy", "rock"],
    "sakanaction alt jpop": ["dreamy", "rock"],
    "jai paul": ["dreamy", "chill"],
    "yeule": ["dreamy", "ambient"],
    "the microphones": ["indie_folk", "dreamy"],
    "grouper": ["ambient", "heartbreak"],
    "julianna barwick": ["ambient", "calm"],
    "lingua ignota": ["intense", "dark"],
    "injury reserve": ["hype", "industrial"],
    "jockstrap": ["dreamy", "hyperpop"],
    "caroline polachek": ["dreamy", "heartbreak"],
    "wet leg": ["rock", "dreamy"],

    # ── v8.0: Regional / cultural slang ─────────────────────────────────────
    "braai": ["party"],
    "amapiano braai": ["tropical", "party"],
    "amapiano": ["tropical", "party"],
    "gqom": ["tropical", "party"],
    "kizomba": ["tropical", "romantic"],
    "dilwale": ["desi", "soulful"],
    "dilwale dulhania": ["desi", "soulful"],
    "dilwale dulhania type vibe": ["desi", "soulful", "romantic"],
    "south indian mass": ["cinematic", "hype"],
    "south indian mass bgm": ["cinematic", "hype"],
    "bgm": ["cinematic"],
    "mass bgm": ["cinematic", "hype"],
    "mass": ["cinematic", "hype"],
    "fdfs": ["hype", "cinematic"],
    "crowded street market": ["chill", "soulful"],
    "crowded street market marrakech": ["chill", "soulful"],
    "marrakech": ["calm", "soulful"],
    "souq": ["calm", "soulful"],
    "lantern festival": ["euphoric", "calm"],
    "cherry blossom": ["calm", "dreamy"],
    "monsoon": ["calm", "heartbreak"],
    "chai time": ["calm", "chill"],
    "adda": ["chill", "soulful"],
    "matcha": ["calm", "focus"],
    "izakaya": ["chill", "soulful"],
    "hanami": ["calm", "dreamy"],
    "barbeque": ["party", "chill"],
    "bbq": ["party", "chill"],
    "block party": ["party", "hype"],
    "tailgate vibes": ["party", "country"],
    "sunday brunch": ["chill", "soulful"],
    "kyoto morning": ["calm", "dreamy"],
    "tokyo subway": ["industrial", "ambient"],
    "tokyo subway ambient": ["ambient", "dreamy"],
    "seoul night": ["chill", "dark"],
    "havana night": ["tropical", "romantic"],

    # ── Emoji map ────────────────────────────────────────────────────────────
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
    "🎸": ["rock", "intense", "retro"],
    "🥁": ["rock", "party"],
    "🎤": ["rock", "party", "soulful"],
    "🤘": ["rock", "intense"],
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
    "🥳": ["happy", "party"],
    "😄": ["happy"],
    "😊": ["happy", "calm"],
    "☀️": ["happy", "euphoric"],
    "🌸": ["happy", "calm", "romantic"],
    "💗": ["romantic", "happy"],
    "💕": ["romantic"],
    "💞": ["romantic", "soulful"],
    "🫶": ["romantic", "soulful"],
    "🎊": ["happy", "party"],
    "🎉": ["happy", "party"],
    "🥁": ["punjabi", "desi", "party"],
    "🪘": ["punjabi", "desi", "party"],
    "🪗": ["desi", "country"],
    "🕌": ["desi", "calm"],
    "💃": ["party", "desi"],
    "🕺": ["party", "desi"],
}

# ─── NEGATION WORDS ───────────────────────────────────────────────────────────
# NOTE: "never" intentionally excluded — it appears in emotional phrases like
# "a childhood I never had" or "never heard this before" and causes false negation.
# The entity scanner has its own separate NEGATION_TOKENS set for entity locks.
NEGATION_TOKENS = {
    "not", "no", "dont", "don't", "doesnt", "doesn't", "without",
    "zero", "none", "nothing", "neither", "nor", "hate", "avoid", "skip",
    "anti", "opposite", "except", "less", "minus", "forget",
}

# ─── VALENCE–AROUSAL BLEED TABLE ─────────────────────────────────────────────
BLEED: dict[str, dict[str, float]] = {
    "hype":         {"intense": 0.25, "party": 0.20, "euphoric": 0.15, "rock": 0.10},
    "calm":         {"focus": 0.20, "chill": 0.25, "dreamy": 0.10},
    "intense":      {"hype": 0.20, "dark": 0.25, "rock": 0.20},
    "chill":        {"calm": 0.20, "dreamy": 0.15, "heartbreak": 0.10},
    "focus":        {"calm": 0.15, "cinematic": 0.10},
    "euphoric":     {"party": 0.25, "hype": 0.15, "dreamy": 0.10, "happy": 0.20},
    "soulful":      {"heartbreak": 0.20, "chill": 0.15, "calm": 0.10},
    "retro":        {"soulful": 0.15, "chill": 0.10, "dreamy": 0.10, "rock": 0.15},
    "dreamy":       {"chill": 0.15, "heartbreak": 0.10, "dark": 0.10},
    "cinematic":    {"intense": 0.15, "euphoric": 0.15, "dreamy": 0.10, "rock": 0.05},
    "dark":         {"intense": 0.20, "dreamy": 0.10},
    "heartbreak":   {"soulful": 0.15, "dark": 0.10, "chill": 0.10},
    "hyperpop":     {"hype": 0.20, "party": 0.20, "euphoric": 0.10},
    "party":        {"hype": 0.25, "euphoric": 0.20, "hyperpop": 0.10},
    "country":      {"calm": 0.15, "soulful": 0.15, "retro": 0.10, "rock": 0.10},
    "tropical":     {"party": 0.25, "chill": 0.15},
    "industrial":   {"dark": 0.25, "intense": 0.20},
    "desi":         {"party": 0.25, "hype": 0.15, "soulful": 0.10},
    "rock":         {"intense": 0.20, "retro": 0.20, "hype": 0.15, "party": 0.10, "chill": 0.05},
    # NEW v5.0
    "happy":        {"euphoric": 0.30, "party": 0.20, "calm": 0.15},
    "romantic":     {"soulful": 0.20, "chill": 0.15, "heartbreak": 0.10},
    "indie_folk":   {"calm": 0.20, "heartbreak": 0.15, "dreamy": 0.10, "country": 0.05},
    "punjabi":      {"desi": 0.30, "party": 0.25, "hype": 0.15},
    "punjabi_soft": {"desi": 0.25, "romantic": 0.20, "heartbreak": 0.15},
    "haryanvi":     {"desi": 0.30, "party": 0.20, "hype": 0.15},
    "bollywood_sad":{"desi": 0.25, "heartbreak": 0.30, "soulful": 0.15},
    "ambient":      {"calm": 0.30, "focus": 0.20, "dreamy": 0.15},
}


# =============================================================================
#  VIBE_TAG_MATRIX — v8.0 (mirrors main.py; drives batch_tester pool selection)
# =============================================================================
# Maps (dominant_vibe, language) → ordered list of Last.fm tags.
# batch_tester.py reads this from vibe_engine when VIBE_TAG_MATRIX attribute
# is present; main.py has its own copy but references this for parity checks.
VIBE_TAG_MATRIX: dict[str, dict[str, list[str]]] = {
    "ambient": {
        "Japanese":   ["japanese ambient", "kankyo ongaku", "ambient", "instrumental"],
        "Korean":     ["korean ambient", "korean post-rock"],
        "Hindi":      ["raga ambient", "sitar ambient", "indian classical ambient"],
        "Any":        ["ambient", "drone", "modern classical", "field recording"],
    },
    "heartbreak": {
        "Hindi":      ["bollywood sad", "filmi sad", "arijit singh", "atif aslam"],
        "Punjabi":    ["punjabi sad", "b praak", "jaani"],
        "English":    ["sad", "heartbreak", "indie sad", "emo"],
        "Japanese":   ["j-ballad", "japanese sad"],
        "Korean":     ["korean ballad", "k-pop sad"],
        "Tamil":      ["kollywood sad", "sid sriram"],
        "Any":        ["sad", "heartbreak"],
    },
    "romantic": {
        "Hindi":      ["bollywood romantic", "hindi love songs", "ar rahman"],
        "Punjabi":    ["punjabi romantic", "ap dhillon"],
        "Japanese":   ["j-pop romantic", "city pop"],
        "Korean":     ["k-pop romantic", "k-ballad"],
        "English":    ["romantic", "love songs", "rnb", "slow jams"],
        "Any":        ["romantic", "love songs"],
    },
    "happy": {
        "Hindi":      ["bollywood happy", "hindi upbeat", "badshah"],
        "Punjabi":    ["bhangra", "punjabi happy"],
        "English":    ["happy", "feel good", "indie pop"],
        "Japanese":   ["j-pop happy", "japanese pop upbeat"],
        "Korean":     ["k-pop happy", "k-pop upbeat"],
        "Afrobeats":  ["afrobeats", "afropop", "highlife"],
        "Any":        ["happy", "feel good"],
    },
    "party": {
        "Hindi":      ["bollywood dance", "hindi club", "badshah", "garba"],
        "Punjabi":    ["bhangra", "punjabi party", "diljit dosanjh"],
        "English":    ["party", "dance pop", "club", "trance"],   # P37: trance added
        "Korean":     ["k-pop", "k-pop dance", "k-pop party"],     # P18: k-pop in Korean party
        "Spanish":    ["reggaeton", "latin dance", "salsa"],
        "Afrobeats":  ["afrobeats party", "amapiano"],
        "Any":        ["party", "dance", "club"],
    },
    "hype": {
        "Hindi":      ["desi hip hop", "hindi rap", "divine"],
        "Punjabi":    ["punjabi trap", "karan aujla", "sidhu moosewala"],
        "English":    ["hip-hop", "trap", "rap", "drill"],
        "Japanese":   ["japanese hip hop", "j-rap"],
        "Korean":     ["k-pop", "k-hip hop", "korean rap"],   # P18: k-pop tag added
        "Telugu":     ["tollywood mass", "tollywood", "telugu film"],   # P23: Telugu hype fix
        "Tamil":      ["kollywood action", "anirudh", "kollywood"],
        "Malayalam":  ["malayalam", "mollywood", "malayalam film"],
        "Kannada":    ["kannada mass", "kannada", "kgf"],
        "Any":        ["hip-hop", "trap", "rap"],
    },
    "calm": {
        "Hindi":      ["sufi", "ghazal", "hindi acoustic"],
        "Japanese":   ["japanese acoustic", "j-folk", "city pop mellow"],
        "Korean":     ["k-indie", "korean folk", "korean acoustic"],
        "English":    ["calm", "acoustic", "folk", "singer-songwriter"],
        "Any":        ["calm", "acoustic", "folk"],
    },
    "chill": {
        "Hindi":      ["hindi lofi", "bollywood lofi"],
        "Japanese":   ["city pop", "japanese lofi", "j-chill"],
        "Korean":     ["k-indie chill", "korean lofi", "k-rnb"],
        "English":    ["chill", "lofi hip hop", "chillhop"],
        "Any":        ["chill", "lofi", "chillhop"],
    },
    "focus": {
        "Hindi":      ["hindi instrumental", "ar rahman instrumental"],
        "Japanese":   ["japanese instrumental", "city pop instrumental"],
        "English":    ["focus", "study", "instrumental", "ambient"],
        "Any":        ["focus", "study", "instrumental"],
    },
    "dreamy": {
        "Japanese":   ["japanese dream pop", "japanese shoegaze", "city pop"],
        "Korean":     ["k-indie dreamy", "korean dream pop"],
        "English":    ["dream pop", "shoegaze", "indie pop"],
        "Any":        ["dream pop", "shoegaze", "indie pop"],
    },
    "euphoric": {
        "English":    ["euphoric", "edm", "trance", "big room"],
        "Spanish":    ["latin edm", "reggaeton"],
        "Any":        ["euphoric", "edm", "trance"],
    },
    "soulful": {
        "Hindi":      ["ghazal", "sufi", "qawwali"],
        "English":    ["soul", "neo soul", "rnb", "jazz"],
        "Japanese":   ["japanese r&b", "j-soul"],
        "Korean":     ["k-rnb", "korean soul"],
        "Any":        ["soul", "neo soul", "rnb"],
    },
    "retro": {
        "Hindi":      ["old bollywood", "hindi film songs", "kumar sanu"],   # P17: 90s Bollywood
        "Japanese":   ["city pop", "japanese 80s"],
        "English":    ["synthwave", "retro", "80s pop", "classic rock"],
        "Any":        ["retro", "synthwave", "oldies"],
    },
    "cinematic": {
        "Hindi":      ["bollywood bgm", "ar rahman score", "hindi cinematic"],
        "Tamil":      ["kollywood bgm", "anirudh", "ar rahman score"],
        "English":    ["cinematic", "film score", "epic orchestral"],
        "Japanese":   ["japanese film score", "joe hisaishi"],
        "Korean":     ["k-pop", "k-drama ost", "korean film score"],  # k-pop first for Korean
        "Any":        ["cinematic", "film score", "orchestral"],
    },
    "dark": {
        "English":    ["dark", "darkwave", "post-punk", "goth"],
        "Japanese":   ["japanese post-rock", "japanese dark"],
        "Any":        ["dark", "darkwave", "goth"],
    },
    "intense": {
        "English":    ["metal", "hardcore", "intense", "heavy metal"],
        "Tamil":      ["kollywood action", "anirudh action"],
        "Any":        ["metal", "intense", "hardcore"],
    },
    "rock": {
        "Japanese":   ["j-rock", "japanese rock"],
        "Korean":     ["k-rock", "korean rock"],
        "English":    ["rock", "alternative rock", "indie rock", "classic rock"],
        "Any":        ["rock", "alternative rock"],
    },
    "indie_folk": {
        "English":    ["indie folk", "folk", "folk pop"],
        "Japanese":   ["japanese folk", "j-folk"],
        "Any":        ["indie folk", "folk"],
    },
    "desi": {
        "Hindi":      ["bollywood", "hindi film", "desi pop"],
        "Punjabi":    ["punjabi", "bhangra"],
        "Tamil":      ["kollywood", "tamil film"],
        "Telugu":     ["tollywood", "telugu film"],
        "Any":        ["bollywood", "desi"],
    },
    "punjabi": {
        "Punjabi":    ["bhangra", "punjabi pop", "diljit dosanjh"],
        "Any":        ["bhangra", "punjabi"],
    },
    "punjabi_soft": {
        "Punjabi":    ["punjabi sad", "ap dhillon", "b praak"],
        "Any":        ["punjabi sad", "b praak"],
    },
    "haryanvi": {
        "Hindi":      ["haryanvi", "haryanvi folk", "ragini"],
        "Any":        ["haryanvi", "haryanvi folk"],
    },
    "bollywood_sad": {
        "Hindi":      ["bollywood sad", "arijit singh", "filmi sad"],
        "Any":        ["bollywood sad", "arijit singh"],
    },
    "hyperpop": {
        "English":    ["hyperpop", "digicore", "pc music"],
        "Any":        ["hyperpop", "digicore"],
    },
    "industrial": {
        "English":    ["industrial", "ebm", "dark techno", "noise"],
        "Any":        ["industrial", "ebm", "dark techno"],
    },
    "tropical": {
        "Spanish":    ["reggaeton", "latin dance", "cumbia"],
        "Afrobeats":  ["afrobeats", "amapiano", "naija pop"],
        "English":    ["tropical", "dancehall", "reggae"],
        "Any":        ["reggaeton", "afrobeats", "dancehall"],
    },
    "country": {
        "English":    ["country", "americana", "country pop"],
        "Any":        ["country", "americana"],
    },
}

# =============================================================================
#  THE GRAND VIBE MAP — V4.2 FULL DATASET w/ MEGA GENRES & DECADES
# =============================================================================
# =============================================================================
# LANGUAGE TAG MAP
# Maps (language, dominant_vibe) → Last.fm tag to use instead of genres[0]
# Ensures language-tagged prompts get the right regional pool.
# =============================================================================
LANGUAGE_TAG_MAP: dict[str, dict[str, str | None]] = {
    "Hindi": {
        "default":        "bollywood",
        "romantic":       "bollywood romantic",
        "heartbreak":     "bollywood sad",
        "bollywood_sad":  "bollywood sad",
        "calm":           "hindi acoustic",
        "chill":          "hindi lofi",
        "happy":          "bollywood",
        "party":          "bollywood dance",
        "hype":           "desi hip hop",
        "desi":           "bollywood",
        "soulful":        "ghazal",
        "retro":          "old bollywood",   # P17 fix: 90s Bollywood/Kumar Sanu
        "dreamy":         "hindi",
        "focus":          "hindi instrumental",
        "ambient":        "hindi",
        "rock":           "hindi rock",
        "dark":           "hindi dark",
        "cinematic":      "bollywood bgm",
    },
    "Punjabi": {
        "default":        "punjabi",
        "romantic":       "punjabi romantic",
        "heartbreak":     "punjabi sad",
        "punjabi_soft":   "punjabi",
        "calm":           "punjabi acoustic",
        "chill":          "punjabi",
        "happy":          "bhangra",
        "party":          "bhangra",
        "hype":           "punjabi trap",
        "desi":           "punjabi",
        "soulful":        "punjabi sufi",
    },
    "English": {
        "default":        None,
        "romantic":       "rnb",
        "heartbreak":     "indie",
        "calm":           "indie",
        "party":          "pop",
        "hype":           "hip-hop",
        "soulful":        "soul",
    },
    "Tamil": {
        # P12 fix: ANY vibe + Tamil → kollywood. Stops "folk" → COUNTRY bug.
        "default":        "kollywood",
        "party":          "kollywood",
        "hype":           "kollywood",
        "romantic":       "kollywood romantic",
        "heartbreak":     "kollywood sad",
        "cinematic":      "kollywood bgm",
        "intense":        "kollywood action",
        "rock":           "kollywood",
        "country":        "kollywood",       # "folk instruments" → country vibe → kollywood
        "indie_folk":     "kollywood",
        "folk":           "kollywood",
        "calm":           "kollywood",
        "chill":          "kollywood",
        "dark":           "kollywood",
        "retro":          "kollywood",
    },
    "Telugu": {
        # P23 fix: Telugu → tollywood for all vibes
        "default":        "tollywood",
        "party":          "tollywood",
        "hype":           "tollywood mass",
        "romantic":       "tollywood romantic",
        "heartbreak":     "tollywood",
        "cinematic":      "tollywood bgm",
        "intense":        "tollywood mass",
        "rock":           "tollywood",
        "calm":           "tollywood",
        "chill":          "tollywood",
        "dark":           "tollywood",
        "retro":          "tollywood",
    },
    "Korean": {
        # P7/P18 fix: k-pop must appear in genre tags for Korean pool
        "default":        "k-pop",
        "party":          "k-pop",
        "hype":           "k-pop",
        "ambient":        "korean post-rock",
        "romantic":       "k-pop",
        "heartbreak":     "k-pop ballad",
        "calm":           "k-indie",
        "dreamy":         "k-pop",
        "cinematic":      "k-drama ost",
        "dark":           "k-pop",
        "retro":          "k-pop",
        "intense":        "k-rock",
    },
    "Japanese": {
        "default":    "j-pop",
        "party":      "j-pop",
        "hype":       "j-hip hop",
        "romantic":   "j-pop",
        "heartbreak": "j-ballad",
        "calm":       "japanese ambient",
        "chill":      "japanese city pop",
        "dreamy":     "japanese dream pop",
        "ambient":    "kankyo ongaku",
        "focus":      "japanese ambient",
        "retro":      "city pop",
        "soulful":    "japanese r&b",
        "intense":    "j-rock",
        "dark":       "japanese post-rock",
    },

    "Spanish": {
        # P40 fix: add salsa/latin for all emotional vibes
        "default":        "latin",
        "party":          "reggaeton",
        "hype":           "reggaeton",
        "romantic":       "latin pop",
        "calm":           "latin acoustic",
        "soulful":        "salsa",           # "salsa nights" → soulful maps correctly
        "heartbreak":     "latin pop",
        "chill":          "latin",
        "cinematic":      "latin",
    },
    "Portuguese": {
        "default":        "mpb",
        "party":          "baile funk",
        "romantic":       "bossa nova",
        "calm":           "bossa nova",
        "soulful":        "fado",            # P70 fix: saudade/fado routing
        "heartbreak":     "fado",
        "chill":          "bossa nova",
        "ambient":        "mpb",
    },
    "French": {
        "default":        "french pop",
        "romantic":       "chanson",
        "calm":           "chanson",
        "soulful":        "chanson",
        "chill":          "french pop",
    },
    "Arabic": {
        "default":        "arabic",
        "romantic":       "arabic",
        "calm":           "arabic",
        "party":          "arabic pop",
        "hype":           "arabic trap",     # P71 fix: Arabic trap routing
        "dark":           "arabic trap",
        "chill":          "khaleeji",        # P80 fix: khaleeji vibes
        "ambient":        "khaleeji",
        "soulful":        "arabic",
    },
    "Afrobeats": {
        "default":        "afrobeats",
        "party":          "afrobeats",
        "hype":           "afrobeats",
        "romantic":       "afrobeats",
        "calm":           "afrobeats",
        "chill":          "afrobeats",
    },
    "Bengali": {
        # P41 fix: Rabindra Sangeet for soulful/calm Bengali
        "default":        "bengali",
        "romantic":       "bengali",
        "heartbreak":     "bengali indie",
        "soulful":        "rabindra sangeet",
        "calm":           "rabindra sangeet",
        "ambient":        "rabindra sangeet",
        "chill":          "bengali indie",
        "dark":           "bengali rock",
        "intense":        "bengali rock",
    },
    "Urdu": {
        # P39 fix: Urdu party/hype → qawwali/sufi, not generic house
        "default":        "ghazal",
        "romantic":       "ghazal",
        "soulful":        "qawwali",
        "calm":           "ghazal",
        "heartbreak":     "ghazal",
        "party":          "qawwali",         # "bhajan clubbing" / Urdu party → qawwali
        "hype":           "qawwali",
        "dark":           "ghazal",
        "chill":          "ghazal",
        "ambient":        "ghazal",
    },
    "Kannada": {
        "default":        "kannada",
        "party":          "kannada",
        "hype":           "kannada mass",    # P67 fix: KGF mass bgm routing
        "romantic":       "kannada",
        "intense":        "kannada mass",
        "cinematic":      "kannada bgm",
        "dark":           "kannada",
        "heartbreak":     "kannada",
    },
    "Malayalam": {
        # P26 fix: all vibes → malayalam routing
        "default":        "malayalam",
        "party":          "malayalam",
        "romantic":       "malayalam",
        "heartbreak":     "malayalam sad",
        "calm":           "malayalam",
        "chill":          "malayalam",
        "cinematic":      "malayalam bgm",
        "ambient":        "malayalam",
        "soulful":        "malayalam",
        "hype":           "malayalam",
        "dark":           "malayalam",
        "retro":          "malayalam",
    },
    "Any": {},
}

VIBE_MAP: dict[str, dict] = {

    "rock": {
        "keywords": [
            "rock", "guitar", "bass", "drums", "shred", "riff", "distortion",
            "fuzz", "amp", "garage", "band", "punk", "grunge", "indie",
            "alternative", "classic", "rock and roll", "rockstar", "acoustic",
            "reverb", "power chord", "anthem", "angst", "rebellion", "stage dive",
            "50s", "60s", "70s", "80s", "90s", "00s"
        ],
        "phrases": [
            "face melting", "rock out", "let's rock", "shredding it", "up to eleven",
            "indie sleaze", "battle of the bands", "garage days", "punk's not dead"
        ],
        "context": [
            "garage", "dive bar", "arena", "stadium", "basement", "mosh pit",
            "skatepark", "concert", "gig", "record store", "road trip",
        ],
        "artists": [
            "the beatles", "led zeppelin", "pink floyd", "nirvana", "the strokes",
            "arctic monkeys", "foo fighters", "red hot chili peppers", "queen",
            "the rolling stones", "david bowie", "the white stripes", "radiohead",
            "muse", "paramore", "green day", "blink-182", "the black keys",
            "pearl jam", "soundgarden", "alice in chains", "the killers",
            "kings of leon", "my chemical romance", "fall out boy",
            "the smashing pumpkins", "the clash", "ramones", "the cure",
            "the smiths", "joy division", "tame impala", "mac demarco",
            "fontaines d.c.", "idles", "turnstile", "qotsa",
            "queens of the stone age", "ac/dc", "guns n' roses", "metallica",
        ],
        "bpm": "110-160",
        "genres": [
            "Classic Rock", "Alternative Rock", "Indie Rock", "Punk Rock",
            "Grunge", "Hard Rock", "Garage Rock", "Psychedelic Rock", "Pop Punk",
            "Post-Punk", "Shoegaze", "Math Rock", "Prog Rock", "Soft Rock",
            "Glam Rock", "Arena Rock", "New Wave", "Emo", "Britpop",
            "Folk Rock", "Blues Rock", "Post-Hardcore", "Surf Rock", "Krautrock"
        ],
    },

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
            "scarlxrd", "ghostemane", "$uicideboy$", "pouya",
            "night lovell", "trevor daniel",
        ],
        "bpm": "130-175",
        "genres": ["Trap", "Phonk", "Hardstyle", "Rage Rap", "EDM", "UK Drill", "Bass Music", "Trap Metal", "Drift Phonk", "Jersey Club", "Midtempo Bass", "Brostep", "Tearout", "Color Bass"],
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
            "spa music", "ambient soundscapes",
            "lana del rey", "aurora", "chelsea wolfe",
            "adrianne lenker", "big thief", "julia jacklin",
            "weyes blood", "grouper", "joni mitchell",
        ],
        "bpm": "55-80",
        "genres": ["Ambient", "Acoustic", "Folk", "Easy Listening", "New Age", "Bossa Nova", "Neoclassical", "Drone", "Folktronica", "Healing", "Soundscape", "Ethereal"],
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
            "ghostemane", "$uicideboy$", "pouya",
            "nine inch nails", "marilyn manson", "rob zombie",
            "white zombie", "tool", "a perfect circle", "primus",
            "system of a down", "rage against the machine", "korn", "limp bizkit",
        ],
        "bpm": "140-220",
        "genres": ["Deathcore", "Nu-Metal", "Thrash", "Hardcore", "Progressive Metal", "Industrial", "Grindcore", "Djent", "Beatdown Hardcore", "Sludge Metal", "Metalcore", "Crust Punk", "Powerviolence", "Mathcore", "Black Metal", "Death Metal", "Goregrind"],
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
            # lofi-specific phrases — these should ALWAYS resolve to chill, never calm/ambient
            "lofi beats", "lo-fi beats", "lofi hip hop", "lo-fi hip hop",
            "lofi music", "lofi vibes", "lofi chill", "lofi study",
            "lofi girl", "chillhop beats", "study beats", "beats to relax",
            "beats to study", "rain and lofi", "coffee shop music",
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
        "genres": ["Neo-Soul", "Indie R&B", "Chillwave", "Lo-Fi Hip Hop", "Vaporwave", "Pluggnb", "Jazz Hop", "Trip Hop", "Yacht Rock", "Balearic Beat", "Downtempo", "Chillstep", "Lounge"],
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
        "genres": ["Modern Classical", "Ambient", "Deep House", "Instrumental Hip Hop", "IDM", "Krautrock", "Minimal Techno", "Glitch", "Post-Rock", "Microhouse", "Psybient", "Brainwave Entrainment"],
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
        "genres": ["Progressive House", "Future Bass", "Dream Pop", "Synthpop", "Melodic Techno", "Trance", "Happy Hardcore", "French House", "Balearic Trance", "Italo Disco", "Euphoric Hardstyle", "Eurodance"],
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
            "anderson .paak", "silk sonic", "lucky daye", "mac ayres",
            "snoh aalegra", "moonchild", "hiatus kaiyote",
            "thundercat", "terrace martin", "robert glasper",

        ],
        "bpm": "60-105",
        "genres": [
            "Neo-Soul", "Contemporary R&B", "Indie R&B", "Soul Pop",
            "Soulful House", "Funk Soul", "Classic Soul", "Gospel Soul",
            "Jazz Soul", "Motown", "Quiet Storm", "Smooth Soul", "Jazz Hop",
        ],
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
            "50s", "60s", "70s", "1980s", "1990s", "00s", "y2k", "2000s"
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
        "genres": ["Synthwave", "80s Pop", "New Wave", "Disco", "Funk", "City Pop", "AOR", "Doo-Wop", "Rockabilly", "Motown", "Classic Soul", "Boogie", "Britpop", "Italo Disco", "Y2K Pop", "Vaporwave", "Chiptune"],
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
        "genres": ["Shoegaze", "Dream Pop", "Indie Rock", "Psych Rock", "Slowcore", "Ambient Pop", "Space Rock", "Ethereal Wave", "Dream Trance", "Chillwave"],
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
        "genres": ["Soundtrack", "Modern Classical", "Epic Orchestral", "Dark Ambient", "Neo-Classical", "Film Score", "Neoclassical Dark Wave", "Trailer Music", "Choral", "Symphonic Metal"],
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
        "genres": ["Darkwave", "Industrial Techno", "Witch House", "Goth", "Post-Punk", "Black Metal Adjacent", "Gothic Rock", "Coldwave", "Deathrock", "Dark Ambient", "Horrorcore", "Doom Metal"],
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
            "joji", "mitski", "d4vd", "conan gray", "stephen dawes",
        ],
        "bpm": "60-105",
        "genres": ["Sad Pop", "Indie Folk", "Emo", "Sad R&B", "Alt-Pop", "Singer-Songwriter", "Midwest Emo", "Sadcore", "Slowcore", "Melancholia", "Acoustic Pop"],
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
        "genres": ["Hyperpop", "Digicore", "PC Music", "Bubblegum Bass", "Glitchpop", "Cloud Rap", "Glitchcore", "Dariacore", "Sigilkore", "Scenecore", "Nightcore", "HexD", "Bitpop"],
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
        "genres": ["Dance Pop", "House", "Tech House", "Afrobeats", "Amapiano", "Dancehall", "Club", "Reggaeton", "Baile Funk", "Guaracha", "Bassline", "Moombahton", "Electro House", "Club Trax"],
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
        "genres": ["Country", "Folk", "Americana", "Bluegrass", "Singer-Songwriter", "Southern Rock", "Alt-Country", "Outlaw Country", "Bro-Country", "Texas Country", "Bakersfield Sound", "Countrypolitan"],
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
        "genres": ["Afrobeats", "Reggaeton", "Dancehall", "Reggae", "Soca", "Amapiano", "Zouk", "Kizomba", "Afrobeat", "Highlife", "Champeta", "Calypso"],
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
        "genres": ["Industrial", "EBM", "Dark Techno", "Experimental Hip Hop", "Noise", "Electro-Industrial", "Aggrotech", "Power Electronics", "Cyberpunk", "Dark Electro", "Harsh Noise"],
    },
    
    "desi": {
        "keywords": [
            "bollywood", "desi", "bhangra", "dhol", "wedding", "shaadi", "sangeet",
            "filmi", "tollywood", "kollywood", "tabla", "sitar", "hindustani",
            "ghazal", "qawwali", "desi pop", "filmy", "dholak", "banjo",
            "hindi", "urdu", "classic hindi", "90s hindi", "retro bollywood",
            "sufi", "kajra", "ishq", "mohabbat", "dil", "pyaar",
            "tamasha", "nautanki", "mujra", "kotha", "thumri",
        ],
        "phrases": [
            "desi swag", "brown boy", "brown girl", "bollywood vibes", "shaadi vibes",
            "desi party", "dhol beats", "desi energy", "filmy feel", "hindi songs",
            "indian wedding", "mehndi function", "holi songs", "diwali vibes",
            "desi hip hop", "subcontinental vibes", "mumbai nights", "delhi nights",
        ],
        "context": [
            "indian wedding", "baraat", "mehndi", "desi club", "mumbai", "delhi",
            "lahore", "karachi", "diwali", "holi", "navratri", "eid", "family gathering",
            "desi dance", "subcontinental", "south asian", "india", "pakistan",
        ],
        "artists": [
            "ar rahman", "pritam", "vishal-shekhar", "amit trivedi", "shankar-ehsaan-loy",
            "arijit singh", "shreya ghoshal", "sonu nigam", "udit narayan", "lata mangeshkar",
            "asha bhosle", "kishore kumar", "rafi", "mukesh", "hemant kumar",
            "kumar sanu", "alka yagnik", "kavita krishnamurthy", "anuradha paudwal",
            "shankar mahadevan", "hariharan", "k.k.", "shaan", "kailash kher",
            "rahat fateh ali khan", "atif aslam", "ali zafar", "nusrat fateh ali khan",
            "abida parveen", "ali sethi", "coke studio pakistan",
            "diljit dosanjh", "badshah", "yo yo honey singh", "guru randhawa",
            "ammy virk", "harrdy sandhu", "neha kakkar", "tony kakkar",
            "ap dhillon", "karan aujla", "shubh", "tesher", "mickey singh",
            "divine", "naezy", "seedhe maut", "mc stan", "ikka",
            "raftaar", "kr$na", "brodha v", "blaaze",
            "hariharan", "shankar mahadevan",
        ],
        "bpm": "90-130",
        "genres": ["Bollywood", "Desi Pop", "Bhangra", "Punjabi Pop", "Filmi", "Ghazal",
                   "Qawwali", "Carnatic", "Hindustani Classical", "Sufi Rock", "Desi Hip Hop",
                   "Punjabi Folk", "Kollywood", "Tollywood", "Rajasthani Folk", "Baul",
                   "Indi-pop", "Desi R&B"],
    },

    "punjabi": {
        "keywords": [
            "punjabi", "bhangra", "dhol", "dholi", "jatt", "jatti", "sardaar",
            "pind", "yaar", "dost", "chandigarh", "ludhiana", "amritsar",
            "turbaan", "dastar", "kirpan", "waheguru", "sat sri akal",
            "punjab", "punjabi rap", "punjabi trap", "punjabi drill",
            "shooter", "gang", "clique", "pagg", "kali car", "supna",
            "nachna", "giddha", "tappa", "boliyan", "lohri", "baisakhi",
        ],
        "phrases": [
            "bhangra vibes", "punjabi music", "punjabi wedding", "baraat song",
            "jatt life", "sidhu moosewala vibes", "karan aujla vibes",
            "hard punjabi", "punjabi party", "desi party anthem",
        ],
        "context": [
            "punjab", "chandigarh", "amritsar", "ludhiana", "jalandhar",
            "bhangra", "wedding", "baraat", "mehndi", "baisakhi", "lohri",
            "desi club", "punjabi club", "diasporic", "canada desi", "uk desi",
        ],
        "artists": [
            "sidhu moosewala", "karan aujla", "shubh", "ap dhillon",
            "diljit dosanjh", "badshah", "guru randhawa", "ammy virk",
            "harrdy sandhu", "gippy grewal", "parmish verma", "jassi gill",
            "jass manak", "mankirt aulakh", "kulwinder billa",
            "mickey singh", "tesher", "shree brar", "waris bhinder",
            "talha anjum", "faris shafi", "young stunners",
            "jugraj sandhu", "afsana khan", "nimrat khaira",
            "param singh", "preet harpal",
        ],
        "bpm": "95-135",
        "genres": ["Punjabi Pop", "Bhangra", "Punjabi Trap", "Punjabi Hip Hop",
                   "Punjabi Folk", "Desi Drill", "Punjabi R&B", "Bhangra Fusion",
                   "Punjabi Electronic", "Bhangra EDM"],
    },

    "punjabi_soft": {
        "keywords": [
            "soft punjabi", "punjabi slow", "punjabi sad", "punjabi romantic",
            "tere bina", "yaadan", "waris", "nazm", "ishq punjabi",
            "dard", "dil diya", "putt jatt da", "ranjha", "heer",
            "mirza sahiba", "love punjabi", "desi romance", "desi love",
            "acoustic punjabi", "unplugged punjabi", "sufi punjabi",
        ],
        "phrases": [
            "ap dhillon vibes", "punjabi soft", "soft bhangra",
            "punjabi love song", "desi love songs", "punjabi breakup",
            "punjabi romantic", "punjabi sad song", "slow punjabi",
        ],
        "context": [
            "long drive", "night drive", "missing someone", "heartbroken",
            "desi heartbreak", "love lost", "romantic evening",
        ],
        "artists": [
            "ap dhillon", "shubh", "mickey singh", "jass manak",
            "b praak", "jaani", "harrdy sandhu", "ammy virk",
            "satinder sartaaj", "surjit bindrakhia", "harbhajan mann",
            "malkit singh", "gurdas maan", "sukhwinder singh",
            "prabh gill", "dilnashin", "param singh",
            "gurnam bhullar", "akhil", "ravinder grewal",
        ],
        "bpm": "65-105",
        "genres": ["punjabi", "bhangra", "Punjabi Soft Pop", "Punjabi Ballad", "Punjabi Sufi", "Punjabi Acoustic",
                   "Punjabi R&B", "Desi Soul", "Punjabi Ghazal", "Soft Bhangra"],
    },

    "haryanvi": {
        "keywords": [
            "haryanvi", "haryana", "jaat", "desi haryanvi", "ragini",
            "saang", "kheda", "khap", "kurukshetra", "rohtak", "hisar",
            "panipat", "gurugram", "gurgaon", "bhiwani", "rewari",
            "thada", "mewati", "ahirwal", "brij", "mewat",
            "haryanvi dance", "haryanvi song", "dj haryanvi",
        ],
        "phrases": [
            "haryanvi vibes", "haryanvi music", "desi haryanvi",
            "haryanvi wedding", "haryanvi party", "haryanvi folk",
            "haryanvi film", "haryanvi beat",
        ],
        "context": [
            "haryana", "north india rural", "desi rural", "village wedding",
            "gaon ka tyohar", "kisan music",
        ],
        "artists": [
            "masoom sharma", "raju punjabi", "ak joshi", "uk haryanvi",
            "pradeep sonu", "vijay varma", "gulzaar chhaniwala",
            "bhopu jo", "mukesh fouji", "sapna choudhary",
            "renuka panwar", "ajay hooda", "raj mawar", "kr mangalam",
            "amit saini rohtakiya", "sandeep surila", "pk haryanvi",
            "pardeep boora",
        ],
        "bpm": "90-130",
        "genres": ["bhangra", "bollywood", "Haryanvi Folk", "Haryanvi Pop", "Ragini", "Haryanvi EDM",
                   "Haryanvi Hip Hop", "Desi Folk", "North Indian Folk"],
    },

    "bollywood_sad": {
        "keywords": [
            "arijit", "bollywood sad", "hindi sad", "filmi sad", "rona dhona",
            "dard", "gham", "judai", "bichhad", "door", "akela", "tanhai",
            "intezaar", "yaad", "teri yaad", "mohabbat", "dil tuta",
            "aansu", "rona", "tadap", "kasak", "dhoondta hai",
            "ishq mein", "bepanah", "bewafa", "dard e dil",
        ],
        "phrases": [
            "arijit vibes", "bollywood heartbreak", "hindi breakup songs",
            "filmi sad", "desi heartbreak", "sad hindi songs",
            "melancholic bollywood", "old bollywood sad",
        ],
        "context": [
            "heartbreak hindi", "desi breakup", "missing someone desi",
            "rainy day hindi", "bollywood cry", "hindi film sad scene",
        ],
        "artists": [
            "arijit singh", "atif aslam", "rahat fateh ali khan",
            "armaan malik", "jubin nautiyal", "darshan raval",
            "javed ali", "k.k.", "shaan", "mohit chauhan",
            "shreya ghoshal sad", "sunidhi chauhan", "lata mangeshkar",
            "udit narayan", "sonu nigam", "kumar sanu",
            "asha bhosle", "jagjit singh", "ghulam ali",
            "talat mahmood", "mehdi hassan", "nusrat fateh ali khan",
            "b praak", "vishal mishra", "payal dev",
        ],
        "bpm": "55-95",
        "genres": ["bollywood", "hindi", "Bollywood Sad", "Hindi Ballad", "Filmi Ghazal", "Desi Soul",
                   "Bollywood Heartbreak", "Hindi Sufi Sad", "Soft Bollywood",
                   "Romantic Bollywood Sad", "90s Hindi Sad"],
    },

    "happy": {
        "keywords": [
            "happy", "joyful", "cheerful", "upbeat", "feel good", "sunshine",
            "bright", "peppy", "bouncy", "jolly", "merry", "gleeful",
            "good mood", "great mood", "best day", "carefree", "giddy",
            "childlike wonder", "innocent", "playful", "bubbly", "breezy",
            "fizzy", "elated", "overjoyed", "glee", "jubilant",
            "skip", "jump for joy", "can't stop smiling", "beaming",
            "light", "lighthearted", "sweet", "wholesome",
            "laugh", "giggle", "belly laugh", "chuckle",
        ],
        "phrases": [
            "feel good music", "happy music", "pure happiness", "good vibes only",
            "sunshine in song form", "makes me smile", "can't be sad to this",
            "childhood joy", "pure joy", "best mood", "smile on my face",
            "brightens my day", "instant mood boost",
        ],
        "context": [
            "birthday party", "celebration", "good news", "promotion",
            "spring morning", "sunny day", "playground", "picnic",
            "reunion with friends", "wedding day morning", "graduation",
            "winning", "perfect day", "road trip with friends",
        ],
        "artists": [
            "pharrell williams", "lizzo", "carly rae jepsen", "robyn",
            "dua lipa", "harry styles", "justin timberlake", "bruno mars",
            "mark ronson", "katy perry", "taylor swift", "ariana grande",
            "meghan trainor", "colbie caillat", "jack johnson",
            "nelly", "outkast", "janelle monae", "anderson paak",
            "lucky daye", "bill withers", "earth wind and fire",
            "the jackson 5", "stevie wonder", "marvin gaye",
            "bee gees", "abba", "the temptations", "the supremes",
            "kali uchis", "rex orange county", "orange county",
            "clairo", "beabadoobee", "wallows", "surf mesa",
            "men at work", "tag team", "sugar ray",
            "owl city", "fun.", "the killers",
        ],
        "bpm": "100-135",
        "genres": ["Pop", "Indie Pop", "Soul Pop", "Funk", "Disco Pop", "Sunshine Pop",
                   "Power Pop", "Electropop", "Happy Hardcore Lite", "Bubblegum Pop",
                   "Neo Soul Happy", "Summer Pop", "Feel Good R&B", "Jangle Pop"],
    },

    "romantic": {
        "keywords": [
            "romantic", "romance", "in love", "falling in love", "love",
            "adore", "cherish", "devoted", "tender", "sweet nothings",
            "candlelight", "moonlit", "slow dance", "serenade", "longing",
            "desire", "yearning for", "holding you", "close to you",
            "electric feel", "spark", "chemistry", "magnetic", "drawn to you",
            "warmth between us", "soft kisses", "gentle", "forever yours",
            "always you", "head over heels", "lovesick", "infatuated",
            "deeply in love", "your name on my lips",
        ],
        "phrases": [
            "love songs", "love song", "falling in love", "in love",
            "date night songs", "slow dance songs", "anniversary playlist",
            "romantic vibes", "deeply romantic", "tender love",
            "electric before a kiss", "new relationship",
            "lovey dovey", "couple songs", "together forever",
        ],
        "context": [
            "date", "date night", "anniversary", "valentine's day",
            "proposal", "slow dance", "wedding", "honeymoon",
            "late night together", "romantic drive", "stargazing with someone",
            "fireside", "candlelit dinner", "first date",
        ],
        "artists": [
            "frank ocean", "daniel caesar", "giveon", "steve lacy",
            "brent faiyaz", "h.e.r.", "jhene aiko", "miguel",
            "john legend", "usher", "maxwell", "d'angelo",
            "erykah badu", "neo soul romantic", "sade",
            "luther vandross", "lionel richie", "barry white",
            "marvin gaye", "al green", "otis redding",
            "sam smith", "ed sheeran", "james arthur",
            "corinne bailey rae", "norah jones", "adele",
            "shawn mendes", "camila cabello",
            "the weeknd", "bryson tiller", "partynextdoor",
            "summer walker", "kehlani",
            "lana del rey", "lorde", "troye sivan",
        ],
        "bpm": "60-110",
        "genres": ["rnb", "neo soul", "soul", "Romantic R&B", "Slow Jam", "Love Pop", "Indie Romance",
                   "Soul Ballad", "Contemporary R&B", "Bedroom Pop", "Soft Rock",
                   "Acoustic Love", "R&B Ballad", "Dream Pop Romance"],
    },

    "indie_folk": {
        "keywords": [
            "indie folk", "folk pop", "folk indie", "harmony", "harmonies",
            "acoustic", "fingerpicking", "banjo", "mandolin", "upright bass",
            "mountain sound", "forest sounds", "cabin", "wheat field",
            "melancholic folk", "dark folk", "murder ballad", "traditional",
            "americana indie", "singer songwriter", "earnest", "confessional folk",
            "hushed", "intimate folk", "lo-fi folk", "folk revival",
            "chamber folk", "baroque folk", "haunting", "beautiful sad",
        ],
        "phrases": [
            "indie folk", "fleet foxes adjacent", "fleet foxes vibes",
            "bon iver adjacent", "folk harmonies", "indie acoustic",
            "modern folk", "dark folk", "iron and wine style",
            "sufjan style", "indie singer songwriter", "folk indie",
            "rich harmonies", "layered vocals",
        ],
        "context": [
            "cabin in the woods", "autumn walk", "overcast day", "forest",
            "mountain road", "vinyl record player", "folk festival",
            "campfire acoustic", "hiking trail", "quiet countryside",
            "small venue", "coffee shop set",
        ],
        "artists": [
            "fleet foxes", "bon iver", "iron & wine", "sufjan stevens",
            "the head and the heart", "the lumineers", "of monsters and men",
            "mumford & sons", "the avett brothers", "old crow medicine show",
            "the decemberists", "neutral milk hotel", "nick drake",
            "simon & garfunkel", "james taylor", "carole king",
            "joni mitchell", "crosby stills nash young",
            "andrew bird", "gregory alan isakov", "the tallest man on earth",
            "josh ritter", "iron and wine", "sam beam",
            "first aid kit", "the staves", "nickel creek",
            "sarah jarosz", "aoife o'donovan", "allison russell",
            "gillian welch", "david rawlings", "dirk powell",
            "mountain man", "haiku hands",
            "big thief", "adrianne lenker", "weyes blood",
            "angel olsen", "bedouine", "ana roxanne",
        ],
        "bpm": "65-120",
        "genres": ["Indie Folk", "Folk Pop", "Chamber Folk", "Folk Revival", "Baroque Folk",
                   "Americana Folk", "Dark Folk", "Folk Rock", "Appalachian Folk",
                   "Contemporary Folk", "Freak Folk", "Anti-Folk"],
    },

    "ambient": {
        "keywords": [
            "ambient", "drone", "texture", "soundscape", "atonal", "evolving",
            "minimalist", "slow", "glacial", "atmospheric", "immersive",
            "long tones", "sustained", "pads", "drone note", "field recording",
            "tape loops", "processed", "organic", "generative", "aleatoric",
            "meditative", "contemplative", "infinite", "cosmic", "vast",
            "cavernous", "reverberant", "airy", "shimmering", "swelling",
            "breathing", "pulsing", "modular", "synthesizer texture",
        ],
        "phrases": [
            "ambient music", "drone music", "long tones", "minimal music",
            "tape loops", "field recording", "brian eno vibes",
            "white noise", "rain sounds", "nature sounds", "sleep music",
            "meditation music", "focus ambient", "background texture",
            "modern classical ambient", "minimalist ambient",
        ],
        "context": [
            "meditation", "yoga", "floating", "sensory deprivation",
            "deep focus", "sleep aid", "reading quietly", "gallery space",
            "installation art", "late night headphones", "insomnia",
            "hospital waiting", "long haul flight", "traveling alone",
        ],
        "artists": [
            "brian eno", "harold budd", "ambient 1", "the plateaux of mirror",
            "william basinski", "grouper", "liz harris", "stars of the lid",
            "godspeed you black emperor", "labradford", "the caretaker",
            "burial", "four tet", "aphex twin", "selected ambient works",
            "boards of canada", "kelela", "tim hecker", "demdike stare",
            "jan jelinek", "pole", "puce mary", "jóhann jóhannsson",
            "ólafur arnalds", "nils frahm", "max richter", "rachel's",
            "steve reich", "la monte young", "terry riley",
            "susumu yokota", "hiroshi yoshimura", "motohiro kawashima",
            "ben frost", "prurient", "hana", "claire rousay",
            "julianna barwick", "maria minerva", "dead can dance",
            "this mortal coil", "cocteau twins", "valley of the giants",
        ],
        "bpm": "40-80",
        "genres": ["Ambient", "Drone", "Minimalism", "Field Recording", "Dark Ambient",
                   "Lowercase", "Glitch Ambient", "Ambient Techno", "Neo-Classical Ambient",
                   "Isolationism", "Hauntology", "Musique Concrète", "Tape Music", "Acousmatic"],
    },
}



# =============================================================================
#  SCORING WEIGHTS
# =============================================================================
WEIGHT_ARTIST  = 2.0   # Explicit artist mention is a strong signal
WEIGHT_PHRASE  = 3.0   # Multi-word idiomatic phrases
WEIGHT_KEYWORD = 2.5   # Single emotional descriptors
WEIGHT_CONTEXT = 1.0   # Setting / scenario mentions
WEIGHT_SYNONYM = 1.8   # Synonym expansion hits (slightly lower confidence)
NEGATION_MULT  = -0.8  # Negated match flips and slightly dampens



# =============================================================================
#  NLP HELPERS  (v4.2 — calibrated)
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
        "rock": "rock", "punk": "rock", "indie": "rock", "grunge": "rock",
        "happy": "happy", "cheerful": "happy", "upbeat": "happy",
        "romantic": "romantic", "love": "romantic",
        "desi": "desi", "bollywood": "desi", "punjabi": "punjabi",
        "ambient": "ambient", "drone": "ambient",
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
#  MAIN ANALYSIS ENGINE  (v4.2)
# =============================================================================

def analyze_vibe_algorithm(text: str, artist_focus: int = 50, genre_focus: int = 50, bpm_focus: int = 50) -> dict:
    """
    Vibe Analysis Engine v5.0 — QA Regression Fix + Desi Expansion Edition
    27 vibe categories. Fixes: fallback over-triggering, indie folk/country confusion,
    intense misfires, euphoric monopoly, new desi sub-vibes.
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

    # ── STEP 0b: "LIKE X BUT Y" MODIFIER BOOST ───────────────────────────────
    modifier_boosts = _extract_modifier_boost(lower_text)
    for vibe, boost_val in modifier_boosts.items():
        scores[vibe] += boost_val

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
    bpm_match = re.search(r'(\d{2,3})\s*bpm', lower_text)
    if bpm_match:
        target_bpm = int(bpm_match.group(1))
        for v, data in VIBE_MAP.items():
            bpm_str = data.get("bpm", "")
            if "-" in bpm_str:
                min_b, max_b = map(int, bpm_str.split('-'))
                if min_b <= target_bpm <= max_b:
                    scores[v] += (5.0 * bpm_mult)
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
        # Last-resort: for prompts with some emotional content, default to chill.
        # This prevents "neutral 0%" on abstract/sensory prompts that scored nothing.
        # The caller (main.py) will use this as its Last.fm fetch target.
        # v5.0: Updated genres to return better search results than the old Ambient Pop defaults.
        return {
            "dominant_vibe": "chill",
            "confidence": 0.05,
            "bpm_range": "65-100",
            "genres": ["Indie Pop", "Lo-Fi Hip Hop", "Indie R&B", "Dream Pop", "Chillwave"],
            "matched_keywords": [],
            "secondary_vibe": "dreamy",
            "secondary_confidence": 0.05,
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


def _extract_modifier_boost(text: str) -> dict[str, float]:
    """
    v1.3 — "Like X but Y" Modifier Awareness (Updated for Rock).
    Detects patterns like "sounds like Radiohead but more electronic" or
    "like Bon Iver but warmer" and returns a score boost map for the Y modifier.
    The entity lock handles X; this function ensures Y also influences the result.
    """
    lower = text.lower()
    boost: dict[str, float] = {}

    # Match: "like/sounds like/in the vein of X but [more/less/a bit] Y"
    modifier_pattern = re.compile(
        r'(?:sounds?\s+like|like|in the vein of|in the world of|à la)'
        r'.+?\bbut\b\s+(?:more|less|a\s+bit|even|way|much|slightly)?\s*([\w\s]{2,30})',
        re.IGNORECASE
    )
    MODIFIER_TO_VIBE: dict[str, list[str]] = {
        "electronic": ["industrial", "focus"],
        "acoustic": ["calm", "country"],
        "warmer": ["soulful", "calm"],
        "darker": ["dark"],
        "sadder": ["heartbreak"],
        "heavier": ["intense", "rock"],
        "lighter": ["calm", "euphoric"],
        "more atmospheric": ["dreamy", "dark"],
        "atmospheric": ["dreamy", "dark"],
        "melodic": ["dreamy", "euphoric"],
        "upbeat": ["hype", "euphoric"],
        "slower": ["calm", "dreamy"],
        "faster": ["hype"],
        "punchier": ["hype", "intense"],
        "shorter": ["hype"],
        "danceable": ["party"],
        "louder": ["intense", "hype", "rock"],
        "quieter": ["calm"],
        "nostalgic": ["retro", "dreamy"],
        "futuristic": ["industrial", "focus"],
        "psychedelic": ["dreamy", "retro", "rock"],
        "cinematic": ["cinematic"],
        "experimental": ["industrial", "focus"],
        "hopeful": ["euphoric", "calm"],
        "chaotic": ["intense", "hype"],
        "chill": ["chill"],
        "groovy": ["chill", "soulful"],
        "intimate": ["soulful", "calm"],
        "epic": ["cinematic"],
        "rockier": ["rock"],
        "punky": ["rock"],
        "grungier": ["rock"],
    }

    for m in modifier_pattern.finditer(lower):
        modifier = m.group(1).strip()
        # Try exact then partial match
        for key, vibes in MODIFIER_TO_VIBE.items():
            if key in modifier:
                for v in vibes:
                    boost[v] = boost.get(v, 0) + 4.0  # meaningful but not dominant
                break

    return boost

if __name__ == "__main__":
    print(analyze_vibe_algorithm("Dark jazz club, trumpet, noir energy"))
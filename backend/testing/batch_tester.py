import asyncio
import logging
import re
from prisma import Prisma

# Import the core brains directly (bypassing FastAPI)
import vibe_engine
from backend.main_old import (
    fetch_lastfm_tracks,
    fetch_lastfm_artist_tracks,
    fetch_lastfm_track_search,
    filter_and_score_tracks,
    VibeRequest,
    COMMON_WORDS_BLACKLIST,
    TRACK_BLOCKLIST,
)

# ---------------------------------------------------------
# 1000 PROMPTS — v5.0 "LIMIT BREAKER" STRESS TEST SUITE
# ---------------------------------------------------------
# Completely overhauled to test the new Desi, Happy, Romantic,
# Indie Folk, and Ambient vectors. Includes messy typos, 
# oxymorons, Gen-Z brain rot, and paragraph-long scenarios.
# ---------------------------------------------------------

# ══════════════════════════════════════════════════════════════════
# PROMPTS v7.0 — LANGUAGE-AWARE LIMIT BREAKER STRESS SUITE
# 1008 prompts across 15 vectors: Desi, Heartbreak, Romantic, Hype,
# Chill, Party, Calm, Dreamy, Intense, Retro, Folk, Global, Emotional
# Scenes, Typo/Gibberish, Abstract Edge Cases.
# Each prompt carries a language tag for LANGUAGE_TAG_MAP routing.
# ══════════════════════════════════════════════════════════════════
PROMPTS = [
    {"text": "bhangra night", "language": "Punjabi"},  # Punjabi
    {"text": "sangeet dance practice", "language": "Punjabi"},  # Punjabi
    {"text": "hard punjabi trap", "language": "Punjabi"},  # Punjabi
    {"text": "drunk uncle dancing to dhol", "language": "Punjabi"},  # Punjabi
    {"text": "haryanvi dj song", "language": "Hindi"},  # Hindi
    {"text": "baraat entering the venue", "language": "Punjabi"},  # Punjabi
    {"text": "desi club night in toronto", "language": "Hindi"},  # Hindi
    {"text": "ap dhillon concert hype", "language": "Punjabi"},  # Punjabi
    {"text": "punjabi wedding bangers", "language": "Punjabi"},  # Punjabi
    {"text": "shaadi vibes", "language": "Punjabi"},  # Punjabi
    {"text": "desi swag", "language": "Hindi"},  # Hindi
    {"text": "brown boy energy", "language": "Hindi"},  # Hindi
    {"text": "brown girl going out", "language": "Hindi"},  # Hindi
    {"text": "dhol beats for mehndi", "language": "Punjabi"},  # Punjabi
    {"text": "navratri garba night", "language": "Any"},
    {"text": "diwali party playlist", "language": "Any"},
    {"text": "holi water fight", "language": "Any"},
    {"text": "sidhu moosewala fast drive", "language": "Punjabi"},  # Punjabi
    {"text": "karan aujla gym playlist", "language": "Punjabi"},  # Punjabi
    {"text": "desi hip hop hard", "language": "Hindi"},  # Hindi
    {"text": "giddha performance", "language": "Punjabi"},  # Punjabi
    {"text": "village wedding in haryana", "language": "Hindi"},  # Hindi
    {"text": "ragini music", "language": "Hindi"},  # Hindi
    {"text": "haryanvi beat thada", "language": "Hindi"},  # Hindi
    {"text": "sangeet night group dance", "language": "Punjabi"},  # Punjabi
    {"text": "desi party anthem", "language": "Hindi"},  # Hindi
    {"text": "desi summer vibes", "language": "Hindi"},  # Hindi
    {"text": "desi festival", "language": "Hindi"},  # Hindi
    {"text": "desi club trax", "language": "Hindi"},  # Hindi
    {"text": "bollywood item songs", "language": "Hindi"},  # Hindi
    {"text": "retro bollywood dance", "language": "Hindi"},  # Hindi
    {"text": "punjabi bass boosted", "language": "Punjabi"},  # Punjabi
    {"text": "haryanvi bass boosted", "language": "Hindi"},  # Hindi
    {"text": "punjabi diaspora party", "language": "Punjabi"},  # Punjabi
    {"text": "desi drill music", "language": "Hindi"},  # Hindi
    {"text": "bhangra fusion edm", "language": "Punjabi"},  # Punjabi
    {"text": "desi wedding reception", "language": "Hindi"},  # Hindi
    {"text": "dhol tasha procession", "language": "Punjabi"},  # Punjabi
    {"text": "haryanvi swag", "language": "Hindi"},  # Hindi
    {"text": "rohtak boys anthem", "language": "Hindi"},  # Hindi
    {"text": "patiala shahi", "language": "Any"},
    {"text": "jatt flex", "language": "Punjabi"},  # Punjabi
    {"text": "desi energy unhinged", "language": "Hindi"},  # Hindi
    {"text": "uk desi scene", "language": "Hindi"},  # Hindi
    {"text": "desi rural hype", "language": "Hindi"},  # Hindi
    {"text": "bhangra at 3am", "language": "Punjabi"},  # Punjabi
    {"text": "punjabi drill dark", "language": "Punjabi"},  # Punjabi
    {"text": "ap dhillon sad voice", "language": "Punjabi"},  # Punjabi
    {"text": "b praak heartbreak hindi", "language": "Hindi"},  # Hindi
    {"text": "arijit singh romantic", "language": "Hindi"},  # Hindi
    {"text": "atif aslam sad", "language": "Hindi"},  # Hindi
    {"text": "armaan malik love song", "language": "Hindi"},  # Hindi
    {"text": "neha kakkar dance", "language": "Hindi"},  # Hindi
    {"text": "badshah party", "language": "Hindi"},  # Hindi
    {"text": "yo yo honey singh classic", "language": "Hindi"},  # Hindi
    {"text": "bollywood sad songs 2020s", "language": "Hindi"},  # Hindi
    {"text": "old bollywood ghazal", "language": "Hindi"},  # Hindi
    {"text": "kishore kumar nostalgic", "language": "Any"},
    {"text": "lata mangeshkar classic", "language": "Any"},
    {"text": "filmi sad 90s", "language": "Hindi"},  # Hindi
    {"text": "rona dhona songs", "language": "Any"},
    {"text": "ishq wala love hindi", "language": "Hindi"},  # Hindi
    {"text": "sufi qawwali night", "language": "Hindi"},  # Hindi
    {"text": "nusrat fateh ali khan", "language": "Any"},
    {"text": "rahat fateh ali khan", "language": "Any"},
    {"text": "hindi lofi beats", "language": "Hindi"},  # Hindi
    {"text": "bollywood lo-fi chill", "language": "Hindi"},  # Hindi
    {"text": "desi chill night", "language": "Hindi"},  # Hindi
    {"text": "satinder sartaaj soulful", "language": "Any"},
    {"text": "punjabi soft romantic", "language": "Punjabi"},  # Punjabi
    {"text": "jubin nautiyal sad", "language": "Hindi"},  # Hindi
    {"text": "shreya ghoshal emotional", "language": "Any"},
    {"text": "sonu nigam classic", "language": "Any"},
    {"text": "udit narayan 90s", "language": "Any"},
    {"text": "hindi folk acoustic", "language": "Hindi"},  # Hindi
    {"text": "rajasthani folk desert", "language": "Any"},
    {"text": "baul music bengali", "language": "Any"},
    {"text": "south indian mass bgm", "language": "Any"},
    {"text": "tamil kuthu", "language": "Tamil"},  # Tamil
    {"text": "telugu mass beat", "language": "Telugu"},  # Telugu
    {"text": "kollywood dance", "language": "Tamil"},  # Tamil
    {"text": "tollywood item", "language": "Telugu"},  # Telugu
    {"text": "ilaiyaraaja sad classic", "language": "Any"},
    {"text": "anirudh upbeat tamil", "language": "Tamil"},  # Tamil
    {"text": "thaman bass telugu", "language": "Telugu"},  # Telugu
    {"text": "allu arjun bgm", "language": "Telugu"},  # Telugu
    {"text": "dsp energetic telugu", "language": "Telugu"},  # Telugu
    {"text": "vijay thalapathy entry", "language": "Tamil"},  # Tamil
    {"text": "rajinikanth mass bgm", "language": "Any"},
    {"text": "bappi lahiri retro", "language": "Any"},
    {"text": "asha bhosle classic", "language": "Any"},
    {"text": "rafi sahab timeless", "language": "Any"},
    {"text": "mukesh sad song", "language": "Any"},
    {"text": "talat mahmood ghazal", "language": "Hindi"},  # Hindi
    {"text": "jagjit singh ghazal", "language": "Hindi"},  # Hindi
    {"text": "mehdi hassan ghazal", "language": "Hindi"},  # Hindi
    {"text": "gulam ali ghazal", "language": "Hindi"},  # Hindi
    {"text": "abida parveen qawwali", "language": "Hindi"},  # Hindi
    {"text": "bride entry song", "language": "Any"},
    {"text": "groom entry song", "language": "Any"},
    {"text": "jaimala music", "language": "Any"},
    {"text": "heartbreak at 3am", "language": "Any"},
    {"text": "can't stop crying in the car", "language": "Any"},
    {"text": "she left and took everything", "language": "Any"},
    {"text": "deleted our photos", "language": "Any"},
    {"text": "reading old texts from someone who's gone", "language": "Any"},
    {"text": "sad indie folk breakup", "language": "Any"},
    {"text": "post breakup shower cry", "language": "Any"},
    {"text": "wrote you a letter i'll never send", "language": "Any"},
    {"text": "our song came on the radio", "language": "Any"},
    {"text": "ghost of you everywhere i go", "language": "Any"},
    {"text": "unrequited love", "language": "Any"},
    {"text": "love that was never mine to begin with", "language": "Any"},
    {"text": "still love them but it's over", "language": "Any"},
    {"text": "moving on but not really", "language": "Any"},
    {"text": "heartbreak and wine", "language": "Any"},
    {"text": "sad songs for a rainy tuesday", "language": "Any"},
    {"text": "crying while driving at night", "language": "Any"},
    {"text": "soft heartbreak bedroom pop", "language": "Any"},
    {"text": "slow sad guitar", "language": "Any"},
    {"text": "empty apartment after a breakup", "language": "Any"},
    {"text": "the day you left", "language": "Any"},
    {"text": "one year later still not over it", "language": "Any"},
    {"text": "sad piano emotional", "language": "Any"},
    {"text": "melancholy at sunset", "language": "Any"},
    {"text": "lonely on a friday night", "language": "Any"},
    {"text": "friends who drifted apart", "language": "Any"},
    {"text": "long distance ended", "language": "Any"},
    {"text": "the last hug before goodbye", "language": "Any"},
    {"text": "boarding a flight knowing you won't come back", "language": "Any"},
    {"text": "watching your stuff walk out the door", "language": "Any"},
    {"text": "hollowness after a breakup", "language": "Any"},
    {"text": "healing but slowly", "language": "Any"},
    {"text": "third week of crying still going", "language": "Any"},
    {"text": "nostalgia that hurts", "language": "Any"},
    {"text": "memories that feel like bruises", "language": "Any"},
    {"text": "sad r&b breakup", "language": "Any"},
    {"text": "slow jam heartbreak", "language": "Any"},
    {"text": "neo soul goodbye", "language": "Any"},
    {"text": "billie eilish emotional", "language": "Any"},
    {"text": "olivia rodrigo betrayal", "language": "Any"},
    {"text": "phoebe bridgers devastating", "language": "Any"},
    {"text": "boygenius sad", "language": "Any"},
    {"text": "sufjan stevens grief", "language": "Any"},
    {"text": "iron and wine melancholy", "language": "Any"},
    {"text": "james blake heartbreak", "language": "Any"},
    {"text": "bon iver winter sadness", "language": "Any"},
    {"text": "sad emo relapse", "language": "Any"},
    {"text": "midwest emo crying", "language": "Any"},
    {"text": "sadcore slow and painful", "language": "Any"},
    {"text": "lana del rey longing", "language": "Any"},
    {"text": "lorde heartbreak green light era", "language": "Any"},
    {"text": "frank ocean blonde mood", "language": "Any"},
    {"text": "the national hopeless", "language": "Any"},
    {"text": "elliot smith delicate", "language": "Any"},
    {"text": "nick drake fragile", "language": "Any"},
    {"text": "tim buckley grief", "language": "Any"},
    {"text": "leonard cohen sad wisdom", "language": "Any"},
    {"text": "damien rice devastating", "language": "Any"},
    {"text": "lisa hannigan lonely", "language": "Any"},
    {"text": "glen hansard emotional", "language": "Any"},
    {"text": "daughter sad indie", "language": "Any"},
    {"text": "vancouver sleep clinic collapse", "language": "Any"},
    {"text": "novo amor anchor", "language": "Any"},
    {"text": "sea of love", "language": "Any"},
    {"text": "slowed reverb emotional tiktok", "language": "Any"},
    {"text": "slowed sad hindi", "language": "Hindi"},  # Hindi
    {"text": "heartbreak slowed + reverb", "language": "Any"},
    {"text": "sad lofi rain", "language": "Any"},
    {"text": "lofi hip hop late night sad", "language": "Any"},
    {"text": "jazz late night lonely", "language": "Any"},
    {"text": "slow saxophone sad", "language": "Any"},
    {"text": "piano alone at midnight", "language": "Any"},
    {"text": "violin heartbreak classical", "language": "Any"},
    {"text": "cello emotional", "language": "Any"},
    {"text": "requiem for a lost love", "language": "Any"},
    {"text": "missing someone who is still alive", "language": "Any"},
    {"text": "emotional numbness after betrayal", "language": "Any"},
    {"text": "soft crying vibes", "language": "Any"},
    {"text": "it's been six months", "language": "Any"},
    {"text": "new place smells like you", "language": "Any"},
    {"text": "took your name out of my phone", "language": "Any"},
    {"text": "still dreaming about you", "language": "Any"},
    {"text": "your birthday and you're gone", "language": "Any"},
    {"text": "autumn heartbreak", "language": "Any"},
    {"text": "november sadness", "language": "Any"},
    {"text": "december loneliness", "language": "Any"},
    {"text": "january cold and empty", "language": "Any"},
    {"text": "february bitter", "language": "Any"},
    {"text": "missing someone far away", "language": "Any"},
    {"text": "long distance heartache", "language": "Any"},
    {"text": "the slow fade", "language": "Any"},
    {"text": "when they stop texting back", "language": "Any"},
    {"text": "left on read for three days", "language": "Any"},
    {"text": "almost relationship regret", "language": "Any"},
    {"text": "they found someone new", "language": "Any"},
    {"text": "saw them with someone else", "language": "Any"},
    {"text": "moving on playlist day one", "language": "Any"},
    {"text": "2am sad songs", "language": "Any"},
    {"text": "everything reminds me of you", "language": "Any"},
    {"text": "driving to nowhere sad", "language": "Any"},
    {"text": "sad girl autumn playlist", "language": "Any"},
    {"text": "sad boy summer", "language": "Any"},
    {"text": "falling in love playlist", "language": "Any"},
    {"text": "first date nervous energy", "language": "Any"},
    {"text": "slow dance in the kitchen", "language": "Any"},
    {"text": "kissing in the rain", "language": "Any"},
    {"text": "romantic evening at home", "language": "Any"},
    {"text": "love songs for two", "language": "Any"},
    {"text": "anniversary dinner playlist", "language": "Any"},
    {"text": "new relationship butterflies", "language": "Any"},
    {"text": "when you look at me like that", "language": "Any"},
    {"text": "soft romantic r&b", "language": "Any"},
    {"text": "neo soul love songs", "language": "Any"},
    {"text": "slow jam for late nights", "language": "Any"},
    {"text": "daniel caesar romantic", "language": "Any"},
    {"text": "frank ocean in love", "language": "Any"},
    {"text": "sza for someone i'm seeing", "language": "Any"},
    {"text": "giveon heartbreak anniversary", "language": "Any"},
    {"text": "john legend perfect", "language": "Any"},
    {"text": "miguel adorn", "language": "Any"},
    {"text": "brent faiyaz romantic", "language": "Any"},
    {"text": "h.e.r. love songs", "language": "Any"},
    {"text": "jhene aiko tender", "language": "Any"},
    {"text": "summer walker slow", "language": "Any"},
    {"text": "corinne bailey rae gentle love", "language": "Any"},
    {"text": "norah jones quiet romance", "language": "Any"},
    {"text": "bedroom pop romantic", "language": "Any"},
    {"text": "acoustic love song", "language": "Any"},
    {"text": "indie romance playlist", "language": "Any"},
    {"text": "soft guitar love", "language": "Any"},
    {"text": "valentine's day playlist", "language": "Any"},
    {"text": "wedding first dance", "language": "Any"},
    {"text": "honeymoon vibes", "language": "Any"},
    {"text": "proposal music", "language": "Any"},
    {"text": "slow dance at prom", "language": "Any"},
    {"text": "first kiss song", "language": "Any"},
    {"text": "love at first sight feeling", "language": "Any"},
    {"text": "that feeling before you say i love you", "language": "Any"},
    {"text": "road trip with someone you love", "language": "Any"},
    {"text": "holding hands playlist", "language": "Any"},
    {"text": "cooking dinner for someone special", "language": "Any"},
    {"text": "sunday morning with you", "language": "Any"},
    {"text": "waking up next to you", "language": "Any"},
    {"text": "good morning beautiful", "language": "Any"},
    {"text": "late night talking getting to know you", "language": "Any"},
    {"text": "staying up all night talking", "language": "Any"},
    {"text": "crush playlist secret", "language": "Any"},
    {"text": "falling slowly", "language": "Any"},
    {"text": "she's the one feeling", "language": "Any"},
    {"text": "he's different vibe", "language": "Any"},
    {"text": "that electric chemistry feeling", "language": "Any"},
    {"text": "spark between two people", "language": "Any"},
    {"text": "love that feels like home", "language": "Any"},
    {"text": "comfortable love", "language": "Any"},
    {"text": "loyal devoted love song", "language": "Any"},
    {"text": "you are my person", "language": "Any"},
    {"text": "romantic bollywood hindi", "language": "Hindi"},  # Hindi
    {"text": "tum hi aana mood", "language": "Any"},
    {"text": "ae dil hai mushkil romantic", "language": "Any"},
    {"text": "dilwale dulhania type vibe", "language": "Any"},
    {"text": "punjabi soft romantic ap dhillon", "language": "Punjabi"},  # Punjabi
    {"text": "kali teri zulf", "language": "Any"},
    {"text": "haaye oye type feeling", "language": "Any"},
    {"text": "dil de de punjabi love", "language": "Punjabi"},  # Punjabi
    {"text": "serenade at midnight", "language": "Any"},
    {"text": "lost in your eyes", "language": "Any"},
    {"text": "tender moment playlist", "language": "Any"},
    {"text": "intimacy playlist", "language": "Any"},
    {"text": "candle lit dinner music", "language": "Any"},
    {"text": "stargazing with someone", "language": "Any"},
    {"text": "i think i love you playlist", "language": "Any"},
    {"text": "confessing feelings songs", "language": "Any"},
    {"text": "making up after a fight", "language": "Any"},
    {"text": "love that survived hard times", "language": "Any"},
    {"text": "growing old together songs", "language": "Any"},
    {"text": "forever yours playlist", "language": "Any"},
    {"text": "devotion songs", "language": "Any"},
    {"text": "unconditional love", "language": "Any"},
    {"text": "long term relationship love", "language": "Any"},
    {"text": "comfortable silence with someone", "language": "Any"},
    {"text": "pre-workout rage", "language": "Any"},
    {"text": "gym lifting heavy", "language": "Any"},
    {"text": "run faster playlist", "language": "Any"},
    {"text": "beast mode activated", "language": "Any"},
    {"text": "trap banger no skip", "language": "Any"},
    {"text": "drill hard aggressive", "language": "Any"},
    {"text": "rage rap 2024", "language": "Any"},
    {"text": "phonk drift aggressive", "language": "Any"},
    {"text": "hardstyle festival crush", "language": "Any"},
    {"text": "edm drop incoming", "language": "Any"},
    {"text": "jersey club bounce", "language": "Any"},
    {"text": "uk drill gritty", "language": "Any"},
    {"text": "dark trap menacing", "language": "Any"},
    {"text": "bass boosted hard", "language": "Any"},
    {"text": "playboi carti whole lotta red", "language": "Any"},
    {"text": "travis scott sicko mode energy", "language": "Any"},
    {"text": "metro boomin dark", "language": "Any"},
    {"text": "future slime season", "language": "Any"},
    {"text": "21 savage cold", "language": "Any"},
    {"text": "young thug banger", "language": "Any"},
    {"text": "lil uzi vert eternal atake energy", "language": "Any"},
    {"text": "destroy lonely plug", "language": "Any"},
    {"text": "ken carson hard", "language": "Any"},
    {"text": "kill bill scarlxrd", "language": "Any"},
    {"text": "suicideboys $uicideboy$ dark", "language": "Any"},
    {"text": "ghostemane aggressive", "language": "Any"},
    {"text": "city morgue violent", "language": "Any"},
    {"text": "nothing nowhere intense", "language": "Any"},
    {"text": "bmth bring me the horizon rage", "language": "Any"},
    {"text": "spiritbox heavy", "language": "Any"},
    {"text": "knocked loose breakdown", "language": "Any"},
    {"text": "converge chaos", "language": "Any"},
    {"text": "code orange noise", "language": "Any"},
    {"text": "jazz cartier aggressive", "language": "Any"},
    {"text": "ski mask the slump god bounce", "language": "Any"},
    {"text": "denzel curry unlocked", "language": "Any"},
    {"text": "jpegmafia experimental hype", "language": "Any"},
    {"text": "billy woods angry", "language": "Any"},
    {"text": "aesop rock intense", "language": "Any"},
    {"text": "brockhampton hype", "language": "Any"},
    {"text": "death grips no love deep web", "language": "Any"},
    {"text": "clipping hard", "language": "Any"},
    {"text": "100 gecs chaotic", "language": "Any"},
    {"text": "machine girl fast", "language": "Any"},
    {"text": "sewerslvt aggressive", "language": "Any"},
    {"text": "goreshit dark", "language": "Any"},
    {"text": "mezzmerize system of a down", "language": "Any"},
    {"text": "chop suey moshpit", "language": "Any"},
    {"text": "rage against the machine protest", "language": "Any"},
    {"text": "enter sandman energy", "language": "Any"},
    {"text": "master of puppets guitar solo hype", "language": "Any"},
    {"text": "lamb of god groove metal", "language": "Any"},
    {"text": "slipknot live energy", "language": "Any"},
    {"text": "korn early nu metal", "language": "Any"},
    {"text": "linkin park in the end hype", "language": "Any"},
    {"text": "breaking the habit intensity", "language": "Any"},
    {"text": "from zero new linkin park", "language": "Any"},
    {"text": "m city jr heat", "language": "Any"},
    {"text": "nf i miss the days hype", "language": "Any"},
    {"text": "polo g hype rap", "language": "Any"},
    {"text": "rod wave emotional hype", "language": "Any"},
    {"text": "NBA youngboy all in", "language": "Any"},
    {"text": "lil baby harder than ever", "language": "Any"},
    {"text": "gunna wunna", "language": "Any"},
    {"text": "dababy rockstar energy", "language": "Any"},
    {"text": "roddy ricch the box bounce", "language": "Any"},
    {"text": "pop smoke drill rip", "language": "Any"},
    {"text": "fivio foreign drill", "language": "Any"},
    {"text": "central cee block", "language": "Any"},
    {"text": "headie one hard uk", "language": "Any"},
    {"text": "stormzy heavy is the head", "language": "Any"},
    {"text": "dave psychodrama intense", "language": "Any"},
    {"text": "slowthai chaotic", "language": "Any"},
    {"text": "idles punk energy", "language": "Any"},
    {"text": "shame rock hype", "language": "Any"},
    {"text": "wet leg indie hype", "language": "Any"},
    {"text": "confidence walk out song", "language": "Any"},
    {"text": "entrance theme boss mode", "language": "Any"},
    {"text": "villain arc playlist", "language": "Any"},
    {"text": "sigma grindset motivation", "language": "Any"},
    {"text": "dark horse moment", "language": "Any"},
    {"text": "underdog rising", "language": "Any"},
    {"text": "lofi hip hop study beats", "language": "Any"},
    {"text": "lo-fi chill rainy day", "language": "Any"},
    {"text": "study session playlist", "language": "Any"},
    {"text": "focus deep work music", "language": "Any"},
    {"text": "jazz cafe background", "language": "Any"},
    {"text": "bossa nova afternoon", "language": "Any"},
    {"text": "nujabes soulful lofi", "language": "Any"},
    {"text": "j dilla instrumental", "language": "Any"},
    {"text": "mf doom mm food chill", "language": "Any"},
    {"text": "black thought instrumental", "language": "Any"},
    {"text": "flying lotus ambient", "language": "Any"},
    {"text": "thundercat bass chill", "language": "Any"},
    {"text": "knxwledge jazzy beats", "language": "Any"},
    {"text": "kaytranada bounce chill", "language": "Any"},
    {"text": "anderson paak chill vibes", "language": "Any"},
    {"text": "frank ocean channel orange chill", "language": "Any"},
    {"text": "daniel caesar get you chill", "language": "Any"},
    {"text": "steve lacy apollo chill", "language": "Any"},
    {"text": "jorja smith lost and found", "language": "Any"},
    {"text": "mahalia romantic chill", "language": "Any"},
    {"text": "omar apollo aiming for your heart", "language": "Any"},
    {"text": "snoh aalegra chill", "language": "Any"},
    {"text": "cleo sol sweet blue", "language": "Any"},
    {"text": "little simz quiet", "language": "Any"},
    {"text": "loyle carner chill rap", "language": "Any"},
    {"text": "kae tempest spoken", "language": "Any"},
    {"text": "novo amor birthplace", "language": "Any"},
    {"text": "bon iver holocene", "language": "Any"},
    {"text": "sufjan stevens illinois", "language": "Any"},
    {"text": "iron and wine creepin", "language": "Any"},
    {"text": "acoustic sunday morning", "language": "Any"},
    {"text": "guitar picking relaxed", "language": "Any"},
    {"text": "coffee shop rainy window", "language": "Any"},
    {"text": "drizzle outside studying", "language": "Any"},
    {"text": "2am coding music", "language": "Any"},
    {"text": "late night reading playlist", "language": "Any"},
    {"text": "sunday afternoon chill", "language": "Any"},
    {"text": "slow morning piano", "language": "Any"},
    {"text": "instrumental hip hop beats", "language": "Any"},
    {"text": "trip hop portishead", "language": "Any"},
    {"text": "massive attack blue lines", "language": "Any"},
    {"text": "tricky pre-millennium tension", "language": "Any"},
    {"text": "burial ghost chill", "language": "Any"},
    {"text": "four tet swaps", "language": "Any"},
    {"text": "bonobo north borders chill", "language": "Any"},
    {"text": "tycho dive ambient", "language": "Any"},
    {"text": "khruangbin texas sun", "language": "Any"},
    {"text": "leon bridges coming home", "language": "Any"},
    {"text": "toro y moi underneath the pine", "language": "Any"},
    {"text": "washed out feel it all around", "language": "Any"},
    {"text": "beach house teen dream", "language": "Any"},
    {"text": "mazzy star fade into you", "language": "Any"},
    {"text": "still woozy bedroom pop chill", "language": "Any"},
    {"text": "rex orange county sunflower", "language": "Any"},
    {"text": "alex g apartment chill", "language": "Any"},
    {"text": "big thief two hands soft", "language": "Any"},
    {"text": "snail mail valentine", "language": "Any"},
    {"text": "beabadoobee indie chill", "language": "Any"},
    {"text": "clairo sling", "language": "Any"},
    {"text": "soccer mommy soft sounds", "language": "Any"},
    {"text": "muna silk chiffon", "language": "Any"},
    {"text": "the japanese house chill", "language": "Japanese"},  # Japanese
    {"text": "japanese breakfast psychopomp", "language": "Japanese"},  # Japanese
    {"text": "hozier cherry wine", "language": "Any"},
    {"text": "dermot kennedy giants", "language": "Any"},
    {"text": "oh wonder technicolour beat", "language": "Any"},
    {"text": "tove lo habits", "language": "Any"},
    {"text": "zara larsson never forget you", "language": "Any"},
    {"text": "sigrid strangers", "language": "Any"},
    {"text": "aurora running with the wolves", "language": "Any"},
    {"text": "freya ridings castles", "language": "Any"},
    {"text": "raye escapism chill", "language": "Any"},
    {"text": "lofi hindi chill", "language": "Hindi"},  # Hindi
    {"text": "desi chill evening", "language": "Hindi"},  # Hindi
    {"text": "slow bollywood instrumental", "language": "Hindi"},  # Hindi
    {"text": "rainy day hindi lofi", "language": "Hindi"},  # Hindi
    {"text": "club night opening", "language": "Any"},
    {"text": "4am dancefloor still going", "language": "Any"},
    {"text": "pre-drinks at home", "language": "Any"},
    {"text": "girls night out banger", "language": "Any"},
    {"text": "boys night loud", "language": "Any"},
    {"text": "birthday party playlist", "language": "Any"},
    {"text": "house music deep groove", "language": "Any"},
    {"text": "tech house warehouse", "language": "Any"},
    {"text": "afrobeats dance floor", "language": "Afrobeats"},  # Afrobeats
    {"text": "amapiano braai", "language": "Afrobeats"},  # Afrobeats
    {"text": "dancehall caribbean heat", "language": "Any"},
    {"text": "reggaeton latin club", "language": "Spanish"},  # Spanish
    {"text": "soca trinidad carnival", "language": "Any"},
    {"text": "baile funk brazil", "language": "Any"},
    {"text": "jersey club nyc", "language": "Any"},
    {"text": "footwork chicago", "language": "Any"},
    {"text": "drum and bass jungle", "language": "Any"},
    {"text": "garage uk bounce", "language": "Any"},
    {"text": "2-step classic uk", "language": "Any"},
    {"text": "happy hardcore early rave", "language": "Any"},
    {"text": "90s rave nostalgia", "language": "Any"},
    {"text": "00s electro indie dance", "language": "Any"},
    {"text": "calvin harris ibiza", "language": "Any"},
    {"text": "dua lipa dance night", "language": "Any"},
    {"text": "charli xcx party girl", "language": "Any"},
    {"text": "caroline polachek dance", "language": "Any"},
    {"text": "doechii chaotic fun", "language": "Any"},
    {"text": "tinashe let's be real", "language": "Any"},
    {"text": "ciara one two step", "language": "Any"},
    {"text": "beyonce renaissance party", "language": "Any"},
    {"text": "lizzo juice good vibes", "language": "Any"},
    {"text": "doja cat say so dance", "language": "Any"},
    {"text": "bad bunny titi me pregunto", "language": "Spanish"},  # Spanish
    {"text": "karol g manana sera bonito", "language": "Spanish"},  # Spanish
    {"text": "burna boy last last dance", "language": "Afrobeats"},  # Afrobeats
    {"text": "wizkid essence", "language": "Afrobeats"},  # Afrobeats
    {"text": "davido fall", "language": "Afrobeats"},  # Afrobeats
    {"text": "tems free mind", "language": "Afrobeats"},  # Afrobeats
    {"text": "fireboy dml peru", "language": "Any"},
    {"text": "rema calm down", "language": "Any"},
    {"text": "ckay love nwantiti", "language": "Any"},
    {"text": "omah lay attention", "language": "Any"},
    {"text": "dance pop hits 2024", "language": "Any"},
    {"text": "summer hits pool party", "language": "Any"},
    {"text": "festival main stage energy", "language": "Any"},
    {"text": "midnight countdown banger", "language": "Any"},
    {"text": "wedding reception floor filler", "language": "Any"},
    {"text": "prom night classics", "language": "Any"},
    {"text": "after party vibes", "language": "Any"},
    {"text": "house party 2am", "language": "Any"},
    {"text": "drunk happy dancing", "language": "Any"},
    {"text": "carefree silly dancing", "language": "Any"},
    {"text": "mosh pit indie", "language": "Any"},
    {"text": "crowd surf moment", "language": "Any"},
    {"text": "drop incoming warehouse rave", "language": "Any"},
    {"text": "festival sunrise set", "language": "Any"},
    {"text": "closing set last track", "language": "Any"},
    {"text": "one more track dj", "language": "Any"},
    {"text": "vinyl selector deep house", "language": "Any"},
    {"text": "bar playlist smooth", "language": "Any"},
    {"text": "falling asleep to music", "language": "Any"},
    {"text": "sleep sounds white noise", "language": "Any"},
    {"text": "rain sounds with piano", "language": "Any"},
    {"text": "ambient for meditation", "language": "Any"},
    {"text": "yoga flow playlist", "language": "Any"},
    {"text": "morning stretch calm", "language": "Any"},
    {"text": "breathing exercise music", "language": "Any"},
    {"text": "anxiety relief ambient", "language": "Any"},
    {"text": "nature sounds birds morning", "language": "Any"},
    {"text": "forest walk ambient", "language": "Any"},
    {"text": "field recording natural", "language": "Any"},
    {"text": "drone ambient endless", "language": "Any"},
    {"text": "brian eno ambient 1", "language": "Any"},
    {"text": "harold budd the plateaux of mirror", "language": "Any"},
    {"text": "william basinski disintegration loops", "language": "Any"},
    {"text": "stars of the lid sad mafioso", "language": "Any"},
    {"text": "the caretaker everywhere", "language": "Any"},
    {"text": "grouper dragging a dead deer", "language": "Any"},
    {"text": "julianna barwick magic place", "language": "Any"},
    {"text": "the album leaf in a safe place", "language": "Any"},
    {"text": "lowercase ambient quiet", "language": "Any"},
    {"text": "acousmatic space", "language": "Any"},
    {"text": "hauntology memory ghost", "language": "Any"},
    {"text": "ghost box records", "language": "Any"},
    {"text": "boards of canada geogaddi", "language": "Any"},
    {"text": "aphex twin selected ambient", "language": "Any"},
    {"text": "autechre incunabula", "language": "Any"},
    {"text": "oval systemisch", "language": "Any"},
    {"text": "eluvium copia", "language": "Any"},
    {"text": "peter broderick float", "language": "Any"},
    {"text": "nils frahm spaces", "language": "Any"},
    {"text": "max richter sleep", "language": "Any"},
    {"text": "olafur arnalds and they have escaped", "language": "Any"},
    {"text": "jon hopkins immunity piano", "language": "Any"},
    {"text": "floating points promises", "language": "Any"},
    {"text": "nala sinephro space 1.8", "language": "Any"},
    {"text": "alabaster deplume gold", "language": "Any"},
    {"text": "calm morning coffee", "language": "Any"},
    {"text": "slow sunday ambient", "language": "Any"},
    {"text": "rainy night in bed", "language": "Any"},
    {"text": "candle lit room", "language": "Any"},
    {"text": "fireplace crackling music", "language": "Any"},
    {"text": "winter cosy ambient", "language": "Any"},
    {"text": "deep focus instrumental", "language": "Any"},
    {"text": "reading room music", "language": "Any"},
    {"text": "museum ambient", "language": "Any"},
    {"text": "art gallery playlist", "language": "Any"},
    {"text": "spa relaxation music", "language": "Any"},
    {"text": "massage therapy ambient", "language": "Any"},
    {"text": "post-yoga savasana", "language": "Any"},
    {"text": "lying on the grass looking up", "language": "Any"},
    {"text": "stargazing ambient", "language": "Any"},
    {"text": "late night drive quiet", "language": "Any"},
    {"text": "driving alone 3am empty roads", "language": "Any"},
    {"text": "empty city streets ambient", "language": "Any"},
    {"text": "headphones on subway quiet moment", "language": "Any"},
    {"text": "tuning out the world", "language": "Any"},
    {"text": "introvert recharge music", "language": "Any"},
    {"text": "alone but okay playlist", "language": "Any"},
    {"text": "dream pop hazy", "language": "Any"},
    {"text": "shoegaze wall of sound", "language": "Any"},
    {"text": "ethereal vocals reverb", "language": "Any"},
    {"text": "slowcore drifting", "language": "Any"},
    {"text": "beach house forever", "language": "Any"},
    {"text": "cocteau twins heaven or las vegas", "language": "Any"},
    {"text": "lush spooky", "language": "Any"},
    {"text": "mazzy star look on down", "language": "Any"},
    {"text": "my bloody valentine loveless", "language": "Any"},
    {"text": "slowdive souvlaki", "language": "Any"},
    {"text": "ride vapour trail", "language": "Any"},
    {"text": "chapterhouse mesmerise", "language": "Any"},
    {"text": "medicine the buried life", "language": "Any"},
    {"text": "nothing tired of tomorrow", "language": "Any"},
    {"text": "title fight floral green", "language": "Any"},
    {"text": "deafheaven sunbather", "language": "Any"},
    {"text": "half waif form", "language": "Any"},
    {"text": "weyes blood front row seat", "language": "Any"},
    {"text": "aldous harding designer", "language": "Hindi"},  # Hindi
    {"text": "julia jacklin crushing", "language": "Any"},
    {"text": "lucy dacus night shift", "language": "Any"},
    {"text": "snail mail pristine", "language": "Any"},
    {"text": "phoebe bridgers moon song", "language": "Any"},
    {"text": "boygenius satanist", "language": "Any"},
    {"text": "big thief shark smile", "language": "Any"},
    {"text": "adrianne lenker songs", "language": "Any"},
    {"text": "angel olsen all mirrors", "language": "Any"},
    {"text": "mitski puberty 2", "language": "Any"},
    {"text": "japanese breakfast brutal", "language": "Japanese"},  # Japanese
    {"text": "soccer mommy bloodstream", "language": "Any"},
    {"text": "clairo alewife dream", "language": "Any"},
    {"text": "rex orange county pluto", "language": "Any"},
    {"text": "men i trust lauren", "language": "Any"},
    {"text": "still woozy goodie bag", "language": "Any"},
    {"text": "the japanese house saw it in a dream", "language": "Japanese"},  # Japanese
    {"text": "blood orange devonte", "language": "Any"},
    {"text": "james blake overgrown ethereal", "language": "Any"},
    {"text": "bon iver re stacks", "language": "Any"},
    {"text": "fleet foxes white winter hymnal", "language": "Any"},
    {"text": "sufjan stevens vesuvius", "language": "Any"},
    {"text": "sigur ros hoppipolla", "language": "Any"},
    {"text": "explosions in the sky first breath", "language": "Any"},
    {"text": "godspeed you black emperor sad and drunk", "language": "Telugu"},  # Telugu
    {"text": "swans the seer intense dream", "language": "Any"},
    {"text": "scott walker tilt", "language": "Any"},
    {"text": "nick cave the mercy seat", "language": "Any"},
    {"text": "mark hollis mark hollis", "language": "Any"},
    {"text": "talk talk spirit of eden", "language": "Any"},
    {"text": "harold budd cascades", "language": "Any"},
    {"text": "villain origin story playlist", "language": "Any"},
    {"text": "cinematic dark score", "language": "Any"},
    {"text": "epic orchestral battle", "language": "Any"},
    {"text": "hans zimmer time", "language": "Any"},
    {"text": "ennio morricone western tension", "language": "Any"},
    {"text": "bernard herrmann psycho strings", "language": "Any"},
    {"text": "john carpenter halloween synths", "language": "Any"},
    {"text": "goblin susperia dark", "language": "Any"},
    {"text": "cliff martinez drive soundtrack", "language": "Any"},
    {"text": "johnny jewel chromatics", "language": "Any"},
    {"text": "perturbator miami nights dark", "language": "Any"},
    {"text": "carpenter brut turbo killer", "language": "Any"},
    {"text": "kavinsky nightcall", "language": "Any"},
    {"text": "gunship dark all night", "language": "Any"},
    {"text": "neon demon soundtrack", "language": "Any"},
    {"text": "blade runner 2049 ambient", "language": "Any"},
    {"text": "tron legacy daft punk", "language": "Any"},
    {"text": "interstellar hans zimmer", "language": "Any"},
    {"text": "inception time piano", "language": "Any"},
    {"text": "dunkirk hans zimmer survival", "language": "Any"},
    {"text": "oppenheimer cillian murphy theme", "language": "Any"},
    {"text": "annihilation score", "language": "Any"},
    {"text": "hereditary ari aster horror", "language": "Any"},
    {"text": "midsommar folk horror", "language": "Any"},
    {"text": "black swan aronofsky", "language": "Any"},
    {"text": "mother darren aronofsky", "language": "Any"},
    {"text": "requiem for a dream dark", "language": "Any"},
    {"text": "pi aronofsky drill", "language": "Any"},
    {"text": "nine inch nails hesitation marks", "language": "Any"},
    {"text": "the fragile nin", "language": "Any"},
    {"text": "marilyn manson antichrist superstar", "language": "Any"},
    {"text": "tool lateralus", "language": "Any"},
    {"text": "a perfect circle thirteenth step", "language": "Any"},
    {"text": "porcupine tree fear of a blank planet", "language": "Any"},
    {"text": "steven wilson hand cannot erase", "language": "Any"},
    {"text": "katatonia tonight's decision", "language": "Any"},
    {"text": "swallow the sun the morning never came", "language": "Any"},
    {"text": "agalloch the mantle", "language": "Any"},
    {"text": "wolves in the throne room celestial lineage", "language": "Any"},
    {"text": "deathspell omega si monvmentvm", "language": "Any"},
    {"text": "dark ambient winter drone", "language": "Any"},
    {"text": "cold wave minimal", "language": "Any"},
    {"text": "cabaret voltaire red mecca", "language": "Any"},
    {"text": "throbbing gristle second annual", "language": "Any"},
    {"text": "coil scatology", "language": "Any"},
    {"text": "nurse with wound chance meeting", "language": "Any"},
    {"text": "current 93 dawn", "language": "Any"},
    {"text": "death in june rose clouds", "language": "Any"},
    {"text": "sol invictus against the modern world", "language": "Any"},
    {"text": "rome nera endurance", "language": "Any"},
    {"text": "triarii mutter", "language": "Any"},
    {"text": "atrium carceri cellblock", "language": "Any"},
    {"text": "lustmord the place where the black stars hang", "language": "Any"},
    {"text": "raison d'être the Empty hollow unfolds", "language": "Any"},
    {"text": "thorn1 industrial dark", "language": "Any"},
    {"text": "nzinga techno dark", "language": "Any"},
    {"text": "final boss music", "language": "Any"},
    {"text": "dungeon crawl rpg soundtrack", "language": "Any"},
    {"text": "horror walk up stairs", "language": "Any"},
    {"text": "last survivor film score", "language": "Any"},
    {"text": "80s synth nostalgia", "language": "Any"},
    {"text": "synthwave neon city night drive", "language": "Any"},
    {"text": "retrowave outrun aesthetic", "language": "Any"},
    {"text": "new wave cold 80s", "language": "Any"},
    {"text": "italo disco 80s dance", "language": "Any"},
    {"text": "city pop japanese 80s", "language": "Japanese"},  # Japanese
    {"text": "vaporwave aesthetic 90s", "language": "Any"},
    {"text": "90s rnb slow jam classic", "language": "Any"},
    {"text": "90s hip hop boom bap", "language": "Any"},
    {"text": "classic boom bap samples", "language": "Any"},
    {"text": "90s alternative rock nostalgia", "language": "Any"},
    {"text": "britpop 90s blur oasis", "language": "Any"},
    {"text": "00s emo throwback", "language": "Any"},
    {"text": "00s pop nostalgia", "language": "Any"},
    {"text": "00s indie sleater kinney le tigre", "language": "Any"},
    {"text": "early 2010s indie", "language": "Any"},
    {"text": "chillwave 2010 nostalgia", "language": "Any"},
    {"text": "dream pop 2012", "language": "Any"},
    {"text": "tumblr era music 2013", "language": "Any"},
    {"text": "tame impala 2012 lonerism", "language": "Any"},
    {"text": "foster the people 2011", "language": "Any"},
    {"text": "mgmt electric feel era", "language": "Any"},
    {"text": "vampire weekend contra era", "language": "Any"},
    {"text": "arcade fire funeral era", "language": "Any"},
    {"text": "the strokes is this it era", "language": "Any"},
    {"text": "interpol turn on the bright lights", "language": "Any"},
    {"text": "joy division unknown pleasures", "language": "Any"},
    {"text": "new order blue monday", "language": "Any"},
    {"text": "kraftwerk autobahn", "language": "Any"},
    {"text": "devo whip it", "language": "Any"},
    {"text": "talking heads remain in light", "language": "Any"},
    {"text": "david bowie ziggy stardust", "language": "Any"},
    {"text": "iggy pop lust for life", "language": "Any"},
    {"text": "lou reed walk on the wild side", "language": "Any"},
    {"text": "velvet underground femme fatale", "language": "Any"},
    {"text": "t. rex bang a gong", "language": "Any"},
    {"text": "bowie heroes", "language": "Any"},
    {"text": "queen bohemian rhapsody", "language": "Any"},
    {"text": "led zeppelin stairway", "language": "Any"},
    {"text": "pink floyd dark side", "language": "Any"},
    {"text": "classic vinyl warmth", "language": "Any"},
    {"text": "cassette tape nostalgia", "language": "Any"},
    {"text": "driving with dad's old mixtape", "language": "Any"},
    {"text": "grandma's radio songs", "language": "Any"},
    {"text": "school disco 2004", "language": "Any"},
    {"text": "first concert memory", "language": "Any"},
    {"text": "summer of 2007 feeling", "language": "Any"},
    {"text": "that one song from 2009", "language": "Any"},
    {"text": "indie folk campfire", "language": "Any"},
    {"text": "acoustic guitar and voice", "language": "Any"},
    {"text": "folk revival modern", "language": "Any"},
    {"text": "mountain folk dark", "language": "Any"},
    {"text": "appalachian folk drone", "language": "Any"},
    {"text": "old weird america", "language": "Any"},
    {"text": "fleet foxes blue ridge mountains", "language": "Any"},
    {"text": "iron and wine naked as we came", "language": "Any"},
    {"text": "nick drake pink moon", "language": "Any"},
    {"text": "john martyn solid air", "language": "Any"},
    {"text": "bert jansch pentangle", "language": "Any"},
    {"text": "richard thompson shoot out", "language": "Any"},
    {"text": "fairport convention liege and lief", "language": "Any"},
    {"text": "sandy denny she moves through", "language": "Any"},
    {"text": "anne briggs living by the water", "language": "Any"},
    {"text": "nic jones canadee-i-o", "language": "Any"},
    {"text": "shirley collins sweet england", "language": "Any"},
    {"text": "martin carthy prince heathen", "language": "Any"},
    {"text": "current folk scene", "language": "Any"},
    {"text": "hozier wasteland baby", "language": "Any"},
    {"text": "noah and the whale 5 years time", "language": "Any"},
    {"text": "laura marling once i was an eagle", "language": "Any"},
    {"text": "tom odell another love", "language": "Any"},
    {"text": "ben howard only love", "language": "Any"},
    {"text": "passenger let her go", "language": "Any"},
    {"text": "james vincent mcmorrow early in the morning", "language": "Any"},
    {"text": "city and colour little hell", "language": "Any"},
    {"text": "greg laswell comes and goes", "language": "Any"},
    {"text": "joshua radin winter", "language": "Any"},
    {"text": "the tallest man on earth king of spain", "language": "Any"},
    {"text": "jose gonzalez heartbeats", "language": "Any"},
    {"text": "damien jurado ohio", "language": "Any"},
    {"text": "bonnie prince billy i see a darkness", "language": "Any"},
    {"text": "smog red apple falls", "language": "Any"},
    {"text": "will oldham ease down the road", "language": "Any"},
    {"text": "mark lanegan has she no pride", "language": "Any"},
    {"text": "josh t. pearson last of the country gentlemen", "language": "Any"},
    {"text": "william tyler impossible truth", "language": "Any"},
    {"text": "william tyler go cloudward", "language": "Any"},
    {"text": "cass mccombs wit's end", "language": "Any"},
    {"text": "sun kil moon ghosts of the great highway", "language": "Any"},
    {"text": "Richard Dawson nothing important", "language": "Any"},
    {"text": "woods songs of shame", "language": "Any"},
    {"text": "six organs of admittance school of the flower", "language": "Any"},
    {"text": "thurston moore demolished thoughts", "language": "Any"},
    {"text": "neil young harvest", "language": "Any"},
    {"text": "crosby stills nash suite judy blue eyes", "language": "Any"},
    {"text": "joni mitchell blue", "language": "Any"},
    {"text": "carole king tapestry", "language": "Any"},
    {"text": "james taylor sweet baby james", "language": "Any"},
    {"text": "bts dynamite hype", "language": "Korean"},  # Korean
    {"text": "blackpink how you like that", "language": "Korean"},  # Korean
    {"text": "newjeans hype boy", "language": "Korean"},  # Korean
    {"text": "stray kids god's menu", "language": "Korean"},  # Korean
    {"text": "aespa black mamba dark kpop", "language": "Korean"},  # Korean
    {"text": "twice feel special", "language": "Korean"},  # Korean
    {"text": "ive love dive", "language": "Any"},
    {"text": "le sserafim fearless", "language": "Any"},
    {"text": "enhypen given-taken", "language": "Any"},
    {"text": "txt eternally kpop", "language": "Korean"},  # Korean
    {"text": "nct 127 cherry bomb", "language": "Any"},
    {"text": "shinee view", "language": "Any"},
    {"text": "exo love shot", "language": "Any"},
    {"text": "monsta x dramarama", "language": "Any"},
    {"text": "g-idle tomboy", "language": "Any"},
    {"text": "mamamoo hip", "language": "Any"},
    {"text": "red velvet psycho", "language": "Any"},
    {"text": "girl's generation gee", "language": "Any"},
    {"text": "2ne1 i am the best", "language": "Any"},
    {"text": "bigbang bang bang bang", "language": "Any"},
    {"text": "taeyang eyes nose lips", "language": "Any"},
    {"text": "zico artist kpop", "language": "Korean"},  # Korean
    {"text": "crush whatever kpop", "language": "Korean"},  # Korean
    {"text": "dean instagram kpop", "language": "Korean"},  # Korean
    {"text": "epik high born hater", "language": "Any"},
    {"text": "bts suga agust d", "language": "Korean"},  # Korean
    {"text": "j-hope more hype kpop", "language": "Korean"},  # Korean
    {"text": "rm mono chill kpop", "language": "Korean"},  # Korean
    {"text": "city pop japanese retro", "language": "Japanese"},  # Japanese
    {"text": "yoasobi idol jpop", "language": "Japanese"},  # Japanese
    {"text": "aimyon marchen jpop", "language": "Japanese"},  # Japanese
    {"text": "yorushika spring thieves", "language": "Any"},
    {"text": "kenshi yonezu flamingo", "language": "Any"},
    {"text": "official hige dandism pretender", "language": "Any"},
    {"text": "king gnu flash jpop", "language": "Japanese"},  # Japanese
    {"text": "radwimps sparkle", "language": "Any"},
    {"text": "bump of chicken karma", "language": "Any"},
    {"text": "asian kung-fu generation rewrite", "language": "Any"},
    {"text": "supercell my dearest", "language": "Any"},
    {"text": "hitorie flash back jpop", "language": "Japanese"},  # Japanese
    {"text": "sakanaction music jpop alt", "language": "Japanese"},  # Japanese
    {"text": "the pillows little busters", "language": "Any"},
    {"text": "buck-tick darker jpop", "language": "Japanese"},  # Japanese
    {"text": "sekai no owari dragon night", "language": "Any"},
    {"text": "kyary pamyu pamyu harajuku", "language": "Any"},
    {"text": "perfume polyrhythm techno jpop", "language": "Japanese"},  # Japanese
    {"text": "capsule sugarless girl", "language": "Any"},
    {"text": "cornelius point jpop art", "language": "Japanese"},  # Japanese
    {"text": "fishmans long season", "language": "Any"},
    {"text": "buffalo daughter dancehall girl", "language": "Any"},
    {"text": "making peace with a decision I can't change", "language": "Any"},
    {"text": "the moment I stopped caring about their opinion", "language": "Any"},
    {"text": "the specific peace of finally submitting a massive project", "language": "Any"},
    {"text": "something to cry to in the shower so nobody hears", "language": "Any"},
    {"text": "watching the sun go down from a moving train window", "language": "Any"},
    {"text": "getting dressed to go out and feeling myself", "language": "Any"},
    {"text": "having a long video call with a friend who moved away", "language": "Any"},
    {"text": "decluttering old belongings and getting hit by memories", "language": "Any"},
    {"text": "sitting in a cafe people watching while it rains outside", "language": "Any"},
    {"text": "getting a new haircut and feeling like a completely new person", "language": "Any"},
    {"text": "making a carefully curated playlist for someone I have a crush on", "language": "Any"},
    {"text": "the beginning of a crush when you notice every little thing", "language": "Any"},
    {"text": "a really long hug after being apart for months", "language": "Any"},
    {"text": "just got back from a trip that changed how I see everything", "language": "Any"},
    {"text": "leaving a toxic relationship and feeling terrifyingly free", "language": "Any"},
    {"text": "landing a plane after a turbulent flight, legs shaky with relief", "language": "Any"},
    {"text": "the first morning in a new apartment", "language": "Any"},
    {"text": "packing up your childhood bedroom", "language": "Any"},
    {"text": "watching your parents get old", "language": "Any"},
    {"text": "calling someone you should have called years ago", "language": "Any"},
    {"text": "forgiving yourself for something you did in the past", "language": "Any"},
    {"text": "realizing you've grown as a person", "language": "Any"},
    {"text": "finishing a book that broke you", "language": "Any"},
    {"text": "the last day of a job you actually loved", "language": "Any"},
    {"text": "graduating and not knowing what comes next", "language": "Any"},
    {"text": "watching a city you love from a plane window leaving", "language": "Any"},
    {"text": "the silence after a long argument", "language": "Any"},
    {"text": "making coffee for someone who isn't coming back", "language": "Any"},
    {"text": "cleaning out someone else's things", "language": "Any"},
    {"text": "first holiday season without someone", "language": "Any"},
    {"text": "driving past your old house", "language": "Any"},
    {"text": "visiting your hometown as an adult", "language": "Any"},
    {"text": "songs that sound like a specific year", "language": "Any"},
    {"text": "that memory you can't shake", "language": "Any"},
    {"text": "something that feels like sunday evening anxiety", "language": "Any"},
    {"text": "music that feels like being seventeen", "language": "Any"},
    {"text": "that liminal space between awake and asleep", "language": "Any"},
    {"text": "the hour before a big decision", "language": "Any"},
    {"text": "waiting room music", "language": "Any"},
    {"text": "music for when you're about to quit", "language": "Any"},
    {"text": "music for the drive after bad news", "language": "Any"},
    {"text": "songs for a last day", "language": "Any"},
    {"text": "an ordinary day that turns out to be the last good one", "language": "Any"},
    {"text": "nostalgia for a time that never existed", "language": "Any"},
    {"text": "music that sounds like you're a main character", "language": "Any"},
    {"text": "coming home feeling", "language": "Any"},
    {"text": "music for when nothing is wrong but nothing is right", "language": "Any"},
    {"text": "saturday afternoon when you have nothing to do", "language": "Any"},
    {"text": "walking home alone after a good night", "language": "Any"},
    {"text": "the quiet after a storm", "language": "Any"},
    {"text": "summer ending feeling", "language": "Any"},
    {"text": "music for 4am thoughts", "language": "Any"},
    {"text": "music for 6am before the world wakes up", "language": "Any"},
    {"text": "that feeling right before something big", "language": "Any"},
    {"text": "music for a final chapter", "language": "Any"},
    {"text": "pujabi dace hrad", "language": "Any"},
    {"text": "hapy vbies onyl", "language": "Any"},
    {"text": "amient focus snd", "language": "Any"},
    {"text": "gud vbes onely", "language": "Any"},
    {"text": "engilsh pop hppy", "language": "Any"},
    {"text": "drk ambint slp", "language": "Any"},
    {"text": "sft lov sng", "language": "Any"},
    {"text": "meditatn ohm", "language": "Any"},
    {"text": "vilin era drk", "language": "Any"},
    {"text": "gthic drk wave", "language": "Any"},
    {"text": "shogaze gtar", "language": "Any"},
    {"text": "jzz clb nigt", "language": "Any"},
    {"text": "sould ful vcals", "language": "Any"},
    {"text": "reggaetn sumer", "language": "Any"},
    {"text": "dncehall clb", "language": "Any"},
    {"text": "hpy hardcore fst", "language": "Any"},
    {"text": "brt sumr sng", "language": "Any"},
    {"text": "vaprwav aesthtic", "language": "Any"},
    {"text": "flk acustic chill", "language": "Any"},
    {"text": "rnb romntc nght", "language": "Any"},
    {"text": "cntry rd trp", "language": "Any"},
    {"text": "mtal brk dwn", "language": "Any"},
    {"text": "pst rck crscndo", "language": "Any"},
    {"text": "hiphp strt bngr", "language": "Any"},
    {"text": "trnce uplftn", "language": "Any"},
    {"text": "blck mtl fst", "language": "Any"},
    {"text": "dth mtl hvry", "language": "Any"},
    {"text": "jzz fson smth", "language": "Any"},
    {"text": "classcl pno nght", "language": "Any"},
    {"text": "gospol emtnl", "language": "Any"},
    {"text": "bngra wedng", "language": "Any"},
    {"text": "blwd rom", "language": "Any"},
    {"text": "hnd brkp", "language": "Any"},
    {"text": "pnjb sft lv", "language": "Any"},
    {"text": "bollwd item", "language": "Any"},
    {"text": "dsi prty", "language": "Any"},
    {"text": "krn pop bts", "language": "Korean"},  # Korean
    {"text": "jpn cty pp", "language": "Any"},
    {"text": "afrbts dncflr", "language": "Korean"},  # Korean
    {"text": "latn nght", "language": "Any"},
    {"text": "lndn grme", "language": "Any"},
    {"text": "drll uk hrd", "language": "Any"},
    {"text": "gme sndtrk epic", "language": "Any"},
    {"text": "wrk out trp", "language": "Any"},
    {"text": "midnght drv", "language": "Any"},
    {"text": "smmr vbs bch", "language": "Any"},
    {"text": "autmn lf fll", "language": "Any"},
    {"text": "wntr clsd frplc", "language": "Any"},
    {"text": "sprng mrng brds", "language": "Any"},
    {"text": "slwd rvb em", "language": "Any"},
    {"text": "unknown familiarity", "language": "Any"},
    {"text": "old news", "language": "Any"},
    {"text": "purposeful accident", "language": "Any"},
    {"text": "ordered randomness", "language": "Any"},
    {"text": "forceful gentleness", "language": "Any"},
    {"text": "arrogant modesty", "language": "Any"},
    {"text": "modest arrogance", "language": "Any"},
    {"text": "selfish generosity", "language": "Any"},
    {"text": "generous selfishness", "language": "Any"},
    {"text": "greedy contentment", "language": "Any"},
    {"text": "bored excitement", "language": "Any"},
    {"text": "Neither loud nor quiet", "language": "Any"},
    {"text": "No synths, purely organic instruments", "language": "Any"},
    {"text": "Something crisp and refreshing like ice water", "language": "Any"},
    {"text": "Something earthy like beets and damp soil", "language": "Any"},
    {"text": "A vibe that's savory and umami like miso", "language": "Any"},
    {"text": "A crowded street market in Marrakech", "language": "Any"},
    {"text": "A cramped apartment in Tokyo with city lights", "language": "Any"},
    {"text": "The cockpit of a spaceship entering warp drive", "language": "Any"},
    {"text": "The final showdown between two lifelong rivals", "language": "Any"},
    {"text": "A magical ball where everyone is wearing masks", "language": "Any"},
    {"text": "music that sounds like the color blue", "language": "Any"},
    {"text": "music that feels like wool", "language": "Any"},
    {"text": "music that tastes like burnt caramel", "language": "Any"},
    {"text": "songs with no beginning or end", "language": "Any"},
    {"text": "music that feels like a threshold", "language": "Any"},
    {"text": "sounds from a dream you can't remember", "language": "Any"},
    {"text": "the texture of old photographs", "language": "Any"},
    {"text": "music that sounds like dissolving", "language": "Any"},
    {"text": "something between awake and not", "language": "Any"},
    {"text": "a melody that exists between major and minor", "language": "Any"},
    {"text": "vibrations rather than notes", "language": "Any"},
    {"text": "songs that feel like they are from another timeline", "language": "Any"},
    {"text": "music that sounds like the future that never came", "language": "Any"},
    {"text": "the aesthetic of abandoned places", "language": "Any"},
    {"text": "overgrown train station vibes", "language": "Any"},
    {"text": "brutalist architecture music", "language": "Any"},
    {"text": "soviet liminal space music", "language": "Any"},
    {"text": "japanese convenience store at 3am music", "language": "Japanese"},  # Japanese
    {"text": "empty shopping mall in 1994", "language": "Any"},
    {"text": "airport departure gate alone at night", "language": "Any"},
    {"text": "hotel corridor at 2am", "language": "Spanish"},  # Spanish
    {"text": "long highway through nothing", "language": "Any"},
    {"text": "small town that time forgot", "language": "Any"},
    {"text": "music for a world with one less person in it", "language": "Any"},
    {"text": "music from a parallel universe", "language": "Any"},
    {"text": "alternate timeline 1987", "language": "Any"},
    {"text": "songs that feel like the moon", "language": "Any"},
    {"text": "music that is the color grey", "language": "Any"},
    {"text": "the smell of petrichor in sound", "language": "Any"},
    {"text": "the feeling of almost remembering", "language": "Any"},
    {"text": "the specific dread of a sunday evening", "language": "Any"},
    {"text": "the anticipation before lightning strikes", "language": "Any"},
    {"text": "music for a recurring dream", "language": "Any"},
    {"text": "the last song on an album you can't name", "language": "Any"},
    {"text": "a song that shouldn't exist but does", "language": "Any"},
    {"text": "sql injection as a vibe", "language": "Any"},
    {"text": "asdfghjkl qwerty", "language": "Any"},
    {"text": "SELECT * FROM tracks WHERE vibe = 'good'", "language": "Any"},
    {"text": "", "language": "Any"},
    {"text": "", "language": "Any"},
    {"text": "     ", "language": "Any"},
    {"text": "123456789", "language": "Any"},
    {"text": "!@#$%^&*()", "language": "Any"},
    {"text": "اغنية حزينة عربية", "language": "Any"},
    {"text": "nostalgia dolore", "language": "Any"},
    {"text": "chanson triste pluie", "language": "Any"},
    {"text": "música triste lluvia", "language": "Any"},
    {"text": "南の風", "language": "Any"},
    {"text": "happy sad simultaneously", "language": "Any"},
    {"text": "calm but urgent", "language": "Any"},
    {"text": "slow and fast at the same time", "language": "Any"},
    {"text": "loud silence", "language": "Any"},
    {"text": "bright darkness", "language": "Any"},
    {"text": "hot ice", "language": "Any"},
    {"text": "soft thunder", "language": "Any"},
    {"text": "music that heals and hurts at once", "language": "Any"},
    {"text": "the feeling at the end of a long journey", "language": "Any"},
    {"text": "music for the moment before everything changes", "language": "Any"},
    {"text": "three words that feel like a whole life", "language": "Any"},
    {"text": "one last time", "language": "Any"},
    {"text": "almost", "language": "Any"},
    {"text": "not yet", "language": "Any"},
    {"text": "finally", "language": "Any"},
    {"text": "already", "language": "Any"},
    {"text": "still here", "language": "Any"},
    {"text": "gone now", "language": "Any"},
    {"text": "somewhere", "language": "Any"},
]

# ---------------------------------------------------------
# CONFIGURE CLEAN TEST LOGGER
# ---------------------------------------------------------
logger = logging.getLogger("QABatchTester_v8")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("qa_batch_results_v87.log", encoding="utf-8")
sh = logging.StreamHandler()
formatter = logging.Formatter("%(message)s")
fh.setFormatter(formatter)
sh.setFormatter(formatter)
logger.handlers = [fh, sh]

async def run_batch():
    db = Prisma()
    await db.connect()

    logger.info("=====================================================")
    logger.info("  VIBEFINDER AI: AUTOMATED EVALUATION PIPELINE v7.0  ")
    logger.info(f"  {len(PROMPTS)} PROMPTS — LIMIT BREAKER STRESS SUITE (LANGUAGE-AWARE)  ")
    logger.info("=====================================================\n")

    try:
        db_artists = await db.artistdirectory.find_many()
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        return

    # ── Entity Scanner helpers ──────────────────
    NEGATION_TOKENS = {"not", "no", "don't", "dont", "nothing", "avoid", "except", "without", "skip", "never"}

    def _is_negated_entity(entity: str, text: str) -> bool:
        pattern = rf'\b({"|".join(re.escape(n) for n in NEGATION_TOKENS)})\s+{re.escape(entity)}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    for idx, item in enumerate(PROMPTS, 1):
        text     = item["text"]
        language = item.get("language", "Any")
        logger.info(f"--- [PROMPT {idx}/{len(PROMPTS)}] ---")
        logger.info(f"INPUT:      \"{text}\"")
        logger.info(f"LANGUAGE:   {language}")

        request = VibeRequest(text=text, language=language, track_limit=5)
        prompt_lower = text.lower()
        prompt_word_count = len(prompt_lower.split())

        # Step 1: Run NLP
        vibe_data = vibe_engine.analyze_vibe_algorithm(
            text=request.text,
            artist_focus=request.artist_focus,
            genre_focus=50,
            bpm_focus=request.bpm_focus
        )

        detected_artist = None
        detected_song = None

        # Step 2: Entity Scanner (negation shield + word count guard)
        for a in db_artists:
            artist_name = a.name.lower()
            artist_pattern = rf'\b{re.escape(artist_name)}\b'

            if re.search(artist_pattern, prompt_lower):
                if _is_negated_entity(artist_name, prompt_lower):
                    continue
                detected_artist = a.name
                if a.songs:
                    for s in [s.strip().lower() for s in a.songs.split(",")]:
                        if s and re.search(rf'\b{re.escape(s)}\b', prompt_lower):
                            if not _is_negated_entity(s, prompt_lower):
                                detected_song = s
                                break
                break
            elif a.songs:
                for s in [s.strip().lower() for s in a.songs.split(",")]:
                    if (len(s) > 3
                            and s not in COMMON_WORDS_BLACKLIST
                            and re.search(rf'\b{re.escape(s)}\b', prompt_lower)):
                        if _is_negated_entity(s, prompt_lower):
                            continue
                        if prompt_word_count >= 10:
                            continue
                        detected_artist = a.name
                        detected_song = s
                        break
                if detected_artist:
                    break

        if detected_song and not detected_artist and vibe_data.get("confidence", 0) >= 0.30:
            detected_song = None

        vibe_data["detected_artist"] = detected_artist
        vibe_data["detected_song"] = detected_song

        # Step 3: Target genre resolution
        if detected_artist and vibe_data.get("confidence", 0) < 0.10:
            vibe_data["dominant_vibe"] = "artist_driven"
            target_genre = None
        else:
            _lang        = (request.language or "Any").strip()
            _lang_map    = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
            _dominant    = vibe_data.get("dominant_vibe", "")
            target_genre = (
                _lang_map.get(_dominant)
                or _lang_map.get("default")
                or vibe_data.get("genres", ["Dream Pop"])[0]
            )

        vibe_data["target_genre_override"] = target_genre

        # Step 4: Pool fetch
        is_fallback = False
        raw_pool = []

        if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist:
            is_fallback = True
            vibe_data["dominant_vibe"] = "Direct Search"
            vibe_data["secondary_vibe"] = "Fallback Mode"
            raw_pool = await fetch_lastfm_track_search(request.text, limit=100)
            JUNK_PATTERNS = re.compile(
                r'\b(podcast|episode|news|npr|bbc|ted talk|morning edition|'
                r'kitchen nightmares|speedrunning|let me explain|'
                r'how to make|react(?:ion)?|compilation|highlights)\b',
                re.IGNORECASE
            )
            raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(
                f"{t.get('title', '')} {t.get('artist', '')}")]

        elif vibe_data.get("dominant_vibe") == "artist_driven":
            raw_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=200)

        else:
            if target_genre:
                genre_pool = await fetch_lastfm_tracks(genre=target_genre, limit=100)
            else:
                genre_pool = []
            artist_pool = []
            if detected_artist and request.artist_focus > 25:
                artist_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=50)

            merged_pool = genre_pool + artist_pool
            seen = set()
            for t in merged_pool:
                ident = f"{t['title'].lower()}|{t['artist'].lower()}"
                if ident not in seen:
                    seen.add(ident)
                    raw_pool.append(t)

        # Step 5: Scoring
        best_tracks = []
        if raw_pool:
            best_tracks = filter_and_score_tracks(raw_pool, request, vibe_data, is_fallback=is_fallback)

        # Step 6: Log
        conf_pct = int(vibe_data.get("confidence", 0) * 100)
        logger.info(f"VIBE:       {vibe_data.get('dominant_vibe')} ({conf_pct}% confidence)")

        if vibe_data.get("secondary_vibe"):
            sec_conf = int(vibe_data.get("secondary_confidence", 0) * 100)
            logger.info(f"SECONDARY:  {vibe_data.get('secondary_vibe')} ({sec_conf}%)")

        if detected_artist:
            logger.info(f"ENTITY:     LOCKED to Artist: [{detected_artist}] | Song: [{detected_song}]")

        logger.info(f"GENRES:     {', '.join(vibe_data.get('genres', []))}")
        logger.info(f"BPM TARGET: {vibe_data.get('bpm_range')}")

        logger.info("TRACKS:")
        if not best_tracks:
            logger.info("  [!] SIGNAL LOST: Zero tracks returned (Fallback triggered or empty pool).")
        else:
            for i, t in enumerate(best_tracks, 1):
                bl_flag = " ⚠️ BLOCKLIST HIT" if f"{t.get('title','').lower()}|{t.get('artist','').lower()}" in TRACK_BLOCKLIST else ""
                logger.info(f"  {i}. {t.get('title')} - {t.get('artist')}{bl_flag}")

        logger.info("\n" + "-" * 50 + "\n")

    await db.disconnect()
    logger.info("=== AUTOMATED BATCH TEST v5.0 COMPLETE ===")
    logger.info(f"=== TOTAL PROMPTS RUN: {len(PROMPTS)} ===")

if __name__ == "__main__":
    asyncio.run(run_batch())
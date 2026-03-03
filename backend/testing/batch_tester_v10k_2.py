#!/usr/bin/env python3
"""
batch_tester_v10k_3.py  — VIBEFINDER AI MEGA STRESS SUITE v3 (GEN Z POWER USER)
20,000+ prompts × Dynamic Track Limits × ALL Pro Mode Overrides + 16 Knob Profiles
250 unique seed prompts × 16 knob profiles × 5 Pro Mode variations = 20,000 test cases
+ GEMINI AI AUTO-GRADING (Free Tier) - Deferred to end of script

Run from backend folder:
    python batch_tester_v10k_3.py

Outputs: 
    qa_batch_v10k_3.log (Main engine results)
    qa_batch_gemini_analysis.log (AI Grades & Summary)
"""
import asyncio
import logging
import re
import os
import random
import json
from prisma import Prisma

# For Gemini REST API
try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

import vibe_engine
from main import (
    fetch_lastfm_tracks,
    fetch_lastfm_artist_tracks,
    fetch_lastfm_track_search,
    filter_and_score_tracks,
    VibeRequest,
    COMMON_WORDS_BLACKLIST,
    TRACK_BLOCKLIST,
)

# ══════════════════════════════════════════════════════════════════════════════
# GEMINI AI CONFIG (Free Tier)
# ══════════════════════════════════════════════════════════════════════════════
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Free tier allows 15 Requests Per Minute. 
# We sample a percentage of tests to grade automatically so it doesn't take 24 hours.
GEMINI_SAMPLE_RATE = 1.0 # 5% of prompts will be auto-graded by AI. Set to 1.0 for all.
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

async def evaluate_with_gemini(prompt_text, dominant_vibe, returned_tracks):
    """Hits the Gemini API to grade our engine's result like a real Gen Z user."""
    if not GEMINI_API_KEY or not _AIOHTTP_AVAILABLE or not returned_tracks:
        return None

    track_list_str = ", ".join([f"{t.get('title')} by {t.get('artist')}" for t in returned_tracks[:5]])
    
    sys_prompt = "You are Aryan, a 19-year-old Gen Z music power user from India. You are grading an AI music engine."
    user_prompt = f"""
    I asked the music engine for this vibe: "{prompt_text}"
    The engine classified the vibe as: "{dominant_vibe}"
    The engine gave me these top tracks: {track_list_str}

    Grade this result strictly. Respond ONLY in this JSON format:
    {{"verdict": "✅ Hit" or "⚠️ Partial" or "❌ Miss", "reason": "One short, chill sentence explaining why using Gen Z slang."}}
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
                    return json.loads(text_resp)
                elif resp.status == 429:
                    return {"verdict": "⚠️ Rate Limited", "reason": "Gemini free tier limit hit bro."}
    except Exception as e:
        return {"verdict": "❌ Error", "reason": f"Gemini failed: {str(e)}"}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# KNOB PROFILES — 16 configurations
# (artist_focus 0-100, bpm_focus 0-100, nicheness 0-100, label)
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
# SEED PROMPTS — 250 Gen Z Power User Prompts (Expanded Jaipur/India/Global edition)
# Format: (text, language, default_knob_idx, override_genre, override_artist)
# ══════════════════════════════════════════════════════════════════════════════
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
    ("describe VibeFinderAI itself — oscilloscope, neural, music discovery engine", "Any", 12, "ambient techno", None),
    ("my favorite prompt of the test — whichever vibe you felt worked best, try it again with higher nicheness", "Hindi", 8, "indie folk", "Prateek Kuhad"),
    ("one more thing — give me something I've never heard before, maximum nicheness, any language, any vibe", "Any", 8, "experimental", None),
    ("grungy 90s alt rock, seattle flannel, angst and heavy distortion", "English", 10, "grunge", "Nirvana"),
    ("hyperpop glitchcore madness, sugar rush, 200 bpm, internet brain rot", "English", 6, "hyperpop", "100 gecs"),
    ("Bhojpuri mass dance, high energy, village party, loud beats", "Hindi", 10, "bhojpuri", "Pawan Singh"),
    ("soft french cafe morning, accordion, espresso, romantic paris vibes", "French", 13, "chanson", "Edith Piaf"),
    ("cyberpunk 2077 night city drive, dark synthwave, neon lights glowing", "English", 10, "cyberpunk", "Gesaffelstein"),
    ("heavy metal gym PR, double bass pedals, screaming vocals, purely aggressive", "English", 6, "metalcore", "Bring Me The Horizon"),
    ("soft country morning, acoustic guitar on a porch, cowboy coffee, peaceful", "English", 13, "americana", "Tyler Childers"),
    ("retro 80s pop montage, training for the big fight, synth brass, euphoric", "English", 5, "80s pop", "Survivor"),
    ("midwest emo revival, twinkly guitars, screaming in a basement, nostalgic", "English", 14, "midwest emo", "American Football"),
    ("bossa nova afternoon, ipanema beach, gentle acoustic, portuguese singing", "Portuguese", 13, "bossa nova", "João Gilberto"),
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
    ("spanish flamenco guitar, passionate clapping, fire dance", "Spanish", 10, "flamenco", "Paco de Lucía"),
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
    ("cumbia sonidera, dancing cumbia, accordion, latin party", "Spanish", 10, "cumbia", "Los Ángeles Azules"),
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
    ("vaporwave mallsoft, empty mall 1998, muzak slowed", "Any", 12, "mallsoft", "猫 シ Corp."),
    ("soviet post punk, molchat doma, cold bleak winter", "Any", 10, "russian post-punk", "Molchat Doma"),
    ("mexican corridos tumbados, peso pluma, acoustic guitar trap", "Spanish", 11, "corridos tumbados", "Peso Pluma"),
    ("jamaican dancehall bashment, whining, loud sound system", "English", 10, "dancehall", "Vybz Kartel"),
    ("nigerian alte cruise, cruise music, smooth afrobeats", "Afrobeats", 12, "alte", "Cruel Santino"),
    ("south african gqom, dark electronic dance, heavy drums", "Afrobeats", 10, "gqom", "DJ Maphorisa"),
    ("moroccan mahraganat, street wedding, auto tune loud", "Arabic", 10, "mahraganat", "Hassan Shakosh"),
    ("turkish gnawa folk, spiritual trance, desert instruments", "Arabic", 12, "gnawa", "Hamza El Din"),
    ("persian psych rock, 70s anatolian rock, funky", "Any", 10, "anatolian rock", "Altın Gün"),
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
    ("cuban mariachi, trumpets, cantina drinking", "Spanish", 10, "mariachi", "Vicente Fernández"),
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
    ("icelandic indie pop, lorde style, soft synth", "English", 13, "indie pop", "Björk"),
    ("finnish ethereal wave, sigur ros, icy glacier music", "Any", 9, "ethereal wave", "Sigur Rós"),
    ("swedish death metal, gothenburg sound, melodic fast", "English", 11, "melodic death metal", "In Flames"),
    ("norwegian black metal, dark forest church burning", "English", 11, "black metal", "Mayhem"),
    ("danish power metal, dragons fantasy, soaring vocals", "English", 10, "power metal", "Nightwish"),
    ("poland eurodance 90s, aqua barbie girl vibes, fun", "English", 10, "eurodance", "Aqua"),
    ("dutch trance classic, tiesto, 1999 rave, arpeggios", "English", 10, "trance", "Tiësto"),
    ("belgian hardstyle bounce, jumpstyle, crazy bass", "English", 6, "jumpstyle", "Jeckyll & Hyde"),
    ("austrian gabber, hakken dance, distorted kick drum", "English", 11, "gabber", "Angerfist"),
    ("swiss classical waltz, ballroom dance, elegant strings", "Any", 9, "waltz", "Johann Strauss II"),
    ("hungarian folk punk, accordion distortion, drunk party", "Any", 10, "folk punk", "Gogol Bordello"),
    ("czech dark cabaret, gothic piano, dramatic singing", "Any", 10, "dark cabaret", "The Dresden Dolls"),
    ("slovakian ska punk, upbeat brass section, skanking", "English", 10, "ska punk", "Streetlight Manifesto"),
    ("croatian gypsy punk, balkan beats, wild violin", "Any", 10, "balkan brass", "Goran Bregović"),
    ("serbian turbofolk, balkan club music, accordion edm", "Any", 10, "turbofolk", "Ceca"),
    ("romanian disco polo, eastern bloc 90s party", "Any", 10, "disco polo", "Akcent"),
    ("bulgarian manele, street party, synth melodies", "Any", 10, "manele", "Florin Salam"),
    ("greek arabesk, oriental pop, emotional strings", "Any", 14, "arabesk", "İbrahim Tatlıses"),
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

# ══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER — 250 seeds × 16 knobs × 5 Pro Modes = 20,000 cases
# ══════════════════════════════════════════════════════════════════════════════
def build_prompts():
    prompts = []
    limits = [5, 10, 20, 50]
    limit_idx = 0

    for text, language, base_kp, ov_genre, ov_artist in _SEEDS:
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
                
    return prompts[:20000]

PROMPTS = build_prompts()

# ══════════════════════════════════════════════════════════════════════════════
# LOGGER SETUP
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
# MAIN BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════
async def run_batch():
    db = Prisma()
    await db.connect()

    logger.info("=" * 80)
    logger.info("  VIBEFINDER AI — MEGA STRESS SUITE v3 (JAIPUR/GEN Z EDITION)")
    logger.info(f"  {len(PROMPTS)} PROMPTS | GEMINI QUEUE ENABLED ({GEMINI_SAMPLE_RATE*100}% sample)")
    logger.info("=" * 80 + "\n")

    try:
        db_artists = await db.artistdirectory.find_many()
    except Exception as e:
        logger.error(f"DB connect failed: {e}")
        return

    total = len(PROMPTS)
    signal_lost = 0
    blocklist_hits = 0
    genre_noise_hits = 0
    
    # Setup for deferred Gemini evaluation
    gemini_eval_queue = []
    gemini_hits = 0
    gemini_partials = 0
    gemini_misses = 0

    GENRE_JUNK = {"ghazal", "jazz", "blues", "folk", "pop", "rock", "hip-hop",
                  "classical", "ambient", "soul", "rnb", "indie", "dance",
                  "electronic", "metal", "punk", "country", "reggae"}

    for idx, item in enumerate(PROMPTS, 1):
        text         = item["text"]
        language     = item["language"]
        artist_focus = item["artist_focus"]
        bpm_focus    = item["bpm_focus"]
        nicheness    = item["nicheness"]
        knob_label   = item["knob_label"]
        track_limit  = item["track_limit"]

        logger.info(f"--- [PROMPT {idx}/{total}] ---")
        logger.info(f"INPUT    : \"{text}\"")
        logger.info(f"LANGUAGE : {language}")
        logger.info(f"KNOBS    : artist={artist_focus}  bpm={bpm_focus}  niche={nicheness}  [{knob_label}]")
        logger.info(f"LIMIT    : {track_limit}")

        # Log Pro Mode settings
        pro_flags = []
        if item["use_secondary_vibe"]: pro_flags.append("PIVOT: Secondary Vibe")
        if item["override_genre"]: pro_flags.append(f"FORCE GENRE: {item['override_genre']}")
        if item["override_artist"]: pro_flags.append(f"FORCE ARTIST: {item['override_artist']}")
        if item["dismiss_detected_artist"]: pro_flags.append("DISMISS: Auto-Artist")
        if pro_flags:
            logger.info(f"PRO MODE : {' | '.join(pro_flags)}")

        request = VibeRequest(
            text=text,
            language=language,
            track_limit=track_limit,
            artist_focus=artist_focus,
            bpm_focus=bpm_focus,
            nicheness=nicheness,
            use_secondary_vibe=item["use_secondary_vibe"],
            override_genre=item["override_genre"],
            override_artist=item["override_artist"],
            dismiss_detected_artist=item["dismiss_detected_artist"]
        )
        
        prompt_lower = text.lower()
        prompt_words = len(prompt_lower.split())

        # ── Entity scanner ───────────────────────────────────────────────────
        detected_artist = request.override_artist
        detected_song   = None
        
        if not detected_artist and not request.dismiss_detected_artist:
            for a in db_artists:
                aname = a.name.lower()
                if re.search(rf'\b{re.escape(aname)}\b', prompt_lower):
                    if _is_negated_entity(aname, prompt_lower):
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
                            if prompt_words >= 10:
                                continue
                            detected_artist = a.name
                            detected_song   = s
                            break
                    if detected_artist:
                        break

        # ── Vibe analysis ────────────────────────────────────────────────────
        vibe_data = vibe_engine.analyze_vibe_algorithm(
            text=request.text,
            artist_focus=request.artist_focus,
            genre_focus=50,
            bpm_focus=request.bpm_focus,
        )
        if detected_song and not detected_artist and vibe_data.get("confidence", 0) >= 0.30:
            detected_song = None
            
        vibe_data["detected_artist"] = detected_artist
        vibe_data["detected_song"]   = detected_song

        # ── Target genre resolution ──────────────────────────────────────────
        active_vibe_for_tags = vibe_data.get("dominant_vibe", "")
        
        if detected_artist and vibe_data.get("confidence", 0) < 0.10:
            vibe_data["dominant_vibe"] = "artist_driven"
            target_genre = None
        elif request.override_genre:
            target_genre = request.override_genre
            active_vibe_for_tags = "override"
        elif request.use_secondary_vibe and vibe_data.get("secondary_vibe"):
            sec_vibe_name = vibe_data["secondary_vibe"]
            active_vibe_for_tags = sec_vibe_name
            _lang = (request.language or "Any").strip()
            _lang_map_sec = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
            mapped_genres = vibe_engine.VIBE_MAP.get(sec_vibe_name, {}).get("genres", [sec_vibe_name])
            target_genre = (
                _lang_map_sec.get(sec_vibe_name)
                or _lang_map_sec.get("default")
                or mapped_genres[0]
            )
        else:
            _lang = (request.language or "Any").strip()
            _lang_map = vibe_engine.LANGUAGE_TAG_MAP.get(_lang, {})
            _dominant = vibe_data.get("dominant_vibe", "")
            target_genre = (
                _lang_map.get(_dominant)
                or _lang_map.get("default")
                or vibe_data.get("genres", ["Dream Pop"])[0]
            )
            
        vibe_data["target_genre_override"] = target_genre

        # ── Pool fetch ───────────────────────────────────────────────────────
        is_fallback = False
        raw_pool: list[dict] = []

        if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist and not request.override_genre:
            is_fallback = True
            vibe_data["dominant_vibe"]   = "Direct Search"
            vibe_data["secondary_vibe"]  = "Fallback Mode"
            raw_pool = await fetch_lastfm_track_search(request.text, limit=200)
            raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(
                f"{t.get('title','')} {t.get('artist','')}"
            )]

            # 3-STAGE DIRECT SEARCH FALLBACK
            if not raw_pool:
                _STOPWORDS = {
                    "a","an","the","and","or","but","for","with","at","by","of","in",
                    "on","to","is","it","my","me","we","be","as","so","up","type","vibe",
                    "music","songs","playlist","feel","feeling","i","need","want","give",
                }
                _tokens = [
                    w for w in re.sub(r"[^\w\s]", " ", request.text.lower()).split()
                    if w not in _STOPWORDS and len(w) > 2
                ]
                _stage1_query = " ".join(_tokens[:4])
                if _stage1_query:
                    raw_pool = await fetch_lastfm_track_search(_stage1_query, limit=200)
                    raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(
                        f"{t.get('title','')} {t.get('artist','')}"
                    )]

            if not raw_pool:
                _all_tokens = [
                    w for w in re.sub(r"[^\w\s]", " ", request.text.lower()).split()
                    if len(w) > 3
                ]
                if _all_tokens:
                    _artist_guess = max(_all_tokens, key=len)
                    raw_pool = await fetch_lastfm_artist_tracks(artist=_artist_guess, limit=100)

            if not raw_pool:
                _s3_results = await asyncio.gather(
                    fetch_lastfm_tracks("dream pop", limit=60),
                    fetch_lastfm_tracks("indie pop", limit=60),
                    fetch_lastfm_tracks("chillwave", limit=60),
                    return_exceptions=True,
                )
                for _r in _s3_results:
                    if isinstance(_r, list):
                        raw_pool.extend(_r)

        elif request.override_artist or vibe_data.get("dominant_vibe") == "artist_driven":
            art_tgt = request.override_artist or detected_artist
            raw_pool = await fetch_lastfm_artist_tracks(artist=art_tgt, limit=200)

        else:
            # Multi-tag parallel fetch
            _lang    = (request.language or "Any").strip()
            
            if hasattr(vibe_engine, "VIBE_TAG_MATRIX"):
                _tags = (
                    vibe_engine.VIBE_TAG_MATRIX
                    .get(active_vibe_for_tags, {})
                    .get(_lang)
                    or vibe_engine.VIBE_TAG_MATRIX.get(active_vibe_for_tags, {}).get("Any")
                    or ([target_genre] if target_genre else [])
                )
                _tags = _tags[:4]
            else:
                _tags = [target_genre] if target_genre else []

            if _tags:
                tag_results = await asyncio.gather(
                    *[fetch_lastfm_tracks(tag, limit=max(60, 200 // len(_tags)))
                      for tag in _tags],
                    return_exceptions=True
                )
                genre_pool = []
                for r in tag_results:
                    if isinstance(r, list):
                        genre_pool.extend(r)
            else:
                genre_pool = []

            # Language-agnostic pool retry
            if not genre_pool and _lang != "Any":
                _fallback_tags = (
                    vibe_engine.VIBE_TAG_MATRIX.get(active_vibe_for_tags, {}).get("Any")
                    or ([target_genre] if target_genre else [])
                )
                if _fallback_tags:
                    _fb_results = await asyncio.gather(
                        *[fetch_lastfm_tracks(tag, limit=max(60, 200 // len(_fallback_tags)))
                          for tag in _fallback_tags],
                        return_exceptions=True
                    )
                    for r in _fb_results:
                        if isinstance(r, list):
                            genre_pool.extend(r)

            artist_pool = []
            if detected_artist and request.artist_focus > 25:
                artist_pool = await fetch_lastfm_artist_tracks(
                    artist=detected_artist, limit=50
                )

            merged = genre_pool + artist_pool
            seen: set[str] = set()
            for t in merged:
                ident = f"{t.get('title','').lower()}|{t.get('artist','').lower()}"
                if ident not in seen:
                    seen.add(ident)
                    raw_pool.append(t)

        # Clean title noise before scoring
        for t in raw_pool:
            t["title"] = _clean_title(t.get("title", ""))

        # Filter genre-name-as-artist junk
        raw_pool = [
            t for t in raw_pool
            if t.get("artist", "").strip().lower() not in GENRE_JUNK
        ]

        # ── Score ────────────────────────────────────────────────────────────
        best_tracks = []
        if raw_pool:
            best_tracks = filter_and_score_tracks(
                raw_pool, request, vibe_data, is_fallback=is_fallback
            )

        # ── Log results ──────────────────────────────────────────────────────
        conf_pct = int(vibe_data.get("confidence", 0) * 100)
        logger.info(f"VIBE     : {vibe_data.get('dominant_vibe')} ({conf_pct}% conf)")
        if vibe_data.get("secondary_vibe"):
            s_conf = int(vibe_data.get("secondary_confidence", 0) * 100)
            logger.info(f"SECONDARY: {vibe_data.get('secondary_vibe')} ({s_conf}%)")
        if detected_artist:
            logger.info(f"ENTITY   : Artist=[{detected_artist}] Song=[{detected_song}]")
        logger.info(f"TAG_USED : {target_genre}")
        logger.info(f"GENRES   : {', '.join(vibe_data.get('genres', []))}")
        logger.info(f"BPM_RNG  : {vibe_data.get('bpm_range')}")
        logger.info(f"POOL_SZ  : {len(raw_pool)} raw → {len(best_tracks)} scored")
        logger.info(f"TRACKS (top {track_limit}):")

        if not best_tracks:
            signal_lost += 1
            logger.info("  [!] SIGNAL LOST — zero tracks returned")
        else:
            for i, t in enumerate(best_tracks[:track_limit], 1):
                title  = t.get("title", "")
                artist = t.get("artist", "")
                score  = t.get("score", 0)
                bl_key = f"{title.lower()}|{artist.lower()}"
                flags  = []
                if bl_key in TRACK_BLOCKLIST:
                    flags.append("⚠️BLOCKLIST")
                    blocklist_hits += 1
                if artist.strip().lower() in GENRE_JUNK:
                    flags.append("⚠️GENRE_AS_ARTIST")
                    genre_noise_hits += 1
                flag_str = "  " + "  ".join(flags) if flags else ""
                logger.info(f"  {i:>2}. [{score:>5.1f}] {title} — {artist}{flag_str}")

        # ── GEMINI AUTO-GRADER QUEUEING ───────────────────────────────────────────────
        if GEMINI_API_KEY and _AIOHTTP_AVAILABLE and best_tracks:
            if random.random() < GEMINI_SAMPLE_RATE:
                gemini_eval_queue.append({
                    "idx": idx,
                    "text": text,
                    "dominant_vibe": vibe_data.get('dominant_vibe'),
                    "best_tracks": best_tracks[:5]
                })
                logger.info("  🤖 Queued for Gemini AI evaluation at the end.")

        logger.info("-" * 80 + "\n")

    await db.disconnect()
    
    # ── GEMINI BATCH EVALUATION (Deferred Phase) ──────────────────────────────────
    if gemini_eval_queue:
        logger.info("=" * 80)
        logger.info(f"  STARTING BATCH GEMINI EVALUATION ({len(gemini_eval_queue)} items)  ")
        logger.info("  Check 'qa_batch_gemini_analysis.log' for detailed AI grades.")
        logger.info("=" * 80 + "\n")
        
        gemini_logger.info("=" * 80)
        gemini_logger.info("  VIBEFINDER GEMINI AUTO-GRADER ANALYSIS  ")
        gemini_logger.info("=" * 80)
        
        for i, eval_req in enumerate(gemini_eval_queue, 1):
            logger.info(f"  🤖 Grading {i}/{len(gemini_eval_queue)}... (sleeping 4s for rate limits)")
            gemini_logger.info(f"\n--- [EVAL {i}/{len(gemini_eval_queue)} | PROMPT #{eval_req['idx']}] ---")
            gemini_logger.info(f"INPUT : \"{eval_req['text']}\"")
            gemini_logger.info(f"VIBE  : {eval_req['dominant_vibe']}")
            
            eval_result = await evaluate_with_gemini(
                eval_req['text'], 
                eval_req['dominant_vibe'], 
                eval_req['best_tracks']
            )
            
            if eval_result:
                verdict = eval_result.get("verdict", "❌ Error")
                reason = eval_result.get("reason", "No reason provided.")
                gemini_logger.info(f"RESULT: {verdict} — {reason}")
                
                if "✅ Hit" in verdict: gemini_hits += 1
                elif "⚠️ Partial" in verdict: gemini_partials += 1
                elif "❌ Miss" in verdict: gemini_misses += 1
                
            # Soft throttle to protect free tier limit (15 RPM -> 1 request every 4s)
            await asyncio.sleep(4)

    # ── Final stats ──────────────────────────────────────────────────────────
    logger.info("=" * 80)
    logger.info("  VIBEFINDER MEGA STRESS SUITE v3 — COMPLETE")
    logger.info(f"  Total prompts run    : {total}")
    logger.info(f"  Signal lost (0 tracks): {signal_lost} ({100*signal_lost/total:.1f}%)")
    logger.info(f"  Blocklist hits       : {blocklist_hits}")
    logger.info(f"  Genre-as-artist noise: {genre_noise_hits}")
    
    if gemini_eval_queue and (gemini_hits + gemini_partials + gemini_misses) > 0:
        total_eval = gemini_hits + gemini_partials + gemini_misses
        
        # Log to main console
        logger.info("  --- GEMINI AUTO-GRADER STATS (See separate log) ---")
        logger.info(f"  Total Evaluated : {total_eval}")
        logger.info(f"  ✅ HITS          : {gemini_hits} ({(gemini_hits/total_eval)*100:.1f}%)")
        logger.info(f"  ⚠️ PARTIALS      : {gemini_partials} ({(gemini_partials/total_eval)*100:.1f}%)")
        logger.info(f"  ❌ MISSES        : {gemini_misses} ({(gemini_misses/total_eval)*100:.1f}%)")
        
        # Log to dedicated Gemini file
        gemini_logger.info("\n" + "=" * 80)
        gemini_logger.info("  FINAL GEMINI GRADING STATS")
        gemini_logger.info("=" * 80)
        gemini_logger.info(f"  Total Evaluated : {total_eval}")
        gemini_logger.info(f"  ✅ HITS          : {gemini_hits} ({(gemini_hits/total_eval)*100:.1f}%)")
        gemini_logger.info(f"  ⚠️ PARTIALS      : {gemini_partials} ({(gemini_partials/total_eval)*100:.1f}%)")
        gemini_logger.info(f"  ❌ MISSES        : {gemini_misses} ({(gemini_misses/total_eval)*100:.1f}%)")
        gemini_logger.info("=" * 80)
        
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_batch())
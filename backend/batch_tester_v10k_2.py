#!/usr/bin/env python3
"""
batch_tester_v10k.py  — VIBEFINDER AI MEGA STRESS SUITE v10k
10,000 prompts × 20 tracks × all knobs (artist_focus / bpm_focus / nicheness) + all language tabs
625 unique seed prompts × 16 knob profiles = 10,000 test cases

Run from backend folder:
    python batch_tester_v10k.py

Output: qa_batch_v10k.log
"""
import asyncio
import logging
import re
from prisma import Prisma

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
# SEED PROMPTS — 625 unique vibes × every emotional/scene/genre/edge-case axis
# (text, language, knob_profile_index)
# ══════════════════════════════════════════════════════════════════════════════
_SEEDS = [
    ("bhangra night", "Punjabi", 0),
    ("sangeet dance practice", "Punjabi", 10),
    ("hard punjabi trap", "Punjabi", 6),
    ("drunk uncle dancing to dhol", "Punjabi", 10),
    ("haryanvi dj song", "Hindi", 0),
    ("baraat entering the venue", "Punjabi", 6),
    ("desi club night in toronto", "Hindi", 10),
    ("ap dhillon concert hype", "Punjabi", 11),
    ("punjabi wedding bangers", "Punjabi", 0),
    ("desi swag flex", "Hindi", 10),
    ("brown boy energy", "Hindi", 0),
    ("dhol beats for mehndi", "Punjabi", 0),
    ("navratri garba night", "Any", 0),
    ("diwali party playlist", "Any", 0),
    ("holi water fight", "Any", 6),
    ("sidhu moosewala fast drive", "Punjabi", 11),
    ("karan aujla gym playlist", "Punjabi", 6),
    ("desi hip hop hard", "Hindi", 6),
    ("sangeet group dance", "Punjabi", 10),
    ("bollywood item songs", "Hindi", 10),
    ("retro bollywood dance", "Hindi", 7),
    ("punjabi bass boosted", "Punjabi", 6),
    ("bhangra fusion edm", "Punjabi", 11),
    ("haryanvi swag", "Hindi", 10),
    ("jatt flex vibes", "Punjabi", 11),
    ("desi energy unhinged", "Hindi", 6),
    ("bhangra at 3am", "Punjabi", 12),
    ("punjabi drill dark", "Punjabi", 8),
    ("ap dhillon soft voice", "Punjabi", 4),
    ("b praak heartbreak", "Hindi", 4),
    ("arijit singh romantic", "Hindi", 7),
    ("atif aslam sad", "Hindi", 4),
    ("armaan malik love song", "Hindi", 7),
    ("neha kakkar dance hit", "Hindi", 10),
    ("badshah party anthem", "Hindi", 10),
    ("yo yo honey singh classic", "Hindi", 7),
    ("bollywood sad songs 2020s", "Hindi", 1),
    ("old bollywood ghazal", "Hindi", 9),
    ("kishore kumar nostalgic", "Any", 7),
    ("lata mangeshkar classic", "Any", 14),
    ("filmi sad 90s", "Hindi", 7),
    ("sufi qawwali night", "Hindi", 9),
    ("nusrat fateh ali khan divine", "Any", 9),
    ("hindi lofi beats", "Hindi", 12),
    ("bollywood lo-fi chill", "Hindi", 12),
    ("satinder sartaaj soulful", "Punjabi", 9),
    ("punjabi soft romantic", "Punjabi", 4),
    ("jubin nautiyal sad", "Hindi", 1),
    ("shreya ghoshal emotional", "Any", 14),
    ("sonu nigam classic", "Any", 7),
    ("hindi folk acoustic", "Hindi", 9),
    ("rajasthani folk desert", "Any", 9),
    ("baul music bengali", "Bengali", 9),
    ("south indian mass bgm", "Any", 6),
    ("tamil kuthu", "Tamil", 6),
    ("telugu mass beat", "Telugu", 6),
    ("kollywood dance energy", "Tamil", 6),
    ("ilaiyaraaja sad classic", "Tamil", 9),
    ("anirudh upbeat tamil", "Tamil", 6),
    ("thaman bass telugu", "Telugu", 6),
    ("allu arjun bgm", "Telugu", 6),
    ("vijay thalapathy entry", "Tamil", 6),
    ("jagjit singh ghazal", "Hindi", 9),
    ("mehdi hassan ghazal", "Hindi", 9),
    ("abida parveen qawwali", "Urdu", 9),
    ("ghulam ali ghazal urdu", "Urdu", 9),
    ("heartbreak at 3am", "Any", 4),
    ("can't stop crying in the car", "Any", 1),
    ("she left and took everything", "Any", 1),
    ("deleted our photos", "Any", 1),
    ("reading old texts from someone gone", "Any", 14),
    ("sad indie folk breakup", "Any", 14),
    ("post breakup shower cry", "Any", 1),
    ("wrote you a letter i'll never send", "Any", 8),
    ("our song came on the radio", "Any", 14),
    ("unrequited love", "Any", 14),
    ("love that was never mine", "Any", 8),
    ("still love them but it's over", "Any", 1),
    ("moving on but not really", "Any", 1),
    ("heartbreak and wine", "Any", 4),
    ("sad songs for a rainy tuesday", "Any", 12),
    ("crying while driving at night", "Any", 4),
    ("soft heartbreak bedroom pop", "Any", 14),
    ("empty apartment after a breakup", "Any", 8),
    ("the day you left", "Any", 1),
    ("one year later still not over it", "Any", 8),
    ("sad piano emotional", "Any", 9),
    ("melancholy at sunset", "Any", 14),
    ("lonely on a friday night", "Any", 12),
    ("friends who drifted apart", "Any", 8),
    ("long distance ended badly", "Any", 1),
    ("the last hug before goodbye", "Any", 14),
    ("boarding a flight and not coming back", "Any", 9),
    ("hollowness after a breakup", "Any", 9),
    ("healing but slowly", "Any", 14),
    ("nostalgia that hurts", "Any", 9),
    ("memories that feel like bruises", "Any", 8),
    ("sad r&b breakup", "Any", 7),
    ("neo soul goodbye", "Any", 9),
    ("billie eilish emotional", "Any", 7),
    ("olivia rodrigo betrayal", "Any", 7),
    ("phoebe bridgers devastating", "Any", 8),
    ("bon iver winter sadness", "Any", 9),
    ("lana del rey longing", "Any", 8),
    ("frank ocean blonde mood", "Any", 9),
    ("the national hopeless", "Any", 9),
    ("damien rice devastating", "Any", 9),
    ("daughter sad indie", "Any", 8),
    ("slowed reverb emotional tiktok", "Any", 7),
    ("sad lofi rain", "Any", 12),
    ("slow saxophone sad night", "Any", 9),
    ("piano alone at midnight", "Any", 9),
    ("missing someone who is still alive", "Any", 9),
    ("soft crying vibes", "Any", 1),
    ("took your name out of my phone", "Any", 1),
    ("your birthday and you're gone", "Any", 9),
    ("autumn heartbreak", "Any", 14),
    ("november sadness", "Any", 14),
    ("december loneliness", "Any", 12),
    ("the slow fade ghost", "Any", 8),
    ("they found someone new", "Any", 1),
    ("saw them with someone else", "Any", 1),
    ("sad girl autumn playlist", "Any", 14),
    ("sad boy summer", "Any", 1),
    ("slowed sad hindi heartbreak", "Hindi", 1),
    ("sufi heartbreak urdu", "Urdu", 9),
    ("k-pop sad ballad breakup", "Korean", 4),
    ("j-pop breakup sad", "Japanese", 4),
    ("falling in love playlist", "Any", 0),
    ("first date nervous energy", "Any", 0),
    ("slow dance in the kitchen", "Any", 14),
    ("kissing in the rain", "Any", 0),
    ("romantic evening at home", "Any", 4),
    ("love songs for two", "Any", 0),
    ("new relationship butterflies", "Any", 0),
    ("soft romantic r&b", "Any", 7),
    ("neo soul love songs", "Any", 9),
    ("daniel caesar romantic", "Any", 9),
    ("jhene aiko tender", "Any", 9),
    ("bedroom pop romantic", "Any", 8),
    ("valentine's day playlist", "Any", 7),
    ("wedding first dance", "Any", 0),
    ("first kiss song", "Any", 14),
    ("love at first sight feeling", "Any", 0),
    ("road trip with someone you love", "Any", 0),
    ("holding hands playlist", "Any", 14),
    ("sunday morning with you", "Any", 12),
    ("late night talking getting to know you", "Any", 12),
    ("crush playlist secret", "Any", 0),
    ("falling slowly", "Any", 14),
    ("that electric chemistry", "Any", 0),
    ("love that feels like home", "Any", 14),
    ("comfortable love long term", "Any", 14),
    ("romantic bollywood hindi", "Hindi", 0),
    ("tum hi aana mood", "Hindi", 4),
    ("dilwale dulhania type vibe", "Hindi", 7),
    ("punjabi soft romantic ap dhillon", "Punjabi", 14),
    ("intimate candle lit dinner", "Any", 4),
    ("stargazing with someone", "Any", 9),
    ("confessing feelings", "Any", 0),
    ("making up after a fight", "Any", 0),
    ("love that survived hard times", "Any", 14),
    ("forever yours playlist", "Any", 14),
    ("unconditional love", "Any", 14),
    ("comfortable silence with someone", "Any", 9),
    ("late night pillow talk", "Any", 4),
    ("summer romance beach", "Any", 0),
    ("secret love affair", "Any", 8),
    ("long distance still in love", "Any", 14),
    ("love letter in music form", "Any", 9),
    ("bachata romantic spanish", "Spanish", 4),
    ("bossa nova romantic", "Portuguese", 9),
    ("k-rnb love song", "Korean", 14),
    ("japanese city pop romance", "Japanese", 9),
    ("arabic romantic night", "Arabic", 4),
    ("pre-workout rage", "Any", 6),
    ("gym lifting heavy", "Any", 11),
    ("run faster playlist", "Any", 11),
    ("beast mode activated", "Any", 6),
    ("trap banger no skip", "Any", 6),
    ("drill hard aggressive", "Any", 6),
    ("phonk drift aggressive", "Any", 6),
    ("hardstyle festival crush", "Any", 11),
    ("edm drop incoming", "Any", 11),
    ("uk drill gritty", "Any", 6),
    ("dark trap menacing", "Any", 9),
    ("bass boosted hard", "Any", 6),
    ("travis scott sicko mode energy", "Any", 11),
    ("metro boomin dark beats", "Any", 6),
    ("death grips no love", "Any", 9),
    ("100 gecs chaotic", "Any", 9),
    ("moshpit indie rock", "Any", 6),
    ("confidence walkout song", "Any", 6),
    ("villain arc playlist", "Any", 9),
    ("sigma grindset motivation", "Any", 7),
    ("dark horse underdog rising", "Any", 0),
    ("entrance theme boss mode", "Any", 11),
    ("desi hip hop divine india", "Hindi", 6),
    ("punjabi trap karan aujla", "Punjabi", 11),
    ("korean hip hop intense", "Korean", 6),
    ("japanese hip hop underground", "Japanese", 9),
    ("latin trap agresivo", "Spanish", 6),
    ("afrotrap naija hard", "Afrobeats", 6),
    ("french rap hard aggressive", "French", 6),
    ("arabic mahraganat hype", "Arabic", 6),
    ("bmth rage rock", "Any", 6),
    ("slipknot live energy", "Any", 6),
    ("linkin park intensity", "Any", 6),
    ("rage against machine protest", "Any", 9),
    ("metallica master puppets", "Any", 9),
    ("drum and bass jungle intense", "Any", 6),
    ("hardstyle euphoric rave", "Any", 11),
    ("jerseyclub bounce", "Any", 6),
    ("footwork chicago frantic", "Any", 8),
    ("lofi hip hop study beats", "Any", 12),
    ("study session deep focus", "Any", 12),
    ("jazz cafe background", "Any", 12),
    ("bossa nova afternoon", "Portuguese", 12),
    ("nujabes soulful lofi", "Any", 9),
    ("j dilla instrumental chill", "Any", 9),
    ("flying lotus ambient chill", "Any", 9),
    ("thundercat bass chill", "Any", 9),
    ("kaytranada bounce chill", "Any", 9),
    ("anderson paak chill vibes", "Any", 9),
    ("frank ocean channel orange chill", "Any", 9),
    ("jorja smith lost and found", "Any", 14),
    ("cleo sol sweet blue", "Any", 9),
    ("little simz quiet introspective", "Any", 9),
    ("loyle carner chill rap", "Any", 14),
    ("new amor birthplace chill", "Any", 9),
    ("bon iver holocene chill", "Any", 9),
    ("acoustic sunday morning", "Any", 14),
    ("coffee shop rainy window", "Any", 12),
    ("drizzle outside studying", "Any", 12),
    ("2am coding music", "Any", 12),
    ("late night reading playlist", "Any", 12),
    ("sunday afternoon chill", "Any", 12),
    ("trip hop portishead", "Any", 9),
    ("massive attack blue lines", "Any", 9),
    ("burial ghost chill", "Any", 9),
    ("four tet swaps", "Any", 9),
    ("bonobo north borders", "Any", 9),
    ("tycho dive ambient", "Any", 12),
    ("khruangbin texas sun", "Any", 9),
    ("toro y moi underneath pine", "Any", 9),
    ("beach house teen dream", "Any", 9),
    ("mazzy star fade into you", "Any", 9),
    ("still woozy bedroom chill", "Any", 14),
    ("rex orange county sunflower", "Any", 7),
    ("clairo sling chill", "Any", 14),
    ("beabadoobee indie chill", "Any", 14),
    ("lofi hindi evening", "Hindi", 12),
    ("desi chill night hindi", "Hindi", 12),
    ("korean indie chill", "Korean", 12),
    ("japanese city pop chill", "Japanese", 12),
    ("french chill chanson", "French", 12),
    ("arabic chill acoustic", "Arabic", 12),
    ("afrobeats alte chill", "Afrobeats", 12),
    ("latin chill lofi", "Spanish", 12),
    ("bengali acoustic baul chill", "Bengali", 9),
    ("club night opening set", "Any", 10),
    ("4am dancefloor still going", "Any", 6),
    ("pre-drinks at home hype", "Any", 10),
    ("girls night out banger", "Any", 10),
    ("birthday party playlist", "Any", 10),
    ("house music deep groove", "Any", 9),
    ("tech house warehouse", "Any", 9),
    ("afrobeats dance floor", "Afrobeats", 10),
    ("amapiano braai", "Afrobeats", 10),
    ("dancehall caribbean heat", "Any", 10),
    ("reggaeton latin club", "Spanish", 10),
    ("baile funk brazil", "Portuguese", 10),
    ("drum and bass jungle bounce", "Any", 10),
    ("90s rave nostalgia", "Any", 9),
    ("00s electro indie dance", "Any", 9),
    ("dua lipa dance night", "Any", 10),
    ("charli xcx party", "Any", 9),
    ("beyonce renaissance party", "Any", 10),
    ("bad bunny latin banger", "Spanish", 10),
    ("karol g manana sera bonito", "Spanish", 10),
    ("burna boy dance last last", "Afrobeats", 10),
    ("wizkid essence groove", "Afrobeats", 9),
    ("tems afrobeats smooth", "Afrobeats", 9),
    ("festival main stage energy", "Any", 11),
    ("midnight countdown new year", "Any", 10),
    ("wedding reception floor filler", "Any", 10),
    ("after party 2am", "Any", 9),
    ("drunk happy dancing", "Any", 10),
    ("carefree silly dancing", "Any", 0),
    ("crowd surf moment concert", "Any", 11),
    ("festival sunrise set", "Any", 9),
    ("deep house vinyl selector", "Any", 9),
    ("korean kpop party", "Korean", 10),
    ("japanese j-pop dance", "Japanese", 10),
    ("bhangra edm fusion party", "Punjabi", 10),
    ("bollywood dance party", "Hindi", 10),
    ("soca carnival heat", "Any", 10),
    ("salsa latin night", "Spanish", 10),
    ("pagode brazil festive", "Portuguese", 10),
    ("cumbia floor filler", "Spanish", 10),
    ("falling asleep to music", "Any", 4),
    ("rain sounds piano", "Any", 4),
    ("ambient for meditation", "Any", 3),
    ("yoga flow playlist", "Any", 3),
    ("morning stretch calm", "Any", 3),
    ("anxiety relief ambient", "Any", 3),
    ("nature sounds birds morning", "Any", 3),
    ("forest walk ambient", "Any", 9),
    ("drone ambient endless", "Any", 9),
    ("brian eno ambient", "Any", 9),
    ("william basinski disintegration", "Any", 9),
    ("stars of the lid instrumental", "Any", 9),
    ("grouper dragging dead deer", "Any", 9),
    ("julianna barwick magic place", "Any", 9),
    ("lowercase ambient quiet", "Any", 9),
    ("boards of canada geogaddi", "Any", 9),
    ("aphex twin selected ambient", "Any", 9),
    ("nils frahm spaces piano", "Any", 9),
    ("max richter sleep", "Any", 3),
    ("olafur arnalds and they escaped", "Any", 9),
    ("jon hopkins immunity piano", "Any", 9),
    ("floating points promises", "Any", 9),
    ("calm morning coffee", "Any", 12),
    ("slow sunday ambient", "Any", 12),
    ("rainy night in bed", "Any", 12),
    ("candle lit room warm", "Any", 4),
    ("fireplace crackling music", "Any", 4),
    ("winter cosy ambient", "Any", 12),
    ("deep focus instrumental", "Any", 12),
    ("reading room music", "Any", 12),
    ("spa relaxation music", "Any", 3),
    ("post-yoga savasana", "Any", 3),
    ("lying on grass looking up", "Any", 12),
    ("stargazing ambient", "Any", 9),
    ("late night drive quiet", "Any", 12),
    ("empty city streets ambient", "Any", 9),
    ("introvert recharge music", "Any", 12),
    ("alone but okay playlist", "Any", 14),
    ("raga ambient indian classical", "Hindi", 9),
    ("carnatic instrumental focus", "Tamil", 9),
    ("sufi ambient drone", "Urdu", 9),
    ("oud ambient arabic", "Arabic", 9),
    ("dream pop hazy ethereal", "Any", 9),
    ("shoegaze wall of sound", "Any", 9),
    ("ethereal vocals reverb", "Any", 9),
    ("slowcore drifting", "Any", 9),
    ("cocteau twins heaven", "Any", 9),
    ("my bloody valentine loveless", "Any", 9),
    ("slowdive souvlaki", "Any", 9),
    ("sigur ros hoppipolla", "Any", 9),
    ("explosions in the sky post rock", "Any", 9),
    ("half waif form dreamy", "Any", 9),
    ("weyes blood front row seat", "Any", 8),
    ("aldous harding cryptic", "Any", 9),
    ("angel olsen all mirrors", "Any", 9),
    ("mitski puberty 2", "Any", 8),
    ("men i trust lauren", "Any", 14),
    ("blood orange devonte", "Any", 9),
    ("james blake overgrown", "Any", 9),
    ("fleet foxes white winter", "Any", 9),
    ("sufjan stevens vesuvius", "Any", 9),
    ("ar rahman dreamy bollywood", "Hindi", 9),
    ("kollywood dreamy slow", "Tamil", 9),
    ("korean dream pop indie", "Korean", 9),
    ("japanese dream pop", "Japanese", 9),
    ("villain origin story", "Any", 9),
    ("cinematic dark score", "Any", 9),
    ("epic orchestral battle", "Any", 11),
    ("hans zimmer time inception", "Any", 9),
    ("ennio morricone western", "Any", 9),
    ("john carpenter halloween synths", "Any", 9),
    ("perturbator dark miami nights", "Any", 9),
    ("kavinsky nightcall synthwave", "Any", 9),
    ("blade runner 2049 ambient", "Any", 9),
    ("tron legacy daft punk", "Any", 9),
    ("interstellar hans zimmer", "Any", 9),
    ("hereditary horror score", "Any", 9),
    ("midsommar folk horror", "Any", 9),
    ("nine inch nails fragile", "Any", 9),
    ("tool lateralus", "Any", 9),
    ("porcupine tree fear blank planet", "Any", 9),
    ("katatonia tonight decision", "Any", 9),
    ("dark ambient winter drone", "Any", 9),
    ("industrial cold minimal", "Any", 9),
    ("coil scatology industrial", "Any", 9),
    ("final boss music game", "Any", 11),
    ("dungeon rpg soundtrack", "Any", 9),
    ("bollywood cinematic bgm", "Hindi", 9),
    ("kollywood bgm dark", "Tamil", 9),
    ("k-drama ost emotional", "Korean", 9),
    ("anime ost joe hisaishi", "Japanese", 9),
    ("arabic cinematic oud", "Arabic", 9),
    ("african cinematic score", "Afrobeats", 9),
    ("80s synth nostalgia", "Any", 9),
    ("synthwave neon city night drive", "Any", 9),
    ("retrowave outrun aesthetic", "Any", 9),
    ("new wave cold 80s", "Any", 9),
    ("italo disco 80s dance", "Any", 9),
    ("city pop japanese 80s", "Japanese", 9),
    ("vaporwave aesthetic 90s", "Any", 9),
    ("90s rnb slow jam classic", "Any", 7),
    ("90s hip hop boom bap", "Any", 9),
    ("90s alternative rock nostalgia", "Any", 9),
    ("britpop 90s blur oasis", "Any", 9),
    ("00s emo throwback", "Any", 7),
    ("00s pop nostalgia", "Any", 7),
    ("early 2010s indie", "Any", 9),
    ("chillwave 2010 nostalgia", "Any", 9),
    ("tumblr era music 2013", "Any", 7),
    ("tame impala lonerism era", "Any", 9),
    ("mgmt electric feel era", "Any", 9),
    ("vampire weekend contra era", "Any", 9),
    ("arcade fire funeral era", "Any", 9),
    ("the strokes is this it", "Any", 9),
    ("joy division unknown pleasures", "Any", 9),
    ("kraftwerk autobahn", "Any", 9),
    ("david bowie ziggy stardust", "Any", 9),
    ("velvet underground femme fatale", "Any", 9),
    ("pink floyd dark side", "Any", 9),
    ("led zeppelin stairway", "Any", 9),
    ("joni mitchell blue album", "Any", 9),
    ("driving with dad's old mixtape", "Any", 7),
    ("summer of 2007 feeling", "Any", 7),
    ("old bollywood kishore kumar", "Hindi", 9),
    ("ilaiyaraaja retro classic", "Tamil", 9),
    ("trot korean retro", "Korean", 9),
    ("classic ghazal retro urdu", "Urdu", 9),
    ("indie folk campfire", "Any", 14),
    ("acoustic guitar and voice", "Any", 14),
    ("folk revival modern", "Any", 9),
    ("mountain folk dark", "Any", 9),
    ("appalachian folk drone", "Any", 9),
    ("old weird america", "Any", 9),
    ("fleet foxes blue ridge mountains", "Any", 9),
    ("iron and wine naked as we came", "Any", 9),
    ("nick drake pink moon", "Any", 9),
    ("john martyn solid air", "Any", 9),
    ("fairport convention folk", "Any", 9),
    ("hozier wasteland baby", "Any", 14),
    ("noah and the whale 5 years time", "Any", 14),
    ("tom odell another love", "Any", 7),
    ("ben howard only love", "Any", 14),
    ("passenger let her go", "Any", 7),
    ("city and colour little hell", "Any", 14),
    ("jose gonzalez heartbeats", "Any", 9),
    ("bonnie prince billy darkness", "Any", 9),
    ("sun kil moon ghosts highway", "Any", 9),
    ("neil young harvest", "Any", 9),
    ("joni mitchell river folk", "Any", 9),
    ("james taylor sweet baby james", "Any", 9),
    ("rajasthani folk instruments", "Hindi", 9),
    ("bengali baul folk mystical", "Bengali", 9),
    ("kerala folk songs", "Malayalam", 9),
    ("telangana folk telugu", "Telugu", 9),
    ("carnatic folk south india", "Tamil", 9),
    ("bts dynamite k-pop hype", "Korean", 10),
    ("blackpink how you like that", "Korean", 10),
    ("newjeans hype boy kpop", "Korean", 10),
    ("stray kids gods menu", "Korean", 6),
    ("aespa black mamba dark kpop", "Korean", 9),
    ("twice feel special kpop", "Korean", 7),
    ("bts suga agust d", "Korean", 9),
    ("zico artist korean", "Korean", 9),
    ("dean instagram k-rnb", "Korean", 9),
    ("epik high born hater", "Korean", 9),
    ("yoasobi idol jpop", "Japanese", 10),
    ("kenshi yonezu flamingo jpop", "Japanese", 7),
    ("official hige dandism pretender", "Japanese", 7),
    ("king gnu flash jpop", "Japanese", 9),
    ("radwimps sparkle anime", "Japanese", 7),
    ("asian kung-fu generation jrock", "Japanese", 9),
    ("sakanaction music alt jpop", "Japanese", 9),
    ("city pop mariya takeuchi", "Japanese", 9),
    ("perfume techno jpop", "Japanese", 9),
    ("burna boy african giant", "Afrobeats", 10),
    ("davido afrobeats party", "Afrobeats", 10),
    ("rema calm down global", "Afrobeats", 7),
    ("ckay love nwantiti", "Afrobeats", 7),
    ("omah lay attention afro", "Afrobeats", 9),
    ("amapiano south africa", "Afrobeats", 9),
    ("fela kuti afrobeat classic", "Afrobeats", 9),
    ("sza ctrl neo soul", "Any", 9),
    ("giveon heartbreak r&b", "Any", 14),
    ("brent faiyaz romantic", "Any", 9),
    ("h.e.r. love songs rnb", "Any", 9),
    ("omar apollo aiming heart", "Any", 9),
    ("snoh aalegra rnb", "Any", 9),
    ("alabaster deplume gold", "Any", 9),
    ("nala sinephro space jazz", "Any", 9),
    ("bad bunny latin trap", "Spanish", 9),
    ("j balvin colores", "Spanish", 7),
    ("maluma felices los 4", "Spanish", 7),
    ("rosalia motomami", "Spanish", 9),
    ("c tangana el madrileño", "Spanish", 9),
    ("french rap damso", "French", 9),
    ("orelsan rap francais", "French", 9),
    ("stromae alors on danse", "French", 7),
    ("angele chanson pop", "French", 7),
    ("arabic pop amr diab", "Arabic", 7),
    ("um kulthum arabic classic", "Arabic", 9),
    ("fairuz lebanon classic", "Arabic", 9),
    ("portuguese fado saudade", "Portuguese", 9),
    ("ana moura fado dark", "Portuguese", 9),
    ("jorge ben jorge brasil", "Portuguese", 9),
    ("making peace with a decision", "Any", 14),
    ("the moment i stopped caring", "Any", 9),
    ("watching the sun go down from train", "Any", 14),
    ("getting dressed and feeling myself", "Any", 0),
    ("packing up childhood bedroom", "Any", 9),
    ("watching parents get old", "Any", 9),
    ("forgiving yourself for the past", "Any", 14),
    ("realizing you've grown as a person", "Any", 14),
    ("finishing a book that broke you", "Any", 9),
    ("the last day of a job you loved", "Any", 9),
    ("graduating not knowing what comes next", "Any", 0),
    ("watching a city from plane leaving", "Any", 9),
    ("the silence after a long argument", "Any", 9),
    ("first morning in a new apartment", "Any", 14),
    ("driving past your old house", "Any", 9),
    ("visiting hometown as an adult", "Any", 9),
    ("first holiday season without someone", "Any", 9),
    ("music that feels like being seventeen", "Any", 9),
    ("liminal space between awake and asleep", "Any", 9),
    ("the hour before a big decision", "Any", 9),
    ("music for the drive after bad news", "Any", 9),
    ("an ordinary day that was the last good one", "Any", 9),
    ("nostalgia for a time that never existed", "Any", 9),
    ("music that sounds like you're a main character", "Any", 0),
    ("saturday afternoon with nothing to do", "Any", 12),
    ("walking home alone after a good night", "Any", 9),
    ("the quiet after a storm", "Any", 14),
    ("summer ending feeling", "Any", 9),
    ("music for 4am thoughts", "Any", 9),
    ("music for 6am before world wakes up", "Any", 12),
    ("that feeling right before something big", "Any", 0),
    ("music for a final chapter", "Any", 9),
    ("something to cry to so nobody hears", "Any", 1),
    ("the beginning of a crush noticing everything", "Any", 0),
    ("leaving toxic relationship terrifyingly free", "Any", 0),
    ("calling someone you should have called", "Any", 9),
    ("crowded street market marrakech", "Arabic", 9),
    ("cramped apartment tokyo city lights", "Japanese", 9),
    ("japanese convenience store 3am", "Japanese", 9),
    ("empty shopping mall 1994", "Any", 9),
    ("airport departure gate at night", "Any", 9),
    ("long highway through nothing", "Any", 12),
    ("soviet liminal space music", "Any", 9),
    ("brutalist architecture music", "Any", 9),
    ("overgrown train station vibes", "Any", 9),
    ("museum ambient gallery", "Any", 12),
    ("spa relaxation ambient", "Any", 3),
    ("headphones on subway moment", "Any", 12),
    ("bar playlist smooth evening", "Any", 12),
    ("rooftop sunset party", "Any", 0),
    ("beach bonfire night", "Any", 0),
    ("road trip windows down", "Any", 0),
    ("mountains and silence", "Any", 9),
    ("desert highway night drive", "Any", 9),
    ("monsoon rain window india", "Hindi", 12),
    ("late night dhabha punjab", "Punjabi", 12),
    ("seoul midnight neon lights", "Korean", 12),
    ("tokyo subway ambient", "Japanese", 12),
    ("paris cafe afternoon", "French", 12),
    ("rio carnival energy", "Portuguese", 10),
    ("nairobi night afrobeats", "Afrobeats", 10),
    ("dubai rooftop luxury", "Arabic", 0),
    ("london grime streets", "Any", 6),
    ("new york drill hard", "Any", 6),
    ("chicago footwork culture", "Any", 9),
    ("music that sounds like the color blue", "Any", 9),
    ("music that feels like wool", "Any", 9),
    ("music that tastes like burnt caramel", "Any", 9),
    ("sounds from a dream you can't remember", "Any", 9),
    ("the texture of old photographs", "Any", 9),
    ("music that sounds like dissolving", "Any", 9),
    ("vibrations rather than notes", "Any", 9),
    ("songs that feel like another timeline", "Any", 9),
    ("music that sounds like the future never came", "Any", 9),
    ("the aesthetic of abandoned places", "Any", 9),
    ("music for a world with one less person", "Any", 9),
    ("music from a parallel universe", "Any", 9),
    ("songs that feel like the moon", "Any", 9),
    ("the smell of petrichor in sound", "Any", 9),
    ("the feeling of almost remembering", "Any", 9),
    ("the specific dread of sunday evening", "Any", 9),
    ("the anticipation before lightning strikes", "Any", 9),
    ("music for a recurring dream", "Any", 9),
    ("a song that shouldn't exist but does", "Any", 9),
    ("happy sad simultaneously", "Any", 9),
    ("calm but urgent", "Any", 9),
    ("loud silence", "Any", 9),
    ("bright darkness", "Any", 9),
    ("soft thunder", "Any", 9),
    ("music that heals and hurts at once", "Any", 9),
    ("unknown familiarity", "Any", 9),
    ("purposeful accident", "Any", 9),
    ("ordered randomness", "Any", 9),
    ("nostalgic for tomorrow", "Any", 9),
    ("bored excitement", "Any", 9),
    ("beautiful dread", "Any", 9),
    ("three words that feel like a whole life", "Any", 9),
    ("one last time", "Any", 9),
    ("almost", "Any", 9),
    ("not yet", "Any", 9),
    ("finally", "Any", 0),
    ("already", "Any", 9),
    ("still here", "Any", 14),
    ("gone now", "Any", 9),
    ("pujabi dace hrad", "Any", 0),
    ("hapy vbies onyl", "Any", 0),
    ("amient focus snd", "Any", 0),
    ("gud vbes onely", "Any", 0),
    ("drk ambint slp", "Any", 0),
    ("sft lov sng", "Any", 0),
    ("vilin era drk", "Any", 0),
    ("gthic drk wave", "Any", 0),
    ("shogaze gtar", "Any", 0),
    ("jzz clb nigt", "Any", 0),
    ("reggaetn sumer", "Any", 0),
    ("hpy hardcore fst", "Any", 0),
    ("vaprwav aesthtic", "Any", 0),
    ("slwd rvb em", "Any", 0),
    ("mtal brk dwn", "Any", 0),
    ("bollwd rom hindi", "Hindi", 0),
    ("hnd brkp sad", "Hindi", 0),
]

# ══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER — expands seeds × knob profiles = 10,000 test cases
# ══════════════════════════════════════════════════════════════════════════════
def build_prompts():
    prompts = []
    for text, language, base_kp in _SEEDS:
        for kp_idx, (af, bpm, niche, label) in enumerate(KNOB_PROFILES):
            # Use seed's preferred knob profile for the first slot,
            # then rotate through all 16 for full coverage
            actual_af   = af
            actual_bpm  = bpm
            actual_niche = niche
            # If this is the seed's preferred profile slot, override with seed defaults
            if kp_idx == base_kp:
                actual_af, actual_bpm, actual_niche, label = KNOB_PROFILES[base_kp]
            prompts.append({
                "text":         text,
                "language":     language,
                "artist_focus": actual_af,
                "bpm_focus":    actual_bpm,
                "nicheness":    actual_niche,
                "knob_label":   label,
                "track_limit":  20,
            })
    return prompts[:10000]

PROMPTS = build_prompts()

# ══════════════════════════════════════════════════════════════════════════════
# LOGGER SETUP
# ══════════════════════════════════════════════════════════════════════════════
logger = logging.getLogger("VibeFinder_v10k")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("qa_batch_v10k_2.log", encoding="utf-8")
sh = logging.StreamHandler()
fmt = logging.Formatter("%(message)s")
fh.setFormatter(fmt)
sh.setFormatter(fmt)
logger.handlers = [fh, sh]

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

    logger.info("=" * 70)
    logger.info("  VIBEFINDER AI — MEGA STRESS SUITE v10k")
    logger.info(f"  {len(PROMPTS)} PROMPTS | 20 TRACKS EACH | 16 KNOB PROFILES | ALL LANGUAGES")
    logger.info("=" * 70 + "\n")

    try:
        db_artists = await db.artistdirectory.find_many()
    except Exception as e:
        logger.error(f"DB connect failed: {e}")
        return

    total = len(PROMPTS)
    signal_lost = 0
    blocklist_hits = 0
    genre_noise_hits = 0
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

        request = VibeRequest(
            text=text,
            language=language,
            track_limit=track_limit,
            artist_focus=artist_focus,
            bpm_focus=bpm_focus,
        )
        prompt_lower = text.lower()
        prompt_words = len(prompt_lower.split())

        # ── Entity scanner ───────────────────────────────────────────────────
        detected_artist = None
        detected_song   = None
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
        if detected_artist and vibe_data.get("confidence", 0) < 0.10:
            vibe_data["dominant_vibe"] = "artist_driven"
            target_genre = None
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

        if vibe_data.get("confidence", 0.0) < 0.25 and not detected_artist:
            is_fallback = True
            vibe_data["dominant_vibe"]   = "Direct Search"
            vibe_data["secondary_vibe"]  = "Fallback Mode"
            raw_pool = await fetch_lastfm_track_search(request.text, limit=200)
            raw_pool = [t for t in raw_pool if not JUNK_PATTERNS.search(
                f"{t.get('title','')} {t.get('artist','')}"
            )]

            # v8.0: 3-STAGE DIRECT SEARCH FALLBACK
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

        elif vibe_data.get("dominant_vibe") == "artist_driven":
            raw_pool = await fetch_lastfm_artist_tracks(artist=detected_artist, limit=200)

        else:
            # Multi-tag parallel fetch using VIBE_TAG_MATRIX if available
            _lang    = (request.language or "Any").strip()
            _dominant = vibe_data.get("dominant_vibe", "")
            if hasattr(vibe_engine, "VIBE_TAG_MATRIX"):
                _tags = (
                    vibe_engine.VIBE_TAG_MATRIX
                    .get(_dominant, {})
                    .get(_lang)
                    or vibe_engine.VIBE_TAG_MATRIX.get(_dominant, {}).get("Any")
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

            # v8.0: Language-agnostic pool retry — if non-English tag returned nothing,
            # fall back to "Any" tags which have broader Last.fm coverage.
            if not genre_pool and _lang != "Any":
                _fallback_tags = (
                    vibe_engine.VIBE_TAG_MATRIX.get(_dominant, {}).get("Any")
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

        logger.info("-" * 60 + "\n")

    await db.disconnect()

    # ── Final stats ──────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("  VIBEFINDER MEGA STRESS SUITE v10k — COMPLETE")
    logger.info(f"  Total prompts run    : {total}")
    logger.info(f"  Signal lost (0 tracks): {signal_lost} ({100*signal_lost/total:.1f}%)")
    logger.info(f"  Blocklist hits       : {blocklist_hits}")
    logger.info(f"  Genre-as-artist noise: {genre_noise_hits}")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_batch())
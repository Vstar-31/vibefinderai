"""
seed_artists.py
───────────────
VibeFinderAI — Artist Directory Seeder

Seeds essential artists into ArtistDirectory across all genres.
Run once after your first `prisma migrate deploy`.

NEW: Run `python seed_artists.py --scrape` to massively expand the 
database by pulling thousands of top artists dynamically from Last.fm!

After seeding, run enrich_artists.py to populate MBID, LB similar artists,
and TheAudioDB metadata for each entry.
"""

import asyncio
import os
import argparse
import httpx
import urllib.parse
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()

async def seed(db: Prisma):
    artists = [
        # ─── POP & MAINSTREAM ────────────────────────────────────────────────
        {"name": "Taylor Swift",      "genres": "pop, country",      "niche": "storytelling",        "songs": "Anti-Hero, Shake It Off, Love Story, Blank Space, Cruel Summer"},
        {"name": "Ariana Grande",     "genres": "pop, r&b",          "niche": "vocalist",            "songs": "thank u next, 7 rings, positions, God is a woman"},
        {"name": "Dua Lipa",          "genres": "pop, disco",        "niche": "dance pop",           "songs": "Levitating, Don't Start Now, New Rules, Physical"},
        {"name": "Harry Styles",      "genres": "pop, soft rock",    "niche": "heartthrob",          "songs": "As It Was, Watermelon Sugar, Adore You"},
        {"name": "Olivia Rodrigo",    "genres": "pop, pop punk",     "niche": "teen angst",          "songs": "drivers license, good 4 u, vampire, brutal"},
        {"name": "Doja Cat",          "genres": "pop, hip hop",      "niche": "versatile",           "songs": "Say So, Kiss Me More, Need to Know, Woman"},
        {"name": "Rihanna",           "genres": "pop, r&b",          "niche": "bad gal",             "songs": "Umbrella, We Found Love, Diamonds, Stay"},
        {"name": "Beyoncé",           "genres": "r&b, pop",          "niche": "queen bey",           "songs": "Crazy in Love, Halo, Lemonade, Renaissance, Texas Hold 'Em"},
        {"name": "Charli XCX",        "genres": "pop, hyperpop",     "niche": "brat",                "songs": "360, Boom Clap, Break The Rules, Speed Drive"},
        {"name": "Chappell Roan",     "genres": "pop, synth-pop",    "niche": "midwest princess",    "songs": "Good Luck Babe!, Pink Pony Club, Casual"},
        {"name": "Sabrina Carpenter", "genres": "pop, r&b",          "niche": "espresso",            "songs": "Espresso, Please Please Please, Skin, Feather"},
        {"name": "Troye Sivan",       "genres": "pop, synth-pop",    "niche": "club pop",            "songs": "Rush, Got Me Started, Youth, WILD"},
        {"name": "Lorde",             "genres": "pop, alternative",  "niche": "melodrama",           "songs": "Royals, Green Light, Ribs, Solar Power"},
        {"name": "Miley Cyrus",       "genres": "pop, rock",         "niche": "chameleon",           "songs": "Flowers, Wrecking Ball, Party in the U.S.A., Midnight Sky"},
        {"name": "Katy Perry",        "genres": "pop, dance pop",    "niche": "candy pop",           "songs": "Roar, Firework, Teenage Dream, Dark Horse"},
        {"name": "Lady Gaga",         "genres": "pop, dance pop",    "niche": "art pop",             "songs": "Bad Romance, Shallow, Poker Face, Alejandro"},
        {"name": "Adele",             "genres": "pop, soul",         "niche": "power ballad",        "songs": "Hello, Rolling in the Deep, Someone Like You, Easy On Me"},
        {"name": "Ed Sheeran",        "genres": "pop, acoustic",     "niche": "everyman pop",        "songs": "Shape of You, Thinking Out Loud, Perfect, Bad Habits"},
        {"name": "Justin Bieber",     "genres": "pop, r&b",          "niche": "pop idol",            "songs": "Baby, Sorry, Love Yourself, Peaches"},
        {"name": "Shawn Mendes",      "genres": "pop, acoustic",     "niche": "soft pop",            "songs": "Stitches, There's Nothing Holdin' Me Back, Mercy"},
        {"name": "Halsey",            "genres": "pop, alternative",  "niche": "emotional pop",       "songs": "Without Me, Colors, Graveyard, Castle"},
        {"name": "Selena Gomez",      "genres": "pop, dance pop",    "niche": "soft power",          "songs": "Come & Get It, Wolves, Bad Liar, Lose You to Love Me"},
        {"name": "Camila Cabello",    "genres": "pop, latin pop",    "niche": "cuban pop",           "songs": "Havana, Señorita, Never Be the Same"},
        {"name": "Lizzo",             "genres": "pop, r&b",          "niche": "empowerment",         "songs": "Juice, Truth Hurts, About Damn Time"},
        {"name": "Cardi B",           "genres": "hip hop, pop",      "niche": "WAP era",             "songs": "Bodak Yellow, WAP, I Like It"},
        {"name": "Nicki Minaj",       "genres": "hip hop, pop",      "niche": "barbz",               "songs": "Super Bass, Anaconda, Starships, Pink Friday"},
        {"name": "Bruno Mars",        "genres": "pop, r&b",          "niche": "funk pop",            "songs": "Uptown Funk, Grenade, Just the Way You Are, 24K Magic"},
        {"name": "Sam Smith",         "genres": "pop, soul",         "niche": "torch song",          "songs": "Stay With Me, Too Good at Goodbyes, Unholy"},
        {"name": "Ellie Goulding",    "genres": "pop, synth-pop",    "niche": "ethereal pop",        "songs": "Lights, Burn, Love Me Like You Do"},
        {"name": "Sia",               "genres": "pop, dance pop",    "niche": "big voice",           "songs": "Chandelier, Cheap Thrills, Titanium, Elastic Heart"},
        {"name": "P!nk",              "genres": "pop, rock",         "niche": "anthems",             "songs": "So What, Just Give Me a Reason, Try"},
        {"name": "The Chainsmokers",  "genres": "electronic, pop",   "niche": "festival pop",        "songs": "Closer, Don't Let Me Down, Roses"},
        {"name": "Marshmello",        "genres": "electronic, pop",   "niche": "happy rave",          "songs": "Alone, Friends, Happier"},
        {"name": "Kygo",              "genres": "electronic, pop",   "niche": "tropical house",      "songs": "Firestone, Stole the Show, Piano Jam"},
        {"name": "Zedd",              "genres": "electronic, pop",   "niche": "electro house",       "songs": "Clarity, Stay the Night, The Middle"},
        {"name": "Calvin Harris",     "genres": "electronic, dance pop", "niche": "ibiza anthems",   "songs": "This Is What You Came For, Summer, Feel So Close"},

        # ─── K-POP ───────────────────────────────────────────────────────────
        {"name": "BTS",        "genres": "k-pop, pop",         "niche": "army",          "songs": "Dynamite, Butter, Boy With Luv, DNA, Fake Love"},
        {"name": "BLACKPINK",  "genres": "k-pop, pop",         "niche": "girl crush",    "songs": "DDU-DU DDU-DU, Pink Venom, Kill This Love, How You Like That"},
        {"name": "NewJeans",   "genres": "k-pop, r&b",         "niche": "y2k kpop",      "songs": "Hype Boy, Attention, Ditto, OMG"},
        {"name": "Stray Kids", "genres": "k-pop, hip hop",     "niche": "noise pop",     "songs": "MIROH, God's Menu, Thunderous, MANIAC"},
        {"name": "aespa",      "genres": "k-pop, electronic",  "niche": "metaverse pop", "songs": "Black Mamba, Savage, Girls, Spicy"},
        {"name": "TWICE",      "genres": "k-pop, pop",         "niche": "candy pop",     "songs": "Cheer Up, TT, FANCY, Feel Special"},
        {"name": "EXO",        "genres": "k-pop, r&b",         "niche": "power vocals",  "songs": "Love Shot, Growl, Ko Ko Bop, Monster"},
        {"name": "NCT 127",    "genres": "k-pop, hip hop",     "niche": "neo culture",   "songs": "Cherry Bomb, Kick It, Punch"},
        {"name": "SHINee",     "genres": "k-pop, r&b",         "niche": "shinee world",  "songs": "View, Replay, Lucifer, Everybody"},
        {"name": "(G)I-DLE",   "genres": "k-pop, hip hop",     "niche": "self-produced", "songs": "TOMBOY, LATATA, Super Lady"},
        {"name": "IVE",        "genres": "k-pop, pop",         "niche": "concept pop",   "songs": "LOVE DIVE, After LIKE, Kitsch"},
        {"name": "LE SSERAFIM","genres": "k-pop, pop",         "niche": "fearless",      "songs": "FEARLESS, ANTIFRAGILE, Perfect Night"},
        {"name": "ENHYPEN",    "genres": "k-pop, pop",         "niche": "dark k-pop",    "songs": "Given-Taken, Fever, Bite Me"},
        {"name": "TXT",        "genres": "k-pop, alternative", "niche": "chaos pop",     "songs": "Crown, Blue Hour, Sugar Rush Ride"},

        # ─── HIP HOP, RAP & TRAP ─────────────────────────────────────────────
        {"name": "Kendrick Lamar", "genres": "hip hop, rap",    "niche": "conscious",       "songs": "HUMBLE., Not Like Us, DNA., Alright, Money Trees"},
        {"name": "Drake",          "genres": "hip hop, pop rap","niche": "mainstream",      "songs": "God's Plan, One Dance, Hotline Bling, Started From the Bottom"},
        {"name": "Travis Scott",   "genres": "hip hop, trap",   "niche": "rage",            "songs": "goosebumps, SICKO MODE, FE!N, Antidote"},
        {"name": "Kanye West",     "genres": "hip hop, rap",    "niche": "genius",          "songs": "Gold Digger, Stronger, All Falls Down, Ultralight Beam"},
        {"name": "J. Cole",        "genres": "hip hop, rap",    "niche": "lyrical",         "songs": "No Role Modelz, Middle Child, GOMD, Apparently"},
        {"name": "21 Savage",      "genres": "hip hop, trap",   "niche": "atlanta trap",    "songs": "redrum, Rockstar, Bank Account, a lot"},
        {"name": "Post Malone",    "genres": "hip hop, pop",    "niche": "sad boy rap",     "songs": "Circles, Sunflower, rockstar, White Iverson"},
        {"name": "Lil Uzi Vert",   "genres": "hip hop, trap",   "niche": "alt trap",        "songs": "XO Tour Llif3, Just Wanna Rock, The Way Life Goes"},
        {"name": "Tyler the Creator","genres":"hip hop, alternative","niche":"odd future",   "songs": "EARFQUAKE, ARE WE STILL FRIENDS?, See You Again, Lumberjack"},
        {"name": "Frank Ocean",    "genres": "r&b, hip hop",    "niche": "channel orange",  "songs": "Nights, Pink + White, Ivy, Self Control, Blonde"},
        {"name": "Childish Gambino","genres":"hip hop, r&b",    "niche": "this is america", "songs": "Redbone, This Is America, Sober, 3005"},
        {"name": "SZA",            "genres": "r&b, hip hop",    "niche": "ctrl",            "songs": "Good Days, Kill Bill, Shirt, Love Galore"},
        {"name": "The Weeknd",     "genres": "r&b, pop",        "niche": "after hours",     "songs": "Blinding Lights, Save Your Tears, Die For You, Starboy"},
        {"name": "Playboi Carti",  "genres": "hip hop, trap",   "niche": "whole lotta red", "songs": "Magnolia, wokeuplikethis*, Sky, Punk Monk"},
        {"name": "Lil Baby",       "genres": "hip hop, trap",   "niche": "quality control", "songs": "Drip Too Hard, Emotionally Scarred, The Bigger Picture"},
        {"name": "Gunna",          "genres": "hip hop, trap",   "niche": "wunna",           "songs": "Drip or Drown, Pussy Fair, One Call, poochie gown"},
        {"name": "Future",         "genres": "hip hop, trap",   "niche": "dirty sprite",    "songs": "Mask Off, Life Is Good, March Madness, WAIT FOR U"},
        {"name": "Metro Boomin",   "genres": "hip hop, trap",   "niche": "producer",        "songs": "Superhero, Creepin', Don't Let Me Down"},
        {"name": "Rod Wave",       "genres": "hip hop, r&b",    "niche": "soulfly",         "songs": "Heart on Ice, Tombstone, Dark Clouds, Beautiful Scarlett"},
        {"name": "Lil Durk",       "genres": "hip hop, drill",  "niche": "chicago drill",   "songs": "All My Life, The Voice, AHHH HA, Broadway Girls"},
        {"name": "Jack Harlow",    "genres": "hip hop, pop rap","niche": "come home the kids miss you","songs":"First Class, What's Poppin, Industry Baby"},
        {"name": "Coi Leray",      "genres": "hip hop, pop",    "niche": "no more parties", "songs": "No More Parties, Players, Twinnem"},
        {"name": "Flo Milli",      "genres": "hip hop, pop",    "niche": "ho why is you here","songs":"Ho Why Is You Here, Not Friendly, Roaring 20s"},

        # ─── R&B & SOUL ──────────────────────────────────────────────────────
        {"name": "H.E.R.",         "genres": "r&b, soul",      "niche": "focus",           "songs": "Focus, Best Part, Damage, Sometimes"},
        {"name": "Jhené Aiko",     "genres": "r&b, soul",      "niche": "chilombo",        "songs": "Sativa, None of Your Concern, Tryna Smoke, While We're Young"},
        {"name": "Kehlani",        "genres": "r&b, pop",       "niche": "blue water road",  "songs": "Gangsta, honey, Nights Like This, Everything Is Yours"},
        {"name": "Brent Faiyaz",   "genres": "r&b, soul",      "niche": "wasting time",    "songs": "Wasting Time, Gravity, Loose Change, Make It Work"},
        {"name": "Daniel Caesar",  "genres": "r&b, soul",      "niche": "freudian",        "songs": "Best Part, Get You, Japanese Denim, Entropy"},
        {"name": "Giveon",         "genres": "r&b, soul",      "niche": "give or take",    "songs": "Heartbreak Anniversary, Stuck on You, For Tonight"},
        {"name": "Lucky Daye",     "genres": "r&b, soul",      "niche": "candydrip",       "songs": "Over, Roll Some Mo, Candy Drip"},
        {"name": "Summer Walker",  "genres": "r&b, soul",      "niche": "over it",         "songs": "Girls Need Love, Come Thru, Playing Games"},
        {"name": "Snoh Aalegra",   "genres": "r&b, soul",      "niche": "ugh those feels", "songs": "Situationship, I Want You Around, Do 4 Love"},
        {"name": "Cleo Sol",       "genres": "r&b, soul",      "niche": "mother",          "songs": "Sweet Blue, Golden Child, When I'm in Your Arms"},
        {"name": "Tom Misch",      "genres": "r&b, jazz",      "niche": "geography",       "songs": "Geography, Lost in Paris, It Runs Through Me"},

        # ─── BOLLYWOOD & HINDI ───────────────────────────────────────────────
        {"name": "Arijit Singh",        "genres": "bollywood, hindi",     "niche": "romantic bollywood",   "songs": "Tum Hi Ho, Channa Mereya, Ae Dil Hai Mushkil, Kesariya"},
        {"name": "Shreya Ghoshal",      "genres": "bollywood, hindi",     "niche": "classical crossover",  "songs": "Teri Meri, Barso Re, Sun Raha Hai, Deewani Mastani"},
        {"name": "Sonu Nigam",          "genres": "bollywood, hindi",     "niche": "golden voice",          "songs": "Kal Ho Naa Ho, Main Hoon Na, Abhi Mujh Mein Kahin"},
        {"name": "Kishore Kumar",       "genres": "bollywood, hindi",     "niche": "classic legend",        "songs": "Ek Ladki Ko Dekha, Roop Tera Mastana, Mere Mehboob Qayamat Hogi"},
        {"name": "Lata Mangeshkar",     "genres": "bollywood, hindi",     "niche": "nightingale of india",  "songs": "Lag Ja Gale, Ajeeb Dastan Hai Yeh, Tere Bina Zindagi Se"},
        {"name": "A.R. Rahman",         "genres": "bollywood, world",     "niche": "oscar winner",          "songs": "Jai Ho, Roja, Dil Se, Vande Mataram, Kun Faya Kun"},
        {"name": "Shankar Ehsaan Loy",  "genres": "bollywood, indie pop", "niche": "dil chahta hai era",    "songs": "Dil Chahta Hai, Kabhi Alvida Naa Kehna, Rock On"},
        {"name": "Vishal-Shekhar",      "genres": "bollywood, pop",       "niche": "yash raj sound",        "songs": "Beintehaa, Badtameez Dil, Dhoom Machale"},
        {"name": "Amit Trivedi",        "genres": "bollywood, indie",     "niche": "experimental bollywood","songs": "Emotional Atyachaar, Ik Bagal, Manmarziyaan"},
        {"name": "Pritam",              "genres": "bollywood, pop",       "niche": "yrf blockbuster",       "songs": "Tum Se Hi, Zoobi Doobi, Agar Tum Saath Ho"},
        {"name": "Armaan Malik",        "genres": "bollywood, pop",       "niche": "young voice",           "songs": "Main Rahoon Ya Na Rahoon, Bol Do Na Zara, Sab Teri Wajah Se"},
        {"name": "B Praak",             "genres": "bollywood, hindi",     "niche": "heartbreak hindi",      "songs": "Filhall, Mann Bharrya, Dil Todne Ka Shauq Tha"},
        {"name": "Jubin Nautiyal",      "genres": "bollywood, hindi",     "niche": "soft romantic",         "songs": "Lut Gaye, Raataan Lambiyan, Tum Hi Aana"},

        # ─── PUNJABI ─────────────────────────────────────────────────────────
        {"name": "AP Dhillon",          "genres": "punjabi, pop",         "niche": "global punjabi",        "songs": "Brown Munde, Excuses, With You, Insane"},
        {"name": "Diljit Dosanjh",      "genres": "punjabi, bhangra",     "niche": "king of punjabi pop",   "songs": "Do You Know, Lover, Patiala Peg, GOAT"},
        {"name": "Sidhu Moosewala",     "genres": "punjabi, hip hop",     "niche": "moosetape",             "songs": "So High, 295, Bambiha Bole, The Last Ride"},
        {"name": "Guru Randhawa",       "genres": "punjabi, pop",         "niche": "made in india",         "songs": "Lahore, Made in India, High Rated Gabru"},
        {"name": "Badshah",             "genres": "punjabi, hip hop",     "niche": "desi rap mainstream",   "songs": "Paagal, Mercy, DJ Waley Babu, Tareefan"},
        {"name": "Yo Yo Honey Singh",   "genres": "punjabi, hip hop",     "niche": "blue eyes era",         "songs": "Blue Eyes, Angreji Beat, Brown Rang, Desi Kalakaar"},
        {"name": "Harrdy Sandhu",       "genres": "punjabi, pop",         "niche": "bijlee",                "songs": "Bijlee Bijlee, Joker, Naah, After Party"},
        {"name": "Prabh Deep",          "genres": "punjabi, hip hop",     "niche": "conscious punjabi",     "songs": "Class-Sick, Suno, Taana Baana, Choliyaan"},
        {"name": "Karan Aujla",         "genres": "punjabi, hip hop",     "niche": "btw era",               "songs": "BTW, Jatt Life, Hint, 4 You"},
        {"name": "Ammy Virk",           "genres": "punjabi, pop",         "niche": "romantic punjabi",      "songs": "Qismat, Duniya, Tenu Yaad Karan"},
        {"name": "Panjabi MC",          "genres": "punjabi, bhangra",     "niche": "mundian to bach ke",    "songs": "Mundian to Bach Ke, Jogi, Morni"},
        {"name": "Malkit Singh",        "genres": "punjabi, bhangra",     "niche": "golden star",           "songs": "Gur Nalon Ishq Mitha, Balle Ni Balle, Jind Mahi"},

        # ─── SOUTH INDIAN ────────────────────────────────────────────────────
        {"name": "Anirudh Ravichander", "genres": "kollywood, tamil",     "niche": "mass bgm",              "songs": "Why This Kolaveri Di, Kannaana Kanney, Arabic Kuthu"},
        {"name": "S.P. Balasubrahmanyam","genres": "indian classical, tollywood", "niche": "sp balu legend","songs": "Ilayaraja hits, Naa Nuvve, Oruvan Oruvan"},
        {"name": "Sid Sriram",          "genres": "carnatic, r&b",        "niche": "devotional crossover",  "songs": "Kannaana Kanney, Uyire, Idhazhin Oram, Nee Hilave"},
        {"name": "Yuvan Shankar Raja",  "genres": "kollywood, tamil",     "niche": "mass romantic",         "songs": "Nenjukulle, Hey Nenje, Hosanna"},
        {"name": "DSP (Devi Sri Prasad)","genres": "tollywood, telugu",   "niche": "tollywood mass",        "songs": "Saami Saami, Butta Bomma, Naatu Naatu"},
        {"name": "Thaman S",            "genres": "tollywood, telugu",    "niche": "power star bgm",        "songs": "Glimpse of God, Pogaru, Vijay Antony hits"},

        # ─── SUFI & GHAZAL ───────────────────────────────────────────────────
        {"name": "Nusrat Fateh Ali Khan","genres": "sufi, qawwali",       "niche": "divine qawwali",        "songs": "Allah Hoo, Afreen Afreen, Mustt Mustt, Tumhe Dillagi"},
        {"name": "Rahat Fateh Ali Khan", "genres": "sufi, bollywood",     "niche": "modern sufi",           "songs": "O Re Piya, Surili Akhiyon Wale, Zaroori Tha"},
        {"name": "Abida Parveen",        "genres": "sufi, classical",     "niche": "queen of sufi",         "songs": "Tere Ishq Nachaya, Allah Allah, Mast Nazron Se"},
        {"name": "Mehdi Hassan",         "genres": "ghazal, classical",   "niche": "ghazal king",           "songs": "Ranjish Hi Sahi, Patta Patta Boota Boota, Zindagi Mein"},
        {"name": "Ghulam Ali",           "genres": "ghazal, classical",   "niche": "hunkarawala",           "songs": "Hungama Hai Kyun, Chupke Chupke, Awaz De Kahan"},
        {"name": "Ustad Zakir Hussain",  "genres": "indian classical",    "niche": "tabla maestro",         "songs": "Tabla solo compositions, Shakti collaborations"},

        # ─── INDIE POP / ALTERNATIVE INDIA ───────────────────────────────────
        {"name": "Prateek Kuhad",        "genres": "indie pop, folk",     "niche": "cold mesi heartbreak", "songs": "cold/mess, Kasoor, Oh Love, Tere Hi Rang"},
        {"name": "The Local Train",      "genres": "indie rock, hindi",   "niche": "dilli ki sardi",       "songs": "Aaoge Tum Kabhi, Khud Ko Talaash Kar, Alvida"},
        {"name": "When Chai Met Toast",  "genres": "indie pop, folk",     "niche": "warm indie",           "songs": "Khoj, Firefly, Run"},
        {"name": "Ritviz",               "genres": "indie pop, electronic","niche": "udd gaye era",        "songs": "Udd Gaye, Liggi, Thandi Hawa, Sage"},
        {"name": "Aashta Gill",          "genres": "punjabi, pop",        "niche": "bass dj pop",          "songs": "Bass Meri Jaan, Nasha, Tenu Mera Pyar"},
        {"name": "Seedhe Maut",          "genres": "indian hip hop, boom bap","niche": "delhi underground","songs": "Nanchaku, Pehli Baar, Takht, Cheenti"},
        {"name": "Tejas",                "genres": "indie pop, alternative","niche": "mumbai indie",       "songs": "Tejas hits, Liggi collaborations"},

        # ─── INDIAN HIP HOP / DESI RAP ───────────────────────────────────────
        {"name": "Divine",         "genres": "indian hip hop, desi rap",       "niche": "gully rap pioneer",    "songs": "Mere Gully Mein, Jungli Sher, Farak, Nazar"},
        {"name": "KR$NA",          "genres": "indian hip hop, rap",            "niche": "technical lyricist",   "songs": "Khol De, Dilli, Aafat, Underground Authority"},
        {"name": "MC Stan",        "genres": "indian hip hop, desi drill",     "niche": "pune underground",     "songs": "Wata, Basti Ka Hasti, Tadipaar, Insaan"},
        {"name": "Raftaar",        "genres": "indian hip hop, desi rap",       "niche": "mainstream desi rap",  "songs": "Swag Mera Desi, Mantoiyat, Black, Dum Dum"},
        {"name": "Emiway Bantai",  "genres": "indian hip hop, rap",            "niche": "independent grind",   "songs": "Machayenge, Firse Machayenge, Aur Bantai, Bounce Back"},
        {"name": "Dino James",     "genres": "indian hip hop, rap",            "niche": "emotional rap",        "songs": "Girlfriend, Loser, Move On, Nahi Hoga"},
        {"name": "Bohemia",        "genres": "punjabi hip hop, rap",           "niche": "punjabi rap pioneer",  "songs": "Kali Denali, Ik Tera, Tenu Lod Nahi, Keh Ke Lunga"},
        {"name": "Karma",          "genres": "indian hip hop, mumbai rap",     "niche": "mumbai trap",          "songs": "Shayad, Yaad, Sone De, Laila"},
        {"name": "Brodha V",       "genres": "indian hip hop, conscious rap",  "niche": "bangalore conscious",  "songs": "Aigiri Nandini Hip Hop, Mera Mann, Brahmanda"},
        {"name": "Encore ABJ",     "genres": "indian hip hop, trap",           "niche": "mumbai trap",          "songs": "Chal Maar, Morni, Trap House"},
        {"name": "Ikka",           "genres": "indian hip hop, punjabi rap",    "niche": "haryanvi rap",         "songs": "Meri Maa, Teri Gali, Changa Munda"},
        {"name": "Prabh Deep",     "genres": "indian hip hop, conscious rap",  "niche": "delhi conscious",      "songs": "Class-Sick, Suno, Taana Baana"},

        # ─── ALTERNATIVE / INDIE / ROCK ──────────────────────────────────────
        {"name": "Radiohead",       "genres": "alternative, art rock",     "niche": "ok computer",       "songs": "Creep, Karma Police, No Surprises, Everything in Its Right Place"},
        {"name": "Arctic Monkeys",  "genres": "indie rock, alternative",   "niche": "am era",            "songs": "Do I Wanna Know?, R U Mine?, 505, Fluorescent Adolescent"},
        {"name": "The 1975",        "genres": "indie pop, alternative",    "niche": "being funny in a foreign language","songs": "Somebody Else, The Ballad of Me and My Brain, If You're Too Shy"},
        {"name": "Tame Impala",     "genres": "psychedelic, indie",        "niche": "currents",          "songs": "The Less I Know the Better, Let It Happen, Eventually"},
        {"name": "Billie Eilish",   "genres": "pop, alternative",          "niche": "dont smile at me",  "songs": "bad guy, ocean eyes, Therefore I Am, What Was I Made For"},
        {"name": "Lana Del Rey",    "genres": "indie pop, dream pop",      "niche": "cinematic sadcore", "songs": "Video Games, Summertime Sadness, Young and Beautiful, Norman Fucking Rockwell"},
        {"name": "Phoebe Bridgers", "genres": "indie folk, alternative",   "niche": "punisher",          "songs": "Motion Sickness, Savior Complex, Funeral, Kyoto"},
        {"name": "Hozier",          "genres": "folk, soul",                "niche": "take me to church", "songs": "Take Me to Church, Work Song, Cherry Wine, Almost"},
        {"name": "Bon Iver",        "genres": "indie folk, ambient",       "niche": "for emma",          "songs": "Skinny Love, Holocene, Perth, Towers"},
        {"name": "Sufjan Stevens",  "genres": "indie folk, chamber pop",   "niche": "illinoise",         "songs": "Chicago, Death With Dignity, Mystery of Love, Death Shall Have No Dominion"},
        {"name": "The National",    "genres": "indie rock, art rock",      "niche": "sleep well beast",  "songs": "Bloodbuzz Ohio, Sorrow, I Need My Girl, Fake Empire"},
        {"name": "Fleet Foxes",     "genres": "indie folk, baroque pop",   "niche": "helplessness blues","songs": "White Winter Hymnal, Helplessness Blues, Mykonos"},
        {"name": "Vampire Weekend", "genres": "indie rock, afro-pop",      "niche": "father of the bride","songs":"A-Punk, Oxford Comma, Harmony Hall, Sunflower"},
        {"name": "Mitski",          "genres": "indie rock, art rock",      "niche": "puberty 2",         "songs": "Nobody, Washing Machine Heart, Your Best American Girl, Working for the Knife"},
        {"name": "Soccer Mommy",    "genres": "indie rock, dream pop",     "niche": "color theory",      "songs": "Circle the Drain, Yellow is the Color, Sophie"},
        {"name": "beabadoobee",     "genres": "indie rock, shoegaze",      "niche": "fake it flowers",   "songs": "Care, Last Day on Earth, cologne, Talk"},
        {"name": "Japanese Breakfast","genres":"indie pop, experimental",  "niche": "psychopomp",        "songs": "Basically Happy, Paprika, In Hell, Posing in Bondage"},
        {"name": "boygenius",       "genres": "indie folk, rock",          "niche": "the record",        "songs": "Not Strong Enough, True Blue, Emily I'm Sorry, Savior Complex"},
        {"name": "Turnstile",       "genres": "hardcore, punk",            "niche": "glow on",           "songs": "Mystery, Blackout, Alien Love Call, T.L.C."},
        {"name": "Weyes Blood",     "genres": "art pop, folk",             "niche": "and in the darkness","songs":"Andromeda, Movies, Everyday, A Lot's Gonna Change"},
        {"name": "MUNA",            "genres": "synth-pop, indie",          "niche": "muna self-titled",  "songs": "Silk Chiffon, Kind of Girl, Anything But Me"},

        # ─── ELECTRONIC / AMBIENT ────────────────────────────────────────────
        {"name": "Aphex Twin",       "genres": "electronic, ambient",     "niche": "selected ambient works","songs": "Windowlicker, Come to Daddy, Alberto Balsam"},
        {"name": "Boards of Canada", "genres": "electronic, ambient",     "niche": "music has the right","songs": "Roygbiv, Dayvan Cowboy, Turquoise Hexagon Sun"},
        {"name": "Brian Eno",        "genres": "ambient, art rock",       "niche": "music for airports", "songs": "Music for Airports, By This River, Here Come the Warm Jets"},
        {"name": "Four Tet",         "genres": "electronic, ambient",     "niche": "rounds",             "songs": "Lush, Pyramid, Angel Echoes, Baby"},
        {"name": "Burial",           "genres": "electronic, dubstep",     "niche": "untrue",             "songs": "Archangel, Shell of Light, Near Dark, Rough Sleeper"},
        {"name": "James Blake",      "genres": "electronic, r&b",         "niche": "assume form",        "songs": "Limit to Your Love, Retrograde, The Wilhelm Scream, Are You In Love?"},
        {"name": "Jon Hopkins",      "genres": "electronic, ambient",     "niche": "immunity",           "songs": "Open Eye Signal, Emerald Rush, Singularity, Vessel"},
        {"name": "Floating Points",  "genres": "electronic, jazz",        "niche": "promises",           "songs": "Promises, Silhouettes I II III, Kuiper"},
        {"name": "Nala Sinephro",    "genres": "jazz, ambient",           "niche": "space 1.8",          "songs": "Space 4, Space 7, Space 1.8"},
        {"name": "Moderat",          "genres": "electronic, ambient",     "niche": "iii",                "songs": "Bad Kingdom, Reminder, Eating Hooks"},
        {"name": "Nicolas Jaar",     "genres": "electronic, ambient",     "niche": "space is only noise","songs": "Space Is Only Noise If You Can See, Keep Me There"},
        {"name": "Perturbator",      "genres": "synthwave, electronic",   "niche": "the uncanny valley", "songs": "Future Club, Perturbator's Theme, She Is Young She Is Beautiful"},
        {"name": "Kavinsky",         "genres": "synthwave, electronic",   "niche": "outrun",             "songs": "Nightcall, Protovision, Odd Look"},
        {"name": "Tycho",            "genres": "electronic, ambient",     "niche": "dive",               "songs": "A Walk, Coastal Brake, Awake, Montana"},
        {"name": "Com Truise",       "genres": "synthwave, electronic",   "niche": "galactic melt",      "songs": "Flightwave, Air Cal, Cathode Girls"},

        # ─── JAZZ & SOUL ─────────────────────────────────────────────────────
        {"name": "Kendrick Scott",   "genres": "jazz, soul",       "niche": "american songwriter",  "songs": "Conviction, Boogaloo, Skyline"},
        {"name": "Chet Baker",       "genres": "jazz, cool jazz",  "niche": "almost blue",          "songs": "Almost Blue, My Funny Valentine, Almost Blue"},
        {"name": "Miles Davis",      "genres": "jazz, fusion",     "niche": "kind of blue",         "songs": "So What, Blue in Green, Kind of Blue"},
        {"name": "John Coltrane",    "genres": "jazz, avant-garde","niche": "a love supreme",       "songs": "A Love Supreme, My Favorite Things, Giant Steps"},
        {"name": "Alfa Mist",        "genres": "jazz, hip hop",    "niche": "antiphon",             "songs": "Keep On, Breathe, Visitor"},
        {"name": "Ezra Collective",  "genres": "jazz, afrobeats",  "niche": "you can't steal my joy","songs":"Pure Shade, Quest for Coin, Life Goes On"},
        {"name": "Yussef Kamaal",    "genres": "jazz, electronic", "niche": "black focus",          "songs": "Strings of Light, Joint 17, Guesthouse"},

        # ─── AFROBEATS & AFROPOP ─────────────────────────────────────────────
        {"name": "Burna Boy",        "genres": "afrobeats, afropop", "niche": "twice as tall",    "songs": "Last Last, Ye, On the Low, Way Too Big"},
        {"name": "Wizkid",           "genres": "afrobeats, afropop", "niche": "made in lagos",    "songs": "Essence, Come Closer, Joro, Soco"},
        {"name": "Davido",           "genres": "afrobeats, afropop", "niche": "a better time",    "songs": "Fall, Risky, FEM, Jowo"},
        {"name": "Tems",             "genres": "afrobeats, r&b",     "niche": "if orange was a place","songs":"Free Mind, Essence, Higher, Me & U"},
        {"name": "Rema",             "genres": "afrobeats, afropop", "niche": "calm down",        "songs": "Calm Down, Bounce, Dumebi, Iron Man"},
        {"name": "Ayra Starr",       "genres": "afrobeats, r&b",     "niche": "19 & dangerous",   "songs": "Rush, Fashion Killer, Bloody Samaritan"},
        {"name": "Amapiano (Kabza)", "genres": "amapiano, afrohouse","niche": "king of amapiano",  "songs": "Sponono, Abalele, Umsebenzi Wethu"},
        {"name": "DJ Maphorisa",     "genres": "amapiano, afrohouse","niche": "spider",            "songs": "Izolo, Banyana, Soweto Baby, Izikhothane"},
        {"name": "Fireboy DML",      "genres": "afropop, r&b",       "niche": "laughter, tears and goosebumps","songs":"Peru, Jealous, New York City Girl"},

        # ─── LATIN ───────────────────────────────────────────────────────────
        {"name": "Bad Bunny",        "genres": "latin trap, reggaeton","niche": "un verano sin ti", "songs": "Me Porto Bonito, Tití Me Preguntó, Moscow Mule, Efecto"},
        {"name": "J Balvin",         "genres": "reggaeton, latin pop", "niche": "colores",          "songs": "Mi Gente, Ay Vamos, X, Rojo"},
        {"name": "Rosalía",          "genres": "flamenco, pop",        "niche": "motomami",         "songs": "Malamente, BIZCOCHITO, Saoko, Chicken Teriyaki"},
        {"name": "Karol G",          "genres": "reggaeton, latin pop", "niche": "mañana será bonito","songs":"PROVENZA, Tusa, Ay DiOs Mío!, Mamiii"},
        {"name": "Rauw Alejandro",   "genres": "reggaeton, r&b",       "niche": "trap cake",        "songs": "Todo de Ti, Tattoo, Elegí, Lo Siento BB"},

        # ─── DREAM POP / SHOEGAZE ─────────────────────────────────────────────
        {"name": "Cocteau Twins",    "genres": "dream pop, shoegaze","niche": "heaven or las vegas","songs": "Musette and Drums, Cherry-Coloured Funk, Heaven or Las Vegas"},
        {"name": "Beach House",      "genres": "dream pop",          "niche": "teen dream",         "songs": "Space Song, Myth, Norway, Take Care"},
        {"name": "My Bloody Valentine","genres":"shoegaze, noise rock","niche":"loveless",           "songs": "Only Shallow, When You Sleep, Sometimes, Sometimes"},
        {"name": "Mazzy Star",       "genres": "dream pop, alternative","niche":"fade into you",     "songs": "Fade Into You, Into Dust, Look on Down from the Bridge"},
        {"name": "Cigarettes After Sex","genres":"ambient pop, dream pop","niche":"crush",           "songs": "Apocalypse, Each Time You Fall in Love, Tejano Blue"},
        {"name": "Men I Trust",      "genres": "dream pop, synth-pop","niche": "untourable album",  "songs": "Tailwhip, Show Me How, Organon"},
        {"name": "Dijon",            "genres": "r&b, dream pop",     "niche": "absolutely",         "songs": "Rodeo Clown, Many Times, Scratching"},
        {"name": "Faye Webster",     "genres": "indie pop, dream pop","niche": "i know i'm funny haha","songs":"Kingston, Cheers, Right Side of My Neck"},

        # ─── DARK / GOTH / INDUSTRIAL ────────────────────────────────────────
        {"name": "Nine Inch Nails",  "genres": "industrial, alternative","niche":"the downward spiral","songs":"Closer, Hurt, Head Like a Hole, The Hand That Feeds"},
        {"name": "Depeche Mode",     "genres": "synth-pop, dark wave","niche": "violator",          "songs": "Personal Jesus, Enjoy the Silence, Policy of Truth"},
        {"name": "Joy Division",     "genres": "post-punk, dark wave","niche": "unknown pleasures",  "songs": "Love Will Tear Us Apart, Atmosphere, Disorder"},
        {"name": "London After Midnight","genres":"goth rock, industrial","niche":"selected scenes", "songs":"The Bondage Song, Kiss, Your Best Nightmare"},
        {"name": "SOPHIE",           "genres": "hyperpop, electronic","niche": "oil of every pearl","songs":"HARD, It's Okay to Cry, Ponyboy, Infatuation"},
        {"name": "100 gecs",         "genres": "hyperpop, pop punk",  "niche": "10000 gecs",        "songs": "stupid horse, money machine, hand crushed by a mallet"},

        # ─── COUNTRY & FOLK ──────────────────────────────────────────────────
        {"name": "Morgan Wallen",    "genres": "country, country pop","niche": "one thing at a time","songs":"Last Night, Wasted on You, Sand in My Boots"},
        {"name": "Zach Bryan",       "genres": "country, folk",       "niche": "american heartbreak","songs":"I Remember Everything, Burn Burn Burn, Oklahoma Smokeshow"},
        {"name": "Noah Kahan",       "genres": "folk, indie pop",     "niche": "stick season",      "songs": "Stick Season, Dial Drunk, Northern Attitude, Forever"},
        {"name": "boygenius",        "genres": "indie folk, rock",    "niche": "the record",        "songs": "Not Strong Enough, True Blue, Emily I'm Sorry"},
        {"name": "Gillian Welch",    "genres": "folk, americana",     "niche": "time the revelator","songs":"Everything Is Free, Dark Turn of Mind, The Way It Goes"},
        
        # ─── CLASSICAL & NEO-CLASSICAL ────────────────────────
        {"name": "Ludovico Einaudi", "genres": "neo-classical, piano", "niche": "minimalist", "songs": "Experience, Nuvole Bianche, Una Mattina"},
        {"name": "Hania Rani",       "genres": "neo-classical, ambient", "niche": "modern piano", "songs": "Glass, Eden, Hawaii Oslo"},
        {"name": "Claude Debussy",   "genres": "classical, impressionist", "niche": "dreamy piano", "songs": "Clair de lune, Rêverie, Arabesque No. 1"},
        {"name": "Erik Satie",       "genres": "classical, avant-garde", "niche": "gymnopédies", "songs": "Gymnopédie No.1, Gnossienne No.1"},
        {"name": "Yann Tiersen",     "genres": "neo-classical, score", "niche": "amelie", "songs": "Comptine d'un autre été, La Valse d'Amélie"},
        {"name": "Philip Glass",     "genres": "classical, minimalist", "niche": "glassworks", "songs": "Opening, Truman Sleeps, Metamorphosis: One"},
        
        # ─── DEEP HOUSE & TECHNO ──────────────────────────────
        {"name": "Bicep",            "genres": "electronic, techno", "niche": "isles", "songs": "Glue, Apricots, Aura"},
        {"name": "Peggy Gou",        "genres": "house, electronic", "niche": "k-house", "songs": "Starry Night, It Goes Like (Nanana), I Go"},
        {"name": "Amelie Lens",      "genres": "techno, electronic", "niche": "hard techno", "songs": "Feel It, Higher, Basiel"},
        {"name": "CamelPhat",        "genres": "house, tech house", "niche": "club anthem", "songs": "Cola, Panic Room, Breathe"},
        {"name": "Gorgon City",      "genres": "house, electronic", "niche": "vocal house", "songs": "Ready for Your Love, Imagination, Voodoo"},

        # ─── METAL & HEAVY ────────────────────────────────────
        {"name": "Sleep Token",      "genres": "metal, alternative", "niche": "worship", "songs": "The Summoning, Chokehold, Take Me Back To Eden"},
        {"name": "Bring Me The Horizon", "genres": "metalcore, rock", "niche": "sempiternal", "songs": "Can You Feel My Heart, Throne, Drown"},
        {"name": "Bad Omens",        "genres": "metalcore, alternative", "niche": "tdopom", "songs": "Just Pretend, The Death of Peace of Mind, Like A Villain"},
        {"name": "Lorna Shore",      "genres": "deathcore, metal", "niche": "pain remains", "songs": "To the Hellfire, Pain Remains I, Into the Earth"},
        {"name": "Deftones",         "genres": "alt metal, shoegaze", "niche": "white pony", "songs": "Change, My Own Summer, Cherry Waves"},
    ]

    # Deduplicate by name (preserves first occurrence)
    seen = set()
    unique_artists = []
    for a in artists:
        if a["name"] not in seen:
            seen.add(a["name"])
            unique_artists.append(a)

    print(f"Seeding {len(unique_artists)} unique baseline artists...")

    success = 0
    failed = 0
    for a in unique_artists:
        try:
            await db.artistdirectory.upsert(
                where={"name": a["name"]},
                data={
                    "create": {
                        "name":   a["name"],
                        "genres": a["genres"],
                        "niche":  a.get("niche", ""),
                        "songs":  a.get("songs", ""),
                        # New fields — left null here, populated by enrich_artists.py
                        "mbid":             None,
                        "mbTags":           None,
                        "lbSimilarArtists": None,
                        "tadbId":           None,
                        "tadbMood":         None,
                        "tadbStyle":        None,
                        "tadbTop10":        None,
                    },
                    "update": {
                        "genres": a["genres"],
                        "niche":  a.get("niche", ""),
                        "songs":  a.get("songs", ""),
                        # Don't overwrite enrichment fields on re-seed
                    },
                },
            )
            print(f"  ✅ {a['name']}")
            success += 1
        except Exception as e:
            print(f"  ❌ {a['name']}: {e}")
            failed += 1

    print(f"\n🚀 Baseline Seed complete — {success} seeded, {failed} failed")


async def scrape_massive_library_from_lastfm(db: Prisma):
    """
    The Gigabrain Scraper: Pulls top 1000 artists across 37 vibe tags 
    directly from Last.fm to populate thousands of diverse artists.
    Fast, doesn't break rate limits, and uses HTTPS + User-Agent to prevent
    Last.fm from silently dropping the connection (which causes freezes).
    """
    LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "b25b959554ed76058ac220b7b2e0a026")
    
    # Covering all the vibe bases in your vibe_engine
    tags = [
        "pop", "k-pop", "j-pop", "hip-hop", "rap", "trap", "rnb", "soul", "jazz",
        "indie rock", "alternative", "shoegaze", "dream pop", "ambient", "drone",
        "electronic", "house", "techno", "synthwave", "hyperpop", "industrial",
        "metal", "metalcore", "deathcore", "classic rock", "country", "folk",
        "americana", "afrobeats", "reggaeton", "dancehall", "bollywood", "bhangra",
        "punjabi", "classical", "neo-classical", "film score"
    ]
    
    print(f"\n🌍 Initating Massive Scrape from Last.fm across {len(tags)} genres...")
    print("Hold tight bro, this is about to inject pure data into your DB.\n")
    
    # Last.fm requires a User-Agent or it might silent-drop the connection
    headers = {
        "User-Agent": "VibeFinderAI/8.0 (https://github.com/yourusername/vibefinder)"
    }
    
    success = 0
    # timeout=15.0 helps prevent connection hangs on Windows
    async with httpx.AsyncClient(headers=headers) as client:
        for tag in tags:
            print(f"  -> Fetching top artists for '{tag}'...")
            try:
                # Ask Last.fm for top 1000 artists for this tag. Must use HTTPS and url-encode!
                encoded_tag = urllib.parse.quote(tag)
                url = f"https://ws.audioscrobbler.com/2.0/?method=tag.gettopartists&tag={encoded_tag}&api_key={LASTFM_API_KEY}&format=json&limit=1000"
                
                r = await client.get(url, timeout=15.0)
                
                if r.status_code == 200:
                    data = r.json()
                    lastfm_artists = data.get("topartists", {}).get("artist", [])
                    
                    # Package all artists into a single list
                    artists_to_insert = []
                    for a in lastfm_artists:
                        name = a.get("name")
                        if name: 
                            artists_to_insert.append({
                                "name": name,
                                "genres": tag,
                                "niche": f"lastfm top {tag}",
                                "songs": "",
                            })
                            
                    if artists_to_insert:
                        # BULK INSERT: Sends all 1000 to Supabase in ONE single network request!
                        # skip_duplicates=True perfectly replaces the empty upsert logic
                        inserted = await db.artistdirectory.create_many(
                            data=artists_to_insert,
                            skip_duplicates=True
                        )
                        success += inserted
                        
                    print(f"  🔥 Scraped & Injected {len(lastfm_artists)} artists for '{tag}'")
                else:
                    print(f"  ⚠️ Bad response from Last.fm for '{tag}': {r.status_code}")
                
                # Chill out so we don't get banned by Last.fm
                await asyncio.sleep(0.5)
                
            except httpx.TimeoutException:
                print(f"  ❌ Timeout while scraping '{tag}' - Last.fm is being slow.")
            except Exception as e:
                print(f"  ❌ Failed scraping '{tag}': {e}")
                
    print(f"\n🚀 MASSIVE SCRAPE COMPLETE! Injected {success} artist records dynamically.")


async def main():
    parser = argparse.ArgumentParser(description="Seed the ArtistDirectory")
    parser.add_argument("--scrape", action="store_true", help="Run the Last.fm massive scraper after baseline seeding")
    parser.add_argument("--skip-baseline", action="store_true", help="Skip the hardcoded 230 baseline artists")
    args = parser.parse_args()

    # 1. Initialize DB exactly ONCE for the whole script
    db = Prisma()
    await db.connect()
    
    try:
        # 2. Run the safe, hardcoded baseline (unless skipped)
        if not args.skip_baseline:
            await seed(db)
        else:
            print("\n⏭️  Skipping the 230 baseline artists...")
        
        # 3. If you asked for the massive expansion, run the scraper
        if args.scrape:
            await scrape_massive_library_from_lastfm(db)
            
    finally:
        # 4. Safely close DB exactly ONCE at the end
        await db.disconnect()
        print(f"\nNext step: run `python enrich_artists.py` to fill out their metadata and top tracks!")

if __name__ == "__main__":
    asyncio.run(main())
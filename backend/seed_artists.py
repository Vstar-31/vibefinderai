import asyncio
import os
from dotenv import load_dotenv
from prisma import Prisma

# Load environment variables so Prisma can find DATABASE_URL
load_dotenv()

# This script slams over 120 essential and highly-requested artists into your Supabase ArtistDirectory.
# It covers everything from mainstream Pop and Rap to Niche EDM, K-Pop, Alt-Rock, and Afrobeats.
async def seed():
    db = Prisma()
    await db.connect()
    
    artists = [
        # Original 25 (Added top songs to the first few as a template)
        {"name": "Joji", "genres": "lo-fi, r&b, alternative", "niche": "sadboy", "songs": "Glimpse of Us, SLOW DANCING IN THE DARK"},
        {"name": "Travis Scott", "genres": "hip hop, trap", "niche": "rage", "songs": "goosebumps, SICKO MODE, FE!N"},
        {"name": "The Weeknd", "genres": "r&b, pop", "niche": "cinematic", "songs": "Blinding Lights, Starboy, The Hills"},
        {"name": "Kendrick Lamar", "genres": "hip hop, rap", "niche": "conscious", "songs": "HUMBLE., Not Like Us, DNA."},
        {"name": "Drake", "genres": "hip hop, pop rap", "niche": "mainstream", "songs": "God's Plan, One Dance"},
        
        {"name": "Taylor Swift", "genres": "pop, country", "niche": "storytelling"},
        {"name": "Frank Ocean", "genres": "r&b, alternative", "niche": "soulful"},
        {"name": "Playboi Carti", "genres": "hip hop, trap", "niche": "vamp"},
        {"name": "Tyler, The Creator", "genres": "hip hop, alternative", "niche": "experimental"},
        {"name": "Bad Bunny", "genres": "reggaeton, latin trap", "niche": "urbano"},
        {"name": "Deftones", "genres": "alternative metal, shoegaze", "niche": "ethereal"},
        {"name": "Lana Del Rey", "genres": "alternative, indie pop", "niche": "cinematic"},
        {"name": "Metro Boomin", "genres": "hip hop, trap", "niche": "producer"},
        {"name": "Future", "genres": "hip hop, trap", "niche": "toxic"},
        {"name": "Billie Eilish", "genres": "pop, alternative", "niche": "whisper"},
        {"name": "Mac Miller", "genres": "hip hop, rap", "niche": "chill"},
        {"name": "Tame Impala", "genres": "psychedelic pop, indie", "niche": "trippy"},
        {"name": "Arctic Monkeys", "genres": "indie rock, alternative", "niche": "night driving"},
        {"name": "Brent Faiyaz", "genres": "r&b, soul", "niche": "toxic r&b"},
        {"name": "Kanye West", "genres": "hip hop, rap", "niche": "genius"},
        {"name": "Radiohead", "genres": "alternative rock, electronic", "niche": "existential"},
        {"name": "MF DOOM", "genres": "underground hip hop", "niche": "villain"},
        {"name": "PinkPantheress", "genres": "drum and bass, pop", "niche": "y2k"},
        {"name": "Childish Gambino", "genres": "hip hop, r&b", "niche": "creative"},
        {"name": "Steve Lacy", "genres": "r&b, indie", "niche": "bedroom pop"},
        
        # Pop & Mainstream Giants
        {"name": "Ariana Grande", "genres": "pop, r&b", "niche": "vocalist"},
        {"name": "Dua Lipa", "genres": "pop, disco", "niche": "dance pop"},
        {"name": "Harry Styles", "genres": "pop, soft rock", "niche": "heartthrob"},
        {"name": "Olivia Rodrigo", "genres": "pop, pop punk", "niche": "teen angst"},
        {"name": "Doja Cat", "genres": "pop, hip hop", "niche": "versatile"},
        {"name": "Rihanna", "genres": "pop, r&b", "niche": "bad gal"},
        {"name": "Beyoncé", "genres": "r&b, pop", "niche": "queen bey"},
        {"name": "Charli XCX", "genres": "pop, hyperpop", "niche": "brat"},
        {"name": "Chappell Roan", "genres": "pop, synth-pop", "niche": "midwest princess"},
        {"name": "Sabrina Carpenter", "genres": "pop, r&b", "niche": "espresso"},
        {"name": "Troye Sivan", "genres": "pop, synth-pop", "niche": "club pop"},
        {"name": "Lorde", "genres": "pop, alternative", "niche": "melodrama"},
        
        # Hip Hop, Rap & Trap
        {"name": "J. Cole", "genres": "hip hop, rap", "niche": "lyrical"},
        {"name": "A$AP Rocky", "genres": "hip hop, trap", "niche": "cloud rap"},
        {"name": "Lil Uzi Vert", "genres": "hip hop, trap", "niche": "emo rap"},
        {"name": "21 Savage", "genres": "hip hop, trap", "niche": "deadpan"},
        {"name": "Eminem", "genres": "hip hop, rap", "niche": "technical"},
        {"name": "Nicki Minaj", "genres": "hip hop, pop", "niche": "barbz"},
        {"name": "Megan Thee Stallion", "genres": "hip hop, rap", "niche": "hottie"},
        {"name": "Ice Spice", "genres": "hip hop, drill", "niche": "bronx drill"},
        {"name": "Post Malone", "genres": "hip hop, pop", "niche": "melodic rap"},
        {"name": "Juice WRLD", "genres": "hip hop, emo rap", "niche": "heartbreak rap"},
        {"name": "XXXTENTACION", "genres": "hip hop, emo rap", "niche": "raw energy"},
        {"name": "Lil Peep", "genres": "hip hop, emo rap", "niche": "gothboiclique"},
        {"name": "$uicideboy$", "genres": "hip hop, trap", "niche": "shadow rap"},
        {"name": "Ghostemane", "genres": "hip hop, trap metal", "niche": "industrial rap"},
        {"name": "JID", "genres": "hip hop, rap", "niche": "fast flow"},
        {"name": "Denzel Curry", "genres": "hip hop, rap", "niche": "aggressive rap"},
        {"name": "Central Cee", "genres": "hip hop, uk drill", "niche": "uk rap"},
        {"name": "Skepta", "genres": "grime, hip hop", "niche": "uk grime"},
        
        # R&B & Neo Soul
        {"name": "SZA", "genres": "r&b, neo soul", "niche": "vulnerable"},
        {"name": "Daniel Caesar", "genres": "r&b, soul", "niche": "romantic"},
        {"name": "Giveon", "genres": "r&b, soul", "niche": "baritone"},
        {"name": "Summer Walker", "genres": "r&b, soul", "niche": "raw r&b"},
        {"name": "Bryson Tiller", "genres": "r&b, trap", "niche": "trapsoul"},
        
        # Indie, Rock & Alternative
        {"name": "Nirvana", "genres": "grunge, alternative rock", "niche": "angst"},
        {"name": "The Strokes", "genres": "indie rock, post-punk", "niche": "garage rock"},
        {"name": "Phoebe Bridgers", "genres": "indie folk, alternative", "niche": "sad indie"},
        {"name": "Mitski", "genres": "indie rock, alternative", "niche": "devastating"},
        {"name": "The Smiths", "genres": "indie pop, post-punk", "niche": "jangle pop"},
        {"name": "Mac DeMarco", "genres": "indie pop, psychedelic", "niche": "slacker rock"},
        {"name": "Clairo", "genres": "indie pop, lo-fi", "niche": "bedroom pop"},
        {"name": "Wallows", "genres": "indie rock, alternative", "niche": "indie pop"},
        {"name": "The 1975", "genres": "pop rock, synth-pop", "niche": "aesthetic"},
        {"name": "Florence + The Machine", "genres": "indie pop, baroque pop", "niche": "ethereal"},
        {"name": "Hozier", "genres": "indie rock, blues", "niche": "poetic"},
        {"name": "Fiona Apple", "genres": "alternative, art pop", "niche": "raw vocal"},
        {"name": "Sufjan Stevens", "genres": "indie folk, alternative", "niche": "heartbreaking"},
        {"name": "Bon Iver", "genres": "indie folk, electronic", "niche": "cabin in the woods"},
        {"name": "Vampire Weekend", "genres": "indie pop, alternative", "niche": "preppy indie"},
        {"name": "Paramore", "genres": "pop punk, alternative", "niche": "emo nostalgia"},
        {"name": "My Chemical Romance", "genres": "emo, alternative rock", "niche": "scene kid"},
        {"name": "Fall Out Boy", "genres": "pop punk, rock", "niche": "emo pop"},
        {"name": "Gorillaz", "genres": "alternative, electronic", "niche": "virtual band"},
        
        # Electronic, Dance & Internet Core
        {"name": "Daft Punk", "genres": "electronic, house", "niche": "french house"},
        {"name": "Skrillex", "genres": "electronic, dubstep", "niche": "bass"},
        {"name": "Fred again..", "genres": "electronic, house", "niche": "emotional dance"},
        {"name": "Disclosure", "genres": "electronic, house", "niche": "uk garage"},
        {"name": "Flume", "genres": "electronic, future bass", "niche": "experimental bass"},
        {"name": "Kaytranada", "genres": "electronic, r&b", "niche": "groove"},
        {"name": "Aphex Twin", "genres": "electronic, idm", "niche": "ambient"},
        {"name": "Justice", "genres": "electronic, electro house", "niche": "french touch"},
        {"name": "ODESZA", "genres": "electronic, chillwave", "niche": "cinematic electronic"},
        {"name": "Peggy Gou", "genres": "electronic, house", "niche": "k-house"},
        {"name": "Bicep", "genres": "electronic, house", "niche": "uk electronic"},
        {"name": "Rüfüs Du Sol", "genres": "electronic, alternative dance", "niche": "live electronic"},
        {"name": "Bladee", "genres": "hip hop, cloud rap", "niche": "drain gang"},
        {"name": "Yung Lean", "genres": "hip hop, cloud rap", "niche": "sad boys"},
        {"name": "100 gecs", "genres": "hyperpop, electronic", "niche": "internet core"},
        {"name": "Porter Robinson", "genres": "electronic, synth-pop", "niche": "weeb electronic"},
        {"name": "Grimes", "genres": "art pop, electronic", "niche": "cyberpunk"},
        
        # Reggaeton, Latin & Afrobeats
        {"name": "Rosalía", "genres": "pop, flamenco", "niche": "motomami"},
        {"name": "J Balvin", "genres": "reggaeton, latin pop", "niche": "colores"},
        {"name": "Rauw Alejandro", "genres": "reggaeton, r&b", "niche": "synth reggaeton"},
        {"name": "Karol G", "genres": "reggaeton, latin pop", "niche": "bichota"},
        {"name": "Peso Pluma", "genres": "regional mexican, corridos", "niche": "corridos tumbados"},
        {"name": "Shakira", "genres": "latin pop, pop", "niche": "global latin"},
        {"name": "Burna Boy", "genres": "afrobeats, dancehall", "niche": "african giant"},
        {"name": "Wizkid", "genres": "afrobeats, pop", "niche": "starboy"},
        {"name": "Rema", "genres": "afrobeats, trap", "niche": "afrorave"},
        {"name": "Tyla", "genres": "amapiano, pop", "niche": "water"},
        
        # K-Pop
        {"name": "BTS", "genres": "k-pop, pop", "niche": "army"},
        {"name": "BLACKPINK", "genres": "k-pop, pop", "niche": "girl crush"},
        {"name": "NewJeans", "genres": "k-pop, r&b", "niche": "y2k kpop"},
        {"name": "Stray Kids", "genres": "k-pop, hip hop", "niche": "noise pop"},
        
        # Country
        {"name": "Zach Bryan", "genres": "country, folk", "niche": "outlaw country"},
        {"name": "Morgan Wallen", "genres": "country, pop", "niche": "bro country"},
        {"name": "Luke Combs", "genres": "country, pop", "niche": "stadium country"},
        {"name": "Kacey Musgraves", "genres": "country, pop", "niche": "space cowboy"},
        
        # Metal & Nu Metal
        {"name": "Slipknot", "genres": "nu metal, heavy metal", "niche": "maggot"},
        {"name": "System Of A Down", "genres": "nu metal, alternative metal", "niche": "political metal"},
        {"name": "Korn", "genres": "nu metal", "niche": "angsty metal"},
        
        # Classics & Legends
        {"name": "The Beatles", "genres": "rock, pop", "niche": "classic rock"},
        {"name": "Michael Jackson", "genres": "pop, r&b", "niche": "king of pop"},
        {"name": "Prince", "genres": "pop, r&b", "niche": "funk"},
        {"name": "Queen", "genres": "rock, pop", "niche": "theatrical rock"},
        {"name": "David Bowie", "genres": "rock, pop", "niche": "art rock"},
        {"name": "Fleetwood Mac", "genres": "rock, pop", "niche": "soft rock"}
    ]
    
    print(f"Seeding {len(artists)} artists into the dictionary...")
    for a in artists:
        try:
            # Upsert ensures we don't create duplicates if you run the script twice
            # Using .get("songs", "") allows you to add songs later without breaking the loop now
            await db.artistdirectory.upsert(
                where={"name": a["name"]},
                data={
                    "create": {"name": a["name"], "genres": a["genres"], "niche": a["niche"], "songs": a.get("songs", "")},
                    "update": {"genres": a["genres"], "niche": a["niche"], "songs": a.get("songs", "")}
                }
            )
            print(f"✅ Seeded: {a['name']}")
        except Exception as e:
            print(f"❌ Failed to seed {a['name']}: {e}")
            
    await db.disconnect()
    print("\n🚀 Database Seed Complete! VibeFinder can now recognize a massive global roster.")

if __name__ == "__main__":
    asyncio.run(seed())
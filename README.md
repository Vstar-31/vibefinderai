# VibeFinderAI — Product Documentation

***

## What is VibeFinderAI?

**VibeFinderAI** is an AI-powered music discovery platform that finds songs matching a *feeling, mood, or scene* — not just a genre or artist name. Instead of searching for "pop" or "hip-hop," you describe an experience in plain language — like *"late night drive through rain-slicked streets, Travis Scott on the radio"* — and the engine analyzes your description and returns a curated playlist of tracks that match that exact vibe. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

The interface is designed with an aesthetic inspired by audio hardware and synthesizers — complete with rotary knobs, oscilloscope animations, and a dark studio-panel visual theme — making it feel like operating a professional audio intelligence machine.

***

## Core Concept: Vibe-Based Discovery

Traditional music apps let you search by artist, song, or genre. VibeFinderAI takes a fundamentally different approach: **describe the emotional and situational context** of what you want to listen to, and the AI figures out what matches. This is particularly powerful for moods, activities, or scenes that don't map neatly to a single genre.

***

## How It Works — Step by Step

### Step 1: Connect / Authenticate
At the top of the interface is the **OSC (Oscillator/Access)** input field alongside a **DISCONNECT** button. This handles the session authentication, connecting your instance to the AI engine before you can run an analysis. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

### Step 2: Describe the Vibe
The large central text field — labeled **"Describe the Vibe // ACOUSTIC DESCRIPTOR INPUT"** — is where you type your mood, scene, or experience in natural language. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

Example prompt shown in the interface:
> *"Late night drive through rain-slicked streets, Travis Scott on the radio..."*

You can mention:
- Moods (chill, dark, euphoric, melancholic)
- Artists you like as a reference point
- Scenes or activities (studying, working out, a night drive, heartbreak)
- Atmospheric descriptions (rainy, dreamy, nostalgic)

### Step 3: Tune the Knobs (Optional)
Three rotary knobs at the top of the panel let you fine-tune the acoustic parameters: [vibefinderai.netlify](https://vibefinderai.netlify.app/)

| Knob | Function |
|------|----------|
| **ARTIST** | How closely the results should resemble a specific artist's sound |
| **NICHENESS** | Controls how obscure or mainstream the track recommendations should be — turn it up for deep cuts, down for popular hits |
| **BPM** | Sets the target energy level / tempo range for the results |

### Step 4: Select Language
A **LANGUAGE** dropdown lets you filter results by the language of the songs. Supported options include: [vibefinderai.netlify](https://vibefinderai.netlify.app/)
- Any Language (default)
- Hindi, Punjabi, Tamil, Telugu, Kannada, Malayalam, Bengali, Urdu *(extensive Indian language support)*
- English, Korean, Japanese, Spanish, Portuguese, French, Arabic
- **Afrobeats** (genre-language hybrid filter)

### Step 5: Set Track Count
Choose how many songs you want in your generated playlist: **5, 10, 20, or 50 tracks**. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

### Step 6: Run Analysis
Click the **RUN ANALYSIS** button to send your vibe description to the AI engine. The button activates only once you've typed something in the descriptor field.

***

## Results — What You Get

After analysis completes, the interface transitions to a detailed results view:

### Analysis Complete Panel

#### Dominant Vibe Card
The AI classifies your description into a **Dominant Vibe** — a single emotional label like *"chill"*, *"hype"*, *"melancholic"*, etc. — along with a **Confidence score** (e.g., 53%). If the AI detects an overlapping mood, it surfaces a **Secondary Signature** with an option to *"Pivot Engine to: [secondary vibe]"* for alternative results. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

#### Target Tempo Card
Displays the matched **BPM range** (e.g., *70–100 BPM*) and describes the rhythmic feel, such as *"Rhythmic Pulse"*. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

#### Engine State / Genre Tags
A panel of clickable genre tags representing the AI's interpretation of your vibe — such as **NEO-SOUL, INDIE R&B, CHILLWAVE, LO-FI HIP HOP, VAPORWAVE, PLUGGNB, JAZZ HOP, TRIP HOP, YACHT ROCK, BALEARIC BEAT, DOWNTEMPO, CHILLSTEP, LOUNGE**. Clicking a genre applies a **hard filter** to narrow results. Locked artist references (e.g., *LOCKED: TRAVIS SCOTT*) show when the AI anchored its analysis to a specific artist you mentioned. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

### Generated Playlist
The main playlist section lists all matched tracks, each with:
- **Album artwork thumbnail**
- **Track title** and **Artist name**
- **👍 / 👎 feedback buttons** — to rate whether a suggestion was a good match (for future refinement)
- **PREVIEW button** — plays a short audio preview of the track inline
- **SPOTIFY button** — opens the track directly on Spotify [vibefinderai.netlify](https://vibefinderai.netlify.app/)

### Neural Match Breakdown
A set of hashtag-style keywords extracted from your input — for example: `#late night` `#late night drive` `#night drive` `#rain` `#travis scott` — showing exactly which semantic concepts the AI used to match your vibe. [vibefinderai.netlify](https://vibefinderai.netlify.app/)

***

## Pro Mode — Manual Overrides

Clicking **MANUAL OVERRIDES // PRO MODE** expands an advanced control panel: [vibefinderai.netlify](https://vibefinderai.netlify.app/)

| Control | What It Does |
|--------|--------------|
| **Force Artist Bypass** | Lock the results to a specific artist's discography or sound profile (e.g., type "Deftones") regardless of vibe |
| **Force Genre Bypass** | Lock results to a specific genre (e.g., "shoegaze") overriding the AI's genre inference |
| **Hard-Switch to Secondary Vibe** | Toggle to force the engine to use the secondary detected vibe instead of the dominant one |

This is designed for power users who want to combine the vibe-based AI matching with manual genre/artist constraints.

***

## Technology Stack

VibeFinderAI is built as a modern full-stack web application:

**Frontend:**
- React with Vite (JavaScript ES6 JSX)
- CSS animations and audio visualization (oscilloscope effects)
- Responsive hybrid UI with hardware knob components
- Deployed on Netlify CDN

**Backend:**
- FastAPI (Python) with JWT authentication
- Prisma ORM for database management
- LangChain orchestration for AI prompts
- vibe_engine.py NLP engine for semantic analysis

**Database:**
- Supabase PostgreSQL with Prisma schema
- User authentication and social graph
- Playlist history and feedback tracking

**External APIs:**
- Last.fm for music metadata and ISRC mapping
- Spotify Web API for track discovery and deep links
- LangChain for prompt orchestration

**Deployment:**
- Backend: Render (OnRender)
- Frontend: Netlify
- CI/CD pipeline for automated testing and deployment

***

## Project Structure

See [filesystem.md](filesystem.md) for complete directory structure. Key directories:

- `/frontend` — React app, components, styling
- `/backend` — FastAPI server, AI engine, enrichment pipeline
- `/backend/schema.prisma` — Database schema
- Documentation files describe architecture and deployment

***

## Development Phases

The project is organized into 6 development phases. See [phases.md](phases.md) for detailed breakdown:

1. **Phase 1**: Foundation, Monorepo, Database & JWT Auth
2. **Phase 2**: Core Music APIs & ISRC Mapping
3. **Phase 3**: AI Recommendation Engine (LangChain + vibe_engine)
4. **Phase 4**: Social Graph & Community Features
5. **Phase 5**: Audio Visualization & Hybrid UI
6. **Phase 6**: Production Deployment & CI/CD

***

## Documentation Reference

- [architecture.md](architecture.md) — System architecture with Mermaid diagrams
- [filesystem.md](filesystem.md) — Complete folder structure
- [features.md](features.md) — Feature-by-phase breakdown
- [phases.md](phases.md) — Development roadmap (Phases 1-6)
- [analysis.md](analysis.md) — QA & stress test results
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — Production deployment instructions
- [monetisation.md](monetisation.md) — API licensing & cost reference

***

## Additional UI Elements

- **SIGNAL ACTIVE** indicator with an animated waveform bar — shows the engine is live and processing [vibefinderai.netlify](https://vibefinderai.netlify.app/)
- **RESET ENGINE** button — appears after a search to clear results and start fresh [vibefinderai.netlify](https://vibefinderai.netlify.app/)
- Real-time **audio waveform visualizer** in the top-right of the input panel
- The entire UI is responsive and styled with a retro-futuristic synthesizer/oscilloscope aesthetic that reinforces the "acoustic intelligence" branding

***

## Key Use Cases

1. **Mood-based listening** — You feel something but don't know what song fits. Just describe the feeling.
2. **Scene or activity playlists** — Gaming session, late-night coding, gym workout, study session — describe the context and get a perfectly tuned playlist.
3. **Artist-inspired discovery** — Mention a reference artist and let the AI find sonically similar but lesser-known tracks (use the Nicheness knob).
4. **Multilingual music discovery** — Specifically powerful for discovering Indian regional music (Hindi, Tamil, Punjabi, etc.) through emotional descriptions.
5. **Genre exploration** — Use the Engine State genre tags as clickable filters to drill into specific subgenres surfaced by the AI.

***

## Summary

VibeFinderAI is a mood-first, language-native music discovery engine. Instead of asking *"what genre?"*, it asks *"what does this moment feel like?"* — and delivers a real, playable Spotify playlist that matches. With support for 16+ languages, adjustable acoustic parameters, genre filtering, and Pro Mode overrides, it serves both casual listeners who just want to describe a feeling and power users who want precise control over their discovery experience. [vibefinderai.netlify](https://vibefinderai.netlify.app/)
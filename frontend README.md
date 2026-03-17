# VibeFinderAI — Frontend

React + Vite frontend for the VibeFinderAI music discovery platform.

## Overview

The frontend is a **full-featured music discovery UI** built with React and Vite, featuring:
- Vibe-based search engine UI with rotary knobs for parameter tuning
- Real-time results with flickering visual feedback
- Multiple audio playback modes (Play All, Play, Preview)
- Analytics dashboard with passphrase authentication
- Service connection management (YouTube, Spotify, Last.fm, etc.)
- Floating music player for full-length playback

## Quick Start

```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

## File Structure

```
src/
├── App.jsx                   # Main search engine UI
├── App.css                   # Styling (dark theme, retro synth aesthetic)
├── MusicPlayer.jsx           # Floating audio player component
├── AnalyticsDashboard.jsx   # Real-time metrics dashboard
├── LandingPage.jsx          # Welcome/intro page
├── PlaylistPanel.jsx         # Playlist management
├── ServicesPanel.jsx         # Service connection UI
├── SharedPlaylist.jsx        # Shared playlist view
├── index.css                 # Global styles
├── main.jsx                  # React entry point
└── assets/                   # Images, icons, etc.
```

## Key Components

### App.jsx (2500+ lines)
Main search interface with:
- Text input for vibe descriptions
- Three rotary knobs (Artist, Nicheness, BPM)
- Language selector (20+ languages including Indian regional)
- Track count selector (5, 10, 20, 50)
- Results display with action buttons
- Pro Mode manual overrides
- Tutorial overlay

### MusicPlayer.jsx
Floating music player for full-length track playback via YouTube embeds.

### AnalyticsDashboard.jsx
Real-time metrics dashboard showing:
- Live searches and vibes
- Engine performance
- User engagement
- Feedback analysis
- Data quality metrics

### Other Components
- **PlaylistPanel.jsx** — Playlist creation, naming, saving
- **ServicesPanel.jsx** — Connect/disconnect from music services
- **LandingPage.jsx** — Welcome page and tutorial
- **SharedPlaylist.jsx** — Public playlist sharing

## Audio Playback System

Three distinct audio modes:

1. **Play All** — Queues all search results with embeds in MusicPlayer
   - Filters to tracks with YouTube embeds only
   - Full-length playback for entire playlist

2. **Play** *(YouTube connected)* — Single track playback
   - Launches MusicPlayer with single track
   - Requires active YouTube OAuth connection

3. **Preview** — Inline 30-second iTunes preview
   - HTML5 audio element (no player needed)
   - Works without any service connection

## Environment Variables

Create a `.env` file in the frontend directory:

```bash
VITE_API_URL=http://localhost:8000  # Development
# or
VITE_API_URL=https://vibefinderai-backend.onrender.com  # Production
```

## Development

### Hot Module Replacement (HMR)
Changes auto-reload in browser during development.

### Building
```bash
npm run build  # Creates optimized production build
npm run preview  # Test production build locally
```

### Linting
```bash
npm run lint  # Run ESLint
```

## Deployment

Frontend is auto-deployed to Netlify on every push to `main` branch:
- Build command: `npm run build`
- Publish directory: `dist/`
- Environment: `VITE_API_URL` set in Netlify dashboard

## UI/UX Features

- **Dark theme** with retro synthesizer aesthetic
- **Rotary knob components** for parameter tuning
- **Oscilloscope animations** for visual feedback
- **Color-coded genre tags** as clickable live filters
- **Responsive design** for desktop and tablet
- **Keyboard accessibility** where possible
- **Tutorial overlay** for first-time users

## State Management

React hooks for state:
- `useState` for component state
- `useEffect` for side effects (API calls, analytics)
- `useRef` for DOM references (music player)
- Props drilling for component communication

## API Integration

All backend communication via fetch API:
- Vibe analysis: `POST /api/vibe/analyze`
- Service connections: `GET /api/spotify/auth`, `GET /api/youtube/auth`
- Analytics: `GET /api/analytics/dashboard` (with metrics token)
- Last.fm proxy: `GET /api/lastfm/proxy`
- Feedback: `POST /api/feedback`

## Testing

Interactive testing in browser:
- Open DevTools (F12) for console logs
- Check Network tab for API calls
- Use React DevTools extension for component inspection

## Common Issues

| Issue | Solution |
|-------|----------|
| CORS errors | Verify `VITE_API_URL` points to backend, check backend CORS config |
| OAuth fails | Confirm redirect URIs match OAuth app settings |
| 404 on routes | Check API endpoints in App.jsx match backend routes |
| Audio doesn't play | Check browser autoplay policy (may need HTTPS) |
| Metrics auth fails | Verify metrics token from `/api/metrics/auth` endpoint |

## Related Documentation

- [../README.md](../README.md) — Main project documentation
- [../QUICK_REFERENCE.md](../QUICK_REFERENCE.md) — API reference
- [../backend/ORGANIZATION_GUIDE.md](../backend/ORGANIZATION_GUIDE.md) — Backend structure

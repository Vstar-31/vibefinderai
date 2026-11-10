import { StrictMode, useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import LandingPage from './LandingPage.jsx'
import SharedPlaylist from './SharedPlaylist.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'
import EmbedPlayer from './EmbedPlayer.jsx'
import AppWithThemedAI from './AppWithThemedAI.jsx'
import PersonalizationAgent from './PersonalizationAgent.jsx'
import ThemedApp from './ThemedApp.jsx'

/* ─── Route resolver ─────────────────────────────────────────────
   Called on every navigation event. Reads the live URL each time.

   OAuth callbacks from Spotify / Last.fm / YouTube land on the root
   because the backend's FRONTEND_URL env var points to the domain
   root. We detect those query params and keep the user on /app so
   callback handlers in App.jsx fire correctly.
──────────────────────────────────────────────────────────────── */
function resolveRoute() {
  const path   = window.location.pathname;
  const params = new URLSearchParams(window.location.search);

  const isOAuthCallback =
    params.get('spotify') ||
    params.get('service_connected') ||
    params.get('service_error');

  if (path.startsWith('/embed/player'))  return 'embed-player';
  if (path.startsWith('/playlist/')) return 'playlist';
  if (path === '/themed')            return 'themed';
  if (window.chrome?.webview && (path === '/' || path.startsWith('/app') || isOAuthCallback)) return 'desktop-app';
  if (path.startsWith('/app'))       return 'app';
  if (path === '/vf-metrics')        return 'metrics';
  if (isOAuthCallback)               return 'app';   // backend lands here → keep on engine
  return 'landing';
}

/* ─── Router component ───────────────────────────────────────── */
function Router() {
  const [route, setRoute] = useState(resolveRoute);

  // navigate() is passed as a prop so child components don't need
  // to know about the router — they just call navigate('/app') etc.
  const navigate = (path) => {
    window.history.pushState({}, '', path);
    setRoute(resolveRoute());
  };

  // Back / forward buttons
  useEffect(() => {
    const handlePop = () => setRoute(resolveRoute());
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, []);

  if (route === 'embed-player') return <EmbedPlayer />;
  if (route === 'playlist') return <SharedPlaylist />;
  if (route === 'metrics')  return <AnalyticsDashboard />;
  if (route === 'themed') return <ThemedApp />;
  if (route === 'desktop-app') return (
    <>
      <PersonalizationAgent />
      <AppWithThemedAI onNavigate={navigate} />
    </>
  );
  if (route === 'app')      return <App onNavigate={navigate} />;
  return <LandingPage onNavigate={navigate} />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>
)

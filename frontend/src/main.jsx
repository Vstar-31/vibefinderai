import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import AppWithThemedAI from './AppWithThemedAI.jsx'
import ThemedApp from './ThemedApp.jsx'
import SharedPlaylist from './SharedPlaylist.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'

/* The Themed.AI branch keeps the existing VibeFinderAI surfaces available,
   while embedding the desktop-first Themed.AI workspace directly into the
   legacy app instead of routing to a separate page. */
function resolveRoute() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);
  const isOAuthCallback = params.get('spotify') || params.get('service_connected') || params.get('service_error');

  if (path.startsWith('/playlist/')) return 'playlist';
  if (path.startsWith('/app')) return 'legacy-app';
  if (path === '/vf-metrics') return 'metrics';
  if (isOAuthCallback) return 'legacy-app';
  return 'themed';
}

function Router() {
  const [route, setRoute] = useState(resolveRoute);
  const navigate = (path) => {
    window.history.pushState({}, '', path);
    setRoute(resolveRoute());
  };

  useEffect(() => {
    const handlePop = () => setRoute(resolveRoute());
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, []);

  if (route === 'playlist') return <SharedPlaylist />;
  if (route === 'metrics') return <AnalyticsDashboard />;
  if (route === 'legacy-app') return <AppWithThemedAI onNavigate={navigate} />;
  return <ThemedApp />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>
)

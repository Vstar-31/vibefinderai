import { StrictMode, useEffect, useState } from 'react'
import AppWithThemedAI from './AppWithThemedAI.jsx'
import ThemedApp from './ThemedApp.jsx'
import SharedPlaylist from './SharedPlaylist.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'
import PersonalizationAgent from './PersonalizationAgent.jsx'

/* Keep the production/web experience on the original VibeFinderAI UI.
   The Themed.AI desktop integration is mounted around /app so the original
   interface remains intact while the host bridge and personalization loop run. */
function resolveRoute() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);
  const isOAuthCallback = params.get('spotify') || params.get('service_connected') || params.get('service_error');

  if (path.startsWith('/playlist/')) return 'playlist';
  if (path === '/themed') return 'themed';
  if (path === '/vf-metrics') return 'metrics';
  if (isOAuthCallback || path.startsWith('/app')) return 'legacy-app';
  return 'legacy-app';
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
  if (route === 'themed') return <ThemedApp />;
  return (
    <>
      <PersonalizationAgent />
      <AppWithThemedAI onNavigate={navigate} />
    </>
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>
)

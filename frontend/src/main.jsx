import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import ThemedApp from './ThemedApp.jsx'
import SharedPlaylist from './SharedPlaylist.jsx'
import AnalyticsDashboard from './AnalyticsDashboard.jsx'

/* The Themed.AI branch is a dedicated Netlify client. Keep the existing
   app/playlist/metrics surfaces available for compatibility, but make the
   desktop-first Themed.AI experience the root experience. */
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
  if (route === 'legacy-app') return <App onNavigate={navigate} />;
  return <ThemedApp />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>
)

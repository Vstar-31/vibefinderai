import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import SharedPlaylist from './SharedPlaylist.jsx'

// Simple client-side router — no react-router dependency needed
const path = window.location.pathname;
const isSharedPlaylist = path.startsWith('/playlist/');

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isSharedPlaylist ? <SharedPlaylist /> : <App />}
  </StrictMode>
)

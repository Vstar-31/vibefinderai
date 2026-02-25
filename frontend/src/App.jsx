import React, { useState } from 'react';

// Custom SVG Icons to replace lucide-react (prevents "module not found" errors)
const IconZap = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.71 14.71 4l-1.64 6.18L20 9.29 9.29 20l1.64-6.18L4 14.71z"/></svg>
);
const IconLock = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
);
const IconUnlock = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>
);
const IconPlay = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>
);
const IconActivity = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
);
const IconMusic = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
);
const IconHash = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/></svg>
);

export default function App() {
  const [token, setToken] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Hit our mock auth endpoint to get the JWT
  const handleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      // FastAPI's OAuth2PasswordBearer expects form data!
      const formData = new URLSearchParams();
      formData.append('username', 'dev_bro');
      formData.append('password', 'password123');

      const res = await fetch('http://127.0.0.1:8000/auth/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      });

      if (!res.ok) throw new Error('Login failed bro');
      
      const data = await res.json();
      setToken(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Send the vibe text to our custom NLP brain
  const analyzeVibe = async () => {
    if (!prompt.trim()) return;
    
    try {
      setLoading(true);
      setError('');
      
      const res = await fetch('http://127.0.0.1:8000/api/vibe/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ text: prompt }),
      });

      if (res.status === 401) {
        setToken(null);
        throw new Error('Token expired or invalid. Log in again!');
      }
      
      if (!res.ok) throw new Error('Failed to analyze vibe');

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-6 md:p-12 font-sans selection:bg-indigo-500/30">
      <div className="max-w-3xl mx-auto space-y-8">
        
        {/* Header section */}
        <header className="flex items-center justify-between pb-6 border-b border-neutral-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-xl">
              <IconZap />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">VibeFinder<span className="text-indigo-400">AI</span></h1>
          </div>
          
          <button 
            onClick={token ? () => setToken(null) : handleLogin}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              token 
                ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' 
                : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/20'
            }`}
          >
            {token ? <IconUnlock /> : <IconLock />}
            {token ? 'Sign Out' : 'Dev Login'}
          </button>
        </header>

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl">
            {error}
          </div>
        )}

        {/* Main Input Area */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl">
          <h2 className="text-lg font-semibold mb-4 text-neutral-300">What's the mood today?</h2>
          
          <div className="relative">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., 'I'm hitting the gym for a crazy pump and need some aggressive energy...'"
              className="w-full h-32 bg-neutral-950 border border-neutral-800 rounded-xl p-4 text-neutral-200 placeholder-neutral-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 resize-none transition-all"
              disabled={!token || loading}
            />
            
            {!token && (
              <div className="absolute inset-0 bg-neutral-950/60 backdrop-blur-sm rounded-xl flex items-center justify-center">
                <p className="text-neutral-400 font-medium flex items-center gap-2">
                  <IconLock /> Please login first bro
                </p>
              </div>
            )}
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={analyzeVibe}
              disabled={!token || loading || !prompt.trim()}
              className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-500/20"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <IconPlay />
              )}
              Analyze Vibe
            </button>
          </div>
        </div>

        {/* Results Dashboard */}
        {result && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 flex flex-col items-center text-center">
              <div className="p-3 bg-blue-500/10 rounded-full mb-3 text-blue-400">
                <IconActivity />
              </div>
              <p className="text-neutral-500 text-sm font-medium mb-1">Dominant Vibe</p>
              <h3 className="text-2xl font-bold capitalize text-neutral-100">{result.dominant_vibe}</h3>
              <p className="text-xs text-neutral-600 mt-2">Confidence: {Math.round(result.confidence * 100)}%</p>
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 flex flex-col items-center text-center">
              <div className="p-3 bg-emerald-500/10 rounded-full mb-3 text-emerald-400">
                <IconMusic />
              </div>
              <p className="text-neutral-500 text-sm font-medium mb-1">Target BPM</p>
              <h3 className="text-2xl font-bold text-neutral-100">{result.bpm_range}</h3>
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 flex flex-col items-center text-center">
              <div className="p-3 bg-purple-500/10 rounded-full mb-3 text-purple-400">
                <IconHash />
              </div>
              <p className="text-neutral-500 text-sm font-medium mb-1">Top Genres</p>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {result.genres.map(genre => (
                  <span key={genre} className="px-2 py-1 bg-neutral-800 text-neutral-300 rounded-md text-xs font-medium border border-neutral-700">
                    {genre}
                  </span>
                ))}
              </div>
            </div>

            <div className="md:col-span-3 bg-neutral-900 border border-neutral-800 rounded-2xl p-6 mt-2">
              <p className="text-sm text-neutral-500 mb-3">Matched Keywords Triggered:</p>
              <div className="flex flex-wrap gap-2">
                {result.matched_keywords.length > 0 ? (
                  result.matched_keywords.map(kw => (
                    <span key={kw} className="px-3 py-1.5 bg-indigo-500/10 text-indigo-300 rounded-lg text-sm font-medium border border-indigo-500/20">
                      {kw}
                    </span>
                  ))
                ) : (
                  <span className="text-neutral-600 text-sm">No specific keywords matched.</span>
                )}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
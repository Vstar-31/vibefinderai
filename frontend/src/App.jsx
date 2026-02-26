import React, { useState } from 'react';

// Custom SVG Icons
const IconZap = () => (<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14.71 14.71 4l-1.64 6.18L20 9.29 9.29 20l1.64-6.18L4 14.71z"/></svg>);
const IconLock = () => (<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>);
const IconUnlock = () => (<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>);
const IconPlay = () => (<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>);
const IconActivity = () => (<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>);
const IconMusic = () => (<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>);
const IconHash = () => (<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/></svg>);
const IconUser = () => (<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>);
const IconMail = () => (<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>);
const IconX = () => (<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>);

export default function App() {
  // Core App State
  const [token, setToken] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Auth Modal State
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLoginView, setIsLoginView] = useState(true);
  const [authForm, setAuthForm] = useState({ email: '', username: '', password: '' });

  // Handle Input Changes for Auth
  const handleAuthChange = (e) => {
    setAuthForm({ ...authForm, [e.target.name]: e.target.value });
  };

  // Secure Registration & Login Flow
  const submitAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // 1. If registering, hit the create user endpoint first
      if (!isLoginView) {
        const regRes = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: authForm.email,
            username: authForm.username,
            password: authForm.password
          })
        });

        if (!regRes.ok) {
          const errData = await regRes.json();
          throw new Error(errData.detail || 'Registration failed');
        }
      }

      // 2. Fetch the actual JWT Token (Runs for both Login and right after Registration)
      const formData = new URLSearchParams();
      formData.append('username', authForm.username);
      formData.append('password', authForm.password);

      const logRes = await fetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!logRes.ok) throw new Error('Invalid credentials, bro');
      
      const data = await logRes.json();
      setToken(data.access_token);
      
      // Cleanup UI
      setShowAuthModal(false);
      setAuthForm({ email: '', username: '', password: '' });
      setIsLoginView(true);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setResult(null);
    setPrompt('');
  };

  // Hit the custom AI vibe analyzer (Using Vite Proxy /api/vibe/analyze)
  const analyzeVibe = async () => {
    if (!prompt.trim()) return;
    try {
      setLoading(true);
      setError('');
      const res = await fetch('/api/vibe/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ text: prompt }),
      });
      if (res.status === 401) {
        handleLogout();
        throw new Error('Session expired. Log in again!');
      }
      if (!res.ok) throw new Error('Analysis failed');
      const data = await res.json();
      setResult(data);
    } catch (err) { 
      setError(err.message); 
    } finally { 
      setLoading(false); 
    }
  };

  return (
    <div className="min-h-screen bg-black text-neutral-100 p-4 md:p-12 font-sans selection:bg-indigo-500/30 overflow-x-hidden relative">
      
      {/* ----------------- AUTH MODAL OVERLAY ----------------- */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 w-full max-w-md shadow-2xl relative">
            
            <button 
              onClick={() => setShowAuthModal(false)}
              className="absolute top-6 right-6 text-neutral-500 hover:text-white transition-colors"
            >
              <IconX />
            </button>

            <div className="flex items-center gap-3 mb-8">
              <div className="p-2 bg-indigo-600/20 rounded-xl text-indigo-400">
                <IconZap />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-tight">
                {isLoginView ? 'System Access' : 'Initialize User'}
              </h2>
            </div>

            {error && (
              <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm font-medium">
                {error}
              </div>
            )}

            <form onSubmit={submitAuth} className="space-y-4">
              {!isLoginView && (
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-widest text-neutral-500 ml-1">Email</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-neutral-500">
                      <IconMail />
                    </div>
                    <input 
                      type="email" name="email" value={authForm.email} onChange={handleAuthChange} required={!isLoginView}
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-xl py-3 pl-12 pr-4 text-white focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all"
                      placeholder="hacker@vibes.com"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-widest text-neutral-500 ml-1">Username</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-neutral-500">
                    <IconUser />
                  </div>
                  <input 
                    type="text" name="username" value={authForm.username} onChange={handleAuthChange} required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-xl py-3 pl-12 pr-4 text-white focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all"
                    placeholder="dev_bro"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-widest text-neutral-500 ml-1">Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-neutral-500">
                    <IconLock />
                  </div>
                  <input 
                    type="password" name="password" value={authForm.password} onChange={handleAuthChange} required
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-xl py-3 pl-12 pr-4 text-white focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button 
                type="submit" disabled={loading}
                className="w-full py-3.5 mt-6 bg-indigo-600 hover:bg-indigo-500 text-white font-black rounded-xl uppercase tracking-widest transition-all shadow-lg shadow-indigo-600/20 active:scale-95 disabled:opacity-50"
              >
                {loading ? 'Processing...' : (isLoginView ? 'Authenticate' : 'Create Identity')}
              </button>
            </form>

            <div className="mt-6 text-center">
              <button 
                type="button"
                onClick={() => { setIsLoginView(!isLoginView); setError(''); setAuthForm({email:'', username:'', password:''}); }}
                className="text-sm text-neutral-500 hover:text-indigo-400 transition-colors"
              >
                {isLoginView ? "Need an account? Initialize one." : "Already have access? Authenticate."}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ------------------------------------------------------ */}


      <div className="max-w-4xl mx-auto space-y-12">
        
        {/* Header */}
        <header className="flex items-center justify-between pb-8 border-b border-neutral-800/50">
          <div className="flex items-center gap-4 group cursor-default">
            <div className="p-3 bg-indigo-600/20 rounded-2xl text-indigo-400 group-hover:scale-110 transition-transform duration-300 shadow-[0_0_20px_rgba(79,70,229,0.2)]">
              <IconZap />
            </div>
            <h1 className="text-3xl font-black tracking-tighter uppercase">
              VibeFinder<span className="text-indigo-500">AI</span>
            </h1>
          </div>
          
          <button 
            onClick={token ? handleLogout : () => setShowAuthModal(true)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold transition-all active:scale-95 ${
              token 
                ? 'bg-neutral-900 text-neutral-400 border border-neutral-800 hover:bg-neutral-800' 
                : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-xl shadow-indigo-600/20'
            }`}
          >
            {token ? <IconUnlock /> : <IconLock />}
            {token ? 'Log Out' : 'Sign In'}
          </button>
        </header>

        {error && !showAuthModal && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-2xl flex items-center gap-3 animate-in fade-in zoom-in duration-300">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            {error}
          </div>
        )}

        {/* Input Card */}
        <section className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-3xl blur opacity-10 group-hover:opacity-20 transition duration-1000 group-hover:duration-200" />
          <div className="relative bg-neutral-900/50 border border-neutral-800/50 backdrop-blur-xl rounded-3xl p-8 shadow-2xl">
            <h2 className="text-xl font-bold mb-6 text-neutral-200 flex items-center gap-3">
              <IconMusic /> Describe the Vibe
            </h2>
            
            <div className="relative">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Ex: 'Hardcore workout hype for heavy lifting'..."
                className="w-full h-44 bg-neutral-950/50 border border-neutral-800 rounded-2xl p-6 text-lg text-neutral-200 placeholder-neutral-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 resize-none transition-all"
                disabled={!token || loading}
              />
              {!token && (
                <div className="absolute inset-0 bg-neutral-950/60 backdrop-blur-[4px] rounded-2xl flex items-center justify-center z-20">
                  <button 
                    onClick={() => setShowAuthModal(true)}
                    className="bg-neutral-900 border border-neutral-800 px-6 py-3 rounded-full flex items-center gap-3 shadow-2xl hover:border-indigo-500/50 transition-colors cursor-pointer"
                  >
                    <IconLock />
                    <span className="font-bold text-neutral-400 hover:text-indigo-400 transition-colors">Authentication Required</span>
                  </button>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-between items-center">
              <div className="flex items-center gap-2 text-neutral-500">
                <div className={`w-2 h-2 rounded-full ${token ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-neutral-700'}`} />
                <span className="text-xs font-bold uppercase tracking-widest">{token ? 'System Ready' : 'System Offline'}</span>
              </div>
              <button
                onClick={analyzeVibe}
                disabled={!token || loading || !prompt.trim()}
                className="flex items-center gap-3 px-10 py-4 bg-indigo-600 text-white rounded-2xl font-black uppercase tracking-widest hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-2xl shadow-indigo-600/30 active:scale-95"
              >
                {loading && token ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <span>Run Algorithm</span>
                    <IconPlay />
                  </>
                )}
              </button>
            </div>
          </div>
        </section>

        {/* Dashboard */}
        {result && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
            
            <div className="bg-neutral-900/40 border border-neutral-800/50 rounded-3xl p-8 flex flex-col items-center text-center group transition-all hover:bg-neutral-800/40">
              <div className="p-4 bg-blue-500/10 rounded-2xl mb-4 text-blue-400 group-hover:scale-110 transition-transform duration-300">
                <IconActivity />
              </div>
              <p className="text-neutral-500 text-xs font-bold uppercase tracking-widest mb-2">Dominant Vibe</p>
              <h3 className="text-3xl font-black capitalize text-white">{result.dominant_vibe}</h3>
              <div className="w-full bg-neutral-800 h-2 rounded-full mt-6 overflow-hidden">
                <div 
                  className="bg-blue-500 h-full rounded-full shadow-[0_0_12px_rgba(59,130,246,0.5)]" 
                  style={{ width: `${result.confidence * 100}%` }}
                />
              </div>
              <p className="text-[10px] text-neutral-500 mt-3 font-bold uppercase tracking-widest">Confidence: {Math.round(result.confidence * 100)}%</p>
            </div>

            <div className="bg-neutral-900/40 border border-neutral-800/50 rounded-3xl p-8 flex flex-col items-center text-center group transition-all hover:bg-neutral-800/40">
              <div className="p-4 bg-emerald-500/10 rounded-2xl mb-4 text-emerald-400 group-hover:scale-110 transition-transform duration-300">
                <IconMusic />
              </div>
              <p className="text-neutral-500 text-xs font-bold uppercase tracking-widest mb-2">Target Tempo</p>
              <h3 className="text-3xl font-black text-white">{result.bpm_range} <span className="text-sm text-neutral-500">BPM</span></h3>
              <p className="text-[10px] text-neutral-500 mt-3 font-bold uppercase tracking-widest">Rhythmic Pulse</p>
            </div>

            <div className="bg-neutral-900/40 border border-neutral-800/50 rounded-3xl p-8 flex flex-col items-center text-center group transition-all hover:bg-neutral-800/40">
              <div className="p-4 bg-purple-500/10 rounded-2xl mb-4 text-purple-400 group-hover:scale-110 transition-transform duration-300">
                <IconHash />
              </div>
              <p className="text-neutral-500 text-xs font-bold uppercase tracking-widest mb-2">Genre Mapping</p>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {result.genres.map(genre => (
                  <span key={genre} className="px-3 py-1 bg-indigo-500/10 text-indigo-400 rounded-lg text-[10px] font-black border border-indigo-500/20 uppercase">
                    {genre}
                  </span>
                ))}
              </div>
            </div>

            {/* Keyword breakdown */}
            <div className="md:col-span-3 bg-neutral-900/30 border border-neutral-800/50 rounded-3xl p-8 overflow-hidden relative">
              <div className="absolute top-0 right-0 p-8 opacity-[0.02] -rotate-12 scale-[3]">
                <IconZap />
              </div>
              <p className="text-xs text-neutral-500 mb-4 font-bold uppercase tracking-[0.2em]">Neural Match Breakdown:</p>
              <div className="flex flex-wrap gap-3">
                {result.matched_keywords.length > 0 ? (
                  result.matched_keywords.map(kw => (
                    <span key={kw} className="px-4 py-2 bg-neutral-950 border border-neutral-800 text-neutral-300 rounded-xl text-xs font-bold hover:border-indigo-500/50 transition-colors">
                      #{kw}
                    </span>
                  ))
                ) : (
                  <span className="text-neutral-600 text-sm italic">Universal mood detected. Falling back to ambient processing.</span>
                )}
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
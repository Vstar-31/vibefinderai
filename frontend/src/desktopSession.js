// Credentials stay in the native app. The response event contains no token; read the
// renewed token from this origin's storage only after the matching request completes.
export function createDesktopSessionClient(host = window, send = (...args) => fetch(...args), timeoutMs = 20000) {
  let pending = null;
  let generation = 0;
  const cancelled = () => Object.assign(new Error('Session request cancelled'), { name: 'AbortError' });
  const cancel = () => {
    generation++;
    pending?.finish(null);
  };
  const renew = () => {
    if (pending) return pending.promise;
    if (!host._themed_session_renewal_supported || !host.chrome?.webview?.postMessage) return Promise.resolve(null);
    const id = host.crypto.randomUUID();
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    const finish = token => {
      host.clearTimeout(timer);
      host.removeEventListener('themed:session-renewed', receive);
      if (host._themed_session_renewal === id) host._themed_session_renewal = null;
      pending = null;
      resolve(token);
    };
    const receive = event => {
      if (event.detail?.id !== id) return;
      let token = null;
      try { if (event.detail.success) token = host.localStorage.getItem('vf_token'); } catch { /* unavailable storage */ }
      finish(token);
    };
    const timer = host.setTimeout(() => finish(null), timeoutMs);
    pending = { promise, finish };
    host._themed_session_renewal = id;
    host.addEventListener('themed:session-renewed', receive);
    try { host.chrome.webview.postMessage(JSON.stringify({ type: 'VIBEFINDER_RENEW_SESSION', requestId: id })); }
    catch { finish(null); }
    return promise;
  };
  const request = async (url, options, onRenewed) => {
    const started = generation;
    let response = await send(url, options);
    if (started !== generation) throw cancelled();
    if (response.status !== 401) return response;
    const token = await renew();
    if (started !== generation) throw cancelled();
    if (!token) return response;
    onRenewed(token);
    // Retry once, preserving the exact prompt, filters, and request body.
    response = await send(url, { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } });
    if (started !== generation) throw cancelled();
    return response;
  };
  return { request, cancel };
}

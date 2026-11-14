import { test } from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { setImmediate } from 'node:timers';
import { createDesktopSessionClient } from './desktopSession.js';

function fixture(send, timeout = 1000) {
  const host = new EventTarget();
  const messages = [];
  let token = 'expired';
  Object.assign(host, {
    _themed_session_renewal_supported: true,
    crypto: webcrypto, setTimeout, clearTimeout,
    localStorage: { getItem: () => token },
    chrome: { webview: { postMessage: message => messages.push(JSON.parse(message)) } },
  });
  const respond = (success = true, id = messages[0].requestId) => {
    if (success) token = 'renewed';
    host.dispatchEvent(new CustomEvent('themed:session-renewed', { detail: { id, success } }));
  };
  return { host, messages, respond, client: createDesktopSessionClient(host, send, timeout) };
}
const options = { method: 'POST', headers: { Authorization: 'Bearer expired', 'Content-Type': 'application/json' }, body: JSON.stringify({ text: 'rainy night drive', track_limit: 5, override_artist: null }) };
const tick = () => new Promise(resolve => setImmediate(resolve));

test('401 renews and retries exactly once with unchanged prompt and filters', async () => {
  const calls = [], tokens = [];
  const f = fixture(async (url, request) => { calls.push({ url, request }); return { status: calls.length === 1 ? 401 : 200 }; });
  const result = f.client.request('/api/vibe/analyze', options, token => tokens.push(token));
  await tick();
  assert.equal(f.messages.length, 1);
  f.respond(true, 'unrelated-id');
  assert.equal(calls.length, 1);
  f.respond();
  assert.equal((await result).status, 200);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].request.body, options.body);
  assert.equal(calls[1].request.headers.Authorization, 'Bearer renewed');
  assert.equal(options.headers.Authorization, 'Bearer expired');
  assert.deepEqual(tokens, ['renewed']);
  assert.equal(f.host._themed_session_renewal, null);
});

test('a rejected retried token does not loop', async () => {
  let calls = 0;
  const f = fixture(async () => { calls++; return { status: 401 }; });
  const result = f.client.request('/api/vibe/analyze', options, () => {});
  await tick(); f.respond();
  assert.equal((await result).status, 401);
  assert.equal(calls, 2);
  assert.equal(f.messages.length, 1);
});

test('concurrent failures share one native renewal', async () => {
  const f = fixture(async (_, request) => ({ status: request.headers.Authorization === 'Bearer renewed' ? 200 : 401 }));
  const results = [f.client.request('/one', options, () => {}), f.client.request('/two', options, () => {})];
  await tick(); assert.equal(f.messages.length, 1); f.respond();
  assert.deepEqual((await Promise.all(results)).map(r => r.status), [200, 200]);
});

test('Sign Out cancels renewal and ignores late completion', async () => {
  let calls = 0, updates = 0;
  const f = fixture(async () => { calls++; return { status: 401 }; });
  const result = f.client.request('/api/vibe/analyze', options, () => updates++);
  const rejected = assert.rejects(result, /cancelled/);
  await tick(); f.client.cancel(); f.respond(); await rejected;
  assert.equal(calls, 1); assert.equal(updates, 0);
  assert.equal(f.host._themed_session_renewal, null);
});

test('an unresponsive host times out without losing the request or retrying', async () => {
  let calls = 0;
  const f = fixture(async () => { calls++; return { status: 401 }; }, 10);
  assert.equal((await f.client.request('/api/vibe/analyze', options, () => {})).status, 401);
  assert.equal(calls, 1); assert.equal(f.host._themed_session_renewal, null);
});

test('renewal rejection and standalone mode return the original 401', async () => {
  const f = fixture(async () => ({ status: 401 }));
  const result = f.client.request('/api/vibe/analyze', options, () => assert.fail('must not update token'));
  await tick(); f.respond(false); assert.equal((await result).status, 401);
  delete f.host.chrome;
  assert.equal((await f.client.request('/api/vibe/analyze', options, () => {})).status, 401);
  assert.equal(f.messages.length, 1);
});

test('successful responses never request native credentials', async () => {
  const f = fixture(async () => ({ status: 200 }));
  assert.equal((await f.client.request('/api/vibe/analyze', options, () => {})).status, 200);
  assert.equal(f.messages.length, 0);
});

test('an older desktop without renewal support returns immediately', async () => {
  const f = fixture(async () => ({ status: 401 }));
  delete f.host._themed_session_renewal_supported;
  assert.equal((await f.client.request('/api/vibe/analyze', options, () => {})).status, 401);
  assert.equal(f.messages.length, 0);
});

test('signing out before the first response prevents a renewal request', async () => {
  let complete;
  const f = fixture(() => new Promise(resolve => { complete = resolve; }));
  const request = f.client.request('/api/vibe/analyze', options, () => assert.fail('must not restore session'));
  const rejected = assert.rejects(request, /cancelled/);
  f.client.cancel(); complete({ status: 401 }); await rejected;
  assert.equal(f.messages.length, 0);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act, useLayoutEffect } from 'react';
import { create } from 'react-test-renderer';
import MusicPlayer from './MusicPlayer.jsx';
import PlaylistPanel from './PlaylistPanel.jsx';
import ThemedAIHostBridge from './ThemedAIHostBridge.jsx';
import { useHostPrompt } from './useHostPrompt.js';
import { useLibraryCollection } from './useLibraryCollection.js';

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const response = data => ({ ok: true, status: 200, json: async () => data });
const api = path => `https://example.test${path}`;
const tick = () => new Promise(r => setTimeout(r, 0));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test('host reconnect cannot replace typed text or run the saved prompt; explicit apply can', async () => {
  let prompt;
  function Harness() { const value = useHostPrompt(); useLayoutEffect(() => { prompt = value; }); return null; }
  let view;
  try {
    await act(() => { view = create(React.createElement(Harness)); });
    await act(() => prompt.applyHostPrompt('$theme'));
    await act(() => prompt.setPrompt('rainy night drive'));
    await act(() => assert.equal(prompt.applyHostPrompt('$theme'), false));
    assert.equal(prompt.prompt, 'rainy night drive');
    assert.equal(prompt.canRunHostAnalysis(false), false);
    await act(() => prompt.applyHostPrompt('explicit saved setting', true));
    assert.equal(prompt.prompt, 'explicit saved setting');
    assert.equal(prompt.canRunHostAnalysis(false), true);
  } finally { if (view) await act(() => view.unmount()); }
});

test('auxiliary bridge forwards profiles without a second command handler, timer or DOM observer', async () => {
  const saved = globalThis.window;
  const events = new Map(), posted = [];
  globalThis.window = {
    addEventListener: (name, fn) => events.set(name, fn),
    removeEventListener: name => events.delete(name),
    chrome: { webview: { postMessage: text => posted.push(JSON.parse(text)),
      addEventListener: () => assert.fail('duplicate desktop command listener') } },
    setInterval: () => assert.fail('DOM polling must not run'),
  };
  let view;
  try {
    await act(() => { view = create(React.createElement(ThemedAIHostBridge)); });
    assert.deepEqual(posted, []);
    events.get('vibefinder:profile')({ detail: { likes: ['calm'] } });
    assert.equal(posted.length, 1);
    assert.equal(posted[0].type, 'VIBEFINDER_PROFILE');
    await act(() => view.unmount()); view = null;
    assert.equal(events.size, 0);
  } finally { if (view) await act(() => view.unmount()); globalThis.window = saved; }
});

test('selecting a still-prefetching track awaits its video and sends the session header', async () => {
  const savedWindow = globalThis.window, savedFetch = globalThis.fetch;
  const pending = deferred(), started = deferred();
  const iframe = { src: 'about:blank', contentWindow: { postMessage() {} } };
  let calls = 0;
  globalThis.window = { location: { origin: 'https://example.test' }, addEventListener() {}, removeEventListener() {} };
  globalThis.fetch = async (url, options) => {
    assert.equal(options.headers.Authorization, 'Bearer test-session');
    if (url.includes('Prefetched')) { calls++; started.resolve(); return pending.promise; }
    return response({ found: true, video_id: 'first-video' });
  };
  let view;
  try {
    await act(async () => { view = create(React.createElement(MusicPlayer, {
      tracks: [{ title: 'First race fixture', artist: 'Test' }, { title: 'Prefetched race fixture', artist: 'Test' }],
      token: 'test-session', buildApiUrl: api, servicesConnected: { youtube: true }, visibleServices: { youtube: true },
    }), { createNodeMock: e => e.type === 'iframe' ? iframe : {} }); });
    await act(async () => { await started.promise; });
    await act(() => view.root.findByProps({ title: 'Queue (2)' }).props.onClick());
    assert.match(JSON.stringify(view.toJSON()), /Prefetched race fixture/);
    await act(() => view.root.findByProps({ title: 'Next' }).props.onClick());
    assert.equal(iframe.src, 'about:blank');
    await act(async () => pending.resolve(response({ found: true, video_id: 'prefetched-video' })));
    assert.match(iframe.src, /embed\/prefetched-video/);
    assert.equal(calls, 1);
  } finally { if (view) await act(() => view.unmount()); globalThis.window = savedWindow; globalThis.fetch = savedFetch; }
});

test('Play retries a temporary video lookup failure instead of caching a permanent miss', async () => {
  const savedWindow = globalThis.window, savedFetch = globalThis.fetch;
  globalThis.window = { location: { origin: 'https://example.test' }, addEventListener() {}, removeEventListener() {} };
  const iframe = { src: 'about:blank', contentWindow: { postMessage() {} } };
  let calls = 0, view;
  globalThis.fetch = async () => ++calls === 1 ? { ok: false, status: 503 } : response({ found: true, video_id: 'retry-video' });
  try {
    await act(async () => { view = create(React.createElement(MusicPlayer, {
      tracks: [{ title: 'Temporary failure fixture', artist: 'Test' }], buildApiUrl: api,
      servicesConnected: { youtube: true }, visibleServices: { youtube: true },
    }), { createNodeMock: e => e.type === 'iframe' ? iframe : {} }); });
    await act(async () => view.root.findByProps({ title: 'Play full track' }).props.onClick());
    assert.equal(calls, 2);
    assert.match(iframe.src, /embed\/retry-video/);
  } finally { if (view) await act(() => view.unmount()); globalThis.window = savedWindow; globalThis.fetch = savedFetch; }
});

test('playlists render while history is pending; history failure has a retry instead of an empty state', async () => {
  const savedDocument = globalThis.document, savedFetch = globalThis.fetch;
  globalThis.document = { body: { style: {} } };
  const history = deferred(); let historyCalls = 0;
  globalThis.fetch = async url => {
    if (url.includes('/playlist/list')) return response({ playlists: [{ id: 'p1', name: 'Saved fixture', track_count: 0, tracks: [], created_at: '2026-11-08' }] });
    if (url.includes('/user/history')) return ++historyCalls === 1 ? history.promise : response({ history: [] });
    return response({});
  };
  let view;
  try {
    await act(async () => { view = create(React.createElement(PlaylistPanel, { token: 'session', buildApiUrl: api })); });
    assert.match(JSON.stringify(view.toJSON()), /Saved fixture/);
    await act(async () => history.resolve({ ok: false, status: 503 }));
    const historyTab = view.root.findAllByType('button').find(b => b.props.children.includes?.('History'));
    await act(() => historyTab.props.onClick());
    assert.match(JSON.stringify(view.toJSON()), /HTTP 503/);
    assert.doesNotMatch(JSON.stringify(view.toJSON()), /No analysis history yet/);
    await act(async () => view.root.findAllByType('button').find(b => b.props.children[0] === 'Retry ').props.onClick());
    assert.match(JSON.stringify(view.toJSON()), /No analysis history yet/);
    assert.equal(historyCalls, 2);
  } finally { if (view) await act(() => view.unmount()); globalThis.document = savedDocument; globalThis.fetch = savedFetch; }
});

test('late library response from the old account cannot replace the new account', async () => {
  const savedFetch = globalThis.fetch, old = deferred(); let state, view;
  globalThis.fetch = async (_, options) => options.headers.Authorization === 'Bearer old' ? old.promise : response({ history: [{ id: 'new' }] });
  function Harness({ token }) { const value = useLibraryCollection(api('/history'), token, 'history', 'history'); useLayoutEffect(() => { state = value; }); return null; }
  try {
    await act(async () => { view = create(React.createElement(Harness, { token: 'old' })); });
    await act(async () => view.update(React.createElement(Harness, { token: 'new' })));
    await act(async () => { old.resolve(response({ history: [{ id: 'old' }] })); await tick(); });
    assert.deepEqual(state.items, [{ id: 'new' }]);
  } finally { if (view) await act(() => view.unmount()); globalThis.fetch = savedFetch; }
});


test('preview audio stops on a track without a preview and recreates after provider changes', async () => {
  const savedWindow = globalThis.window, savedAudio = globalThis.Audio, savedFetch = globalThis.fetch;
  globalThis.window = { location: { origin: 'https://example.test' }, addEventListener() {}, removeEventListener() {} };
  const instances = [];
  class FakeAudio {
    constructor() { this.events = new Map(); this.src = ''; this.paused = true; instances.push(this); }
    addEventListener(name, fn) { this.events.set(name, fn); }
    play() { this.paused = false; this.events.get('play')?.(); return Promise.resolve(); }
    pause() { this.paused = true; this.events.get('pause')?.(); }
  }
  globalThis.Audio = FakeAudio;
  globalThis.fetch = async () => response({ found: true, video_id: 'provider-switch' });
  const tracks = [{ title: 'Audio fixture', artist: 'Test', preview_url: 'https://example.test/clip.mp3' }, { title: 'No preview fixture', artist: 'Test' }];
  const props = { tracks, buildApiUrl: api, visibleServices: { youtube: true } };
  const iframe = { src: 'about:blank', contentWindow: { postMessage() {} } };
  let view;
  try {
    await act(async () => { view = create(React.createElement(MusicPlayer, props), { createNodeMock: e => e.type === 'iframe' ? iframe : {} }); });
    assert.equal(instances[0].paused, false);
    assert.ok(view.root.findByProps({ title: 'Pause' }));
    await act(() => view.root.findByProps({ title: 'Next' }).props.onClick());
    assert.equal(instances[0].paused, true);
    assert.equal(instances[0].src, '');
    await act(async () => view.update(React.createElement(MusicPlayer, { ...props, servicesConnected: { youtube: true } })));
    await act(async () => view.update(React.createElement(MusicPlayer, props)));
    assert.equal(instances.length, 2);
    await act(async () => view.root.findByProps({ title: 'Previous' }).props.onClick());
    assert.equal(instances[1].paused, false);
  } finally { if (view) await act(() => view.unmount()); globalThis.window = savedWindow; globalThis.Audio = savedAudio; globalThis.fetch = savedFetch; }
});

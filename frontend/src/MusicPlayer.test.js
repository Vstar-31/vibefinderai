import { test } from 'node:test';
import assert from 'node:assert/strict';
import React, { act } from 'react';
import { create } from 'react-test-renderer';
import MusicPlayer from './MusicPlayer.jsx';

test('YouTube snapshots drive pause/resume UI, commands and desktop state', async () => {
  const listeners = new Map();
  const commands = [];
  const hostStates = [];
  const playerWindow = { postMessage: data => commands.push(JSON.parse(data)) };
  const iframe = { src: 'about:blank', contentWindow: playerWindow };
  const savedWindow = globalThis.window;
  const savedFetch = globalThis.fetch;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.window = {
    location: { origin: 'https://test.example' },
    addEventListener: (name, callback) => listeners.set(name, callback),
    removeEventListener: name => listeners.delete(name),
    chrome: { webview: { postMessage: data => hostStates.push(JSON.parse(data)) } },
  };
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ found: true, video_id: 'test-video' }) });
  let view;
  const send = async data => act(() => listeners.get('message')({
    origin: 'https://www.youtube.com', source: playerWindow, data: JSON.stringify(data),
  }));
  try {
    await act(async () => {
      view = create(React.createElement(MusicPlayer, {
        tracks: [{ title: 'Test track', artist: 'Test artist' }],
        servicesConnected: { youtube: true }, visibleServices: { youtube: true },
        buildApiUrl: path => `https://test.example${path}`,
      }), { createNodeMock: element => element.type === 'iframe' ? iframe : {} });
    });
    await send({ event: 'infoDelivery', info: { playerState: 1, currentTime: 8, duration: 62 } });
    const pause = view.root.findByProps({ title: 'Pause' });
    assert.equal(hostStates.at(-1).isPlaying, true);
    await act(() => pause.props.onClick());
    assert.equal(commands.at(-1).func, 'pauseVideo');
    await send({ event: 'infoDelivery', info: { playerState: 2, currentTime: 8 } });
    assert.equal(hostStates.at(-1).isPlaying, false);
    await act(() => view.root.findByProps({ title: 'Play full track' }).props.onClick());
    assert.equal(commands.at(-1).func, 'playVideo');
    await send({ event: 'onStateChange', info: 1 });
    assert.ok(view.root.findByProps({ title: 'Pause' }));
    await send({ event: 'infoDelivery', info: { playerState: 1, currentTime: 9 } });
    assert.equal(hostStates.at(-1).isPlaying, true);
    // An unrelated YouTube iframe must not pause this player.
    await act(() => listeners.get('message')({ origin: 'https://www.youtube.com', source: {}, data: { event: 'onStateChange', info: 2 } }));
    assert.ok(view.root.findByProps({ title: 'Pause' }));
    await send({ event: 'onError', info: 150 });
    assert.ok(view.root.findByProps({ title: 'Play full track' }));
  } finally {
    if (view) await act(() => view.unmount());
    globalThis.window = savedWindow;
    globalThis.fetch = savedFetch;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readYouTubeMessage } from './youtubeMessages.js';

const player = {};
const message = data => ({ origin: 'https://www.youtube.com', source: player, data });

test('playing and paused snapshots supply transport state without state-change events', () => {
  for (const event of ['initialDelivery', 'infoDelivery']) {
    for (const playerState of [1, 2, 0, 3, 5, -1]) {
      const result = readYouTubeMessage(message(JSON.stringify({ event, info: { playerState, currentTime: 8 } })), player);
      assert.equal(result.state, playerState);
      assert.equal(result.info.currentTime, 8);
    }
  }
});

test('explicit state changes use the same state representation as snapshots', () => {
  assert.equal(readYouTubeMessage(message({ event: 'onStateChange', info: 1 }), player).state, 1);
  assert.equal(readYouTubeMessage(message({ event: 'onStateChange', info: 2 }), player).state, 2);
});

test('progress alone does not imply playing, including a paused seek', () => {
  const result = readYouTubeMessage(message({ event: 'infoDelivery', info: { currentTime: 15 } }), player);
  assert.equal(result.state, undefined);
  assert.equal(result.info.currentTime, 15);
});

test('rejects other frames, other origins and malformed messages', () => {
  const valid = message({ event: 'onStateChange', info: 1 });
  assert.equal(readYouTubeMessage({ ...valid, source: {} }, player), null);
  assert.equal(readYouTubeMessage({ ...valid, origin: 'https://example.com' }, player), null);
  assert.equal(readYouTubeMessage(valid, null), null);
  for (const data of ['{', null, 42]) assert.equal(readYouTubeMessage(message(data), player), null);
  assert.equal(readYouTubeMessage(message({ event: 'infoDelivery', info: { playerState: '1' } }), player).state, undefined);
});

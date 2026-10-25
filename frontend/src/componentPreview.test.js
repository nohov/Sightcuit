import test from 'node:test';
import assert from 'node:assert/strict';
import { detectedPreview } from './componentPreview.js';
const track = {track_id: 7, component_preview: {model_id: 'resistor', observed_label: 'resistor', illustrative: true}};
test('live relay component selects its reference without claiming a value', () => {
  assert.deepEqual(detectedPreview({tracks: [track]}, true, true), {...track.component_preview, track_id: 7});
});
test('stale, paused, unsupported, missing and ambiguous observations cannot select a model', () => {
  assert.equal(detectedPreview({tracks: [track]}, false, true), null);
  assert.equal(detectedPreview({tracks: [track]}, true, false), null);
  assert.equal(detectedPreview({tracks: [track, {...track, track_id: 8}]}, true, true), null);
  assert.equal(detectedPreview({tracks: [{gemini_label: 'resistor'}]}, true, true), null);
  assert.equal(detectedPreview({tracks: [{component_preview: {model_id: 'phone'}}]}, true, true), null);
  assert.equal(detectedPreview(null, true, true), null);
});

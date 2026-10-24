// Detection feed. Each message is one frame shaped like the JSONL records
// written by recognition/live_runner.py:
//
// {
//   "frame_index": 412,
//   "timestamp": 1792850000.12,
//   "tracks": [
//     { "track_id": 3,
//       "proposal": { "box_xyxy_pixels": [x1, y1, x2, y2], "confidence": 0.62 },
//       "gemini_label": "phone",
//       "label_source": "gemini" | "track_cache" | null }
//   ]
// }
//
// Set VITE_FEED_URL (e.g. ws://localhost:8765) to read real frames from a
// WebSocket. The backend does not serve one yet; until it does, the mock
// feed below cycles through every device so each screen can be tested.

import { DEVICE_IDS } from "./devices.js";

export const FRAME_WIDTH = 1280;
export const FRAME_HEIGHT = 720;

export function subscribe(onFrame) {
  const url = import.meta.env?.VITE_FEED_URL;
  return url ? subscribeWebSocket(url, onFrame) : subscribeMock(onFrame);
}

function subscribeWebSocket(url, onFrame) {
  let socket;
  let closed = false;
  let retry;

  const open = () => {
    socket = new WebSocket(url);
    socket.onmessage = (event) => {
      try {
        onFrame(JSON.parse(event.data));
      } catch {
        // Ignore malformed frames rather than crash the dashboard.
      }
    };
    socket.onclose = () => {
      if (!closed) retry = setTimeout(open, 2000);
    };
  };
  open();

  return () => {
    closed = true;
    clearTimeout(retry);
    socket?.close();
  };
}

function subscribeMock(onFrame) {
  const FRAMES_PER_DEVICE = 40; // 40 frames at 4 fps = 10 s per device
  let frame = 0;

  const tick = () => {
    const deviceIndex = Math.floor(frame / FRAMES_PER_DEVICE) % DEVICE_IDS.length;
    const label = DEVICE_IDS[deviceIndex];
    const local = frame % FRAMES_PER_DEVICE;
    const drift = Math.sin(frame / 6) * 18;
    const w = 360;
    const h = 260;
    const x1 = FRAME_WIDTH / 2 - w / 2 + drift;
    const y1 = FRAME_HEIGHT / 2 - h / 2 + drift / 2;

    onFrame({
      frame_index: frame,
      timestamp: Date.now() / 1000,
      tracks: [
        {
          track_id: deviceIndex + 1,
          proposal: {
            box_xyxy_pixels: [x1, y1, x1 + w, y1 + h],
            confidence: 0.55 + 0.1 * Math.sin(frame / 4),
          },
          // The first frames of a new track are unlabelled while Gemini is called.
          gemini_label: local < 3 ? null : label,
          label_source: local < 3 ? null : local === 3 ? "gemini" : "track_cache",
        },
      ],
    });
    frame += 1;
  };

  tick();
  const id = setInterval(tick, 250);
  return () => clearInterval(id);
}

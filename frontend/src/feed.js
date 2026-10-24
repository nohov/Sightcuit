// Detection feed and live video.
//
// Each detection message is one frame shaped like this (built by
// dashboard_record() in recognition/live_runner.py):
//
// {
//   "frame_index": 412,
//   "timestamp": 1792850000.12,
//   "image_size_hw_pixels": [720, 1280],
//   "tracks": [
//     { "track_id": 3,
//       "proposal": { "box_xyxy_pixels": [x1, y1, x2, y2], "confidence": 0.62 },
//       "gemini_label": "phone",              // null while Gemini is still labelling, "none" if not a device
//       "name": "Apple iPhone",               // Gemini's free-text brand/type, null while pending or "none"
//       "description": "...",                 // 2-3 sentences from recognition/narrator.py, null until written
//       "label_source": "gemini" | "track_cache" | null }
//   ]
// }
//
// Live mode reads the glasses relay started with
//   python -m recognition.live_runner ... --listen 0.0.0.0:8765
// which serves the video at /stream.mjpg and detections at /events.
// The relay URL and token come from, in order: the page URL
// (?relay=http://localhost:8765&token=...), the last values saved in this
// browser, or VITE_RELAY_URL / VITE_RELAY_TOKEN. With none set, a mock feed
// cycles through every device so each screen can be tested.

import { DEVICE_IDS } from "./devices.js";

export const DEFAULT_SIZE_HW = [720, 1280];
const STORAGE_KEY = "scavscrap.relay";

function readStored() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveRelay(relay) {
  try {
    if (relay) localStorage.setItem(STORAGE_KEY, JSON.stringify(relay));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be unavailable (private windows); the relay still works for this visit.
  }
}

// Returns { url, token } or null for mock mode.
export function initialRelay() {
  const params = new URLSearchParams(window.location.search);
  const url = params.get("relay");
  const token = params.get("token");
  if (url && token) {
    const relay = { url: url.replace(/\/+$/, ""), token };
    saveRelay(relay);
    // Keep the token out of the address bar and browser history.
    window.history.replaceState(null, "", window.location.pathname);
    return relay;
  }
  const stored = readStored();
  if (stored?.url && stored?.token) return stored;
  const env = import.meta.env || {};
  if (env.VITE_RELAY_URL && env.VITE_RELAY_TOKEN) {
    return { url: env.VITE_RELAY_URL.replace(/\/+$/, ""), token: env.VITE_RELAY_TOKEN };
  }
  return null;
}

export function videoUrl(relay) {
  return relay ? `${relay.url}/stream.mjpg?token=${encodeURIComponent(relay.token)}` : null;
}

// onStatus receives "mock" | "connecting" | "live" | "error".
export function subscribe(relay, onFrame, onStatus) {
  return relay ? subscribeRelay(relay, onFrame, onStatus) : subscribeMock(onFrame, onStatus);
}

function subscribeRelay(relay, onFrame, onStatus) {
  onStatus("connecting");
  const source = new EventSource(`${relay.url}/events?token=${encodeURIComponent(relay.token)}`);
  source.onopen = () => onStatus("live");
  source.onmessage = (event) => {
    try {
      onFrame(JSON.parse(event.data));
      onStatus("live");
    } catch {
      // Ignore a malformed record rather than crash the dashboard.
    }
  };
  // EventSource reconnects by itself; report the gap meanwhile.
  source.onerror = () => onStatus("error");
  return () => source.close();
}

function subscribeMock(onFrame, onStatus) {
  onStatus("mock");
  const [height, width] = DEFAULT_SIZE_HW;
  const FRAMES_PER_DEVICE = 40; // 40 frames at 4 fps = 10 s per device
  let frame = 0;

  const tick = () => {
    const deviceIndex = Math.floor(frame / FRAMES_PER_DEVICE) % DEVICE_IDS.length;
    const label = DEVICE_IDS[deviceIndex];
    const local = frame % FRAMES_PER_DEVICE;
    const drift = Math.sin(frame / 6) * 18;
    const w = 360;
    const h = 260;
    const x1 = width / 2 - w / 2 + drift;
    const y1 = height / 2 - h / 2 + drift / 2;

    onFrame({
      frame_index: frame,
      timestamp: Date.now() / 1000,
      image_size_hw_pixels: [height, width],
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

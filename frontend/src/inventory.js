// Inventory: the user's parts and projects, kept in this browser.
//
// Parts: the LED kit from DESIGN.md. A part counts as "seen" only when a fresh
// live relay event carries a supported `component_preview.model_id` for it
// (the same signal the lesson's model circle uses). The first sighting also
// saves a small snapshot cropped from the glasses video. Nothing is guessed
// from the lesson step or the detector's free-text name.
//
// Projects: a project marks itself complete the first time the lesson reaches
// its final step and stays complete (with the time) even if the user steps
// back. It records lesson progress, not a wiring check.
//
// Everything survives reloads (localStorage) until removed or reset.

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "scavscrap.inventory.v2";
const PART_THUMB_SIDE = 220; // px, cropped part snapshots
const SAVE_DELAY_MS = 800;

const asset = (file) => `${import.meta.env.BASE_URL}electronics/vendor/${file}`;

// Keys match the model ids in componentPreview.js. USB has no detector class,
// so it is never marked as seen.
export const KIT = [
  {
    id: "uno",
    name: "Arduino UNO R3",
    qty: 1,
    art: asset("arduino_Uno_Rev3_breadboard.svg"),
    what: "Supplies 5 volts to the circuit from its 5V and GND pins while USB is plugged in.",
  },
  {
    id: "breadboard",
    name: "Breadboard",
    qty: 1,
    art: asset("breadboard.svg"),
    what: "Holds parts and connects them without solder. Holes in the same short row are joined underneath.",
  },
  {
    id: "resistor",
    name: "330 Ω resistor",
    qty: 1,
    art: asset("resistor_330.svg"),
    what: "Limits the current so the LED doesn't burn out. Works either way round.",
  },
  {
    id: "led",
    name: "Red LED",
    qty: 1,
    art: asset("LED-5mm-red-leg.svg"),
    what: "Lights up when current flows the right way: long leg (+) toward 5V, short leg (−) toward GND.",
  },
  {
    id: "jumper",
    name: "Jumper wire",
    qty: 2,
    art: null,
    what: "Carries power between the Arduino and the breadboard. Colour doesn't change how it works.",
  },
  {
    id: "usb",
    name: "USB cable",
    qty: 1,
    art: null,
    what: "Powers the Arduino. Plugging it in last is what turns the circuit on.",
    notDetected: true,
  },
];

export const KIT_IDS = new Set(KIT.map((p) => p.id));

const empty = () => ({ parts: {} });

function load() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (data && typeof data.parts === "object") return { parts: data.parts };
  } catch {
    // Unreadable storage: start empty.
  }
  return empty();
}

function save(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Storage full or blocked: the inventory still works for this visit.
  }
}

// Draws (part of) the current video frame to a small JPEG. Null when there is
// no video or the browser can't read it (e.g. the relay sent no CORS header).
function grab(img, box, frameW, frameH, maxSide) {
  if (!img || !img.naturalWidth) return null;
  try {
    const sx = img.naturalWidth / frameW;
    const sy = img.naturalHeight / frameH;
    const [x1, y1, x2, y2] = box || [0, 0, frameW, frameH];
    const w = Math.max(1, (x2 - x1) * sx);
    const h = Math.max(1, (y2 - y1) * sy);
    const scale = Math.min(1, maxSide / Math.max(w, h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    canvas.getContext("2d").drawImage(img, x1 * sx, y1 * sy, w, h, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.8);
  } catch {
    return null;
  }
}

export function useInventory() {
  const [data, setData] = useState(load);
  const countedTracks = useRef(new Map()); // part id -> track ids already counted this visit

  useEffect(() => {
    const id = setTimeout(() => save(data), SAVE_DELAY_MS);
    return () => clearTimeout(id);
  }, [data]);

  // Call on every relay frame. `live` must be false for stale or paused feeds.
  const recordFrame = useCallback((frame, sizeHW, img, live) => {
    if (!live || !frame?.tracks?.length) return;
    const [frameH, frameW] = sizeHW;
    const now = Date.now();
    setData((prev) => {
      let parts = prev.parts;
      for (const track of frame.tracks) {
        const id = track.component_preview?.model_id;
        if (!KIT_IDS.has(id)) continue;
        const ids = countedTracks.current.get(id) || new Set();
        const newSighting = !ids.has(track.track_id);
        ids.add(track.track_id);
        countedTracks.current.set(id, ids);

        const old = parts[id];
        const thumb = old?.thumb || grab(img, track.proposal?.box_xyxy_pixels, frameW, frameH, PART_THUMB_SIDE);
        // Skip unless something changed; lastSeen refreshes at most every 5 s.
        if (old && !newSighting && thumb === old.thumb && now - old.lastSeen < 5000) continue;
        if (parts === prev.parts) parts = { ...prev.parts };
        parts[id] = {
          firstSeen: old?.firstSeen ?? now,
          lastSeen: now,
          sightings: (old?.sightings ?? 0) + (newSighting ? 1 : 0),
          thumb,
        };
      }
      return parts === prev.parts ? prev : { ...prev, parts };
    });
  }, []);

  const forgetPart = useCallback((id) => {
    countedTracks.current.delete(id);
    setData((prev) => {
      const { [id]: _gone, ...parts } = prev.parts;
      return { ...prev, parts };
    });
  }, []);

  return { parts: data.parts, recordFrame, forgetPart };
}

// ---------- projects ----------

const PROJECTS_KEY = "scavscrap.projects.v1";

function loadProjects() {
  try {
    const data = JSON.parse(localStorage.getItem(PROJECTS_KEY) || "{}");
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

function saveProjects(data) {
  try {
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(data));
  } catch {
    // Storage blocked: completion still shows for this visit.
  }
}

// completed: { [projectId]: completedAt ms }
export function useProjects(projectId, stepIndex, stepCount) {
  const [completed, setCompleted] = useState(loadProjects);

  useEffect(() => saveProjects(completed), [completed]);

  useEffect(() => {
    if (stepIndex !== stepCount - 1) return;
    setCompleted((prev) => (prev[projectId] ? prev : { ...prev, [projectId]: Date.now() }));
  }, [projectId, stepIndex, stepCount]);

  const reset = useCallback((id) => {
    setCompleted((prev) => {
      const { [id]: _gone, ...rest } = prev;
      return rest;
    });
  }, []);

  return { completed, reset };
}

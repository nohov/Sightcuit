// Inventory: every part the tutor has named and every project the user confirmed, kept in this browser.
//
// Parts come from the tutor's "parts" list in each /events message: what the vision model named after
// "what is this?", or the value code decoded from resistor bands the user read aloud. A part counts one
// sighting each time it joins that list (again after "start over"), and its first sighting saves a
// snapshot of the glasses video at that moment. Nothing comes from a fixed kit.
//
// Projects come from the tutor's current build. One marks itself complete the first time the tutor
// reports it finished and stays complete (with the time) even if the user steps back. It records lesson
// progress, not a wiring check.
//
// Everything survives reloads (localStorage) until removed.

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "scavscrap.inventory.v3";
const PART_THUMB_SIDE = 220; // px, part snapshots
const SAVE_DELAY_MS = 800;

// Compare part names loosely, like the tutor's part_key: "220 Ohms resistor" matches "220 ohm resistor".
export const partKey = (name) =>
  (name.toLowerCase().match(/[a-z0-9]+/g) || []).map((word) => word.replace(/s$/, "")).join(" ");

function load() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (data && typeof data.parts === "object" && typeof data.projects === "object") return data;
  } catch {
    // Unreadable storage: start empty.
  }
  return { parts: {}, projects: {} };
}

function save(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Storage full or blocked: the inventory still works for this visit.
  }
}

// Draws the current video frame to a small JPEG. Null when there is no video or the browser can't
// read it (e.g. the relay sent no CORS header).
function grab(img, maxSide) {
  if (!img || !img.naturalWidth) return null;
  try {
    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.8);
  } catch {
    return null;
  }
}

export function useInventory() {
  const [data, setData] = useState(load);
  const listed = useRef(null); // part keys in the tutor's list at the last message; null before the first

  useEffect(() => {
    const id = setTimeout(() => save(data), SAVE_DELAY_MS);
    return () => clearTimeout(id);
  }, [data]);

  // Call with each message's "tutor" field (null on the mock feed or live_runner).
  const recordLesson = useCallback((lesson, img) => {
    if (!lesson) return;
    const now = Date.now();
    const names = lesson.parts || [];
    const first = listed.current === null;
    const joined = names.filter((name) => first || !listed.current.has(partKey(name)));
    listed.current = new Set(names.map(partKey));
    const project = lesson.project && lesson.steps?.length ? lesson.project : null;
    setData((prev) => {
      let { parts, projects } = prev;
      if (joined.length) {
        parts = { ...parts };
        for (const name of joined) {
          const old = parts[partKey(name)];
          if (first && old) continue; // a reload or reconnect mid-session is not a new sighting
          parts[partKey(name)] = {
            name: old?.name ?? name,
            firstSeen: old?.firstSeen ?? now,
            lastSeen: now,
            sightings: (old?.sightings ?? 0) + 1,
            thumb: old?.thumb || grab(img, PART_THUMB_SIDE),
          };
        }
      }
      if (project) {
        const old = projects[project];
        const next = {
          title: project,
          steps: lesson.steps,
          parts: (lesson.needed || []).map((item) => item.part),
          step: lesson.step_index,
          started: old?.started ?? now,
          completedAt: old?.completedAt ?? (lesson.finished ? now : null),
        };
        if (JSON.stringify(old) !== JSON.stringify(next)) projects = { ...projects, [project]: next };
      }
      return parts === prev.parts && projects === prev.projects ? prev : { parts, projects };
    });
  }, []);

  const forgetPart = useCallback((key) => {
    setData((prev) => {
      const { [key]: _gone, ...parts } = prev.parts;
      return { ...prev, parts };
    });
  }, []);

  const resetProject = useCallback((title) => {
    setData((prev) => ({ ...prev, projects: { ...prev.projects, [title]: { ...prev.projects[title], completedAt: null } } }));
  }, []);

  return { parts: data.parts, projects: data.projects, recordLesson, forgetPart, resetProject };
}

// Inventory: every device the glasses have identified, kept in this browser.
//
// One item per product (Gemini's name, or the class when there is no name).
// Each item keeps when it was first and last seen, how many separate times it
// came into view, Gemini's description once written, and a snapshot cropped
// from the glasses video the first time it was seen. Items survive page
// reloads (localStorage) until cleared.

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "scavscrap.inventory.v1";
const MAX_ITEMS = 60; // oldest are dropped beyond this, keeping storage small
const THUMB_MAX_SIDE = 200; // px; snapshots are small JPEGs
const SAVE_DELAY_MS = 1000;

function load() {
  try {
    const items = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

function save(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Storage full or unavailable: the inventory still works for this visit.
  }
}

// Crop a track's box out of the current video frame. Null when there is no
// video (mock feed) or the browser refuses to read the image.
function snapshot(img, box, frameW, frameH) {
  if (!img || !img.naturalWidth || !box) return null;
  try {
    const sx = img.naturalWidth / frameW;
    const sy = img.naturalHeight / frameH;
    const [x1, y1, x2, y2] = box;
    const w = Math.max(1, (x2 - x1) * sx);
    const h = Math.max(1, (y2 - y1) * sy);
    const scale = Math.min(1, THUMB_MAX_SIDE / Math.max(w, h));
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
  const [items, setItems] = useState(load);
  const seenTracks = useRef(new Map()); // item key -> track ids already counted this visit

  useEffect(() => {
    const id = setTimeout(() => save(items), SAVE_DELAY_MS);
    return () => clearTimeout(id);
  }, [items]);

  // Called with the devices in view on every detection frame.
  const record = useCallback((entries, sizeHW, img) => {
    if (!entries.length) return;
    const [frameH, frameW] = sizeHW;
    const now = Date.now();
    setItems((prev) => {
      let next = prev;
      let changed = false;
      for (const entry of entries) {
        const key = entry.title;
        const ids = seenTracks.current.get(key) || new Set();
        const newSighting = !ids.has(entry.key);
        ids.add(entry.key);
        seenTracks.current.set(key, ids);

        const index = next.findIndex((item) => item.key === key);
        const old = index >= 0 ? next[index] : null;
        const description = entry.track.description || old?.description || null;
        const needsThumb = !old?.thumb;
        const thumb = needsThumb ? snapshot(img, entry.track.proposal?.box_xyxy_pixels, frameW, frameH) : old.thumb;

        // Skip the update unless something visible changed (lastSeen is refreshed at most every 5 s).
        if (old && !newSighting && description === old.description && thumb === old.thumb && now - old.lastSeen < 5000) {
          continue;
        }
        const item = {
          key,
          name: entry.title,
          id: entry.id,
          firstSeen: old?.firstSeen ?? now,
          lastSeen: now,
          sightings: (old?.sightings ?? 0) + (newSighting ? 1 : 0),
          description,
          thumb,
        };
        if (!changed) next = [...next];
        changed = true;
        if (old) next[index] = item;
        else next.unshift(item);
      }
      return changed ? next.slice(0, MAX_ITEMS) : prev;
    });
  }, []);

  const clear = useCallback(() => {
    seenTracks.current = new Map();
    setItems([]);
  }, []);

  const remove = useCallback((key) => {
    seenTracks.current.delete(key);
    setItems((prev) => prev.filter((item) => item.key !== key));
  }, []);

  return { items, record, clear, remove };
}

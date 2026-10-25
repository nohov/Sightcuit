const supported = new Set(["uno", "breadboard", "led", "resistor", "jumper"]);

// No model is guessed from the current lesson, free-text name or proposal box.
export function detectedPreview(frame, live, fresh) {
  if (!live || !fresh) return null;
  const tracks = (frame?.tracks || []).filter(track => supported.has(track.component_preview?.model_id));
  if (tracks.length !== 1) return null;
  const track = tracks[0];
  return { ...track.component_preview, track_id: track.track_id };
}

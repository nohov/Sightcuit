# ScavScrap scan dashboard (frontend)

Steampunk dashboard for a device scan: the Meta glasses recording with
detection boxes, a rotating model of the detected device, its measurements,
a description panel and a metal assay chart.

## Run it

```sh
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # production build in frontend/dist
```

## Device labels

The dashboard is built for five detector labels, spelled exactly:

`laptop` · `phone` · `headphones` · `speaker` · `watch`

These are not the five classes in `labels/classes.json` on `main`
(laptop, desktop_computer_tower, monitor, printer, projector). The recognition
side needs to switch to these labels, and the YOLO weights need retraining on
them, before real detections will match. Any label the dashboard doesn't know
is shown as "Unrecognized device" instead of breaking the page.

Per-device data (dimensions, weight, metal content) lives in
`src/devices.js`. **All numbers there are placeholders** for layout work and
must be replaced with sourced values.

## Data feed

The dashboard reads frames shaped like the JSONL records that
`recognition/live_runner.py` writes: `frame_index`, `timestamp` and a
`tracks` list where each track has `track_id`,
`proposal.box_xyxy_pixels`, `proposal.confidence`, `gemini_label` and
`label_source`. It shows the most confident labelled track.

- **Default: mock feed.** `src/feed.js` cycles through all five devices,
  10 seconds each, so every screen can be tested without a model.
- **Real feed:** set `VITE_FEED_URL` to a WebSocket that sends one frame
  JSON per message, for example `VITE_FEED_URL=ws://localhost:8765 npm run dev`.
  The backend does not serve this WebSocket yet; `live_runner.py` would need a
  small sender added.

The dashboard always follows the feed: it shows whichever device the most
confident labelled track is.

## Structure

```text
src/
  App.jsx                    layout and panels
  devices.js                 per-label device data (placeholders)
  feed.js                    mock feed + WebSocket feed
  components/DeviceModels.jsx  rotating CSS 3D models, one per device
  styles.css                 theme tokens and styles
```

The 3D models use CSS 3D transforms, so there are no model files or WebGL
dependency. They can later be swapped for three.js with real `.glb` models.

The recording panel is a placeholder: no video stream is connected yet.

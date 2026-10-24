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

`laptop` · `phone` · `headphones` · `smartwatch` · `speaker`

These are the five classes in `labels/classes.json`. Any label the dashboard
doesn't know is shown as "Unrecognized device" instead of breaking the page.

Per-device data (dimensions, weight, metal content) lives in
`src/devices.js`. **All numbers there are placeholders** for layout work and
must be replaced with sourced values.

## Live glasses feed

The dashboard shows the Meta glasses video and live detection boxes from the
glasses relay (`recognition/live_runner.py --listen`, see `app/ios/README.md`).

1. Start the relay on the laptop as in `app/ios/README.md` ("Run"). Besides the
   token it prints a ready-made dashboard link:

   ```text
   relay listening on 0.0.0.0:8765; token 3f9c...
   dashboard: open http://localhost:5173/?relay=http://localhost:8765&token=3f9c...
   ```

2. Run `npm run dev` here and open that link. The token is saved in this
   browser and removed from the address bar.
3. Start streaming from the ScavRelay app. Video appears as soon as frames
   arrive; boxes follow each finished detection.

Without `SCAVSCRAP_RELAY_TOKEN` in `.env` the relay prints a new token every
run, so open the new link (or use **Relay settings** in the recording panel)
after restarting it. With a fixed token the dashboard reconnects by itself.

The relay serves two read-only endpoints, both needing `?token=`:

- `/stream.mjpg`: newest glasses frame as MJPEG (no boxes drawn)
- `/events`: Server-Sent Events, one record per finished detection:
  `frame_index`, `timestamp`, `image_size_hw_pixels` and `tracks`, each with
  `track_id`, `proposal.box_xyxy_pixels`, `proposal.confidence`,
  `gemini_label` (null while labelling, `none` for a non-target) and
  `label_source`

The dashboard shows the most confident labelled track. The confidence shown
is the box proposal's, not Gemini's (Gemini returns none).

Without a relay, a mock feed cycles through all five devices, 10 seconds
each, so every screen can be tested. `VITE_RELAY_URL` and `VITE_RELAY_TOKEN`
set a default relay at build time.

## Structure

```text
src/
  App.jsx                    layout and panels
  devices.js                 per-label device data (placeholders)
  feed.js                    relay connection (video + detections) and mock feed
  components/DeviceModels.jsx  rotating CSS 3D models, one per device
  styles.css                 theme tokens and styles
```

The 3D models use CSS 3D transforms, so there are no model files or WebGL
dependency. They can later be swapped for three.js with real `.glb` models.

# ScavScrap lesson dashboard (frontend)

Steampunk dashboard with a vertical Meta glasses recording, a five-step LED
lesson preview, and a conceptual breadboard drawing. The model circle renders
drafting-style reference artwork for a supported component observation.

The desktop layout has a compact rule for a 15-inch MacBook Pro sized browser
window (about 1440 CSS pixels wide with 800 pixels of usable height). Shorter
browser windows scroll instead of squeezing the lesson panels over each other.

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
  `gemini_label` (project class; null while labelling, `none` for a
  non-target), `name` (Gemini's product name), `description` (Gemini's
  short description once written, else null), `hint` and `label_source`

The hero shows the vertical recording feed, Steps panel, and Breadboard Setup.
The five lesson steps are based on `DESIGN.md` and use a 330 Ω resistor. Back
and Next only change the visible step; they do not verify wiring or control the
glasses. The Parts list shows which components belong to earlier, current, and
later steps in the plan; it does not confirm physical placement. The breadboard
drawing shows orientation and the series circuit path,
without assigning holes or showing a powered circuit. Exact hole placements,
connection review, and power-up procedure still need a prepared plan for the
confirmed breadboard. Keep USB disconnected during assembly. The separate
`public/electronics/` demo depicts a 220 Ω example and is not this lesson's
wiring guide.

The model circle starts in automatic mode. It selects reference artwork only
when one supported component appears in a fresh live relay event. The current
five-device detector does not recognize lesson components, so the circle waits
unless a future component-capable backend supplies that event. The artwork
does not confirm resistance, LED color, placement, or wiring.

Temporary React design studies and their source assets remain in the repository
for review, but are not rendered below the dashboard in development or
production mode.

Live detection boxes still appear on the recording feed. Their confidence is
the detector proposal's, not Gemini's (Gemini returns none).

Without a relay, the hero remains in a stable preview state. It does not cycle
through mock device labels. `VITE_RELAY_URL` and `VITE_RELAY_TOKEN` set a
default relay at build time.

## Inventory

The brass **Inventory** tab on the bottom edge opens a drawer with two tabs
(drawer design from `gurashish/inventory-v2`, fed by the tutor instead of a
fixed kit):

- **My Parts**: every part the tutor has named (`tutor.parts` in each
  `/events` message), with a snapshot from the glasses video at its first
  sighting and a count of how many times it was named.
- **My Projects**: every build the user confirmed, with its steps and parts.
  It marks itself complete the first time the tutor reports it finished and
  stays complete if the user steps back; **Reset completion** clears it. It
  records lesson progress only and does not verify wiring.

Kept in this browser (`localStorage`).

## Structure

```text
src/
  App.jsx                    dashboard layout and recording panel
  components/LessonPreview.jsx  five-step preview and breadboard concept
  components/lesson-preview.css  lesson panel styles
  devices.js                 per-label device data (placeholders)
  feed.js                    relay connection (video + detections) and mock feed
  styles.css                 theme tokens and styles
```

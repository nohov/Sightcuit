# ScavRelay: Meta glasses → laptop relay (dev-mode prototype)

ScavRelay streams the glasses camera through the Meta Wearables Device Access
Toolkit (DAT) and POSTs each frame to `recognition.live_runner --listen` on the
laptop. All recognition (YOLO-World proposals, Gemini labels, JSONL records)
runs on the laptop; the phone only relays frames and draws the returned boxes.
Boxes trail the newest frame by one inference. Relay or network failures show
as a red banner, never as detections.

Status: these sources built and launched in an iPhone 17 Pro simulator with
Xcode 26.6 and the existing DAT SDK 1.0.1 package. On 2026-10-24 a physical
iPhone 15 Plus streamed Meta glasses frames to the laptop relay, which wrote
records. If Start reports that the glasses app needs an update, ScavRelay opens
Meta AI's update screen; re-enable Developer Mode after updating.

## Requirements

- Mac with Xcode 26.4+, iPhone on iOS 17.2+, Meta AI app installed.
- Supported glasses on current firmware (Meta AI > Devices > gear icon > General
  > About > Version) with Developer Mode on: Meta AI > Settings > App Info, tap
  the app version five times, then enable Developer Mode. It can turn off after
  firmware updates.
- Free Apple ID is enough for your own phone (re-install every 7 days).

## Create the Xcode project

1. Xcode > New Project > iOS App, SwiftUI, name `ScavRelay`, save it in this folder.
2. Delete the generated `ContentView.swift`/`ScavRelayApp.swift` and add the
   files in `ScavRelay/` to the target.
3. Build Settings > Info.plist File: `ScavRelay/Info.plist`; turn off
   "Generate Info.plist File".
4. File > Add Package Dependencies: `https://github.com/facebook/meta-wearables-dat-ios`,
   add `MWDATCore`, `MWDATCamera`, `MWDATInputs`, and `MWDATMockDevice` to the target.
   For the capture button, also enable the experimental Inputs
   capability for this app in Wearables Developer Center. Without it, the stream
   still runs and the app says to use "tutor, done" instead.
5. Signing & Capabilities: pick your team. `TeamID` in `Info.plist` comes from `$(DEVELOPMENT_TEAM)`.
6. Optional, for the simulator: add a permitted local clip as `mock-feed.mp4` to the
   target. DEBUG builds then show "Use mock glasses".

## Run

On the laptop (same Wi-Fi as the phone):

```sh
set -a; . ./.env; set +a
.venv/bin/python -m recognition.live_runner \
  evaluation/glasses_predictions.jsonl \
  --weights /absolute/path/to/yolov8l-worldv2.pt \
  --allow-upload --listen 0.0.0.0:8765
```

It prints `relay listening on 0.0.0.0:8765; token ...`. The token is random
each run unless `.env` sets `SCAVSCRAP_RELAY_TOKEN` (32+ lowercase hex
characters, e.g. from `openssl rand -hex 16`); a fixed token keeps the phone and
dashboard connected across relay restarts. Find the laptop's Wi-Fi
address (`ip addr` on Linux, `ipconfig getifaddr en0` on macOS), then check the
relay before involving the phone. It should print the tracks as JSON:

```sh
curl -H "Authorization: Bearer <token>" \
  --data-binary @<a-permitted-photo>.jpg http://localhost:8765/frame
```

On the phone:

1. Select the iPhone in Xcode and press Run. On first launch, trust the
   developer certificate: Settings > General > VPN & Device Management.
2. In ScavRelay, enter `<laptop-ip>:8765` and the token.
3. Tap "Connect glasses in Meta AI" and approve the app there.
4. Tap "Start streaming", and allow local-network access when iOS asks.

Boxes appear on the phone, and new lines land in
`evaluation/glasses_predictions.jsonl`.

The laptop opens a "scavscrap relay" window showing the newest glasses frame with
the last finished boxes; press `q` in it to stop. Add `--no-display` to run headless.

To watch the stream in the dashboard instead, run `npm run dev` in `frontend/`
and open the `dashboard: open http://localhost:5173/?relay=...` link the relay
prints at startup. See `frontend/README.md`.

### Spoken descriptions

Short-press the capture button on the glasses while streaming: the phone speaks the
description of each identified item in turn, nearest (biggest box) first, using Apple's built-in voice, and the
stream keeps running. Press again while it is speaking to stop. This uses Meta's
Inputs capability, which Meta marks as beta; if it does not attach, the status line
says so. Fallback: tap the glasses once. That pauses (freezes) the stream and speaks;
tap again to stop and resume. **Speak description** in the app does the same thing.
The status line shows where the audio went: a Bluetooth port (`BluetoothA2DPOutput`)
means the glasses, `Speaker` means the phone. If it is the phone, pair the glasses
as an audio device in iOS Settings > Bluetooth. Descriptions take 10-30 s to arrive
the first time an item is seen. Taking the glasses off also pauses the stream, so
it also starts a description.

## Circuit tutor

Run the tutor on the laptop instead of `live_runner`. The app is the same and so
is the frame path; `/frame` returns no boxes.

```sh
set -a; . ./.env; set +a
.venv/bin/python -m recognition.tutor_runner evaluation/tutor_log.jsonl \
  --project projects/led_resistor.json --allow-upload
```

Enter the printed token, start streaming, then tap "Start listening".

- **Ask:** say "tutor, which resistor is this?" with the part in view. Speech is
  recognized on the iPhone, and only the words after "tutor" go to the laptop.
  The laptop sends the newest frame to the cheap model tier, and to the stronger
  tier only when the cheap answer is uncertain or its reading is not in the
  project. Replies are spoken on the phone, through the glasses when they are
  the Bluetooth audio route.
- **Step done:** a short press of the glasses capture button while the app is
  listening; when it is not, the press speaks descriptions as above. The stream
  keeps running. The laptop checks the newest frame against the current step and moves
  on only if the model confirms it. "tutor, next" skips without a check, and
  "tutor, repeat" and "tutor, back" also cost no model call.

Not yet verified on hardware: whether a short capture press also saves a photo
to the wearer's camera roll, and whether the glasses mic and speakers take over
the audio route through HFP.

## Troubleshooting

- **Stuck on `waitingForDevice`:** the glasses are out of range, Developer Mode
  is off, or the hinges are closed.
- **App stopped launching after a week:** free-account builds expire after 7
  days. Press Run in Xcode again.

## Privacy

The glasses see whatever the wearer looks at, including bystanders. Frames with
new tracks are uploaded to Google by the laptop (`--allow-upload`). Frames cross
the LAN as plain HTTP behind the token, so use a trusted home network only.
DAT analytics and crash reporting are opted out in `Info.plist`.

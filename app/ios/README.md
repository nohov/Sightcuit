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
   add `MWDATCore`, `MWDATCamera`, and `MWDATMockDevice` to the target.
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

It prints `relay listening on 0.0.0.0:8765; token ...`. Find the laptop's Wi-Fi
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

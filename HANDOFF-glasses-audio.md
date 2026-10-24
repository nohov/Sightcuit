# Handoff: spoken descriptions on the Meta glasses

For a new Claude Code session. Read this whole file before acting. Written
2026-10-24 from the session that built the live app's descriptions.

## 0. TL;DR

Goal: the wearer presses or taps the Meta Ray-Ban glasses, and a short spoken
description of the item they are looking at plays through the glasses' speakers.

```text
tap on glasses ─▶ iPhone app (ScavRelay) sees it
               ─▶ POST /describe to the laptop relay
               ◀─ {label, name, description, audio_url}
               ─▶ iPhone plays audio_url, or speaks description itself
               ─▶ sound comes out of the glasses (iPhone audio → Bluetooth)
```

Two parts, two owners:

| Part | Where | Owner | Status |
|---|---|---|---|
| A. `/describe` + `/audio` on the laptop relay | `recognition/live_runner.py`, `recognition/narrator.py` | Gursimar (models: YOLO + Gemini) | **not built** |
| B. Trigger + playback on the phone | `app/ios/ScavRelay/` | iOS/glasses teammates | **not built** |

Do part A first: part B can then be tested against a real endpoint. If you are
working on part B and `grep -n '"/describe"' recognition/live_runner.py` finds
nothing, part A is not done yet.

Ownership rule (from the repo owner): frontend and glasses code belongs to the
teammates and their behaviour wins. Do not change the detector or Gemini
behaviour from the iOS side, and do not break the relay contract the app and
dashboard already read (section 2.3).

## 1. What is verified and what is not

| Claim | Status |
|---|---|
| Laptop relay serves `/frame`, `/events`, `/stream.mjpg` with a bearer token | Verified (tests + a real POST on 2026-10-24) |
| Descriptions: Gemini writes 2-3 sentences per product family, cached on disk | Verified in the laptop camera window (iPhone, MacBook, HP laptop) |
| Descriptions are generated in `--listen` (glasses) mode | **No**: only in the laptop window today (part A fixes) |
| ElevenLabs audio | Built, **never called against the real API** |
| A one-finger tap on the glasses pauses/resumes the DAT session | Meta docs say so; the app's own comment agrees (`GlassesController.swift`, "a tap on the glasses resumes") |
| The app can tell *why* a session paused | **No** (Meta docs: state does not expose the reason) |
| Capture-button events (`.capture`) via the Inputs API | Exists in Meta docs, **beta channel only**; model support and whether the glasses still take a photo are undocumented |
| iPhone audio plays through the glasses while streaming | Expected (the glasses are a Bluetooth audio device), **not tested** during a DAT camera session |

## 2. What exists today

### 2.1 Laptop relay

`python -m recognition.live_runner <out.jsonl> --allow-upload --listen 0.0.0.0:8765`
runs the trained YOLO v2 detector (`training/weights/scavscrap_v2_best.pt`) and
Gemini on frames the phone POSTs. Key code in `recognition/live_runner.py`:

- `serve_relay()`: starts the detector thread and the HTTP server; `keep()` is
  the per-detection callback that stores `shown["tracks"]`.
- `make_relay_server()`: the `Handler` class with `do_GET` (`/stream.mjpg`,
  `/events`, token in `?token=`) and `do_POST` (`/frame`, token in the
  `Authorization: Bearer` header, compared with `hmac.compare_digest`).
- `project_label(track)` / `gemini_name(track)`: what the app and dashboard get.
- `run_with_display()`: the laptop-window mode. It owns the only `Narrator`
  today (`narrator.prepare(label)` per named box, `narrator.click(label)` on
  click). **Relay mode has no narrator.**
- Token: random per run unless `.env` sets `SCAVSCRAP_RELAY_TOKEN` (32+ lowercase
  hex). Set it so the phone keeps working across relay restarts.

### 2.2 Descriptions (`recognition/narrator.py`)

- `gemini_describe(label, model)`: text-only Gemini call (no image) with
  `recognition/prompt-describe-v1.txt`; 2-3 sentences, under 60 words, written to
  be read aloud. 3-7 s per call.
- `elevenlabs_speak(text, voice, model)`: `POST
  https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=wav_22050`,
  header `xi-api-key`, returns WAV bytes. Needs `ELEVENLABS_API_KEY`.
- `Narrator(text_dir, describe, speak=None, audio_dir=None, ...)`: one job per
  label on a 1-worker pool. Files: `cache/narration/describe-v1/<slug>.txt` and,
  with audio on, `cache/narration/describe-v1/<voice>_<model>/<slug>.wav`.
  `ready()`, `description()`, `prepare()`, `click()`, `wav()`.
  **Not thread-safe**: its docstring says prepare/click run on one thread.

### 2.3 Contract the app and dashboard already read (do not break)

- `POST /frame` reply: `{"tracks": [{"track_id", "box_xyxy_pixels", "label",
  "name"}], "image_size_hw_pixels"}`. `label` is a project class (`laptop`,
  `phone`, `headphones`, `smartwatch`, `speaker` from `labels/classes.json`) once
  Gemini confirms the item, `"none"` if not a device, `null` while pending. The
  iOS app colours a box green only when `label` is a project class
  (`ContentView.swift`, `projectClasses.contains(label)`). `name` is Gemini's
  free text ("Apple iPhone"); the app ignores it today.
- `/events`: `dashboard_record()`, same `gemini_label` rule plus `name`, `hint`.

## 3. Part A: laptop side (models owner)

### 3.1 Generate descriptions in relay mode

In `serve_relay()`, create a `Narrator` the same way `main()` does for the
window (move that construction into a small helper `make_narrator(args)` and
pass the result into both `run_with_display` and `serve_relay`). In `keep()`,
call `narrator.prepare(t["label"])` for each track where
`t["label"] not in (None, "none")`.

Thread safety: in relay mode `prepare()` runs on the detector thread and
`/describe` runs on HTTP handler threads. Add a `threading.Lock` to `Narrator`
and hold it in `prepare()` and `click()` (and any new method that reads or
writes `self.jobs`). Update the class docstring.

### 3.2 `POST /describe`

Auth: same `Authorization: Bearer <token>` check as `/frame` (copy that block,
including `hmac.compare_digest`). Body: none.

Which item: the "primary track", same rule as the dashboard's `primaryTrack`
(`frontend/src/App.jsx`): among `shown["tracks"]` whose `label` is not `None`
or `"none"`, the one with the highest `proposal["confidence"]`. When the
session is paused by a tap, no new frames arrive, so `shown["tracks"]` is still
the scene the wearer was looking at. That is the point.

Behaviour:

1. No named track: `404 {"error": "nothing identified yet"}`.
2. Description ready: `200` with
   ```json
   {"track_id": 3, "label": "phone", "name": "Apple iPhone",
    "description": "You are holding an iPhone, ...",
    "audio_url": "/audio/apple-iphone.wav"}
   ```
   `label` uses `project_label()`, `name` uses `gemini_name()`. `audio_url` is
   `null` when audio is off or the WAV is not ready.
3. Not ready yet: make sure a job exists (`prepare`), then wait on it up to 15 s
   (store the `Future` so the handler can `future.result(timeout=15)`). Still
   not ready: `503 {"error": "description not ready, try again"}`. A failed job:
   `502 {"error": "<first line of the exception>"}` and allow a retry on the
   next request (that is what `Narrator.click()` already does).

### 3.3 `GET /audio/<slug>.wav`

Auth: `Authorization: Bearer` header (the phone uses URLSession, so headers
work; do not put the token in this URL). Serve only an exact file name from
`narrator.audio_dir` that matches `^[a-z0-9-]+\.wav$`; anything else is 404, so
no path traversal. `Content-Type: audio/wav`, `Content-Length`, body = bytes.

### 3.4 Audio choice (cost)

- Free and unlimited: leave `ELEVENLABS_API_KEY` unset. `audio_url` is `null`
  and the phone speaks `description` with Apple's built-in voice (part B). Use
  this for all testing.
- Demo quality: set `ELEVENLABS_API_KEY`. The free plan is about 10,000
  characters a month, about 30 descriptions. Each product family is generated
  once and cached, so a 10-item demo costs about 3,500 characters. Do **one**
  real ElevenLabs call well before the demo; it has never been run.
- Keys go in `.env` only, never in chat, logs, commits or URLs.

### 3.5 Tests and checks

- Add tests in `recognition/tests/test_live_runner.py` next to
  `RelayServerTests` (they start a real server on a free port with a fake
  `shown` dict). Cover: 401 without token; 404 with no named track; primary
  track = highest confidence named; 200 shape with a fake narrator; 503 on
  timeout (use a never-finishing Future); `/audio` 404 for `../x.wav` and for a
  missing file; 200 with WAV bytes for an existing one.
- Add a `Narrator` lock test only if it stays simple.
- Run: `training/.venv/bin/python -m unittest discover -s recognition/tests -t .`
  and `... -s tests -t .` (66 + 2 tests passed before this work).
- Manual: start the relay with `SCAVSCRAP_RELAY_TOKEN` set, POST a permitted
  phone photo to `/frame` until the reply's `label` is `phone`, then:
  ```sh
  curl -s -X POST -H "Authorization: Bearer $SCAVSCRAP_RELAY_TOKEN" http://localhost:8765/describe
  ```
  The same-day check used `training/datasets/scavscrap/images/oi_000f78a66fd29c49.jpg`
  (a phone; Gemini named it "Apple iPhone").
- Update `RUNBOOK.md` section 5 with the two endpoints.

## 4. Part B: phone side (iOS/glasses owners)

Read `app/ios/README.md` first (build, Developer Mode, relay setup). The app is
`ScavRelay`, DAT SDK **1.0.1** (stable channel), modules `MWDATCore`,
`MWDATCamera`, `MWDATMockDevice`.

### 4.1 Prove audio reaches the glasses (do this first, ~10 min)

Before any trigger work, check that phone audio plays through the glasses
**while the DAT camera stream is running**:

```swift
import AVFoundation

// Keep a strong reference (e.g. a property on GlassesController);
// a local synthesizer is deallocated mid-sentence.
let speech = AVSpeechSynthesizer()

func speak(_ text: String) {
  let audio = AVAudioSession.sharedInstance()
  try? audio.setCategory(.playback, mode: .spokenAudio)
  try? audio.setActive(true)
  speech.speak(AVSpeechUtterance(string: text))
}
```

Call `speak("Testing the glasses speakers")` from a temporary button while
streaming. Expected: the voice comes from the glasses. Also check
`AVAudioSession.sharedInstance().currentRoute.outputs` (port type should be
Bluetooth A2DP or HFP, not the built-in speaker). If it plays from the phone,
pair the glasses as an audio device in iOS Settings > Bluetooth and retry.
Use `.playback`, not `.playAndRecord`: recording forces the low-quality
hands-free (HFP) profile.

### 4.2 Trigger option 1: tap on the glasses (works on SDK 1.0.1)

Meta's session lifecycle docs: while a session runs, "a one-finger tap pauses or
resumes the device session"; "tap and hold stops" it. The app already observes
the camera stream state in `GlassesController.observe(_:)`
(`stream.statePublisher.listen`). Use **that** stream state, not
`DeviceSession`'s state: Meta's known-issues page says `DeviceStateSession`
is unreliable together with a camera stream session.

Steps:

1. Log `String(describing: state)` on every transition, tap the glasses, and
   note the exact paused/resumed case names in SDK 1.0.1 (do not guess them).
2. On the transition *into* paused: call `/describe` (4.4) and play (4.5).
3. On resume: stop playback (`speech.stopSpeaking(at: .immediate)` /
   `player.stop()`).
4. Debounce: ignore a second pause within ~2 s.

Caveat: the app cannot tell a tap from other pauses (taking the glasses off,
closing the hinges). Those will also start a description. Acceptable for a
demo; option 2 fixes it.

### 4.3 Trigger option 2: capture button via Inputs (beta)

Meta's Inputs capability delivers decoded events, including the capture button
(`.capture` with short press / hold / double press) and touchpad `.select` /
`.nav`. Facts from https://wearables.developer.meta.com/docs/develop/dat/inputs/ :

- Beta: "available in the development and beta release channels only"; the API
  may change. The app is on the stable 1.0.1 package, so this means switching
  the package to the beta channel.
- iOS: `import MWDATInputs`; `session.addInputs(configuration:
  InputsConfiguration(sources: [...]))`, then `for await event in
  inputs.events`; wait for the `.active` state; keep listener tokens; call
  `session.removeInputs()` on teardown. No user permission prompt.
- Not documented: which glasses models support it, and whether a capture press
  still takes a native photo/video at the same time. Test both.

Only try this after option 1 works end to end.

### 4.4 Call `/describe`

Add to `RelayClient.swift` (it already holds the host and token; `/frame` is
built in `configure(host:token:)`):

```swift
struct DescribeResult: Decodable {
  let label: String?
  let name: String?
  let description: String
  let audio_url: String?
}

func describe() async throws -> DescribeResult {
  // Same host and Bearer token as /frame. The laptop may wait up to 15 s.
  var request = URLRequest(url: baseURL.appendingPathComponent("describe"), timeoutInterval: 20)
  request.httpMethod = "POST"
  request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
  let (data, response) = try await URLSession.shared.data(for: request)
  // 404: nothing identified yet. 503: still writing, retry once.
  ...
}
```

`baseURL` is `http://<host>`; today the client only stores the `/frame` URL, so
keep the base too. Handle 404 by speaking a short local line ("Nothing
identified yet") and 503 by retrying once.

### 4.5 Play

- `audio_url` present: `GET http://<host><audio_url>` with the same
  `Authorization: Bearer` header, then `AVAudioPlayer(data:)` (keep a strong
  reference) and `play()`.
- `audio_url` null: `speak(result.description)` from 4.1 (free, unlimited).

Same audio session setup as 4.1 in both cases.

### 4.6 Fallback trigger: iPhone Action Button (no app code)

If glasses triggers misbehave before the demo: a Shortcut on an iPhone with an
Action Button: "Get Contents of URL" (`POST
http://<laptop-ip>:8765/describe`, header `Authorization: Bearer <token>`),
"Get Dictionary Value" `description`, "Speak Text". Assign it to the Action
Button. Audio goes to the glasses the same way as 4.1.

## 5. End-to-end acceptance

1. Laptop: relay running with a fixed token; `/describe` answers via curl (3.5).
2. Phone: 4.1 voice comes from the glasses while streaming.
3. Look at a phone or laptop for ~10 s (Gemini needs time to name it), tap the
   glasses once: the description plays from the glasses within a few seconds.
4. Tap again: playback stops and the stream resumes.
5. Look at something with no box, tap: "Nothing identified yet".

## 6. Gotchas

- Same Wi-Fi for phone and laptop; laptop IP from `ipconfig getifaddr en0`.
- Gemini naming takes 6-26 s (frequent HTTP 503 retries on Google's side), and
  descriptions 3-7 s more the first time per product family. Cached families
  are instant. Warm the cache before a demo by showing each demo item once.
- Do not add the microphone to the DAT session for this feature; mic capture
  is experimental and would push audio to the HFP profile.
- `cache/` and `.env` are gitignored; each machine generates its own cache.
- References: Meta Inputs docs (link above); session lifecycle
  https://wearables.developer.meta.com/docs/develop/dat/lifecycle-events/ ;
  known issues https://wearables.developer.meta.com/docs/knownissues ; SDK
  https://github.com/facebook/meta-wearables-dat-ios ; ElevenLabs TTS
  https://elevenlabs.io/docs/api-reference/text-to-speech/convert

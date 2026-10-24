# Handoff: spoken descriptions on the Meta glasses

For a new Claude Code session. Read this whole file before acting. Written
2026-10-24 against `main` at `27c9a4a` ("Use fixed per-category descriptions
for unbranded items in relay mode").

## 0. TL;DR

Goal: the wearer taps or presses the Meta Ray-Ban glasses, and a short spoken
description of the item they are looking at plays through the glasses' speakers.

The laptop already sends the description text to the phone with every frame.
So the free version is **phone-only work**:

```text
tap on glasses ─▶ ScavRelay (iPhone) sees the stream pause
               ─▶ picks the main track from its last /frame reply
               ─▶ speaks track.description with Apple's built-in voice
               ─▶ sound comes out of the glasses (iPhone audio → Bluetooth)
```

| Part | Where | Owner | Needed for |
|---|---|---|---|
| B. Trigger + playback on the phone | `app/ios/ScavRelay/` | iOS/glasses teammates | **everything** (free path) |
| A. ElevenLabs audio in relay mode | `recognition/live_runner.py` | Gursimar (models: YOLO + Gemini) | optional, better voice only |

Start with part B. Do part A only if the built-in voice is not good enough.

Ownership rule (from the repo owner): frontend and glasses code belongs to the
teammates and their behaviour wins. Do not change detector or Gemini behaviour
from the iOS side, and do not break the relay contract in section 2.

## 1. What is verified and what is not

| Claim | Status |
|---|---|
| Relay `/frame` reply carries `label`, `name`, `description` per track | Verified in code at `27c9a4a` (`recognition/live_runner.py`, `do_POST`) |
| Branded items ("Apple iPhone") get a Gemini description; unbranded ("smartphone") get a fixed per-category text | Verified in code (`describe_tracks`, `UNBRANDED_DESCRIPTIONS`) |
| ScavRelay decodes `description` | **No**: `RelayTrack` in `RelayClient.swift` has `track_id`, `box_xyxy_pixels`, `label` only |
| A one-finger tap on the glasses pauses/resumes the DAT session | Meta docs say so; the app's own comment agrees (`GlassesController.swift`, "a tap on the glasses resumes") |
| The app can tell *why* a session paused | **No** (Meta docs: state does not expose the reason) |
| Capture-button events (`.capture`) via the Inputs API | In Meta docs, **beta channel only**; model support and whether the glasses still take a photo are undocumented |
| iPhone audio plays through the glasses while streaming | Expected (the glasses are a Bluetooth audio device), **not tested** during a DAT camera session |
| ElevenLabs audio | Built for the laptop window, **off in relay mode**, never called against the real API |

## 2. The relay contract today (do not break)

`python -m recognition.live_runner <out.jsonl> --allow-upload --listen 0.0.0.0:8765`
runs the trained YOLO v2 detector and Gemini on frames the phone POSTs. Set
`SCAVSCRAP_RELAY_TOKEN` in `.env` (32+ lowercase hex, `openssl rand -hex 16`) so
the token survives relay restarts.

`POST /frame` (header `Authorization: Bearer <token>`, body JPEG) replies:

```json
{"tracks": [{"track_id": 3,
             "box_xyxy_pixels": [x1, y1, x2, y2],
             "label": "phone",
             "name": "Apple iPhone",
             "description": "You are holding an iPhone, ..."}],
 "image_size_hw_pixels": [896, 504]}
```

- `label`: a project class (`laptop`, `phone`, `headphones`, `smartwatch`,
  `speaker`) once Gemini confirms the item; `"none"` if not a device; `null`
  while pending; Gemini's name for detector classes outside the five. The app
  colours a box green only when `label` is a project class.
- `name`: Gemini's free-text name, or `null`.
- `description`: `null` until written (first time per product family: Gemini
  naming 6-26 s, then description 3-7 s; cached families are instant). Unbranded
  names get a fixed text at once. Tracks without a name have `null`.
- Boxes trail the newest frame by one inference.

## 3. Part B: phone side (iOS/glasses owners)

Read `app/ios/README.md` first (build, Developer Mode, relay setup). App:
`ScavRelay`, DAT SDK **1.0.1** (stable channel), modules `MWDATCore`,
`MWDATCamera`, `MWDATMockDevice`.

### 3.1 Prove audio reaches the glasses (do this first, ~10 min)

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
  speech.stopSpeaking(at: .immediate)
  speech.speak(AVSpeechUtterance(string: text))
}
```

Call `speak("Testing the glasses speakers")` from a temporary button while
streaming. Expected: the voice comes from the glasses. Check
`AVAudioSession.sharedInstance().currentRoute.outputs`: the port type should be
Bluetooth (A2DP or HFP), not the built-in speaker. If it plays from the phone,
pair the glasses as an audio device in iOS Settings > Bluetooth and retry.
Use `.playback`, not `.playAndRecord`: recording forces the low-quality
hands-free (HFP) profile.

### 3.2 Decode the description

In `RelayClient.swift`, add the two optional fields to `RelayTrack` (the
laptop already sends them; `Decodable` ignored them until now):

```swift
struct RelayTrack: Decodable, Identifiable {
  let track_id: Int
  let box_xyxy_pixels: [Double]
  let label: String?
  let name: String?
  let description: String?
  var id: Int { track_id }
}
```

`GlassesController.result` already holds the last `RelayResult`.

### 3.3 Pick the item to describe

The reply has no confidence, so use the biggest box that has a description
(the item the wearer is closest to or looking at):

```swift
func mainTrack(_ result: RelayResult?) -> RelayTrack? {
  result?.tracks
    .filter { $0.description != nil }
    .max { area($0.box_xyxy_pixels) < area($1.box_xyxy_pixels) }
}

func area(_ b: [Double]) -> Double { (b[2] - b[0]) * (b[3] - b[1]) }
```

No such track: speak a short local line, e.g. "Nothing identified yet. Hold
the item in view for a few seconds."

### 3.4 Trigger option 1: tap on the glasses (works on SDK 1.0.1)

Meta's session lifecycle docs: while a session runs, "a one-finger tap pauses or
resumes the device session" and "tap and hold stops" it. The app already
observes the camera stream state in `GlassesController.observe(_:)`
(`stream.statePublisher.listen`). Use **that** stream state, not
`DeviceSession`'s: Meta's known-issues page says `DeviceStateSession` is
unreliable together with a camera stream session.

1. Log `String(describing: state)` on every transition, tap the glasses, and
   note the exact paused/resumed case names in SDK 1.0.1. Do not guess them.
2. On the transition *into* paused: `speak(mainTrack(result)?.description ?? ...)`.
   While paused no frames arrive, so `result` is still the scene the wearer was
   looking at.
3. On resume: `speech.stopSpeaking(at: .immediate)`.
4. Debounce: ignore a second pause within ~2 s.

Caveat: the app cannot tell a tap from other pauses (taking the glasses off,
closing the hinges). Those also start a description. Fine for a demo; option 2
fixes it.

### 3.5 Trigger option 2: capture button via Inputs (beta)

Meta's Inputs capability delivers decoded events, including the capture button
(`.capture` with short press / hold / double press) and touchpad `.select` /
`.nav`. From https://wearables.developer.meta.com/docs/develop/dat/inputs/ :

- Beta: "available in the development and beta release channels only"; the API
  may change. The app uses the stable 1.0.1 package, so this means switching
  the package to the beta channel.
- iOS: `import MWDATInputs`; `session.addInputs(configuration:
  InputsConfiguration(sources: [...]))`, then `for await event in
  inputs.events`; wait for the `.active` state; keep listener tokens; call
  `session.removeInputs()` on teardown. No user permission prompt.
- Not documented: which glasses models support it, and whether a capture press
  still takes a native photo/video at the same time. Test both.

Only try this after option 1 works end to end.

### 3.6 Fallback trigger: iPhone Action Button (no app code)

If glasses triggers misbehave before the demo, a Shortcut can be put on the
Action Button. There is no laptop endpoint that returns only the description,
so this needs part A's `/describe` (4.4) first: "Get Contents of URL" (`POST
http://<laptop-ip>:8765/describe`, header `Authorization: Bearer <token>`),
"Get Dictionary Value" `description`, "Speak Text". Audio goes to the glasses
the same way as 3.1.

## 4. Part A: laptop side, optional (models owner)

Only for a better voice than Apple's built-in one, or for the 3.6 fallback.

### 4.1 Audio cost

ElevenLabs free plan: about 10,000 characters a month, about 30 descriptions.
Each product family is voiced once and cached, so a 10-item demo costs about
3,500 characters. Do **one** real ElevenLabs call well before the demo; it has
never been run. Keys go in `.env` only, never in chat, logs, commits or URLs.
Test everything else with the free built-in voice.

### 4.2 Voice descriptions in relay mode

In `main()`, relay mode skips audio on purpose today (`if args.listen: pass`,
"descriptions go to the dashboard as text"). To add it: build the `Narrator`
with `speak` and `audio_dir` when `ELEVENLABS_API_KEY` is set, in relay mode
too. `describe_tracks()` already calls `narrator.prepare(name)` for branded
names, which then also writes the WAV (`Narrator._make`). Unbranded fixed texts
are not voiced; the phone keeps the built-in voice for those.

### 4.3 `audio_url` and `GET /audio/<slug>.wav`

- In the `/frame` reply, add `"audio_url": "/audio/<slug>.wav"` per track when
  `narrator.audio_dir` is set and `narrator.wav(name)` exists, else `null`. The
  file name is `slug(name) + ".wav"` (`slug` in `recognition/narrator.py`).
  Additive field; the app ignores unknown fields.
- `GET /audio/<file>`: `Authorization: Bearer` header (the phone uses
  URLSession, so do not put the token in the URL). Serve only names matching
  `^[a-z0-9-]+\.wav$` from `narrator.audio_dir`; anything else 404 (no path
  traversal). `Content-Type: audio/wav`, `Content-Length`.
- Phone side: if `audio_url` is set, GET it with the header,
  `AVAudioPlayer(data:)` (strong reference), `play()`; else `speak(description)`.

### 4.4 `POST /describe` (only for the 3.6 fallback)

Bearer header like `/frame`. Pick the main track from `shown["tracks"]` (named,
largest box, same rule as 3.3). Reply `{"label", "name", "description",
"audio_url"}`; `404 {"error": "nothing identified yet"}` when none. Do not
block on Gemini: return what `describe_tracks` has already attached.

### 4.5 Thread safety

`Narrator` is not thread-safe (its docstring says one thread). In relay mode
`describe_tracks()` runs on the detector thread. Anything new that touches the
narrator from HTTP handler threads (4.3, 4.4) should only read files
(`wav()` exists, `description()`), or add a `threading.Lock` around
`self.jobs`.

### 4.6 Tests

Add tests next to `RelayServerTests` in `recognition/tests/test_live_runner.py`
(they run a real server on a free port with a fake `shown`): `audio_url` null
without audio, set when the WAV exists; `/audio` 401 without token, 404 for
`../x.wav` and missing files, 200 with WAV bytes. Run
`training/.venv/bin/python -m unittest discover -s recognition/tests -t .` and
`... -s tests -t .`. Update `RUNBOOK.md` section 5.

## 5. End-to-end acceptance (free path)

1. Laptop: relay running with a fixed token. A curl POST of a permitted phone
   photo to `/frame` returns a track with a `description` after a few tries.
   (`training/datasets/scavscrap/images/oi_000f78a66fd29c49.jpg` is a phone;
   Gemini named it "Apple iPhone" on 2026-10-24.)
2. Phone: 3.1 voice comes from the glasses while streaming.
3. Look at a phone or laptop for ~10-30 s, tap the glasses once: its
   description plays from the glasses within a second.
4. Tap again: speech stops and the stream resumes.
5. Look at nothing, tap: "Nothing identified yet".

## 6. Gotchas

- Same Wi-Fi for phone and laptop; laptop IP from `ipconfig getifaddr en0`.
- Warm the cache before a demo: show each demo item once so its name and
  description are already written (`cache/narration/`, per machine, gitignored).
- Do not add the microphone to the DAT session for this; mic capture is
  experimental and would push audio to the HFP profile.
- References: Meta Inputs https://wearables.developer.meta.com/docs/develop/dat/inputs/ ;
  session lifecycle https://wearables.developer.meta.com/docs/develop/dat/lifecycle-events/ ;
  known issues https://wearables.developer.meta.com/docs/knownissues ;
  SDK https://github.com/facebook/meta-wearables-dat-ios ;
  ElevenLabs TTS https://elevenlabs.io/docs/api-reference/text-to-speech/convert

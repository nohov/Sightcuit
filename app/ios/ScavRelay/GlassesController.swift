import AVFoundation
import MWDATCamera
import MWDATCore
import MWDATInputs
import SwiftUI
#if DEBUG
import MWDATMockDevice
#endif

/// Glasses registration, camera permission, and one camera stream whose frames go to the laptop relay.
@MainActor
final class GlassesController: ObservableObject {
  @Published var registration = "unknown"
  @Published var streamState = "stopped"
  @Published var status = ""
  @Published var frame: UIImage?
  @Published var result: RelayResult?
  @Published var resultFrame: UIImage?
  @Published var relayError: String?
  @Published var detectorError: String?

  let relay = RelayClient()
  private let detectorRelay = RelayClient()
  private var useDetector = false
  /// Short press of the glasses capture button: the tutor's "step done" press. Returns false when the tutor is
  /// not listening, so the press speaks descriptions instead. The stream keeps running.
  var onCapture: (() -> Bool)?
  private var session: DeviceSession?
  private var camera: Camera?
  private let tokens = ListenerTokenBag()
  // Held here: a local synthesizer is deallocated mid-sentence.
  private let speech = AVSpeechSynthesizer()
  private var lastSpoken: Date?
  private var inputsTask: Task<Void, Never>?

  init() {
    Task {
      for await state in Wearables.shared.registrationStateStream() {
        registration = String(describing: state)
      }
    }
  }

  func register() async {
    do {
      try await Wearables.shared.startRegistration()
    } catch {
      status = error.description
    }
  }

  func start(host: String, detectorHost: String, token: String) async {
    relay.configure(host: host, token: token)
    useDetector = !detectorHost.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    if useDetector { detectorRelay.configure(host: detectorHost, token: token) }
    result = nil
    resultFrame = nil
    relayError = nil
    detectorError = nil
    do {
      if try await Wearables.shared.checkPermissionStatus(.camera) != .granted {
        guard try await Wearables.shared.requestPermission(.camera) == .granted else {
          status = "Camera permission denied in Meta AI"
          return
        }
      }
      // The device list fills in asynchronously; creating a session before it does throws noEligibleDevice.
      let selector = AutoDeviceSelector(wearables: Wearables.shared)
      // shortcut: polls instead of racing activeDeviceStream() against a timer; fine for a 10 s one-off wait.
      for _ in 0..<20 where selector.activeDevice == nil {
        status = "Waiting for glasses..."
        try await Task.sleep(for: .milliseconds(500))
      }
      guard selector.activeDevice != nil else {
        let known = Wearables.shared.devices.count
        status = known == 0
          ? "No glasses known to Meta AI: check pairing and Developer Mode"
          : "\(known) glasses known but none connected: open the arms, wear them, check Bluetooth"
        return
      }
      // A stopped session cannot restart; always open a new one.
      let session = try Wearables.shared.createSession(deviceSelector: selector)
      self.session = session
      // Subscribe before start() so early errors and states are not missed.
      let errors = session.errorStream()
      let states = session.stateStream()
      var sessionError: String?
      Task {
        for await error in errors {
          sessionError = error.description
          status = "Glasses session error: \(error.description)"
          // Meta AI owns the glasses-app update screen; there is no fixed menu path to send the user to.
          if error == .datAppOnTheGlassesUpdateRequired {
            try? await Wearables.shared.openDATGlassesAppUpdate()
          }
        }
      }
      try session.start()
      var seen: [String] = []
      for await state in states {
        seen.append(String(describing: state))
        if state == .started { break }
        if state == .stopped {
          stop()
          status = "Glasses session stopped before it started (\(seen.joined(separator: " → "))): \(sessionError ?? "no error reported")"
          return
        }
      }
      // High is 720x1280: medium (504x896) left resistor bands too blurry to read. 7 fps is plenty because the
      // laptop only handles the newest frame.
      let config = StreamConfiguration(videoCodec: .raw, resolution: .high, frameRate: 7)
      guard let camera = try session.addCamera(config: config) else {
        status = "Camera would not attach"
        return
      }
      self.camera = camera
      observe(camera.stream)
      camera.stream.start()
      status = ""
      observeInputs(session)
    } catch {
      // Leftover sessions make the next Start fail with sessionAlreadyExists.
      stop()
      status = error.localizedDescription
    }
  }

  /// Speaks every box from the last relay reply in turn, biggest (nearest the wearer) first.
  func describeCurrent() {
    var texts: [String] = []
    for track in (result?.tracks ?? []).sorted(by: { area($0.box_xyxy_pixels) > area($1.box_xyxy_pixels) }) {
      // Two items of the same product share one text; say it once.
      let text = useDetector ? (track.description ?? track.name ?? track.label) : track.description
      if let text, !texts.contains(text) { texts.append(text) }
    }
    speak(texts.isEmpty ? ["Nothing identified yet. Hold the item in view for a few seconds."] : texts)
  }

  private func area(_ b: [Double]) -> Double { b.count == 4 ? (b[2] - b[0]) * (b[3] - b[1]) : 0 }

  private func speak(_ texts: [String]) {
    let audio = AVAudioSession.sharedInstance()
    // .playback, not .playAndRecord: recording forces the low-quality hands-free Bluetooth profile.
    try? audio.setCategory(.playback, mode: .spokenAudio)
    try? audio.setActive(true)
    speech.stopSpeaking(at: .immediate)
    // The synthesizer queues utterances and plays them back to back.
    for text in texts { speech.speak(AVSpeechUtterance(string: text)) }
    // Shows whether the voice goes to the glasses (Bluetooth) or the phone speaker.
    status = "Audio out: " + audio.currentRoute.outputs.map { $0.portType.rawValue }.joined(separator: ", ")
  }

  /// Capture button press: speak (or stop speaking) without pausing the stream. Meta marks Inputs as beta.
  /// Optional: if it does not attach, streaming and the tap trigger still work.
  private func observeInputs(_ session: DeviceSession) {
    do {
      guard let inputs = try session.addInputs(configuration: InputsConfiguration(sources: [.captureButton])) else {
        status = "Capture button unavailable; tap the glasses instead"
        return
      }
      inputs.statePublisher.listen { state in print("Glasses inputs state: \(state)") }.store(in: tokens)
      inputs.errorPublisher.listen { [weak self] error in
        Task { @MainActor in self?.status = "Capture button: \(error.description); tap the glasses instead" }
      }.store(in: tokens)
      let events = inputs.events
      inputsTask = Task { @MainActor [weak self] in
        for await event in events {
          print("Glasses input: \(event)")
          guard let self, case .capture(.shortPress, _, _) = event else { continue }
          // While the tutor listens, a press means "step done"; otherwise it speaks descriptions.
          if self.onCapture?() == true { continue }
          if self.speech.isSpeaking {
            self.speech.stopSpeaking(at: .immediate)
          } else {
            self.describeCurrent()
          }
        }
      }
    } catch {
      status = "Capture button: \(error.localizedDescription); tap the glasses instead"
    }
  }

  func stop() {
    speech.stopSpeaking(at: .immediate)
    // Cancel the event task before removing Inputs, as the DAT docs require.
    inputsTask?.cancel()
    inputsTask = nil
    try? session?.removeInputs()
    camera?.stop()
    session?.stop()
    tokens.clear()
    camera = nil
    session = nil
    streamState = "stopped"
  }

  // Subscribe before start() so no transition is missed.
  private func observe(_ stream: MWDATCamera.Stream) {
    stream.statePublisher.listen { [weak self] state in
      // paused keeps the last frame on screen; a tap on the glasses resumes.
      Task { @MainActor in
        guard let self else { return }
        print("Glasses stream state: \(state)")
        self.streamState = String(describing: state)
        switch state {
        case .paused:
          // A tap pauses the stream, so it is the trigger. Taking the glasses off or closing them also pauses
          // and also speaks: the SDK does not say why it paused. While paused, result is still the last scene.
          // Fallback trigger: freezes the stream until the next tap. The capture button (observeInputs) does not.
          if self.lastSpoken.map({ Date().timeIntervalSince($0) > 2 }) ?? true {
            self.lastSpoken = Date()
            self.describeCurrent()
          }
        case .streaming:
          self.speech.stopSpeaking(at: .immediate)
        default:
          break
        }
      }
    }.store(in: tokens)
    stream.errorPublisher.listen { [weak self] error in
      Task { @MainActor in self?.status = error.localizedDescription }
    }.store(in: tokens)
    stream.videoFramePublisher.listen { [weak self] videoFrame in
      guard let image = videoFrame.makeUIImage() else { return }
      Task { @MainActor in
        guard let self else { return }
        self.frame = image
        self.relay.send(image) { outcome in
          switch outcome {
          case .success(let (result, resultFrame)):
            if !self.useDetector, let resultFrame {
              self.resultFrame = resultFrame
              self.result = result
            }
            self.relayError = nil
          case .failure(let error):
            self.relayError = "Tutor: \(error.localizedDescription)"
          }
        }
        if self.useDetector {
          self.detectorRelay.send(image) { outcome in
            switch outcome {
            case .success(let (result, resultFrame)):
              if let resultFrame {
                self.resultFrame = resultFrame
                self.result = result
              }
              self.detectorError = nil
            case .failure(let error):
              self.detectorError = "Detector: \(error.localizedDescription)"
            }
          }
        }
      }
    }.store(in: tokens)
  }

  #if DEBUG
  /// Simulated glasses for the simulator: feeds a local clip instead of the real camera.
  func useMockGlasses(feed: URL) {
    MockDeviceKit.shared.enable(config: MockDeviceKitConfig(initiallyRegistered: true, initialPermissionsGranted: true))
    do {
      let device = try MockDeviceKit.shared.pairGlasses(model: .rayBanMeta)
      device.powerOn()
      device.unfold()
      device.don()
      device.services.camera.setCameraFeed(fileURL: feed)
    } catch {
      status = "Mock glasses failed: \(error.localizedDescription)"
    }
  }
  #endif
}

import MWDATCamera
import MWDATCore
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
  @Published var relayError: String?

  let relay = RelayClient()
  private var session: DeviceSession?
  private var camera: Camera?
  private let tokens = ListenerTokenBag()

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

  func start(host: String, token: String) async {
    relay.configure(host: host, token: token)
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
      // Medium is 504x896; 7 fps is plenty because the laptop only handles the newest frame.
      let config = StreamConfiguration(videoCodec: .raw, resolution: .medium, frameRate: 7)
      guard let camera = try session.addCamera(config: config) else {
        status = "Camera would not attach"
        return
      }
      self.camera = camera
      observe(camera.stream)
      camera.stream.start()
      status = ""
    } catch {
      // Leftover sessions make the next Start fail with sessionAlreadyExists.
      stop()
      status = error.localizedDescription
    }
  }

  func stop() {
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
      Task { @MainActor in self?.streamState = String(describing: state) }
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
          case .success(let result):
            self.result = result
            self.relayError = nil
          case .failure(let error):
            self.relayError = error.localizedDescription
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

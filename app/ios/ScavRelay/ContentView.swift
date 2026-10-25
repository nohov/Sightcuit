import Security
import SwiftUI

let projectClasses: Set<String> = ["laptop", "phone", "headphones", "smartwatch", "speaker"]

struct ContentView: View {
  @ObservedObject var glasses: GlassesController
  @StateObject private var voice = Voice()
  @AppStorage("relayHost") private var host = ""
  @AppStorage("detectorHost") private var detectorHost = ""
  @State private var token = Keychain.read() ?? ""
  @FocusState private var editingRelay: Bool

  var body: some View {
    VStack(spacing: 0) {
      Form {
        Section("Laptop relay") {
          TextField("192.168.1.20:8765", text: $host)
            .keyboardType(.URL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .focused($editingRelay)
          VStack(alignment: .leading) {
            Text("Detector relay (optional)").font(.caption).foregroundStyle(.secondary)
            TextField("192.168.1.20:8766", text: $detectorHost)
              .keyboardType(.URL)
              .textInputAutocapitalization(.never)
              .autocorrectionDisabled()
              .focused($editingRelay)
          }
          SecureField("Token printed by live_runner", text: $token)
            .focused($editingRelay)
            .onChange(of: token) { _, value in Keychain.save(value) }
        }
        Section("Glasses") {
          LabeledContent("Registration", value: glasses.registration)
          LabeledContent("Stream", value: glasses.streamState)
          Button("Connect glasses in Meta AI") { Task { await glasses.register() } }
          #if DEBUG
          // Needs a permitted clip bundled as mock-feed.mp4; see app/ios/README.md.
          if let feed = Bundle.main.url(forResource: "mock-feed", withExtension: "mp4") {
            Button("Use mock glasses") { glasses.useMockGlasses(feed: feed) }
          }
          #endif
          if glasses.streamState == "stopped" {
            Button("Start streaming") {
              editingRelay = false
              Task { await glasses.start(host: host, detectorHost: detectorHost, token: token) }
            }
              .disabled(host.isEmpty || token.isEmpty)
          } else {
            // Same as a tap on the glasses; also the check that audio reaches the glasses during a stream.
            Button("Speak description") { glasses.describeCurrent() }
            Button("Stop", role: .destructive) { glasses.stop() }
          }
        }
        // Needs `recognition.tutor_runner` on the laptop instead of live_runner.
        Section("Circuit tutor") {
          if !voice.step.isEmpty { LabeledContent("Progress", value: voice.step) }
          if voice.listening {
            Text(voice.heard.isEmpty ? "Say \"\(Voice.wakeWord), …\"; press capture when a step is done" : voice.heard)
              .font(.footnote)
            Button("Stop listening", role: .destructive) { voice.stop() }
          } else {
            Button("Start listening") { Task { await voice.start(relay: glasses.relay) } }
              .disabled(glasses.streamState == "stopped")
          }
          if !voice.said.isEmpty { Text(voice.said).font(.footnote).foregroundStyle(.secondary) }
        }
      }
      .frame(maxHeight: 620)
      .scrollDismissesKeyboard(.interactively)
      .onSubmit { editingRelay = false }
      .toolbar {
        ToolbarItemGroup(placement: .keyboard) {
          Spacer()
          Button("Done") { editingRelay = false }
        }
      }
      .onAppear {
        glasses.onCapture = { [voice, glasses] in
          guard voice.listening else { return false }
          voice.send("done", relay: glasses.relay)
          return true
        }
      }

      if let voiceError = voice.error {
        Banner(text: voiceError)
      }

      if !glasses.status.isEmpty {
        Banner(text: glasses.status)
      }
      if let relayError = glasses.relayError {
        // Failures are never shown as detections.
        Banner(text: relayError)
      }
      if let detectorError = glasses.detectorError {
        Banner(text: detectorError)
      }
      ZStack {
        Color(red: 0.05, green: 0.10, blue: 0.11)
        if let frame = glasses.frame {
          FrameOverlay(image: glasses.resultFrame ?? frame, result: glasses.result)
        } else {
          Label("Camera feed appears when streaming", systemImage: "viewfinder")
            .font(.footnote)
            .foregroundStyle(.white.opacity(0.7))
        }
      }
      .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(Color(red: 0.05, green: 0.10, blue: 0.11).ignoresSafeArea())
  }
}

struct Banner: View {
  let text: String

  var body: some View {
    Label(text, systemImage: "exclamationmark.triangle.fill")
      .font(.footnote)
      .foregroundStyle(.white)
      .padding(8)
      .frame(maxWidth: .infinity, alignment: .leading)
      .background(.red, in: RoundedRectangle(cornerRadius: 8))
      .padding(.horizontal)
  }
}

/// Last glasses frame with the relay's boxes, scaled from the size the laptop saw.
struct FrameOverlay: View {
  let image: UIImage
  let result: RelayResult?

  var body: some View {
    Image(uiImage: image)
      .resizable()
      .scaledToFit()
      .overlay {
        GeometryReader { geometry in
          if let result, let size = result.image_size_hw_pixels, size.count == 2 {
            let sx = geometry.size.width / Double(size[1])
            let sy = geometry.size.height / Double(size[0])
            ForEach(result.tracks) { track in
              let b = track.box_xyxy_pixels
              let label = track.label ?? "..."
              let color: Color = projectClasses.contains(label) ? .green : .gray
              Rectangle()
                .stroke(color, lineWidth: 2)
                .frame(width: (b[2] - b[0]) * sx, height: (b[3] - b[1]) * sy)
                .overlay(alignment: .topLeading) {
                  Text("#\(track.track_id) \(label)")
                    .font(.caption2)
                    .foregroundStyle(color)
                    .offset(y: -14)
                }
                .position(x: (b[0] + b[2]) / 2 * sx, y: (b[1] + b[3]) / 2 * sy)
                .accessibilityLabel("Track \(track.track_id), \(label)")
            }
          }
        }
      }
      .padding(.horizontal)
  }
}

/// Relay token lives in the Keychain, not UserDefaults.
enum Keychain {
  private static let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "scavscrap.relay",
    kSecAttrAccount as String: "token",
  ]

  static func read() -> String? {
    var item: CFTypeRef?
    var lookup = query
    lookup[kSecReturnData as String] = true
    guard SecItemCopyMatching(lookup as CFDictionary, &item) == errSecSuccess, let data = item as? Data else {
      return nil
    }
    return String(data: data, encoding: .utf8)
  }

  static func save(_ token: String) {
    SecItemDelete(query as CFDictionary)
    var item = query
    item[kSecValueData as String] = Data(token.utf8)
    SecItemAdd(item as CFDictionary, nil)
  }
}

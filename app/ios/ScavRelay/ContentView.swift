import Security
import SwiftUI

let projectClasses: Set<String> = ["laptop", "desktop_computer_tower", "monitor", "printer", "projector"]

struct ContentView: View {
  @ObservedObject var glasses: GlassesController
  @AppStorage("relayHost") private var host = ""
  @State private var token = Keychain.read() ?? ""

  var body: some View {
    VStack(spacing: 12) {
      Form {
        Section("Laptop relay") {
          TextField("192.168.1.20:8765", text: $host)
            .keyboardType(.URL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
          SecureField("Token printed by live_runner", text: $token)
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
            Button("Start streaming") { Task { await glasses.start(host: host, token: token) } }
              .disabled(host.isEmpty || token.isEmpty)
          } else {
            Button("Stop", role: .destructive) { glasses.stop() }
          }
        }
      }
      .frame(maxHeight: 340)

      if !glasses.status.isEmpty {
        Banner(text: glasses.status)
      }
      if let relayError = glasses.relayError {
        // Failures are never shown as detections.
        Banner(text: relayError)
      }
      if let frame = glasses.frame {
        FrameOverlay(image: frame, result: glasses.result)
      }
      Spacer(minLength: 0)
    }
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

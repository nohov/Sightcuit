import MWDATCore
import SwiftUI

@main
struct ScavRelayApp: App {
  @StateObject private var glasses = GlassesController()

  init() {
    do {
      try Wearables.configure()
    } catch {
      assertionFailure("DAT would not configure: \(error)")
    }
  }

  var body: some Scene {
    WindowGroup {
      ContentView(glasses: glasses)
        .onOpenURL { url in
          // Only Meta AI's registration callbacks belong to the SDK.
          guard URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.contains(where: { $0.name == "metaWearablesAction" }) == true
          else { return }
          Task {
            do {
              _ = try await Wearables.shared.handleUrl(url)
            } catch {
              glasses.status = "Registration callback failed: \(error.localizedDescription)"
            }
          }
        }
    }
  }
}

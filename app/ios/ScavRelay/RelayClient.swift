import UIKit

struct RelayTrack: Decodable, Identifiable {
  let track_id: Int
  let box_xyxy_pixels: [Double]
  let label: String?
  let name: String?
  let description: String?
  var id: Int { track_id }
}

/// Last finished tracks from the laptop; they trail the frame just sent by one inference.
struct RelayResult: Decodable {
  let tracks: [RelayTrack]
  let image_size_hw_pixels: [Int]?
}

/// The circuit tutor's spoken reply and where the build is (`recognition.tutor_runner`).
struct TutorReply: Decodable {
  let say: String
  let step_index: Int
  let step_count: Int
  let project: String?
  /// The model that answered; nil when no model call answered (step commands, no frame, model unreachable).
  let model: String?
}

struct RelayError: LocalizedError {
  let errorDescription: String?
}

/// POSTs JPEG frames to `recognition.live_runner --listen` with at most one request in flight.
@MainActor
final class RelayClient {
  private var endpoint: URL?
  private var askEndpoint: URL?
  private var token = ""
  private var inFlight = false

  func configure(host: String, token: String) {
    // Pasting a whole terminal line into the hidden token field brings a trailing newline.
    let host = host.trimmingCharacters(in: .whitespacesAndNewlines)
    endpoint = URL(string: "http://\(host)/frame")
    askEndpoint = URL(string: "http://\(host)/ask")
    self.token = token.trimmingCharacters(in: .whitespacesAndNewlines)
  }

  /// Sends one spoken request to the tutor; the laptop answers about the newest frame it has.
  func ask(_ text: String, done: @escaping @MainActor (Result<TutorReply, Error>) -> Void) {
    guard let askEndpoint else { return done(.failure(RelayError(errorDescription: "Relay host is not a valid URL"))) }
    var request = URLRequest(url: askEndpoint, timeoutInterval: 90)  // may wait on two model tiers
    request.httpMethod = "POST"
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    Task {
      do {
        let body = try JSONEncoder().encode(["text": text])
        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
          let message = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? "no detail"
          throw RelayError(errorDescription: "Tutor HTTP \(status): \(message)")
        }
        done(.success(try JSONDecoder().decode(TutorReply.self, from: data)))
      } catch {
        done(.failure(error))
      }
    }
  }

  /// Drops the frame when the previous one is still in flight; the laptop only wants the newest frame anyway.
  func send(_ image: UIImage, done: @escaping @MainActor (Result<RelayResult, Error>) -> Void) {
    guard !inFlight else { return }
    guard let endpoint else { return done(.failure(RelayError(errorDescription: "Relay host is not a valid URL"))) }
    guard let jpeg = image.jpegData(compressionQuality: 0.9) else { return }
    var request = URLRequest(url: endpoint, timeoutInterval: 10)
    request.httpMethod = "POST"
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.setValue("image/jpeg", forHTTPHeaderField: "Content-Type")
    inFlight = true
    Task {
      defer { inFlight = false }
      do {
        let (data, response) = try await URLSession.shared.upload(for: request, from: jpeg)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
          let message = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? "no detail"
          throw RelayError(errorDescription: "Relay HTTP \(status): \(message)")
        }
        done(.success(try JSONDecoder().decode(RelayResult.self, from: data)))
      } catch {
        done(.failure(error))
      }
    }
  }
}

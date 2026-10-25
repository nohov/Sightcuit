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
  /// ElevenLabs WAV of `say`; nil when the laptop has no ElevenLabs key or speaking failed.
  let audio_wav_base64: String?
}

struct RelayError: LocalizedError {
  let errorDescription: String?
  var status = 0
}

/// POSTs JPEG frames to `recognition.live_runner --listen` with at most one request in flight.
@MainActor
final class RelayClient {
  private var endpoint: URL?
  private var askEndpoint: URL?
  private var token = ""
  private var inFlight = false
  // shortcut: replies are paired with the prior successful send; add frame IDs if inference falls further behind.
  private var previousImage: UIImage?

  func configure(host: String, token: String) {
    // Pasting a whole terminal line into the hidden token field brings a trailing newline.
    let host = host.trimmingCharacters(in: .whitespacesAndNewlines)
    endpoint = URL(string: "http://\(host)/frame")
    askEndpoint = URL(string: "http://\(host)/ask")
    self.token = token.trimmingCharacters(in: .whitespacesAndNewlines)
    previousImage = nil
  }

  /// Sends one spoken request to the tutor; the laptop answers about the newest frame it has.
  /// With `audio` the laptop transcribes it with ElevenLabs; `text`, the phone's own transcript, goes when it cannot.
  func ask(_ text: String, audio: Data? = nil, done: @escaping @MainActor (Result<TutorReply, Error>) -> Void) {
    guard let askEndpoint else { return done(.failure(RelayError(errorDescription: "Relay host is not a valid URL"))) }
    Task {
      do {
        if let audio {
          do {
            return done(.success(try await post(audio, type: "audio/wav", to: askEndpoint)))
          } catch let error as RelayError where error.status == 503 {}  // no ElevenLabs or nothing heard
        }
        done(.success(try await post(try JSONEncoder().encode(["text": text]), type: "application/json", to: askEndpoint)))
      } catch {
        done(.failure(error))
      }
    }
  }

  private func post(_ body: Data, type: String, to url: URL) async throws -> TutorReply {
    var request = URLRequest(url: url, timeoutInterval: 90)  // may wait on transcription and two model tiers
    request.httpMethod = "POST"
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.setValue(type, forHTTPHeaderField: "Content-Type")
    let (data, response) = try await URLSession.shared.upload(for: request, from: body)
    let status = (response as? HTTPURLResponse)?.statusCode ?? 0
    guard status == 200 else {
      let message = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? "no detail"
      throw RelayError(errorDescription: "HTTP \(status): \(message)", status: status)
    }
    return try JSONDecoder().decode(TutorReply.self, from: data)
  }

  /// Drops the frame when the previous one is still in flight; the laptop only wants the newest frame anyway.
  func send(_ image: UIImage, done: @escaping @MainActor (Result<(RelayResult, UIImage?), Error>) -> Void) {
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
        let result = try JSONDecoder().decode(RelayResult.self, from: data)
        let resultFrame = previousImage
        previousImage = image
        done(.success((result, resultFrame)))
      } catch {
        done(.failure(error))
      }
    }
  }
}

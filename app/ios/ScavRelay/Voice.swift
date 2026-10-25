import AVFoundation
import Speech

/// On-device speech in and out for the circuit tutor; only the recognized question text goes to the laptop.
@MainActor
final class Voice: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
  @Published var listening = false
  @Published var heard = ""
  @Published var said = ""
  @Published var step = ""
  @Published var error: String?

  static let wakeWord = "tutor"
  private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
  private let engine = AVAudioEngine()
  private let synthesizer = AVSpeechSynthesizer()
  private var request: SFSpeechAudioBufferRecognitionRequest?
  private var task: SFSpeechRecognitionTask?
  private var silence: Task<Void, Never>?
  private var relay: RelayClient?

  override init() {
    super.init()
    synthesizer.delegate = self
  }

  func start(relay: RelayClient) async {
    self.relay = relay
    error = nil
    let speechAllowed = await withCheckedContinuation { done in
      SFSpeechRecognizer.requestAuthorization { done.resume(returning: $0 == .authorized) }
    }
    guard speechAllowed else { error = "Speech recognition is not allowed in Settings"; return }
    guard await AVAudioApplication.requestRecordPermission() else { error = "Microphone is not allowed in Settings"; return }
    // Cloud recognition would send audio to Apple; on-device keeps it free and on the phone.
    guard recognizer?.supportsOnDeviceRecognition == true else {
      error = "On-device English speech recognition is unavailable on this phone"
      return
    }
    do {
      // HFP routes the mic and speakers of the glasses when they are the connected Bluetooth headset.
      try AVAudioSession.sharedInstance().setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetooth])
      try AVAudioSession.sharedInstance().setActive(true)
      listening = true
      listen()
      engine.prepare()
      try engine.start()
    } catch {
      stop()
      self.error = "Audio would not start: \(error.localizedDescription)"
    }
  }

  func stop() {
    listening = false
    endUtterance()
    engine.stop()
    synthesizer.stopSpeaking(at: .immediate)
  }

  /// Send a fixed request (the glasses tap meaning "this step is done") without speech recognition.
  func send(_ text: String, relay: RelayClient) {
    speak("Sent.")
    relay.ask(text) { [weak self] outcome in self?.answered(outcome) }
  }

  /// One recognition request per utterance.
  /// shortcut: Apple ends a request after about a minute, so silence or a final result restarts it; replace if words drop.
  private func listen() {
    guard listening else { return }
    let request = SFSpeechAudioBufferRecognitionRequest()
    request.requiresOnDeviceRecognition = true
    request.shouldReportPartialResults = true
    self.request = request
    let input = engine.inputNode
    input.removeTap(onBus: 0)
    nonisolated(unsafe) let buffered = request  // append is safe from the audio thread
    input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
      buffered.append(buffer)
    }
    let id = ObjectIdentifier(request)
    task = recognizer?.recognitionTask(with: request) { [weak self] result, error in
      let text = result?.bestTranscription.formattedString
      let ended = (result?.isFinal ?? false) || error != nil
      Task { @MainActor in self?.recognized(text, ended: ended, request: id) }
    }
  }

  private func recognized(_ text: String?, ended: Bool, request id: ObjectIdentifier) {
    // Cancelling a finished request calls back once more; ignore stale requests.
    guard let request, ObjectIdentifier(request) == id else { return }
    if let text { heard = text }
    silence?.cancel()
    if ended { return finish() }
    silence = Task {
      try? await Task.sleep(for: .seconds(1.2))  // a pause ends the utterance
      if !Task.isCancelled { finish() }
    }
  }

  private func endUtterance() {
    silence?.cancel()
    request?.endAudio()
    task?.cancel()
    request = nil
    task = nil
    engine.inputNode.removeTap(onBus: 0)
  }

  private func finish() {
    endUtterance()
    let text = heard
    heard = ""
    guard listening else { return }
    guard let question = Self.question(in: text), let relay else { return listen() }
    // The laptop only answers after the model does, so this confirms the send; the reply confirms the model.
    speak("Sent.")
    relay.ask(question) { [weak self] outcome in self?.answered(outcome) }
  }

  private func answered(_ outcome: Result<TutorReply, Error>) {
    switch outcome {
    case .success(let reply):
      error = nil
      step = "Step \(reply.step_index + 1) of \(reply.step_count)" + (reply.project.map { " · \($0)" } ?? "")
      speak(reply.model == nil ? reply.say : "The model says: \(reply.say)")
    case .failure(let failure):
      error = failure.localizedDescription
      speak("I couldn't reach the laptop.")
    }
  }

  /// The words after the wake word, so side conversation never leaves the phone.
  static func question(in text: String) -> String? {
    guard let range = text.range(of: wakeWord, options: .caseInsensitive) else { return nil }
    let rest = text[range.upperBound...].trimmingCharacters(in: .punctuationCharacters.union(.whitespaces))
    return rest.isEmpty ? nil : rest
  }

  private func speak(_ text: String) {
    said = text
    // Not listening while speaking keeps the tutor from hearing itself.
    endUtterance()
    synthesizer.speak(AVSpeechUtterance(string: text))
  }

  nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
    Task { @MainActor in self.listen() }
  }
}

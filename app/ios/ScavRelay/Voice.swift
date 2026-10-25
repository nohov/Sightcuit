import AVFoundation
import Speech

/// Mic samples of one utterance as 16-bit mono WAV; appended on the audio thread, read on the main actor.
final class Recording: @unchecked Sendable {
  static let maxSeconds = 30.0  // keeps the upload under the laptop's 4 MB limit at 48 kHz
  private let lock = NSLock()
  private var samples: [Int16] = []
  private var rate = 0.0

  func append(_ buffer: AVAudioPCMBuffer) {
    guard let channel = buffer.floatChannelData?[0] else { return }
    lock.withLock {
      rate = buffer.format.sampleRate
      guard Double(samples.count) < rate * Self.maxSeconds else { return }
      samples += UnsafeBufferPointer(start: channel, count: Int(buffer.frameLength))
        .map { Int16(max(-1, min(1, $0)) * Float(Int16.max)) }
    }
  }

  func wav() -> Data {
    lock.withLock {
      var data = Data()
      func put<T: FixedWidthInteger>(_ value: T) { withUnsafeBytes(of: value.littleEndian) { data.append(contentsOf: $0) } }
      let bytes = UInt32(samples.count * 2)
      data.append(contentsOf: Array("RIFF".utf8)); put(36 + bytes)
      data.append(contentsOf: Array("WAVEfmt ".utf8)); put(UInt32(16)); put(UInt16(1)); put(UInt16(1))
      put(UInt32(rate)); put(UInt32(rate) * 2); put(UInt16(2)); put(UInt16(16))
      data.append(contentsOf: Array("data".utf8)); put(bytes)
      samples.withUnsafeBytes { data.append(contentsOf: $0) }  // iPhones are little-endian, as WAV is
      return data
    }
  }
}

/// Speech in and out for the circuit tutor. The wake word is heard on the phone; only an utterance containing it
/// goes to the laptop, as audio for ElevenLabs speech-to-text and as the on-device transcript for when that fails.
@MainActor
final class Voice: NSObject, ObservableObject, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate {
  @Published var listening = false
  @Published var heard = ""
  @Published var said = ""
  @Published var step = ""
  @Published var error: String?

  static let wakeWord = "tutor"
  private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
  private let engine = AVAudioEngine()
  private let synthesizer = AVSpeechSynthesizer()
  private var player: AVAudioPlayer?
  private var request: SFSpeechAudioBufferRecognitionRequest?
  private var task: SFSpeechRecognitionTask?
  private var recording: Recording?
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
    player?.stop()
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
    let recording = Recording()
    self.recording = recording
    input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
      buffered.append(buffer)
      recording.append(buffer)
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
    let wav = recording?.wav()
    recording = nil
    guard listening else { return }
    guard let question = Self.question(in: text), let relay else { return listen() }
    // The laptop only answers after the model does, so this confirms the send; the reply confirms the model.
    speak("Sent.")
    relay.ask(question, audio: wav) { [weak self] outcome in self?.answered(outcome) }
  }

  private func answered(_ outcome: Result<TutorReply, Error>) {
    switch outcome {
    case .success(let reply):
      error = nil
      step = reply.step_count == 0 ? "No build chosen"
        : "Step \(reply.step_index + 1) of \(reply.step_count)" + (reply.project.map { " · \($0)" } ?? "")
      play(reply.audio_wav_base64, saying: reply.say)
    case .failure(let failure):
      error = "Tutor: \(failure.localizedDescription)"
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

  /// The laptop's ElevenLabs audio when it sent some; the on-device voice otherwise.
  private func play(_ wav: String?, saying text: String) {
    guard let wav, let data = Data(base64Encoded: wav), let player = try? AVAudioPlayer(data: data) else {
      return speak(text)
    }
    said = text
    endUtterance()
    player.delegate = self
    self.player = player
    if !player.play() { speak(text) }
  }

  nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
    Task { @MainActor in self.listen() }
  }

  nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
    Task { @MainActor in self.listen() }
  }
}

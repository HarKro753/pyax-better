import AVFoundation
import Speech

/// Handles text-to-speech output and speech recognition input.
///
/// - TTS: Uses `AVSpeechSynthesizer` to speak agent responses.
/// - STT: Uses `SFSpeechRecognizer` for push-to-talk dictation.
@Observable
@MainActor
final class VoiceService {

    // MARK: - Private State

    private let _synthesizer: AVSpeechSynthesizer
    private var _speechRecognizer: SFSpeechRecognizer?
    private var _recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var _recognitionTask: SFSpeechRecognitionTask?
    private var _audioEngine: AVAudioEngine?
    private var _isListening = false
    private var _isSpeaking = false
    private var _recognizedText = ""
    private var _speechAuthorizationStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined

    // MARK: - Read Access

    var isListening: Bool { _isListening }
    var isSpeaking: Bool { _isSpeaking }
    var recognizedText: String { _recognizedText }
    var hasSpeechPermission: Bool { _speechAuthorizationStatus == .authorized }

    // MARK: - Init

    init() {
        self._synthesizer = AVSpeechSynthesizer()
        self._speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - Text-to-Speech

    /// Speak text aloud using the system TTS engine.
    func speak(_ text: String, rate: Double = 0.5) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = Float(max(0.0, min(1.0, rate)))
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0

        if let voice = AVSpeechSynthesisVoice(language: "en-US") {
            utterance.voice = voice
        }

        _isSpeaking = true
        _synthesizer.speak(utterance)

        Task {
            while _synthesizer.isSpeaking {
                try? await Task.sleep(for: .milliseconds(100))
            }
            _isSpeaking = false
        }
    }

    /// Stop any current speech.
    func stopSpeaking() {
        _synthesizer.stopSpeaking(at: .immediate)
        _isSpeaking = false
    }

    // MARK: - Speech Recognition

    /// Request speech recognition authorization.
    func requestSpeechPermission() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            Task { @MainActor in
                self?._speechAuthorizationStatus = status
            }
        }
    }

    /// Start listening for speech input (push-to-talk).
    func startListening() {
        guard !_isListening else { return }
        guard _speechAuthorizationStatus == .authorized else {
            requestSpeechPermission()
            return
        }
        guard let recognizer = _speechRecognizer, recognizer.isAvailable else { return }

        _recognizedText = ""

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        self._recognitionRequest = request

        let audioEngine = AVAudioEngine()
        self._audioEngine = audioEngine

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            request.append(buffer)
        }

        audioEngine.prepare()

        do {
            try audioEngine.start()
            _isListening = true
        } catch {
            stopListening()
            return
        }

        _recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self else { return }
                if let result {
                    self._recognizedText = result.bestTranscription.formattedString
                }
                if error != nil || (result?.isFinal ?? false) {
                    self.stopListening()
                }
            }
        }
    }

    /// Stop listening and return the recognized text.
    @discardableResult
    func stopListening() -> String {
        _audioEngine?.stop()
        _audioEngine?.inputNode.removeTap(onBus: 0)
        _audioEngine = nil

        _recognitionRequest?.endAudio()
        _recognitionRequest = nil

        _recognitionTask?.cancel()
        _recognitionTask = nil

        _isListening = false

        return _recognizedText
    }
}

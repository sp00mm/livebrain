import struct
import sys
from typing import Callable, Optional

from audio.interfaces import Transcriber

if sys.platform != 'darwin':
    raise ImportError('Apple Speech requires macOS')

import Speech as SF
import AVFoundation as AVF


class AppleSpeechTranscriber(Transcriber):
    SAMPLE_RATE = 48000

    def __init__(self):
        self._recognizer: Optional[SF.SFSpeechRecognizer] = None
        self._request: Optional[SF.SFSpeechAudioBufferRecognitionRequest] = None
        self._task: Optional[SF.SFSpeechRecognitionTask] = None
        self._on_result: Optional[Callable[[str, float, bool], None]] = None
        self._running = False
        self._format: Optional[AVF.AVAudioFormat] = None

    def is_available(self) -> bool:
        recognizer = SF.SFSpeechRecognizer.alloc().init()
        return recognizer is not None and recognizer.isAvailable()

    def request_permission(self, callback: Callable[[bool], None]) -> None:
        def handler(status):
            granted = status == SF.SFSpeechRecognizerAuthorizationStatusAuthorized
            callback(granted)
        SF.SFSpeechRecognizer.requestAuthorization_(handler)

    def start(self, on_result: Callable[[str, float, bool], None]) -> None:
        if self._running:
            return

        self._on_result = on_result
        self._recognizer = SF.SFSpeechRecognizer.alloc().init()

        if not self._recognizer or not self._recognizer.isAvailable():
            return

        self._request = SF.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        self._request.setShouldReportPartialResults_(True)
        self._request.setRequiresOnDeviceRecognition_(True)

        self._format = AVF.AVAudioFormat.alloc().initWithCommonFormat_sampleRate_channels_interleaved_(
            AVF.AVAudioPCMFormatFloat32,
            self.SAMPLE_RATE,
            1,
            False
        )

        def result_handler(result, error):
            if error or not result:
                return
            transcription = result.bestTranscription()
            text = transcription.formattedString()
            if not text:
                return
            confidence = 0.0
            segments = transcription.segments()
            if segments and len(segments) > 0:
                total_conf = sum(s.confidence() for s in segments)
                confidence = total_conf / len(segments)
            is_final = result.isFinal()
            if self._on_result:
                self._on_result(text, confidence, is_final)

        self._task = self._recognizer.recognitionTaskWithRequest_resultHandler_(
            self._request, result_handler
        )
        self._running = True

    def feed_audio(self, audio_data: bytes) -> None:
        if not self._running or not self._request or not self._format:
            return

        num_samples = len(audio_data) // 4
        floats = struct.unpack(f'{num_samples}f', audio_data)

        buffer = AVF.AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(
            self._format, num_samples
        )
        if not buffer:
            return
        buffer.setFrameLength_(num_samples)

        float_data = buffer.floatChannelData()
        if float_data:
            channel_data = float_data[0]
            for i, f in enumerate(floats):
                channel_data[i] = f

        self._request.appendAudioPCMBuffer_(buffer)

    def stop(self) -> None:
        if not self._running:
            return
        if self._request:
            self._request.endAudio()
        if self._task:
            self._task.cancel()
            self._task = None
        self._request = None
        self._recognizer = None
        self._on_result = None
        self._running = False

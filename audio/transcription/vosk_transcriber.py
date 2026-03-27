import json
import os
import struct
import sys
from typing import Callable, Optional

from audio.interfaces import Transcriber


def _model_dir():
    if sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support/Livebrain')
    else:
        base = os.path.expanduser('~/.livebrain')
    return os.path.join(base, 'models', 'vosk-model-small-en-us-0.15')


class VoskTranscriber(Transcriber):
    def __init__(self):
        self._recognizer = None
        self._on_result = None

    def start(self, on_result: Callable[[str, float, bool], None]):
        from vosk import Model, KaldiRecognizer
        self._on_result = on_result
        model = Model(model_path=_model_dir())
        self._recognizer = KaldiRecognizer(model, 48000)
        self._recognizer.SetWords(True)

    def stop(self):
        if self._recognizer:
            final = json.loads(self._recognizer.FinalResult())
            if final.get('text') and self._on_result:
                self._on_result(final['text'], 0.9, True)
        self._recognizer = None
        self._on_result = None

    def feed_audio(self, audio_data: bytes):
        if not self._recognizer:
            return
        floats = struct.unpack(f'{len(audio_data) // 4}f', audio_data)
        peak = max(abs(f) for f in floats) if floats else 0
        gain = min(0.9 / peak, 30.0) if peak > 0.005 else 1.0
        int16_data = struct.pack(f'{len(floats)}h',
            *(max(-32768, min(32767, int(f * gain * 32767))) for f in floats))

        if self._recognizer.AcceptWaveform(int16_data):
            result = json.loads(self._recognizer.Result())
            if result.get('text'):
                self._on_result(result['text'], 0.9, True)
        else:
            partial = json.loads(self._recognizer.PartialResult())
            if partial.get('partial'):
                self._on_result(partial['partial'], 0.5, False)

    def is_available(self):
        return os.path.isdir(_model_dir())

    def request_permission(self, callback: Callable[[bool], None]):
        callback(True)

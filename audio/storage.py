import os
import struct
import sys
import wave
from typing import Optional


class AudioStorage:
    SAMPLE_RATE = 48000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit

    def __init__(self, session_id: str, base_dir: Optional[str] = None):
        if base_dir is None:
            if sys.platform == 'darwin':
                base_dir = os.path.expanduser('~/Library/Application Support/Livebrain/recordings')
            else:
                base_dir = os.path.expanduser('~/.livebrain/recordings')
        self.session_dir = os.path.join(base_dir, session_id)
        os.makedirs(self.session_dir, exist_ok=True)
        self._mic_file: Optional[wave.Wave_write] = None
        self._system_file: Optional[wave.Wave_write] = None

    def start(self) -> None:
        self._mic_file = self._open_wav('mic.wav')
        self._system_file = self._open_wav('system.wav')

    def write_mic(self, audio_data: bytes) -> None:
        if self._mic_file:
            self._mic_file.writeframes(audio_data)

    def write_system(self, audio_data: bytes) -> None:
        if self._system_file:
            self._system_file.writeframes(audio_data)

    def stop(self) -> None:
        if self._mic_file:
            self._mic_file.close()
            self._mic_file = None
        if self._system_file:
            self._system_file.close()
            self._system_file = None

    def get_mic_path(self) -> str:
        return os.path.join(self.session_dir, 'mic.wav')

    def get_system_path(self) -> str:
        return os.path.join(self.session_dir, 'system.wav')

    def _open_wav(self, filename: str) -> wave.Wave_write:
        path = os.path.join(self.session_dir, filename)
        wf = wave.open(path, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.SAMPLE_WIDTH)
        wf.setframerate(self.SAMPLE_RATE)
        return wf

    @staticmethod
    def convert_float32_to_int16(float_data: bytes) -> bytes:
        num_samples = len(float_data) // 4
        floats = struct.unpack(f'{num_samples}f', float_data)
        int16s = [int(max(-32768, min(32767, f * 32767))) for f in floats]
        return struct.pack(f'{num_samples}h', *int16s)

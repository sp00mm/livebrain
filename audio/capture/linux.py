import subprocess
import threading
import time
from typing import Callable, Optional

import sounddevice as sd

from audio.interfaces import AudioCaptureSource


class LinuxMicCapture(AudioCaptureSource):
    on_audio: Optional[Callable[[bytes, float], None]] = None

    def __init__(self, device: Optional[str] = None):
        self._stream = None
        self._device = int(device) if device else self._find_physical_mic()

    def start(self):
        self._stream = sd.InputStream(
            samplerate=48000, channels=1, dtype='float32',
            device=self._device, callback=self._callback
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_available(self):
        return sd.query_devices(kind='input') is not None

    def request_permission(self, callback: Callable[[bool], None]):
        callback(True)

    def _callback(self, indata, frames, time_info, status):
        if self.on_audio:
            self.on_audio(indata.tobytes(), time.time())

    @staticmethod
    def _find_physical_mic():
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0 and d['hostapi'] == 0:
                name = d['name'].lower()
                if any(skip in name for skip in ['monitor', 'loopback', 'pipewire', 'default', 'sysdefault', 'dmix']):
                    continue
                return i
        return None


class LinuxSystemCapture(AudioCaptureSource):
    on_audio: Optional[Callable[[bytes, float], None]] = None

    def __init__(self, sink: Optional[str] = None):
        self._proc = None
        self._thread = None
        self._running = False
        self._sink = sink or self._find_default_sink()

    def start(self):
        self._running = True
        self._proc = subprocess.Popen(
            ['pw-cat', '--record', '--target', self._sink,
             '--rate', '48000', '--channels', '1', '--format', 'f32',
             '-P', 'stream.capture.sink=true', '-'],
            stdout=subprocess.PIPE
        )
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._proc:
            self._proc.stdout.close()
            self._proc.terminate()
            self._proc.wait()
            self._proc = None

    def is_available(self):
        return self._sink is not None

    def request_permission(self, callback: Callable[[bool], None]):
        callback(True)

    def _read_loop(self):
        chunk_bytes = 48000 * 4 // 100
        while self._running and self._proc and self._proc.poll() is None:
            data = self._proc.stdout.read(chunk_bytes)
            if data and self.on_audio:
                self.on_audio(data, time.time())

    @staticmethod
    def _find_default_sink():
        for cmd in [
            ['pactl', 'get-default-sink'],
            ['wpctl', 'inspect', '@DEFAULT_AUDIO_SINK@'],
        ]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if cmd[0] == 'pactl' and result.returncode == 0:
                    return result.stdout.strip()
                if cmd[0] == 'wpctl' and result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if 'node.name' in line:
                            return line.split('"')[1]
            except FileNotFoundError:
                continue
        return None

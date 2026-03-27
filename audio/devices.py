import subprocess
import sys
from dataclasses import dataclass


@dataclass
class AudioDevice:
    name: str
    id: str


def list_input_devices() -> list[AudioDevice]:
    import sounddevice as sd
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] <= 0:
            continue
        name = d['name']
        if sys.platform != 'darwin':
            lower = name.lower()
            if any(skip in lower for skip in ['monitor', 'loopback']):
                continue
        devices.append(AudioDevice(name=name, id=str(i)))
    return devices


def list_output_devices() -> list[AudioDevice]:
    if sys.platform == 'darwin':
        return []
    return _list_linux_sinks()


def _list_linux_sinks() -> list[AudioDevice]:
    try:
        result = subprocess.run(
            ['pactl', 'list', 'sinks', 'short'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            devices = []
            for line in result.stdout.strip().splitlines():
                parts = line.split('\t')
                if len(parts) >= 2:
                    devices.append(AudioDevice(name=parts[1], id=parts[1]))
            return devices
    except FileNotFoundError:
        pass
    return []

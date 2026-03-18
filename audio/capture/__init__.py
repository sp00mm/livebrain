import sys
from typing import Optional


def create_mic_capture(device: Optional[str] = None):
    if sys.platform == 'darwin':
        from .macos import MacOSMicCapture
        return MacOSMicCapture()
    from .linux import LinuxMicCapture
    return LinuxMicCapture(device=device)


def create_system_capture(device: Optional[str] = None):
    if sys.platform == 'darwin':
        from .macos import MacOSSystemCapture
        return MacOSSystemCapture()
    from .linux import LinuxSystemCapture
    return LinuxSystemCapture(sink=device)

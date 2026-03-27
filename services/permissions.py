import os
import sys

from services.embedder import Embedder
from services.secrets import secrets


def check_microphone() -> bool:
    if sys.platform != 'darwin':
        return True
    import AVFoundation as AVF
    status = AVF.AVCaptureDevice.authorizationStatusForMediaType_(AVF.AVMediaTypeAudio)
    return status == 3


def check_speech_recognition() -> bool:
    if sys.platform != 'darwin':
        return True
    import Speech as SF
    status = SF.SFSpeechRecognizer.authorizationStatus()
    return status == 3


def check_screen_recording(callback):
    if sys.platform != 'darwin':
        callback(True)
        return
    from ScreenCaptureKit import SCShareableContent
    def handler(content, error):
        callback(error is None)
    SCShareableContent.getShareableContentWithCompletionHandler_(handler)


def check_model_downloaded() -> bool:
    model_dir = Embedder.get_model_dir()
    return os.path.isfile(os.path.join(model_dir, 'onnx', 'model_q4.onnx'))


def check_vosk_model_downloaded() -> bool:
    if sys.platform == 'darwin':
        return True
    from audio.transcription.vosk_transcriber import _model_dir
    return os.path.isdir(_model_dir())


def check_api_key() -> bool:
    return bool(secrets.get('openai_api_key'))


def request_microphone(callback):
    if sys.platform != 'darwin':
        callback(True)
        return
    import AVFoundation as AVF
    AVF.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        AVF.AVMediaTypeAudio, callback
    )


def request_speech_recognition(callback):
    if sys.platform != 'darwin':
        callback(True)
        return
    import subprocess
    subprocess.Popen(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_SpeechRecognition'])
    callback(False)


def request_screen_recording(callback):
    check_screen_recording(callback)

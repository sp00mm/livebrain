import sys


def create_transcriber():
    if sys.platform == 'darwin':
        from .apple_speech import AppleSpeechTranscriber
        return AppleSpeechTranscriber()
    from .vosk_transcriber import VoskTranscriber
    return VoskTranscriber()


def create_subprocess_transcriber():
    if sys.platform == 'darwin':
        from .subprocess_transcriber import SubprocessTranscriber
        return SubprocessTranscriber()
    from .vosk_transcriber import VoskTranscriber
    return VoskTranscriber()

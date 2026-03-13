import sys
from multiprocessing import Process, Queue
from threading import Thread
from typing import Callable, Optional

from audio.interfaces import Transcriber


def _transcriber_worker(audio_queue: Queue, result_queue: Queue):
    from threading import Thread
    from Foundation import NSRunLoop, NSDate
    from audio.transcription.apple_speech import AppleSpeechTranscriber

    transcriber = AppleSpeechTranscriber()
    running = True

    def on_result(text: str, confidence: float, is_final: bool):
        result_queue.put((text, confidence, is_final))

    transcriber.start(on_result)

    def audio_reader():
        nonlocal running
        while running:
            msg = audio_queue.get()
            if msg is None:
                running = False
                break
            transcriber.feed_audio(msg)

    reader = Thread(target=audio_reader, daemon=True)
    reader.start()

    run_loop = NSRunLoop.currentRunLoop()
    while running:
        run_loop.runMode_beforeDate_('kCFRunLoopDefaultMode', NSDate.dateWithTimeIntervalSinceNow_(0.1))

    transcriber.stop()


class SubprocessTranscriber(Transcriber):

    def __init__(self):
        self._process: Optional[Process] = None
        self._audio_queue: Optional[Queue] = None
        self._result_queue: Optional[Queue] = None
        self._reader_thread: Optional[Thread] = None
        self._on_result: Optional[Callable[[str, float, bool], None]] = None
        self._running = False

    def is_available(self) -> bool:
        if sys.platform != 'darwin':
            return False
        from audio.transcription.apple_speech import AppleSpeechTranscriber
        return AppleSpeechTranscriber().is_available()

    def request_permission(self, callback: Callable[[bool], None]) -> None:
        from audio.transcription.apple_speech import AppleSpeechTranscriber
        AppleSpeechTranscriber().request_permission(callback)

    def start(self, on_result: Callable[[str, float, bool], None]) -> None:
        if self._running:
            return

        self._on_result = on_result
        self._audio_queue = Queue()
        self._result_queue = Queue()

        self._process = Process(
            target=_transcriber_worker,
            args=(self._audio_queue, self._result_queue)
        )
        self._process.start()

        self._running = True
        self._reader_thread = Thread(target=self._read_results, daemon=True)
        self._reader_thread.start()

    def feed_audio(self, audio_data: bytes) -> None:
        if self._running and self._audio_queue:
            self._audio_queue.put(audio_data)

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._audio_queue:
            self._audio_queue.put(None)

        if self._process:
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None

        self._audio_queue = None
        self._result_queue = None
        self._on_result = None

    def _read_results(self):
        from queue import Empty
        while self._running and self._result_queue:
            try:
                result = self._result_queue.get(timeout=0.1)
            except Empty:
                continue
            if result and self._on_result:
                text, confidence, is_final = result
                self._on_result(text, confidence, is_final)

import struct
import sys
from typing import Callable, Optional

from audio.interfaces import AudioCaptureSource

if sys.platform != 'darwin':
    raise ImportError('macOS audio capture requires macOS')

import objc
import AVFoundation as AVF
import CoreMedia
from Foundation import NSObject


class MacOSMicCapture(AudioCaptureSource):
    BUFFER_SIZE = 4096

    def __init__(self):
        self.on_audio: Optional[Callable[[bytes, float], None]] = None
        self._engine: Optional[AVF.AVAudioEngine] = None
        self._running = False
        self._sample_rate = 48000.0
        self._tap_block = None

    def is_available(self) -> bool:
        return AVF.AVAudioSession is not None

    def request_permission(self, callback: Callable[[bool], None]) -> None:
        AVF.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVF.AVMediaTypeAudio, callback
        )

    def start(self) -> None:
        if self._running:
            return

        self._engine = AVF.AVAudioEngine.alloc().init()
        input_node = self._engine.inputNode()
        bus = 0

        native_format = input_node.outputFormatForBus_(bus)
        self._sample_rate = native_format.sampleRate()

        def tap_block(buffer, when):
            if not self.on_audio:
                return
            frame_length = buffer.frameLength()
            float_data = buffer.floatChannelData()
            if not float_data:
                return
            channel_data = float_data[0]
            floats = [channel_data[i] for i in range(frame_length)]
            audio_bytes = struct.pack(f'{frame_length}f', *floats)
            timestamp = when.sampleTime() / self._sample_rate
            self.on_audio(audio_bytes, timestamp)

        self._tap_block = tap_block  # prevent garbage collection

        input_node.installTapOnBus_bufferSize_format_block_(
            bus, self.BUFFER_SIZE, native_format, self._tap_block
        )

        self._engine.startAndReturnError_(None)
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        if self._engine:
            self._engine.inputNode().removeTapOnBus_(0)
            self._engine.stop()
            self._engine = None
        self._running = False


class SCStreamOutputDelegate(NSObject):
    def init(self):
        self = objc.super(SCStreamOutputDelegate, self).init()
        if self is None:
            return None
        self.on_audio = None
        return self

    @objc.signature(b'v@:@@q')  # void, self, _cmd, SCStream*, CMSampleBufferRef, SCStreamOutputType (int64)
    def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
        if output_type != 1:  # SCStreamOutputTypeAudio = 1
            return
        if not self.on_audio:
            return

        block_buffer = CoreMedia.CMSampleBufferGetDataBuffer(sample_buffer)
        if not block_buffer:
            return

        length = CoreMedia.CMBlockBufferGetDataLength(block_buffer)
        data = bytearray(length)
        CoreMedia.CMBlockBufferCopyDataBytes(block_buffer, 0, length, data)

        pts = CoreMedia.CMSampleBufferGetPresentationTimeStamp(sample_buffer)
        timestamp = CoreMedia.CMTimeGetSeconds(pts)

        self.on_audio(bytes(data), timestamp)


class MacOSSystemCapture(AudioCaptureSource):
    SAMPLE_RATE = 48000

    def __init__(self):
        self.on_audio: Optional[Callable[[bytes, float], None]] = None
        self._stream = None
        self._delegate = None
        self._running = False

    def is_available(self) -> bool:
        try:
            import ScreenCaptureKit
            return True
        except ImportError:
            return False

    def request_permission(self, callback: Callable[[bool], None]) -> None:
        try:
            import ScreenCaptureKit as SCK
            def handler(content, error):
                callback(content is not None)
            SCK.SCShareableContent.getShareableContentWithCompletionHandler_(handler)
        except ImportError:
            callback(False)

    def start(self) -> None:
        if self._running:
            return

        import ScreenCaptureKit as SCK

        self._delegate = SCStreamOutputDelegate.alloc().init()
        self._delegate.on_audio = self._handle_audio

        def content_handler(content, error):
            if error or not content:
                return

            displays = content.displays()
            if not displays:
                return

            display = displays[0]
            self._filter = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])

            self._config = SCK.SCStreamConfiguration.alloc().init()
            self._config.setCapturesAudio_(True)
            self._config.setExcludesCurrentProcessAudio_(True)
            self._config.setSampleRate_(self.SAMPLE_RATE)
            self._config.setChannelCount_(1)

            self._stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
                self._filter, self._config, None
            )

            if not self._stream:
                return

            self._stream.addStreamOutput_type_sampleHandlerQueue_error_(
                self._delegate, 1, None, None  # SCStreamOutputTypeAudio = 1
            )

            def start_handler(error):
                if error:
                    self._running = False

            self._stream.startCaptureWithCompletionHandler_(start_handler)
            self._running = True

        self._content_handler = content_handler  # prevent GC
        SCK.SCShareableContent.getShareableContentWithCompletionHandler_(self._content_handler)

    def _handle_audio(self, audio_data: bytes, timestamp: float) -> None:
        if self.on_audio:
            self.on_audio(audio_data, timestamp)

    def stop(self) -> None:
        if not self._running:
            return
        if self._stream:
            self._stream.stopCaptureWithCompletionHandler_(lambda e: None)
            self._stream = None
        self._delegate = None
        self._running = False

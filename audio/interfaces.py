from abc import ABC, abstractmethod
from typing import Callable, Optional


class AudioCaptureSource(ABC):
    on_audio: Optional[Callable[[bytes, float], None]] = None

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def request_permission(self, callback: Callable[[bool], None]) -> None:
        pass


class Transcriber(ABC):
    @abstractmethod
    def start(self, on_result: Callable[[str, float, bool], None]) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def feed_audio(self, audio_data: bytes) -> None:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def request_permission(self, callback: Callable[[bool], None]) -> None:
        pass

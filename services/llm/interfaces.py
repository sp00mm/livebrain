from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generator, Optional

from models import ModelConfig


@dataclass
class Message:
    role: str  # 'user', 'assistant', 'system'
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0


StreamCallback = Callable[[str, bool], None]  # (delta, is_final)


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[Message], config: ModelConfig,
                 system_prompt: Optional[str] = None,
                 tools: Optional[list[dict]] = None) -> LLMResponse:
        pass

    @abstractmethod
    def stream(self, messages: list[Message], config: ModelConfig,
               system_prompt: Optional[str] = None,
               on_delta: Optional[StreamCallback] = None,
               tools: Optional[list[dict]] = None) -> Generator[str, None, LLMResponse]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

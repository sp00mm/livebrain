from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Generator, Optional


@dataclass
class Message:
    role: str
    content: str | list[dict]


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    output_items: list = field(default_factory=list)


StreamCallback = Callable[[str, bool], None]


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[Message], model: str,
                 system_prompt: Optional[str] = None,
                 tools: Optional[list[dict]] = None,
                 extra_input: Optional[list[dict]] = None) -> LLMResponse:
        pass

    @abstractmethod
    def stream(self, messages: list[Message], model: str,
               system_prompt: Optional[str] = None,
               on_delta: Optional[StreamCallback] = None,
               tools: Optional[list[dict]] = None,
               extra_input: Optional[list[dict]] = None) -> Generator[str, None, LLMResponse]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

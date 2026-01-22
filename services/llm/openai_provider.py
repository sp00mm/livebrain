from typing import Generator, Optional

from openai import OpenAI

from models import ModelConfig
from .interfaces import LLMProvider, Message, LLMResponse, StreamCallback


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def complete(self, messages: list[Message], config: ModelConfig,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        response = self._client.responses.create(
            model=config.model,
            input=self._build_input(messages),
            instructions=system_prompt,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )
        return LLMResponse(
            text=response.output_text,
            model=config.model,
            tokens_input=response.usage.input_tokens if response.usage else 0,
            tokens_output=response.usage.output_tokens if response.usage else 0,
        )

    def stream(self, messages: list[Message], config: ModelConfig,
               system_prompt: Optional[str] = None,
               on_delta: Optional[StreamCallback] = None) -> Generator[str, None, LLMResponse]:
        stream = self._client.responses.create(
            model=config.model,
            input=self._build_input(messages),
            instructions=system_prompt,
            stream=True,
        )
        full_text = ''
        usage = None
        for event in stream:
            if event.type == 'response.output_text.delta':
                full_text += event.delta
                yield event.delta
                if on_delta:
                    on_delta(event.delta, False)
            elif event.type == 'response.completed':
                usage = getattr(event.response, 'usage', None)
                if on_delta:
                    on_delta('', True)
        return LLMResponse(
            text=full_text,
            model=config.model,
            tokens_input=usage.input_tokens if usage else 0,
            tokens_output=usage.output_tokens if usage else 0
        )

    def _build_input(self, messages: list[Message]) -> list[dict]:
        return [{'role': msg.role, 'content': msg.content} for msg in messages]

    def is_available(self) -> bool:
        return self._client is not None

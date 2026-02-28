from typing import Generator, Optional

from ..database import Database
from .interfaces import LLMProvider, Message, LLMResponse, StreamCallback
from .openai_provider import OpenAIProvider

DEFAULT_MODEL = 'gpt-5-chat-latest'


class LLMService:
    def __init__(self, db: Database):
        self.db = db
        self._providers: dict[str, LLMProvider] = {}

    def get_provider(self, name: str = 'openai') -> LLMProvider:
        if name not in self._providers:
            self._providers[name] = self._create_provider(name)
        return self._providers[name]

    def complete(self, messages: list[Message],
                 system_prompt: Optional[str] = None,
                 tools: Optional[list[dict]] = None) -> LLMResponse:
        provider = self.get_provider('openai')
        return provider.complete(messages, DEFAULT_MODEL, system_prompt, tools)

    def stream(self, messages: list[Message],
               system_prompt: Optional[str] = None,
               on_delta: Optional[StreamCallback] = None,
               tools: Optional[list[dict]] = None) -> Generator[str, None, LLMResponse]:
        provider = self.get_provider('openai')
        return provider.stream(messages, DEFAULT_MODEL, system_prompt, on_delta, tools)

    def _create_provider(self, name: str) -> LLMProvider:
        api_key = self._get_api_key()
        if name == 'openai':
            return OpenAIProvider(api_key)
        raise ValueError(f'Unknown provider: {name}')

    def _get_api_key(self) -> str:
        from services.secrets import secrets
        return secrets.get('openai_api_key') or ''

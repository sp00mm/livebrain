from typing import Generator, Optional

from models import ModelConfig
from ..database import Database, UserSettingsRepository
from .interfaces import LLMProvider, Message, LLMResponse, StreamCallback
from .openai_provider import OpenAIProvider


class LLMService:
    def __init__(self, db: Database):
        self.db = db
        self._settings_repo = UserSettingsRepository(db)
        self._providers: dict[str, LLMProvider] = {}

    def get_provider(self, name: str = 'openai') -> LLMProvider:
        if name not in self._providers:
            self._providers[name] = self._create_provider(name)
        return self._providers[name]

    def complete(self, messages: list[Message], config: Optional[ModelConfig] = None,
                 system_prompt: Optional[str] = None) -> LLMResponse:
        config = config or self._default_config()
        provider = self._provider_for_model(config.model)
        return provider.complete(messages, config, system_prompt)

    def stream(self, messages: list[Message], config: Optional[ModelConfig] = None,
               system_prompt: Optional[str] = None,
               on_delta: Optional[StreamCallback] = None) -> Generator[str, None, LLMResponse]:
        config = config or self._default_config()
        provider = self._provider_for_model(config.model)
        return provider.stream(messages, config, system_prompt, on_delta)

    def _create_provider(self, name: str) -> LLMProvider:
        api_key = self._get_api_key()
        if name == 'openai':
            return OpenAIProvider(api_key)
        raise ValueError(f'Unknown provider: {name}')

    def _provider_for_model(self, model: str) -> LLMProvider:
        return self.get_provider('openai')

    def _default_config(self) -> ModelConfig:
        settings = self._settings_repo.get()
        return ModelConfig(model=settings.preferred_model)

    def _get_api_key(self) -> str:
        settings = self._settings_repo.get()
        return settings.api_key_encrypted or ''

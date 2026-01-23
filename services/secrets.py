from abc import ABC, abstractmethod
from typing import Optional

import keyring


SERVICE_NAME = 'LiveBrain'


class SecretsStore(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set(self, key: str, value: str):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass


class KeychainStore(SecretsStore):
    def get(self, key: str) -> Optional[str]:
        return keyring.get_password(SERVICE_NAME, key)

    def set(self, key: str, value: str):
        keyring.set_password(SERVICE_NAME, key, value)

    def delete(self, key: str):
        keyring.delete_password(SERVICE_NAME, key)


secrets = KeychainStore()

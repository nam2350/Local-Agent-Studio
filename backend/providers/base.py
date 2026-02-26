from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    """Abstract base class for all model providers."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider type identifier: ollama | lmstudio | llamacpp | transformers | simulation"""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier used by this provider."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream text tokens from the model."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable/ready."""
        pass

    async def list_models(self) -> list[str]:
        return []

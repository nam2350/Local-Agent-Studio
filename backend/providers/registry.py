"""Provider registry — factory + health checks for all backends."""

import asyncio
import logging
from typing import Dict, Optional

from .base import BaseProvider
from .openai_compat import OpenAICompatProvider, DEFAULT_URLS

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}

    def register(self, key: str, provider: BaseProvider) -> None:
        self._providers[key] = provider

    def get(self, key: str) -> Optional[BaseProvider]:
        return self._providers.get(key)

    def get_openai_compat(
        self,
        provider_type: str,
        model: str,
        base_url: Optional[str] = None,
    ) -> Optional[BaseProvider]:
        url = base_url or DEFAULT_URLS.get(provider_type)
        if not url:
            return None
        key = f"{provider_type}:{model}"
        if key not in self._providers:
            self._providers[key] = OpenAICompatProvider(
                base_url=url, model=model, provider_type=provider_type
            )
        return self._providers[key]

    def get_transformers(self, model_id: str, device: str = "auto") -> BaseProvider:
        """fp16 TransformersProvider 인스턴스 반환 (캐싱)."""
        from .transformers_provider import TransformersProvider

        key = f"transformers:{model_id}"
        if key not in self._providers:
            self._providers[key] = TransformersProvider(model_id=model_id, device=device)
        return self._providers[key]

    def unload_transformers(self, model_id: str) -> bool:
        """특정 Transformers 모델을 registry + GPU 캐시에서 제거."""
        from .transformers_provider import unload_model

        self._providers.pop(f"transformers:{model_id}", None)
        return unload_model(model_id)

    def unload_all_transformers(self) -> list:
        """모든 Transformers 모델을 언로드. 제거된 model_id 목록 반환."""
        from .transformers_provider import unload_all_models

        keys = [k for k in self._providers if k.startswith("transformers:")]
        for k in keys:
            del self._providers[k]
        return unload_all_models()

    async def health_check_all(self) -> Dict[str, bool]:
        """Check default provider endpoints + any registered providers."""
        results: Dict[str, bool] = {}

        # Check default OpenAI-compat endpoints
        checks = {
            name: OpenAICompatProvider(url, "test", name)
            for name, url in DEFAULT_URLS.items()
        }
        tasks = {name: p.health_check() for name, p in checks.items()}
        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, result in zip(tasks.keys(), done):
            results[name] = bool(result) if not isinstance(result, Exception) else False

        # Transformers is always available if torch is installed
        try:
            import torch  # noqa: F401
            results["transformers"] = True
        except ImportError:
            results["transformers"] = False

        return results

    async def list_models_all(self) -> Dict[str, list]:
        """List available models from each reachable OpenAI-compat endpoint."""
        results: Dict[str, list] = {}
        for name, url in DEFAULT_URLS.items():
            p = OpenAICompatProvider(url, "test", name)
            if await p.health_check():
                results[name] = await p.list_models()
            else:
                results[name] = []
        return results


# Singleton
registry = ProviderRegistry()

"""OpenAI-compatible provider: supports Ollama, LM Studio, llama-cpp-python server."""

import json
import logging
from typing import AsyncGenerator

import httpx

from .base import BaseProvider

logger = logging.getLogger(__name__)

DEFAULT_URLS = {
    "ollama":    "http://localhost:11434",
    "lmstudio":  "http://localhost:1234",
    "llamacpp":  "http://localhost:8080",
}


class OpenAICompatProvider(BaseProvider):
    def __init__(self, base_url: str, model: str, provider_type: str = "ollama"):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._ptype = provider_type

    @property
    def provider_type(self) -> str:
        return self._ptype

    @property
    def model_id(self) -> str:
        return self._model

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/v1/models")
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []

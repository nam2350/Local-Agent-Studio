"""Provider registry — factory + health checks for all backends.
Phase 19: ModelMeta dataclass + ModelWatcher singleton for real-time model discovery.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import httpx

from .base import BaseProvider
from .openai_compat import OpenAICompatProvider, DEFAULT_URLS  # DEFAULT_URLS: env-aware URL map

logger = logging.getLogger(__name__)


# ─── ModelMeta ────────────────────────────────────────────────────────────────

@dataclass
class ModelMeta:
    """모델 메타데이터. Ollama는 /api/tags로 풍부한 정보 제공, LMStudio는 id만."""
    model_id: str
    provider: str
    size_bytes: int = 0
    family: str = ""
    parameter_size: str = ""
    quantization: str = ""
    format: str = ""


# ─── ModelWatcher ─────────────────────────────────────────────────────────────

class ModelWatcher:
    """
    Singleton. 3초마다 Ollama(/api/tags) + LMStudio(/v1/models)를 폴링하여
    모델 추가/제거 이벤트를 모든 구독 큐에 브로드캐스트한다.
    """

    _instance: Optional["ModelWatcher"] = None

    def __init__(self, poll_interval: float = 3.0):
        self._interval = poll_interval
        self._known: Dict[str, List[ModelMeta]] = {}  # provider → [ModelMeta]
        self._queues: List[asyncio.Queue] = []         # SSE 클라이언트 큐 목록
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_instance(cls) -> "ModelWatcher":
        if cls._instance is None:
            cls._instance = ModelWatcher()
        return cls._instance

    def subscribe(self) -> "asyncio.Queue[dict]":
        """SSE 클라이언트 연결 시 새 큐를 등록하고 반환."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue") -> None:
        """SSE 연결 종료 시 큐 제거."""
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def start(self) -> None:
        """백그라운드 폴링 태스크 시작 (중복 실행 방지)."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("ModelWatcher started (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def get_current_models(self) -> Dict[str, List[dict]]:
        """현재 알려진 모델 목록 반환 (SSE 연결 직후 스냅샷 전송용)."""
        return {
            provider: [asdict(m) for m in metas]
            for provider, metas in self._known.items()
        }

    # ── 내부 메서드 ────────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._poll_once()
            except Exception as e:
                logger.debug("ModelWatcher poll error: %s", e)
            await asyncio.sleep(self._interval)

    async def _get_http_client(self) -> httpx.AsyncClient:
        """재사용 가능한 httpx 클라이언트 반환 (매 폴링마다 새로 생성하지 않음)."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=3.0)
        return self._http_client

    async def _poll_once(self) -> None:
        """Ollama /api/tags + LMStudio /v1/models 조회 후 diff 계산."""
        current: Dict[str, List[ModelMeta]] = {}
        client = await self._get_http_client()

        # ── Ollama: /api/tags (메타데이터 풍부) ──────────────────────────────
        try:
            resp = await client.get(f"{DEFAULT_URLS['ollama']}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                metas: List[ModelMeta] = []
                for m in data.get("models", []):
                    details = m.get("details", {})
                    metas.append(ModelMeta(
                        model_id=m.get("name", m.get("model", "")),
                        provider="ollama",
                        size_bytes=m.get("size", 0),
                        family=details.get("family", ""),
                        parameter_size=details.get("parameter_size", ""),
                        quantization=details.get("quantization_level", ""),
                        format=details.get("format", "gguf"),
                    ))
                current["ollama"] = metas
            else:
                current["ollama"] = list(self._known.get("ollama", []))
        except Exception:
            # 연결 실패 시 기존 유지 — 일시적 다운으로 인한 model_removed 오발 방지
            current["ollama"] = list(self._known.get("ollama", []))

        # ── LMStudio: /v1/models (id만 제공) ─────────────────────────────────
        try:
            resp = await client.get(f"{DEFAULT_URLS['lmstudio']}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                current["lmstudio"] = [
                    ModelMeta(model_id=m["id"], provider="lmstudio")
                    for m in data.get("data", [])
                ]
            else:
                current["lmstudio"] = list(self._known.get("lmstudio", []))
        except Exception:
            current["lmstudio"] = list(self._known.get("lmstudio", []))

        # ── Diff 계산 (lock 내부) + 이벤트 수집, broadcast는 lock 밖 ─────────
        events_to_broadcast: list[dict] = []
        async with self._lock:
            for provider, metas in current.items():
                prev_ids = {m.model_id for m in self._known.get(provider, [])}
                curr_ids = {m.model_id for m in metas}

                for meta in metas:
                    if meta.model_id not in prev_ids:
                        events_to_broadcast.append({
                            "type": "model_added",
                            "provider": provider,
                            "model_id": meta.model_id,
                            "meta": asdict(meta),
                            "timestamp": time.time(),
                        })

                for model_id in prev_ids - curr_ids:
                    events_to_broadcast.append({
                        "type": "model_removed",
                        "provider": provider,
                        "model_id": model_id,
                        "timestamp": time.time(),
                    })

            self._known = current

        # lock 밖에서 broadcast — 다른 subscribe/unsubscribe가 블로킹되지 않음
        for ev in events_to_broadcast:
            await self._broadcast(ev)

    async def _broadcast(self, event: dict) -> None:
        """등록된 모든 큐에 이벤트 전송. 가득 찬 큐는 skip."""
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("SSE queue full, skipping client")


# ─── ProviderRegistry ─────────────────────────────────────────────────────────

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

        checks = {
            name: OpenAICompatProvider(url, "test", name)
            for name, url in DEFAULT_URLS.items()
        }
        tasks = {name: p.health_check() for name, p in checks.items()}
        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, result in zip(tasks.keys(), done):
            results[name] = bool(result) if not isinstance(result, Exception) else False

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

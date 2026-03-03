"""HuggingFace Transformers provider — fp16, bitsandbytes 없음.

Phase 16 변경사항:
- BitsAndBytesConfig (4-bit/8-bit) 제거 → fp16 고정
- attn_implementation="sdpa" 우선 시도, 실패 시 기본 attention으로 fallback
- VRAM 실측 static 메서드 (get_vram_allocated_gb, get_vram_info)
- 모듈 레벨 unload_model() / unload_all_models() 함수
- Thread 내 CUDA OOM → asyncio 루프로 에러 시그널 전파 개선
"""

import asyncio
import gc
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import AsyncGenerator

from .base import BaseProvider

logger = logging.getLogger(__name__)

# 모듈 레벨 캐시: model_id → model / tokenizer
_model_cache: dict = {}
_tokenizer_cache: dict = {}
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="transformers")


# ── VRAM 유틸리티 ──────────────────────────────────────────────────────────────

def _get_torch():
    try:
        import torch
        return torch
    except ImportError:
        return None


def _vram_allocated_gb() -> float:
    t = _get_torch()
    if t and t.cuda.is_available():
        return round(t.cuda.memory_allocated() / 1024 ** 3, 3)
    return 0.0


# ── 언로드 함수 ────────────────────────────────────────────────────────────────

def unload_model(model_id: str) -> bool:
    """캐시에서 모델을 제거하고 GPU 메모리를 해제. 성공 시 True."""
    if model_id not in _model_cache:
        return False

    model = _model_cache.pop(model_id)
    _tokenizer_cache.pop(model_id, None)

    try:
        model.cpu()
    except Exception:
        pass
    del model
    gc.collect()

    t = _get_torch()
    if t and t.cuda.is_available():
        t.cuda.empty_cache()

    logger.info(
        "[Transformers] Unloaded '%s' | VRAM now: %.2f GB",
        model_id, _vram_allocated_gb(),
    )
    return True


def unload_all_models() -> list:
    """모든 캐시 모델을 언로드. 제거된 model_id 목록 반환."""
    ids = list(_model_cache.keys())
    for mid in ids:
        unload_model(mid)
    return ids


# ── Provider 클래스 ────────────────────────────────────────────────────────────

class TransformersProvider(BaseProvider):

    def __init__(self, model_id: str, device: str = "auto"):
        self._model_id = model_id
        self._device = device

    # ── BaseProvider 인터페이스 ────────────────────────────────────────────────

    @property
    def provider_type(self) -> str:
        return "transformers"

    @property
    def model_id(self) -> str:
        return self._model_id

    # ── VRAM 실측 (static) ────────────────────────────────────────────────────

    @staticmethod
    def get_vram_allocated_gb() -> float:
        """현재 GPU VRAM 사용량을 GB 단위로 반환. CUDA 없으면 0.0."""
        return _vram_allocated_gb()

    @staticmethod
    def get_vram_info() -> dict:
        """allocated / reserved / total / free (GB) 딕셔너리 반환."""
        t = _get_torch()
        if t and t.cuda.is_available():
            try:
                alloc    = t.cuda.memory_allocated()
                reserved = t.cuda.memory_reserved()
                total    = t.cuda.get_device_properties(0).total_memory
                return {
                    "allocated_gb": round(alloc    / 1024 ** 3, 3),
                    "reserved_gb":  round(reserved / 1024 ** 3, 3),
                    "total_gb":     round(total    / 1024 ** 3, 3),
                    "free_gb":      round((total - alloc) / 1024 ** 3, 3),
                }
            except Exception as e:
                logger.warning("[Transformers] VRAM info error: %s", e)
        return {"allocated_gb": 0.0, "reserved_gb": 0.0, "total_gb": 0.0, "free_gb": 0.0}

    # ── 내부 유틸 ─────────────────────────────────────────────────────────────

    def _resolve_load_path(self) -> str:
        """로컬 backend/models/ 경로를 우선 탐색, 없으면 HF model_id 그대로 사용."""
        try:
            from config import resolve_model_path
            path = resolve_model_path(self._model_id)
            if path != self._model_id:
                logger.info("[Transformers] Using local model: %s", path)
            return path
        except ImportError:
            return self._model_id

    def _load_model(self):
        """fp16 + SDPA로 모델 로드 (blocking — Thread 내에서 실행)."""
        if self._model_id in _model_cache:
            return _model_cache[self._model_id], _tokenizer_cache[self._model_id]

        load_path = self._resolve_load_path()
        logger.info(
            "[Transformers] Loading '%s' from '%s' (fp16) ...",
            self._model_id, load_path,
        )
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        tokenizer = AutoTokenizer.from_pretrained(load_path, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        base_kwargs: dict = {
            "device_map": self._device,
            "trust_remote_code": True,
            "torch_dtype": torch.float16,
        }

        # SDPA 우선 시도, 미지원 모델이면 기본 attention으로 fallback
        try:
            model = AutoModelForCausalLM.from_pretrained(
                load_path, attn_implementation="sdpa", **base_kwargs
            )
            logger.info("[Transformers] '%s' loaded with SDPA attention", self._model_id)
        except (ValueError, TypeError, NotImplementedError) as e:
            logger.warning(
                "[Transformers] SDPA not supported (%s), falling back to default attention", e
            )
            model = AutoModelForCausalLM.from_pretrained(load_path, **base_kwargs)

        model.eval()
        _model_cache[self._model_id] = model
        _tokenizer_cache[self._model_id] = tokenizer
        logger.info(
            "[Transformers] '%s' loaded on %s | VRAM: %.2f GB",
            self._model_id, model.device, _vram_allocated_gb(),
        )
        return model, tokenizer

    # ── 스트리밍 생성 ─────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        from transformers import TextIteratorStreamer

        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue = asyncio.Queue()

        def run_generation():
            try:
                model, tokenizer = self._load_model()

                # 채팅 템플릿 적용
                if getattr(tokenizer, "chat_template", None):
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    text = tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                else:
                    text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

                inputs = tokenizer(
                    text, return_tensors="pt", truncation=True, max_length=2048
                )
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

                streamer = TextIteratorStreamer(
                    tokenizer, skip_special_tokens=True, skip_prompt=True
                )
                gen_kwargs = {
                    **inputs,
                    "max_new_tokens": max_tokens,
                    "do_sample": temperature > 0,
                    "temperature": temperature if temperature > 0 else 1.0,
                    "streamer": streamer,
                    "pad_token_id": tokenizer.eos_token_id,
                }

                gen_thread = Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
                gen_thread.start()

                for token_text in streamer:
                    if token_text:
                        future = asyncio.run_coroutine_threadsafe(
                            token_queue.put(token_text), loop
                        )
                        future.result(timeout=10.0)

            except Exception as e:
                logger.error("[Transformers] Generation error: %s", e, exc_info=True)
                # OOM 등 에러를 asyncio 루프로 전파
                try:
                    asyncio.run_coroutine_threadsafe(
                        token_queue.put(("__error__", str(e))), loop
                    ).result(timeout=5.0)
                except Exception:
                    pass
            finally:
                asyncio.run_coroutine_threadsafe(token_queue.put(None), loop)

        _executor.submit(run_generation)

        while True:
            token = await token_queue.get()
            if token is None:
                break
            if isinstance(token, tuple) and token[0] == "__error__":
                raise RuntimeError(token[1])
            yield token

    # ── 헬스체크 ─────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        t = _get_torch()
        if t is None:
            return False
        return t.cuda.is_available()

    async def list_models(self) -> list:
        return list(_model_cache.keys())

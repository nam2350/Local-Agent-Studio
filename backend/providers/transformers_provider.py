"""HuggingFace Transformers provider — runs models directly in-process via GPU."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import AsyncGenerator

from .base import BaseProvider

logger = logging.getLogger(__name__)

# Module-level cache: model_id → (model, tokenizer)
_model_cache: dict = {}
_tokenizer_cache: dict = {}
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="transformers")


class TransformersProvider(BaseProvider):
    def __init__(
        self,
        model_id: str,
        device: str = "auto",
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
    ):
        self._model_id = model_id
        self._device = device
        self._load_in_4bit = load_in_4bit
        self._load_in_8bit = load_in_8bit

    @property
    def provider_type(self) -> str:
        return "transformers"

    @property
    def model_id(self) -> str:
        return self._model_id

    def _resolve_load_path(self) -> str:
        """
        로컬 backend/models/<org>--<name>/ 경로를 우선 사용.
        로컬에 없으면 HF model_id 그대로 사용 (HF 캐시/다운로드 폴백).
        """
        try:
            from config import resolve_model_path
            path = resolve_model_path(self._model_id)
            if path != self._model_id:
                logger.info(f"[Transformers] Using local model: {path}")
            return path
        except ImportError:
            return self._model_id

    def _load_model(self):
        """Load model & tokenizer into cache (blocking — run in thread)."""
        if self._model_id in _model_cache:
            return _model_cache[self._model_id], _tokenizer_cache[self._model_id]

        load_path = self._resolve_load_path()
        logger.info(f"[Transformers] Loading {self._model_id} from {load_path} ...")
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        import torch

        tokenizer = AutoTokenizer.from_pretrained(
            load_path, trust_remote_code=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        kwargs: dict = {"device_map": self._device, "trust_remote_code": True}

        if self._load_in_4bit:
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
        elif self._load_in_8bit:
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            kwargs["torch_dtype"] = torch.float16

        model = AutoModelForCausalLM.from_pretrained(load_path, **kwargs)
        model.eval()

        _model_cache[self._model_id] = model
        _tokenizer_cache[self._model_id] = tokenizer
        logger.info(f"[Transformers] {self._model_id} loaded on {model.device}")
        return model, tokenizer

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

                # Build prompt using chat template if available
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
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=2048,
                )
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

                streamer = TextIteratorStreamer(
                    tokenizer,
                    skip_special_tokens=True,
                    skip_prompt=True,
                )

                gen_kwargs = {
                    **inputs,
                    "max_new_tokens": max_tokens,
                    "do_sample": temperature > 0,
                    "temperature": temperature if temperature > 0 else 1.0,
                    "streamer": streamer,
                    "pad_token_id": tokenizer.eos_token_id,
                }

                gen_thread = Thread(
                    target=model.generate, kwargs=gen_kwargs, daemon=True
                )
                gen_thread.start()

                for token_text in streamer:
                    if token_text:
                        future = asyncio.run_coroutine_threadsafe(
                            token_queue.put(token_text), loop
                        )
                        future.result(timeout=10.0)

            except Exception as e:
                logger.error(f"[Transformers] Generation error: {e}", exc_info=True)
            finally:
                asyncio.run_coroutine_threadsafe(token_queue.put(None), loop)

        _executor.submit(run_generation)

        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield token

    async def health_check(self) -> bool:
        try:
            import torch
            return True  # GPU or CPU available
        except ImportError:
            return False

    async def list_models(self) -> list[str]:
        return list(_model_cache.keys())

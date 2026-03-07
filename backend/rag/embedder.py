"""임베딩 모델 싱글톤 — SentenceTransformers all-MiniLM-L6-v2 (90MB, CPU 가능)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: "SentenceTransformer | None" = None


def get_embedder() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("[RAG] Loading embedding model all-MiniLM-L6-v2 ...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("[RAG] Embedding model loaded.")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    return get_embedder().encode(texts, convert_to_numpy=True).tolist()

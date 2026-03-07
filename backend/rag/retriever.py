"""RAG 검색 — 쿼리 임베딩 + ChromaDB 유사도 검색."""

from __future__ import annotations

import logging
from typing import Optional

from .embedder import embed
from .store import query, list_collections

logger = logging.getLogger(__name__)


def retrieve(
    collection_name: str,
    query_text: str,
    top_k: int = 5,
    min_score: float = 0.3,
) -> list[dict]:
    """컬렉션에서 쿼리와 가장 유사한 청크를 반환.

    Returns:
        [{text, source, score}, ...] — score 오름차순 내림차순 정렬 (높을수록 유사)
    """
    q_embedding = embed([query_text])[0]
    results = query(collection_name, q_embedding, top_k=top_k)
    filtered = [r for r in results if r["score"] >= min_score]
    logger.debug(
        "[RAG] retrieve '%s' → %d/%d chunks (min_score=%.2f)",
        query_text[:60], len(filtered), len(results), min_score,
    )
    return filtered


def build_rag_context(
    collection_name: str,
    query_text: str,
    top_k: int = 5,
    min_score: float = 0.3,
) -> Optional[str]:
    """검색 결과를 프롬프트 주입용 컨텍스트 문자열로 변환.

    Returns:
        None — 컬렉션 없음 or 결과 없음
        str  — 형식화된 컨텍스트 블록
    """
    chunks = retrieve(collection_name, query_text, top_k=top_k, min_score=min_score)
    if not chunks:
        return None

    lines = ["[KNOWLEDGE BASE CONTEXT]"]
    for i, c in enumerate(chunks, 1):
        lines.append(f"\n[{i}] Source: {c['source']} (score={c['score']})")
        lines.append(c["text"])
    lines.append("\n[END KNOWLEDGE BASE CONTEXT]")
    return "\n".join(lines)

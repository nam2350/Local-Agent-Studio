"""ChromaDB 컬렉션 관리 — 싱글톤 client + 컬렉션 CRUD."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

# ChromaDB 영속 경로: backend/rag_data/
_DB_PATH = Path(__file__).parent.parent / "rag_data"
_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(_DB_PATH))
        logger.info("[RAG] ChromaDB initialized at %s", _DB_PATH)
    return _client


def list_collections() -> list[dict]:
    """모든 컬렉션 이름 + 문서 수 반환."""
    client = get_client()
    result = []
    for col in client.list_collections():
        try:
            count = client.get_collection(col.name).count()
        except Exception:
            count = 0
        result.append({"name": col.name, "count": count})
    return result


def get_or_create(name: str) -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def delete_collection(name: str) -> bool:
    try:
        get_client().delete_collection(name)
        return True
    except Exception:
        return False


def add_chunks(
    collection_name: str,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    col = get_or_create(collection_name)
    col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def query(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """유사도 검색 → [{text, source, score}, ...]"""
    try:
        col = get_client().get_collection(collection_name)
    except Exception:
        return []

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "score": round(1 - dist, 4),  # cosine distance → similarity
        })
    return chunks

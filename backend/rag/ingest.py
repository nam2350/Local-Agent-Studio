"""문서 파싱 + 청크 분할 + ChromaDB 인제스트.

지원 형식: PDF (.pdf), 텍스트 (.txt, .md, .py, .ts, .tsx, .js, .json, .csv)
청크 전략: 512토큰 윈도우, 50토큰 overlap (단어 기준 근사)
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import AsyncGenerator

from .embedder import embed
from .store import add_chunks

logger = logging.getLogger(__name__)

CHUNK_SIZE    = 400  # 단어 수 기준
CHUNK_OVERLAP = 50


def _parse_pdf(path: Path) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(pages)


def _parse_text(path: Path) -> str:
    import chardet
    raw = path.read_bytes()
    enc = chardet.detect(raw).get("encoding") or "utf-8"
    return raw.decode(enc, errors="replace")


def _parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    return _parse_text(path)


def _split_chunks(text: str, source: str) -> list[dict]:
    """단어 단위로 슬라이딩 윈도우 청크 분할."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        chunk_text = " ".join(words[start:end])
        chunk_text = re.sub(r"\s+", " ", chunk_text).strip()
        if chunk_text:
            uid = hashlib.md5(f"{source}:{start}".encode()).hexdigest()
            chunks.append({"id": uid, "text": chunk_text, "source": source, "start": start})
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


async def ingest_file(
    collection_name: str,
    file_path: Path,
    source_name: str,
) -> AsyncGenerator[dict, None]:
    """파일을 파싱 → 청크 → 임베딩 → ChromaDB 저장. 진행률 이벤트를 yield."""
    import asyncio

    yield {"type": "rag_parse", "file": source_name}

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(None, lambda: _parse_file(file_path))
    except Exception as e:
        yield {"type": "rag_error", "message": f"Parse failed: {e}"}
        return

    if not text.strip():
        yield {"type": "rag_error", "message": "File is empty or unreadable"}
        return

    chunks = _split_chunks(text, source_name)
    total = len(chunks)
    yield {"type": "rag_chunks", "total": total, "file": source_name}

    BATCH = 32
    stored = 0
    for i in range(0, total, BATCH):
        batch = chunks[i : i + BATCH]
        texts  = [c["text"] for c in batch]
        embeddings = await loop.run_in_executor(None, lambda t=texts: embed(t))
        ids    = [c["id"] for c in batch]
        metas  = [{"source": c["source"], "start": c["start"]} for c in batch]
        await loop.run_in_executor(None, lambda: add_chunks(collection_name, ids, embeddings, texts, metas))
        stored += len(batch)
        yield {"type": "rag_progress", "stored": stored, "total": total, "pct": round(stored / total * 100, 1)}

    yield {"type": "rag_done", "file": source_name, "chunks": total}

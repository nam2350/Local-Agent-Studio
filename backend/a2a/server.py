"""A2A 서버 핸들러 — 외부 에이전트로부터 태스크를 수신하고 파이프라인을 실행."""

from __future__ import annotations

import json
import logging
import time as _time
import uuid
from collections import OrderedDict
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ─── A2A Task 저장소 (TTL + maxlen LRU) ──────────────────────────────────────

_TASK_TTL_SEC  = 3600   # 1시간 후 만료
_TASK_MAX_SIZE = 500    # 최대 보관 수


class _TaskStore:
    """maxlen + TTL을 지원하는 순서 유지 태스크 저장소."""

    def __init__(self, maxlen: int = _TASK_MAX_SIZE, ttl: float = _TASK_TTL_SEC):
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._maxlen = maxlen
        self._ttl = ttl

    def _evict_expired(self):
        now = _time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]

    def __setitem__(self, key: str, value: dict):
        self._evict_expired()
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (_time.time(), value)
        while len(self._store) > self._maxlen:
            self._store.popitem(last=False)

    def __getitem__(self, key: str) -> dict:
        self._evict_expired()
        return self._store[key][1]

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def values(self):
        self._evict_expired()
        return [v for _, v in self._store.values()]


_TASKS = _TaskStore()


def _new_task(skill_id: str, input_text: str, session_id: str | None) -> dict:
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "sessionId": session_id or task_id,
        "skillId": skill_id,
        "status": {"state": "submitted"},
        "artifacts": [],
        "history": [{"role": "user", "parts": [{"type": "text", "text": input_text}]}],
    }
    _TASKS[task_id] = task
    return task


def get_task(task_id: str) -> dict | None:
    return _TASKS.get(task_id)


def list_tasks() -> list[dict]:
    return list(_TASKS.values())


def cancel_task(task_id: str) -> bool:
    task = _TASKS.get(task_id)
    if not task:
        return False
    task["status"]["state"] = "canceled"
    return True


# ─── A2A 태스크 실행 ─────────────────────────────────────────────────────────

async def handle_task_send(payload: dict) -> AsyncGenerator[dict, None]:
    """
    `tasks/send` 엔드포인트 핸들러.
    파이프라인을 실행하고 A2A 이벤트 dict를 yield (SSE로 스트리밍).
    """
    skill_id = payload.get("skillId", "run_pipeline")
    session_id = payload.get("sessionId")
    parts = payload.get("message", {}).get("parts", [])
    input_text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()

    if not input_text:
        yield {"type": "error", "code": -32600, "message": "No text input provided"}
        return

    task = _new_task(skill_id, input_text, session_id)
    task_id = task["id"]

    # ── 태스크 접수 이벤트 ────────────────────────────────────────────────────
    task["status"]["state"] = "working"
    yield {
        "id": task_id,
        "sessionId": task["sessionId"],
        "status": task["status"],
    }

    # ── 스킬별 실행 ──────────────────────────────────────────────────────────
    try:
        if skill_id == "rag_query":
            yield await _handle_rag_query(task, payload)
        else:
            # 기본: run_pipeline
            async for event in _handle_pipeline(task, input_text):
                yield event
    except Exception as e:
        logger.exception("[A2A] Task %s failed: %s", task_id, e)
        task["status"]["state"] = "failed"
        task["status"]["message"] = {"role": "agent", "parts": [{"type": "text", "text": str(e)}]}
        yield {"id": task_id, "status": task["status"]}


async def _handle_pipeline(task: dict, prompt: str) -> AsyncGenerator[dict, None]:
    """파이프라인을 실행하고 최종 결과를 A2A artifact로 반환."""
    from pipeline.orchestrator import run_pipeline
    from pipeline.models import RunRequest, ProviderConfig

    req = RunRequest(
        prompt=prompt,
        use_real_models=False,
        default_provider=ProviderConfig(type="simulation"),
    )

    full_output: dict[str, str] = {}  # agent_id → output
    current_agent: str = ""
    agent_buf: str = ""

    async for chunk in run_pipeline(prompt, req):
        if not chunk.startswith("data: "):
            continue
        try:
            ev = json.loads(chunk[6:])
        except Exception:
            continue

        ev_type = ev.get("type", "")

        if ev_type == "agent_start":
            current_agent = ev.get("agentId", "")
            agent_buf = ""

        elif ev_type == "agent_token":
            agent_buf += ev.get("token", "")

        elif ev_type == "agent_done":
            if current_agent:
                full_output[current_agent] = agent_buf
            # 중간 진행 이벤트
            yield {
                "id": task["id"],
                "sessionId": task["sessionId"],
                "status": {
                    "state": "working",
                    "message": {
                        "role": "agent",
                        "parts": [{
                            "type": "text",
                            "text": f"[{current_agent}] done ({ev.get('totalTokens',0)} tokens)",
                        }],
                    },
                },
            }

        elif ev_type == "pipeline_done":
            # 최종 결과를 artifact로 첨부
            synthesizer_output = full_output.get("synthesizer-1", "") or next(iter(full_output.values()), "")
            task["artifacts"] = [{
                "name": "pipeline_result",
                "description": "Final synthesized pipeline output",
                "parts": [{"type": "text", "text": synthesizer_output}],
                "metadata": {
                    "totalTokens": ev.get("totalPipelineTokens", 0),
                    "totalMs": ev.get("totalPipelineMs", 0),
                    "agentOutputs": full_output,
                },
            }]
            task["status"]["state"] = "completed"
            yield {
                "id": task["id"],
                "sessionId": task["sessionId"],
                "status": task["status"],
                "artifacts": task["artifacts"],
            }
            return


async def _handle_rag_query(task: dict, payload: dict) -> dict:
    """RAG 쿼리 스킬 처리."""
    parts = payload.get("message", {}).get("parts", [])
    query_data = {}
    for p in parts:
        if p.get("type") == "data":
            query_data = p.get("data", {})
            break
    text_query = " ".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()

    collection = query_data.get("collection", "default")
    query = query_data.get("query", text_query)

    try:
        from rag.retriever import retrieve
        chunks = retrieve(collection, query, top_k=5, min_score=0.2)
    except Exception as e:
        chunks = []

    task["artifacts"] = [{
        "name": "rag_result",
        "parts": [{"type": "data", "data": {"chunks": chunks, "count": len(chunks)}}],
    }]
    task["status"]["state"] = "completed"
    return {
        "id": task["id"],
        "sessionId": task["sessionId"],
        "status": task["status"],
        "artifacts": task["artifacts"],
    }

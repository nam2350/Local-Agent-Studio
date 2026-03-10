"""A2A 클라이언트 — 원격 A2A 에이전트에게 태스크를 전송하고 결과를 수신."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


@dataclass
class A2ATaskResult:
    task_id: str
    state: str                  # submitted | working | completed | failed | canceled
    artifacts: list[dict] = field(default_factory=list)
    error: str = ""


async def fetch_agent_card(agent_url: str) -> dict:
    """원격 에이전트의 Agent Card를 조회."""
    url = agent_url.rstrip("/") + "/a2a/.well-known/agent.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def send_task(
    agent_url: str,
    prompt: str,
    skill_id: str = "run_pipeline",
    session_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    원격 A2A 에이전트에 태스크 전송 후 SSE 스트림을 yield.
    각 이벤트는 A2A 태스크 상태 업데이트 dict.
    """
    url = agent_url.rstrip("/") + "/a2a/tasks/send"
    payload = {
        "skillId": skill_id,
        "sessionId": session_id or str(uuid.uuid4()),
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": prompt}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                buf = ""
                async for raw in resp.aiter_text():
                    buf += raw
                    lines = buf.split("\n\n")
                    buf = lines.pop()
                    for line in lines:
                        if not line.startswith("data: "):
                            continue
                        try:
                            ev = json.loads(line[6:])
                            yield ev
                        except Exception:
                            pass
    except httpx.RequestError as e:
        yield {"type": "error", "message": f"Connection failed: {e}"}
    except httpx.HTTPStatusError as e:
        yield {"type": "error", "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}


async def test_agent_connection(agent_url: str) -> dict:
    """에이전트 연결 테스트 — Agent Card 조회 성공 여부 반환."""
    try:
        card = await fetch_agent_card(agent_url)
        return {
            "ok": True,
            "name": card.get("name", "Unknown"),
            "version": card.get("version", "?"),
            "skills": [s["id"] for s in card.get("skills", [])],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

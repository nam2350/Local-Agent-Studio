"""LangGraph 오케스트레이션 엔진 — Phase 12B

asyncio.Queue 이벤트 브릿지로 LangGraph 노드 → SSE 스트림 변환.
_run_single_agent() 재사용, 기존 SSE 이벤트 포맷 100% 유지.
새 이벤트 타입 langgraph_retry 추가 (기존 필드 변경 없음).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional, TYPE_CHECKING

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from pipeline.models import RunRequest

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


# ── State ──────────────────────────────────────────────────────────────────────
class GraphState(TypedDict):
    prompt: str
    previous_outputs: dict        # mutable 공유 dict (에이전트 간 컨텍스트)
    stage_2_agents: list          # router가 결정한 specialists 목록
    retry_count: int
    validator_passed: bool
    request: Any                  # RunRequest
    event_queue: Any              # asyncio.Queue[Optional[str]]
    agent_tokens_map: dict
    pipeline_start_ms: float


# ── SSE helpers ────────────────────────────────────────────────────────────────
def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _parse_sse(s: str) -> Optional[dict]:
    if not s.startswith("data: "):
        return None
    try:
        return json.loads(s[6:])
    except Exception:
        return None


# ── Validator 결과 파싱 ────────────────────────────────────────────────────────
def _validator_passed(output: str) -> bool:
    """PASS/FAIL 신호 감지. 키워드 없으면 fail-safe(PASS) 반환."""
    text = output.upper()
    for sig in ["VALIDATION: FAIL", "REJECTED", "VALIDATION FAILED"]:
        if sig in text:
            return False
    for sig in ["VALIDATION: PASS", "APPROVED", "VALIDATION PASSED"]:
        if sig in text:
            return True
    return True  # 기본값: PASS (no keyword → fail-safe)


# ── 에이전트 실행 → Queue put ──────────────────────────────────────────────────
async def _run_agent_into_queue(
    agent: dict, state: GraphState, queue: asyncio.Queue
) -> str:
    """단일 에이전트를 실행하고 SSE 이벤트를 queue에 넣는다. 최종 출력 반환."""
    from pipeline.orchestrator import _run_single_agent  # lazy import (순환 방지)

    agent_id = agent["id"]
    async for event_str in _run_single_agent(
        agent, state["previous_outputs"], state["prompt"], state["request"]
    ):
        await queue.put(event_str)
        parsed = _parse_sse(event_str)
        if parsed and parsed.get("type") == "agent_done":
            state["agent_tokens_map"][agent_id] = parsed.get("totalTokens", 0)

    return state["previous_outputs"].get(agent_id, "")


async def _run_parallel_into_queue(
    agents: list[dict], state: GraphState, queue: asyncio.Queue
) -> None:
    """여러 에이전트를 병렬 실행하고 SSE 이벤트를 queue에 넣는다."""
    inner: asyncio.Queue = asyncio.Queue()

    async def collect(agent: dict) -> None:
        from pipeline.orchestrator import _run_single_agent  # lazy import

        agent_id = agent["id"]
        async for event_str in _run_single_agent(
            agent, state["previous_outputs"], state["prompt"], state["request"]
        ):
            await inner.put(event_str)
            parsed = _parse_sse(event_str)
            if parsed and parsed.get("type") == "agent_done":
                state["agent_tokens_map"][agent_id] = parsed.get("totalTokens", 0)
        await inner.put(None)  # sentinel

    tasks = [asyncio.create_task(collect(a)) for a in agents]
    done_count = 0
    while done_count < len(agents):
        item = await inner.get()
        if item is None:
            done_count += 1
        else:
            await queue.put(item)
    await asyncio.gather(*tasks)


# ── 노드 함수 ──────────────────────────────────────────────────────────────────
async def node_route(state: GraphState) -> dict:
    """Stage 1: router-1 실행 → target_agents 파싱."""
    from pipeline.orchestrator import AGENTS_BY_ID  # lazy import
    from orchestration.pydantic_router import extract_target_agents

    queue = state["event_queue"]
    await _run_agent_into_queue(AGENTS_BY_ID["router-1"], state, queue)

    router_output = state["previous_outputs"].get("router-1", "")
    parsed = extract_target_agents(
        output=router_output,
        structured_routing=getattr(state["request"], "structured_routing", True),
    )
    stage_2 = parsed if parsed is not None else ["coder-1", "analyzer-1"]
    logger.info("[LangGraph] node_route → stage_2_agents=%s", stage_2)
    return {"stage_2_agents": stage_2}


async def node_specialists(state: GraphState) -> dict:
    """Stage 2: specialists 실행 (병렬 가능)."""
    from pipeline.orchestrator import AGENTS_BY_ID  # lazy import

    queue = state["event_queue"]
    stage_2_agents = state["stage_2_agents"]

    if not stage_2_agents:
        logger.info("[LangGraph] node_specialists: no agents, skipping")
        return {}

    agents = [AGENTS_BY_ID[aid] for aid in stage_2_agents if aid in AGENTS_BY_ID]

    if len(agents) > 1:
        await queue.put(_sse({
            "type": "stage_parallel",
            "stageIndex": 1,
            "agentIds": [a["id"] for a in agents],
        }))
        await _run_parallel_into_queue(agents, state, queue)
    elif agents:
        await _run_agent_into_queue(agents[0], state, queue)

    return {}


async def node_validate(state: GraphState) -> dict:
    """Stage 3: validator-1 실행 + PASS/FAIL 판정."""
    from pipeline.orchestrator import AGENTS_BY_ID  # lazy import

    queue = state["event_queue"]
    retry_count = state.get("retry_count", 0)

    # coder-1이 실행된 경우에만 validator 작동
    if "coder-1" not in state.get("stage_2_agents", []):
        logger.info("[LangGraph] node_validate: coder-1 absent, auto-PASS")
        return {"validator_passed": True}

    output = await _run_agent_into_queue(AGENTS_BY_ID["validator-1"], state, queue)
    passed = _validator_passed(output)

    if not passed and retry_count >= MAX_RETRIES:
        logger.warning("[LangGraph] max retries (%d) reached, forcing PASS", MAX_RETRIES)
        passed = True

    if not passed:
        await queue.put(_sse({
            "type": "langgraph_retry",
            "agentId": "validator-1",
            "retryCount": retry_count + 1,
            "maxRetries": MAX_RETRIES,
            "reason": "VALIDATION: FAIL — re-routing to specialists",
        }))
        # 재시도를 위해 이전 출력 초기화
        state["previous_outputs"].pop("validator-1", None)
        state["previous_outputs"].pop("coder-1", None)
        logger.info(
            "[LangGraph] node_validate: FAIL (retry %d/%d)", retry_count + 1, MAX_RETRIES
        )
    else:
        logger.info("[LangGraph] node_validate: PASS (retry_count=%d)", retry_count)

    return {"validator_passed": passed, "retry_count": retry_count + 1}


async def node_synthesize(state: GraphState) -> dict:
    """Stage 4: synthesizer-1 최종 통합."""
    from pipeline.orchestrator import AGENTS_BY_ID  # lazy import

    await _run_agent_into_queue(AGENTS_BY_ID["synthesizer-1"], state, state["event_queue"])
    return {}


# ── 조건 분기 ──────────────────────────────────────────────────────────────────
def route_after_validate(state: GraphState) -> str:
    """validator_passed에 따라 다음 노드 결정."""
    return "synthesizer" if state.get("validator_passed", True) else "specialists"


# ── 그래프 빌더 (lazy singleton) ───────────────────────────────────────────────
_compiled_graph = None


def _get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        from langgraph.graph import StateGraph, END  # lazy import

        b = StateGraph(GraphState)
        b.add_node("router",      node_route)
        b.add_node("specialists", node_specialists)
        b.add_node("validator",   node_validate)
        b.add_node("synthesizer", node_synthesize)

        b.set_entry_point("router")
        b.add_edge("router",      "specialists")
        b.add_edge("specialists", "validator")
        b.add_conditional_edges(
            "validator",
            route_after_validate,
            {"specialists": "specialists", "synthesizer": "synthesizer"},
        )
        b.add_edge("synthesizer", END)

        _compiled_graph = b.compile()
        logger.info("[LangGraph] StateGraph compiled successfully")

    return _compiled_graph


# ── 진입점 ────────────────────────────────────────────────────────────────────
async def run_langgraph_pipeline(
    prompt: str, request: "RunRequest"
) -> AsyncGenerator[str, None]:
    """LangGraph 파이프라인 실행 — asyncio.Queue 브릿지 패턴.

    LangGraph 노드(상태 반환) ↔ SSE AsyncGenerator(이벤트 스트리밍)의
    패러다임 간극을 asyncio.Queue를 이벤트 버스로 사용하여 해소.
    """
    pipeline_start = time.time()
    queue: asyncio.Queue = asyncio.Queue()
    previous_outputs: dict = {}
    agent_tokens_map: dict = {}

    yield _sse({"type": "pipeline_start", "totalAgents": 4, "prompt": prompt[:120]})

    initial_state: GraphState = {
        "prompt": prompt,
        "previous_outputs": previous_outputs,
        "stage_2_agents": ["coder-1", "analyzer-1"],
        "retry_count": 0,
        "validator_passed": False,
        "request": request,
        "event_queue": queue,
        "agent_tokens_map": agent_tokens_map,
        "pipeline_start_ms": pipeline_start,
    }

    async def run_graph() -> None:
        try:
            await _get_compiled_graph().ainvoke(initial_state)
        except Exception as exc:
            logger.exception("[LangGraph] graph execution error")
            await queue.put(_sse({"type": "pipeline_error", "message": str(exc)}))
        finally:
            await queue.put(None)  # sentinel: generator 종료 신호

    task = asyncio.create_task(run_graph())

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item

    await task  # 예외 전파 보장

    total_tokens = sum(agent_tokens_map.values())
    total_ms = int((time.time() - pipeline_start) * 1000)
    yield _sse({
        "type": "pipeline_done",
        "totalPipelineTokens": total_tokens,
        "totalPipelineMs": total_ms,
    })

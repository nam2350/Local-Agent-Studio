"""
Pydantic-based router output parser — Phase 12A guardrails.

파싱 전략 (우선순위):
  1. JSON: {"target_agents": [...], "reason": "..."}
  2. 레거시 정규식: [TARGET_AGENTS] coder-1, analyzer-1
  3. Fallback: None 반환 (호출자가 기본값 결정)
"""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class RouterDecision(BaseModel):
    """라우터 에이전트의 구조화된 출력 스키마."""
    target_agents: list[str]
    reason: str = ""
    confidence: float = 1.0
    model_config = {"extra": "ignore"}  # LLM 추가 필드 무시


# target_agents 포함 JSON 객체 추출 (텍스트 내 어느 위치든)
_JSON_EXTRACT_RE = re.compile(
    r'\{[^{}]*"target_agents"\s*:\s*\[[^\]]*\][^{}]*\}',
    re.DOTALL,
)

# 레거시 [TARGET_AGENTS] 포맷
_LEGACY_RE = re.compile(
    r'\[TARGET_AGENTS\](.*?)(?:\n|$)',
    re.IGNORECASE,
)

# 키워드 → agent ID 매핑
_LEGACY_KEYWORD_MAP: dict[str, str] = {
    "coder": "coder-1",
    "analyzer": "analyzer-1",
    "validator": "validator-1",
    "vision": "vision-1",
}


def _get_routable_agents() -> frozenset[str]:
    """DB에서 router 이외의 에이전트 ID를 동적으로 로드.
    DB 조회 실패 시 하드코딩 기본값으로 fallback.
    """
    try:
        from db.crud import list_agents
        agents = list_agents()
        ids = frozenset(a["id"] for a in agents if a.get("role") != "router")
        if ids:
            return ids
    except Exception:
        pass
    return frozenset({"coder-1", "analyzer-1", "validator-1", "vision-1"})


def parse_router_output(output: str) -> Optional[RouterDecision]:
    """라우터 출력에서 RouterDecision JSON을 파싱한다.

    마크다운 코드 펜스 제거 후 JSON 탐색.
    텍스트 어느 위치에 JSON이 있어도 추출 가능.

    Returns:
        RouterDecision if JSON found and valid, else None.
    """
    cleaned = re.sub(r"```(?:json)?", "", output).strip()

    for m in _JSON_EXTRACT_RE.finditer(cleaned):
        try:
            decision = RouterDecision.model_validate_json(m.group(0))
            logger.debug(
                "[pydantic_router] JSON OK: agents=%s reason=%r",
                decision.target_agents, (decision.reason or "")[:80],
            )
            return decision
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.debug("[pydantic_router] JSON candidate rejected: %s", exc)

    return None


def extract_target_agents(
    output: str,
    structured_routing: bool = True,
    known_agents: Optional[frozenset[str]] = None,
) -> Optional[list[str]]:
    """라우터 출력에서 실행할 에이전트 ID 목록을 추출한다.

    3단계 파싱 전략:
      Stage 1 (JSON)  : {"target_agents": [...]} — structured_routing=True 시 우선 시도
      Stage 2 (Regex) : [TARGET_AGENTS] 레거시 포맷 — 기존 동작 유지
      Stage 3 (None)  : 파싱 실패 — 호출자가 fallback 기본값 결정

    Returns:
        list[str] — 결정된 에이전트 목록 (빈 리스트 = 명시적 none).
        None       — 파싱 실패, 호출자가 ["coder-1", "analyzer-1"] fallback 처리.
    """
    _known = known_agents if known_agents is not None else _get_routable_agents()

    # ── Stage 1: JSON 파싱 ────────────────────────────────────────────────────
    if structured_routing:
        decision = parse_router_output(output)
        if decision is not None:
            filtered = [a for a in decision.target_agents if a in _known]
            # 명시적 빈 리스트(none) 또는 필터 후 결과가 있으면 확정
            if not decision.target_agents or filtered:
                logger.info(
                    "[pydantic_router] Stage1 (JSON): %s | reason=%r",
                    filtered, decision.reason[:60],
                )
                return filtered
            # JSON에 값이 있으나 모두 미등록 에이전트 → 다음 Stage로
            logger.warning(
                "[pydantic_router] Stage1 all-unknown agents %s, falling through",
                decision.target_agents,
            )

    # ── Stage 2: 레거시 [TARGET_AGENTS] 정규식 ───────────────────────────────
    m = _LEGACY_RE.search(output)
    if m:
        raw = m.group(1).strip().lower()
        if "none" in raw:
            logger.info("[pydantic_router] Stage2 (regex): none → []")
            return []
        agents: list[str] = []
        for keyword, agent_id in _LEGACY_KEYWORD_MAP.items():
            if keyword in raw:
                agents.append(agent_id)
        if agents:
            logger.info("[pydantic_router] Stage2 (regex): %s", agents)
            return agents

    # ── Stage 3: fallback 신호 ────────────────────────────────────────────────
    logger.info(
        "[pydantic_router] Stage3 fallback (no parse). snippet=%r",
        output[:120],
    )
    return None

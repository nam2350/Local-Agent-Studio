"""LLM-as-Judge 평가기 — Validator 에이전트(Phi-4-mini)를 재활용하여 품질 점수 산출."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JudgeScore:
    metric: str
    score: float          # 0.0 ~ 10.0
    reasoning: str
    agent_id: str


# ─── 평가 프롬프트 템플릿 ──────────────────────────────────────────────────────

_JUDGE_PROMPT = """\
You are an objective AI evaluator. Score the following agent response on the given metric.

METRIC: {metric}
DESCRIPTION: {description}

USER QUESTION:
{question}

AGENT RESPONSE:
{response}

{expected_section}

Provide your evaluation as valid JSON:
{{"score": <0-10>, "reasoning": "<one sentence explanation>"}}

Score 0=completely wrong/irrelevant, 5=adequate, 10=perfect.
Output ONLY the JSON object, nothing else."""

_METRIC_DESCRIPTIONS = {
    "answer_relevance": "Does the response directly answer the question? Is it on-topic?",
    "faithfulness": "Is the response factually accurate? Are claims supported?",
    "code_quality": "Is the code syntactically correct, readable, and follows best practices?",
    "completeness": "Does the response fully address all aspects of the question?",
    "conciseness": "Is the response appropriately concise without unnecessary padding?",
}


def _extract_score(text: str) -> tuple[float, str]:
    """LLM 출력에서 score와 reasoning 추출."""
    # JSON 블록 찾기
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        # 순수 JSON 파싱 시도
        data = json.loads(clean)
        return float(data["score"]), str(data.get("reasoning", ""))
    except Exception:
        pass
    # 정규식 폴백
    score_m = re.search(r'"score"\s*:\s*([0-9.]+)', clean)
    reason_m = re.search(r'"reasoning"\s*:\s*"([^"]+)"', clean)
    score = float(score_m.group(1)) if score_m else 5.0
    reason = reason_m.group(1) if reason_m else clean[:100]
    return min(max(score, 0.0), 10.0), reason


async def judge_response(
    agent_id: str,
    question: str,
    response: str,
    metric: str,
    expected: Optional[str] = None,
) -> JudgeScore:
    """단일 에이전트 응답을 단일 메트릭으로 평가.

    실제 Validator 에이전트(Phi-4-mini)를 사용하거나 시뮬레이션 점수 반환.
    """
    description = _METRIC_DESCRIPTIONS.get(metric, "Evaluate response quality.")
    expected_section = f"EXPECTED ANSWER:\n{expected}\n" if expected else ""
    prompt = _JUDGE_PROMPT.format(
        metric=metric,
        description=description,
        question=question,
        response=response[:2000],  # 토큰 제한
        expected_section=expected_section,
    )

    # Validator 에이전트로 실제 평가 시도
    try:
        from db import crud
        validator = crud.get_agent("validator-1")
        if validator and validator.get("provider_type") == "transformers":
            from providers.registry import registry
            model_id = validator["model_id"]
            provider = registry.get_transformers(model_id=model_id)
            if provider and await provider.health_check():
                full_output = ""
                async for token in provider.generate(
                    prompt=prompt,
                    system_prompt="You are an objective AI evaluator. Always output valid JSON.",
                    max_tokens=120,
                    temperature=0.1,
                ):
                    full_output += token
                score, reasoning = _extract_score(full_output)
                return JudgeScore(metric=metric, score=score, reasoning=reasoning, agent_id=agent_id)
    except Exception as e:
        logger.warning("[judge] Real model evaluation failed: %s — using heuristic", e)

    # 휴리스틱 시뮬레이션 (Validator 미사용 시)
    score = _heuristic_score(metric, response, expected)
    return JudgeScore(
        metric=metric,
        score=score,
        reasoning=f"[Heuristic] {metric} estimated from response length and content",
        agent_id=agent_id,
    )


def _heuristic_score(metric: str, response: str, expected: Optional[str]) -> float:
    """실제 LLM 없이 간단한 휴리스틱으로 점수 추정."""
    length = len(response.strip())
    if length < 20:
        return 1.0
    if length > 5000:
        return 6.0

    if metric == "code_quality":
        has_code = "```" in response or "def " in response or "function " in response
        return 7.5 if has_code else 4.0
    if metric == "answer_relevance":
        return 6.5 if length > 100 else 4.0
    if metric == "completeness":
        return min(8.0, 4.0 + length / 500)
    if metric == "conciseness":
        return 8.0 if length < 800 else max(4.0, 10.0 - length / 1000)
    if expected:
        # 단순 단어 겹침 기반
        exp_words = set(expected.lower().split())
        resp_words = set(response.lower().split())
        overlap = len(exp_words & resp_words) / max(len(exp_words), 1)
        return round(overlap * 10, 1)
    return 5.5

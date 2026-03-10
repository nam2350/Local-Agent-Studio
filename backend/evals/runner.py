"""평가 실행기 — eval_set을 실행하고 SSE 이벤트를 yield."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from .judge import judge_response, _METRIC_DESCRIPTIONS

logger = logging.getLogger(__name__)

# 지원 메트릭
DEFAULT_METRICS = ["answer_relevance", "completeness", "conciseness"]
CODE_METRICS    = ["code_quality", "answer_relevance", "completeness"]

# ─── DB 초기화 ─────────────────────────────────────────────────────────────────

def init_eval_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_sets (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            eval_set_id TEXT NOT NULL REFERENCES eval_sets(id) ON DELETE CASCADE,
            question    TEXT NOT NULL,
            expected    TEXT DEFAULT '',
            metrics     TEXT DEFAULT '["answer_relevance","completeness","conciseness"]',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            eval_set_id  TEXT NOT NULL,
            run_label    TEXT DEFAULT '',
            provider     TEXT DEFAULT 'simulation',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_scores (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id    INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
            case_id   INTEGER NOT NULL,
            agent_id  TEXT NOT NULL,
            metric    TEXT NOT NULL,
            score     REAL NOT NULL,
            reasoning TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _get_conn():
    from db.database import get_connection
    return get_connection()


# ─── Eval Set CRUD ────────────────────────────────────────────────────────────

def create_eval_set(name: str) -> dict:
    sid = str(uuid.uuid4())[:8]
    with _get_conn() as conn:
        conn.execute("INSERT INTO eval_sets (id, name) VALUES (?,?)", (sid, name))
        conn.commit()
    return {"id": sid, "name": name}


def list_eval_sets() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM eval_sets ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            cases = conn.execute("SELECT COUNT(*) as c FROM eval_cases WHERE eval_set_id=?", (d["id"],)).fetchone()
            d["case_count"] = cases["c"] if cases else 0
            result.append(d)
    return result


def add_eval_case(eval_set_id: str, question: str, expected: str = "", metrics: Optional[list] = None) -> int:
    mlist = json.dumps(metrics or DEFAULT_METRICS)
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO eval_cases (eval_set_id, question, expected, metrics) VALUES (?,?,?,?)",
            (eval_set_id, question, expected, mlist),
        )
        conn.commit()
        return cur.lastrowid


def delete_eval_case(case_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM eval_cases WHERE id=?", (case_id,))
        conn.commit()


def list_eval_cases(eval_set_id: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, expected, metrics FROM eval_cases WHERE eval_set_id=? ORDER BY id",
            (eval_set_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_eval_results(eval_set_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    with _get_conn() as conn:
        q = "SELECT id, eval_set_id, run_label, provider, created_at FROM eval_runs"
        params: list = []
        if eval_set_id:
            q += " WHERE eval_set_id=?"
            params.append(eval_set_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        runs = [dict(r) for r in conn.execute(q, params).fetchall()]

        for run in runs:
            scores = conn.execute(
                "SELECT agent_id, metric, AVG(score) as avg_score FROM eval_scores WHERE run_id=? GROUP BY agent_id, metric",
                (run["id"],)
            ).fetchall()
            run["scores"] = [dict(s) for s in scores]
    return runs


def compare_runs(run_a: int, run_b: int) -> dict:
    with _get_conn() as conn:
        def fetch(run_id):
            rows = conn.execute(
                "SELECT agent_id, metric, AVG(score) as avg FROM eval_scores WHERE run_id=? GROUP BY agent_id, metric",
                (run_id,)
            ).fetchall()
            return {(r["agent_id"], r["metric"]): r["avg"] for r in rows}

        a_scores = fetch(run_a)
        b_scores = fetch(run_b)

    all_keys = set(a_scores) | set(b_scores)
    diff = []
    for (aid, m) in sorted(all_keys):
        diff.append({
            "agent_id": aid, "metric": m,
            "run_a": a_scores.get((aid, m), 0.0),
            "run_b": b_scores.get((aid, m), 0.0),
            "delta": b_scores.get((aid, m), 0.0) - a_scores.get((aid, m), 0.0),
        })
    return {"run_a": run_a, "run_b": run_b, "diff": diff}


# ─── 평가 실행 ────────────────────────────────────────────────────────────────

async def run_eval(
    eval_set_id: str,
    run_label: str = "",
    provider: str = "simulation",
) -> AsyncGenerator[dict, None]:
    """평가 세트를 실행하고 SSE 이벤트 dict를 yield."""
    cases = list_eval_cases(eval_set_id)
    if not cases:
        yield {"type": "eval_error", "message": "No cases in eval set"}
        return

    # eval_run 생성
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO eval_runs (eval_set_id, run_label, provider) VALUES (?,?,?)",
            (eval_set_id, run_label, provider),
        )
        conn.commit()
        run_id = cur.lastrowid

    total = len(cases)
    yield {"type": "eval_start", "runId": run_id, "totalCases": total, "evalSetId": eval_set_id}

    # 파이프라인 에이전트 목록 가져오기
    from db import crud as _crud
    agents = _crud.list_agents()
    synthesizer_agents = [a for a in agents if a["role"] in ("synthesizer", "assistant")]
    eval_agents = synthesizer_agents or agents[:3]

    total_scores: dict[tuple, list] = {}

    for case_idx, case in enumerate(cases):
        question = case["question"]
        expected = case.get("expected", "")
        metrics = json.loads(case.get("metrics", "[]")) if isinstance(case.get("metrics"), str) else (case.get("metrics") or DEFAULT_METRICS)

        yield {
            "type": "eval_case_start",
            "runId": run_id,
            "caseIdx": case_idx,
            "totalCases": total,
            "question": question[:80],
        }

        # 파이프라인 실행으로 에이전트별 실제 응답 수집
        response_by_agent: dict[str, str] = {}
        try:
            from pipeline.orchestrator import run_pipeline
            from pipeline.models import RunRequest, ProviderConfig
            req = RunRequest(
                prompt=question,
                use_real_models=(provider != "simulation"),
                default_provider=ProviderConfig(type=provider if provider != "simulation" else "simulation"),
            )
            _current_agent: str = ""
            _agent_buf: str = ""
            async for chunk in run_pipeline(question, req):
                if not chunk.startswith("data: "):
                    continue
                try:
                    ev = json.loads(chunk[6:])
                    ev_type = ev.get("type", "")
                    if ev_type == "agent_start":
                        _current_agent = ev.get("agentId", "")
                        _agent_buf = ""
                    elif ev_type == "agent_token":
                        _agent_buf += ev.get("token", "")
                    elif ev_type == "agent_done":
                        if _current_agent:
                            response_by_agent[_current_agent] = _agent_buf
                    elif ev_type == "pipeline_done":
                        break
                except json.JSONDecodeError:
                    pass
            # synthesizer 출력 우선, 없으면 마지막 에이전트 출력 사용
            response_text = (
                response_by_agent.get("synthesizer-1", "")
                or (list(response_by_agent.values())[-1] if response_by_agent else "")
                or "[Pipeline produced no output]"
            )
        except Exception as e:
            logger.error("[Eval] Pipeline failed for case %d: %s", case_idx, e)
            response_text = f"[Pipeline failed: {e}]"

        # 에이전트별 메트릭 평가 (에이전트 자신의 실제 출력 사용)
        for agent in eval_agents:
            aid = agent["id"]
            for metric in metrics:
                agent_response = response_by_agent.get(aid, response_text)
                try:
                    js = await judge_response(
                        agent_id=aid,
                        question=question,
                        response=agent_response,
                        metric=metric,
                        expected=expected or None,
                    )
                except Exception as e:
                    logger.error("[Eval] Judge failed for %s/%s: %s", aid, metric, e)
                    from .judge import JudgeScore
                    js = JudgeScore(score=0.0, reasoning=f"Judge error: {e}")

                # DB 저장
                with _get_conn() as conn:
                    conn.execute(
                        "INSERT INTO eval_scores (run_id, case_id, agent_id, metric, score, reasoning) VALUES (?,?,?,?,?,?)",
                        (run_id, case["id"], aid, metric, js.score, js.reasoning),
                    )
                    conn.commit()

                key = (aid, metric)
                total_scores.setdefault(key, []).append(js.score)

                yield {
                    "type": "eval_score",
                    "runId": run_id,
                    "caseIdx": case_idx,
                    "agentId": aid,
                    "metric": metric,
                    "score": js.score,
                    "reasoning": js.reasoning[:120],
                }
                await asyncio.sleep(0)  # event loop 양보

    # 최종 집계
    summary = [
        {"agentId": aid, "metric": m, "avgScore": round(sum(vals) / len(vals), 2)}
        for (aid, m), vals in total_scores.items()
    ]
    yield {
        "type": "eval_done",
        "runId": run_id,
        "summary": summary,
    }

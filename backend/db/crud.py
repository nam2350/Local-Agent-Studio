"""CRUD operations for pipeline presets."""

import json
from typing import Any
from .database import get_connection


def list_pipelines() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description, created_at, updated_at "
            "FROM pipelines ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_pipeline(pipeline_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["nodes"] = json.loads(d.pop("nodes_json", "[]"))
        d["edges"] = json.loads(d.pop("edges_json", "[]"))
        d["node_configs"] = json.loads(d.pop("node_configs_json", "{}"))
        return d


def create_pipeline(
    name: str,
    description: str,
    nodes: list[Any],
    edges: list[Any],
    node_configs: dict[str, Any],
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pipelines (name, description, nodes_json, edges_json, node_configs_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, description, json.dumps(nodes), json.dumps(edges), json.dumps(node_configs)),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def update_pipeline(
    pipeline_id: int,
    name: str,
    description: str,
    nodes: list[Any],
    edges: list[Any],
    node_configs: dict[str, Any],
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE pipelines SET name=?, description=?, nodes_json=?, edges_json=?, "
            "node_configs_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (name, description, json.dumps(nodes), json.dumps(edges), json.dumps(node_configs), pipeline_id),
        )
        conn.commit()


def delete_pipeline(pipeline_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM pipelines WHERE id=?", (pipeline_id,))
        conn.commit()


def list_agents() -> list[dict]:
    """Retrieve all configurable agent templates from the registry."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM agent_registry ORDER BY role ASC").fetchall()
        return [dict(r) for r in rows]


def get_agent(agent_id: str) -> dict | None:
    """Retrieve a single agent template by its registry ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM agent_registry WHERE id = ?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None


def create_agent(
    agent_id: str,
    name: str,
    role: str,
    provider_type: str,
    model_id: str,
    system_prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_registry (id, name, role, provider_type, model_id, system_prompt, max_tokens, temperature) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_id, name, role, provider_type, model_id, system_prompt, max_tokens, temperature),
        )
        conn.commit()


def update_agent(
    agent_id: str,
    name: str,
    role: str,
    provider_type: str,
    model_id: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE agent_registry SET name=?, role=?, provider_type=?, model_id=?, "
            "system_prompt=?, max_tokens=?, temperature=? WHERE id=?",
            (name, role, provider_type, model_id, system_prompt, max_tokens, temperature, agent_id),
        )
        conn.commit()


def delete_agent(agent_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM agent_registry WHERE id=?", (agent_id,))
        conn.commit()


# ── Pipeline Run History CRUD (Phase 15) ──────────────────────────────────────

def create_run(
    prompt: str,
    provider: str,
    orchestration_mode: str,
    status: str,
    total_tokens: int,
    total_ms: int,
    agent_outputs: dict,
    error_message: str | None = None,
) -> int:
    import json as _json
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pipeline_runs "
            "(prompt, provider, orchestration_mode, status, total_tokens, total_ms, agent_outputs_json, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (prompt, provider, orchestration_mode, status,
             total_tokens, total_ms, _json.dumps(agent_outputs, ensure_ascii=False), error_message),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, prompt, provider, orchestration_mode, status, "
            "total_tokens, total_ms, error_message, created_at "
            "FROM pipeline_runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    import json as _json
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["agent_outputs"] = _json.loads(d.pop("agent_outputs_json", "{}"))
        return d


def delete_run(run_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM pipeline_runs WHERE id = ?", (run_id,))
        conn.commit()


def count_runs() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM pipeline_runs").fetchone()
        return row["c"] if row else 0


# ── Conversation CRUD (Phase 13) ──────────────────────────────────────────────

def create_session(session_id: str, title: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO conversation_sessions (id, title) VALUES (?, ?)",
            (session_id, title),
        )
        conn.commit()


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_sessions WHERE id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def list_sessions() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_session(session_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM conversation_sessions WHERE id=?", (session_id,))
        conn.commit()


def get_session_turn_count(session_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM conversation_turns WHERE session_id=?", (session_id,)
        ).fetchone()
        return row["c"] if row else 0


def create_turn(
    session_id: str, turn_index: int, user_prompt: str, orchestration_mode: str = "dag"
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_turns (session_id, turn_index, user_prompt, orchestration_mode) "
            "VALUES (?, ?, ?, ?)",
            (session_id, turn_index, user_prompt, orchestration_mode),
        )
        conn.execute(
            "UPDATE conversation_sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (session_id,),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def list_turns(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_turns WHERE session_id=? ORDER BY turn_index ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_agent_output(
    turn_id: int,
    agent_id: str,
    role: str,
    full_output: str,
    token_count: int = 0,
    latency_ms: int = 0,
    vram_gb: float = 0.0,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO agent_outputs "
            "(turn_id, agent_id, role, full_output, token_count, latency_ms, vram_gb) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (turn_id, agent_id, role, full_output, token_count, latency_ms, vram_gb),
        )
        conn.commit()


def list_agent_outputs(turn_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_outputs WHERE turn_id=? ORDER BY id ASC", (turn_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_turns_with_outputs(session_id: str) -> list[dict]:
    """conversation_turns + agent_outputs를 단일 JOIN 쿼리로 조회 (N+1 방지)."""
    from collections import OrderedDict
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ct.id          AS turn_id,
                ct.session_id,
                ct.turn_index,
                ct.user_prompt,
                ct.orchestration_mode,
                ct.created_at  AS turn_created_at,
                ao.id          AS output_id,
                ao.agent_id,
                ao.role,
                ao.full_output,
                ao.token_count,
                ao.latency_ms,
                ao.vram_gb,
                ao.created_at  AS output_created_at
            FROM conversation_turns ct
            LEFT JOIN agent_outputs ao ON ao.turn_id = ct.id
            WHERE ct.session_id = ?
            ORDER BY ct.turn_index ASC, ao.id ASC
            """,
            (session_id,),
        ).fetchall()

    turns: OrderedDict[int, dict] = OrderedDict()
    for r in rows:
        tid = r["turn_id"]
        if tid not in turns:
            turns[tid] = {
                "id": tid,
                "session_id": r["session_id"],
                "turn_index": r["turn_index"],
                "user_prompt": r["user_prompt"],
                "orchestration_mode": r["orchestration_mode"],
                "created_at": r["turn_created_at"],
                "agent_outputs": [],
            }
        if r["output_id"] is not None:
            turns[tid]["agent_outputs"].append({
                "id": r["output_id"],
                "turn_id": tid,
                "agent_id": r["agent_id"],
                "role": r["role"],
                "full_output": r["full_output"],
                "token_count": r["token_count"],
                "latency_ms": r["latency_ms"],
                "vram_gb": r["vram_gb"],
                "created_at": r["output_created_at"],
            })
    return list(turns.values())

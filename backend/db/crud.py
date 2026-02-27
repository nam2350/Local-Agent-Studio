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

"""외부 A2A 에이전트 레지스트리 — SQLite 기반 등록/조회/삭제."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def _get_conn():
    from db.database import get_connection
    return get_connection()


def init_a2a_table(conn) -> None:
    """a2a_agents 테이블 생성 및 기본 시드."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS a2a_agents (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            description TEXT DEFAULT '',
            skills      TEXT DEFAULT '[]',
            enabled     INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _parse_skills(raw: str) -> list:
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def list_a2a_agents() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM a2a_agents ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["skills"] = _parse_skills(d.get("skills", "[]"))
            result.append(d)
    return result


def get_a2a_agent(agent_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM a2a_agents WHERE id=?", (agent_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["skills"] = _parse_skills(d.get("skills", "[]"))
    return d


def create_a2a_agent(agent_id: str, name: str, url: str, description: str = "", skills: list | None = None) -> dict:
    with _get_conn() as conn:
        skills_json = json.dumps(skills or [])
        conn.execute(
            "INSERT INTO a2a_agents (id, name, url, description, skills) VALUES (?,?,?,?,?)",
            (agent_id, name, url, description, skills_json),
        )
        conn.commit()
    return {"id": agent_id, "name": name, "url": url, "description": description, "skills": skills or []}


def delete_a2a_agent(agent_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM a2a_agents WHERE id=?", (agent_id,))
        conn.commit()
        return cur.rowcount > 0


def update_a2a_agent_skills(agent_id: str, skills: list) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE a2a_agents SET skills=? WHERE id=?", (json.dumps(skills), agent_id))
        conn.commit()

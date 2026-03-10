"""MCP 서버 레지스트리 — SQLite 기반 서버 목록 관리 + 런타임 클라이언트 캐시."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .client import MCPTool, MCPCallResult, make_client

logger = logging.getLogger(__name__)

# ─── DB 초기화 ────────────────────────────────────────────────────────────────

def init_mcp_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id       TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            transport TEXT NOT NULL,   -- stdio | sse
            command  TEXT,
            url      TEXT,
            enabled  INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 기본 DuckDuckGo 서버 (내장 래퍼)
    conn.execute("""
        INSERT OR IGNORE INTO mcp_servers (id, name, transport, command, url, enabled)
        VALUES ('duckduckgo-builtin', 'DuckDuckGo Search', 'builtin', NULL, NULL, 1)
    """)
    conn.commit()


def _get_conn():
    from db.database import get_connection
    return get_connection()


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def list_servers() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, transport, command, url, enabled, created_at FROM mcp_servers ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_server(server_id: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, transport, command, url, enabled FROM mcp_servers WHERE id=?", (server_id,)
        ).fetchone()
        return dict(row) if row else None


def create_server(id_: str, name: str, transport: str, command: Optional[str], url: Optional[str]) -> dict:
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO mcp_servers (id, name, transport, command, url) VALUES (?,?,?,?,?)",
            (id_, name, transport, command, url),
        )
        conn.commit()
    return get_server(id_)


def delete_server(server_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
        conn.commit()
        return cur.rowcount > 0


def toggle_server(server_id: str, enabled: bool):
    with _get_conn() as conn:
        conn.execute("UPDATE mcp_servers SET enabled=? WHERE id=?", (1 if enabled else 0, server_id))
        conn.commit()


# ─── 런타임 클라이언트 관리 ───────────────────────────────────────────────────

_clients: dict[str, object] = {}  # server_id → MCPClient*


def _get_client(server: dict):
    sid = server["id"]
    if sid not in _clients:
        _clients[sid] = make_client(
            transport=server["transport"],
            command=server.get("command"),
            url=server.get("url"),
            server_id=sid,
        )
    return _clients[sid]


async def list_all_tools() -> list[MCPTool]:
    """모든 활성 MCP 서버의 도구 목록을 합산."""
    servers = [s for s in list_servers() if s["enabled"] and s["transport"] != "builtin"]
    tasks = []
    for s in servers:
        client = _get_client(s)
        tasks.append(client.list_tools())

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tools: list[MCPTool] = []
    for res in results:
        if isinstance(res, list):
            tools.extend(res)
    return tools


async def test_server(server_id: str) -> dict:
    """서버 연결 테스트 — 도구 목록 반환."""
    server = get_server(server_id)
    if not server:
        return {"ok": False, "error": "Server not found"}
    if server["transport"] == "builtin":
        return {"ok": True, "tools": [{"name": "web_search", "description": "DuckDuckGo 웹 검색 (내장)"}]}
    try:
        client = _get_client(server)
        tools = await client.list_tools()
        return {"ok": True, "tools": [{"name": t.name, "description": t.description} for t in tools]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def call_mcp_tool(tool_name: str, arguments: dict) -> MCPCallResult:
    """tool_name으로 적절한 서버를 찾아 실행."""
    # builtin: web_search
    if tool_name == "web_search":
        from pipeline.tools import web_search
        result = web_search(arguments.get("query", ""))
        return MCPCallResult(content=result)

    # 외부 서버: 도구 이름으로 서버 검색
    servers = [s for s in list_servers() if s["enabled"] and s["transport"] != "builtin"]
    for server in servers:
        try:
            client = _get_client(server)
            tools = await client.list_tools()
            if any(t.name == tool_name for t in tools):
                return await client.call_tool(tool_name, arguments)
        except Exception as e:
            logger.warning("[MCP] Server '%s' failed during tool dispatch: %s", server["id"], e)
            continue

    return MCPCallResult(content=f"Tool '{tool_name}' not found in any MCP server", is_error=True)

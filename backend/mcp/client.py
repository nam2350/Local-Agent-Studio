"""MCP (Model Context Protocol) 클라이언트 — stdio / SSE 두 가지 transport 지원."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── 데이터 클래스 ─────────────────────────────────────────────────────────────

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    server_id: str = ""


@dataclass
class MCPCallResult:
    content: str
    is_error: bool = False


# ─── JSON-RPC 헬퍼 ────────────────────────────────────────────────────────────

def _rpc(method: str, params: dict, req_id: int = 1) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})


# ─── stdio 클라이언트 ─────────────────────────────────────────────────────────

class MCPClientStdio:
    """subprocess stdio 기반 MCP 클라이언트."""

    def __init__(self, command: str, server_id: str = ""):
        # command는 공백 구분 문자열 (예: "npx -y @modelcontextprotocol/server-filesystem /tmp")
        self.command = command
        self.server_id = server_id
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._req_id = 0
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()

    async def _ensure_started(self):
        """프로세스 시작 보장 — start_lock으로 동시 시작 방지."""
        async with self._start_lock:
            if self._proc and self._proc.returncode is None:
                return
            args = self.command.split()
            self._proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            # initialize 핸드셰이크
            resp = await self._send_recv("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "local-agent-studio", "version": "0.2.0"},
            })
            if "error" in resp:
                logger.warning("[MCP stdio] initialize handshake failed for %s: %s", self.server_id, resp)

    async def _send_recv(self, method: str, params: dict) -> dict:
        async with self._lock:
            self._req_id += 1
            payload = _rpc(method, params, self._req_id) + "\n"
            self._proc.stdin.write(payload.encode())
            await self._proc.stdin.drain()
            try:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=10.0)
                return json.loads(line)
            except asyncio.TimeoutError:
                return {"error": {"message": "MCP server timeout"}}

    async def list_tools(self) -> list[MCPTool]:
        try:
            await self._ensure_started()
            resp = await self._send_recv("tools/list", {})
            tools_raw = resp.get("result", {}).get("tools", [])
            return [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_id=self.server_id,
                )
                for t in tools_raw
            ]
        except Exception as e:
            logger.warning("[MCP stdio] list_tools failed for %s: %s", self.server_id, e)
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPCallResult:
        try:
            await self._ensure_started()
            resp = await self._send_recv("tools/call", {"name": tool_name, "arguments": arguments})
            result = resp.get("result", {})
            content_list = result.get("content", [])
            text = "\n".join(c.get("text", "") for c in content_list if c.get("type") == "text")
            is_error = result.get("isError", False)
            return MCPCallResult(content=text or str(result), is_error=is_error)
        except Exception as e:
            return MCPCallResult(content=str(e), is_error=True)

    async def close(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass


# ─── SSE 클라이언트 ───────────────────────────────────────────────────────────

class MCPClientSse:
    """HTTP SSE 기반 MCP 클라이언트 (원격 MCP 서버)."""

    def __init__(self, url: str, server_id: str = ""):
        self.url = url.rstrip("/")
        self.server_id = server_id
        self._http = httpx.AsyncClient(timeout=15.0)

    async def list_tools(self) -> list[MCPTool]:
        try:
            resp = await self._http.get(f"{self.url}/tools")
            data = resp.json()
            return [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_id=self.server_id,
                )
                for t in data.get("tools", [])
            ]
        except Exception as e:
            logger.warning("[MCP SSE] list_tools failed for %s: %s", self.server_id, e)
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPCallResult:
        try:
            resp = await self._http.post(
                f"{self.url}/tools/call",
                json={"name": tool_name, "arguments": arguments},
            )
            data = resp.json()
            content_list = data.get("content", [])
            text = "\n".join(c.get("text", "") for c in content_list if c.get("type") == "text")
            return MCPCallResult(content=text or str(data), is_error=data.get("isError", False))
        except Exception as e:
            return MCPCallResult(content=str(e), is_error=True)

    async def close(self):
        await self._http.aclose()


# ─── 팩토리 ──────────────────────────────────────────────────────────────────

def make_client(transport: str, command: Optional[str], url: Optional[str], server_id: str) -> Any:
    if transport == "stdio" and command:
        return MCPClientStdio(command=command, server_id=server_id)
    elif transport == "sse" and url:
        return MCPClientSse(url=url, server_id=server_id)
    raise ValueError(f"Invalid MCP transport config: transport={transport!r}, command={command!r}, url={url!r}")

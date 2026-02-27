"""Tool execution engine."""

import json
import math
import re
import urllib.request
import urllib.parse
import urllib.error
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(__file__).parent.parent.parent  # project root


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a named tool with given arguments. Returns result string."""
    try:
        if name == "web_search":
            return _web_search(arguments.get("query", ""))
        if name == "calculator":
            return _calculator(arguments.get("expression", ""))
        if name == "read_file":
            return _read_file(arguments.get("path", ""))
        return f"[Unknown tool: {name}]"
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return f"[Tool error: {e}]"


# ─── Tool implementations ─────────────────────────────────────────────────────

def _web_search(query: str) -> str:
    """Query DuckDuckGo Instant Answer API (no key required)."""
    if not query.strip():
        return "[Empty query]"
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "LocalAgentStudio/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        parts: list[str] = []

        # Abstract (main answer)
        if data.get("AbstractText"):
            parts.append(data["AbstractText"])

        # Related topics (up to 3)
        topics = data.get("RelatedTopics", [])[:3]
        for t in topics:
            if isinstance(t, dict) and t.get("Text"):
                parts.append(f"• {t['Text']}")

        # Answer (e.g. calculator, conversions)
        if data.get("Answer"):
            parts.append(f"Answer: {data['Answer']}")

        if parts:
            return "\n".join(parts)[:800]
        return f"No instant answer found for: {query}"
    except urllib.error.URLError as e:
        return f"[Search unavailable: {e}]"


def _calculator(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    # Allow only safe characters
    cleaned = expression.strip()
    if not re.match(r'^[\d\s\+\-\*\/\%\(\)\.\,\^epsqrtlogabsroundfloorce\s]*$', cleaned):
        # Fallback: reject if contains unsafe chars
        allowed = re.sub(r'[^\d\s\+\-\*\/\%\(\)\.\^]', '', cleaned)
        if not allowed.strip():
            return "[Invalid expression]"
        cleaned = allowed

    # Replace ^ with ** for Python
    cleaned = cleaned.replace("^", "**")

    try:
        # Safe eval with math namespace only
        safe_ns = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_ns.update({"abs": abs, "round": round, "min": min, "max": max})
        result = eval(cleaned, {"__builtins__": {}}, safe_ns)  # noqa: S307
        if isinstance(result, float):
            return str(round(result, 6))
        return str(result)
    except Exception as e:
        return f"[Calc error: {e}]"


def _read_file(path: str) -> str:
    """Read a file from the workspace."""
    if not path:
        return "[No path provided]"
    # Security: prevent path traversal
    try:
        target = (WORKSPACE_ROOT / path).resolve()
        if not str(target).startswith(str(WORKSPACE_ROOT.resolve())):
            return "[Access denied: outside workspace]"
        if not target.exists():
            return f"[File not found: {path}]"
        if target.stat().st_size > 50_000:
            return f"[File too large: {target.stat().st_size} bytes]"
        return target.read_text(encoding="utf-8", errors="replace")[:2000]
    except Exception as e:
        return f"[Read error: {e}]"


# ─── Tool call detection ──────────────────────────────────────────────────────

TOOL_CALL_PATTERN = re.compile(
    r'\[TOOL:\s*(\w+)\]\s*(\{.*?\})\s*\[/TOOL\]',
    re.DOTALL | re.IGNORECASE
)


def detect_and_execute_tools(text: str, enabled_tools: list[str]) -> list[dict]:
    """
    Scan text for [TOOL: name] {...} [/TOOL] patterns.
    Execute matched tools and return list of {tool, input, output} dicts.
    """
    results = []
    for m in TOOL_CALL_PATTERN.finditer(text):
        tool_name = m.group(1).strip()
        args_str  = m.group(2).strip()
        if tool_name not in enabled_tools:
            continue
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {"raw": args_str}
        output = execute_tool(tool_name, args)
        results.append({"tool": tool_name, "input": args, "output": output})
    return results

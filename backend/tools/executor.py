"""Tool execution engine."""

import math
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(__file__).parent.parent.parent  # project root


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a named tool with given arguments. Returns result string."""
    try:
        if name == "calculator":
            return _calculator(arguments.get("expression", ""))
        if name == "read_file":
            return _read_file(arguments.get("path", ""))
        return f"[Unknown tool: {name}]"
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return f"[Tool error: {e}]"


# ─── Tool implementations ─────────────────────────────────────────────────────

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


"""코드 샌드박스 실행 엔진 — Python/Shell 코드 격리 실행."""

from __future__ import annotations

import ast as _ast
import asyncio
import logging
import re
import sys
import textwrap
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# ─── 상수 ─────────────────────────────────────────────────────────────────────

TIMEOUT_SEC = 30
MAX_OUTPUT_BYTES = 32_768  # 32 KB

# 위험 패턴 (실행 전 거부)
_BLOCKED_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.(?!run\b)",          # subprocess.Popen / call 등 직접 쉘 접근
    r"__import__\s*\(\s*['\"]os['\"]",
    r"open\s*\(.*['\"]w['\"]",         # 파일 쓰기
    r"shutil\.(rmtree|move|copy)",
    r"socket\.",
    r"requests\.",
    r"urllib\.request",
    r"eval\s*\(",
    r"exec\s*\(",
    r"compile\s*\(",
]
_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    language: str
    timed_out: bool = False
    blocked: bool = False
    block_reason: str = ""


# ─── 코드 블록 추출 ───────────────────────────────────────────────────────────

_CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>python|py|bash|sh|shell)?\s*\n(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """텍스트에서 (language, code) 쌍 목록을 추출.

    언어가 지정되지 않은 블록은 무시 (안전 실행 불가).
    """
    blocks = []
    for m in _CODE_BLOCK_RE.finditer(text):
        lang = (m.group("lang") or "").lower().strip()
        code = m.group("code").strip()
        if not code:
            continue
        if lang in ("python", "py", ""):
            blocks.append(("python", code))
        elif lang in ("bash", "sh", "shell"):
            blocks.append(("shell", code))
    return blocks


# ─── 보안 검사 ────────────────────────────────────────────────────────────────

# AST 기반 차단: 위험 모듈 + 위험 빌트인
_BLOCKED_MODULES  = {"os", "subprocess", "socket", "requests", "urllib", "shutil",
                     "ctypes", "importlib", "pickle", "shelve", "tempfile", "pty"}
_BLOCKED_BUILTINS = {"eval", "exec", "compile", "__import__", "breakpoint"}


class _ASTSecurityVisitor(_ast.NodeVisitor):
    """AST 순회로 위험 패턴을 탐지."""

    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: _ast.Import):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in _BLOCKED_MODULES:
                self.violations.append(f"blocked import: {alias.name!r}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: _ast.ImportFrom):
        if node.module:
            root = node.module.split(".")[0]
            if root in _BLOCKED_MODULES:
                self.violations.append(f"blocked from-import: {node.module!r}")
        self.generic_visit(node)

    def visit_Call(self, node: _ast.Call):
        if isinstance(node.func, _ast.Name):
            if node.func.id in _BLOCKED_BUILTINS:
                self.violations.append(f"blocked builtin: {node.func.id!r}")
            # open(..., 'w') 파일 쓰기 탐지
            if node.func.id == "open" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, _ast.Constant) and "w" in str(arg.value):
                    self.violations.append("blocked: open() with write mode")
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, _ast.Constant):
                if "w" in str(kw.value.value):
                    self.violations.append("blocked: open() with write mode (kwarg)")
        self.generic_visit(node)

    def visit_Attribute(self, node: _ast.Attribute):
        if isinstance(node.value, _ast.Name) and node.value.id in _BLOCKED_MODULES:
            self.violations.append(f"blocked attribute: {node.value.id}.{node.attr}")
        self.generic_visit(node)


def _security_check(code: str) -> Optional[str]:
    """
    2단계 보안 검사:
    1) regex 빠른 스캔 (기존 패턴)
    2) AST 파싱 기반 정밀 검사
    차단 이유 문자열 반환, 통과 시 None.
    """
    # 1단계: regex
    m = _BLOCKED_RE.search(code)
    if m:
        return f"Blocked pattern (regex): {m.group()!r}"

    # 2단계: AST
    try:
        tree = _ast.parse(code, mode="exec")
    except SyntaxError as e:
        return f"Syntax error in code: {e}"

    visitor = _ASTSecurityVisitor()
    visitor.visit(tree)
    if visitor.violations:
        return "Blocked (AST): " + "; ".join(visitor.violations)

    return None


# ─── Python 실행 ──────────────────────────────────────────────────────────────

async def _run_python(code: str) -> ExecResult:
    """RestrictedPython 없이 subprocess 격리 실행."""
    block_reason = _security_check(code)
    if block_reason:
        return ExecResult(
            stdout="", stderr=block_reason, exit_code=1,
            duration_ms=0, language="python", blocked=True, block_reason=block_reason,
        )

    # 코드를 임시 스크립트로 실행
    script = textwrap.dedent(code)
    python_exe = sys.executable

    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            python_exe, "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=TIMEOUT_SEC
            )
            duration_ms = int((time.time() - start) * 1000)
            return ExecResult(
                stdout=stdout_b[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                stderr=stderr_b[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
                duration_ms=duration_ms,
                language="python",
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecResult(
                stdout="", stderr=f"Execution timed out after {TIMEOUT_SEC}s",
                exit_code=-1, duration_ms=TIMEOUT_SEC * 1000,
                language="python", timed_out=True,
            )
    except Exception as e:
        return ExecResult(
            stdout="", stderr=str(e), exit_code=-1,
            duration_ms=int((time.time() - start) * 1000), language="python",
        )


# ─── Shell 실행 ───────────────────────────────────────────────────────────────

# 허용 명령어 (앞 단어 기준 화이트리스트)
_SHELL_WHITELIST = {
    "echo", "ls", "dir", "pwd", "cat", "head", "tail",
    "python", "python3", "pip", "node", "npm", "git",
    "curl", "wget", "ping",
}


async def _run_shell(code: str) -> ExecResult:
    lines = [l.strip() for l in code.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
    for line in lines:
        first = line.split()[0].lower().rstrip(".exe")
        if first not in _SHELL_WHITELIST:
            reason = f"Shell command not whitelisted: {first!r}"
            return ExecResult(
                stdout="", stderr=reason, exit_code=1,
                duration_ms=0, language="shell", blocked=True, block_reason=reason,
            )

    shell_code = "\n".join(lines)
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_shell(
            shell_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=TIMEOUT_SEC
            )
            return ExecResult(
                stdout=stdout_b[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                stderr=stderr_b[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
                duration_ms=int((time.time() - start) * 1000),
                language="shell",
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecResult(
                stdout="", stderr=f"Timed out after {TIMEOUT_SEC}s",
                exit_code=-1, duration_ms=TIMEOUT_SEC * 1000,
                language="shell", timed_out=True,
            )
    except Exception as e:
        return ExecResult(
            stdout="", stderr=str(e), exit_code=-1,
            duration_ms=int((time.time() - start) * 1000), language="shell",
        )


# ─── 공개 API ─────────────────────────────────────────────────────────────────

async def execute_code(language: str, code: str) -> ExecResult:
    """language: 'python' | 'shell'"""
    if language in ("python", "py"):
        return await _run_python(code)
    elif language in ("shell", "bash", "sh"):
        return await _run_shell(code)
    else:
        return ExecResult(
            stdout="", stderr=f"Unsupported language: {language}",
            exit_code=1, duration_ms=0, language=language,
        )


async def run_code_blocks_sse(
    agent_id: str,
    full_output: str,
) -> AsyncGenerator[dict, None]:
    """에이전트 출력에서 코드 블록을 추출하고 실행하며 SSE 이벤트 dict를 yield.

    이벤트 타입:
      - code_exec_start  { agentId, language, code }
      - code_exec_output { agentId, stdout, stderr }
      - code_exec_done   { agentId, exitCode, durationMs, blocked, timedOut }
    """
    blocks = extract_code_blocks(full_output)
    if not blocks:
        return

    for lang, code in blocks:
        snippet = code[:120] + ("…" if len(code) > 120 else "")
        yield {
            "type": "code_exec_start",
            "agentId": agent_id,
            "language": lang,
            "code": snippet,
        }

        result = await execute_code(lang, code)

        if result.stdout or result.stderr:
            yield {
                "type": "code_exec_output",
                "agentId": agent_id,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
            }

        yield {
            "type": "code_exec_done",
            "agentId": agent_id,
            "exitCode": result.exit_code,
            "durationMs": result.duration_ms,
            "blocked": result.blocked,
            "timedOut": result.timed_out,
            "language": result.language,
        }

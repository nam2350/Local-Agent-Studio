"""Pipeline orchestrator — DAG-based parallel execution with multi-provider support."""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from pipeline.models import RunRequest, ProviderConfig
from providers.registry import registry
from providers.base import BaseProvider
from pipeline.tools import web_search
from orchestration.pydantic_router import extract_target_agents  # Phase 12A
import re

logger = logging.getLogger(__name__)

# ─── Agent definitions ────────────────────────────────────────────────────────

def _get_agent(agent_id: str) -> dict:
    from db import crud
    agent_record = crud.get_agent(agent_id)
    if not agent_record:
        # Fallback for dynamic/custom nodes that might not be in the registry
        return {
            "id": agent_id,
            "label": agent_id.capitalize(),
            "model": "Qwen/Qwen3.5-4B",
            "hf_model": "Qwen/Qwen3.5-4B",
            "system_prompt": "You are a helpful assistant.",
            "role": "assistant",
            "max_tokens": 512,
            "temperature": 0.7,
            "tokensPerSec": 35.0,
            "vramGb": 3.0,
            "warmupSec": 0.5,
        }

    return {
        "id": agent_record["id"],
        "label": agent_record["name"],
        "model": agent_record["model_id"],
        "hf_model": agent_record["model_id"],
        "system_prompt": agent_record["system_prompt"],
        "role": agent_record.get("role", "assistant"),
        "max_tokens": agent_record.get("max_tokens", 512),
        "temperature": agent_record.get("temperature", 0.7),
        "tokensPerSec": 35.0,
        "vramGb": 3.0,
        "warmupSec": 0.5,
    }


class _AgentsByIdDict:
    """A dictionary-like wrapper that lazy-loads agents from the SQLite DB."""
    def __getitem__(self, key: str) -> dict:
        return _get_agent(key)
        
    def __contains__(self, key: str) -> bool:
        from db import crud
        return crud.get_agent(key) is not None

AGENTS_BY_ID = _AgentsByIdDict()

# ─── DAG pipeline stages ──────────────────────────────────────────────────────
# The pipeline is now dynamic. The hardcoded PIPELINE_STAGES logic below
# is retained only as a fallback, but the run_pipeline loop builds it dynamically.

FALLBACK_STAGES: list[list[str]] = [
    ["router-1"],
    ["coder-1", "analyzer-1"],
    ["validator-1"],
    ["synthesizer-1"],
]

# ─── Role-based simulation outputs ───────────────────────────────────────────
# 에이전트 ID가 아닌 role(역할)로 키를 매핑 — 어떤 agent_id가 와도 동작함

_ROLE_SIM_OUTPUTS: dict[str, str] = {
    "router": """\
<think>
The task involves both code generation and architectural analysis.
I need to dispatch to coder-1 for implementation and analyzer-1 for review.
</think>

Analyzing incoming request... Task classification in progress.

[ROUTING ENGINE]
  Input complexity : MODERATE
  Estimated tokens : ~1,200
  Parallelizable   : YES (2 branches)

[DECISION MATRIX]
  → Coder    (confidence: 94%) — code generation required
  → Analyzer (confidence: 89%) — architecture review needed

[EXECUTION PLAN]
  Step 1 · Router      → classify & dispatch
  Step 2 · Coder       → generate implementation  ┐ PARALLEL
  Step 2 · Analyzer    → requirements analysis    ┘
  Step 3 · Validator   → quality & security checks
  Step 4 · Synthesizer → merge & deliver

{"target_agents": ["coder-1", "analyzer-1"], "reason": "Code generation and architecture review both required for this task."}

Dispatching to specialist agents. Pipeline initialized. ✓""",

    "coder": """\
Generating implementation...

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import jwt

app = FastAPI(title="Auth API", version="1.0.0")
SECRET_KEY = "change-me-in-production"
ALGORITHM  = "HS256"

class Token(BaseModel):
    access_token: str
    token_type: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + (expires or timedelta(minutes=30))
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/auth/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    token = create_access_token({"sub": form.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload.get("sub")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
```
Implementation complete. ✓""",

    "analyzer": """\
Deep analysis initiated...

[SECURITY REVIEW]
  ✓ JWT signing       : HS256 (consider RS256 for distributed systems)
  ✓ Token expiry      : 30 min (RFC 6749 §4.1.4 compliant)
  ⚠ Refresh tokens   : not implemented → session expiry risk
  ⚠ Rate limiting     : absent on /auth/login → brute-force vector

[ARCHITECTURE ASSESSMENT]
  Pattern       : OAuth2 Password Flow
  Scalability   : Stateless JWT — horizontally scalable ✓
  Performance   : Login P99 ~45ms | Token verify ~0.3ms

Recommendations forwarded to Validator & Synthesizer. ✓""",

    "validator": """\
Running validation suite...

[CODE QUALITY]   Score: 94 / 100
  ✓ Type hints        : complete
  ✓ Error handling    : HTTPException with codes
  ✗ Rate limiting absent          → WARN: add slowapi
  ✗ No account lockout mechanism  → WARN: add Redis counter

[SECURITY SCAN]
  ✓ No plaintext passwords stored
  ✓ No SQL injection vectors

[VERDICT]   APPROVED ✓
VALIDATION: PASS
Proceed with recommended hardening before production.""",

    "synthesizer": """\
Synthesizing outputs from all agents...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FINAL SYNTHESIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Production-ready implementation generated.

Parallel analysis completed successfully.

Priority Actions:
  [HIGH]   Add /auth/refresh endpoint
  [HIGH]   Implement rate limiting (5 req/min)
  [MEDIUM] Switch to RS256 for multi-service deployments

Pipeline complete. All agents finished successfully. ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",

    "vision": """\
Analyzing visual content...

[VISUAL ANALYSIS]
  Layout        : Grid-based, 12-column responsive ✓
  Accessibility : WCAG 2.1 AA compliant (contrast ratio 4.7:1) ✓
  Components    : 14 UI elements detected

[DESIGN REVIEW]
  Typography    : Consistent scale (16px base, 1.5 line-height)
  Color palette : 4 primary colors + 2 accent — cohesive ✓
  Spacing       : 8px grid system applied throughout

[RECOMMENDATIONS]
  ⚠ Add aria-labels to icon-only buttons (3 found)
  ⚠ Increase touch target size on mobile (min 44×44px)

Visual analysis complete. ✓""",

    "assistant": "Processing your request...\n\nAnalysis complete. Ready for next stage.",
}

_ROLE_SIM_DEFAULT = "Processing...\n\nTask handled. Passing results downstream."


def _get_sim_output(agent: dict) -> str:
    """에이전트의 role을 기반으로 시뮬레이션 출력을 반환."""
    role = agent.get("role", "assistant")
    return _ROLE_SIM_OUTPUTS.get(role, _ROLE_SIM_DEFAULT)


# ─── SSE helper ───────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _parse_sse(event_str: str) -> Optional[dict]:
    if not event_str.startswith("data: "):
        return None
    try:
        return json.loads(event_str[6:])
    except Exception:
        return None


# ─── Provider resolution ──────────────────────────────────────────────────────

def _resolve_provider(agent: dict, request: RunRequest) -> Optional[BaseProvider]:
    if not request.use_real_models:
        return None

    agent_cfg = None
    if request.agent_configs:
        agent_cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)

    cfg: ProviderConfig = agent_cfg.provider if agent_cfg else request.default_provider

    if cfg.type == "simulation":
        return None

    if cfg.type == "transformers":
        model_id = cfg.model_id or agent.get("hf_model", agent["model"])
        return registry.get_transformers(model_id=model_id)

    model = cfg.model_id or agent["model"]
    return registry.get_openai_compat(
        provider_type=cfg.type,
        model=model,
        base_url=cfg.base_url,
    )


_TOOL_SCHEMAS = {
    "web_search": '{"name": "web_search", "arguments": {"query": "your search query"}}',
    "calculator": '{"name": "calculator", "arguments": {"expression": "2 + 2 * 3"}}',
    "read_file":  '{"name": "read_file", "arguments": {"path": "relative/file.txt"}}',
}
_TOOL_DESCRIPTIONS = {
    "web_search": "Search the web for current/recent information (DuckDuckGo).",
    "calculator": "Evaluate a math expression and return the numeric result.",
    "read_file":  "Read a text file from the local workspace by relative path.",
}


def _resolve_system_prompt(agent: dict, request: RunRequest) -> str:
    base_prompt = agent.get("system_prompt", "")
    active_tools: list[str] = []

    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            if cfg.system_prompt:
                base_prompt = cfg.system_prompt
            if cfg.tools:
                active_tools = cfg.tools

    if active_tools:
        tool_lines = "\n".join(
            f"- {t}: {_TOOL_DESCRIPTIONS.get(t, '')}  Example: {_TOOL_SCHEMAS.get(t, '')}"
            for t in active_tools if t in _TOOL_SCHEMAS
        )
        tools_addon = (
            "\n\n[TOOLS AVAILABLE]\nWhen you need external information, output ONLY a JSON object on its own line:\n"
            f"{tool_lines}\n"
            "Output normal text if no tool is needed."
        )
        base_prompt += tools_addon

    return base_prompt


def _resolve_rag_context(agent: dict, prompt: str, request: RunRequest) -> Optional[str]:
    """Phase 22: RAG 컨텍스트를 에이전트 입력 앞에 주입.

    에이전트별 rag_collections 목록에서 각 컬렉션을 검색하여 컨텍스트를 합산.
    """
    if not request.agent_configs:
        return None
    cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
    if not cfg or not cfg.rag_collections:
        return None

    try:
        from rag.retriever import build_rag_context
    except Exception:
        return None

    contexts: list[str] = []
    for col_name in cfg.rag_collections:
        ctx = build_rag_context(col_name, prompt, top_k=4)
        if ctx:
            contexts.append(ctx)

    return "\n\n".join(contexts) if contexts else None


def _resolve_max_tokens(agent: dict, request: RunRequest) -> int:
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            return cfg.max_tokens
    # agent_configs 없음 → DB에 저장된 에이전트별 max_tokens 사용
    return agent.get("max_tokens", 512)


def _resolve_temperature(agent: dict, request: RunRequest) -> float:
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            return cfg.temperature
    # agent_configs 없음 → DB에 저장된 에이전트별 temperature 사용
    return agent.get("temperature", 0.7)


# ─── Agent input builder ──────────────────────────────────────────────────────

def _build_agent_input(prompt: str, agent_id: str, previous: dict) -> str:
    """이전 에이전트 출력을 컨텍스트로 포함한 입력 프롬프트를 생성.

    agent_id에 의존하지 않는 제네릭 구현 — 어떤 파이프라인 구성도 지원.
    """
    if not previous:
        return prompt
    ctx_parts = [f"Original task: {prompt}"]
    for prev_id, prev_out in previous.items():
        # Qwen3.5 Thinking Mode: thinking 태그 제거 후 컨텍스트에 포함
        cleaned_out = re.sub(r"<think>.*?</think>", "", str(prev_out), flags=re.DOTALL).strip()
        ctx_parts.append(f"\n--- {prev_id} output ---\n{cleaned_out[:800]}")
    return "\n".join(ctx_parts)


# ─── Simulation generator ─────────────────────────────────────────────────────

async def _simulate_agent(agent: dict) -> AsyncGenerator[str, None]:
    tps = agent["tokensPerSec"]
    delay = 1.0 / tps
    output = _get_sim_output(agent)
    for word in output.split(" "):
        await asyncio.sleep(delay)
        yield word + " "


# ─── Single-agent runner ──────────────────────────────────────────────────────

async def _run_single_agent(
    agent: dict,
    previous_outputs: dict,
    prompt: str,
    request: RunRequest,
) -> AsyncGenerator[str, None]:
    """Yield SSE strings for one agent. Stores full output in previous_outputs when done."""
    agent_id    = agent["id"]
    provider    = _resolve_provider(agent, request)
    pname       = provider.provider_type if provider else "simulation"
    agent_input = _build_agent_input(prompt, agent_id, previous_outputs)

    # Phase 22: RAG 컨텍스트 주입 (에이전트별 rag_collections 설정 시)
    rag_ctx = _resolve_rag_context(agent, prompt, request)
    if rag_ctx:
        agent_input = rag_ctx + "\n\n" + agent_input

    # agent_start
    yield sse({
        "type": "agent_start",
        "agentId": agent_id,
        "label": agent["label"],
        "model": agent["model"],
        "provider": pname,
    })

    # VRAM warmup — 시뮬레이션: 기존 애니메이션 유지 / 실제 모델: 즉시 실측값 전송
    vram   = agent["vramGb"]
    warmup = agent["warmupSec"]
    if provider is None:
        for i in range(1, 7):
            await asyncio.sleep(warmup / 6)
            yield sse({"type": "agent_vram", "agentId": agent_id, "vramGb": round(vram * i / 6, 2)})
    else:
        from providers.transformers_provider import TransformersProvider
        yield sse({"type": "agent_vram", "agentId": agent_id, "vramGb": TransformersProvider.get_vram_allocated_gb()})

    # Token streaming
    agent_tokens = 0
    agent_start_t = time.time()
    full_output = ""

    async def _stream_tokens():
        nonlocal agent_tokens, full_output
        if provider:
            try:
                if not await provider.health_check():
                    raise RuntimeError(f"{pname} unreachable")
                async for token_text in provider.generate(
                    prompt=agent_input,
                    system_prompt=_resolve_system_prompt(agent, request),
                    max_tokens=_resolve_max_tokens(agent, request),
                    temperature=_resolve_temperature(agent, request),
                ):
                    if token_text.startswith("__SSE__:"):
                        try:
                            sse_data = json.loads(token_text[8:])
                            sse_data["agentId"] = agent_id
                            yield sse(sse_data)
                        except Exception:
                            pass
                        continue

                    full_output += token_text
                    agent_tokens += max(1, len(token_text.split()))
                    elapsed = time.time() - agent_start_t
                    tps = round(agent_tokens / elapsed, 1) if elapsed > 0 else 0
                    yield sse({"type": "agent_token", "agentId": agent_id, "token": token_text, "totalTokens": agent_tokens, "tokensPerSec": tps})
                return
            except Exception as e:
                logger.warning(f"[{agent_id}] Provider {pname} failed ({e}), falling back to simulation")

        # Simulation (or fallback)
        async for chunk in _simulate_agent(agent):
            full_output += chunk
            agent_tokens += 1
            elapsed = time.time() - agent_start_t
            tps = round(agent_tokens / elapsed, 1) if elapsed > 0 else 0
            yield sse({"type": "agent_token", "agentId": agent_id, "token": chunk, "totalTokens": agent_tokens, "tokensPerSec": tps})

    async for event_str in _stream_tokens():
        yield event_str

    # ── Tool Interception & Execution ──
    # Detect any tool call JSON in the output (any of the 3 supported tools).
    # Pattern: {"name": "tool_name", "arguments": {...}}
    tool_json_pattern = re.compile(
        r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})\s*\}',
        re.DOTALL
    )
    tool_matches = list(tool_json_pattern.finditer(full_output))

    # Resolve which tools are enabled for this agent
    active_tools: list[str] = []
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent_id), None)
        if cfg and cfg.tools:
            active_tools = cfg.tools

    if tool_matches and (provider or active_tools):
        allowed_tools = active_tools or ["web_search", "calculator", "read_file"]
        tool_results_context = ""

        for tool_match in tool_matches:
            tool_name = tool_match.group(1)
            args_str  = tool_match.group(2)

            if tool_name not in allowed_tools:
                continue

            try:
                tool_args = json.loads(args_str)
            except json.JSONDecodeError:
                tool_args = {}

            yield sse({
                "type": "tool_call",
                "agentId": agent_id,
                "tool": tool_name,
                "input": tool_args,
            })

            # Execute the tool
            if tool_name == "web_search":
                tool_result = web_search(tool_args.get("query", ""))
            else:
                from tools.executor import execute_tool
                tool_result = execute_tool(tool_name, tool_args)

            yield sse({
                "type": "tool_result",
                "agentId": agent_id,
                "tool": tool_name,
                "output": tool_result[:500],
            })

            # Notify user via token stream
            yield sse({
                "type": "agent_token",
                "agentId": agent_id,
                "token": f"\n\n[{tool_name.upper()} RESULT]\n{tool_result[:400]}\n\n",
                "totalTokens": agent_tokens,
                "tokensPerSec": 0,
            })

            tool_results_context += (
                f"\n[TOOL RESULT for {tool_name}({args_str})]:\n{tool_result}\n"
            )

        # ── Second pass: re-prompt with all tool results ──
        if tool_results_context and provider:
            tool_prompt = (
                f"{agent_input}\n\n"
                f"{tool_results_context}\n"
                "Now provide your final answer based on the tool results above."
            )
            added_output = ""
            try:
                async for token_text in provider.generate(
                    prompt=tool_prompt,
                    system_prompt=agent.get("system_prompt", ""),
                    max_tokens=_resolve_max_tokens(agent, request),
                    temperature=_resolve_temperature(agent, request),
                ):
                    added_output += token_text
                    agent_tokens += max(1, len(token_text.split()))
                    elapsed = time.time() - agent_start_t
                    tps = round(agent_tokens / elapsed, 1) if elapsed > 0 else 0
                    yield sse({"type": "agent_token", "agentId": agent_id, "token": token_text, "totalTokens": agent_tokens, "tokensPerSec": tps})
                full_output += "\n\n[Tool Results Applied]\n" + added_output
            except Exception as e:
                logger.warning(f"[{agent_id}] Re-prompting after tool calls failed: {e}")

    # Store output BEFORE yielding agent_done
    previous_outputs[agent_id] = full_output

    latency_ms = int((time.time() - agent_start_t) * 1000)
    if provider is not None:
        from providers.transformers_provider import TransformersProvider
        final_vram = TransformersProvider.get_vram_allocated_gb()
    else:
        final_vram = vram  # 시뮬레이션: 하드코딩 기본값
    yield sse({
        "type": "agent_done",
        "agentId": agent_id,
        "totalTokens": agent_tokens,
        "tokensPerSec": round(agent_tokens / max(latency_ms / 1000, 0.001), 1),
        "latencyMs": latency_ms,
        "vramGb": final_vram,
        "provider": pname,
    })


# ─── Parallel stage runner ────────────────────────────────────────────────────

async def _run_parallel_stage(
    agents: list[dict],
    previous_outputs: dict,
    prompt: str,
    request: RunRequest,
) -> AsyncGenerator[str, None]:
    """에이전트 스테이지 실행.

    시뮬레이션(use_real_models=False): asyncio 병렬 실행 (기존 동작 100% 유지)
    실제 모델(use_real_models=True): 순차 실행 → VRAM OOM 방지 (Stage 2 ~15GB 위험)
    """
    if request.use_real_models:
        # 순차 실행 — 실제 모델은 동시 로드 시 VRAM 초과 위험
        logger.info(
            "[orchestrator] Stage %s → sequential (real models, OOM prevention)",
            [a["id"] for a in agents],
        )
        for agent in agents:
            async for event_str in _run_single_agent(agent, previous_outputs, prompt, request):
                yield event_str
        return

    # 시뮬레이션: 기존 asyncio 병렬 실행 (불변)
    queue: asyncio.Queue = asyncio.Queue()

    async def collect(agent: dict) -> None:
        async for event_str in _run_single_agent(agent, previous_outputs, prompt, request):
            await queue.put(event_str)
        await queue.put(None)  # sentinel

    tasks = [asyncio.create_task(collect(a)) for a in agents]

    done = 0
    while done < len(agents):
        item = await queue.get()
        if item is None:
            done += 1
        else:
            yield item

    await asyncio.gather(*tasks)


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def run_pipeline(
    prompt: str,
    request: Optional[RunRequest] = None,
) -> AsyncGenerator[str, None]:
    if request is None:
        request = RunRequest(prompt=prompt)

    # ── Phase 12B: orchestration_mode 분기 ─────────────────────────────────────
    mode = getattr(request, "orchestration_mode", "dag")
    if mode == "langgraph":
        try:
            from orchestration.langgraph_engine import run_langgraph_pipeline
            async for event_str in run_langgraph_pipeline(prompt, request):
                yield event_str
            return
        except ImportError as e:
            logger.warning("[orchestrator] langgraph not installed (%s), falling back to DAG", e)
        except Exception as e:
            logger.exception("[orchestrator] langgraph pipeline failed")
            yield sse({"type": "pipeline_error", "message": f"LangGraph failed: {e}"})
            return
    # ── 기존 DAG 로직 (한 줄도 변경 없음) ────────────────────────────────────────

    pipeline_start    = time.time()
    previous_outputs: dict = {}
    agent_tokens_map: dict = {}   # agent_id → total tokens (from agent_done events)
    agent_stats_map: dict  = {}   # agent_id → {tokens, latency_ms, vram_gb}

    # Phase 13: 대화 이력 컨텍스트 주입 (router-1 입력에만)
    router_prompt = prompt
    session_id = getattr(request, "session_id", None)
    if session_id:
        try:
            from db import crud as _crud
            turns = _crud.list_turns(session_id)
            if turns:
                history_parts = []
                for t in turns[-3:]:  # 최근 3턴만
                    outputs = _crud.list_agent_outputs(t["id"])
                    synth = next((o for o in outputs if o["role"] == "synthesizer"), None)
                    summary = synth["full_output"][:400] if synth else ""
                    history_parts.append(
                        f"Turn {t['turn_index'] + 1}: User asked: {t['user_prompt'][:100]}"
                        + (f"\nSummary: {summary}" if summary else "")
                    )
                if history_parts:
                    router_prompt = (
                        "=== Previous conversation ===\n"
                        + "\n---\n".join(history_parts)
                        + "\n=== Current request ===\n"
                        + prompt
                    )
        except Exception as e:
            logger.warning("[orchestrator] conversation history load failed: %s", e)

    yield sse({
        "type": "pipeline_start",
        "totalAgents": sum(len(s) for s in FALLBACK_STAGES),  # 5: router+coder+analyzer+validator+synthesizer
        "prompt": prompt[:120],
    })

    # --- STAGE 1: ROUTER ---
    stage_idx = 0
    gen_router = _run_single_agent(AGENTS_BY_ID["router-1"], previous_outputs, router_prompt, request)
    async for event_str in gen_router:
        parsed = _parse_sse(event_str)
        if parsed and parsed.get("type") == "agent_done":
            aid = parsed["agentId"]
            agent_tokens_map[aid] = parsed.get("totalTokens", 0)
            agent_stats_map[aid] = {
                "tokens": parsed.get("totalTokens", 0),
                "latency_ms": parsed.get("latencyMs", 0),
                "vram_gb": parsed.get("vramGb", 0.0),
            }
        yield event_str

    router_output = previous_outputs.get("router-1", "")

    # Qwen3.5 Thinking Mode: <think>...</think> 태그 제거 후 파싱
    router_output_clean = re.sub(r"<think>.*?</think>", "", router_output, flags=re.DOTALL).strip()

    # --- DYNAMIC ROUTING LOGIC (Phase 12A: PydanticAI 가드레일) ---
    # 3단계 파싱: JSON → regex → fallback
    parsed_agents = extract_target_agents(
        output=router_output_clean,
        structured_routing=getattr(request, "structured_routing", True),
    )
    if parsed_agents is None:
        stage_2_agents = ["coder-1", "analyzer-1"]  # Stage 3: fallback
    else:
        stage_2_agents = parsed_agents               # Stage 1 or 2 성공

    dynamic_stages = []
    if stage_2_agents:
        dynamic_stages.append(stage_2_agents)
        if "coder-1" in stage_2_agents:
            dynamic_stages.append(["validator-1"])
            
    dynamic_stages.append(["synthesizer-1"])

    # --- EXECUTE REMAINING STAGES ---
    for stage_ids in dynamic_stages:
        stage_idx += 1
        agents = [AGENTS_BY_ID[aid] for aid in stage_ids]
        is_parallel = len(agents) > 1

        # Emit stage info for parallel stages
        if is_parallel:
            yield sse({
                "type": "stage_parallel",
                "stageIndex": stage_idx,
                "agentIds": stage_ids,
            })

        # Run stage
        if is_parallel:
            gen = _run_parallel_stage(agents, previous_outputs, prompt, request)
        else:
            gen = _run_single_agent(agents[0], previous_outputs, prompt, request)

        async for event_str in gen:
            # Track token totals from agent_done events
            parsed = _parse_sse(event_str)
            if parsed and parsed.get("type") == "agent_done":
                aid = parsed["agentId"]
                agent_tokens_map[aid] = parsed.get("totalTokens", 0)
                agent_stats_map[aid] = {
                    "tokens": parsed.get("totalTokens", 0),
                    "latency_ms": parsed.get("latencyMs", 0),
                    "vram_gb": parsed.get("vramGb", 0.0),
                }
            yield event_str

        # Brief pause between stages
        if stage_idx < len(dynamic_stages):
            await asyncio.sleep(0.2)

    total_tokens = sum(agent_tokens_map.values())
    total_ms     = int((time.time() - pipeline_start) * 1000)

    yield sse({
        "type": "pipeline_done",
        "totalPipelineTokens": total_tokens,
        "totalPipelineMs": total_ms,
    })

    # Phase 15: 실행 히스토리 저장
    try:
        from db import crud as _crud_run
        _provider = request.default_provider.type if request.default_provider else "simulation"
        _mode     = getattr(request, "orchestration_mode", "dag")
        _crud_run.create_run(
            prompt=prompt,
            provider=_provider,
            orchestration_mode=_mode,
            status="success",
            total_tokens=total_tokens,
            total_ms=total_ms,
            agent_outputs={aid: out[:800] for aid, out in previous_outputs.items()},
        )
    except Exception as _e:
        logger.warning("[orchestrator] Failed to save run history: %s", _e)

    # Phase 13: 대화 세션에 턴 저장
    if session_id:
        try:
            from db import crud as _crud2
            if not _crud2.get_session(session_id):
                title = prompt[:60] + ("..." if len(prompt) > 60 else "")
                _crud2.create_session(session_id, title)
            turn_idx = _crud2.get_session_turn_count(session_id)
            mode = getattr(request, "orchestration_mode", "dag")
            turn_id = _crud2.create_turn(session_id, turn_idx, prompt, mode)
            for aid, output_text in previous_outputs.items():
                stats = agent_stats_map.get(aid, {})
                agent_rec = _crud2.get_agent(aid)
                role = agent_rec["role"] if agent_rec else "assistant"
                _crud2.create_agent_output(
                    turn_id=turn_id,
                    agent_id=aid,
                    role=role,
                    full_output=output_text,
                    token_count=stats.get("tokens", 0),
                    latency_ms=stats.get("latency_ms", 0),
                    vram_gb=stats.get("vram_gb", 0.0),
                )
            logger.info("[orchestrator] Saved turn %d for session %s", turn_idx, session_id)
        except Exception as e:
            logger.warning("[orchestrator] Failed to save conversation turn: %s", e)

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
import re

logger = logging.getLogger(__name__)

# ─── Agent definitions ────────────────────────────────────────────────────────

AGENTS = [
    {
        "id": "router-1",
        "label": "Router",
        "model": "Qwen2.5-3B-Instruct",
        "hf_model": "Qwen/Qwen2.5-3B-Instruct",
        "system_prompt": (
            "You are a task routing system. Analyze the user request briefly. "
            "Classify the task type, estimate complexity, and decide which specialist "
            "agents are needed: 'coder-1' (for coding/programming), 'analyzer-1' (for architecture/security review).\n\n"
            "CRITICAL: You MUST include a line exactly like this in your response:\n"
            "[TARGET_AGENTS] coder-1, analyzer-1\n"
            "If no specialists are needed (e.g. general chat), output: [TARGET_AGENTS] none"
        ),
        "tokensPerSec": 52.0,
        "vramGb": 2.4,
        "warmupSec": 0.4,
    },
    {
        "id": "coder-1",
        "label": "Code Writer",
        "model": "Qwen2.5-Coder-7B",
        "hf_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "system_prompt": (
            "You are an expert programmer. Generate clean, working code for the task. "
            "Include type hints and brief comments. Keep the implementation concise."
        ),
        "tokensPerSec": 34.0,
        "vramGb": 5.1,
        "warmupSec": 0.7,
    },
    {
        "id": "analyzer-1",
        "label": "Analyzer",
        "model": "Gemma-3-4B-IT",
        "hf_model": "google/gemma-3-4b-it",
        "system_prompt": (
            "You are a technical analyst. Review the task and any code provided. "
            "Identify security issues, performance concerns, and give brief recommendations."
        ),
        "tokensPerSec": 41.0,
        "vramGb": 3.1,
        "warmupSec": 0.5,
    },
    {
        "id": "validator-1",
        "label": "Validator",
        "model": "Phi-4-mini-4B",
        "hf_model": "microsoft/phi-4-mini-instruct",
        "system_prompt": (
            "You are a code quality expert. Score the provided code out of 100 for "
            "quality and security. List top 3 issues. Give a final verdict: APPROVED or NEEDS_REVISION."
        ),
        "tokensPerSec": 58.0,
        "vramGb": 3.3,
        "warmupSec": 0.4,
    },
    {
        "id": "synthesizer-1",
        "label": "Synthesizer",
        "model": "Llama-3.1-8B-Instruct",
        "hf_model": "meta-llama/Llama-3.1-8B-Instruct",
        "system_prompt": (
            "You are a technical writer. Synthesize the outputs from all agents into "
            "a clear final summary. Include: implementation overview, quality score, "
            "top recommendations. Be concise."
        ),
        "tokensPerSec": 26.0,
        "vramGb": 5.9,
        "warmupSec": 0.8,
    },
]

AGENTS_BY_ID = {a["id"]: a for a in AGENTS}

# ─── DAG pipeline stages ──────────────────────────────────────────────────────
# The pipeline is now dynamic. The hardcoded PIPELINE_STAGES logic below
# is retained only as a fallback, but the run_pipeline loop builds it dynamically.

FALLBACK_STAGES: list[list[str]] = [
    ["router-1"],
    ["coder-1", "analyzer-1"],
    ["validator-1"],
    ["synthesizer-1"],
]

# ─── Simulation outputs ───────────────────────────────────────────────────────

AGENT_OUTPUTS = {
    "router-1": """\
Analyzing incoming request... Task classification in progress.

[ROUTING ENGINE]
  Input complexity : MODERATE
  Estimated tokens : ~1,200
  Parallelizable   : YES (2 branches)

[DECISION MATRIX]
  → Code Writer   (confidence: 94%) — code generation required
  → Analyzer      (confidence: 89%) — architecture review needed

[EXECUTION PLAN]
  Step 1 · Router    → classify & dispatch
  Step 2 · Coder     → generate implementation  ┐ PARALLEL
  Step 2 · Analyzer  → requirements analysis    ┘
  Step 3 · Validator → quality & security checks
  Step 4 · Synthesizer → merge & deliver

Dispatching to specialist agents. Pipeline initialized. ✓""",

    "coder-1": """\
Generating implementation...

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import jwt, bcrypt

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

    "analyzer-1": """\
Deep analysis initiated... [RUNNING IN PARALLEL WITH CODER]

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

    "validator-1": """\
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
Proceed with recommended hardening before production.""",

    "synthesizer-1": """\
Synthesizing outputs from all agents...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FINAL SYNTHESIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FastAPI JWT Auth — production-ready implementation generated.

Security Score : 94 / 100  ·  Code Quality: 94 / 100

Parallel analysis completed:
  Coder    → implementation generated (JWT + OAuth2)
  Analyzer → security & architecture reviewed simultaneously

Priority Actions:
  [HIGH]   Add /auth/refresh endpoint
  [HIGH]   Implement rate limiting (slowapi, 5 req/min)
  [MEDIUM] Switch to RS256 for multi-service deployments

Pipeline complete. All agents finished successfully. ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
}


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
        return registry.get_transformers(
            model_id=model_id,
            load_in_4bit=cfg.load_in_4bit,
            load_in_8bit=cfg.load_in_8bit,
        )

    model = cfg.model_id or agent["model"]
    return registry.get_openai_compat(
        provider_type=cfg.type,
        model=model,
        base_url=cfg.base_url,
    )


def _resolve_system_prompt(agent: dict, request: RunRequest) -> str:
    base_prompt = agent.get("system_prompt", "")
    active_tools = []
    
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            if cfg.system_prompt:
                base_prompt = cfg.system_prompt
            if cfg.tools:
                active_tools = cfg.tools

    if "web_search" in active_tools:
        tools_addon = (
            "\n\n[TOOLS]\nYou have access to the following tools if external/recent information is needed. "
            "To use a tool, YOU MUST output ONLY a valid JSON object matching this schema, nothing else:\n"
            '{"name": "web_search", "arguments": { "query": "your search query here" }}\n'
            "If no tool is needed, output normal text."
        )
        base_prompt += tools_addon
        
    return base_prompt


def _resolve_max_tokens(agent: dict, request: RunRequest) -> int:
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            return cfg.max_tokens
    return 512


def _resolve_temperature(agent: dict, request: RunRequest) -> float:
    if request.agent_configs:
        cfg = next((c for c in request.agent_configs if c.agent_id == agent["id"]), None)
        if cfg:
            return cfg.temperature
    return 0.7


# ─── Agent input builder ──────────────────────────────────────────────────────

def _build_agent_input(prompt: str, agent_id: str, previous: dict) -> str:
    if agent_id == "router-1":
        return prompt
    if agent_id == "coder-1":
        return f"Task: {prompt}\n\nRouter decision:\n{previous.get('router-1', '')}"
    if agent_id == "analyzer-1":
        return f"Task: {prompt}\n\nRouter analysis:\n{previous.get('router-1', '')}"
    if agent_id == "validator-1":
        return f"Review this code:\n{previous.get('coder-1', '')}"
    if agent_id == "synthesizer-1":
        parts = [f"Original task: {prompt}"]
        for aid, lbl in [("router-1","Router"),("coder-1","Coder"),("analyzer-1","Analyzer"),("validator-1","Validator")]:
            if aid in previous:
                parts.append(f"\n--- {lbl} ---\n{previous[aid]}")
        return "\n".join(parts)
    return prompt


# ─── Simulation generator ─────────────────────────────────────────────────────

async def _simulate_agent(agent: dict) -> AsyncGenerator[str, None]:
    tps = agent["tokensPerSec"]
    delay = 1.0 / tps
    output = AGENT_OUTPUTS.get(agent["id"], "Processing...")
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

    # agent_start
    yield sse({
        "type": "agent_start",
        "agentId": agent_id,
        "label": agent["label"],
        "model": agent["model"],
        "provider": pname,
    })

    # VRAM warmup
    vram   = agent["vramGb"]
    warmup = agent["warmupSec"]
    for i in range(1, 7):
        await asyncio.sleep(warmup / 6)
        yield sse({"type": "agent_vram", "agentId": agent_id, "vramGb": round(vram * i / 6, 2)})

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
    # Check if the generated full_output is asking for a tool call JSON.
    # Simple regex to catch json blocks or inline json.
    tool_pattern = re.compile(r'\{\s*"name"\s*:\s*"web_search"\s*,\s*"arguments"\s*:\s*\{\s*"query"\s*:\s*"(.*?)"\s*\}\s*\}')
    match = tool_pattern.search(full_output)
    
    if match and provider: # Execute tool if matched and running real models
        query = match.group(1)
        yield sse({
            "type": "agent_token", 
            "agentId": agent_id, 
            "token": f"\n\n[SYSTEM: Executing Web Search for '{query}'...]\n\n",
            "totalTokens": agent_tokens,
            "tokensPerSec": 0
        })
        
        # Actually run python tool
        search_results = web_search(query)
        
        # Build new prompt
        tool_prompt = f"{agent_input}\n\n[TOOL CALL RESULT for '{query} भी']:\n{search_results}\n\nNow, provide a final response strictly based on the tool results above."
        
        yield sse({
            "type": "agent_token", 
            "agentId": agent_id, 
            "token": "[SYSTEM: Results received, generating final response...]\n\n",
            "totalTokens": agent_tokens,
            "tokensPerSec": 0
        })
        
        # Second stream phase (Re-prompt with results)
        added_output = ""
        try:
            async for token_text in provider.generate(
                prompt=tool_prompt,
                system_prompt=_resolve_system_prompt(agent, request),
                max_tokens=_resolve_max_tokens(agent, request),
                temperature=_resolve_temperature(agent, request),
            ):
                added_output += token_text
                agent_tokens += max(1, len(token_text.split()))
                elapsed = time.time() - agent_start_t
                tps = round(agent_tokens / elapsed, 1) if elapsed > 0 else 0
                yield sse({"type": "agent_token", "agentId": agent_id, "token": token_text, "totalTokens": agent_tokens, "tokensPerSec": tps})
            
            full_output += f"\n\n[Search Results Used] \n" + added_output
        except Exception as e:
            logger.warning(f"[{agent_id}] Re-prompting failed: {e}")

    # Store output BEFORE yielding agent_done
    previous_outputs[agent_id] = full_output

    latency_ms = int((time.time() - agent_start_t) * 1000)
    yield sse({
        "type": "agent_done",
        "agentId": agent_id,
        "totalTokens": agent_tokens,
        "tokensPerSec": round(agent_tokens / max(latency_ms / 1000, 0.001), 1),
        "latencyMs": latency_ms,
        "vramGb": vram,
        "provider": pname,
    })


# ─── Parallel stage runner ────────────────────────────────────────────────────

async def _run_parallel_stage(
    agents: list[dict],
    previous_outputs: dict,
    prompt: str,
    request: RunRequest,
) -> AsyncGenerator[str, None]:
    """Run multiple agents concurrently, merging their SSE streams."""
    queue: asyncio.Queue = asyncio.Queue()

    async def collect(agent: dict) -> None:
        async for event_str in _run_single_agent(agent, previous_outputs, prompt, request):
            await queue.put(event_str)
        await queue.put(None)  # sentinel for this agent

    # Launch all agents in parallel
    tasks = [asyncio.create_task(collect(a)) for a in agents]

    done = 0
    while done < len(agents):
        item = await queue.get()
        if item is None:
            done += 1
        else:
            yield item

    # Ensure all tasks completed (they should be by now)
    await asyncio.gather(*tasks)


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def run_pipeline(
    prompt: str,
    request: Optional[RunRequest] = None,
) -> AsyncGenerator[str, None]:
    if request is None:
        request = RunRequest(prompt=prompt)

    pipeline_start    = time.time()
    previous_outputs: dict = {}
    agent_tokens_map: dict = {}   # agent_id → total tokens (from agent_done events)

    # Count total agents roughly (will adjust later)
    yield sse({
        "type": "pipeline_start",
        "totalAgents": 4, # Estimated default
        "prompt": prompt[:120],
    })

    # --- STAGE 1: ROUTER ---
    stage_idx = 0
    gen_router = _run_single_agent(AGENTS_BY_ID["router-1"], previous_outputs, prompt, request)
    async for event_str in gen_router:
        parsed = _parse_sse(event_str)
        if parsed and parsed.get("type") == "agent_done":
            agent_tokens_map[parsed["agentId"]] = parsed.get("totalTokens", 0)
        yield event_str

    router_output = previous_outputs.get("router-1", "")
    
    # --- DYNAMIC ROUTING LOGIC ---
    # Parse [TARGET_AGENTS] from router output
    target_agents_str = ""
    match = re.search(r'\[TARGET_AGENTS\](.*?)(?:\n|$)', router_output)
    if match:
        target_agents_str = match.group(1).lower()
    
    stage_2_agents = []
    if "coder-1" in target_agents_str or "coder" in target_agents_str:
        stage_2_agents.append("coder-1")
    if "analyzer-1" in target_agents_str or "analyzer" in target_agents_str:
        stage_2_agents.append("analyzer-1")
        
    # If no valid agents parsed but it's not explicitly "none", fallback to all
    if not stage_2_agents and "none" not in target_agents_str:
        stage_2_agents = ["coder-1", "analyzer-1"]

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
                agent_tokens_map[parsed["agentId"]] = parsed.get("totalTokens", 0)
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

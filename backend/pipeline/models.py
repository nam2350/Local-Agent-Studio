from pydantic import BaseModel
from typing import Literal, Optional, List


class ProviderConfig(BaseModel):
    type: Literal["ollama", "lmstudio", "llamacpp", "transformers", "simulation"] = "simulation"
    base_url: Optional[str] = None    # for openai-compat backends
    model_id: Optional[str] = None    # HF model ID for transformers (fp16만 지원, bitsandbytes 없음)


class AgentRunConfig(BaseModel):
    agent_id: str
    provider: ProviderConfig = ProviderConfig()
    system_prompt: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    tools: Optional[List[str]] = None       # e.g. ["web_search", "calculator"]
    rag_collections: Optional[List[str]] = None  # Phase 22: RAG 컬렉션 이름 목록
    auto_execute: bool = False               # Phase 21: 코드 블록 자동 실행 (coder role)


class RunRequest(BaseModel):
    prompt: str = "Build a user authentication REST API with JWT tokens"
    use_real_models: bool = False
    default_provider: ProviderConfig = ProviderConfig()
    agent_configs: Optional[List[AgentRunConfig]] = None
    # Phase 12A: 구조화된 JSON 라우팅 활성화
    # True(기본): JSON → regex → fallback 3단계 파싱
    # False: regex → fallback만 사용 (하위 호환)
    structured_routing: bool = True
    # Phase 12B: 오케스트레이션 모드
    # "dag"       — 기존 DAG 파이프라인 (완전 불변, 기본값)
    # "langgraph" — LangGraph StateGraph (Validator 루프백 포함)
    orchestration_mode: Literal["dag", "langgraph"] = "dag"
    # Phase 13: 대화 세션 ID (None이면 저장 안 함)
    session_id: Optional[str] = None


class PipelineEvent(BaseModel):
    type: Literal[
        "pipeline_start",
        "agent_start",
        "agent_token",
        "agent_vram",
        "agent_done",
        "tool_call",
        "tool_result",
        "stage_parallel",
        "pipeline_done",
        "pipeline_error",
        # Phase 21: 코드 샌드박스
        "code_exec_start",
        "code_exec_output",
        "code_exec_done",
    ]
    agentId: Optional[str] = None
    label: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    token: Optional[str] = None
    totalTokens: Optional[int] = None
    tokensPerSec: Optional[float] = None
    latencyMs: Optional[int] = None
    vramGb: Optional[float] = None
    totalAgents: Optional[int] = None
    totalPipelineTokens: Optional[int] = None
    totalPipelineMs: Optional[int] = None
    prompt: Optional[str] = None
    message: Optional[str] = None
    # Tool calling fields
    tool: Optional[str] = None
    input: Optional[dict] = None
    output: Optional[str] = None
    # Stage info
    stageIndex: Optional[int] = None
    agentIds: Optional[List[str]] = None
    # Phase 21: 코드 샌드박스 필드
    language: Optional[str] = None
    code: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exitCode: Optional[int] = None
    durationMs: Optional[int] = None
    blocked: Optional[bool] = None
    timedOut: Optional[bool] = None

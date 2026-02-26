from pydantic import BaseModel
from typing import Literal, Optional, List


class ProviderConfig(BaseModel):
    type: Literal["ollama", "lmstudio", "llamacpp", "transformers", "simulation"] = "simulation"
    base_url: Optional[str] = None    # for openai-compat backends
    model_id: Optional[str] = None    # HF model ID for transformers
    load_in_4bit: bool = False
    load_in_8bit: bool = False


class AgentRunConfig(BaseModel):
    agent_id: str
    provider: ProviderConfig = ProviderConfig()
    system_prompt: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7


class RunRequest(BaseModel):
    prompt: str = "Build a user authentication REST API with JWT tokens"
    use_real_models: bool = False
    default_provider: ProviderConfig = ProviderConfig()
    agent_configs: Optional[List[AgentRunConfig]] = None


class PipelineEvent(BaseModel):
    type: Literal[
        "pipeline_start",
        "agent_start",
        "agent_token",
        "agent_vram",
        "agent_done",
        "pipeline_done",
        "pipeline_error",
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

import type { ProviderType } from "@/context/PipelineContext";

export type AgentType =
  | "router" | "coder" | "analyzer" | "synthesizer"
  | "validator" | "input" | "output" | "custom";

export type NodeConfig = {
  provider: ProviderType;
  modelId: string;
  systemPrompt: string;
  maxTokens: number;
  temperature: number;
  tools?: {
    web_search?: boolean;
  };
};

// ─── Per-agentType defaults ───────────────────────────────────────────────────

export const AGENT_TYPE_DEFAULTS: Record<AgentType, NodeConfig> = {
  router: {
    provider: "simulation",
    modelId: "Qwen2.5-3B-Instruct",
    systemPrompt:
      "You are a task routing system. Analyze the user request briefly. " +
      "Classify the task type, estimate complexity, and state which specialist " +
      "agents (Coder, Analyzer) should handle it and why. Be concise (3-5 lines).",
    maxTokens: 256,
    temperature: 0.3,
  },
  coder: {
    provider: "simulation",
    modelId: "Qwen2.5-Coder-7B",
    systemPrompt:
      "You are an expert programmer. Generate clean, working code for the task. " +
      "Include type hints and brief comments. Keep the implementation concise.",
    maxTokens: 1024,
    temperature: 0.1,
  },
  analyzer: {
    provider: "simulation",
    modelId: "Gemma-3-4B-IT",
    systemPrompt:
      "You are a technical analyst. Review the task and any code provided. " +
      "Identify security issues, performance concerns, and give brief recommendations.",
    maxTokens: 512,
    temperature: 0.5,
  },
  validator: {
    provider: "simulation",
    modelId: "Phi-4-mini-4B",
    systemPrompt:
      "You are a code quality expert. Score the provided code out of 100 for " +
      "quality and security. List top 3 issues. Give a final verdict: APPROVED or NEEDS_REVISION.",
    maxTokens: 512,
    temperature: 0.2,
  },
  synthesizer: {
    provider: "simulation",
    modelId: "Llama-3.1-8B-Instruct",
    systemPrompt:
      "You are a technical writer. Synthesize the outputs from all agents into " +
      "a clear final summary. Include: implementation overview, quality score, " +
      "top recommendations. Be concise.",
    maxTokens: 768,
    temperature: 0.4,
  },
  input:  { provider: "simulation", modelId: "user-query",    systemPrompt: "", maxTokens: 0,   temperature: 0 },
  output: { provider: "simulation", modelId: "result-stream", systemPrompt: "", maxTokens: 0,   temperature: 0 },
  custom: { provider: "simulation", modelId: "",              systemPrompt: "", maxTokens: 512, temperature: 0.7 },
};

// ─── Well-known node defaults (by static node ID) ─────────────────────────────

export const NODE_ID_TO_AGENT_TYPE: Record<string, AgentType> = {
  "input-1":       "input",
  "router-1":      "router",
  "coder-1":       "coder",
  "analyzer-1":    "analyzer",
  "validator-1":   "validator",
  "synthesizer-1": "synthesizer",
};

export function getDefaultConfig(nodeId: string, agentType?: AgentType): NodeConfig {
  const type = agentType ?? NODE_ID_TO_AGENT_TYPE[nodeId] ?? "custom";
  return { ...AGENT_TYPE_DEFAULTS[type] };
}

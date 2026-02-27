"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getDefaultConfig, type NodeConfig, type AgentType } from "@/constants/agentDefaults";

// ─── Types ────────────────────────────────────────────────────────────────────

export type AgentStatus = "idle" | "running" | "done" | "error";
export type PipelineStatus = "idle" | "running" | "done" | "stopped";
export type ProviderType = "simulation" | "ollama" | "lmstudio" | "llamacpp" | "transformers";

export type { NodeConfig };

export type AgentMetrics = {
  status: AgentStatus;
  tokens: number;
  tokensPerSec: number;
  latencyMs: number;
  vramGb: number;
  output: string;
  provider: ProviderType;
};

export type ParallelStageInfo = {
  stageIndex: number;
  agentIds: string[];
} | null;

export type ProviderStatus = {
  ollama: boolean;
  lmstudio: boolean;
  llamacpp: boolean;
  transformers: boolean;
};

export type SelectedNodeInfo = {
  id: string;
  label: string;
  agentType: AgentType;
} | null;

type PipelineState = {
  status: PipelineStatus;
  prompt: string;
  agentMetrics: Record<string, AgentMetrics>;
  totalTokens: number;
  totalMs: number;
  error: string | null;
  useRealModels: boolean;
  providerType: ProviderType;
  providerStatus: ProviderStatus;
  availableModels: Record<string, string[]>;
  selectedNode: SelectedNodeInfo;
  nodeConfigs: Record<string, NodeConfig>;
  activeParallelStage: ParallelStageInfo;
};

type PipelineContextValue = PipelineState & {
  setPrompt: (p: string) => void;
  setUseRealModels: (v: boolean) => void;
  setProviderType: (p: ProviderType) => void;
  setSelectedNode: (info: SelectedNodeInfo) => void;
  setNodeConfig: (nodeId: string, patch: Partial<NodeConfig>) => void;
  resetNodeConfig: (nodeId: string, agentType?: AgentType) => void;
  run: () => void;
  stop: () => void;
  reset: () => void;
};

// ─── Defaults ─────────────────────────────────────────────────────────────────

const DEFAULT_AGENT_IDS = [
  "router-1", "coder-1", "analyzer-1", "validator-1", "synthesizer-1",
];

function defaultMetrics(): Record<string, AgentMetrics> {
  return Object.fromEntries(
    DEFAULT_AGENT_IDS.map((id) => [
      id,
      { status: "idle", tokens: 0, tokensPerSec: 0, latencyMs: 0, vramGb: 0, output: "", provider: "simulation" as ProviderType },
    ])
  );
}

const DEFAULT_PROVIDER_STATUS: ProviderStatus = {
  ollama: false, lmstudio: false, llamacpp: false, transformers: false,
};

// ─── Context ──────────────────────────────────────────────────────────────────

const PipelineContext = createContext<PipelineContextValue | null>(null);
const BACKEND = "http://localhost:8000";

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PipelineState>({
    status: "idle",
    prompt: "Build a user authentication REST API with JWT tokens",
    agentMetrics: defaultMetrics(),
    totalTokens: 0,
    totalMs: 0,
    error: null,
    useRealModels: false,
    providerType: "simulation",
    providerStatus: DEFAULT_PROVIDER_STATUS,
    availableModels: {},
    selectedNode: null,
    nodeConfigs: {},
    activeParallelStage: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  // ── Poll provider health + available models every 10s ─────────────────────
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [provRes, modRes] = await Promise.all([
          fetch(`${BACKEND}/api/providers`, { signal: AbortSignal.timeout(4000) }),
          fetch(`${BACKEND}/api/models`, { signal: AbortSignal.timeout(4000) }),
        ]);
        const provData = provRes.ok ? await provRes.json() : null;
        const modData = modRes.ok ? await modRes.json() : null;

        setState((s) => ({
          ...s,
          ...(provData && {
            providerStatus: {
              ollama: provData.providers?.ollama ?? false,
              lmstudio: provData.providers?.lmstudio ?? false,
              llamacpp: provData.providers?.llamacpp ?? false,
              transformers: provData.providers?.transformers ?? false,
            },
          }),
          ...(modData && { availableModels: modData.models ?? {} }),
        }));
      } catch {
        // backend offline
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 10_000);
    return () => clearInterval(id);
  }, []);

  // ── Setters ───────────────────────────────────────────────────────────────
  const setPrompt = useCallback((p: string) => setState((s) => ({ ...s, prompt: p })), []);
  const setUseRealModels = useCallback((v: boolean) => setState((s) => ({ ...s, useRealModels: v })), []);
  const setProviderType = useCallback((p: ProviderType) => setState((s) => ({ ...s, providerType: p })), []);
  const setSelectedNode = useCallback((info: SelectedNodeInfo) => setState((s) => ({ ...s, selectedNode: info })), []);

  const setNodeConfig = useCallback((nodeId: string, patch: Partial<NodeConfig>) => {
    setState((s) => ({
      ...s,
      nodeConfigs: {
        ...s.nodeConfigs,
        [nodeId]: { ...getDefaultConfig(nodeId), ...s.nodeConfigs[nodeId], ...patch },
      },
    }));
  }, []);

  const resetNodeConfig = useCallback((nodeId: string, agentType?: AgentType) => {
    setState((s) => {
      const next = { ...s.nodeConfigs };
      delete next[nodeId];
      return { ...s, nodeConfigs: next };
    });
    // suppress unused warning
    void agentType;
  }, []);

  // ── Run pipeline ──────────────────────────────────────────────────────────
  const run = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setState((s) => ({
      ...s,
      status: "running",
      agentMetrics: defaultMetrics(),
      totalTokens: 0,
      totalMs: 0,
      error: null,
    }));

    // Build agent_configs from nodeConfigs
    const agentConfigs = Object.entries(state.nodeConfigs).map(([agentId, cfg]) => {
      const activeTools: string[] = [];
      if (cfg.tools?.web_search) activeTools.push("web_search");

      return {
        agent_id: agentId,
        provider: {
          type: cfg.provider,
          model_id: cfg.modelId || undefined,
        },
        system_prompt: cfg.systemPrompt || undefined,
        max_tokens: cfg.maxTokens,
        temperature: cfg.temperature,
        tools: activeTools.length > 0 ? activeTools : undefined,
      };
    });

    try {
      const response = await fetch(`${BACKEND}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: state.prompt,
          use_real_models: state.useRealModels,
          default_provider: { type: state.providerType },
          agent_configs: agentConfigs.length > 0 ? agentConfigs : undefined,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok) throw new Error(`Backend error: ${response.status}`);

      const reader = response.body!.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try { handleEvent(JSON.parse(raw)); } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : String(err);
      setState((s) => ({
        ...s, status: "stopped",
        error: `Connection failed: ${msg}. Is the backend running?`,
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.prompt, state.useRealModels, state.providerType, state.nodeConfigs]);

  const handleEvent = useCallback((event: Record<string, unknown>) => {
    switch (event.type as string) {
      case "agent_start":
        setState((s) => ({
          ...s,
          agentMetrics: {
            ...s.agentMetrics,
            [event.agentId as string]: {
              ...s.agentMetrics[event.agentId as string],
              status: "running",
              provider: (event.provider as ProviderType) ?? "simulation",
            },
          },
        }));
        break;

      case "agent_token":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id] ?? { status: "running", tokens: 0, tokensPerSec: 0, latencyMs: 0, vramGb: 0, output: "", provider: "simulation" as ProviderType };
          return {
            ...s,
            agentMetrics: {
              ...s.agentMetrics,
              [id]: {
                ...prev,
                tokens: (event.totalTokens as number) ?? prev.tokens,
                tokensPerSec: (event.tokensPerSec as number) ?? prev.tokensPerSec,
                output: prev.output + ((event.token as string) ?? ""),
              },
            },
          };
        });
        break;

      case "agent_vram":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id];
          if (!prev) return s;
          return { ...s, agentMetrics: { ...s.agentMetrics, [id]: { ...prev, vramGb: event.vramGb as number } } };
        });
        break;

      case "agent_done":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id];
          if (!prev) return s;
          return {
            ...s,
            agentMetrics: {
              ...s.agentMetrics,
              [id]: {
                ...prev,
                status: "done",
                tokens: (event.totalTokens as number) ?? prev.tokens,
                tokensPerSec: (event.tokensPerSec as number) ?? prev.tokensPerSec,
                latencyMs: (event.latencyMs as number) ?? prev.latencyMs,
                vramGb: (event.vramGb as number) ?? prev.vramGb,
                provider: (event.provider as ProviderType) ?? prev.provider,
              },
            },
          };
        });
        break;

      case "stage_parallel":
        setState((s) => ({
          ...s,
          activeParallelStage: {
            stageIndex: event.stageIndex as number,
            agentIds: event.agentIds as string[],
          },
        }));
        break;

      case "pipeline_done":
        setState((s) => ({
          ...s,
          status: "done",
          activeParallelStage: null,
          totalTokens: (event.totalPipelineTokens as number) ?? s.totalTokens,
          totalMs: (event.totalPipelineMs as number) ?? s.totalMs,
        }));
        break;

      case "pipeline_error":
        setState((s) => ({ ...s, status: "stopped", activeParallelStage: null, error: (event.message as string) ?? "Unknown error" }));
        break;
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    readerRef.current?.cancel();
    setState((s) => ({ ...s, status: "stopped" }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    readerRef.current?.cancel();
    setState((s) => ({
      ...s, status: "idle",
      agentMetrics: defaultMetrics(),
      totalTokens: 0, totalMs: 0, error: null,
    }));
  }, []);

  return (
    <PipelineContext.Provider
      value={{
        ...state,
        setPrompt, setUseRealModels, setProviderType,
        setSelectedNode, setNodeConfig, resetNodeConfig,
        run, stop, reset,
      }}
    >
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error("usePipeline must be used inside PipelineProvider");
  return ctx;
}

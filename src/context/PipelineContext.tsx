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
import type { AgentRecord } from "@/components/modals/AgentEditorModal";
import { BACKEND } from "@/lib/config";

// ─── Types ────────────────────────────────────────────────────────────────────

export type AgentStatus = "idle" | "running" | "done" | "error";
export type PipelineStatus = "idle" | "running" | "done" | "stopped";
export type ProviderType = "simulation" | "ollama" | "lmstudio" | "llamacpp" | "transformers";
export type OrchestrationMode = "dag" | "langgraph";

export type RetryInfo = {
  agentId: string;
  retryCount: number;
  maxRetries: number;
  reason: string;
};

export type { NodeConfig };

export type ToolCallEvent = {
  tool: string;
  input: Record<string, unknown>;
  output: string;
  agentId: string;
};

export type CodeExecResult = {
  language: string;
  stdout: string;
  stderr: string;
  exitCode: number;
  durationMs: number;
  blocked: boolean;
  timedOut: boolean;
};

export type AgentMetrics = {
  status: AgentStatus;
  tokens: number;
  tokensPerSec: number;
  latencyMs: number;
  vramGb: number;
  output: string;
  provider: ProviderType;
  toolCalls: ToolCallEvent[];
  codeExecs: CodeExecResult[];  // Phase 21
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

// Phase 19: 모델 메타데이터 타입
export type ModelMeta = {
  model_id: string;
  provider: string;
  size_bytes: number;
  family: string;
  parameter_size: string;
  quantization: string;
  format: string;
  discovered_at: number; // Date.now() — NEW 배지 만료 계산용
};

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
  registryAgents: AgentRecord[];
  orchestrationMode: OrchestrationMode;
  retryInfo: RetryInfo | null;
  // Phase 13: 대화 세션
  sessionId: string | null;
  imagePaths: string[];
  // Phase 19: 동적 모델 디스커버리
  modelMetadata: Record<string, ModelMeta[]>; // provider → 메타 배열
  newModelKeys: Set<string>;                  // "provider:model_id" 형식
};

type PipelineContextValue = PipelineState & {
  setPrompt: (p: string) => void;
  setUseRealModels: (v: boolean) => void;
  setProviderType: (p: ProviderType) => void;
  setOrchestrationMode: (m: OrchestrationMode) => void;
  setSelectedNode: (info: SelectedNodeInfo) => void;
  setNodeConfig: (nodeId: string, patch: Partial<NodeConfig>) => void;
  resetNodeConfig: (nodeId: string, agentType?: AgentType) => void;
  setSessionId: (id: string | null) => void;
  setImagePaths: (paths: string[] | ((prev: string[]) => string[])) => void;
  refreshModels: () => Promise<void>;
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
      { status: "idle", tokens: 0, tokensPerSec: 0, latencyMs: 0, vramGb: 0, output: "", provider: "simulation" as ProviderType, toolCalls: [], codeExecs: [] },
    ])
  );
}

const DEFAULT_PROVIDER_STATUS: ProviderStatus = {
  ollama: false, lmstudio: false, llamacpp: false, transformers: false,
};

// ─── Context ──────────────────────────────────────────────────────────────────

const PipelineContext = createContext<PipelineContextValue | null>(null);

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
    registryAgents: [] as AgentRecord[],
    orchestrationMode: "dag",
    retryInfo: null,
    sessionId: null,
    imagePaths: [],
    modelMetadata: {},
    newModelKeys: new Set<string>(),
  });

  const abortRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  // ── Poll provider health + available models every 10s ─────────────────────
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [provRes, modRes, regRes] = await Promise.all([
          fetch(`${BACKEND}/api/providers`, { signal: AbortSignal.timeout(4000) }),
          fetch(`${BACKEND}/api/models`, { signal: AbortSignal.timeout(4000) }),
          fetch(`${BACKEND}/api/registry/agents`, { signal: AbortSignal.timeout(4000) }),
        ]);
        const provData = provRes.ok ? await provRes.json() : null;
        const modData = modRes.ok ? await modRes.json() : null;
        const regData = regRes.ok ? await regRes.json() : null;

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
          ...(regData && { registryAgents: regData.agents ?? [] }),
        }));
      } catch {
        // backend offline
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 10_000);
    return () => clearInterval(id);
  }, []);

  // ── Phase 19: ModelWatcher SSE 구독 ───────────────────────────────────────
  useEffect(() => {
    let abortController = new AbortController();
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 2000;
    const badgeTimers = new Set<ReturnType<typeof setTimeout>>();

    const handleModelEvent = (event: Record<string, unknown>) => {
      const type = event.type as string;

      if (type === "model_snapshot") {
        const provider = event.provider as string;
        const models = (event.models as Array<Record<string, unknown>>).map((m) => ({
          ...(m as Omit<ModelMeta, "discovered_at">),
          discovered_at: Date.now(),
        })) as ModelMeta[];

        setState((s) => ({
          ...s,
          modelMetadata: { ...s.modelMetadata, [provider]: models },
          availableModels: {
            ...s.availableModels,
            [provider]: models.map((m) => m.model_id),
          },
        }));
      }

      if (type === "model_added") {
        const provider = event.provider as string;
        const modelId = event.model_id as string;
        const meta = event.meta as Omit<ModelMeta, "discovered_at">;
        const key = `${provider}:${modelId}`;

        setState((s) => {
          const prevMetas = s.modelMetadata[provider] ?? [];
          const prevIds = s.availableModels[provider] ?? [];
          if (prevIds.includes(modelId)) return s; // 중복 방지

          const newMeta: ModelMeta = { ...meta, discovered_at: Date.now() };
          const newKeys = new Set(s.newModelKeys);
          newKeys.add(key);

          return {
            ...s,
            modelMetadata: { ...s.modelMetadata, [provider]: [...prevMetas, newMeta] },
            availableModels: { ...s.availableModels, [provider]: [...prevIds, modelId] },
            newModelKeys: newKeys,
          };
        });

        // 30초 후 NEW 배지 소멸 (cleanup 위해 timer ID 추적)
        const timerId = setTimeout(() => {
          badgeTimers.delete(timerId);
          setState((s) => {
            const next = new Set(s.newModelKeys);
            next.delete(key);
            return { ...s, newModelKeys: next };
          });
        }, 30_000);
        badgeTimers.add(timerId);
      }

      if (type === "model_removed") {
        const provider = event.provider as string;
        const modelId = event.model_id as string;

        setState((s) => ({
          ...s,
          modelMetadata: {
            ...s.modelMetadata,
            [provider]: (s.modelMetadata[provider] ?? []).filter((m) => m.model_id !== modelId),
          },
          availableModels: {
            ...s.availableModels,
            [provider]: (s.availableModels[provider] ?? []).filter((id) => id !== modelId),
          },
        }));
      }
      // "ping" 이벤트는 무시
    };

    const connect = async () => {
      try {
        const response = await fetch(`${BACKEND}/api/models/watch`, {
          signal: abortController.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        retryDelay = 2000; // 연결 성공 시 딜레이 리셋

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
            try { handleModelEvent(JSON.parse(raw)); } catch { /* skip */ }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        // 백엔드 오프라인 — 지수 백오프 재연결 (최대 30초)
        retryDelay = Math.min(retryDelay * 1.5, 30_000);
      }

      // 재연결 스케줄
      if (!abortController.signal.aborted) {
        retryTimeout = setTimeout(connect, retryDelay);
      }
    };

    connect();

    return () => {
      abortController.abort();
      if (retryTimeout) clearTimeout(retryTimeout);
      badgeTimers.forEach(clearTimeout);
      badgeTimers.clear();
    };
  }, []); // 마운트 시 1회만

  // ── Setters ───────────────────────────────────────────────────────────────
  const setPrompt = useCallback((p: string) => setState((s) => ({ ...s, prompt: p })), []);
  const setUseRealModels = useCallback((v: boolean) => setState((s) => ({ ...s, useRealModels: v })), []);
  const setProviderType = useCallback((p: ProviderType) => setState((s) => ({ ...s, providerType: p })), []);
  const setOrchestrationMode = useCallback((m: OrchestrationMode) => setState((s) => ({ ...s, orchestrationMode: m })), []);
  const setSelectedNode = useCallback((info: SelectedNodeInfo) => setState((s) => ({ ...s, selectedNode: info })), []);
  const setSessionId = useCallback((id: string | null) => setState((s) => ({ ...s, sessionId: id })), []);
  const setImagePaths = useCallback((paths: string[] | ((prev: string[]) => string[])) => {
    setState((s) => ({
      ...s,
      imagePaths: typeof paths === "function" ? paths(s.imagePaths) : paths,
    }));
  }, []);

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
    void agentType;
  }, []);

  // Phase 19: 수동 새로고침
  const refreshModels = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/models/refresh`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        const models = data.models as Record<string, Array<Record<string, unknown>>>;
        setState((s) => {
          const newMeta: Record<string, ModelMeta[]> = { ...s.modelMetadata };
          const newAvail: Record<string, string[]> = { ...s.availableModels };
          for (const [provider, metas] of Object.entries(models)) {
            newMeta[provider] = (metas as Array<Record<string, unknown>>).map((m) => ({
              ...(m as Omit<ModelMeta, "discovered_at">),
              discovered_at: Date.now(),
            }));
            newAvail[provider] = newMeta[provider].map((m) => m.model_id);
          }
          return { ...s, modelMetadata: newMeta, availableModels: newAvail };
        });
      }
    } catch { /* backend offline */ }
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

    const agentConfigs = Object.entries(state.nodeConfigs).map(([agentId, cfg]) => {
      const activeTools: string[] = [];
      if (cfg.tools?.web_search) activeTools.push("web_search");
      return {
        agent_id: agentId,
        provider: { type: cfg.provider, model_id: cfg.modelId || undefined },
        system_prompt: cfg.systemPrompt || undefined,
        max_tokens: cfg.maxTokens,
        temperature: cfg.temperature,
        tools: activeTools.length > 0 ? activeTools : undefined,
        rag_collections: cfg.ragCollections && cfg.ragCollections.length > 0 ? cfg.ragCollections : undefined,
        auto_execute: cfg.autoExecute ?? false,
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
          orchestration_mode: state.orchestrationMode,
          structured_routing: true,
          session_id: state.sessionId,
          image_paths: state.imagePaths.length > 0 ? state.imagePaths : undefined,
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
  }, [state.prompt, state.useRealModels, state.providerType, state.nodeConfigs, state.orchestrationMode, state.sessionId, state.imagePaths]);

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
              toolCalls: [],
              codeExecs: [],
            },
          },
        }));
        break;

      case "tool_call":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id] ?? { status: "running", tokens: 0, tokensPerSec: 0, latencyMs: 0, vramGb: 0, output: "", provider: "simulation" as ProviderType, toolCalls: [] };
          return {
            ...s,
            agentMetrics: {
              ...s.agentMetrics,
              [id]: {
                ...prev,
                toolCalls: [
                  ...prev.toolCalls,
                  { tool: event.tool as string, input: (event.input as Record<string, unknown>) ?? {}, output: "", agentId: id },
                ],
              },
            },
          };
        });
        break;

      case "tool_result":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id];
          if (!prev) return s;
          const toolName = event.tool as string;
          const updatedCalls = prev.toolCalls.map((tc) =>
            tc.tool === toolName && tc.output === "" ? { ...tc, output: (event.output as string) ?? "" } : tc
          );
          return { ...s, agentMetrics: { ...s.agentMetrics, [id]: { ...prev, toolCalls: updatedCalls } } };
        });
        break;

      case "code_exec_done":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id];
          if (!prev) return s;
          const execResult: CodeExecResult = {
            language: (event.language as string) ?? "python",
            stdout: (event.stdout as string) ?? "",
            stderr: (event.stderr as string) ?? "",
            exitCode: (event.exitCode as number) ?? 0,
            durationMs: (event.durationMs as number) ?? 0,
            blocked: (event.blocked as boolean) ?? false,
            timedOut: (event.timedOut as boolean) ?? false,
          };
          return { ...s, agentMetrics: { ...s.agentMetrics, [id]: { ...prev, codeExecs: [...(prev.codeExecs ?? []), execResult] } } };
        });
        break;

      case "agent_token":
        setState((s) => {
          const id = event.agentId as string;
          const prev = s.agentMetrics[id] ?? { status: "running", tokens: 0, tokensPerSec: 0, latencyMs: 0, vramGb: 0, output: "", provider: "simulation" as ProviderType, toolCalls: [], codeExecs: [] };
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

      case "langgraph_retry":
        setState((s) => ({
          ...s,
          retryInfo: {
            agentId: event.agentId as string,
            retryCount: event.retryCount as number,
            maxRetries: event.maxRetries as number,
            reason: event.reason as string,
          },
        }));
        break;

      case "pipeline_done":
        setState((s) => ({
          ...s,
          status: "done",
          activeParallelStage: null,
          retryInfo: null,
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
      ...s,
      status: "idle",
      agentMetrics: defaultMetrics(),
      totalTokens: 0,
      totalMs: 0,
      error: null,
      retryInfo: null,
      imagePaths: [],
    }));
  }, []);

  return (
    <PipelineContext.Provider
      value={{
        ...state,
        setPrompt, setUseRealModels, setProviderType, setOrchestrationMode,
        setSelectedNode, setNodeConfig, resetNodeConfig, setSessionId,
        setImagePaths,
        refreshModels,
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

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import NodeConfigPanel from "@/components/canvas/NodeConfigPanel";
import AgentEditorModal, { type AgentRecord } from "@/components/modals/AgentEditorModal";
import {
  Activity,
  Cpu,
  Eye,
  MemoryStick,
  Zap,
  Clock,
  TrendingUp,
  MessageSquare,
  GitBranch,
  Code2,
  FlaskConical,
  Layers,
  ShieldCheck,
  BarChart2,
  CheckCircle2,
  Loader2,
  Circle,
  Wifi,
  WifiOff,
  Download,
  HardDrive,
  X,
  RefreshCw,
  Package,
  AlertTriangle,
  Pencil,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePipeline, type AgentMetrics, type ProviderType } from "@/context/PipelineContext";
import { BACKEND } from "@/lib/config";
import React from "react";

// ─── Config ───────────────────────────────────────────────────────────────────


type RoleMeta = { icon: React.ComponentType<{ size?: number; color?: string }>; color: string; vramMax: number };

const ROLE_META: Record<string, RoleMeta> = {
  router:      { icon: GitBranch,    color: "#22d3ee", vramMax: 8 },
  coder:       { icon: Code2,        color: "#a855f7", vramMax: 8 },
  analyzer:    { icon: FlaskConical, color: "#f472b6", vramMax: 8 },
  validator:   { icon: ShieldCheck,  color: "#f59e0b", vramMax: 8 },
  synthesizer: { icon: Layers,       color: "#10b981", vramMax: 4 },
  vision:      { icon: Eye,          color: "#3b82f6", vramMax: 2 },
  assistant:   { icon: MessageSquare,color: "#64748b", vramMax: 2 },
};
const DEFAULT_ROLE_META: RoleMeta = { icon: Activity, color: "#64748b", vramMax: 4 };

const PROVIDER_COLORS: Record<ProviderType, string> = {
  simulation:   "#64748b",
  ollama:       "#22d3ee",
  lmstudio:     "#a855f7",
  llamacpp:     "#f59e0b",
  transformers: "#10b981",
};

const PROVIDER_LABELS: Record<ProviderType, string> = {
  simulation:   "SIM",
  ollama:       "OLLAMA",
  lmstudio:     "LMS",
  llamacpp:     "GGUF",
  transformers: "HF",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function VramBar({ used, max, color }: { used: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((used / max) * 100, 100) : 0;
  return (
    <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
      <motion.div
        className="h-full rounded-full"
        style={{ background: `linear-gradient(90deg, ${color}60, ${color})` }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      />
    </div>
  );
}

function StatusIcon({ status }: { status: AgentMetrics["status"] }) {
  if (status === "running") return <Loader2 size={10} className="animate-spin text-cyber-cyan" />;
  if (status === "done")    return <CheckCircle2 size={10} className="text-cyber-green" />;
  return <Circle size={10} className="text-cyber-subtle" />;
}

// ─── DB 기반 에이전트 행 ──────────────────────────────────────────────────────

function AgentRowDB({
  agent,
  meta,
  metrics,
  onEdit,
}: {
  agent: AgentRecord;
  meta: RoleMeta;
  metrics: AgentMetrics;
  onEdit: () => void;
}) {
  const Icon = meta.icon;
  const isRunning = metrics.status === "running";
  const providerColor = PROVIDER_COLORS[metrics.provider as ProviderType] ?? "#64748b";
  const providerLabel = PROVIDER_LABELS[metrics.provider as ProviderType] ?? "SIM";

  return (
    <motion.div
      layout
      className="group rounded-lg p-2.5"
      style={{
        background: `${meta.color}06`,
        border: `1px solid ${meta.color}${isRunning ? "35" : "15"}`,
        transition: "border-color 0.3s",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ background: `${meta.color}15` }}
        >
          <Icon size={12} color={meta.color} />
        </div>
        <span className="text-xs font-medium text-cyber-text flex-1 truncate">{agent.name}</span>
        <div className="flex items-center gap-1.5">
          {metrics.provider !== "simulation" && (
            <span
              className="text-[8px] font-bold px-1 rounded"
              style={{ color: providerColor, background: `${providerColor}20` }}
            >
              {providerLabel}
            </span>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(); }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded transition-all hover:bg-white/10"
            title="편집"
          >
            <Pencil size={9} color="#64748b" />
          </button>
          <StatusIcon status={metrics.status} />
          <span
            className="text-[10px] font-mono"
            style={{
              color:
                metrics.status === "running" ? meta.color :
                metrics.status === "done"    ? "#10b981" :
                "#64748b",
            }}
          >
            {metrics.status}
          </span>
        </div>
      </div>

      {/* Model ID */}
      <p className="text-[9px] text-cyber-subtle font-mono truncate mb-2" title={agent.model_id}>
        {agent.model_id}
      </p>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-1.5 mb-2">
        <div>
          <p className="text-[9px] text-cyber-subtle uppercase tracking-wider mb-0.5">T/s</p>
          <p className="text-[11px] font-mono font-semibold" style={{ color: isRunning ? meta.color : "#64748b" }}>
            {metrics.tokensPerSec > 0 ? metrics.tokensPerSec.toFixed(1) : "—"}
          </p>
        </div>
        <div>
          <p className="text-[9px] text-cyber-subtle uppercase tracking-wider mb-0.5">Latency</p>
          <p className="text-[11px] font-mono font-semibold text-cyber-muted">
            {metrics.latencyMs > 0 ? `${(metrics.latencyMs / 1000).toFixed(1)}s` : "—"}
          </p>
        </div>
        <div>
          <p className="text-[9px] text-cyber-subtle uppercase tracking-wider mb-0.5">Tokens</p>
          <p className="text-[11px] font-mono font-semibold text-cyber-text">
            {metrics.tokens > 0 ? metrics.tokens.toLocaleString() : "—"}
          </p>
        </div>
      </div>

      {/* VRAM */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-cyber-subtle uppercase tracking-wider">VRAM</span>
          <span className="text-[9px] font-mono" style={{ color: meta.color }}>
            {metrics.vramGb.toFixed(1)} / {meta.vramMax} GB
          </span>
        </div>
        <VramBar used={metrics.vramGb} max={meta.vramMax} color={meta.color} />
      </div>

      {/* Running progress bar */}
      {isRunning && (
        <motion.div className="mt-2 h-0.5 rounded-full overflow-hidden bg-white/[0.04]">
          <motion.div
            className="h-full rounded-full"
            style={{ background: `linear-gradient(90deg, transparent, ${meta.color})` }}
            animate={{ x: ["-100%", "100%"] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          />
        </motion.div>
      )}
    </motion.div>
  );
}

// ─── Tool call badge ──────────────────────────────────────────────────────────

const TOOL_COLORS: Record<string, string> = {
  web_search:  "#22d3ee",
  calculator:  "#f59e0b",
  read_file:   "#a855f7",
};

function ToolCallBadge({ tool, input, output }: { tool: string; input: Record<string, unknown>; output: string }) {
  const color = TOOL_COLORS[tool] ?? "#64748b";
  const inputStr = Object.values(input)[0]?.toString() ?? "";
  return (
    <div
      className="my-2 rounded-md p-2 text-[9px] font-mono"
      style={{ background: `${color}10`, border: `1px solid ${color}30` }}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className="font-bold uppercase" style={{ color }}>{tool.replace("_", " ")}</span>
        <span className="text-cyber-subtle truncate max-w-[140px]">{inputStr}</span>
      </div>
      {output && (
        <p className="text-cyber-muted leading-relaxed line-clamp-3">{output}</p>
      )}
    </div>
  );
}

// ─── Output viewer ────────────────────────────────────────────────────────────

function OutputPanel() {
  const { agentMetrics, registryAgents } = usePipeline();
  const [activeAgent, setActiveAgent] = useState("router-1");
  const currentMetrics = agentMetrics[activeAgent];
  const currentOutput = currentMetrics?.output ?? "";
  const toolCalls = currentMetrics?.toolCalls ?? [];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-1 flex-wrap">
        {registryAgents.map((agent) => {
          const color = ROLE_META[agent.role]?.color ?? DEFAULT_ROLE_META.color;
          const m = agentMetrics[agent.id];
          const hasOutput = m && m.output.length > 0;
          const hasTools = m && m.toolCalls && m.toolCalls.length > 0;
          const label = agent.role.charAt(0).toUpperCase() + agent.role.slice(1);
          return (
            <button
              key={agent.id}
              onClick={() => setActiveAgent(agent.id)}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-medium transition-all",
                activeAgent === agent.id ? "text-white" : "text-cyber-muted hover:text-cyber-text"
              )}
              style={
                activeAgent === agent.id
                  ? { background: `${color}20`, border: `1px solid ${color}40`, color }
                  : { background: "transparent", border: "1px solid transparent" }
              }
            >
              {label}
              {hasOutput && (
                <span
                  className="ml-1 w-1 h-1 rounded-full inline-block align-middle"
                  style={{ background: color }}
                />
              )}
              {hasTools && (
                <span className="ml-0.5 text-[8px]" style={{ color: "#22d3ee" }}>⚡</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tool calls for this agent */}
      {toolCalls.length > 0 && (
        <div>
          <p className="text-[9px] text-cyber-muted uppercase tracking-widest mb-1">Tool Calls</p>
          {toolCalls.map((tc, i) => (
            <ToolCallBadge key={i} tool={tc.tool} input={tc.input} output={tc.output} />
          ))}
        </div>
      )}

      <div
        className="rounded-lg p-2.5 min-h-[120px] max-h-[220px] overflow-y-auto"
        style={{
          background: "rgba(0, 0, 0, 0.3)",
          border: "1px solid rgba(255,255,255,0.06)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {currentOutput ? (
          <p className="text-[10px] text-cyber-text whitespace-pre-wrap leading-relaxed">
            {currentOutput}
          </p>
        ) : (
          <p className="text-[10px] text-cyber-subtle italic">
            No output yet — start a pipeline run
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Model download panel ─────────────────────────────────────────────────────

type DownloadState =
  | { stage: "idle" }
  | { stage: "listing"; modelId: string }
  | { stage: "downloading"; modelId: string; currentFile: string; fileIndex: number; totalFiles: number; pct: number }
  | { stage: "complete"; modelId: string; downloaded: number; errors: number }
  | { stage: "error"; message: string };

type LocalModel = { model_id: string; size_str: string; nb_files: number };

type VramInfo = { allocated_gb: number; total_gb: number; free_gb: number; reserved_gb: number };

function ModelDownloadPanel() {
  const [input, setInput] = useState("");
  const [dlState, setDlState] = useState<DownloadState>({ stage: "idle" });
  const [localModels, setLocalModels] = useState<LocalModel[]>([]);
  const [loadingLocal, setLoadingLocal] = useState(false);
  const [vramInfo, setVramInfo] = useState<VramInfo | null>(null);
  const [cachedModels, setCachedModels] = useState<string[]>([]);
  const [unloadingModel, setUnloadingModel] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchLocalModels = useCallback(async () => {
    setLoadingLocal(true);
    try {
      const res = await fetch(`${BACKEND}/api/models/local`);
      if (res.ok) {
        const data = await res.json();
        setLocalModels(data.models ?? []);
      }
    } catch { /* backend offline */ }
    finally { setLoadingLocal(false); }
  }, []);

  useEffect(() => { fetchLocalModels(); }, [fetchLocalModels]);

  // VRAM 상태 5초 폴링
  useEffect(() => {
    const fetchVram = async () => {
      try {
        const res = await fetch(`${BACKEND}/api/vram`);
        if (res.ok) {
          const data = await res.json();
          setVramInfo(data.vram ?? null);
          setCachedModels(data.cached_models ?? []);
        }
      } catch { /* backend offline */ }
    };
    fetchVram();
    const id = setInterval(fetchVram, 5000);
    return () => clearInterval(id);
  }, []);

  const handleUnload = useCallback(async (modelId: string) => {
    setUnloadingModel(modelId);
    try {
      await fetch(`${BACKEND}/api/models/unload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
    } finally {
      setUnloadingModel(null);
    }
  }, []);

  const handleUnloadAll = useCallback(async () => {
    setUnloadingModel("__all__");
    try {
      await fetch(`${BACKEND}/api/models/unload_all`, { method: "POST" });
    } finally {
      setUnloadingModel(null);
    }
  }, []);

  const handleDownload = useCallback(async () => {
    const modelId = input.trim();
    if (!modelId || dlState.stage === "downloading" || dlState.stage === "listing") return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setDlState({ stage: "listing", modelId });

    try {
      const res = await fetch(`${BACKEND}/api/models/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "download_start") {
              setDlState({ stage: "downloading", modelId, currentFile: "…", fileIndex: 0, totalFiles: ev.totalFiles, pct: 0 });
            } else if (ev.type === "download_file") {
              setDlState({ stage: "downloading", modelId, currentFile: ev.filename, fileIndex: ev.fileIndex, totalFiles: ev.totalFiles, pct: ev.pct });
            } else if (ev.type === "download_complete") {
              setDlState({ stage: "complete", modelId, downloaded: ev.downloaded, errors: ev.errors });
              fetchLocalModels();
            } else if (ev.type === "download_error") {
              setDlState({ stage: "error", message: ev.message });
            }
          } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        setDlState({ stage: "idle" });
      } else {
        setDlState({ stage: "error", message: err instanceof Error ? err.message : String(err) });
      }
    }
  }, [input, dlState.stage, fetchLocalModels]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    setDlState({ stage: "idle" });
  }, []);

  const isActive = dlState.stage === "listing" || dlState.stage === "downloading";
  const pct = dlState.stage === "downloading" ? dlState.pct : 0;

  return (
    <div className="flex flex-col gap-3">
      {/* Download input */}
      <div
        className="rounded-lg p-2.5"
        style={{ background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.12)" }}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <Download size={10} className="text-cyber-green" />
          <span className="text-[10px] text-cyber-muted font-medium">Download HF Model</span>
        </div>

        <div className="flex gap-1.5 mb-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleDownload(); }}
            placeholder="Qwen/Qwen2.5-3B-Instruct"
            disabled={isActive}
            className="flex-1 bg-black/30 rounded px-2 py-1.5 text-[10px] font-mono text-cyber-text placeholder-cyber-subtle outline-none border border-white/[0.08] focus:border-cyber-green/30 disabled:opacity-50 transition-colors"
          />
          {isActive ? (
            <button
              onClick={handleCancel}
              className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-cyber-orange hover:text-white transition-colors"
              style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <X size={10} />
            </button>
          ) : (
            <button
              onClick={handleDownload}
              disabled={!input.trim()}
              className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-cyber-green hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}
            >
              <Download size={10} />
            </button>
          )}
        </div>

        {/* Progress */}
        <AnimatePresence mode="wait">
          {dlState.stage === "listing" && (
            <motion.div key="listing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-1.5">
              <Loader2 size={9} className="animate-spin text-cyber-green" />
              <span className="text-[9px] text-cyber-muted font-mono">Listing files…</span>
            </motion.div>
          )}

          {dlState.stage === "downloading" && (
            <motion.div key="downloading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-cyber-muted font-mono truncate max-w-[140px]" title={dlState.currentFile}>
                  {dlState.currentFile.split("/").pop()}
                </span>
                <span className="text-[9px] font-mono text-cyber-green flex-shrink-0">
                  {dlState.fileIndex}/{dlState.totalFiles} · {dlState.pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: "linear-gradient(90deg, #10b981, #22d3ee)" }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </motion.div>
          )}

          {dlState.stage === "complete" && (
            <motion.div key="complete" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-1.5">
              <CheckCircle2 size={9} className="text-cyber-green" />
              <span className="text-[9px] text-cyber-green font-mono">
                {dlState.downloaded} files cached · {dlState.errors > 0 ? `${dlState.errors} errors` : "no errors"}
              </span>
            </motion.div>
          )}

          {dlState.stage === "error" && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-start gap-1.5">
              <X size={9} className="text-cyber-red flex-shrink-0 mt-0.5" />
              <span className="text-[9px] text-cyber-red font-mono leading-tight">{dlState.message}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* GPU VRAM 게이지 */}
      {vramInfo && vramInfo.total_gb > 0 && (
        <div
          className="rounded-lg p-2.5"
          style={{ background: "rgba(168,85,247,0.04)", border: "1px solid rgba(168,85,247,0.12)" }}
        >
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <MemoryStick size={10} className="text-cyber-purple" />
              <span className="text-[10px] text-cyber-muted">GPU VRAM</span>
            </div>
            <span className="text-[9px] font-mono text-cyber-purple">
              {vramInfo.allocated_gb.toFixed(2)} / {vramInfo.total_gb.toFixed(1)} GB
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{ background: "linear-gradient(90deg, #a855f7, #22d3ee)" }}
              animate={{ width: `${Math.min((vramInfo.allocated_gb / vramInfo.total_gb) * 100, 100).toFixed(1)}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
          <p className="text-[9px] text-cyber-subtle mt-1">
            Free: {vramInfo.free_gb.toFixed(2)} GB · Reserved: {vramInfo.reserved_gb.toFixed(2)} GB
          </p>
        </div>
      )}

      {/* Local models — 디스크 */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <HardDrive size={10} className="text-cyber-muted" />
            <span className="text-[10px] text-cyber-muted">Cached Models</span>
          </div>
          <button
            onClick={fetchLocalModels}
            disabled={loadingLocal}
            className="text-cyber-subtle hover:text-cyber-muted transition-colors disabled:opacity-40"
          >
            <RefreshCw size={9} className={loadingLocal ? "animate-spin" : ""} />
          </button>
        </div>

        {localModels.length === 0 ? (
          <div
            className="rounded-lg px-3 py-4 flex flex-col items-center gap-1.5"
            style={{ background: "rgba(11,16,37,0.4)", border: "1px solid rgba(255,255,255,0.04)" }}
          >
            <Package size={16} className="text-cyber-subtle" />
            <p className="text-[9px] text-cyber-subtle text-center">No cached models yet</p>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {localModels.map((m) => {
              const inVram = cachedModels.includes(m.model_id);
              return (
                <div
                  key={m.model_id}
                  className="rounded px-2.5 py-1.5 flex items-center gap-2"
                  style={{ background: "rgba(11,16,37,0.4)", border: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <div
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: inVram ? "#a855f7" : "#10b981" }}
                    title={inVram ? "Loaded in VRAM" : "On disk"}
                  />
                  <span className="text-[10px] text-cyber-text flex-1 truncate font-mono">{m.model_id}</span>
                  <span className="text-[9px] text-cyber-muted flex-shrink-0">{m.size_str}</span>
                  {inVram && (
                    <button
                      onClick={() => handleUnload(m.model_id)}
                      disabled={unloadingModel === m.model_id}
                      className="text-cyber-subtle hover:text-cyber-red transition-colors disabled:opacity-40 flex-shrink-0"
                      title="Unload from GPU"
                    >
                      {unloadingModel === m.model_id
                        ? <Loader2 size={9} className="animate-spin" />
                        : <X size={9} />
                      }
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Unload All 버튼 (VRAM에 모델이 있을 때만) */}
      {cachedModels.length > 0 && (
        <button
          onClick={handleUnloadAll}
          disabled={unloadingModel === "__all__"}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] text-cyber-red/70 hover:text-cyber-red disabled:opacity-40 transition-colors"
          style={{ border: "1px solid rgba(239,68,68,0.15)" }}
        >
          {unloadingModel === "__all__"
            ? <Loader2 size={9} className="animate-spin" />
            : <X size={9} />
          }
          <span>Unload All ({cachedModels.length} model{cachedModels.length > 1 ? "s" : ""})</span>
        </button>
      )}
    </div>
  );
}

// ─── Metrics Dashboard panel ──────────────────────────────────────────────────

// ─── Remote Models Section (Phase 19) ─────────────────────────────────────────

function RemoteModelsSection() {
  const { modelMetadata, newModelKeys, refreshModels } = usePipeline();
  const [refreshing, setRefreshing] = useState(false);

  const providers = Object.entries(modelMetadata).filter(([, metas]) => metas.length > 0);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshModels();
    setTimeout(() => setRefreshing(false), 800);
  };

  if (providers.length === 0) return null;

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-cyber-muted">
          Live Models
        </span>
        <button
          onClick={handleRefresh}
          className="p-1 rounded hover:bg-white/10 transition-colors"
          title="Refresh model list"
        >
          <RefreshCw size={9} color="#64748b" className={refreshing ? "animate-spin" : ""} />
        </button>
      </div>

      {providers.map(([provider, metas]) => (
        <div key={provider} className="mb-2">
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded"
              style={{
                color: provider === "ollama" ? "#22d3ee" : "#a855f7",
                background: provider === "ollama" ? "rgba(34,211,238,0.1)" : "rgba(168,85,247,0.1)",
              }}
            >
              {provider}
            </span>
            <span className="text-[9px] text-cyber-subtle">
              {metas.length} model{metas.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="space-y-0.5">
            {metas.map((meta) => {
              const key = `${provider}:${meta.model_id}`;
              const isNew = newModelKeys.has(key);
              return (
                <motion.div
                  key={meta.model_id}
                  initial={isNew ? { opacity: 0, x: -6 } : false}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                  className="flex items-center gap-1.5 px-2 py-1.5 rounded"
                  style={{
                    background: isNew ? "rgba(34,211,238,0.06)" : "rgba(11,16,37,0.5)",
                    border: `1px solid ${isNew ? "rgba(34,211,238,0.25)" : "rgba(255,255,255,0.04)"}`,
                  }}
                >
                  <AnimatePresence>
                    {isNew && (
                      <motion.span
                        initial={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.75 }}
                        className="text-[7px] font-bold px-1 py-0.5 rounded flex-shrink-0"
                        style={{ color: "#22d3ee", background: "rgba(34,211,238,0.15)" }}
                      >
                        NEW
                      </motion.span>
                    )}
                  </AnimatePresence>

                  <span className="text-[10px] text-cyber-text font-mono flex-1 truncate min-w-0">
                    {meta.model_id}
                  </span>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    {meta.parameter_size && (
                      <span className="text-[8px] text-cyber-subtle">{meta.parameter_size}</span>
                    )}
                    {meta.quantization && (
                      <span
                        className="text-[7px] font-mono px-1 rounded"
                        style={{ color: "#f59e0b", background: "rgba(245,158,11,0.1)" }}
                      >
                        {meta.quantization}
                      </span>
                    )}
                    {meta.size_bytes > 0 && (
                      <span className="text-[8px] text-cyber-subtle">
                        {(meta.size_bytes / 1e9).toFixed(1)}GB
                      </span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricsPanel() {
  const { agentMetrics, status, totalMs, registryAgents } = usePipeline();

  // Build sorted data for agents that have run
  const agentData = registryAgents.map((agent) => {
    const meta = ROLE_META[agent.role] ?? DEFAULT_ROLE_META;
    const m = agentMetrics[agent.id];
    return {
      id: agent.id,
      label: agent.role.charAt(0).toUpperCase() + agent.role.slice(1),
      color: meta.color,
      latencyMs:    m?.latencyMs    ?? 0,
      tokensPerSec: m?.tokensPerSec ?? 0,
      tokens:       m?.tokens       ?? 0,
      status:       m?.status       ?? "idle",
    };
  }).filter((a) => a.latencyMs > 0 || a.tokensPerSec > 0 || a.tokens > 0);

  const hasData = agentData.length > 0;
  const maxLatency    = Math.max(...agentData.map((a) => a.latencyMs),    1);
  const maxTokensSec  = Math.max(...agentData.map((a) => a.tokensPerSec), 1);
  const maxTokens     = Math.max(...agentData.map((a) => a.tokens),       1);

  // Bottleneck: agent with highest latency among "done" ones
  const doneAgents = agentData.filter((a) => a.status === "done");
  const bottleneck  = doneAgents.length > 0
    ? doneAgents.reduce((a, b) => (a.latencyMs > b.latencyMs ? a : b))
    : null;

  if (!hasData) {
    return (
      <div className="flex flex-col items-center justify-center py-10 gap-2">
        <BarChart2 size={22} className="text-cyber-subtle" />
        <p className="text-xs text-cyber-subtle">Run a pipeline to see metrics</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Bottleneck alert */}
      {bottleneck && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg px-3 py-2.5 flex items-start gap-2"
          style={{
            background: "rgba(245,158,11,0.06)",
            border: "1px solid rgba(245,158,11,0.2)",
          }}
        >
          <AlertTriangle size={11} className="text-cyber-orange flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[10px] font-semibold text-cyber-orange">Bottleneck Detected</p>
            <p className="text-[9px] text-cyber-muted mt-0.5">
              <span style={{ color: bottleneck.color }}>{bottleneck.label}</span>
              {" "}took {(bottleneck.latencyMs / 1000).toFixed(1)}s
              {totalMs > 0 && (
                <> · {((bottleneck.latencyMs / totalMs) * 100).toFixed(0)}% of total</>
              )}
            </p>
          </div>
        </motion.div>
      )}

      {/* Latency chart */}
      <div
        className="rounded-lg p-3"
        style={{ background: "rgba(11,16,37,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-1.5 mb-2.5">
          <Clock size={9} className="text-cyber-muted" />
          <span className="text-[10px] text-cyber-muted font-medium">Latency (s)</span>
        </div>
        <div className="flex flex-col gap-1.5">
          {agentData.filter((a) => a.latencyMs > 0).map((a) => {
            const pct = (a.latencyMs / maxLatency) * 100;
            const isBottleneck = bottleneck?.id === a.id;
            return (
              <div key={a.id}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[9px] text-cyber-muted">{a.label}</span>
                  <span
                    className="text-[9px] font-mono"
                    style={{ color: isBottleneck ? "#f59e0b" : a.color }}
                  >
                    {(a.latencyMs / 1000).toFixed(2)}s
                    {isBottleneck && " ⚠"}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background: isBottleneck
                        ? "linear-gradient(90deg, #f59e0b80, #f59e0b)"
                        : `linear-gradient(90deg, ${a.color}60, ${a.color})`,
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tokens/s chart */}
      <div
        className="rounded-lg p-3"
        style={{ background: "rgba(11,16,37,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-1.5 mb-2.5">
          <Zap size={9} className="text-cyber-cyan" />
          <span className="text-[10px] text-cyber-muted font-medium">Tokens / sec</span>
        </div>
        <div className="flex flex-col gap-1.5">
          {agentData.filter((a) => a.tokensPerSec > 0).map((a) => {
            const pct = (a.tokensPerSec / maxTokensSec) * 100;
            return (
              <div key={a.id}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[9px] text-cyber-muted">{a.label}</span>
                  <span className="text-[9px] font-mono" style={{ color: a.color }}>
                    {a.tokensPerSec.toFixed(1)} T/s
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: `linear-gradient(90deg, ${a.color}60, ${a.color})` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5, ease: "easeOut", delay: 0.1 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Token counts */}
      <div
        className="rounded-lg p-3"
        style={{ background: "rgba(11,16,37,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-1.5 mb-2.5">
          <MessageSquare size={9} className="text-cyber-purple" />
          <span className="text-[10px] text-cyber-muted font-medium">Token Output</span>
        </div>
        <div className="flex flex-col gap-1.5">
          {agentData.filter((a) => a.tokens > 0).map((a) => {
            const pct = (a.tokens / maxTokens) * 100;
            return (
              <div key={a.id}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[9px] text-cyber-muted">{a.label}</span>
                  <span className="text-[9px] font-mono" style={{ color: a.color }}>
                    {a.tokens.toLocaleString()} tok
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: `linear-gradient(90deg, ${a.color}60, ${a.color})` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5, ease: "easeOut", delay: 0.2 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pipeline timeline */}
      {totalMs > 0 && agentData.some((a) => a.latencyMs > 0) && (
        <div
          className="rounded-lg p-3"
          style={{ background: "rgba(11,16,37,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}
        >
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-1.5">
              <TrendingUp size={9} className="text-cyber-muted" />
              <span className="text-[10px] text-cyber-muted font-medium">Pipeline Timeline</span>
            </div>
            <span className="text-[9px] font-mono text-cyber-cyan">{(totalMs / 1000).toFixed(1)}s total</span>
          </div>
          {/* Gantt-style bars: simplified — proportional widths */}
          <div className="flex gap-0.5 h-3 rounded overflow-hidden">
            {agentData.filter((a) => a.latencyMs > 0).map((a) => {
              const pct = (a.latencyMs / totalMs) * 100;
              return (
                <div
                  key={a.id}
                  className="h-full rounded-sm flex-shrink-0 transition-all"
                  style={{
                    width: `${pct}%`,
                    background: a.color,
                    opacity: 0.7,
                    minWidth: "2px",
                  }}
                  title={`${a.label}: ${(a.latencyMs / 1000).toFixed(1)}s`}
                />
              );
            })}
          </div>
          <div className="flex flex-wrap gap-x-2.5 gap-y-0.5 mt-1.5">
            {agentData.filter((a) => a.latencyMs > 0).map((a) => (
              <div key={a.id} className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-sm" style={{ background: a.color }} />
                <span className="text-[8px] text-cyber-subtle">{a.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Conversation History Panel (Phase 13) ────────────────────────────────────

type SessionSummary = { id: string; title: string; created_at: string; updated_at: string; turn_count: number };
type TurnRecord = {
  id: number; session_id: string; turn_index: number; user_prompt: string;
  orchestration_mode: string; created_at: string;
  agent_outputs: { id: number; agent_id: string; role: string; full_output: string; token_count: number; latency_ms: number }[];
};

function ConversationPanel() {
  const { sessionId, setSessionId } = usePipeline();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [turns, setTurns] = useState<TurnRecord[]>([]);
  const [expandedTurn, setExpandedTurn] = useState<number | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND}/api/conversations`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions ?? []);
      }
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }, []);

  const fetchTurns = useCallback(async (sid: string) => {
    try {
      const res = await fetch(`${BACKEND}/api/conversations/${sid}`);
      if (res.ok) {
        const data = await res.json();
        setTurns(data.turns ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  const deleteSession = useCallback(async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("이 대화를 삭제하시겠습니까?")) return;
    try {
      await fetch(`${BACKEND}/api/conversations/${sid}`, { method: "DELETE" });
      if (sessionId === sid) setSessionId(null);
      fetchSessions();
      if (expandedSession === sid) { setExpandedSession(null); setTurns([]); }
    } catch { /* ignore */ }
  }, [sessionId, setSessionId, fetchSessions, expandedSession]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  useEffect(() => {
    if (expandedSession) fetchTurns(expandedSession);
  }, [expandedSession, fetchTurns]);

  const continueSession = useCallback((sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessionId(sid);
  }, [setSessionId]);

  return (
    <div className="flex flex-col gap-2">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-cyber-muted font-medium">대화 기록</span>
        <button
          onClick={fetchSessions}
          disabled={loading}
          className="text-cyber-subtle hover:text-cyber-muted transition-colors disabled:opacity-40"
        >
          <RefreshCw size={9} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* 세션 목록 */}
      {sessions.length === 0 ? (
        <div
          className="rounded-lg px-3 py-6 flex flex-col items-center gap-2"
          style={{ background: "rgba(11,16,37,0.4)", border: "1px solid rgba(255,255,255,0.04)" }}
        >
          <MessageSquare size={18} className="text-cyber-subtle" />
          <p className="text-[9px] text-cyber-subtle text-center">
            대화 기록이 없습니다.<br />
            TopBar의 <span className="text-cyber-cyan">New Session</span>을 눌러 시작하세요.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {sessions.map((s) => {
            const isActive = sessionId === s.id;
            const isExpanded = expandedSession === s.id;
            return (
              <div key={s.id}>
                <div
                  className="rounded-lg px-2.5 py-2 cursor-pointer transition-all"
                  style={{
                    background: isActive ? "rgba(34,211,238,0.08)" : "rgba(11,16,37,0.4)",
                    border: `1px solid ${isActive ? "rgba(34,211,238,0.25)" : "rgba(255,255,255,0.06)"}`,
                  }}
                  onClick={() => {
                    setExpandedSession(isExpanded ? null : s.id);
                    if (!isExpanded) setExpandedTurn(null);
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    {isExpanded
                      ? <ChevronDown size={9} className="text-cyber-muted flex-shrink-0" />
                      : <ChevronRight size={9} className="text-cyber-muted flex-shrink-0" />
                    }
                    <span className="text-[10px] text-cyber-text flex-1 truncate" title={s.title}>
                      {s.title}
                    </span>
                    <span className="text-[9px] text-cyber-subtle flex-shrink-0">
                      {s.turn_count}턴
                    </span>
                    <button
                      onClick={(e) => continueSession(s.id, e)}
                      className="text-[8px] px-1 rounded transition-colors flex-shrink-0"
                      style={{ color: isActive ? "#22d3ee" : "#64748b", background: isActive ? "rgba(34,211,238,0.1)" : "transparent" }}
                      title="이 세션으로 계속하기"
                    >
                      {isActive ? "활성" : "재개"}
                    </button>
                    <button
                      onClick={(e) => deleteSession(s.id, e)}
                      className="text-cyber-subtle hover:text-cyber-red transition-colors flex-shrink-0"
                      title="삭제"
                    >
                      <Trash2 size={8} />
                    </button>
                  </div>
                  <p className="text-[8px] text-cyber-subtle ml-4 mt-0.5 font-mono">
                    {new Date(s.updated_at).toLocaleDateString("ko-KR")} · {s.id.slice(0, 8)}
                  </p>
                </div>

                {/* 턴 목록 */}
                {isExpanded && turns.length > 0 && (
                  <div className="mt-1 ml-2 flex flex-col gap-1">
                    {turns.map((t) => (
                      <div key={t.id}>
                        <div
                          className="rounded px-2 py-1.5 cursor-pointer"
                          style={{ background: "rgba(11,16,37,0.6)", border: "1px solid rgba(255,255,255,0.05)" }}
                          onClick={() => setExpandedTurn(expandedTurn === t.id ? null : t.id)}
                        >
                          <div className="flex items-center gap-1">
                            {expandedTurn === t.id
                              ? <ChevronDown size={8} className="text-cyber-subtle flex-shrink-0" />
                              : <ChevronRight size={8} className="text-cyber-subtle flex-shrink-0" />
                            }
                            <span className="text-[9px] text-cyber-muted flex-shrink-0">#{t.turn_index + 1}</span>
                            <span className="text-[9px] text-cyber-text truncate flex-1">{t.user_prompt}</span>
                          </div>
                        </div>
                        {expandedTurn === t.id && t.agent_outputs.length > 0 && (
                          <div className="ml-2 mt-0.5 flex flex-col gap-0.5">
                            {t.agent_outputs.map((o) => (
                              <div
                                key={o.id}
                                className="rounded px-2 py-1.5"
                                style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.04)" }}
                              >
                                <div className="flex items-center gap-1.5 mb-1">
                                  <span className="text-[8px] font-bold text-cyber-muted uppercase">{o.role}</span>
                                  <span className="text-[8px] text-cyber-subtle">{o.token_count} tok · {(o.latency_ms / 1000).toFixed(1)}s</span>
                                </div>
                                <p className="text-[8px] text-cyber-text leading-relaxed line-clamp-4 whitespace-pre-wrap">
                                  {o.full_output.slice(0, 300)}
                                  {o.full_output.length > 300 && "…"}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ─── Provider health panel ────────────────────────────────────────────────────

function ProvidersPanel() {
  const { providerStatus, providerType, useRealModels } = usePipeline();

  const items = [
    { key: "ollama",       label: "Ollama",          port: "11434", color: "#22d3ee" },
    { key: "lmstudio",     label: "LM Studio",       port: "1234",  color: "#a855f7" },
    { key: "llamacpp",     label: "llama-cpp-python", port: "8080",  color: "#f59e0b" },
    { key: "transformers", label: "HF Transformers",  port: "—",     color: "#10b981" },
  ] as const;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[10px] text-cyber-muted">
          Mode: <span className="text-cyber-cyan font-mono">
            {useRealModels ? providerType : "simulation"}
          </span>
        </span>
      </div>
      {items.map(({ key, label, port, color }) => {
        const online = providerStatus[key];
        const isActive = providerType === key && useRealModels;
        return (
          <div
            key={key}
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2"
            style={{
              background: isActive ? `${color}10` : "rgba(11,16,37,0.4)",
              border: `1px solid ${isActive ? color + "30" : "rgba(255,255,255,0.06)"}`,
            }}
          >
            {online
              ? <Wifi size={11} style={{ color, flexShrink: 0 }} />
              : <WifiOff size={11} className="text-cyber-subtle flex-shrink-0" />
            }
            <div className="flex-1 min-w-0">
              <p className="text-[11px] text-cyber-text font-medium">{label}</p>
              <p className="text-[9px] text-cyber-muted font-mono">localhost:{port}</p>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: online ? "#10b981" : "#334155" }}
              />
              <span className="text-[9px] font-mono" style={{ color: online ? "#10b981" : "#64748b" }}>
                {online ? "online" : "offline"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function RightPanel() {
  const { agentMetrics, totalTokens, totalMs, status, selectedNode, activeParallelStage } = usePipeline();
  const [uptime, setUptime] = useState(0);
  const [activeTab, setActiveTab] = useState<"agents" | "output" | "metrics" | "providers" | "models" | "chat">("agents");
  const [registryAgents, setRegistryAgents] = useState<AgentRecord[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentRecord | undefined>(undefined);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/registry/agents`);
      if (res.ok) {
        const data = await res.json();
        setRegistryAgents(data.agents ?? []);
      }
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    const t = setInterval(() => setUptime((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const totalVram = Object.values(agentMetrics).reduce((s, m) => s + m.vramGb, 0);
  const activeAgentCount = Object.values(agentMetrics).filter((m) => m.status === "running").length;
  const doneCount = Object.values(agentMetrics).filter((m) => m.status === "done").length;
  const avgLatency =
    doneCount > 0
      ? Math.round(Object.values(agentMetrics).reduce((s, m) => s + m.latencyMs, 0) / doneCount)
      : 0;

  return (
    <motion.aside
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut", delay: 0.1 }}
      className="flex flex-col h-full w-full relative overflow-hidden"
      style={{
        background: "rgba(7, 10, 22, 0.95)",
        borderLeft: "1px solid rgba(34, 211, 238, 0.08)",
      }}
    >
      {/* ── Node Config Panel (replaces monitor when node is selected) ── */}
      <AnimatePresence mode="wait">
        {selectedNode && (
          <motion.div
            key="node-config"
            className="flex flex-col h-full w-full absolute inset-0 z-10"
            style={{ background: "rgba(7, 10, 22, 0.98)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <NodeConfigPanel />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.04] flex-shrink-0">
        <div className="flex items-center justify-between mb-0.5">
          <p className="text-sm font-semibold text-cyber-text">Monitor</p>
          <div className="flex items-center gap-1.5">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: status === "running" ? "#22d3ee" : "#334155",
                animation: status === "running" ? "pulse 1.5s ease-in-out infinite" : "none",
              }}
            />
            <span className="text-[10px] font-mono text-cyber-muted">{fmt(uptime)}</span>
          </div>
        </div>
        <p className="text-[10px] text-cyber-muted">Agent metrics & resource usage</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-1.5 p-2.5 flex-shrink-0">
        {[
          { label: "Tokens",      value: totalTokens > 0 ? totalTokens.toLocaleString() : "—", icon: MessageSquare, color: "#22d3ee" },
          { label: "Avg Latency", value: avgLatency > 0 ? `${(avgLatency / 1000).toFixed(1)}s` : "—", icon: Clock, color: "#a855f7" },
          { label: "VRAM",        value: totalVram > 0 ? `${totalVram.toFixed(1)} GB` : "—", icon: MemoryStick, color: "#f472b6" },
          { label: "Active",      value: `${activeAgentCount} / ${registryAgents.length}`, icon: Activity, color: "#10b981" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-lg p-2"
            style={{ background: `${color}07`, border: `1px solid ${color}18` }}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Icon size={10} color={color} />
              <span className="text-[9px] text-cyber-subtle uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-xs font-bold font-mono" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* GPU card */}
      <div className="px-2.5 pb-2 flex-shrink-0">
        <div
          className="rounded-lg p-2.5"
          style={{
            background: "rgba(34, 211, 238, 0.04)",
            border: "1px solid rgba(34, 211, 238, 0.1)",
          }}
        >
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <Cpu size={10} className="text-cyber-cyan" />
              <span className="text-[10px] text-cyber-muted font-medium">RTX 5080 · 16GB</span>
            </div>
            <span className="text-[10px] font-mono text-cyber-cyan">
              {totalVram.toFixed(1)} / 16.0 GB
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden mb-1">
            <motion.div
              className="h-full rounded-full"
              style={{ background: "linear-gradient(90deg, #22d3ee, #a855f7)" }}
              animate={{ width: `${(totalVram / 16) * 100}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] text-cyber-subtle">CUDA 13.0 · Compute 12.0</span>
            <div className="flex items-center gap-1">
              <Zap size={9} className="text-cyber-muted" />
              <span className="text-[9px] text-cyber-muted">
                {status === "running" ? "~200W" : "0W"} / 360W
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex px-2.5 pb-1.5 gap-1 flex-shrink-0">
        {([
          { key: "agents",    label: "Agents" },
          { key: "output",    label: "Output" },
          { key: "metrics",   label: "Metrics" },
          { key: "providers", label: "Prvdrs" },
          { key: "models",    label: "Models" },
          { key: "chat",      label: "Chat" },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "flex-1 py-1 rounded text-[9px] font-medium transition-all duration-150",
              activeTab === key
                ? "bg-cyber-cyan/10 text-cyber-cyan"
                : "text-cyber-muted hover:text-cyber-text"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-2.5 pb-2.5">
        <AnimatePresence mode="wait">
          {activeTab === "agents" && (
            <motion.div
              key="agents"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex flex-col gap-1.5"
            >
              {/* Parallel stage banner */}
              {activeParallelStage && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg px-3 py-2 flex items-center gap-2 mb-1"
                  style={{
                    background: "rgba(34,211,238,0.06)",
                    border: "1px solid rgba(34,211,238,0.2)",
                  }}
                >
                  <div className="flex gap-0.5">
                    {[0,1,2].map((i) => (
                      <motion.div
                        key={i}
                        className="w-1 h-1 rounded-full bg-cyber-cyan"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
                      />
                    ))}
                  </div>
                  <span className="text-[10px] text-cyber-cyan font-mono">
                    Parallel execution — {activeParallelStage.agentIds.length} agents
                  </span>
                </motion.div>
              )}

              {/* 에이전트 추가 버튼 */}
              <motion.button
                onClick={() => { setEditingAgent(undefined); setEditorOpen(true); }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className="flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] text-cyber-muted hover:text-cyber-text transition-colors"
                style={{ border: "1px dashed rgba(255,255,255,0.12)" }}
              >
                <Plus size={10} />
                Add Agent
              </motion.button>

              {registryAgents.map((agent, i) => {
                const meta = ROLE_META[agent.role] ?? DEFAULT_ROLE_META;
                const m = agentMetrics[agent.id] ?? {
                  status: "idle" as const,
                  tokens: 0,
                  tokensPerSec: 0,
                  latencyMs: 0,
                  vramGb: 0,
                  output: "",
                  provider: "simulation" as const,
                };
                return (
                  <motion.div
                    key={agent.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <AgentRowDB
                      agent={agent}
                      meta={meta}
                      metrics={m}
                      onEdit={() => { setEditingAgent(agent); setEditorOpen(true); }}
                    />
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          {activeTab === "output" && (
            <motion.div
              key="output"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <OutputPanel />
            </motion.div>
          )}

          {activeTab === "models" && (
            <motion.div
              key="models"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <ModelDownloadPanel />
              <RemoteModelsSection />
            </motion.div>
          )}

          {activeTab === "metrics" && (
            <motion.div
              key="metrics"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <MetricsPanel />
            </motion.div>
          )}

          {activeTab === "chat" && (
            <motion.div
              key="chat"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <ConversationPanel />
            </motion.div>
          )}

          {activeTab === "providers" && (
            <motion.div
              key="providers"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex flex-col gap-3"
            >
              <ProvidersPanel />

              {/* Pipeline stats */}
              {totalMs > 0 && (
                <div
                  className="rounded-lg p-3"
                  style={{
                    background: "rgba(34, 211, 238, 0.04)",
                    border: "1px solid rgba(34, 211, 238, 0.1)",
                  }}
                >
                  <div className="flex items-center gap-1.5 mb-2">
                    <TrendingUp size={11} className="text-cyber-cyan" />
                    <span className="text-[10px] text-cyber-muted">Last Run</span>
                  </div>
                  {[
                    { label: "Total Tokens", value: totalTokens.toLocaleString() },
                    { label: "Total Time",   value: `${(totalMs / 1000).toFixed(1)}s` },
                    {
                      label: "Throughput",
                      value: totalMs > 0 ? `${(totalTokens / (totalMs / 1000)).toFixed(1)} T/s` : "—",
                    },
                    { label: "Agents Run",   value: `${doneCount} / ${registryAgents.length}` },
                  ].map(({ label, value }) => (
                    <div
                      key={label}
                      className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0"
                    >
                      <span className="text-[10px] text-cyber-subtle">{label}</span>
                      <span className="text-[10px] font-mono text-cyber-cyan">{value}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* System info */}
              <div
                className="rounded-lg p-2.5"
                style={{
                  background: "rgba(11, 16, 37, 0.6)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <div className="flex items-center gap-1.5 mb-2">
                  <BarChart2 size={10} className="text-cyber-muted" />
                  <span className="text-[10px] text-cyber-muted">System</span>
                </div>
                {[
                  { label: "CPU", value: "Ryzen 9 9900X", sub: "24-core" },
                  { label: "RAM", value: "64.0 GB",       sub: "DDR5" },
                  { label: "GPU", value: "RTX 5080",      sub: "16 GB GDDR7" },
                  { label: "CUDA",value: "13.0",          sub: "Compute 12.0" },
                ].map(({ label, value, sub }) => (
                  <div
                    key={label}
                    className="flex items-center justify-between py-1 border-b border-white/[0.04] last:border-0"
                  >
                    <span className="text-[10px] text-cyber-subtle">{label}</span>
                    <div>
                      <span className="text-[10px] text-cyber-text">{value}</span>
                      <span className="text-[9px] text-cyber-muted ml-1.5">{sub}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom status */}
      <div
        className="px-4 py-2 border-t border-white/[0.04] flex-shrink-0"
        style={{ background: "rgba(0,0,0,0.2)" }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: status === "idle" ? "#334155" : "#22d3ee" }}
          />
          <span className="text-[10px] text-cyber-muted">
            {status === "idle" ? "Ready" : `${new URL(BACKEND).host} · online`}
          </span>
        </div>
      </div>

      {/* Agent Editor Modal */}
      <AgentEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        agent={editingAgent}
        onSaved={fetchAgents}
      />
    </motion.aside>
  );
}

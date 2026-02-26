"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import NodeConfigPanel from "@/components/canvas/NodeConfigPanel";
import {
  Activity,
  Cpu,
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePipeline, type AgentMetrics, type ProviderType } from "@/context/PipelineContext";

// ─── Config ───────────────────────────────────────────────────────────────────

const AGENT_CONFIG = [
  { id: "router-1",      label: "Router",      icon: GitBranch,   color: "#22d3ee", vramMax: 2.5 },
  { id: "coder-1",       label: "Code Writer", icon: Code2,       color: "#a855f7", vramMax: 5.2 },
  { id: "analyzer-1",    label: "Analyzer",    icon: FlaskConical,color: "#f472b6", vramMax: 3.1 },
  { id: "validator-1",   label: "Validator",   icon: ShieldCheck, color: "#f59e0b", vramMax: 3.4 },
  { id: "synthesizer-1", label: "Synthesizer", icon: Layers,      color: "#10b981", vramMax: 6.0 },
];

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

function AgentRow({
  config,
  metrics,
}: {
  config: (typeof AGENT_CONFIG)[number];
  metrics: AgentMetrics;
}) {
  const Icon = config.icon;
  const isRunning = metrics.status === "running";
  const providerColor = PROVIDER_COLORS[metrics.provider] ?? "#64748b";
  const providerLabel = PROVIDER_LABELS[metrics.provider] ?? "SIM";

  return (
    <motion.div
      layout
      className="rounded-lg p-2.5"
      style={{
        background: `${config.color}06`,
        border: `1px solid ${config.color}${isRunning ? "35" : "15"}`,
        transition: "border-color 0.3s",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ background: `${config.color}15` }}
        >
          <Icon size={12} color={config.color} />
        </div>
        <span className="text-xs font-medium text-cyber-text flex-1">{config.label}</span>
        <div className="flex items-center gap-1.5">
          {metrics.provider !== "simulation" && (
            <span
              className="text-[8px] font-bold px-1 rounded"
              style={{ color: providerColor, background: `${providerColor}20` }}
            >
              {providerLabel}
            </span>
          )}
          <StatusIcon status={metrics.status} />
          <span
            className="text-[10px] font-mono"
            style={{
              color:
                metrics.status === "running" ? config.color :
                metrics.status === "done"    ? "#10b981" :
                "#64748b",
            }}
          >
            {metrics.status}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-1.5 mb-2">
        <div>
          <p className="text-[9px] text-cyber-subtle uppercase tracking-wider mb-0.5">T/s</p>
          <p className="text-[11px] font-mono font-semibold" style={{ color: isRunning ? config.color : "#64748b" }}>
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
          <span className="text-[9px] font-mono" style={{ color: config.color }}>
            {metrics.vramGb.toFixed(1)} / {config.vramMax} GB
          </span>
        </div>
        <VramBar used={metrics.vramGb} max={config.vramMax} color={config.color} />
      </div>

      {/* Running progress bar */}
      {isRunning && (
        <motion.div className="mt-2 h-0.5 rounded-full overflow-hidden bg-white/[0.04]">
          <motion.div
            className="h-full rounded-full"
            style={{ background: `linear-gradient(90deg, transparent, ${config.color})` }}
            animate={{ x: ["-100%", "100%"] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          />
        </motion.div>
      )}
    </motion.div>
  );
}

// ─── Output viewer ────────────────────────────────────────────────────────────

function OutputPanel() {
  const { agentMetrics } = usePipeline();
  const [activeAgent, setActiveAgent] = useState("router-1");
  const currentOutput = agentMetrics[activeAgent]?.output ?? "";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-1 flex-wrap">
        {AGENT_CONFIG.map((c) => {
          const m = agentMetrics[c.id];
          const hasOutput = m && m.output.length > 0;
          return (
            <button
              key={c.id}
              onClick={() => setActiveAgent(c.id)}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-medium transition-all",
                activeAgent === c.id ? "text-white" : "text-cyber-muted hover:text-cyber-text"
              )}
              style={
                activeAgent === c.id
                  ? { background: `${c.color}20`, border: `1px solid ${c.color}40`, color: c.color }
                  : { background: "transparent", border: "1px solid transparent" }
              }
            >
              {c.label}
              {hasOutput && (
                <span
                  className="ml-1 w-1 h-1 rounded-full inline-block align-middle"
                  style={{ background: c.color }}
                />
              )}
            </button>
          );
        })}
      </div>
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

const BACKEND = "http://localhost:8000";

function ModelDownloadPanel() {
  const [input, setInput] = useState("");
  const [dlState, setDlState] = useState<DownloadState>({ stage: "idle" });
  const [localModels, setLocalModels] = useState<LocalModel[]>([]);
  const [loadingLocal, setLoadingLocal] = useState(false);
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

      {/* Local models */}
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
            {localModels.map((m) => (
              <div
                key={m.model_id}
                className="rounded px-2.5 py-1.5 flex items-center gap-2"
                style={{ background: "rgba(11,16,37,0.4)", border: "1px solid rgba(255,255,255,0.04)" }}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: "#10b981" }}
                />
                <span className="text-[10px] text-cyber-text flex-1 truncate font-mono">{m.model_id}</span>
                <span className="text-[9px] text-cyber-muted flex-shrink-0">{m.size_str}</span>
              </div>
            ))}
          </div>
        )}
      </div>
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
  const [activeTab, setActiveTab] = useState<"agents" | "output" | "providers" | "models">("agents");

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
          { label: "Active",      value: `${activeAgentCount} / ${AGENT_CONFIG.length}`, icon: Activity, color: "#10b981" },
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
        {(["agents", "output", "providers", "models"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "flex-1 py-1 rounded text-[10px] font-medium transition-all duration-150 capitalize",
              activeTab === tab
                ? "bg-cyber-cyan/10 text-cyber-cyan"
                : "text-cyber-muted hover:text-cyber-text"
            )}
          >
            {tab}
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

              {AGENT_CONFIG.map((cfg, i) => {
                const m = agentMetrics[cfg.id] ?? {
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
                    key={cfg.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <AgentRow config={cfg} metrics={m} />
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
                    { label: "Agents Run",   value: `${doneCount} / ${AGENT_CONFIG.length}` },
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
            {status === "idle" ? "Ready" : "localhost:8000 · online"}
          </span>
        </div>
      </div>
    </motion.aside>
  );
}

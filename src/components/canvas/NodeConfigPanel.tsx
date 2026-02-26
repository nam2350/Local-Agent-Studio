"use client";

import { useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft, RotateCcw, Cpu, Thermometer, Hash,
  GitBranch, Code2, FlaskConical, Layers, ShieldCheck,
  MessageSquare, Sparkles, ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePipeline, type ProviderType } from "@/context/PipelineContext";
import { getDefaultConfig, type AgentType, type NodeConfig } from "@/constants/agentDefaults";

// ─── Agent type config ────────────────────────────────────────────────────────

const AGENT_ICONS: Record<AgentType, React.FC<{ size?: number; color?: string }>> = {
  router:      GitBranch,
  coder:       Code2,
  analyzer:    FlaskConical,
  synthesizer: Layers,
  validator:   ShieldCheck,
  input:       MessageSquare,
  output:      Sparkles,
  custom:      Cpu,
};

const AGENT_COLORS: Record<AgentType, string> = {
  router:      "#22d3ee",
  coder:       "#a855f7",
  analyzer:    "#f472b6",
  synthesizer: "#10b981",
  validator:   "#f59e0b",
  input:       "#3b82f6",
  output:      "#10b981",
  custom:      "#64748b",
};

// ─── Provider options ─────────────────────────────────────────────────────────

const PROVIDERS: { value: ProviderType; label: string; color: string }[] = [
  { value: "simulation",   label: "Simulation",    color: "#64748b" },
  { value: "ollama",       label: "Ollama",         color: "#22d3ee" },
  { value: "lmstudio",     label: "LM Studio",      color: "#a855f7" },
  { value: "llamacpp",     label: "llama.cpp",      color: "#f59e0b" },
  { value: "transformers", label: "HF Transformers",color: "#10b981" },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[9px] font-semibold text-cyber-muted uppercase tracking-widest mb-1.5">
      {children}
    </p>
  );
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
  color,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (v: number) => void;
  color: string;
}) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <SectionLabel>{label}</SectionLabel>
        <span
          className="text-[10px] font-mono font-bold"
          style={{ color }}
        >
          {display}
        </span>
      </div>
      <div className="relative h-1.5 rounded-full bg-white/[0.06]">
        <div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}60, ${color})` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full opacity-0 cursor-pointer"
          style={{ height: "100%" }}
        />
        {/* Thumb */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-cyber-bg shadow-lg"
          style={{ left: `calc(${pct}% - 6px)`, background: color, pointerEvents: "none" }}
        />
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function NodeConfigPanel() {
  const {
    selectedNode,
    setSelectedNode,
    nodeConfigs,
    setNodeConfig,
    resetNodeConfig,
    providerStatus,
    availableModels,
  } = usePipeline();

  if (!selectedNode) return null;

  const { id: nodeId, label, agentType } = selectedNode;
  const color = AGENT_COLORS[agentType] ?? "#64748b";
  const Icon  = AGENT_ICONS[agentType]  ?? Cpu;
  const defaults = getDefaultConfig(nodeId, agentType);
  const config: NodeConfig = { ...defaults, ...nodeConfigs[nodeId] };

  const patch = useCallback(
    (p: Partial<NodeConfig>) => setNodeConfig(nodeId, p),
    [nodeId, setNodeConfig]
  );

  const isInputOutput = agentType === "input" || agentType === "output";

  // Model options depending on provider
  const modelOptions: string[] = useMemo(() => {
    if (config.provider === "ollama")   return availableModels.ollama   ?? [];
    if (config.provider === "lmstudio") return availableModels.lmstudio ?? [];
    return [];
  }, [config.provider, availableModels]);

  const providerOnline = (p: ProviderType): boolean => {
    if (p === "simulation")   return true;
    if (p === "transformers") return providerStatus.transformers;
    return providerStatus[p as keyof typeof providerStatus] ?? false;
  };

  return (
    <motion.div
      key={nodeId}
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 8 }}
      transition={{ duration: 0.18 }}
      className="flex flex-col h-full"
    >
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-2.5 px-3 py-2.5 border-b border-white/[0.04] flex-shrink-0"
        style={{ background: `${color}08` }}
      >
        <button
          onClick={() => setSelectedNode(null)}
          className="flex items-center justify-center w-6 h-6 rounded-md text-cyber-muted hover:text-cyber-text transition-colors flex-shrink-0"
          style={{ background: "rgba(255,255,255,0.04)" }}
        >
          <ArrowLeft size={12} />
        </button>

        <div
          className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0"
          style={{ background: `${color}18`, border: `1px solid ${color}30` }}
        >
          <Icon size={14} color={color} />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-cyber-text truncate leading-none">
            {label}
          </p>
          <p className="text-[10px] font-medium uppercase tracking-widest" style={{ color }}>
            {agentType} · config
          </p>
        </div>

        <button
          onClick={() => resetNodeConfig(nodeId, agentType)}
          className="flex items-center justify-center w-6 h-6 rounded-md text-cyber-muted hover:text-cyber-orange transition-colors flex-shrink-0"
          style={{ background: "rgba(255,255,255,0.04)" }}
          title="Reset to defaults"
        >
          <RotateCcw size={11} />
        </button>
      </div>

      {/* ── Scrollable body ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-4">

        {isInputOutput ? (
          <div className="flex flex-col items-center justify-center h-24 gap-2">
            <p className="text-[11px] text-cyber-muted text-center">
              {agentType === "input"
                ? "Entry point — accepts user prompt"
                : "Output node — displays final result"}
            </p>
          </div>
        ) : (
          <>
            {/* ── Provider ─────────────────────────────────────────── */}
            <div>
              <SectionLabel>Provider</SectionLabel>
              <div className="flex flex-col gap-1">
                {PROVIDERS.map((p) => {
                  const online   = providerOnline(p.value);
                  const selected = config.provider === p.value;
                  return (
                    <button
                      key={p.value}
                      onClick={() => patch({ provider: p.value })}
                      className={cn(
                        "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-all duration-150 text-left",
                        selected ? "text-white" : "text-cyber-muted hover:text-cyber-text"
                      )}
                      style={
                        selected
                          ? { background: `${p.color}18`, border: `1px solid ${p.color}40` }
                          : { background: "transparent", border: "1px solid rgba(255,255,255,0.04)" }
                      }
                    >
                      <div
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: online ? "#10b981" : "#334155" }}
                      />
                      <span className="flex-1" style={selected ? { color: p.color } : {}}>
                        {p.label}
                      </span>
                      {selected && (
                        <span className="text-[9px] font-mono" style={{ color: p.color }}>
                          active
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── Model ────────────────────────────────────────────── */}
            <div>
              <SectionLabel>Model</SectionLabel>

              {modelOptions.length > 0 ? (
                /* Dropdown for providers with known model list */
                <div className="relative">
                  <select
                    value={config.modelId}
                    onChange={(e) => patch({ modelId: e.target.value })}
                    className="w-full appearance-none text-[11px] text-cyber-text font-mono px-2.5 py-2 pr-7 rounded-lg outline-none"
                    style={{
                      background: "rgba(11,16,37,0.8)",
                      border: `1px solid ${color}30`,
                    }}
                  >
                    {modelOptions.map((m) => (
                      <option key={m} value={m} style={{ background: "#0b1025" }}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={11}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-cyber-muted pointer-events-none"
                  />
                </div>
              ) : (
                /* Text input for transformers / custom */
                <input
                  type="text"
                  value={config.modelId}
                  onChange={(e) => patch({ modelId: e.target.value })}
                  placeholder={
                    config.provider === "transformers"
                      ? "e.g. Qwen/Qwen2.5-3B-Instruct"
                      : defaults.modelId
                  }
                  className="w-full text-[11px] text-cyber-text font-mono px-2.5 py-2 rounded-lg outline-none placeholder-cyber-subtle"
                  style={{
                    background: "rgba(11,16,37,0.8)",
                    border: `1px solid ${color}30`,
                  }}
                />
              )}

              {config.provider === "transformers" && (
                <p className="text-[9px] text-cyber-subtle mt-1">
                  HuggingFace model ID — downloaded on first run
                </p>
              )}
            </div>

            {/* ── System Prompt ─────────────────────────────────────── */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <SectionLabel>System Prompt</SectionLabel>
                <span className="text-[9px] text-cyber-subtle">
                  {config.systemPrompt.length} chars
                </span>
              </div>
              <textarea
                value={config.systemPrompt}
                onChange={(e) => patch({ systemPrompt: e.target.value })}
                rows={5}
                className="w-full text-[10px] text-cyber-text font-mono px-2.5 py-2 rounded-lg outline-none resize-none placeholder-cyber-subtle leading-relaxed"
                style={{
                  background: "rgba(11,16,37,0.8)",
                  border: `1px solid ${color}25`,
                }}
                placeholder="Enter a system prompt for this agent..."
              />
            </div>

            {/* ── Max Tokens ────────────────────────────────────────── */}
            <SliderRow
              label="Max Tokens"
              value={config.maxTokens}
              min={64}
              max={2048}
              step={64}
              display={config.maxTokens.toString()}
              onChange={(v) => patch({ maxTokens: v })}
              color={color}
            />

            {/* ── Temperature ───────────────────────────────────────── */}
            <SliderRow
              label="Temperature"
              value={config.temperature}
              min={0}
              max={2}
              step={0.05}
              display={config.temperature.toFixed(2)}
              onChange={(v) => patch({ temperature: v })}
              color={color}
            />

            {/* ── Config summary ────────────────────────────────────── */}
            <div
              className="rounded-lg p-2.5 mt-auto"
              style={{
                background: `${color}06`,
                border: `1px solid ${color}18`,
              }}
            >
              <div className="flex items-center gap-1.5 mb-1.5">
                <Hash size={9} style={{ color }} />
                <span className="text-[9px] text-cyber-muted uppercase tracking-wider">
                  Config Summary
                </span>
              </div>
              {[
                { label: "Provider", value: config.provider },
                { label: "Model",    value: config.modelId || "—" },
                { label: "Tokens",   value: `max ${config.maxTokens}` },
                { label: "Temp",     value: config.temperature.toFixed(2) },
              ].map(({ label: l, value: v }) => (
                <div
                  key={l}
                  className="flex items-center justify-between py-0.5"
                >
                  <span className="text-[9px] text-cyber-subtle">{l}</span>
                  <span className="text-[9px] font-mono" style={{ color }}>
                    {v.length > 24 ? v.slice(0, 22) + "…" : v}
                  </span>
                </div>
              ))}
            </div>

            {/* Quantization note for transformers */}
            {config.provider === "transformers" && (
              <div
                className="rounded-lg p-2.5"
                style={{
                  background: "rgba(16, 185, 129, 0.04)",
                  border: "1px solid rgba(16, 185, 129, 0.15)",
                }}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <Thermometer size={9} className="text-cyber-green" />
                  <span className="text-[9px] text-cyber-green uppercase tracking-wider">
                    GPU · RTX 5080
                  </span>
                </div>
                <p className="text-[9px] text-cyber-subtle leading-relaxed">
                  Model loads on first run. Use 4-bit quant for models {">"} 8B.
                  Stays cached in VRAM until server restarts.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}

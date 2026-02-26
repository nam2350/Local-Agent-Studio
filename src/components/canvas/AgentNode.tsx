"use client";

import { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import {
  Cpu,
  GitBranch,
  Code2,
  FlaskConical,
  Layers,
  ShieldCheck,
  Sparkles,
  MessageSquare,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProviderType } from "@/context/PipelineContext";

export type AgentType =
  | "router"
  | "coder"
  | "analyzer"
  | "synthesizer"
  | "validator"
  | "input"
  | "output"
  | "custom";

export type AgentStatus = "idle" | "running" | "done" | "error";

export type AgentNodeData = {
  label: string;
  agentType: AgentType;
  model: string;
  status: AgentStatus;
  tokens?: number;
  tokensPerSec?: number;
  description?: string;
  provider?: ProviderType;
};

const AGENT_CONFIG: Record<
  AgentType,
  {
    icon: React.FC<{ size?: number; className?: string; color?: string }>;
    color: string;
    borderColor: string;
    glowColor: string;
    bgGradient: string;
  }
> = {
  router: {
    icon: GitBranch,
    color: "#22d3ee",
    borderColor: "rgba(34, 211, 238, 0.3)",
    glowColor: "rgba(34, 211, 238, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(34, 211, 238, 0.08), rgba(34, 211, 238, 0.02))",
  },
  coder: {
    icon: Code2,
    color: "#a855f7",
    borderColor: "rgba(168, 85, 247, 0.3)",
    glowColor: "rgba(168, 85, 247, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(168, 85, 247, 0.08), rgba(168, 85, 247, 0.02))",
  },
  analyzer: {
    icon: FlaskConical,
    color: "#f472b6",
    borderColor: "rgba(244, 114, 182, 0.3)",
    glowColor: "rgba(244, 114, 182, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(244, 114, 182, 0.08), rgba(244, 114, 182, 0.02))",
  },
  synthesizer: {
    icon: Layers,
    color: "#10b981",
    borderColor: "rgba(16, 185, 129, 0.3)",
    glowColor: "rgba(16, 185, 129, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(16, 185, 129, 0.02))",
  },
  validator: {
    icon: ShieldCheck,
    color: "#f59e0b",
    borderColor: "rgba(245, 158, 11, 0.3)",
    glowColor: "rgba(245, 158, 11, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(245, 158, 11, 0.02))",
  },
  input: {
    icon: MessageSquare,
    color: "#3b82f6",
    borderColor: "rgba(59, 130, 246, 0.3)",
    glowColor: "rgba(59, 130, 246, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(59, 130, 246, 0.02))",
  },
  output: {
    icon: Sparkles,
    color: "#10b981",
    borderColor: "rgba(16, 185, 129, 0.3)",
    glowColor: "rgba(16, 185, 129, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(16, 185, 129, 0.02))",
  },
  custom: {
    icon: Cpu,
    color: "#64748b",
    borderColor: "rgba(100, 116, 139, 0.3)",
    glowColor: "rgba(100, 116, 139, 0.15)",
    bgGradient: "linear-gradient(135deg, rgba(100, 116, 139, 0.08), rgba(100, 116, 139, 0.02))",
  },
};

const PROVIDER_LABEL: Record<ProviderType, { text: string; color: string }> = {
  simulation: { text: "SIM",   color: "#64748b" },
  ollama:     { text: "OLLAMA",color: "#22d3ee" },
  lmstudio:   { text: "LMS",   color: "#a855f7" },
  llamacpp:   { text: "GGUF",  color: "#f59e0b" },
  transformers: { text: "HF",  color: "#10b981" },
};

function StatusIcon({ status }: { status: AgentStatus }) {
  switch (status) {
    case "running":
      return <Loader2 size={10} className="animate-spin text-cyber-cyan" />;
    case "done":
      return <CheckCircle2 size={10} className="text-cyber-green" />;
    case "error":
      return <AlertCircle size={10} className="text-cyber-red" />;
    default:
      return <Circle size={10} className="text-cyber-muted" />;
  }
}

const AgentNode = memo(function AgentNode({ data, selected }: NodeProps) {
  const nodeData = data as AgentNodeData;
  const config = AGENT_CONFIG[nodeData.agentType] ?? AGENT_CONFIG.custom;
  const Icon = config.icon;
  const isRunning = nodeData.status === "running";
  const providerInfo = PROVIDER_LABEL[nodeData.provider ?? "simulation"];

  return (
    <motion.div
      initial={{ scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="relative"
    >
      {/* Glow halo when running or selected */}
      {(isRunning || selected) && (
        <motion.div
          className="absolute inset-0 rounded-xl -z-10"
          style={{
            background: config.glowColor,
            filter: "blur(12px)",
          }}
          animate={{ opacity: isRunning ? [0.4, 1, 0.4] : 0.6 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {/* Node card */}
      <div
        className={cn(
          "relative w-[200px] rounded-xl overflow-hidden",
          "transition-all duration-200",
          selected && "ring-1 ring-cyber-cyan/60"
        )}
        style={{
          background: "rgba(11, 16, 37, 0.92)",
          border: `1px solid ${selected ? config.color + "80" : config.borderColor}`,
          boxShadow: selected
            ? `0 0 20px ${config.glowColor}, 0 4px 24px rgba(0,0,0,0.4)`
            : `0 4px 24px rgba(0,0,0,0.3)`,
        }}
      >
        {/* Top accent bar */}
        <div
          className="h-[2px] w-full"
          style={{
            background: `linear-gradient(90deg, transparent, ${config.color}, transparent)`,
          }}
        />

        {/* Header */}
        <div
          className="flex items-center gap-2.5 px-3 py-2.5"
          style={{ background: config.bgGradient }}
        >
          {/* Icon container */}
          <div
            className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
            style={{
              background: `${config.color}18`,
              border: `1px solid ${config.color}30`,
            }}
          >
            <Icon size={15} color={config.color} />
          </div>

          {/* Label + type */}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-cyber-text truncate leading-none mb-0.5">
              {nodeData.label}
            </p>
            <p
              className="text-[10px] font-medium uppercase tracking-widest"
              style={{ color: config.color }}
            >
              {nodeData.agentType}
            </p>
          </div>

          {/* Status */}
          <div className="flex-shrink-0">
            <StatusIcon status={nodeData.status} />
          </div>
        </div>

        {/* Divider */}
        <div className="h-px bg-white/[0.04]" />

        {/* Body */}
        <div className="px-3 py-2">
          {/* Model + provider badge row */}
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] text-cyber-muted font-mono truncate flex-1 mr-1">
              {nodeData.model}
            </p>
            {nodeData.provider && nodeData.provider !== "simulation" && (
              <span
                className="text-[8px] font-bold px-1 py-0.5 rounded flex-shrink-0"
                style={{
                  color: providerInfo.color,
                  background: `${providerInfo.color}20`,
                  border: `1px solid ${providerInfo.color}40`,
                }}
              >
                {providerInfo.text}
              </span>
            )}
          </div>

          {/* Metrics row */}
          <div className="flex items-center gap-3">
            {nodeData.tokens !== undefined && (
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] text-cyber-subtle uppercase tracking-wider">Tokens</span>
                <span className="text-[11px] font-semibold font-mono text-cyber-text">
                  {nodeData.tokens.toLocaleString()}
                </span>
              </div>
            )}
            {nodeData.tokensPerSec !== undefined && (
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] text-cyber-subtle uppercase tracking-wider">T/s</span>
                <span
                  className="text-[11px] font-semibold font-mono"
                  style={{ color: config.color }}
                >
                  {nodeData.tokensPerSec}
                </span>
              </div>
            )}
            {nodeData.description && !nodeData.tokens && (
              <p className="text-[10px] text-cyber-muted leading-relaxed line-clamp-2">
                {nodeData.description}
              </p>
            )}
          </div>

          {/* Progress bar when running */}
          {isRunning && (
            <motion.div className="mt-2 h-0.5 rounded-full overflow-hidden bg-white/[0.06]">
              <motion.div
                className="h-full rounded-full"
                style={{
                  background: `linear-gradient(90deg, transparent, ${config.color})`,
                }}
                animate={{ x: ["-100%", "100%"] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
              />
            </motion.div>
          )}
        </div>
      </div>

      {/* React Flow Handles */}
      {nodeData.agentType !== "input" && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: config.color,
            border: `2px solid #0b1025`,
            left: -5,
          }}
        />
      )}
      {nodeData.agentType !== "output" && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            background: config.color,
            border: `2px solid #0b1025`,
            right: -5,
          }}
        />
      )}
    </motion.div>
  );
});

export default AgentNode;

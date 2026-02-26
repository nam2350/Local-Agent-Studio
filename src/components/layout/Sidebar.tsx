"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutGrid,
  GitBranch,
  Code2,
  FlaskConical,
  Layers,
  ShieldCheck,
  Sparkles,
  MessageSquare,
  Settings,
  Activity,
  BookOpen,
  ChevronDown,
  Plus,
  Cpu,
  Wifi,
  WifiOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePipeline } from "@/context/PipelineContext";

const navItems = [
  { id: "canvas",   icon: LayoutGrid, label: "Canvas" },
  { id: "monitor",  icon: Activity,   label: "Monitor" },
  { id: "models",   icon: BookOpen,   label: "Models" },
  { id: "settings", icon: Settings,   label: "Settings" },
];

type AgentTemplate = {
  id: string;
  label: string;
  model: string;
  type: string;
  icon: React.FC<{ size?: number; className?: string; style?: React.CSSProperties }>;
  color: string;
  description: string;
  vram: string;
};

const agentTemplates: AgentTemplate[] = [
  {
    id: "router",
    label: "Router",
    model: "Qwen2.5-3B-Instruct",
    type: "router",
    icon: GitBranch,
    color: "#22d3ee",
    description: "Classifies and routes tasks",
    vram: "~2.5 GB",
  },
  {
    id: "coder",
    label: "Code Writer",
    model: "Qwen2.5-Coder-7B",
    type: "coder",
    icon: Code2,
    color: "#a855f7",
    description: "Code generation & review",
    vram: "~5.2 GB",
  },
  {
    id: "analyzer",
    label: "Analyzer",
    model: "Gemma-3-4B-IT",
    type: "analyzer",
    icon: FlaskConical,
    color: "#f472b6",
    description: "Deep analysis & reasoning",
    vram: "~3.1 GB",
  },
  {
    id: "synthesizer",
    label: "Synthesizer",
    model: "Llama-3.1-8B-Instruct",
    type: "synthesizer",
    icon: Layers,
    color: "#10b981",
    description: "Merges & summarizes results",
    vram: "~6.0 GB",
  },
  {
    id: "validator",
    label: "Validator",
    model: "Phi-4-mini-4B",
    type: "validator",
    icon: ShieldCheck,
    color: "#f59e0b",
    description: "Quality checks & validation",
    vram: "~3.4 GB",
  },
  {
    id: "input",
    label: "User Input",
    model: "user-query",
    type: "input",
    icon: MessageSquare,
    color: "#3b82f6",
    description: "Entry point for user tasks",
    vram: "—",
  },
  {
    id: "output",
    label: "Output",
    model: "result-stream",
    type: "output",
    icon: Sparkles,
    color: "#10b981",
    description: "Final response output",
    vram: "—",
  },
];

function AgentCard({ agent }: { agent: AgentTemplate }) {
  const Icon = agent.icon;

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData(
      "application/agentTemplate",
      JSON.stringify({ label: agent.label, model: agent.model, type: agent.type })
    );
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <motion.div whileHover={{ scale: 1.02, y: -1 }} whileTap={{ scale: 0.98 }}>
      <div
        className="group cursor-grab active:cursor-grabbing rounded-lg p-2.5 transition-all duration-200"
        style={{
          background: `${agent.color}08`,
          border: `1px solid ${agent.color}20`,
        }}
        draggable
        onDragStart={handleDragStart}
      >
      <div className="flex items-center gap-2">
        <div
          className="flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0"
          style={{ background: `${agent.color}15`, border: `1px solid ${agent.color}25` }}
        >
          <Icon size={13} style={{ color: agent.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-cyber-text leading-none mb-0.5 truncate">
            {agent.label}
          </p>
          <p className="text-[10px] text-cyber-muted truncate font-mono">
            {agent.model}
          </p>
        </div>
        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          <Plus size={12} className="text-cyber-muted" />
        </div>
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <p className="text-[9px] text-cyber-subtle">{agent.description}</p>
        <span
          className="text-[9px] font-mono px-1.5 py-0.5 rounded"
          style={{ color: agent.color, background: `${agent.color}15` }}
        >
          {agent.vram}
        </span>
      </div>
      </div>
    </motion.div>
  );
}

// ─── Provider status indicator ────────────────────────────────────────────────

function ProviderBadge({ label, online }: { label: string; online: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {online
        ? <Wifi size={9} className="text-cyber-green" />
        : <WifiOff size={9} className="text-cyber-muted" />
      }
      <span
        className="text-[9px] font-mono"
        style={{ color: online ? "#10b981" : "#64748b" }}
      >
        {label}
      </span>
    </div>
  );
}

export default function Sidebar() {
  const [activeNav, setActiveNav] = useState("canvas");
  const [expanded, setExpanded] = useState(true);
  const { providerStatus } = usePipeline();

  const anyOnline = Object.values(providerStatus).some(Boolean);

  return (
    <motion.aside
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="flex flex-col h-full w-full"
      style={{
        background: "rgba(7, 10, 22, 0.95)",
        borderRight: "1px solid rgba(34, 211, 238, 0.08)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/[0.04]">
        <div
          className="flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0"
          style={{
            background: "linear-gradient(135deg, #22d3ee20, #a855f720)",
            border: "1px solid rgba(34, 211, 238, 0.25)",
          }}
        >
          <Cpu size={16} className="text-cyber-cyan" />
        </div>
        <div>
          <p className="text-sm font-bold text-cyber-text leading-none tracking-tight">
            Agent Studio
          </p>
          <p className="text-[10px] text-cyber-muted mt-0.5">Local Swarm v0.2</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-2 pt-3 pb-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeNav === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveNav(item.id)}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg mb-0.5 text-left transition-all duration-150",
                isActive
                  ? "bg-cyber-cyan/10 text-cyber-cyan border-l-2 border-cyber-cyan"
                  : "text-cyber-muted hover:bg-white/[0.03] hover:text-cyber-text border-l-2 border-transparent"
              )}
            >
              <Icon size={15} />
              <span className="text-xs font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="h-px bg-white/[0.04] mx-4" />

      {/* Agent Library */}
      <div className="flex-1 overflow-y-auto px-2 py-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-2 py-1.5 mb-2 text-left"
        >
          <span className="text-[10px] font-semibold text-cyber-muted uppercase tracking-widest">
            Agent Library
          </span>
          <motion.div animate={{ rotate: expanded ? 0 : -90 }} transition={{ duration: 0.15 }}>
            <ChevronDown size={12} className="text-cyber-muted" />
          </motion.div>
        </button>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {/* Drag hint */}
              <p className="text-[9px] text-cyber-subtle text-center mb-2 px-1">
                Drag agents onto the canvas
              </p>

              <div className="flex flex-col gap-1.5">
                {agentTemplates.map((agent, i) => (
                  <motion.div
                    key={agent.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.2 }}
                  >
                    <AgentCard agent={agent} />
                  </motion.div>
                ))}
              </div>

              {/* Total VRAM estimate */}
              <div
                className="mt-3 mx-1 p-2.5 rounded-lg"
                style={{
                  background: "rgba(34, 211, 238, 0.04)",
                  border: "1px solid rgba(34, 211, 238, 0.1)",
                }}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-cyber-muted">Est. VRAM (all)</span>
                  <span className="text-[10px] font-mono text-cyber-cyan">~20.2 GB</span>
                </div>
                <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background: "linear-gradient(90deg, #22d3ee, #a855f7)",
                      width: "63%",
                    }}
                    initial={{ scaleX: 0, originX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: 0.4, duration: 0.6, ease: "easeOut" }}
                  />
                </div>
                <p className="text-[9px] text-cyber-subtle mt-1">16 GB GPU · partial offload</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Provider status strip */}
      <div
        className="px-3 py-2.5 border-t border-white/[0.04]"
        style={{ background: "rgba(0,0,0,0.2)" }}
      >
        <p className="text-[9px] text-cyber-subtle uppercase tracking-widest mb-1.5">Providers</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <ProviderBadge label="Ollama"   online={providerStatus.ollama} />
          <ProviderBadge label="LM Studio" online={providerStatus.lmstudio} />
          <ProviderBadge label="llama.cpp" online={providerStatus.llamacpp} />
          <ProviderBadge label="HF Trans." online={providerStatus.transformers} />
        </div>
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/[0.04]">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: anyOnline ? "#22d3ee" : "#334155" }}
          />
          <span className="text-[10px] text-cyber-muted">
            {anyOnline ? "Backend online" : "Backend offline"}
          </span>
          <span className="ml-auto text-[10px] font-mono text-cyber-subtle">:8000</span>
        </div>
      </div>
    </motion.aside>
  );
}

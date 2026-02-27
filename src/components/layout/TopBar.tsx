"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play,
  Square,
  RotateCcw,
  Zap,
  ChevronDown,
  FolderOpen,
  Save,
  Terminal,
  CheckCircle2,
  AlertCircle,
  Send,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePipeline, type ProviderType } from "@/context/PipelineContext";
import SavePipelineModal from "@/components/modals/SavePipelineModal";
import LoadPipelineModal from "@/components/modals/LoadPipelineModal";

const pipelineTemplates = [
  "Build a user authentication REST API with JWT tokens",
  "Create a React component with form validation",
  "Analyze and optimize a slow SQL query",
  "Write unit tests for a payment processing module",
  "Design a microservices architecture for e-commerce",
];

const PROVIDERS: { value: ProviderType; label: string; color: string }[] = [
  { value: "simulation", label: "Simulation", color: "#64748b" },
  { value: "ollama",     label: "Ollama",     color: "#22d3ee" },
  { value: "lmstudio",  label: "LM Studio",  color: "#a855f7" },
  { value: "llamacpp",  label: "llama.cpp",  color: "#f59e0b" },
  { value: "transformers", label: "HF Transformers", color: "#10b981" },
];

export default function TopBar() {
  const {
    status, prompt, setPrompt,
    run, stop, reset,
    totalTokens, totalMs, error,
    useRealModels, setUseRealModels,
    providerType, setProviderType,
    providerStatus,
  } = usePipeline();

  const [showTemplates, setShowTemplates] = useState(false);
  const [showProviders, setShowProviders] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showLoadModal, setShowLoadModal] = useState(false);

  const isRunning = status === "running";
  const isDone    = status === "done";
  const isStopped = status === "stopped";

  const currentProvider = PROVIDERS.find((p) => p.value === providerType) ?? PROVIDERS[0];
  const isProviderOnline =
    providerType === "simulation" ? true :
    providerType === "transformers" ? providerStatus.transformers :
    providerStatus[providerType as keyof typeof providerStatus] ?? false;

  return (
    <motion.header
      initial={{ y: -10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="flex items-center gap-3 px-4 h-full"
      style={{
        background: "rgba(5, 8, 20, 0.98)",
        borderBottom: "1px solid rgba(34, 211, 238, 0.08)",
      }}
    >
      {/* Logo / pipeline name */}
      <div className="relative flex-shrink-0">
        <button
          onClick={() => { setShowTemplates(!showTemplates); setShowProviders(false); }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-150 hover:bg-white/[0.04]"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <Zap size={13} className="text-cyber-cyan" />
          <span className="text-sm font-semibold text-cyber-text">Agent Studio</span>
          <ChevronDown size={12} className="text-cyber-muted" />
        </button>

        <AnimatePresence>
          {showTemplates && (
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.97 }}
              transition={{ duration: 0.12 }}
              className="absolute top-full left-0 mt-1 w-72 rounded-xl overflow-hidden z-50"
              style={{
                background: "rgba(7, 10, 22, 0.98)",
                border: "1px solid rgba(34, 211, 238, 0.12)",
                boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
              }}
            >
              <div className="p-1">
                <p className="text-[10px] text-cyber-muted uppercase tracking-widest px-3 py-1.5">
                  Example Tasks
                </p>
                {pipelineTemplates.map((tmpl) => (
                  <button
                    key={tmpl}
                    onClick={() => { setPrompt(tmpl); setShowTemplates(false); }}
                    className="w-full text-left px-3 py-2 rounded-lg text-xs text-cyber-text hover:bg-cyber-cyan/10 hover:text-cyber-cyan transition-colors duration-100"
                  >
                    {tmpl}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-white/[0.08] flex-shrink-0" />

      {/* Prompt input */}
      <div className="flex-1 relative min-w-0">
        {editingPrompt ? (
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onBlur={() => setEditingPrompt(false)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setEditingPrompt(false); if (!isRunning) run(); }
                if (e.key === "Escape") setEditingPrompt(false);
              }}
              className="flex-1 bg-transparent text-sm text-cyber-text outline-none placeholder-cyber-muted font-mono"
              style={{ borderBottom: "1px solid rgba(34, 211, 238, 0.3)", paddingBottom: "2px" }}
              placeholder="Describe the task for your agent pipeline..."
            />
            <button
              onClick={() => { setEditingPrompt(false); if (!isRunning) run(); }}
              className="flex-shrink-0 text-cyber-cyan hover:text-white transition-colors"
            >
              <Send size={13} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => !isRunning && setEditingPrompt(true)}
            className="w-full text-left text-sm text-cyber-muted hover:text-cyber-text transition-colors truncate"
            style={{ cursor: isRunning ? "default" : "text" }}
            title={prompt}
          >
            <span className="text-cyber-subtle mr-1.5 font-mono text-xs">▸</span>
            {prompt}
          </button>
        )}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-white/[0.08] flex-shrink-0" />

      {/* Provider selector */}
      <div className="relative flex-shrink-0">
        <button
          onClick={() => { setShowProviders(!showProviders); setShowTemplates(false); }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all duration-150"
          style={{
            border: `1px solid ${currentProvider.color}40`,
            background: `${currentProvider.color}08`,
            color: currentProvider.color,
          }}
          title="Select inference provider"
        >
          <Cpu size={11} />
          <span className="font-medium">{currentProvider.label}</span>
          {providerType !== "simulation" && (
            <div
              className="w-1.5 h-1.5 rounded-full ml-0.5"
              style={{ background: isProviderOnline ? "#10b981" : "#ef4444" }}
              title={isProviderOnline ? "online" : "offline"}
            />
          )}
          <ChevronDown size={10} />
        </button>

        <AnimatePresence>
          {showProviders && (
            <motion.div
              initial={{ opacity: 0, y: -4, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.97 }}
              transition={{ duration: 0.12 }}
              className="absolute top-full right-0 mt-1 w-52 rounded-xl overflow-hidden z-50"
              style={{
                background: "rgba(7, 10, 22, 0.98)",
                border: "1px solid rgba(34, 211, 238, 0.12)",
                boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
              }}
            >
              <div className="p-1">
                <p className="text-[10px] text-cyber-muted uppercase tracking-widest px-3 py-1.5">
                  Inference Backend
                </p>
                {PROVIDERS.map((p) => {
                  const online =
                    p.value === "simulation" ? true :
                    p.value === "transformers" ? providerStatus.transformers :
                    providerStatus[p.value as keyof typeof providerStatus] ?? false;

                  return (
                    <button
                      key={p.value}
                      onClick={() => {
                        setProviderType(p.value);
                        setUseRealModels(p.value !== "simulation");
                        setShowProviders(false);
                      }}
                      className={cn(
                        "w-full text-left px-3 py-1.5 rounded-lg text-xs flex items-center gap-2 transition-colors duration-100",
                        providerType === p.value
                          ? "text-white"
                          : "text-cyber-muted hover:text-cyber-text"
                      )}
                      style={
                        providerType === p.value
                          ? { background: `${p.color}20`, color: p.color }
                          : {}
                      }
                    >
                      <div
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: online ? "#10b981" : "#334155" }}
                      />
                      <span className="flex-1">{p.label}</span>
                      {p.value !== "simulation" && !online && (
                        <span className="text-[9px] text-cyber-subtle">offline</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Pipeline controls */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <motion.button
          onClick={isRunning ? stop : run}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150"
          style={{
            background: isRunning ? "rgba(239, 68, 68, 0.12)" : "rgba(34, 211, 238, 0.12)",
            border: isRunning ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(34, 211, 238, 0.3)",
            color: isRunning ? "#ef4444" : "#22d3ee",
          }}
        >
          {isRunning ? <Square size={12} /> : <Play size={12} />}
          <span>{isRunning ? "Stop" : "Run"}</span>
        </motion.button>

        <motion.button
          onClick={reset}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          disabled={isRunning}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-cyber-muted hover:text-cyber-text disabled:opacity-30 transition-colors duration-150"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <RotateCcw size={12} />
        </motion.button>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-3 flex-shrink-0 min-w-[160px]">
        <AnimatePresence mode="wait">
          {isRunning && (
            <motion.div
              key="running"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              className="flex items-center gap-2"
            >
              <div className="flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="w-1 h-1 rounded-full bg-cyber-cyan"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: i * 0.2, ease: "easeInOut" }}
                  />
                ))}
              </div>
              <span className="text-xs text-cyber-cyan font-mono">
                {useRealModels ? `${currentProvider.label}` : "running"}
              </span>
            </motion.div>
          )}

          {isDone && (
            <motion.div
              key="done"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2"
            >
              <CheckCircle2 size={13} className="text-cyber-green" />
              <span className="text-xs text-cyber-green font-mono">
                {totalTokens.toLocaleString()} tok · {(totalMs / 1000).toFixed(1)}s
              </span>
            </motion.div>
          )}

          {(isStopped || error) && (
            <motion.div
              key="stopped"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-1.5"
            >
              <AlertCircle size={13} className="text-cyber-orange flex-shrink-0" />
              <span
                className="text-xs text-cyber-orange font-mono truncate max-w-[180px]"
                title={error ?? "Stopped"}
              >
                {error ? "backend offline" : "stopped"}
              </span>
            </motion.div>
          )}

          {status === "idle" && (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <span className="text-xs text-cyber-muted font-mono">idle · press Run ↵</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-cyber-muted hover:text-cyber-text transition-colors duration-150"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
          title="Terminal (coming soon)"
        >
          <Terminal size={12} />
        </button>
        <button
          onClick={() => setShowSaveModal(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-cyber-muted hover:text-cyber-cyan hover:border-cyber-cyan/30 transition-all duration-150"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
          title="Save Pipeline"
        >
          <Save size={12} />
        </button>
        <button
          onClick={() => setShowLoadModal(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-cyber-muted hover:text-cyber-purple hover:border-cyber-purple/30 transition-all duration-150"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
          title="Load Pipeline"
        >
          <FolderOpen size={12} />
        </button>
      </div>

      {/* Modals */}
      <SavePipelineModal open={showSaveModal} onClose={() => setShowSaveModal(false)} />
      <LoadPipelineModal open={showLoadModal} onClose={() => setShowLoadModal(false)} />
    </motion.header>
  );
}

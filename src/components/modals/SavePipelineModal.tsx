"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Save, X, Loader2, CheckCircle2 } from "lucide-react";
import { useCanvasBridge } from "@/context/CanvasBridgeContext";
import { usePipeline } from "@/context/PipelineContext";

const BACKEND = "http://localhost:8000";

interface SavePipelineModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SavePipelineModal({ open, onClose }: SavePipelineModalProps) {
  const { getStateRef } = useCanvasBridge();
  const { nodeConfigs } = usePipeline();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = useCallback(async () => {
    const trimmed = name.trim();
    if (!trimmed) return;

    const snapshot = getStateRef.current();
    if (!snapshot) { setError("Canvas not ready"); return; }

    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`${BACKEND}/api/pipelines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmed,
          description: description.trim(),
          nodes: snapshot.nodes,
          edges: snapshot.edges,
          node_configs: nodeConfigs,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      setTimeout(() => {
        setSaved(false);
        setName("");
        setDescription("");
        onClose();
      }, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [name, description, getStateRef, nodeConfigs, onClose]);

  const handleClose = () => {
    if (saving) return;
    setName("");
    setDescription("");
    setError(null);
    setSaved(false);
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50"
            style={{ background: "rgba(0,0,0,0.7)" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
          />

          {/* Modal */}
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <div
              className="pointer-events-auto w-[380px] rounded-2xl p-5"
              style={{
                background: "rgba(7, 10, 22, 0.98)",
                border: "1px solid rgba(34, 211, 238, 0.15)",
                boxShadow: "0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px rgba(34,211,238,0.05)",
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.2)" }}
                  >
                    <Save size={13} className="text-cyber-cyan" />
                  </div>
                  <span className="text-sm font-semibold text-cyber-text">Save Pipeline</span>
                </div>
                <button onClick={handleClose} className="text-cyber-muted hover:text-cyber-text transition-colors">
                  <X size={15} />
                </button>
              </div>

              {/* Fields */}
              <div className="flex flex-col gap-3">
                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    Name <span className="text-cyber-red">*</span>
                  </label>
                  <input
                    autoFocus
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") handleClose(); }}
                    placeholder="My Agent Pipeline"
                    maxLength={64}
                    className="w-full bg-black/30 rounded-lg px-3 py-2 text-sm text-cyber-text placeholder-cyber-subtle outline-none transition-colors"
                    style={{ border: "1px solid rgba(255,255,255,0.08)", }}
                    onFocus={(e) => (e.target.style.borderColor = "rgba(34,211,238,0.3)")}
                    onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.08)")}
                  />
                </div>

                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    Description
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Optional description..."
                    maxLength={200}
                    rows={2}
                    className="w-full bg-black/30 rounded-lg px-3 py-2 text-sm text-cyber-text placeholder-cyber-subtle outline-none resize-none transition-colors"
                    style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                    onFocus={(e) => (e.target.style.borderColor = "rgba(34,211,238,0.3)")}
                    onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.08)")}
                  />
                </div>

                {error && (
                  <p className="text-[11px] text-cyber-red font-mono">{error}</p>
                )}
              </div>

              {/* Footer */}
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={handleClose}
                  disabled={saving}
                  className="px-4 py-2 rounded-lg text-xs text-cyber-muted hover:text-cyber-text transition-colors disabled:opacity-40"
                  style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  Cancel
                </button>
                <motion.button
                  onClick={handleSave}
                  disabled={!name.trim() || saving || saved}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    background: saved ? "rgba(16,185,129,0.15)" : "rgba(34,211,238,0.12)",
                    border: saved ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(34,211,238,0.3)",
                    color: saved ? "#10b981" : "#22d3ee",
                  }}
                >
                  {saving ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : saved ? (
                    <CheckCircle2 size={11} />
                  ) : (
                    <Save size={11} />
                  )}
                  {saving ? "Saving…" : saved ? "Saved!" : "Save"}
                </motion.button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

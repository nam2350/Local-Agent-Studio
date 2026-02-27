"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FolderOpen, X, Loader2, Trash2, Clock, ChevronRight } from "lucide-react";
import { useCanvasBridge } from "@/context/CanvasBridgeContext";
import { usePipeline } from "@/context/PipelineContext";
import type { Edge, Node } from "@xyflow/react";

const BACKEND = "http://localhost:8000";

interface PipelineItem {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

interface LoadPipelineModalProps {
  open: boolean;
  onClose: () => void;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr + "Z").getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function LoadPipelineModal({ open, onClose }: LoadPipelineModalProps) {
  const { setStateRef } = useCanvasBridge();
  const { resetNodeConfig, setNodeConfig } = usePipeline();
  const [pipelines, setPipelines] = useState<PipelineItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchPipelines = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND}/api/pipelines`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPipelines(data.pipelines ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchPipelines();
  }, [open, fetchPipelines]);

  const handleLoad = useCallback(async (id: number) => {
    setLoadingId(id);
    setError(null);
    try {
      const res = await fetch(`${BACKEND}/api/pipelines/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Apply canvas state
      setStateRef.current(data.nodes as Node[], data.edges as Edge[]);

      // Apply node configs
      const configs = data.node_configs as Record<string, unknown>;
      Object.entries(configs).forEach(([nodeId]) => {
        resetNodeConfig(nodeId);
      });
      Object.entries(configs).forEach(([nodeId, cfg]) => {
        setNodeConfig(nodeId, cfg as Parameters<typeof setNodeConfig>[1]);
      });

      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoadingId(null);
    }
  }, [setStateRef, resetNodeConfig, setNodeConfig, onClose]);

  const handleDelete = useCallback(async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(id);
    try {
      await fetch(`${BACKEND}/api/pipelines/${id}`, { method: "DELETE" });
      setPipelines((prev) => prev.filter((p) => p.id !== id));
    } catch {
      // silent
    } finally {
      setDeletingId(null);
    }
  }, []);

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
            onClick={onClose}
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
              className="pointer-events-auto w-[440px] rounded-2xl p-5"
              style={{
                background: "rgba(7, 10, 22, 0.98)",
                border: "1px solid rgba(168, 85, 247, 0.15)",
                boxShadow: "0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px rgba(168,85,247,0.05)",
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: "rgba(168,85,247,0.1)", border: "1px solid rgba(168,85,247,0.2)" }}
                  >
                    <FolderOpen size={13} className="text-cyber-purple" />
                  </div>
                  <span className="text-sm font-semibold text-cyber-text">Load Pipeline</span>
                </div>
                <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text transition-colors">
                  <X size={15} />
                </button>
              </div>

              {/* Content */}
              <div className="min-h-[160px] max-h-[360px] overflow-y-auto flex flex-col gap-1.5">
                {loading ? (
                  <div className="flex items-center justify-center py-10">
                    <Loader2 size={18} className="animate-spin text-cyber-muted" />
                  </div>
                ) : error ? (
                  <div className="text-center py-6">
                    <p className="text-xs text-cyber-red font-mono">{error}</p>
                    <button
                      onClick={fetchPipelines}
                      className="mt-2 text-[10px] text-cyber-muted hover:text-cyber-text transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                ) : pipelines.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-2">
                    <FolderOpen size={24} className="text-cyber-subtle" />
                    <p className="text-xs text-cyber-subtle">No saved pipelines yet</p>
                    <p className="text-[10px] text-cyber-subtle">Use the Save button to save your current pipeline</p>
                  </div>
                ) : (
                  pipelines.map((p) => (
                    <motion.button
                      key={p.id}
                      onClick={() => handleLoad(p.id)}
                      disabled={loadingId !== null || deletingId !== null}
                      whileHover={{ x: 2 }}
                      className="w-full flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-left transition-all disabled:opacity-60 group"
                      style={{
                        background: "rgba(168,85,247,0.04)",
                        border: "1px solid rgba(168,85,247,0.1)",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "rgba(168,85,247,0.09)";
                        (e.currentTarget as HTMLElement).style.borderColor = "rgba(168,85,247,0.25)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "rgba(168,85,247,0.04)";
                        (e.currentTarget as HTMLElement).style.borderColor = "rgba(168,85,247,0.1)";
                      }}
                    >
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-cyber-text truncate">{p.name}</p>
                        {p.description && (
                          <p className="text-[10px] text-cyber-muted truncate mt-0.5">{p.description}</p>
                        )}
                        <div className="flex items-center gap-1 mt-1">
                          <Clock size={8} className="text-cyber-subtle" />
                          <span className="text-[9px] text-cyber-subtle font-mono">
                            {timeAgo(p.updated_at)}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {loadingId === p.id ? (
                          <Loader2 size={13} className="animate-spin text-cyber-purple" />
                        ) : (
                          <ChevronRight size={13} className="text-cyber-subtle group-hover:text-cyber-purple transition-colors" />
                        )}
                        <button
                          onClick={(e) => handleDelete(p.id, e)}
                          disabled={deletingId === p.id}
                          className="w-6 h-6 flex items-center justify-center rounded text-cyber-subtle hover:text-cyber-red transition-colors opacity-0 group-hover:opacity-100"
                          title="Delete"
                        >
                          {deletingId === p.id
                            ? <Loader2 size={10} className="animate-spin" />
                            : <Trash2 size={10} />
                          }
                        </button>
                      </div>
                    </motion.button>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="flex justify-end mt-4">
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg text-xs text-cyber-muted hover:text-cyber-text transition-colors"
                  style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  Close
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

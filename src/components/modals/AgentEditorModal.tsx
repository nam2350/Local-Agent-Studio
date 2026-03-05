"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, X, Loader2, CheckCircle2, Trash2, ChevronDown } from "lucide-react";
import { usePipeline } from "@/context/PipelineContext";

const BACKEND = "http://localhost:8000";

export type AgentRecord = {
  id: string;
  name: string;
  role: string;
  provider_type: string;
  model_id: string;
  system_prompt: string;
  max_tokens: number;
  temperature: number;
};

const ROLES = ["router", "coder", "analyzer", "validator", "synthesizer", "vision", "assistant"];
const PROVIDERS = ["transformers", "ollama", "lmstudio", "llamacpp", "simulation"];

const EMPTY_FORM: AgentRecord = {
  id: "",
  name: "",
  role: "assistant",
  provider_type: "transformers",
  model_id: "",
  system_prompt: "",
  max_tokens: 512,
  temperature: 0.7,
};

interface Props {
  open: boolean;
  onClose: () => void;
  agent?: AgentRecord;
  onSaved: () => void;
}

export default function AgentEditorModal({ open, onClose, agent, onSaved }: Props) {
  const isEdit = !!agent;
  const [form, setForm] = useState<AgentRecord>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { availableModels } = usePipeline();

  const dynamicModelOptions: string[] = useMemo(() => {
    const pType = form.provider_type as keyof typeof availableModels;
    return Array.isArray(availableModels[pType]) ? availableModels[pType] : [];
  }, [form.provider_type, availableModels]);

  // 모달이 열릴 때 폼 초기화
  useEffect(() => {
    if (open) {
      setForm(agent ? { ...agent } : { ...EMPTY_FORM });
      setSaved(false);
      setError(null);
    }
  }, [open, agent]);

  const set = (key: keyof AgentRecord, value: string | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = useCallback(async () => {
    if (!form.id.trim() || !form.name.trim() || !form.model_id.trim()) {
      setError("ID, 이름, 모델 ID는 필수입니다.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const url = isEdit
        ? `${BACKEND}/api/registry/agents/${form.id}`
        : `${BACKEND}/api/registry/agents`;
      const method = isEdit ? "PUT" : "POST";
      const body = isEdit
        ? {
          name: form.name, role: form.role, provider_type: form.provider_type,
          model_id: form.model_id, system_prompt: form.system_prompt,
          max_tokens: form.max_tokens, temperature: form.temperature,
        }
        : form;

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `HTTP ${res.status}`);
      }
      setSaved(true);
      setTimeout(() => {
        setSaved(false);
        onSaved();
        onClose();
      }, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }, [form, isEdit, onSaved, onClose]);

  const handleDelete = useCallback(async () => {
    if (!agent) return;
    if (!window.confirm(`"${agent.name}" 에이전트를 삭제하시겠습니까?`)) return;

    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND}/api/registry/agents/${agent.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
      setSaving(false);
    }
  }, [agent, onSaved, onClose]);

  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  const inputCls =
    "w-full bg-black/30 rounded-lg px-3 py-2 text-sm text-cyber-text placeholder-cyber-subtle outline-none transition-colors";
  const inputStyle = { border: "1px solid rgba(255,255,255,0.08)" };
  const focusHandler = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    (e.target.style.borderColor = "rgba(34,211,238,0.3)");
  const blurHandler = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    (e.target.style.borderColor = "rgba(255,255,255,0.08)");

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50"
            style={{ background: "rgba(0,0,0,0.75)" }}
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
              className="pointer-events-auto w-[480px] max-h-[90vh] overflow-y-auto rounded-2xl p-5"
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
                    <Bot size={13} color="#a855f7" />
                  </div>
                  <span className="text-sm font-semibold text-cyber-text">
                    {isEdit ? "에이전트 편집" : "에이전트 추가"}
                  </span>
                </div>
                <button onClick={handleClose} className="text-cyber-muted hover:text-cyber-text transition-colors">
                  <X size={15} />
                </button>
              </div>

              {/* Fields */}
              <div className="flex flex-col gap-3">
                {/* ID */}
                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    Agent ID <span className="text-cyber-red">*</span>
                    {isEdit && <span className="ml-1 text-cyber-subtle">(수정 불가)</span>}
                  </label>
                  <input
                    autoFocus={!isEdit}
                    value={form.id}
                    onChange={(e) => set("id", e.target.value)}
                    disabled={isEdit}
                    placeholder="my-agent-1"
                    maxLength={64}
                    className={inputCls}
                    style={{
                      ...inputStyle,
                      opacity: isEdit ? 0.5 : 1,
                      background: isEdit ? "rgba(0,0,0,0.5)" : undefined,
                    }}
                    onFocus={focusHandler}
                    onBlur={blurHandler}
                  />
                </div>

                {/* Name */}
                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    이름 <span className="text-cyber-red">*</span>
                  </label>
                  <input
                    autoFocus={isEdit}
                    value={form.name}
                    onChange={(e) => set("name", e.target.value)}
                    placeholder="My Custom Agent"
                    maxLength={64}
                    className={inputCls}
                    style={inputStyle}
                    onFocus={focusHandler}
                    onBlur={blurHandler}
                  />
                </div>

                {/* Role + Provider */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                      Role
                    </label>
                    <select
                      value={form.role}
                      onChange={(e) => set("role", e.target.value)}
                      className={inputCls}
                      style={{ ...inputStyle, cursor: "pointer" }}
                      onFocus={focusHandler}
                      onBlur={blurHandler}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r} style={{ background: "#0b1025" }}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                      Provider
                    </label>
                    <select
                      value={form.provider_type}
                      onChange={(e) => set("provider_type", e.target.value)}
                      className={inputCls}
                      style={{ ...inputStyle, cursor: "pointer" }}
                      onFocus={focusHandler}
                      onBlur={blurHandler}
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p} value={p} style={{ background: "#0b1025" }}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Model ID */}
                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    Model ID <span className="text-cyber-red">*</span>
                  </label>
                  {dynamicModelOptions.length > 0 ? (
                    <div className="relative">
                      <select
                        value={form.model_id}
                        onChange={(e) => set("model_id", e.target.value)}
                        className={inputCls}
                        style={{ ...inputStyle, cursor: "pointer", appearance: "none" }}
                        onFocus={focusHandler}
                        onBlur={blurHandler}
                      >
                        <option value="" disabled style={{ background: "#0b1025" }}>
                          모델을 선택하세요...
                        </option>
                        {dynamicModelOptions.map((m) => (
                          <option key={m} value={m} style={{ background: "#0b1025" }}>
                            {m}
                          </option>
                        ))}
                      </select>
                      <ChevronDown
                        size={11}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted pointer-events-none"
                      />
                    </div>
                  ) : (
                    <input
                      value={form.model_id}
                      onChange={(e) => set("model_id", e.target.value)}
                      placeholder="예: Qwen/Qwen3.5-4B, llama3.2:3b"
                      className={inputCls}
                      style={inputStyle}
                      onFocus={focusHandler}
                      onBlur={blurHandler}
                    />
                  )}
                </div>

                {/* System Prompt */}
                <div>
                  <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                    System Prompt
                  </label>
                  <textarea
                    value={form.system_prompt}
                    onChange={(e) => set("system_prompt", e.target.value)}
                    placeholder="에이전트 역할과 지시사항을 입력하세요..."
                    rows={4}
                    className="w-full bg-black/30 rounded-lg px-3 py-2 text-sm text-cyber-text placeholder-cyber-subtle outline-none resize-none transition-colors"
                    style={inputStyle}
                    onFocus={focusHandler}
                    onBlur={blurHandler}
                  />
                </div>

                {/* Max Tokens + Temperature */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                      Max Tokens
                    </label>
                    <input
                      type="number"
                      value={form.max_tokens}
                      onChange={(e) => set("max_tokens", parseInt(e.target.value) || 256)}
                      min={64}
                      max={8192}
                      step={256}
                      className={inputCls}
                      style={inputStyle}
                      onFocus={focusHandler}
                      onBlur={blurHandler}
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-cyber-muted uppercase tracking-wider mb-1.5 block">
                      Temperature
                      <span className="ml-1 text-cyber-cyan">{form.temperature.toFixed(1)}</span>
                    </label>
                    <input
                      type="range"
                      value={form.temperature}
                      onChange={(e) => set("temperature", parseFloat(e.target.value))}
                      min={0}
                      max={1}
                      step={0.1}
                      className="w-full h-2 rounded-lg appearance-none cursor-pointer"
                      style={{ accentColor: "#22d3ee", marginTop: "10px" }}
                    />
                  </div>
                </div>

                {error && (
                  <p className="text-[11px] text-cyber-red font-mono">{error}</p>
                )}
              </div>

              {/* Footer */}
              <div className="flex justify-between gap-2 mt-4">
                {/* 삭제 버튼 (편집 시에만) */}
                <div>
                  {isEdit && (
                    <motion.button
                      onClick={handleDelete}
                      disabled={saving}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40"
                      style={{
                        background: "rgba(239,68,68,0.08)",
                        border: "1px solid rgba(239,68,68,0.25)",
                        color: "#ef4444",
                      }}
                    >
                      <Trash2 size={11} />
                      삭제
                    </motion.button>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleClose}
                    disabled={saving}
                    className="px-4 py-2 rounded-lg text-xs text-cyber-muted hover:text-cyber-text transition-colors disabled:opacity-40"
                    style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    취소
                  </button>
                  <motion.button
                    onClick={handleSave}
                    disabled={saving || saved}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    style={{
                      background: saved ? "rgba(16,185,129,0.15)" : "rgba(168,85,247,0.12)",
                      border: saved ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(168,85,247,0.3)",
                      color: saved ? "#10b981" : "#a855f7",
                    }}
                  >
                    {saving ? (
                      <Loader2 size={11} className="animate-spin" />
                    ) : saved ? (
                      <CheckCircle2 size={11} />
                    ) : null}
                    {saving ? "저장 중…" : saved ? "저장됨!" : isEdit ? "저장" : "추가"}
                  </motion.button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

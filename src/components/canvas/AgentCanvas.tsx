"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  BackgroundVariant,
  type Connection,
  type Edge,
  type Node,
  type NodeMouseHandler,
  MarkerType,
  ReactFlowProvider,
} from "@xyflow/react";
import { motion } from "framer-motion";
import { usePipeline } from "@/context/PipelineContext";
import AgentNode, { type AgentNodeData } from "./AgentNode";
import type { AgentType } from "@/constants/agentDefaults";

const nodeTypes = { agentNode: AgentNode };

type AgentFlowNode = Node<AgentNodeData>;

// ─── Edge color map ───────────────────────────────────────────────────────────

const EDGE_COLORS: Record<string, string> = {
  "e-input-router":    "#22d3ee",
  "e-router-coder":    "#a855f7",
  "e-router-analyzer": "#f472b6",
  "e-coder-validator": "#f59e0b",
  "e-coder-synth":     "#22d3ee",
  "e-analyzer-synth":  "#22d3ee",
  "e-validator-synth": "#10b981",
};

const edgeBase = (color: string, id: string, source: string, target: string): Edge => ({
  id,
  source,
  target,
  animated: true,
  style: { strokeWidth: 1.5, stroke: `${color}55` },
  markerEnd: { type: MarkerType.ArrowClosed, color: `${color}88` },
  data: { baseColor: color },
});

const initialNodes: AgentFlowNode[] = [
  {
    id: "input-1",
    type: "agentNode",
    position: { x: 60, y: 240 },
    data: {
      label: "User Input",
      agentType: "input",
      model: "user-query",
      status: "idle",
      description: "Accepts user queries and task descriptions",
    },
  },
  {
    id: "router-1",
    type: "agentNode",
    position: { x: 340, y: 240 },
    data: { label: "Router", agentType: "router", model: "Qwen2.5-3B-Instruct", status: "idle", tokens: 0, tokensPerSec: 0 },
  },
  {
    id: "coder-1",
    type: "agentNode",
    position: { x: 620, y: 80 },
    data: { label: "Code Writer", agentType: "coder", model: "Qwen2.5-Coder-7B", status: "idle", tokens: 0, tokensPerSec: 0 },
  },
  {
    id: "analyzer-1",
    type: "agentNode",
    position: { x: 620, y: 400 },
    data: { label: "Analyzer", agentType: "analyzer", model: "Gemma-3-4B-IT", status: "idle", tokens: 0, tokensPerSec: 0 },
  },
  {
    id: "validator-1",
    type: "agentNode",
    position: { x: 900, y: 80 },
    data: { label: "Validator", agentType: "validator", model: "Phi-4-mini-4B", status: "idle", tokens: 0, tokensPerSec: 0 },
  },
  {
    id: "synthesizer-1",
    type: "agentNode",
    position: { x: 1160, y: 240 },
    data: { label: "Synthesizer", agentType: "synthesizer", model: "Llama-3.1-8B-Instruct", status: "idle", tokens: 0, tokensPerSec: 0 },
  },
];

const initialEdges: Edge[] = [
  edgeBase("#22d3ee", "e-input-router",    "input-1",   "router-1"),
  edgeBase("#a855f7", "e-router-coder",    "router-1",  "coder-1"),
  edgeBase("#f472b6", "e-router-analyzer", "router-1",  "analyzer-1"),
  edgeBase("#f59e0b", "e-coder-validator", "coder-1",   "validator-1"),
  edgeBase("#22d3ee", "e-coder-synth",     "coder-1",   "synthesizer-1"),
  edgeBase("#22d3ee", "e-analyzer-synth",  "analyzer-1","synthesizer-1"),
  edgeBase("#10b981", "e-validator-synth", "validator-1","synthesizer-1"),
];

// ─── Inner canvas (needs ReactFlowProvider context) ───────────────────────────

function CanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<AgentFlowNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { agentMetrics, status, setSelectedNode } = usePipeline();
  const { screenToFlowPosition } = useReactFlow();
  const nodeCounter = useRef(100);

  // ── Sync node data with pipeline metrics ──────────────────────────────────
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const m = agentMetrics[node.id];
        if (!m) return node;
        return {
          ...node,
          data: {
            ...node.data,
            status: m.status,
            tokens: m.tokens,
            tokensPerSec: Math.round(m.tokensPerSec),
            provider: m.provider,
          } as AgentNodeData,
        };
      })
    );
  }, [agentMetrics, setNodes]);

  // ── Reset input node status ────────────────────────────────────────────────
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id !== "input-1") return node;
        return {
          ...node,
          data: {
            ...node.data,
            status:
              status === "running" ? "done" : status === "idle" ? "idle" : node.data.status,
          } as AgentNodeData,
        };
      })
    );
  }, [status, setNodes]);

  // ── Edge glow animation when agents are active ────────────────────────────
  useEffect(() => {
    setEdges((eds) =>
      eds.map((edge) => {
        const baseColor = (edge.data as { baseColor?: string })?.baseColor ??
          EDGE_COLORS[edge.id] ?? "#22d3ee";

        const sourceDone    = agentMetrics[edge.source]?.status === "done";
        const sourceRunning = agentMetrics[edge.source]?.status === "running";
        const targetRunning = agentMetrics[edge.target]?.status === "running";

        const isGlowing = (sourceDone && targetRunning) || sourceRunning;

        return {
          ...edge,
          style: isGlowing
            ? {
                strokeWidth: 2.5,
                stroke: baseColor,
                filter: `drop-shadow(0 0 5px ${baseColor}) drop-shadow(0 0 10px ${baseColor}60)`,
              }
            : { strokeWidth: 1.5, stroke: `${baseColor}55` },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isGlowing ? baseColor : `${baseColor}88`,
          },
          animated: true,
        };
      })
    );
  }, [agentMetrics, setEdges]);

  // ── Node click → open config panel ───────────────────────────────────────
  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const data = node.data as AgentNodeData;
      setSelectedNode({
        id: node.id,
        label: data.label,
        agentType: data.agentType as AgentType,
      });
    },
    [setSelectedNode]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, [setSelectedNode]);

  // ── Connect nodes ──────────────────────────────────────────────────────────
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            animated: true,
            style: { strokeWidth: 1.5, stroke: "rgba(34,211,238,0.4)" },
            markerEnd: { type: MarkerType.ArrowClosed, color: "rgba(34,211,238,0.6)" },
            data: { baseColor: "#22d3ee" },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  // ── Drag-from-sidebar drop handler ────────────────────────────────────────
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData("application/agentTemplate");
      if (!raw) return;

      let template: { label: string; model: string; type: string };
      try {
        template = JSON.parse(raw);
      } catch {
        return;
      }

      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      const id = `${template.type}-${Date.now()}-${++nodeCounter.current}`;

      const newNode: AgentFlowNode = {
        id,
        type: "agentNode",
        position,
        data: {
          label: template.label,
          agentType: template.type as AgentNodeData["agentType"],
          model: template.model,
          status: "idle",
          tokens: 0,
          tokensPerSec: 0,
        },
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [screenToFlowPosition, setNodes]
  );

  const activeCount = Object.values(agentMetrics).filter(
    (m) => m.status === "running" || m.status === "done"
  ).length;

  return (
    <motion.div
      className="w-full h-full relative"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Overlay info */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 pointer-events-none">
        <div className="glass px-3 py-1.5 rounded-lg flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: status === "running" ? "#22d3ee" : "#334155",
              animation: status === "running" ? "pulse 1.5s ease-in-out infinite" : "none",
            }}
          />
          <span className="text-xs text-cyber-muted font-mono">
            {nodes.length} agents · {edges.length} links
            {activeCount > 0 && (
              <span className="text-cyber-cyan ml-1.5">· {activeCount} active</span>
            )}
          </span>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.25}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="rgba(34, 211, 238, 0.08)"
        />
        <Controls showInteractive={false} style={{ bottom: 16, left: 16 }} />
        <MiniMap nodeStrokeWidth={2} pannable zoomable style={{ bottom: 16, right: 16 }} />
      </ReactFlow>
    </motion.div>
  );
}

// ─── Exported component (wraps with ReactFlowProvider) ────────────────────────

export default function AgentCanvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

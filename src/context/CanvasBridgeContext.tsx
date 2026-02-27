"use client";

/**
 * CanvasBridgeContext
 * Provides a ref-based bridge so components outside ReactFlowProvider
 * (e.g. TopBar, Sidebar) can read and write the canvas nodes/edges.
 *
 * Usage in AgentCanvas (inside ReactFlowProvider):
 *   const { getStateRef, setStateRef } = useCanvasBridge();
 *   getStateRef.current = () => ({ nodes, edges });
 *   setStateRef.current = (n, e) => { setNodes(n); setEdges(e); };
 *
 * Usage in TopBar:
 *   const { getStateRef } = useCanvasBridge();
 *   const data = getStateRef.current(); // { nodes, edges } | null
 */

import { createContext, useContext, useRef, type MutableRefObject, type ReactNode } from "react";
import type { Edge, Node } from "@xyflow/react";

export type CanvasSnapshot = { nodes: Node[]; edges: Edge[] };

type CanvasBridgeContextValue = {
  getStateRef: MutableRefObject<() => CanvasSnapshot | null>;
  setStateRef:  MutableRefObject<(nodes: Node[], edges: Edge[]) => void>;
};

const CanvasBridgeContext = createContext<CanvasBridgeContextValue | null>(null);

export function CanvasBridgeProvider({ children }: { children: ReactNode }) {
  const getStateRef = useRef<() => CanvasSnapshot | null>(() => null);
  const setStateRef  = useRef<(nodes: Node[], edges: Edge[]) => void>(() => {});

  return (
    <CanvasBridgeContext.Provider value={{ getStateRef, setStateRef }}>
      {children}
    </CanvasBridgeContext.Provider>
  );
}

export function useCanvasBridge() {
  const ctx = useContext(CanvasBridgeContext);
  if (!ctx) throw new Error("useCanvasBridge must be used inside CanvasBridgeProvider");
  return ctx;
}

"use client";

/**
 * Phase 18: Canvas UX Polish
 * 파이프라인 실행 중 엣지를 따라 흐르는 파티클 애니메이션.
 * SVG animateMotion + mpath 로 베지어 경로를 따라 dot이 흐름.
 */
import { getBezierPath, BaseEdge, type EdgeProps } from "@xyflow/react";
import { usePipeline } from "@/context/PipelineContext";

// 파티클 시작 시간 오프셋 (초) — 3개 dot이 균등 간격으로 흐름
const PARTICLE_OFFSETS = [0, 0.6, 1.2];
const PARTICLE_DUR = "1.8s";

export default function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  source,
  target,
  data,
  style,
  markerEnd,
}: EdgeProps) {
  const { agentMetrics } = usePipeline();

  const sourceDone    = agentMetrics[source]?.status === "done";
  const sourceRunning = agentMetrics[source]?.status === "running";
  const targetRunning = agentMetrics[target]?.status === "running";
  const isActive = sourceRunning || (sourceDone && targetRunning);

  const [edgePath] = getBezierPath({
    sourceX, sourceY, targetX, targetY,
    sourcePosition, targetPosition,
  });

  const baseColor = (data as Record<string, string>)?.baseColor ?? "#22d3ee";
  const pathId = `anim-path-${id}`;

  return (
    <>
      {/* 파티클이 따라갈 숨겨진 경로 */}
      <path
        id={pathId}
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={0}
      />

      {/* 기본 엣지 선 */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={style}
        markerEnd={markerEnd}
      />

      {/* 활성 시 파티클 dots */}
      {isActive &&
        PARTICLE_OFFSETS.map((offset, i) => (
          <circle
            key={i}
            r={2.8}
            fill={baseColor}
            style={{
              filter: `drop-shadow(0 0 4px ${baseColor})`,
              opacity: 0.95,
            }}
          >
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {(
              <animateMotion
                dur={PARTICLE_DUR}
                repeatCount="indefinite"
                begin={`${offset}s`}
                calcMode="linear"
              >
                <mpath href={`#${pathId}`} />
              </animateMotion>
            ) as any}
          </circle>
        ))}
    </>
  );
}

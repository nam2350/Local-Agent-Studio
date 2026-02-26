"use client";

import dynamic from "next/dynamic";

const AgentCanvas = dynamic(
  () => import("./AgentCanvas"),
  { ssr: false }
);

export default function ClientCanvas() {
  return <AgentCanvas />;
}

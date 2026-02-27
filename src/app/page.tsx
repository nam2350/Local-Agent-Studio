import { PipelineProvider } from "@/context/PipelineContext";
import { CanvasBridgeProvider } from "@/context/CanvasBridgeContext";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import RightPanel from "@/components/layout/RightPanel";
import ClientCanvas from "@/components/canvas/ClientCanvas";

export default function Home() {
  return (
    <CanvasBridgeProvider>
    <PipelineProvider>
      <div
        className="flex flex-col w-screen h-screen overflow-hidden"
        style={{ background: "#050814" }}
      >
        {/* Top bar */}
        <div className="flex-shrink-0 h-[52px]">
          <TopBar />
        </div>

        {/* Main layout */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left sidebar */}
          <div className="flex-shrink-0 w-[260px] overflow-hidden">
            <Sidebar />
          </div>

          {/* Main canvas */}
          <main className="flex-1 relative overflow-hidden grid-bg">
            {/* Ambient glow top-left */}
            <div
              className="absolute -top-32 -left-32 w-96 h-96 rounded-full pointer-events-none"
              style={{
                background:
                  "radial-gradient(circle, rgba(34, 211, 238, 0.04) 0%, transparent 70%)",
              }}
            />
            {/* Ambient glow bottom-right */}
            <div
              className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full pointer-events-none"
              style={{
                background:
                  "radial-gradient(circle, rgba(168, 85, 247, 0.04) 0%, transparent 70%)",
              }}
            />
            <ClientCanvas />
          </main>

          {/* Right panel */}
          <div className="flex-shrink-0 w-[288px] overflow-hidden">
            <RightPanel />
          </div>
        </div>
      </div>
    </PipelineProvider>
    </CanvasBridgeProvider>
  );
}

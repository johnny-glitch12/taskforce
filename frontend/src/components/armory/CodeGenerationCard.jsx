/* eslint-disable react/prop-types */
/**
 * CodeGenerationCard — the "✅ Generated: BotName" card shown after a build.
 * No-code by default: the primary action opens the agent's preview/dashboard,
 * not the source. Code + Workflows actions appear only in developer mode.
 */
import { CheckCircle2, FileCode2, GitBranch, ArrowRight, LayoutDashboard } from "lucide-react";
import { useAuth } from "@/App";

export default function CodeGenerationCard({ name, files = [], nodes = [], durationMs, onViewFiles, onOpenInWorkflows }) {
  const { developerMode } = useAuth() || {};
  const fileList = files.slice(0, 5).map((f) => f.path).join(", ");
  const moreFiles = files.length > 5 ? ` +${files.length - 5} more` : "";
  return (
    <div
      data-testid="armory-codegen-card"
      className="rounded-sm overflow-hidden"
      style={{
        background: "var(--armory-build-card-bg)",
        borderLeft: "3px solid var(--armory-accent)",
        border: "1px solid var(--armory-border)",
        borderLeftWidth: 3,
      }}
    >
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-1.5">
          <CheckCircle2 size={14} style={{ color: "var(--armory-success)" }} />
          <span className="text-[10px] font-mono uppercase tracking-[0.18em]" style={{ color: "var(--armory-success)" }}>
            Generated
          </span>
        </div>
        <h3
          className="text-lg mb-2"
          style={{ color: "var(--armory-text)", fontFamily: "'Rajdhani', 'Space Grotesk', sans-serif", fontWeight: 500 }}
        >
          {name || "Untitled Bot"}
        </h3>
        {/* Build stats are developer detail — no-code users just see the result */}
        {developerMode && (
          <div className="flex items-center gap-3 text-[11px] font-mono mb-3" style={{ color: "var(--armory-text-mute)" }}>
            <span className="inline-flex items-center gap-1">
              <FileCode2 size={11} /> {files.length} files
            </span>
            <span className="inline-flex items-center gap-1">
              <GitBranch size={11} /> {nodes.length} nodes
            </span>
            {durationMs != null && (
              <span>· {(durationMs / 1000).toFixed(1)}s</span>
            )}
          </div>
        )}
        {developerMode && fileList && (
          <div className="text-[11px] font-mono mb-3 opacity-75" style={{ color: "var(--armory-text-mute)" }}>
            <span className="opacity-60">Files: </span>{fileList}{moreFiles}
          </div>
        )}
        <div className="flex gap-2">
          {onViewFiles && (
            <button
              data-testid="armory-codegen-view-files"
              onClick={onViewFiles}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
              style={{
                background: "var(--armory-accent)",
                color: "#0a0a0a",
                fontWeight: 600,
              }}
            >
              {developerMode ? <>View Code <ArrowRight size={10} /></> : <><LayoutDashboard size={11} /> Open Dashboard</>}
            </button>
          )}
          {developerMode && onOpenInWorkflows && (
            <button
              data-testid="armory-codegen-open-workflows"
              onClick={onOpenInWorkflows}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all hover:bg-white/5"
              style={{
                background: "transparent",
                color: "var(--armory-text)",
                border: "1px solid var(--armory-border)",
              }}
            >
              Open in Workflows <ArrowRight size={10} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

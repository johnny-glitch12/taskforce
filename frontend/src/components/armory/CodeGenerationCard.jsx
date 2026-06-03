/* eslint-disable react/prop-types */
/**
 * CodeGenerationCard — the special "✅ Generated: BotName" card shown after a build.
 */
import { CheckCircle2, FileCode2, GitBranch, ArrowRight } from "lucide-react";

export default function CodeGenerationCard({ name, files = [], nodes = [], durationMs, onViewFiles, onOpenInWorkflows }) {
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
        {fileList && (
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
              View Code <ArrowRight size={10} />
            </button>
          )}
          {onOpenInWorkflows && (
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

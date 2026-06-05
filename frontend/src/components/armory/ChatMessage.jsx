/* eslint-disable react/prop-types */
/**
 * ChatMessage — one row in the chat thread.
 * Renders user / assistant / error / code-generation / build-progress cards.
 *
 * Per-action credit costs are intentionally NOT displayed. The app uses a
 * dual-pool credit balance shown in the navbar + Credits page only.
 */
import { Bot, User, AlertCircle, CheckCircle2, Loader2, Circle, AlertTriangle, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import CodeGenerationCard from "./CodeGenerationCard";

const STAGE_LABELS = {
  architect: "Architect",
  planner: "Planner",
  builder: "Builder",
  reviewer: "Reviewer",
  polisher: "Polisher",
  ui_builder: "UI Builder",
};
const ALL_STAGES = ["architect", "planner", "builder", "reviewer", "polisher", "ui_builder"];

function StageChip({ stage, status, durationMs }) {
  const Icon = status === "done" ? CheckCircle2
    : status === "running" || status === "queued" ? Loader2
    : status === "failed" ? AlertTriangle
    : Circle;
  const color = status === "done" ? "#10b981"
    : status === "running" ? "var(--armory-accent)"
    : status === "failed" ? "#f43f5e"
    : status === "paused" ? "#fbbf24"
    : status === "skipped" ? "var(--armory-text-mute)"
    : "var(--armory-text-mute)";
  const opacity = status === "skipped" ? 0.4 : 1;
  return (
    <div
      data-testid={`stage-chip-${stage}`}
      data-status={status || "pending"}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-sm text-[10px] font-mono uppercase tracking-[0.1em]"
      style={{
        background: "var(--armory-card)",
        border: `1px solid ${status === "done" ? "rgba(16,185,129,0.3)" : "var(--armory-border)"}`,
        color,
        opacity,
      }}
    >
      <Icon size={10} className={status === "running" ? "animate-spin" : ""} />
      <span>{STAGE_LABELS[stage] || stage}</span>
      {status === "done" && durationMs != null && (
        <span className="opacity-60">{Math.round(durationMs / 100) / 10}s</span>
      )}
    </div>
  );
}

function BuildProgressCard({ msg, onResume }) {
  const progress = msg.progress || [];
  const byStage = Object.fromEntries(progress.map((p) => [p.stage, p]));
  const status = msg.status;

  return (
    <div
      data-testid="armory-msg-build-progress"
      className="px-4 py-3 rounded-sm"
      style={{
        background: "var(--armory-card)",
        border: "1px solid var(--armory-border)",
        borderLeft: status === "paused" ? "3px solid #fbbf24" : status === "failed" ? "3px solid #f43f5e" : "3px solid var(--armory-accent)",
      }}
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <Loader2 size={12} className={status === "queued" || status === "running" ? "animate-spin" : ""} style={{ color: "var(--armory-accent)" }} />
          <span className="text-[11px] font-mono uppercase tracking-[0.15em]" style={{ color: "var(--armory-accent)" }}>
            {status === "complete" ? "Build Complete" : status === "paused" ? "Build Paused" : status === "failed" ? "Build Failed" : "Building Agent"}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {ALL_STAGES.map((s) => {
          const entry = byStage[s];
          return (
            <StageChip
              key={s}
              stage={s}
              status={entry?.status}
              durationMs={entry?.duration_ms}
            />
          );
        })}
      </div>

      {status === "paused" && (
        <div data-testid="build-paused-banner" className="mt-3 px-3 py-2 rounded-sm text-[12px]" style={{ background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.3)" }}>
          <div className="flex items-center gap-2 text-amber-300 mb-1 font-mono text-[10px] uppercase tracking-[0.15em]">
            <AlertTriangle size={10} /> Out of credits at {msg.paused?.stage || "stage"}
          </div>
          <div className="text-[12px]" style={{ color: "var(--armory-text)" }}>
            Top up credits then resume the build — already-completed stages will be skipped.
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <Link to="/credits" data-testid="build-paused-topup" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm bg-amber-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono hover:bg-amber-300">
              Top Up Credits <ArrowUpRight size={9} />
            </Link>
            <button data-testid="build-resume-btn" onClick={onResume} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm border border-cyan-400 text-cyan-300 text-[10px] font-bold uppercase tracking-widest font-mono hover:bg-cyan-400/10">
              Resume Build
            </button>
          </div>
        </div>
      )}

      {status === "failed" && msg.error && (
        <div className="mt-2 text-[12px] text-rose-300 font-mono">{msg.error}</div>
      )}
    </div>
  );
}

export default function ChatMessage({ msg, onViewFiles, onOpenInWorkflows, onResume }) {
  const isUser = msg.role === "user";
  const isError = msg.type === "error";
  const isBuild = msg.type === "build" || msg.kind === "build";
  const isBuildProgress = msg.type === "build_progress";

  if (isBuildProgress) {
    return (
      <div className="flex gap-3 mb-4 fade-in">
        <Avatar role="assistant" />
        <div className="flex-1 max-w-[680px]">
          <BuildProgressCard msg={msg} onResume={onResume} />
        </div>
      </div>
    );
  }

  if (isBuild) {
    return (
      <div data-testid={`armory-msg-build`} className="flex gap-3 mb-4 fade-in">
        <Avatar role="assistant" />
        <div className="flex-1 max-w-[680px]">
          {msg.progress && msg.progress.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {ALL_STAGES.map((s) => {
                const entry = msg.progress.find((p) => p.stage === s);
                if (!entry) return null;
                return (
                  <StageChip key={s} stage={s} status={entry.status} durationMs={entry.duration_ms} />
                );
              })}
            </div>
          )}
          <CodeGenerationCard
            name={msg.name}
            files={msg.files || []}
            nodes={msg.nodes || []}
            durationMs={msg.duration_ms}
            onViewFiles={onViewFiles}
            onOpenInWorkflows={onOpenInWorkflows}
          />
          {msg.has_ui && msg.app_slug && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <Link
                to={`/apps/${msg.app_slug}`}
                data-testid={`open-mini-app-${msg.app_slug}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm bg-cyan-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono hover:bg-cyan-300"
              >
                Open Mini App <ArrowUpRight size={9} />
              </Link>
              <span className="text-[10px] font-mono opacity-50">/apps/{msg.app_slug}</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div data-testid="armory-msg-error" className="flex gap-3 mb-4 fade-in">
        <Avatar role="error" />
        <div className="flex-1 max-w-[680px]">
          <div className="px-4 py-3 rounded-sm" style={{ background: "var(--armory-error-bg)", borderLeft: "3px solid var(--armory-error)" }}>
            <div className="flex items-center gap-2 mb-1">
              <AlertCircle size={12} style={{ color: "var(--armory-error)" }} />
              <span className="text-[11px] font-mono uppercase tracking-[0.15em]" style={{ color: "var(--armory-error)" }}>
                Error
              </span>
            </div>
            <div className="text-[13px] leading-relaxed" style={{ color: "var(--armory-text)" }}>
              {msg.content}
            </div>
            {msg.suggestion && (
              <div className="mt-2 text-[12px] opacity-80" style={{ color: "var(--armory-text-mute)" }}>
                {msg.suggestion}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div data-testid="armory-msg-user" className="flex justify-end mb-4 fade-in">
        <div className="max-w-[680px] flex flex-row-reverse gap-3 items-start">
          <Avatar role="user" />
          <div
            className="px-4 py-3 rounded-sm"
            style={{
              background: "var(--armory-user-bubble)",
              border: "1px solid var(--armory-border)",
              color: "var(--armory-text)",
            }}
          >
            <div className="text-[13px] leading-relaxed whitespace-pre-wrap">{msg.content}</div>
          </div>
        </div>
      </div>
    );
  }

  // Assistant text (no bubble — just text with avatar)
  return (
    <div data-testid="armory-msg-assistant" className="flex gap-3 mb-4 fade-in">
      <Avatar role="assistant" />
      <div className="flex-1 max-w-[680px]">
        <div className="text-[13px] leading-relaxed whitespace-pre-wrap" style={{ color: "var(--armory-text)" }}>
          {renderWithCodeBlocks(msg.content || "")}
        </div>
      </div>
    </div>
  );
}

function Avatar({ role }) {
  const cfg = {
    user: { bg: "var(--armory-accent)", color: "#0a0a0a", Icon: User },
    assistant: { bg: "var(--armory-card)", color: "var(--armory-accent)", Icon: Bot, border: "var(--armory-border)" },
    error: { bg: "var(--armory-error-bg)", color: "var(--armory-error)", Icon: AlertCircle, border: "var(--armory-error)" },
  };
  const c = cfg[role] || cfg.assistant;
  return (
    <div
      className="w-8 h-8 rounded-sm flex items-center justify-center shrink-0"
      style={{
        background: c.bg,
        border: c.border ? `1px solid ${c.border}` : "none",
      }}
    >
      <c.Icon size={13} style={{ color: c.color }} />
    </div>
  );
}

// Render text with ```triple-backtick``` code fences as code blocks.
function renderWithCodeBlocks(text) {
  const parts = text.split(/```([\s\S]*?)```/g);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      // Code block
      const firstNewline = part.indexOf("\n");
      const lang = firstNewline > 0 ? part.slice(0, firstNewline).trim() : "";
      const code = firstNewline > 0 ? part.slice(firstNewline + 1) : part;
      return (
        <pre
          key={i}
          className="my-2 p-3 rounded-sm overflow-x-auto"
          style={{
            background: "var(--armory-code-bg)",
            border: "1px solid var(--armory-border)",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12,
            color: "var(--armory-text)",
          }}
        >
          {lang && (
            <div className="mb-2 text-[9px] uppercase tracking-[0.18em] opacity-50">{lang}</div>
          )}
          <code>{code}</code>
        </pre>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

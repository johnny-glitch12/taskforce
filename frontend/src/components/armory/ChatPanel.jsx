/* eslint-disable react/prop-types */
/**
 * ChatPanel — Center column of the Armory.
 * Header (session title + status pill + Open in Workflows)
 * Scrollable message thread
 * Sticky input with toolbar (Chat / Generate Code buttons)
 */
import { useEffect, useRef } from "react";
import { Sparkles, Send, Loader2, Code2, Paperclip, MessageSquare } from "lucide-react";
import { useAuth } from "@/App";
import ChatMessage from "./ChatMessage";
import EmptyState from "./EmptyState";

export default function ChatPanel({
  session, messages, model, models, input, setInput,
  busy, busyMode, onSend, onSuggest,
  onViewFiles, onOpenInWorkflows, onResume, hasProject,
  collapsed,
}) {
  const { developerMode } = useAuth() || {};
  const endRef = useRef(null);
  const taRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  const isEmpty = messages.length === 0;
  const status = busy ? "Building" : (hasProject ? "Ready" : "Draft");
  const statusColor = busy ? "#f59e0b" : (hasProject ? "var(--armory-success)" : "var(--armory-text-mute)");

  return (
    <div
      data-testid="armory-chat-panel"
      className="flex-1 flex flex-col min-w-0"
      style={{ background: "var(--armory-bg)" }}
    >
      {/* Header */}
      <header
        className="shrink-0 flex items-center gap-3 px-5 py-3"
        style={{ borderBottom: "1px solid var(--armory-border)" }}
      >
        <Sparkles size={14} style={{ color: "var(--armory-accent)" }} />
        <div className="flex-1 min-w-0">
          <div
            data-testid="armory-session-title"
            className="text-[13px] truncate"
            style={{ color: "var(--armory-text)", fontWeight: 500 }}
          >
            {session?.title || "New build"}
          </div>
        </div>
        <span
          data-testid="armory-status-pill"
          className="text-[9px] font-mono uppercase tracking-[0.18em] px-2 py-1 rounded-sm inline-flex items-center gap-1.5"
          style={{ background: "var(--armory-card)", color: statusColor, border: `1px solid ${statusColor}55` }}
        >
          {busy && <Loader2 size={9} className="animate-spin" />}
          {status}
        </span>
        {developerMode && hasProject && onOpenInWorkflows && (
          <button
            data-testid="armory-open-workflows-header"
            onClick={onOpenInWorkflows}
            className="text-[10px] font-mono uppercase tracking-[0.15em] px-2.5 py-1 rounded-sm transition-all hover:bg-white/5 inline-flex items-center gap-1.5"
            style={{ background: "transparent", color: "var(--armory-text-mute)", border: "1px solid var(--armory-border)" }}
          >
            <Code2 size={10} /> Open in Workflows
          </button>
        )}
      </header>

      {/* Thread */}
      <div
        data-testid="armory-thread"
        className="flex-1 overflow-y-auto"
        style={{ background: "var(--armory-bg)" }}
      >
        {isEmpty ? (
          <EmptyState onSuggest={onSuggest} />
        ) : (
          <div className="px-5 py-6 max-w-4xl mx-auto">
            {messages.map((m, i) => (
              <ChatMessage
                key={i}
                msg={m}
                onViewFiles={onViewFiles}
                onOpenInWorkflows={onOpenInWorkflows}
                onResume={onResume}
              />
            ))}
            {busy && (
              <div data-testid="armory-typing-indicator" className="flex items-center gap-2 py-2 px-1">
                <PulseDot />
                <span className="text-[11px] font-mono opacity-60" style={{ color: "var(--armory-text-mute)" }}>
                  {busyMode === "build" ? "Generating code…" : "Thinking…"}
                </span>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Input area (sticky bottom) */}
      <div
        className="shrink-0"
        style={{
          background: "var(--armory-bg)",
          borderTop: "1px solid var(--armory-border)",
        }}
      >
        <div className={`max-w-4xl mx-auto px-5 py-3 ${collapsed ? "" : ""}`}>
          <div
            className="rounded-sm overflow-hidden flex flex-col"
            style={{
              background: "var(--armory-card)",
              border: `1px solid ${input.trim() ? "var(--armory-accent)" : "var(--armory-border)"}`,
              transition: "border-color 150ms ease",
            }}
          >
            <textarea
              data-testid="armory-input"
              ref={taRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  onSend("chat");
                }
              }}
              placeholder="Describe what you want to build, or ask a question…"
              rows={1}
              className="w-full px-4 py-3 text-[13px] resize-none outline-none bg-transparent"
              style={{
                color: "var(--armory-text)",
                fontFamily: "'Inter', sans-serif",
                lineHeight: 1.5,
                minHeight: 44,
                maxHeight: 160,
              }}
            />
            {/* Toolbar */}
            <div className="flex items-center px-3 py-2 gap-2" style={{ borderTop: "1px solid var(--armory-border)" }}>
              <button
                data-testid="armory-input-attach"
                aria-label="Attach file (coming soon)"
                disabled
                className="p-1.5 rounded-sm opacity-40 cursor-not-allowed"
                style={{ color: "var(--armory-text-mute)" }}
                title="Attachments coming soon"
              >
                <Paperclip size={12} />
              </button>
              <div className="flex-1 text-[10px] font-mono" style={{ color: "var(--armory-text-dim)" }}>
                Chat freely, then click <span style={{ color: "var(--armory-text-mute)" }}>Generate Code</span> when you&apos;re ready.
              </div>
              <button
                data-testid="armory-send-chat"
                onClick={() => onSend("chat")}
                disabled={!input.trim() || busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
                style={{
                  background: "transparent",
                  color: input.trim() && !busy ? "var(--armory-text)" : "var(--armory-text-dim)",
                  border: "1px solid var(--armory-border)",
                  cursor: input.trim() && !busy ? "pointer" : "not-allowed",
                  opacity: busy ? 0.5 : 1,
                }}
              >
                {busy && busyMode === "chat" ? <Loader2 size={10} className="animate-spin" /> : <MessageSquare size={10} />} Chat
              </button>
              <button
                data-testid="armory-send-build"
                onClick={() => onSend("build")}
                disabled={!input.trim() || busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
                style={{
                  background: input.trim() && !busy ? "var(--armory-accent)" : "var(--armory-card-hover)",
                  color: input.trim() && !busy ? "#0a0a0a" : "var(--armory-text-dim)",
                  fontWeight: 600,
                  cursor: input.trim() && !busy ? "pointer" : "not-allowed",
                }}
              >
                {busy && busyMode === "build" ? <Loader2 size={10} className="animate-spin" /> : <Send size={10} />} Generate Code
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PulseDot() {
  return (
    <span className="inline-block w-2 h-2 rounded-sm" style={{
      background: "var(--armory-accent)",
      animation: "armory-pulse 1.4s ease-in-out infinite",
    }} />
  );
}

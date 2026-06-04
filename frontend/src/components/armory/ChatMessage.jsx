/* eslint-disable react/prop-types */
/**
 * ChatMessage — one row in the chat thread.
 * Renders user / assistant / error / code-generation cards.
 */
import { Bot, User, AlertCircle, Coins } from "lucide-react";
import CodeGenerationCard from "./CodeGenerationCard";

export default function ChatMessage({ msg, onViewFiles, onOpenInWorkflows }) {
  const isUser = msg.role === "user";
  const isError = msg.type === "error";
  const isBuild = msg.type === "build" || msg.kind === "build";

  if (isBuild) {
    return (
      <div data-testid={`armory-msg-build`} className="flex gap-3 mb-4 fade-in">
        <Avatar role="assistant" />
        <div className="flex-1 max-w-[680px]">
          <CodeGenerationCard
            name={msg.name}
            files={msg.files || []}
            nodes={msg.nodes || []}
            durationMs={msg.duration_ms}
            onViewFiles={onViewFiles}
            onOpenInWorkflows={onOpenInWorkflows}
          />
          {msg.credits_used !== undefined && (
            <CreditMeta credits={msg.credits_used} model={msg.model} inputTokens={msg.input_tokens} outputTokens={msg.output_tokens} keySource={msg.key_source} />
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
        {msg.credits_used !== undefined && (
          <CreditMeta credits={msg.credits_used} model={msg.model} inputTokens={msg.input_tokens} outputTokens={msg.output_tokens} keySource={msg.key_source} />
        )}
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

function CreditMeta({ credits, model, inputTokens, outputTokens, keySource }) {
  const totalTokens = (inputTokens || 0) + (outputTokens || 0);
  const isByok = keySource === "byok";
  return (
    <div data-testid="armory-credit-meta" className="mt-2 inline-flex items-center gap-2 text-[10px] font-mono opacity-70 flex-wrap" style={{ color: "var(--armory-text-dim)" }}>
      <span className="inline-flex items-center gap-1">
        <Coins size={9} style={{ color: "var(--armory-accent)" }} />
        <span data-testid="credit-meta-cost">−{credits}cr</span>
      </span>
      {model && <span>· {model.split("-").slice(0, 2).join("-")}</span>}
      {totalTokens > 0 && (
        <span data-testid="credit-meta-tokens">· {inputTokens || 0}→{outputTokens || 0} tok</span>
      )}
      {isByok && (
        <span data-testid="credit-meta-byok" className="px-1.5 py-0.5 rounded-sm text-[9px] font-bold uppercase tracking-wider" style={{ background: "rgba(168,85,247,0.15)", color: "#c084fc", border: "1px solid rgba(168,85,247,0.3)" }}>
          BYOK
        </span>
      )}
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

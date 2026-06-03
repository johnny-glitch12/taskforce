/* eslint-disable react/prop-types */
/**
 * EmptyState — "What do you want to build?" welcome screen.
 * Shown in the center panel before the first message is sent.
 */
import { Bot, Headset, Database, MessageCircle, ListChecks } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: Headset,
    title: "Customer support bot",
    prompt: "Build a customer-support bot that triages inbound emails — classify by topic, draft a reply, and escalate angry messages to Slack.",
  },
  {
    icon: Database,
    title: "Data pipeline",
    prompt: "Build a pipeline that ingests CSV files from a Google Drive folder, normalises the rows, and writes a daily summary to a Notion page.",
  },
  {
    icon: MessageCircle,
    title: "Slack daily summary",
    prompt: "Build a Slack bot that reads the previous day's messages from #general, summarises the top three threads, and posts a digest each morning.",
  },
  {
    icon: ListChecks,
    title: "Lead qualifier",
    prompt: "Build an agent that scores inbound Typeform leads (1–10) using GPT, writes the score to HubSpot, and sends qualified leads to Slack.",
  },
];

export default function EmptyState({ onSuggest }) {
  return (
    <div data-testid="armory-empty-state" className="h-full flex flex-col items-center justify-center px-6 py-10">
      <div className="w-16 h-16 mb-6 rounded-sm flex items-center justify-center"
           style={{
             background: "var(--armory-card)",
             border: "1px solid var(--armory-accent)",
             boxShadow: "0 0 60px rgba(0,229,204,0.12)",
           }}>
        <Bot size={28} style={{ color: "var(--armory-accent)" }} />
      </div>
      <h1
        data-testid="armory-empty-heading"
        className="text-3xl sm:text-4xl mb-2 text-center"
        style={{ color: "var(--armory-text)", fontFamily: "'Rajdhani', 'Space Grotesk', sans-serif", fontWeight: 500, letterSpacing: "-0.01em" }}
      >
        What do you want to build?
      </h1>
      <p className="text-sm text-center max-w-md mb-10" style={{ color: "var(--armory-text-mute)" }}>
        Describe an agent in plain English. We'll plan it with you, generate the code, and let you deploy or publish in one click.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-2xl w-full">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={s.title}
            data-testid={`armory-suggestion-${i}`}
            onClick={() => onSuggest(s.prompt)}
            className="text-left p-4 rounded-sm transition-all group"
            style={{
              background: "var(--armory-card)",
              border: "1px solid var(--armory-border)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--armory-accent)"; e.currentTarget.style.background = "var(--armory-card-hover)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--armory-border)"; e.currentTarget.style.background = "var(--armory-card)"; }}
          >
            <div className="flex items-center gap-2 mb-2">
              <s.icon size={14} style={{ color: "var(--armory-accent)" }} />
              <span className="text-[11px] font-mono uppercase tracking-[0.15em]" style={{ color: "var(--armory-text)" }}>
                {s.title}
              </span>
            </div>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--armory-text-mute)" }}>
              {s.prompt}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}

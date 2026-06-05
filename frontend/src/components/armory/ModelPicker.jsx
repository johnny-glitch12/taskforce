/* eslint-disable react/prop-types */
/**
 * ModelPicker — Compact model selection radio group, grouped by Platform / Your Keys.
 * Per-model credit costs are hidden — users pick on capability, not cost.
 */
import { Lock, Zap, Crown, ExternalLink } from "lucide-react";

export default function ModelPicker({ models, model, onChange }) {
  // A model belongs to "Your Keys" when it has an upstream BYOK service
  // (gpt-4o, claude-sonnet …) — even though the platform key still fronts it
  // by default. Models with no byok_service (gemini-flash/pro) are platform-only.
  const platform = (models || []).filter((m) => !m.byok_service);
  const byok = (models || []).filter((m) => !!m.byok_service);

  if (!models?.length) {
    return (
      <div className="text-[10px] font-mono opacity-50" style={{ color: "var(--armory-text-dim)" }}>
        Loading models…
      </div>
    );
  }

  return (
    <div data-testid="armory-model-picker">
      <div className="text-[9px] font-mono uppercase tracking-[0.18em] mb-1.5" style={{ color: "var(--armory-text-dim)" }}>
        Model
      </div>
      <div className="space-y-1">
        {platform.length > 0 && (
          <div>
            <div className="text-[9px] font-mono uppercase tracking-[0.12em] mt-1 mb-0.5" style={{ color: "var(--armory-text-dim)", opacity: 0.7 }}>
              Platform
            </div>
            {platform.map((m) => (
              <ModelRow key={m.id} m={m} selected={m.id === model} onSelect={() => onChange(m.id)} />
            ))}
          </div>
        )}
        {byok.length > 0 && (
          <div>
            <div className="text-[9px] font-mono uppercase tracking-[0.12em] mt-2 mb-0.5" style={{ color: "var(--armory-text-dim)", opacity: 0.7 }}>
              Your Keys
            </div>
            {byok.map((m) => (
              <ModelRow key={m.id} m={m} selected={m.id === model} onSelect={() => onChange(m.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ModelRow({ m, selected, onSelect }) {
  const needs = m.needs_byok && !m.using_byok;
  const Icon = m.speed === "fast" ? Zap : Crown;
  return (
    <button
      data-testid={`armory-model-${m.id}`}
      onClick={onSelect}
      disabled={needs}
      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-sm text-left transition-all"
      style={{
        background: selected ? "var(--armory-active-bg)" : "transparent",
        border: `1px solid ${selected ? "var(--armory-accent)" : "var(--armory-border)"}`,
        opacity: needs ? 0.5 : 1,
        cursor: needs ? "not-allowed" : "pointer",
      }}
      title={m.label}
    >
      <Icon size={10} style={{ color: selected ? "var(--armory-accent)" : "var(--armory-text-mute)" }} />
      <span className="flex-1 text-[10.5px] font-mono truncate" style={{ color: selected ? "var(--armory-text)" : "var(--armory-text-mute)" }}>
        {m.label}
      </span>
      {needs ? (
        <Lock size={9} style={{ color: "var(--armory-text-dim)" }} />
      ) : m.using_byok ? (
        <ExternalLink size={9} style={{ color: "var(--armory-accent)" }} />
      ) : null}
    </button>
  );
}

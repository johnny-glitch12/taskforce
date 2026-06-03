/* eslint-disable react/prop-types */
/**
 * SessionSidebar — Left-rail of the Armory.
 * 240px wide (collapses to 48px icon strip).
 *   Top:      "+ New Build" cyan CTA, search input
 *   Middle:   Sessions grouped by Today / Yesterday / This Week / Older
 *   Bottom:   ModelPicker (sticky)
 */
import { useMemo, useState } from "react";
import {
  Plus, Search, Trash2, ChevronLeft, ChevronRight, MessageSquare, Sparkles,
} from "lucide-react";
import ModelPicker from "./ModelPicker";

function groupSessions(items) {
  const now = new Date();
  const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const todayTs = startOf(now);
  const yesterdayTs = todayTs - 86400000;
  const weekTs = todayTs - 86400000 * 6;
  const groups = { Today: [], Yesterday: [], "This Week": [], Older: [] };
  for (const s of items) {
    const t = new Date(s.updated_at || s.created_at || 0).getTime();
    if (t >= todayTs) groups.Today.push(s);
    else if (t >= yesterdayTs) groups.Yesterday.push(s);
    else if (t >= weekTs) groups["This Week"].push(s);
    else groups.Older.push(s);
  }
  return groups;
}

export default function SessionSidebar({
  sessions, currentId, onSelect, onNew, onDelete,
  open, onToggle,
  models, model, onModelChange, credits,
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    if (!query.trim()) return sessions;
    const q = query.toLowerCase();
    return sessions.filter((s) => (s.title || "").toLowerCase().includes(q));
  }, [sessions, query]);
  const groups = useMemo(() => groupSessions(filtered), [filtered]);

  if (!open) {
    return (
      <aside
        data-testid="armory-sidebar"
        className="shrink-0 flex flex-col items-center py-3 gap-2"
        style={{ width: 48, background: "var(--armory-panel)", borderRight: "1px solid var(--armory-border)" }}
      >
        <button
          data-testid="armory-sidebar-toggle"
          onClick={onToggle}
          aria-label="Expand sidebar"
          className="w-8 h-8 rounded-sm flex items-center justify-center transition-colors hover:bg-white/5"
          style={{ color: "var(--armory-text-mute)" }}
        >
          <ChevronRight size={14} />
        </button>
        <button
          data-testid="armory-new-build-icon"
          onClick={onNew}
          aria-label="New build"
          className="w-8 h-8 rounded-sm flex items-center justify-center transition-colors"
          style={{ background: "var(--armory-accent)", color: "#0a0a0a" }}
        >
          <Plus size={14} />
        </button>
      </aside>
    );
  }

  return (
    <aside
      data-testid="armory-sidebar"
      className="shrink-0 flex flex-col"
      style={{
        width: 240,
        background: "var(--armory-panel)",
        borderRight: "1px solid var(--armory-border)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5" style={{ borderBottom: "1px solid var(--armory-border)" }}>
        <span className="text-[10px] font-mono uppercase tracking-[0.18em]" style={{ color: "var(--armory-text-mute)" }}>
          Sessions
        </span>
        <button
          data-testid="armory-sidebar-toggle"
          onClick={onToggle}
          aria-label="Collapse sidebar"
          className="p-1 rounded-sm transition-colors hover:bg-white/5"
          style={{ color: "var(--armory-text-mute)" }}
        >
          <ChevronLeft size={12} />
        </button>
      </div>

      {/* New build */}
      <div className="p-2.5">
        <button
          data-testid="armory-new-build"
          onClick={onNew}
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-[11px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all hover:brightness-110"
          style={{ background: "var(--armory-accent)", color: "#0a0a0a", fontWeight: 600 }}
        >
          <Plus size={12} /> New Build
        </button>
        <div className="relative mt-2">
          <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "var(--armory-text-dim)" }} />
          <input
            data-testid="armory-search-sessions"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-sm outline-none"
            style={{
              background: "var(--armory-bg)",
              border: "1px solid var(--armory-border)",
              color: "var(--armory-text)",
            }}
          />
        </div>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-1.5 pb-2">
        {sessions.length === 0 ? (
          <div className="text-center mt-8 px-4">
            <MessageSquare size={20} className="mx-auto mb-2 opacity-30" style={{ color: "var(--armory-text-mute)" }} />
            <p className="text-[11px] font-mono" style={{ color: "var(--armory-text-dim)" }}>
              No builds yet — start one above.
            </p>
          </div>
        ) : (
          Object.entries(groups).map(([label, items]) => items.length > 0 && (
            <div key={label} className="mb-3">
              <div className="px-2 pb-1.5 text-[9px] font-mono uppercase tracking-[0.18em]" style={{ color: "var(--armory-text-dim)" }}>
                {label}
              </div>
              <ul className="space-y-1">
                {items.map((s) => (
                  <SessionRow
                    key={s.id}
                    s={s}
                    active={s.id === currentId}
                    onSelect={() => onSelect(s.id)}
                    onDelete={() => onDelete(s.id)}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      {/* Model picker (sticky) */}
      <div className="shrink-0 px-2.5 pt-2 pb-2.5" style={{ borderTop: "1px solid var(--armory-border)" }}>
        <ModelPicker models={models} model={model} onChange={onModelChange} />
        {credits && (
          <div className="mt-3 p-2 rounded-sm" style={{ background: "var(--armory-bg)", border: "1px solid var(--armory-border)" }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-mono uppercase tracking-[0.15em]" style={{ color: "var(--armory-text-dim)" }}>
                Credits
              </span>
              <Sparkles size={9} style={{ color: "var(--armory-accent)" }} />
            </div>
            <div className="text-[10px] font-mono" style={{ color: "var(--armory-text-mute)" }}>
              <span style={{ color: "var(--armory-text)" }}>{credits.subscription_credits ?? "—"}</span>
              <span className="opacity-60"> / {credits.monthly_limit ?? "—"} monthly</span>
            </div>
            <div className="text-[10px] font-mono mt-0.5" style={{ color: "var(--armory-text-mute)" }}>
              <span style={{ color: "var(--armory-text)" }}>+{credits.topup_credits ?? 0}</span>
              <span className="opacity-60"> top-up</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function SessionRow({ s, active, onSelect, onDelete }) {
  const ts = new Date(s.updated_at || s.created_at || 0);
  const timeLabel = ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (
    <li
      data-testid={`armory-session-${s.id}`}
      onClick={onSelect}
      className="group relative pl-3 pr-2 py-2 rounded-sm cursor-pointer transition-all"
      style={{
        background: active ? "var(--armory-active-bg)" : "transparent",
        borderLeft: active ? `2px solid var(--armory-accent)` : "2px solid transparent",
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-[11.5px] leading-snug truncate"
               style={{ color: active ? "var(--armory-text)" : "var(--armory-text-mute)" }}>
            {s.title || "Untitled"}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[9px] font-mono opacity-60" style={{ color: "var(--armory-text-dim)" }}>
              {timeLabel}
            </span>
            {s.model && (
              <span className="text-[8.5px] font-mono px-1 py-px rounded-sm"
                    style={{ background: "var(--armory-bg)", color: "var(--armory-text-dim)" }}>
                {s.model.split("-")[0]}
              </span>
            )}
            {s.project_id && (
              <Sparkles size={8} style={{ color: "var(--armory-accent)" }} />
            )}
          </div>
        </div>
        <button
          data-testid={`armory-delete-session-${s.id}`}
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          aria-label="Delete session"
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded-sm hover:bg-rose-500/15"
          style={{ color: "var(--armory-text-dim)" }}
        >
          <Trash2 size={10} />
        </button>
      </div>
    </li>
  );
}

import { useState, useEffect, useMemo } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import {
  Brain, Trash2, Pencil, AlertTriangle, Download, Save, X, Info, ShieldAlert, Cpu, Settings2, Sparkles, ChevronRight,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TYPE_GROUPS = [
  { key: "correction",       label: "Corrections",      sublabel: "Highest priority — never repeat the underlying mistake", icon: ShieldAlert, accent: "red" },
  { key: "business_context", label: "Business Context", sublabel: "Who you are and what you work on", icon: Brain,    accent: "cyan" },
  { key: "preference",       label: "Preferences",      sublabel: "How you like the AI to respond", icon: Settings2, accent: "cyan" },
  { key: "technical",        label: "Technical",        sublabel: "Languages, frameworks, infra patterns you use", icon: Cpu,       accent: "cyan" },
  { key: "feedback",         label: "Feedback",         sublabel: "Past answers you liked or didn't", icon: Sparkles,  accent: "cyan" },
];

const TYPE_LABEL = Object.fromEntries(TYPE_GROUPS.map((g) => [g.key, g.label]));

/** Renders a single memory row with inline edit + delete. */
function MemoryRow({ memory, isCorrection, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memory.content);

  useEffect(() => { setDraft(memory.content); }, [memory.content]);

  const accentBorder = isCorrection ? "rgba(239,68,68,0.3)" : "var(--border)";
  const accentBg = isCorrection ? "rgba(239,68,68,0.04)" : "var(--bg-card)";

  return (
    <div
      data-testid={`memory-row-${memory.id}`}
      className="p-3 rounded-sm flex items-start gap-3"
      style={{ background: accentBg, border: `1px solid ${accentBorder}` }}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <textarea
            data-testid={`memory-edit-input-${memory.id}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            className="config-input w-full text-[12px] font-mono"
            autoFocus
          />
        ) : (
          <div className="text-[12px] t-text leading-relaxed whitespace-pre-wrap break-words">
            {memory.content}
          </div>
        )}
        <div className="text-[10px] t-text-mute font-mono mt-1.5 flex items-center gap-2">
          <span className="uppercase tracking-widest">{memory.type}</span>
          <span>·</span>
          <span>{memory.source || "extracted"}</span>
          {memory.created_at && (
            <>
              <span>·</span>
              <span>{String(memory.created_at).slice(0, 10)}</span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {editing ? (
          <>
            <button
              data-testid={`memory-save-${memory.id}`}
              onClick={async () => {
                if (draft.trim().length === 0) {
                  toast.error("Memory content cannot be empty.");
                  return;
                }
                const ok = await onSave(memory.id, draft.trim());
                if (ok) setEditing(false);
              }}
              className="p-1.5 rounded-sm text-cyan-400 hover:bg-cyan-400/10"
              title="Save"
            >
              <Save size={13} />
            </button>
            <button
              data-testid={`memory-cancel-${memory.id}`}
              onClick={() => { setDraft(memory.content); setEditing(false); }}
              className="p-1.5 rounded-sm t-text-mute hover:t-text"
              title="Cancel"
            >
              <X size={13} />
            </button>
          </>
        ) : (
          <>
            <button
              data-testid={`memory-edit-btn-${memory.id}`}
              onClick={() => setEditing(true)}
              className="p-1.5 rounded-sm t-text-mute hover:text-cyan-400"
              title="Edit"
            >
              <Pencil size={13} />
            </button>
            <button
              data-testid={`memory-delete-btn-${memory.id}`}
              onClick={() => {
                if (confirm("Delete this memory? It will be soft-deleted and stop influencing the AI immediately.")) {
                  onDelete(memory.id);
                }
              }}
              className="p-1.5 rounded-sm t-text-mute hover:text-red-400"
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/** Profile section — renders an arbitrary object as a bullet list of "key: value" rows.
 *  Empty values are skipped so the section can render half-filled profiles cleanly. */
function ProfileBulletList({ obj }) {
  const items = useMemo(() => {
    if (!obj || typeof obj !== "object") return [];
    return Object.entries(obj).flatMap(([k, v]) => {
      if (v === null || v === undefined || v === "") return [];
      if (typeof v === "boolean") return [{ k, v: v ? "yes" : "no" }];
      if (Array.isArray(v)) {
        if (v.length === 0) return [];
        return [{ k, v: v.join(", ") }];
      }
      if (typeof v === "object") {
        return [{ k, v: JSON.stringify(v) }];
      }
      return [{ k, v: String(v) }];
    });
  }, [obj]);

  if (items.length === 0) {
    return <div className="text-[11px] t-text-mute italic">— nothing on file —</div>;
  }
  return (
    <ul className="space-y-1">
      {items.map(({ k, v }) => (
        <li key={k} className="text-[12px] t-text leading-relaxed flex gap-2">
          <span className="t-text-dim shrink-0 uppercase tracking-widest text-[10px] mt-0.5">{k.replace(/_/g, " ")}:</span>
          <span className="flex-1 break-words">{v}</span>
        </li>
      ))}
    </ul>
  );
}

/** Integrations section — renders the BYOK key list + any oauth boolean flags.
 *  CRITICAL: we never show the key values themselves, only the service slugs +
 *  configured booleans. */
function IntegrationsSection({ integrations }) {
  if (!integrations || typeof integrations !== "object") {
    return <div className="text-[11px] t-text-mute italic">— no integrations configured —</div>;
  }
  const byokKeys = Array.isArray(integrations.byok_keys) ? integrations.byok_keys : [];
  const flags = Object.entries(integrations)
    .filter(([k, v]) => k !== "byok_keys" && (v === true || v === "yes" || v === 1))
    .map(([k]) => k);

  if (byokKeys.length === 0 && flags.length === 0) {
    return <div className="text-[11px] t-text-mute italic">— no integrations configured —</div>;
  }
  return (
    <ul className="space-y-1">
      {byokKeys.map((slug) => (
        <li key={`byok-${slug}`} className="text-[12px] t-text flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400" />
          <span className="uppercase tracking-wider">{slug}</span>
          <span className="t-text-mute text-[10px]">— BYOK key configured</span>
        </li>
      ))}
      {flags.map((slug) => (
        <li key={`flag-${slug}`} className="text-[12px] t-text flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span className="uppercase tracking-wider">{slug.replace(/_/g, " ")}</span>
          <span className="t-text-mute text-[10px]">— active</span>
        </li>
      ))}
    </ul>
  );
}

/** Confirm modal for the destructive "clear all" action. */
function ClearAllConfirm({ open, onClose, onConfirm }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        data-testid="clear-confirm-modal"
        className="w-full max-w-md rounded-sm p-5"
        style={{ background: "var(--bg-elevated)", border: "1px solid rgba(239,68,68,0.3)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle size={16} className="text-red-400" />
          <span className="text-[13px] tracking-widest uppercase t-text">Clear All Memory</span>
          <button onClick={onClose} className="ml-auto t-text-mute hover:t-text">
            <X size={14} />
          </button>
        </div>
        <p className="text-[12px] t-text leading-relaxed mb-4">
          This will permanently clear everything the AI has learned about you. Are you sure?
        </p>
        <p className="text-[11px] t-text-mute mb-4 leading-relaxed">
          The AI will start fresh on your next conversation. You can re-export your memory before clearing.
        </p>
        <div className="flex items-center gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 py-2 text-[11px] t-text-mute rounded-sm"
            style={{ border: "1px solid var(--border)" }}
          >
            CANCEL
          </button>
          <button
            data-testid="clear-confirm-btn"
            onClick={onConfirm}
            className="px-4 py-2 text-[11px] font-medium rounded-sm bg-red-500 text-white hover:bg-red-400"
          >
            CLEAR EVERYTHING
          </button>
        </div>
      </div>
    </div>
  );
}

export default function BuilderMemory() {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ profile: null, memories: {} });
  const [confirmClear, setConfirmClear] = useState(false);

  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/builder/memory`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData({ profile: json.profile || {}, memories: json.memories || {} });
    } catch (e) {
      toast.error("Failed to load memory.");
    }
    setLoading(false);
  };

  useEffect(() => { if (token) load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [token]);

  const handleEditSave = async (id, content) => {
    try {
      const res = await fetch(`${API}/api/builder/memory/${id}`, {
        method: "PATCH", headers, body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success("Memory updated.");
      await load();
      return true;
    } catch {
      toast.error("Update failed.");
      return false;
    }
  };

  const handleDelete = async (id) => {
    try {
      const res = await fetch(`${API}/api/builder/memory/${id}`, { method: "DELETE", headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success("Memory deleted.");
      await load();
    } catch {
      toast.error("Delete failed.");
    }
  };

  const handleClearAll = async () => {
    setConfirmClear(false);
    try {
      const res = await fetch(`${API}/api/builder/memory`, { method: "DELETE", headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      toast.success(`Cleared ${json.cleared_count} memories.`);
      await load();
    } catch {
      toast.error("Clear failed.");
    }
  };

  const handleExport = async () => {
    try {
      const res = await fetch(`${API}/api/builder/memory/export`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "taskforce-memory-export.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Memory exported.");
    } catch {
      toast.error("Export failed.");
    }
  };

  // Aggregate empty state — true only when profile is empty AND no memories
  const isEmpty = useMemo(() => {
    const m = data.memories || {};
    const total = Object.values(m).reduce((acc, arr) => acc + (arr?.length || 0), 0);
    const p = data.profile || {};
    const pEmpty = !p.business || Object.keys(p.business).length === 0;
    const prefEmpty = !p.preferences || Object.keys(p.preferences).length === 0;
    const intEmpty = !p.integrations || (
      (!p.integrations.byok_keys || p.integrations.byok_keys.length === 0)
      && Object.values(p.integrations).every((v) => !v || (Array.isArray(v) && v.length === 0))
    );
    return total === 0 && pEmpty && prefEmpty && intEmpty;
  }, [data]);

  const profile = data.profile || {};
  const memories = data.memories || {};

  return (
    <div data-testid="builder-memory-page" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-sm flex items-center justify-center" style={{ background: "rgba(34,211,238,0.1)" }}>
            <Brain size={18} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl tracking-wide t-text" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: "0.05em" }}>
              BUILDER MEMORY
            </h1>
            <p className="text-[12px] t-text-dim uppercase tracking-widest">
              The AI remembers these things about you and your work
            </p>
          </div>
        </div>

        <div className="text-[11px] t-text-dim mb-6 max-w-2xl">
          Everything below is stored encrypted at rest. Edit or remove anything that&apos;s stale, wrong, or you&apos;d
          rather the AI didn&apos;t know. Corrections are highest priority — the model is instructed to re-read them
          before every reply.
        </div>

        {loading && <div className="t-text-dim text-[12px]">Loading...</div>}

        {!loading && isEmpty && (
          <div
            data-testid="memory-empty-state"
            className="t-text-dim text-[12px] p-8 rounded-sm text-center"
            style={{ background: "var(--bg-card)", border: "1px dashed var(--border)" }}
          >
            <Brain size={28} className="mx-auto mb-3 opacity-50" />
            <div className="t-text text-[13px] mb-2">The AI hasn&apos;t learned anything yet.</div>
            <div className="mb-4">Start a conversation in the Armory to teach it about your work.</div>
            <Link
              to="/armory"
              className="inline-block px-4 py-2 text-[12px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300"
            >
              GO TO THE ARMORY
            </Link>
          </div>
        )}

        {!loading && !isEmpty && (
          <>
            {/* Business */}
            <Section title="Business" sublabel="Who you are, what you work on">
              <ProfileBulletList obj={profile.business} />
            </Section>

            {/* Preferences */}
            <Section title="Preferences" sublabel="How you like the AI to respond">
              <ProfileBulletList obj={profile.preferences} />
            </Section>

            {/* Technical / Integrations */}
            <Section title="Technical" sublabel="Active integrations and configured services">
              <IntegrationsSection integrations={profile.integrations} />
            </Section>

            {/* Memories grouped */}
            <div className="mt-6 mb-2 text-[10px] tracking-widest uppercase t-text-mute">
              Individual Memories
            </div>

            {TYPE_GROUPS.map((g) => {
              const list = memories[g.key] || [];
              if (list.length === 0) return null;
              const Icon = g.icon;
              const isCorrection = g.key === "correction";
              return (
                <div
                  key={g.key}
                  data-testid={`memory-group-${g.key}`}
                  className="mb-4 p-4 rounded-sm"
                  style={{
                    background: isCorrection ? "rgba(239,68,68,0.03)" : "var(--bg-card)",
                    border: `1px solid ${isCorrection ? "rgba(239,68,68,0.25)" : "var(--border)"}`,
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon size={14} className={isCorrection ? "text-red-400" : "text-cyan-400"} />
                    <span className="text-[12px] tracking-widest uppercase t-text">{g.label}</span>
                    <span className="text-[10px] t-text-mute font-mono">({list.length})</span>
                  </div>
                  <div className="text-[10px] t-text-mute mb-3">{g.sublabel}</div>
                  <div className="space-y-2">
                    {list.map((m) => (
                      <MemoryRow
                        key={m.id}
                        memory={m}
                        isCorrection={isCorrection}
                        onSave={handleEditSave}
                        onDelete={handleDelete}
                      />
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Action row */}
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <button
                data-testid="memory-clear-all-btn"
                onClick={() => setConfirmClear(true)}
                className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-sm text-red-300 hover:text-red-200 hover:bg-red-500/5"
                style={{ border: "1px solid rgba(239,68,68,0.3)" }}
              >
                <Trash2 size={13} /> CLEAR ALL MEMORY
              </button>
              <button
                data-testid="memory-export-btn"
                onClick={handleExport}
                className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-sm t-text hover:text-cyan-400"
                style={{ border: "1px solid var(--border)" }}
              >
                <Download size={13} /> EXPORT AS JSON
              </button>
            </div>
          </>
        )}

        {/* Footer notice — always shown so users can find this page later */}
        <div
          className="mt-8 p-4 rounded-sm text-[11px] t-text-dim flex items-start gap-2"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <Info size={13} className="text-cyan-400 mt-0.5 shrink-0" />
          <span>
            The AI learns from your conversations to give better results. You can clear or edit any memory at any
            time. Memory content is encrypted at rest with a key separate from your BYOK vault.
          </span>
        </div>
      </div>

      <ClearAllConfirm
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        onConfirm={handleClearAll}
      />
    </div>
  );
}

function Section({ title, sublabel, children }) {
  return (
    <div
      data-testid={`profile-section-${title.toLowerCase()}`}
      className="mb-4 p-4 rounded-sm"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="text-[12px] tracking-widest uppercase t-text mb-1 flex items-center gap-2">
        {title}
        <ChevronRight size={11} className="t-text-mute" />
        <span className="text-[10px] tracking-wider t-text-mute normal-case">{sublabel}</span>
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

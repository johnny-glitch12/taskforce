/* eslint-disable react/prop-types */
/**
 * MiniApp — public per-agent runner page (Prompt 31 Phase 4).
 *
 * Route: /app/:agentSlug  (NOT inside ProtectedRoute)
 *
 * Behaviour:
 *   - Anonymous visitors: see name + description + input form + "Sign in to run" CTA
 *   - Authenticated: button enabled, calls /api/apps/{slug}/run, renders result JSON
 *   - Respects mini_app_settings.input_mode (form | json) and visibility
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  Play, Loader2, AlertTriangle, Copy as CopyIcon, ChevronRight, Lock,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function tokenFromStorage() {
  try { return localStorage.getItem("taskforce_token") || null; } catch { return null; }
}

function inferFieldType(value) {
  if (Array.isArray(value)) return "select";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  return "text";
}

function FormField({ name, value, onChange, template }) {
  const tplValue = template?.[name];
  const type = inferFieldType(tplValue);
  const label = name.replace(/_/g, " ");

  if (type === "select") {
    return (
      <div className="mb-3">
        <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">{label}</label>
        <select value={value ?? tplValue[0]} onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 rounded-sm text-[12px] font-mono"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}>
          {tplValue.map((opt) => <option key={String(opt)} value={opt}>{String(opt)}</option>)}
        </select>
      </div>
    );
  }
  if (type === "boolean") {
    return (
      <div className="mb-3 flex items-center gap-2 text-[12px] font-mono t-text-sub">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} className="accent-cyan-400" />
        {label}
      </div>
    );
  }
  return (
    <div className="mb-3">
      <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">{label}</label>
      <input
        type={type === "number" ? "number" : (name.endsWith("_url") ? "url" : "text")}
        value={value ?? (tplValue || "")}
        onChange={(e) => onChange(type === "number" ? Number(e.target.value) : e.target.value)}
        className="w-full px-3 py-2 rounded-sm text-[12px] font-mono"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}
      />
    </div>
  );
}

export default function MiniApp() {
  const { agentSlug } = useParams();
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const token = tokenFromStorage();
  const isAuthed = !!token;

  // Input state — form values OR raw JSON string depending on mode
  const [formValues, setFormValues] = useState({});
  const [jsonText, setJsonText] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [runError, setRunError] = useState(null);

  useEffect(() => {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    fetch(`${API}/api/apps/public/${agentSlug}`, { headers })
      .then(async (r) => {
        if (!r.ok) {
          if (r.status === 404) throw new Error("NOT_FOUND");
          throw new Error(`HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((d) => {
        setMeta(d);
        if (d.input_template) {
          setFormValues({ ...d.input_template });
          setJsonText(JSON.stringify(d.input_template, null, 2));
        } else {
          setJsonText("{}");
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [agentSlug, token]);

  const inputMode = meta?.mini_app_settings?.input_mode || "json";
  const canRun = isAuthed && meta && meta.agent_state !== "paused" && meta.agent_state !== "archived";

  const buildInput = () => {
    if (inputMode === "form") return formValues;
    try { return JSON.parse(jsonText || "{}"); }
    catch (e) { throw new Error(`Invalid JSON: ${e.message}`); }
  };

  const handleRun = async () => {
    setRunning(true);
    setResult(null);
    setRunError(null);
    try {
      const input = buildInput();
      const res = await fetch(`${API}/api/apps/${agentSlug}/run`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ input }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.success) setResult(data.output);
      else setRunError(data.error || "Run failed");
    } catch (e) {
      setRunError(e.message || String(e));
    } finally { setRunning(false); }
  };

  if (loading) {
    return (
      <div data-testid="mini-app-page" className="min-h-screen flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-cyan-400" />
      </div>
    );
  }
  if (error === "NOT_FOUND") {
    return (
      <div data-testid="mini-app-page" className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <Lock size={28} className="text-rose-400 mx-auto mb-3 opacity-60" />
          <h1 className="text-2xl font-bold t-text mb-2">Agent unavailable</h1>
          <p className="text-[12px] t-text-mute">This mini-app may have been removed or set to private.</p>
        </div>
      </div>
    );
  }
  if (error || !meta) {
    return (
      <div data-testid="mini-app-page" className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center text-rose-400 text-[12px] font-mono">Error: {error || "Failed to load agent"}</div>
      </div>
    );
  }

  return (
    <div data-testid="mini-app-page" className="min-h-screen px-4 sm:px-6 lg:px-10 py-8 lg:py-12">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        {meta.mini_app_settings?.cover_url && (
          <img src={meta.mini_app_settings.cover_url} alt={meta.name}
               className="w-full h-40 object-cover rounded-sm mb-6"
               style={{ border: "1px solid var(--border)" }} />
        )}
        <div className="mb-2">
          <span className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-mute">
            {meta.category || "mini-app"}
          </span>
        </div>
        <h1 data-testid="mini-app-name" className="text-3xl sm:text-4xl font-bold t-text mb-2">
          {meta.name}
        </h1>
        <p data-testid="mini-app-creator" className="text-[11px] uppercase tracking-[0.12em] font-mono t-text-mute mb-3">
          by @{meta.creator?.handle || meta.creator?.name || "anonymous"}
        </p>
        {meta.description && (
          <p className="text-sm t-text-sub leading-relaxed mb-6">{meta.description}</p>
        )}

        {/* Visibility / state indicators */}
        {meta.mini_app_settings?.visibility === "private" && (
          <div className="mb-4 p-2 rounded-sm bg-amber-500/5 border border-amber-500/20 text-[11px] font-mono t-text-sub">
            <Lock size={11} className="inline text-amber-400 mr-1" /> Private — only you can run this agent.
          </div>
        )}
        {meta.agent_state === "paused" && (
          <div className="mb-4 p-2 rounded-sm bg-rose-500/5 border border-rose-500/20 text-[11px] font-mono t-text-sub">
            ⏸ This agent is paused. Resume in the Operations Hub to make it runnable.
          </div>
        )}

        {/* Input section */}
        <div data-testid="mini-app-input-form"
             className="rounded-sm p-5 mb-4"
             style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <h2 className="text-[12px] uppercase tracking-[0.12em] font-mono t-text-mute mb-3">Input</h2>
          {inputMode === "form" && meta.input_template ? (
            <div>
              {Object.keys(meta.input_template).map((key) => (
                <FormField
                  key={key}
                  name={key}
                  value={formValues[key]}
                  onChange={(v) => setFormValues((prev) => ({ ...prev, [key]: v }))}
                  template={meta.input_template}
                />
              ))}
            </div>
          ) : (
            <textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              rows={8}
              spellCheck={false}
              className="w-full px-3 py-2 rounded-sm text-[11px] font-mono"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)", resize: "vertical" }}
              placeholder='{"key": "value"}'
            />
          )}

          {!isAuthed ? (
            <Link
              to={`/login?return=${encodeURIComponent(`/app/${agentSlug}`)}`}
              data-testid="mini-app-run-btn"
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 text-[11px] uppercase tracking-[0.12em] font-mono"
            >
              <ChevronRight size={11} /> Sign in to run
            </Link>
          ) : (
            <button
              data-testid="mini-app-run-btn"
              onClick={handleRun}
              disabled={!canRun || running}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 text-[11px] uppercase tracking-[0.12em] font-mono disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {running ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
              {running ? "Running…" : `Run agent — ${meta.credits_per_run}cr`}
            </button>
          )}
        </div>

        {/* Error */}
        {runError && (
          <div data-testid="mini-app-error"
               className="rounded-sm p-3 mb-4 bg-rose-500/10 border border-rose-500/30 text-[11px] font-mono text-rose-300">
            <AlertTriangle size={11} className="inline mr-1" /> {runError}
          </div>
        )}

        {/* Results */}
        {result && (
          <div data-testid="mini-app-results"
               className="rounded-sm p-5 mb-4"
               style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-[12px] uppercase tracking-[0.12em] font-mono t-text-mute">Result</h2>
              <button
                onClick={() => { navigator.clipboard.writeText(JSON.stringify(result, null, 2)); toast.success("Copied"); }}
                className="text-[10px] uppercase tracking-wider font-mono t-text-sub hover:text-cyan-400"
              >
                <CopyIcon size={10} className="inline" /> Copy
              </button>
            </div>
            <pre className="bg-black/40 p-3 rounded-sm overflow-x-auto t-text font-mono text-[11px] whitespace-pre-wrap">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}

        {/* Branding footer */}
        {meta.mini_app_settings?.show_branding && meta.mini_app_settings?.allow_sharing && (
          <div className="text-center mt-8 pt-6 border-t" style={{ borderColor: "var(--border)" }}>
            <Link to="/" className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-mute hover:text-cyan-400">
              Powered by Task Force AI
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

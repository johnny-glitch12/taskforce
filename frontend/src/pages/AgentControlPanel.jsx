/* eslint-disable react/prop-types */
/**
 * AgentControlPanel — single-agent operations dashboard.
 *
 * Route: /my-agents/:id  (Prompt 31 Phase 2)
 *
 * Tabs:
 *   Overview      — uptime bar + 7-day chart + recent activity
 *   Run History   — paginated table with expandable rows + CSV export
 *   Logs          — color-coded log stream with level filter + paging
 *   Data & Inputs — Coming in Phase 3
 *   Settings      — Coming in Phase 3
 *   Mini-App      — Coming in Phase 4
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Pause, Play, Edit3, ExternalLink, Activity, BarChart3,
  Loader2, Download, ChevronDown, ChevronRight, Copy as CopyIcon, RefreshCw,
  Upload, FileText, Trash2, Eye, Key, Plus, Save, AlertTriangle,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TABS = [
  { id: "overview", label: "Overview", live: true, testid: "tab-overview" },
  { id: "run-history", label: "Run History", live: true, testid: "tab-run-history" },
  { id: "logs", label: "Logs", live: true, testid: "tab-logs" },
  { id: "data", label: "Data & Inputs", live: true, testid: "tab-data" },
  { id: "settings", label: "Settings", live: true, testid: "tab-settings" },
  { id: "mini-app", label: "Mini-App", live: true, testid: "tab-mini-app" },
];

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

/* ─── Overview tab ──────────────────────────────────────────────────── */
function UptimeBar({ uptime }) {
  if (!uptime || !uptime.buckets) return null;
  return (
    <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-mute">Uptime · last 24h</div>
          <div className="text-2xl font-bold t-text font-mono mt-1">{uptime.percentage}%</div>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="flex items-center gap-1 text-emerald-400"><span className="w-2 h-2 bg-emerald-400 inline-block" /> {uptime.up_count} up</span>
          <span className="flex items-center gap-1 text-rose-400"><span className="w-2 h-2 bg-rose-400 inline-block" /> {uptime.down_count} down</span>
          <span className="flex items-center gap-1 t-text-mute"><span className="w-2 h-2 bg-zinc-700 inline-block" /> {uptime.gray_count} idle</span>
        </div>
      </div>
      <div data-testid="uptime-bar" className="flex items-stretch gap-px h-6 rounded-sm overflow-hidden" style={{ background: "var(--bg-elevated)" }}>
        {uptime.buckets.map((b, i) => {
          const cls =
            b.state === "up" ? "bg-emerald-400/80" :
            b.state === "down" ? "bg-rose-500" :
            "bg-zinc-700/60";
          return (
            <div
              key={i}
              className={`flex-1 ${cls}`}
              title={`${b.start} — ${b.state}${b.runs ? ` (${b.runs} runs, ${b.errors} errors)` : ""}`}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between text-[9px] t-text-mute mt-1 font-mono">
        <span>24h ago</span>
        <span>now</span>
      </div>
    </div>
  );
}

function UsageChart({ stats_7d }) {
  const data = (stats_7d || []).map((d) => ({
    date: d.date?.slice(5) || "", // "MM-DD"
    runs: d.runs,
    errors: d.errors,
  }));
  return (
    <div data-testid="usage-chart" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-mute mb-3">Runs · last 7 days</div>
      <div style={{ width: "100%", height: 200 }}>
        <ResponsiveContainer>
          <BarChart data={data}>
            <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 10, fontFamily: "monospace" }} />
            <YAxis stroke="#71717a" tick={{ fontSize: 10, fontFamily: "monospace" }} />
            <Tooltip
              contentStyle={{
                background: "#0a0a0c",
                border: "1px solid #27272a",
                borderRadius: "2px",
                fontSize: 11,
                fontFamily: "monospace",
              }}
            />
            <Bar dataKey="runs" fill="#22d3ee" />
            <Bar dataKey="errors" fill="#f43f5e" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RecentActivity({ activity }) {
  return (
    <div data-testid="recent-activity" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-mute mb-3">Recent activity</div>
      {(!activity || activity.length === 0) && (
        <div className="text-[11px] t-text-mute">No runs yet.</div>
      )}
      <ul className="space-y-1.5">
        {(activity || []).map((a) => (
          <li key={a.id} className="flex items-center gap-2 text-[11px] font-mono">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${a.status === "success" ? "bg-emerald-400" : "bg-rose-400"}`} />
            <span className="t-text-mute w-32 truncate">{fmtTime(a.created_at)}</span>
            <span className={a.status === "success" ? "text-emerald-400" : "text-rose-400"}>{a.status}</span>
            <span className="t-text-sub truncate flex-1">{a.summary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function OverviewTab({ stats }) {
  if (!stats) return <div className="py-12 text-center"><Loader2 size={20} className="animate-spin text-cyan-400 inline" /></div>;
  return (
    <div className="space-y-4">
      <UptimeBar uptime={stats.uptime_24h} />
      <UsageChart stats_7d={stats.stats_7d} />
      <RecentActivity activity={stats.recent_activity} />
    </div>
  );
}

/* ─── Run History tab ───────────────────────────────────────────────── */
function RunRow({ run, agentId, token, navigate }) {
  const [open, setOpen] = useState(false);
  const [full, setFull] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadFull = async () => {
    if (full) { setOpen(!open); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/runs/${run.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setFull(await res.json());
      setOpen(true);
    } catch (e) {
      toast.error(`Failed to load run detail: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  const copy = (text) => {
    navigator.clipboard.writeText(typeof text === "string" ? text : JSON.stringify(text, null, 2));
    toast.success("Copied");
  };

  return (
    <>
      <tr
        data-testid={`run-row-${run.id}`}
        onClick={loadFull}
        className="cursor-pointer hover:bg-cyan-500/5 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <td className="px-3 py-2 text-[11px]">
          {open ? <ChevronDown size={11} className="inline" /> : <ChevronRight size={11} className="inline" />}
        </td>
        <td className="px-3 py-2 text-[11px] font-mono">
          <span className={`px-1.5 py-0.5 rounded-sm text-[9px] uppercase tracking-wider ${
            run.status === "success" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
          }`}>
            {run.status}
          </span>
        </td>
        <td className="px-3 py-2 text-[11px] font-mono t-text-sub">{fmtTime(run.created_at)}</td>
        <td className="px-3 py-2 text-[11px] font-mono t-text">{run.execution_time_ms}ms</td>
        <td className="px-3 py-2 text-[11px] font-mono t-text">{run.credits_charged} cr</td>
      </tr>
      {open && full && (
        <tr style={{ background: "var(--bg-elevated)" }}>
          <td colSpan={5} className="px-3 py-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="t-text-mute uppercase tracking-wider text-[9px]">Input</div>
                  <button onClick={() => copy(full.input)} className="text-[9px] t-text-sub hover:text-cyan-400">
                    <CopyIcon size={9} className="inline" /> Copy Input
                  </button>
                </div>
                <pre className="bg-black/40 p-2 rounded-sm overflow-x-auto t-text font-mono text-[10px] max-h-48">
                  {JSON.stringify(full.input, null, 2)}
                </pre>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="t-text-mute uppercase tracking-wider text-[9px]">Output</div>
                  <button onClick={() => copy(full.output)} className="text-[9px] t-text-sub hover:text-cyan-400">
                    <CopyIcon size={9} className="inline" /> Copy Output
                  </button>
                </div>
                <pre className="bg-black/40 p-2 rounded-sm overflow-x-auto t-text font-mono text-[10px] max-h-48">
                  {JSON.stringify(full.output, null, 2)}
                </pre>
              </div>
            </div>
            {full.error && (
              <div className="mt-2 p-2 rounded-sm bg-rose-500/10 border border-rose-500/30 text-[11px] text-rose-300 font-mono">
                {full.error}
              </div>
            )}
            <div className="mt-2">
              <button
                onClick={() => {
                  const q = encodeURIComponent(JSON.stringify(full.input || {}));
                  navigate(`/apps/${agentId}?input=${q}`);
                }}
                className="text-[10px] uppercase tracking-wider font-mono t-text-sub hover:text-cyan-400"
              >
                <RefreshCw size={10} className="inline" /> Re-run with same input →
              </button>
            </div>
          </td>
        </tr>
      )}
      {loading && (
        <tr><td colSpan={5} className="px-3 py-2 text-[10px] t-text-mute"><Loader2 size={10} className="inline animate-spin" /> loading…</td></tr>
      )}
    </>
  );
}

function RunHistoryTab({ agentId, token }) {
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState("all");
  const [dateRange, setDateRange] = useState("7d");
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const load = async (replace = true, _cursor = null) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ status, date_range: dateRange, limit: "25" });
      if (_cursor) params.set("cursor", _cursor);
      const res = await fetch(`${API}/api/agents/${agentId}/runs?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const d = await res.json();
      setRuns((prev) => replace ? d.runs : [...prev, ...d.runs]);
      setCursor(d.next_cursor);
      setHasMore(d.has_more);
    } catch (e) {
      toast.error(`Failed to load runs: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(true, null); }, [status, dateRange]); // eslint-disable-line

  const exportCsv = async () => {
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/runs/export?date_range=${dateRange}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `runs-${dateRange}.csv`;
      a.click();
      toast.success("CSV downloaded");
    } catch (e) {
      toast.error(`Export failed: ${e.message || e}`);
    }
  };

  return (
    <div data-testid="run-history-table" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="px-2 py-1 rounded-sm text-[11px] font-mono"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}>
          <option value="all">All statuses</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>
        <select value={dateRange} onChange={(e) => setDateRange(e.target.value)}
          className="px-2 py-1 rounded-sm text-[11px] font-mono"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}>
          <option value="24h">Last 24h</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time</option>
        </select>
        <div className="flex-1" />
        <button
          data-testid="export-csv-btn"
          onClick={exportCsv}
          className="flex items-center gap-1 px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
        >
          <Download size={10} /> Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-[9px] uppercase tracking-wider t-text-mute font-mono border-b" style={{ borderColor: "var(--border)" }}>
              <th className="px-3 py-2 w-6"></th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Duration</th>
              <th className="px-3 py-2">Credits</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <RunRow key={r.id} run={r} agentId={agentId} token={token} navigate={navigate} />
            ))}
          </tbody>
        </table>
      </div>
      {runs.length === 0 && !loading && (
        <div className="text-center py-8 t-text-mute text-[11px]">No runs match these filters.</div>
      )}
      {hasMore && (
        <div className="text-center pt-4">
          <button
            onClick={() => load(false, cursor)}
            disabled={loading}
            className="px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-zinc-500/10 t-text-sub border border-zinc-500/30 hover:bg-zinc-500/15"
          >
            {loading ? <Loader2 size={10} className="inline animate-spin" /> : "Load older"}
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Logs tab ──────────────────────────────────────────────────────── */
function LogsTab({ agentId, token }) {
  const [logs, setLogs] = useState([]);
  const [level, setLevel] = useState("all");
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  const load = async (replace = true, _cursor = null) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ level, limit: "100" });
      if (_cursor) params.set("cursor", _cursor);
      const res = await fetch(`${API}/api/agents/${agentId}/logs?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const d = await res.json();
      setLogs((prev) => replace ? d.logs : [...prev, ...d.logs]);
      setCursor(d.next_cursor);
      setHasMore(d.has_more);
    } catch (e) {
      toast.error(`Failed to load logs: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(true, null); }, [level]); // eslint-disable-line

  const levelColor = {
    info: "text-cyan-400",
    warn: "text-amber-400",
    error: "text-rose-400",
  };

  return (
    <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select value={level} onChange={(e) => setLevel(e.target.value)}
          className="px-2 py-1 rounded-sm text-[11px] font-mono"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}>
          <option value="all">All levels</option>
          <option value="info">Info</option>
          <option value="warn">Warn</option>
          <option value="error">Error</option>
        </select>
        <label className="flex items-center gap-1 text-[10px] uppercase tracking-wider font-mono t-text-sub">
          <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} className="accent-cyan-400" />
          Auto-scroll
        </label>
      </div>
      <div className="bg-black/40 rounded-sm p-2 max-h-[60vh] overflow-y-auto font-mono text-[10px]">
        {logs.length === 0 && !loading && (
          <div className="text-center py-6 t-text-mute">No logs in this window.</div>
        )}
        {logs.map((l) => (
          <div
            key={l.id}
            data-testid={`log-row-${l.id}`}
            className={`flex gap-2 py-0.5 ${levelColor[l.level] || "t-text"}`}
          >
            <span className="t-text-mute w-32 shrink-0">{l.timestamp?.slice(11, 23)}</span>
            <span className="uppercase tracking-wider w-10 shrink-0">{l.level}</span>
            <span className="t-text-mute w-14 shrink-0">{l.source}</span>
            <span className="break-all">{l.message}</span>
          </div>
        ))}
      </div>
      {hasMore && (
        <div className="text-center pt-3">
          <button
            onClick={() => load(false, cursor)}
            disabled={loading}
            className="px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-zinc-500/10 t-text-sub border border-zinc-500/30 hover:bg-zinc-500/15"
          >
            {loading ? <Loader2 size={10} className="inline animate-spin" /> : "Load older"}
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Placeholder tab ───────────────────────────────────────────────── */
function PlaceholderTab({ phase, label }) {
  return (
    <div className="rounded-sm p-12 text-center" style={{ background: "var(--bg-card)", border: "1px dashed var(--border)" }}>
      <Activity size={28} className="text-cyan-400 mx-auto mb-3 opacity-40" />
      <div className="t-text font-medium mb-1">{label}</div>
      <div className="text-[11px] t-text-mute">Coming in {phase}.</div>
    </div>
  );
}

/* ═══ Phase 3: Data & Inputs tab ════════════════════════════════════ */

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function ConfirmModal({ title, body, onConfirm, onCancel, danger }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative w-full max-w-sm rounded-sm p-5"
           style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
        <h3 className="t-text font-bold mb-2">{title}</h3>
        <p className="text-[12px] t-text-sub mb-4">{body}</p>
        <div className="flex items-center justify-end gap-2">
          <button onClick={onCancel}
            className="px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-wider font-mono t-text-sub">
            Cancel
          </button>
          <button onClick={onConfirm}
            className={`px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-wider font-mono border ${
              danger
                ? "bg-rose-500/10 text-rose-400 border-rose-500/30 hover:bg-rose-500/15"
                : "bg-cyan-500/10 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/15"
            }`}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

function InputTemplateSection({ agentId, token, agent }) {
  const initial = agent?.input_template ? JSON.stringify(agent.input_template, null, 2) : "";
  const [text, setText] = useState(initial);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const validate = (s) => {
    if (!s.trim()) { setError(null); return null; }
    try { return JSON.parse(s); }
    catch (e) { setError(e.message); return undefined; }
  };

  const save = async () => {
    const parsed = validate(text);
    if (parsed === undefined) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/input-template`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ template: parsed }),
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Default input saved");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="t-text font-semibold text-[13px]">Default Input Template</h3>
        <button
          data-testid="save-input-template-btn"
          onClick={save}
          disabled={saving || error !== null}
          className="px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 size={10} className="inline animate-spin" /> : <><Save size={10} className="inline" /> Save</>}
        </button>
      </div>
      <p className="text-[11px] t-text-mute mb-3">JSON shape pre-populated when this agent runs. Leave blank to require explicit input each time.</p>
      <textarea
        data-testid="input-template-editor"
        value={text}
        onChange={(e) => { setText(e.target.value); setError(null); }}
        onBlur={(e) => validate(e.target.value)}
        rows={8}
        placeholder={`{\n  "gmail_query": "is:unread"\n}`}
        spellCheck={false}
        className="w-full px-3 py-2 rounded-sm font-mono text-[11px]"
        style={{
          background: "var(--bg-elevated)",
          border: `1px solid ${error ? "rgb(244 63 94 / 0.5)" : "var(--border)"}`,
          color: "var(--text)",
          resize: "vertical",
        }}
      />
      {error && (
        <div className="mt-2 text-[10px] text-rose-400 font-mono">⚠ Invalid JSON: {error}</div>
      )}
    </div>
  );
}

function DataFilesSection({ agentId, token }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [preview, setPreview] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/data`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setFiles(d.files || []);
    } catch (e) {
      toast.error(`Failed to load files: ${e.message || e}`);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [agentId]); // eslint-disable-line

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File too large — max 10MB");
      e.target.value = "";
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/api/agents/${agentId}/data`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      toast.success(`Uploaded ${file.name}`);
      e.target.value = "";
      load();
    } catch (e2) {
      toast.error(`Upload failed: ${e2.message || e2}`);
    } finally { setUploading(false); }
  };

  const previewFile = async (f) => {
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/data/${f.id}/preview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      setPreview(await res.json());
    } catch (e) {
      toast.error(`Preview failed: ${e.message || e}`);
    }
  };

  const download = (f) => {
    fetch(`${API}/api/agents/${agentId}/data/${f.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (r) => {
      if (!r.ok) throw new Error(`${r.status}`);
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = f.filename;
      a.click();
    }).catch((e) => toast.error(`Download failed: ${e.message || e}`));
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/data/${confirmDelete.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("File deleted");
      setConfirmDelete(null);
      load();
    } catch (e) {
      toast.error(`Delete failed: ${e.message || e}`);
    }
  };

  return (
    <div className="rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="t-text font-semibold text-[13px]">Uploaded Data Files</h3>
        <label
          data-testid="upload-data-btn"
          className="inline-flex items-center gap-1 px-3 py-1 rounded-sm cursor-pointer text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
        >
          {uploading ? <Loader2 size={10} className="animate-spin" /> : <Upload size={10} />}
          {uploading ? "Uploading…" : "Upload data file"}
          <input
            type="file"
            accept=".csv,.json,.txt,.xlsx,text/csv,application/json,text/plain"
            onChange={onPick}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>
      <p className="text-[11px] t-text-mute mb-3">CSV, JSON, or text files (≤10MB, up to 10 per agent). Files are streamed to GridFS and re-attached to every agent run.</p>

      <div data-testid="data-files-table" className="overflow-x-auto">
        {loading && <div className="text-center py-6 text-[11px] t-text-mute"><Loader2 size={12} className="inline animate-spin" /></div>}
        {!loading && files.length === 0 && (
          <div className="text-center py-6 text-[11px] t-text-mute">
            No data files yet. Upload CSVs, JSON, or text files your agent can reference during runs.
          </div>
        )}
        {!loading && files.length > 0 && (
          <table className="w-full">
            <thead>
              <tr className="text-left text-[9px] uppercase tracking-wider t-text-mute font-mono border-b" style={{ borderColor: "var(--border)" }}>
                <th className="px-3 py-2">Filename</th>
                <th className="px-3 py-2">Rows</th>
                <th className="px-3 py-2">Size</th>
                <th className="px-3 py-2">Uploaded</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id} data-testid={`data-file-row-${f.id}`} className="border-b" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2 text-[11px] font-mono t-text">
                    <FileText size={10} className="inline t-text-mute mr-1" /> {f.filename}
                  </td>
                  <td className="px-3 py-2 text-[11px] font-mono t-text-sub">{f.row_count ?? "—"}</td>
                  <td className="px-3 py-2 text-[11px] font-mono t-text-sub">{fmtBytes(f.size_bytes)}</td>
                  <td className="px-3 py-2 text-[10px] font-mono t-text-mute">{f.uploaded_at?.slice(0, 16).replace("T", " ")}</td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => previewFile(f)} title="Preview" className="p-1 text-cyan-400 hover:text-cyan-300">
                      <Eye size={11} />
                    </button>
                    <button onClick={() => download(f)} title="Download" className="p-1 t-text-sub hover:t-text">
                      <Download size={11} />
                    </button>
                    <button onClick={() => setConfirmDelete(f)} title="Delete" className="p-1 text-rose-400 hover:text-rose-300">
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setPreview(null)} />
          <div className="relative w-full max-w-3xl rounded-sm p-5 max-h-[80vh] overflow-y-auto"
               style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="t-text font-semibold text-[13px] font-mono">{preview.filename}</h3>
              <button onClick={() => setPreview(null)} className="t-text-mute hover:t-text">×</button>
            </div>
            {preview.parsed_rows && Array.isArray(preview.parsed_rows[0]) ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] font-mono">
                  <tbody>
                    {preview.parsed_rows.map((row, i) => (
                      <tr key={i} className={`border-b ${i === 0 ? "t-text font-bold" : "t-text-sub"}`} style={{ borderColor: "var(--border)" }}>
                        {row.map((cell, j) => <td key={j} className="px-2 py-1">{String(cell)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : preview.parsed_rows ? (
              <pre className="bg-black/40 p-2 rounded-sm text-[10px] font-mono t-text overflow-x-auto">
                {JSON.stringify(preview.parsed_rows, null, 2)}
              </pre>
            ) : (
              <pre className="bg-black/40 p-2 rounded-sm text-[10px] font-mono t-text overflow-x-auto whitespace-pre-wrap">
                {preview.preview_chars}
              </pre>
            )}
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmModal
          title="Delete data file?"
          body={`This will permanently remove "${confirmDelete.filename}". Your agent will no longer have access to this data.`}
          danger
          onConfirm={doDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

function EnvVarsSection({ agentId, token }) {
  const [vars, setVars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/env`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setVars(d.env || []);
    } catch (e) {
      toast.error(`Failed to load env vars: ${e.message || e}`);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [agentId]); // eslint-disable-line

  const create = async () => {
    if (!newKey.trim() || !newValue) return;
    if (!/^[A-Z_][A-Z0-9_]*$/.test(newKey.trim())) {
      toast.error("Key must be UPPER_SNAKE_CASE (letters, digits, underscores)");
      return;
    }
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/env`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ key: newKey.trim(), value: newValue }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      toast.success("Variable saved");
      setNewKey(""); setNewValue(""); setAdding(false);
      load();
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    }
  };

  const startEdit = (ev) => { setEditingId(ev.id); setEditValue(""); };
  const saveEdit = async (ev) => {
    if (!editValue) { setEditingId(null); return; }
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/env/${ev.id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ value: editValue }),
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Value updated");
      setEditingId(null); setEditValue("");
      load();
    } catch (e) {
      toast.error(`Update failed: ${e.message || e}`);
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/env/${confirmDelete.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Variable removed");
      setConfirmDelete(null);
      load();
    } catch (e) {
      toast.error(`Delete failed: ${e.message || e}`);
    }
  };

  return (
    <div className="rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="t-text font-semibold text-[13px]">Environment Variables</h3>
        <button
          data-testid="add-env-var-btn"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1 px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
        >
          <Plus size={10} /> Add Variable
        </button>
      </div>
      <p className="text-[11px] t-text-mute mb-3">
        API keys and secrets this agent needs at runtime. Values are Fernet-encrypted at rest and only decrypted inside the sandbox during a run.
      </p>

      <div data-testid="env-vars-table" className="overflow-x-auto">
        {loading && <div className="text-center py-6 text-[11px] t-text-mute"><Loader2 size={12} className="inline animate-spin" /></div>}
        {!loading && vars.length === 0 && !adding && (
          <div className="text-center py-6 text-[11px] t-text-mute">
            No environment variables configured. Add API keys your agent uses (Gmail, Slack, etc.).
          </div>
        )}
        {!loading && (vars.length > 0 || adding) && (
          <table className="w-full">
            <thead>
              <tr className="text-left text-[9px] uppercase tracking-wider t-text-mute font-mono border-b" style={{ borderColor: "var(--border)" }}>
                <th className="px-3 py-2">Key</th>
                <th className="px-3 py-2">Value</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {vars.map((ev) => (
                <tr key={ev.id} data-testid={`env-var-row-${ev.id}`} className="border-b" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2 text-[11px] font-mono t-text">
                    <Key size={10} className="inline t-text-mute mr-1" /> {ev.key}
                  </td>
                  <td className="px-3 py-2 text-[11px] font-mono t-text-sub">
                    {editingId === ev.id ? (
                      <input
                        type="password"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        autoFocus
                        placeholder="new value"
                        className="px-2 py-0.5 rounded-sm font-mono text-[11px] w-48"
                        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}
                      />
                    ) : (
                      ev.value_masked
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {editingId === ev.id ? (
                      <>
                        <button onClick={() => saveEdit(ev)} className="text-[10px] uppercase font-mono text-cyan-400 mr-2">Save</button>
                        <button onClick={() => { setEditingId(null); setEditValue(""); }} className="text-[10px] uppercase font-mono t-text-mute">Cancel</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => startEdit(ev)} title="Edit" className="p-1 t-text-sub hover:text-cyan-400">
                          <Edit3 size={11} />
                        </button>
                        <button onClick={() => setConfirmDelete(ev)} title="Remove" className="p-1 text-rose-400 hover:text-rose-300">
                          <Trash2 size={11} />
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {adding && (
                <tr className="border-b" style={{ borderColor: "var(--border)", background: "var(--bg-elevated)" }}>
                  <td className="px-3 py-2">
                    <input
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value.toUpperCase())}
                      placeholder="API_KEY_NAME"
                      autoFocus
                      className="px-2 py-1 rounded-sm font-mono text-[11px] w-full"
                      style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="password"
                      value={newValue}
                      onChange={(e) => setNewValue(e.target.value)}
                      placeholder="secret value"
                      className="px-2 py-1 rounded-sm font-mono text-[11px] w-full"
                      style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }}
                    />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={create} className="text-[10px] uppercase font-mono text-cyan-400 mr-2">Save</button>
                    <button onClick={() => { setAdding(false); setNewKey(""); setNewValue(""); }} className="text-[10px] uppercase font-mono t-text-mute">Cancel</button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {confirmDelete && (
        <ConfirmModal
          title="Remove variable?"
          body={`"${confirmDelete.key}" will be deleted permanently. Any running agent will lose access to this value.`}
          danger
          onConfirm={doDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

function DataTab({ agentId, token, agent }) {
  return (
    <div data-testid="tab-data-content" className="space-y-4">
      <InputTemplateSection agentId={agentId} token={token} agent={agent} />
      <DataFilesSection agentId={agentId} token={token} />
      <EnvVarsSection agentId={agentId} token={token} />
    </div>
  );
}

/* ═══ Phase 3: Settings tab ════════════════════════════════════════ */

const CATEGORY_OPTIONS = [
  "productivity", "sales", "marketing", "support", "ops",
  "data", "research", "content", "engineering", "finance", "other",
];

function SettingsTab({ agentId, token, agent, onAgentUpdated, navigate }) {
  // Section A — General
  const [name, setName] = useState(agent?.name || "");
  const [description, setDescription] = useState(agent?.description || "");
  const [category, setCategory] = useState(agent?.category || "productivity");
  const [tagsText, setTagsText] = useState((agent?.tags || []).join(", "));
  const [savingGeneral, setSavingGeneral] = useState(false);

  // Section C — Limits
  const settings = agent?.agent_settings || {};
  const [maxHour, setMaxHour] = useState(settings.max_runs_per_hour || 0);
  const [maxDay, setMaxDay] = useState(settings.max_runs_per_day || 0);
  const [autoPauseOn, setAutoPauseOn] = useState(!!settings.auto_pause_on_errors);
  const [autoPauseThr, setAutoPauseThr] = useState(settings.auto_pause_threshold || 5);
  const [savingLimits, setSavingLimits] = useState(false);

  // Section D — Notifications
  const nots = settings.notifications || {};
  const [notError, setNotError] = useState(!!nots.on_error);
  const [notPause, setNotPause] = useState(!!nots.on_pause);
  const [milestone, setMilestone] = useState(nots.milestone_every || 0);
  const [dailySummary, setDailySummary] = useState(!!nots.daily_summary);
  const [savingNots, setSavingNots] = useState(false);

  // Section F — Danger
  const [confirmDeleteAgent, setConfirmDeleteAgent] = useState(false);
  const [typed, setTyped] = useState("");

  const patchAgent = async (payload) => {
    const res = await fetch(`${API}/api/agents/${agentId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    return await res.json();
  };

  const saveGeneral = async () => {
    setSavingGeneral(true);
    try {
      const tags = tagsText.split(",").map((s) => s.trim()).filter(Boolean);
      const updated = await patchAgent({ name, description, category, tags });
      onAgentUpdated?.(updated.agent);
      toast.success("General settings saved");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally { setSavingGeneral(false); }
  };

  const saveLimits = async () => {
    setSavingLimits(true);
    try {
      const updated = await patchAgent({
        agent_settings: {
          max_runs_per_hour: Number(maxHour) || 0,
          max_runs_per_day: Number(maxDay) || 0,
          auto_pause_on_errors: !!autoPauseOn,
          auto_pause_threshold: Number(autoPauseThr) || 5,
        },
      });
      onAgentUpdated?.(updated.agent);
      toast.success("Limits saved");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally { setSavingLimits(false); }
  };

  const saveNots = async () => {
    setSavingNots(true);
    try {
      const updated = await patchAgent({
        agent_settings: {
          notifications: {
            on_error: !!notError,
            on_pause: !!notPause,
            milestone_every: Number(milestone) || 0,
            daily_summary: !!dailySummary,
          },
        },
      });
      onAgentUpdated?.(updated.agent);
      toast.success("Notification preferences saved");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally { setSavingNots(false); }
  };

  const deleteAgent = async () => {
    try {
      const res = await fetch(`${API}/api/agents/${agentId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: "DELETE_AGENT" }),
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Agent deleted");
      navigate("/my-agents");
    } catch (e) {
      toast.error(`Delete failed: ${e.message || e}`);
    }
  };

  const cardCls = "rounded-sm p-5";
  const cardStyle = { background: "var(--bg-card)", border: "1px solid var(--border)" };
  const inputCls = "w-full px-3 py-2 rounded-sm text-[12px] font-mono";
  const inputStyle = { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" };
  const saveBtnCls = "px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 disabled:opacity-40";

  const credits = agent?.credits_per_run || 1;
  const sellerCut = credits * 0.9;
  const withBonus = sellerCut * 1.3;

  return (
    <div data-testid="tab-settings-content" className="space-y-4">
      {/* A. General */}
      <div data-testid="settings-general-form" className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3">General</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} style={inputStyle} />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputCls} style={{ ...inputStyle, resize: "vertical" }} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Category</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputCls} style={inputStyle}>
                {CATEGORY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Tags (comma separated)</label>
              <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} className={inputCls} style={inputStyle} />
            </div>
          </div>
          <div className="text-right">
            <button onClick={saveGeneral} disabled={savingGeneral} className={saveBtnCls}>
              {savingGeneral ? <Loader2 size={10} className="inline animate-spin" /> : <><Save size={10} className="inline mr-1" /> Save Changes</>}
            </button>
          </div>
        </div>
      </div>

      {/* B. Pricing (read-only) */}
      <div className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-2">Pricing</h3>
        <div className="text-[12px] t-text-sub font-mono space-y-1">
          <div>Price per run: <span className="t-text">{credits} credits</span></div>
          <div className="text-[11px] t-text-mute">{credits} × 90% = {sellerCut.toFixed(1)} + 30% bonus = {withBonus.toFixed(2)} credits per run earnings</div>
          <div className="text-[10px] t-text-mute mt-2">Pricing is set on the Exchange listing — visit the Exchange to adjust.</div>
        </div>
      </div>

      {/* C. Limits */}
      <div data-testid="settings-limits-form" className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3">Run Limits</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Max runs/hour (0 = unlimited)</label>
            <input type="number" min="0" value={maxHour} onChange={(e) => setMaxHour(e.target.value)} className={inputCls} style={inputStyle} />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Max runs/day (0 = unlimited)</label>
            <input type="number" min="0" value={maxDay} onChange={(e) => setMaxDay(e.target.value)} className={inputCls} style={inputStyle} />
          </div>
        </div>
        <div className="mt-3 space-y-2">
          <label className="flex items-center gap-2 text-[11px] font-mono t-text-sub">
            <input type="checkbox" checked={autoPauseOn} onChange={(e) => setAutoPauseOn(e.target.checked)} className="accent-cyan-400" />
            Auto-pause after consecutive errors
          </label>
          <div>
            <label className="block text-[10px] uppercase tracking-wider t-text-mute font-mono mb-1">Auto-pause threshold</label>
            <input type="number" min="1" disabled={!autoPauseOn} value={autoPauseThr} onChange={(e) => setAutoPauseThr(e.target.value)} className={inputCls} style={inputStyle} />
          </div>
        </div>
        <div className="text-right mt-3">
          <button onClick={saveLimits} disabled={savingLimits} className={saveBtnCls}>
            {savingLimits ? <Loader2 size={10} className="inline animate-spin" /> : <><Save size={10} className="inline mr-1" /> Save Limits</>}
          </button>
        </div>
      </div>

      {/* D. Notifications */}
      <div data-testid="settings-notifications-form" className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3">Notifications</h3>
        <div className="space-y-2 text-[11px] font-mono t-text-sub">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={notError} onChange={(e) => setNotError(e.target.checked)} className="accent-cyan-400" />
            Email me on every error
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={notPause} onChange={(e) => setNotPause(e.target.checked)} className="accent-cyan-400" />
            Email me when the agent is auto-paused
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={milestone > 0} onChange={(e) => setMilestone(e.target.checked ? 100 : 0)} className="accent-cyan-400" />
            Email every
            <input type="number" min="0" value={milestone} onChange={(e) => setMilestone(e.target.value)}
                   className="w-20 px-1 py-0.5 rounded-sm font-mono text-[11px]" style={inputStyle} />
            runs (milestone)
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={dailySummary} onChange={(e) => setDailySummary(e.target.checked)} className="accent-cyan-400" />
            Daily summary email
          </label>
        </div>
        <div className="mt-3 p-2 rounded-sm bg-cyan-500/5 border border-cyan-500/20 text-[10px] t-text-sub">
          ℹ️ Email delivery wires up in a future phase — settings are saved now and will take effect once enabled.
        </div>
        <div className="text-right mt-3">
          <button onClick={saveNots} disabled={savingNots} className={saveBtnCls}>
            {savingNots ? <Loader2 size={10} className="inline animate-spin" /> : <><Save size={10} className="inline mr-1" /> Save Notifications</>}
          </button>
        </div>
      </div>

      {/* E. Scheduling — Phase 4 */}
      <SchedulingSection agentId={agentId} token={token} agent={agent} onAgentUpdated={onAgentUpdated} />

      {/* F. Danger zone */}
      <div data-testid="danger-zone" className={cardCls} style={{ ...cardStyle, borderColor: "rgba(244, 63, 94, 0.3)" }}>
        <h3 className="text-rose-400 font-semibold text-[13px] mb-3 flex items-center gap-2">
          <AlertTriangle size={13} /> Danger Zone
        </h3>
        {agent?.exchange_status === "published" && (
          <button data-testid="unpublish-btn"
            onClick={() => toast.info("Visit /exchange to delist the listing.")}
            className="block w-full mb-2 px-3 py-2 rounded-sm text-[11px] uppercase tracking-wider font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/15 text-left">
            Unpublish from Exchange
          </button>
        )}
        <button data-testid="delete-agent-btn"
          onClick={() => setConfirmDeleteAgent(true)}
          className="block w-full px-3 py-2 rounded-sm text-[11px] uppercase tracking-wider font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/15 text-left">
          <Trash2 size={11} className="inline mr-1" /> Delete this agent (cascade)
        </button>
        {confirmDeleteAgent && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setConfirmDeleteAgent(false)} />
            <div className="relative w-full max-w-md rounded-sm p-6"
                 style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-3"><AlertTriangle className="text-rose-400" size={16} /><h3 className="t-text font-bold">Delete agent?</h3></div>
              <p className="text-[12px] t-text-sub mb-4">
                This will permanently delete <span className="t-text">{agent?.name}</span> and ALL runs, logs, files, env vars, listings. This cannot be undone.
              </p>
              <p className="text-[11px] t-text-mute mb-2 font-mono uppercase tracking-wide">
                Type <span className="text-rose-400">delete</span> to confirm:
              </p>
              <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus
                     className="w-full px-3 py-2 rounded-sm text-[12px] font-mono mb-4"
                     style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }} />
              <div className="flex justify-end gap-2">
                <button onClick={() => { setConfirmDeleteAgent(false); setTyped(""); }}
                        className="px-3 py-1.5 rounded-sm text-[11px] uppercase tracking-wider font-mono t-text-sub">Cancel</button>
                <button onClick={deleteAgent} disabled={typed.toLowerCase() !== "delete"}
                        className="px-3 py-1.5 rounded-sm text-[11px] uppercase tracking-wider font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/15 disabled:opacity-40 disabled:cursor-not-allowed">
                  Delete agent
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Phase 4: SchedulingSection (Settings tab section E) ──────────── */
const PRESET_OPTIONS = [
  { value: "off",    label: "Off" },
  { value: "hourly", label: "Hourly" },
  { value: "6h",     label: "Every 6 hours" },
  { value: "daily",  label: "Daily" },
  { value: "weekly", label: "Weekly" },
];

function SchedulingSection({ agentId, token, agent, onAgentUpdated }) {
  const existing = agent?.schedule || {};
  const initialPreset = existing.enabled ? (existing.preset || "hourly") : "off";
  const [preset, setPreset] = useState(initialPreset);
  const [saving, setSaving] = useState(false);
  const [localSchedule, setLocalSchedule] = useState(existing);

  const save = async () => {
    setSaving(true);
    try {
      const enabled = preset !== "off";
      const body = enabled ? { enabled: true, preset } : { enabled: false, preset: "off" };
      const res = await fetch(`${API}/api/agents/${agentId}/schedule`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt);
      }
      const j = await res.json();
      setLocalSchedule(j.schedule || {});
      // Refresh parent's view of the agent so the next-run timestamp is consistent
      try {
        const a = await fetch(`${API}/api/agents/${agentId}`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then((r) => r.json());
        onAgentUpdated?.(a);
      } catch (_e) { /* best-effort */ }
      toast.success(enabled ? `Schedule saved · ${preset}` : "Scheduling turned off");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const cardCls = "rounded-sm p-5";
  const cardStyle = { background: "var(--bg-card)", border: "1px solid var(--border)" };
  const saveBtnCls = "px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 disabled:opacity-40";

  const isActive = !!localSchedule.enabled;
  const nextRun = localSchedule.next_run_at || null;
  const lastRun = localSchedule.last_run_at || null;
  const consecutiveFailures = Number(localSchedule.consecutive_failures || 0);

  return (
    <div data-testid="settings-scheduling-form" className={cardCls} style={cardStyle}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="t-text font-semibold text-[13px] flex items-center gap-2">
          <Activity size={13} className="text-cyan-400" /> Scheduling
        </h3>
        <span
          data-testid="schedule-status-indicator"
          className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm ${
            isActive
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "bg-zinc-500/10 t-text-mute border border-zinc-500/30"
          }`}
        >
          {isActive ? "Scheduled" : "Off"}
        </span>
      </div>

      <p className="text-[11px] t-text-sub mb-3">
        Pick a cadence and the operations hub will run this agent on a schedule.
        Paused or archived agents are skipped automatically.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">
            Run frequency
          </label>
          <select
            data-testid="schedule-preset-select"
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            className="w-full px-3 py-2 rounded-sm text-[12px] font-mono"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" }}
          >
            {PRESET_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="text-[11px] font-mono t-text-sub flex flex-col justify-end">
          <div data-testid="schedule-next-run-display" className="mb-1">
            <span className="t-text-mute uppercase text-[10px] tracking-[0.12em] mr-2">Next run</span>
            <span className="t-text">{isActive ? fmtTime(nextRun) : "—"}</span>
          </div>
          <div>
            <span className="t-text-mute uppercase text-[10px] tracking-[0.12em] mr-2">Last run</span>
            <span className="t-text">{fmtTime(lastRun)}</span>
          </div>
          {consecutiveFailures >= 1 && (
            <div className="mt-1 text-amber-400">
              <AlertTriangle size={11} className="inline mr-1" />
              {consecutiveFailures} consecutive failure{consecutiveFailures === 1 ? "" : "s"}
              {consecutiveFailures >= 3 && " · circuit breaker tripped"}
            </div>
          )}
        </div>
      </div>

      <div className="text-right">
        <button
          data-testid="save-schedule-btn"
          onClick={save}
          disabled={saving}
          className={saveBtnCls}
        >
          {saving ? <Loader2 size={10} className="inline animate-spin" /> : (
            <><Save size={10} className="inline mr-1" /> Save Schedule</>
          )}
        </button>
      </div>
    </div>
  );
}

/* ─── Phase 4: MiniAppTab ──────────────────────────────────────────── */
function MiniAppTab({ agentId, token, agent, onAgentUpdated }) {
  const slug = agent?.app_slug || agent?.id || agentId;
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const publicUrl = `${origin}/app/${slug}`;
  const embedSnippet = `<iframe src="${publicUrl}?embed=1" width="480" height="640" frameborder="0" sandbox="allow-scripts allow-same-origin"></iframe>`;

  const settings = agent?.mini_app_settings || {};
  const [visibility, setVisibility] = useState(settings.visibility || "public");
  const [coverUrl, setCoverUrl] = useState(settings.cover_url || "");
  const [inputMode, setInputMode] = useState(settings.input_mode || "json");
  const [showBranding, setShowBranding] = useState(settings.show_branding !== false);
  const [allowSharing, setAllowSharing] = useState(settings.allow_sharing !== false);
  const [saving, setSaving] = useState(false);

  const copy = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Copy failed — copy manually");
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/agents/${agentId}/mini-app`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          visibility,
          cover_url: coverUrl || null,
          input_mode: inputMode,
          show_branding: !!showBranding,
          allow_sharing: !!allowSharing,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      try {
        const a = await fetch(`${API}/api/agents/${agentId}`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then((r) => r.json());
        onAgentUpdated?.(a);
      } catch (_e) { /* best-effort */ }
      toast.success("Mini-app settings saved");
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const cardCls = "rounded-sm p-5";
  const cardStyle = { background: "var(--bg-card)", border: "1px solid var(--border)" };
  const inputCls = "w-full px-3 py-2 rounded-sm text-[12px] font-mono";
  const inputStyle = { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text)" };
  const saveBtnCls = "px-3 py-1 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 disabled:opacity-40";

  const isPublic = visibility === "public";

  return (
    <div data-testid="tab-mini-app-content" className="space-y-4">
      {/* A. Share */}
      <div className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3 flex items-center gap-2">
          <ExternalLink size={13} className="text-cyan-400" /> Share & embed
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">
              Public URL
            </label>
            <div className="flex gap-2">
              <input
                data-testid="mini-app-share-url"
                readOnly
                value={publicUrl}
                className={inputCls}
                style={inputStyle}
                onClick={(e) => e.target.select()}
              />
              <button
                data-testid="mini-app-copy-link-btn"
                onClick={() => copy(publicUrl, "URL")}
                className="px-3 py-2 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
                title="Copy public URL"
              >
                <CopyIcon size={11} />
              </button>
              <a
                href={publicUrl}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="mini-app-open-link-btn"
                className="px-3 py-2 rounded-sm text-[10px] uppercase tracking-wider font-mono t-text-sub border"
                style={{ borderColor: "var(--border)" }}
                title="Open in new tab"
              >
                <ExternalLink size={11} />
              </a>
            </div>
            {!isPublic && (
              <p className="text-[10px] text-amber-400 mt-1">
                <AlertTriangle size={10} className="inline mr-1" />
                This agent is private — only you can open this URL.
              </p>
            )}
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">
              Embed snippet
            </label>
            <div className="flex gap-2">
              <textarea
                data-testid="mini-app-embed-code"
                readOnly
                rows={2}
                value={embedSnippet}
                className={inputCls}
                style={{ ...inputStyle, resize: "none" }}
                onClick={(e) => e.target.select()}
              />
              <button
                data-testid="mini-app-copy-embed-btn"
                onClick={() => copy(embedSnippet, "Embed snippet")}
                className="px-3 py-2 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
                title="Copy embed code"
              >
                <CopyIcon size={11} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* B. Preview */}
      <div className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3 flex items-center gap-2">
          <Eye size={13} className="text-cyan-400" /> Live preview
        </h3>
        <div className="rounded-sm overflow-hidden" style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}>
          <iframe
            data-testid="mini-app-preview-iframe"
            title="Mini-app preview"
            src={publicUrl}
            className="w-full"
            style={{ height: 480, border: 0, background: "var(--bg-elevated)" }}
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
        </div>
        <p className="text-[10px] t-text-mute mt-2">
          Preview loads the same page anonymous visitors see at <code>{publicUrl}</code>.
        </p>
      </div>

      {/* C. Customization */}
      <div className={cardCls} style={cardStyle}>
        <h3 className="t-text font-semibold text-[13px] mb-3 flex items-center gap-2">
          <Edit3 size={13} className="text-cyan-400" /> Customization
        </h3>

        <div className="mb-4">
          <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-2">
            Visibility
          </label>
          <div className="flex gap-4 text-[12px] font-mono">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                value="public"
                checked={visibility === "public"}
                onChange={() => setVisibility("public")}
                data-testid="mini-app-visibility-public"
                className="accent-cyan-400"
              />
              <span>Public — anyone with the link can run it</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                value="private"
                checked={visibility === "private"}
                onChange={() => setVisibility("private")}
                data-testid="mini-app-visibility-private"
                className="accent-cyan-400"
              />
              <span>Private — only you can run it</span>
            </label>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-2">
            Input mode
          </label>
          <div className="flex gap-4 text-[12px] font-mono">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="input_mode"
                value="form"
                checked={inputMode === "form"}
                onChange={() => setInputMode("form")}
                data-testid="mini-app-input-mode-form"
                className="accent-cyan-400"
              />
              <span>Form — auto-generated fields from input_template</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="input_mode"
                value="json"
                checked={inputMode === "json"}
                onChange={() => setInputMode("json")}
                data-testid="mini-app-input-mode-json"
                className="accent-cyan-400"
              />
              <span>JSON — raw editor for advanced users</span>
            </label>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-[10px] uppercase tracking-[0.12em] t-text-mute font-mono mb-1">
            Cover image URL <span className="t-text-mute normal-case">(optional)</span>
          </label>
          <input
            data-testid="mini-app-cover-url"
            value={coverUrl}
            onChange={(e) => setCoverUrl(e.target.value)}
            placeholder="https://…"
            className={inputCls}
            style={inputStyle}
          />
        </div>

        <div className="flex gap-6 text-[12px] font-mono t-text-sub">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showBranding}
              onChange={(e) => setShowBranding(e.target.checked)}
              data-testid="mini-app-show-branding"
              className="accent-cyan-400"
            />
            Show Task Force branded header
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={allowSharing}
              onChange={(e) => setAllowSharing(e.target.checked)}
              data-testid="mini-app-allow-sharing"
              className="accent-cyan-400"
            />
            Allow social share buttons
          </label>
        </div>

        <div className="text-right mt-4">
          <button
            data-testid="save-mini-app-settings-btn"
            onClick={save}
            disabled={saving}
            className={saveBtnCls}
          >
            {saving ? <Loader2 size={10} className="inline animate-spin" /> : (
              <><Save size={10} className="inline mr-1" /> Save Mini-App Settings</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Main ──────────────────────────────────────────────────────────── */
export default function AgentControlPanel() {
  const { id } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");

  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  }), [token]);

  const loadAgent = async () => {
    setLoading(true);
    try {
      const [aRes, sRes] = await Promise.all([
        fetch(`${API}/api/agents/${id}`, { headers }),
        fetch(`${API}/api/agents/${id}/stats`, { headers }),
      ]);
      if (!aRes.ok) throw new Error(`agent: ${aRes.status}`);
      if (!sRes.ok) throw new Error(`stats: ${sRes.status}`);
      const a = await aRes.json();
      setAgent(a.agent);
      setStats(await sRes.json());
    } catch (e) {
      toast.error(`Failed to load agent: ${e.message || e}`);
      navigate("/my-agents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token && id) loadAgent(); }, [token, id]); // eslint-disable-line

  const handlePauseToggle = async () => {
    const action = agent.agent_state === "paused" ? "resume" : "pause";
    try {
      const res = await fetch(`${API}/api/agents/${id}/${action}`, {
        method: "POST", headers, body: "{}",
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success(`Agent ${action}d`);
      loadAgent();
    } catch (e) {
      toast.error(`Failed to ${action}: ${e.message || e}`);
    }
  };

  if (loading || !agent) {
    return (
      <div data-testid="agent-control-panel" className="min-h-[calc(100vh-56px)] flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-cyan-400" />
      </div>
    );
  }

  const stateDot = {
    active: "bg-emerald-400",
    paused: "bg-rose-400",
    draft: "bg-zinc-500",
    archived: "bg-zinc-700",
  }[agent.agent_state] || "bg-zinc-500";

  return (
    <div data-testid="agent-control-panel" className="min-h-[calc(100vh-56px)] px-4 sm:px-6 lg:px-10 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <Link to="/my-agents" className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-mono t-text-mute hover:text-cyan-400 mb-3">
          <ArrowLeft size={11} /> My Agents
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${stateDot}`} />
            <h1 data-testid="agent-name-header" className="text-2xl sm:text-3xl font-bold t-text truncate">{agent.name}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              data-testid="control-pause-btn"
              onClick={handlePauseToggle}
              disabled={agent.agent_state === "draft" || agent.agent_state === "archived"}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-wider font-mono ${
                agent.agent_state === "paused"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {agent.agent_state === "paused" ? <><Play size={11} /> Resume</> : <><Pause size={11} /> Pause</>}
            </button>
            <Link
              to={`/armory?agent_id=${id}`}
              className="flex items-center gap-1 px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-zinc-500/10 t-text-sub border border-zinc-500/30"
            >
              <Edit3 size={11} /> Edit in Builder
            </Link>
            {agent.exchange_status === "published" && (
              <Link
                to={`/listing/${id}`}
                className="flex items-center gap-1 px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-wider font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
              >
                <ExternalLink size={11} /> View on Exchange
              </Link>
            )}
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-[11px] uppercase tracking-wider font-mono t-text-mute mb-6">
          {agent.category && <span>{agent.category}</span>}
          <span>·</span>
          <span>{agent.exchange_status || "unlisted"}</span>
          <span>·</span>
          <span>{agent.credits_per_run} cr/run</span>
          <span>·</span>
          <span>{agent.agent_state}</span>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-[10px] uppercase tracking-[0.15em] t-text-mute font-mono mb-1">Runs · 24h</div>
            <div className="text-2xl font-bold t-text font-mono">{stats?.stats_24h?.runs ?? "—"}</div>
          </div>
          <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-[10px] uppercase tracking-[0.15em] t-text-mute font-mono mb-1">Success rate</div>
            <div className="text-2xl font-bold text-emerald-400 font-mono">{stats?.stats_24h?.success_rate ?? "—"}%</div>
          </div>
          <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-[10px] uppercase tracking-[0.15em] t-text-mute font-mono mb-1">Errors · 24h</div>
            <div className="text-2xl font-bold text-rose-400 font-mono">{stats?.stats_24h?.errors ?? "—"}</div>
          </div>
          <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-[10px] uppercase tracking-[0.15em] t-text-mute font-mono mb-1">Credits · 24h</div>
            <div className="text-2xl font-bold t-text font-mono">{stats?.stats_24h?.credits ?? "—"}</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b mb-4" style={{ borderColor: "var(--border)" }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              data-testid={t.testid}
              onClick={() => setTab(t.id)}
              className={`px-3 py-2 text-[10px] uppercase tracking-[0.12em] font-mono relative whitespace-nowrap ${
                tab === t.id ? "text-cyan-400" : "t-text-sub hover:t-text"
              }`}
            >
              {t.label}
              {!t.live && <span className="ml-1 text-[8px] t-text-mute">soon</span>}
              {tab === t.id && (
                <span className="absolute left-0 right-0 bottom-0 h-px bg-cyan-400" style={{ boxShadow: "0 0 6px rgba(34,211,238,0.6)" }} />
              )}
            </button>
          ))}
        </div>

        {/* Tab body */}
        {tab === "overview" && <OverviewTab stats={stats} />}
        {tab === "run-history" && <RunHistoryTab agentId={id} token={token} />}
        {tab === "logs" && <LogsTab agentId={id} token={token} />}
        {tab === "data" && <DataTab agentId={id} token={token} agent={agent} />}
        {tab === "settings" && (
          <SettingsTab
            agentId={id}
            token={token}
            agent={agent}
            onAgentUpdated={(a) => setAgent(a)}
            navigate={navigate}
          />
        )}
        {tab === "mini-app" && <MiniAppTab agentId={id} token={token} agent={agent} onAgentUpdated={(a) => setAgent(a)} />}
      </div>
    </div>
  );
}

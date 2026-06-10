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
  { id: "data", label: "Data & Inputs", live: false, testid: "tab-data" },
  { id: "settings", label: "Settings", live: false, testid: "tab-settings" },
  { id: "mini-app", label: "Mini-App", live: false, testid: "tab-mini-app" },
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
        {tab === "data" && <PlaceholderTab phase="Phase 3" label="Data & Inputs" />}
        {tab === "settings" && <PlaceholderTab phase="Phase 3" label="Settings" />}
        {tab === "mini-app" && <PlaceholderTab phase="Phase 4" label="Mini-App" />}
      </div>
    </div>
  );
}

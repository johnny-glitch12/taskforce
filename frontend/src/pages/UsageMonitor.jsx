import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft, Activity, Zap, AlertCircle, CheckCircle2, XCircle, Clock,
  TrendingUp, Coins, RefreshCw, Play,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL;

function StatCard({ label, value, sub, accent = "#22d3ee", icon: Icon, testid }) {
  return (
    <div
      data-testid={testid}
      className="t-card rounded-sm p-4 transition-all hover:border-opacity-80"
      style={{ background: "var(--bg-card)", border: `1px solid var(--border)` }}
    >
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon size={12} style={{ color: accent }} />}
        <span className="text-[9px] uppercase tracking-[0.2em] font-mono t-text-dim">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold font-mono t-text leading-none">{value}</div>
      {sub && <div className="text-[10px] t-text-mute mt-1.5 font-mono">{sub}</div>}
    </div>
  );
}

function DailyBarChart({ daily }) {
  const max = Math.max(1, ...daily.map((d) => d.runs));
  return (
    <div className="t-card rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mb-1">Execution Volume</div>
          <div className="text-[12px] t-text font-medium">Last {daily.length} days</div>
        </div>
        <div className="flex items-center gap-3 text-[9px] font-mono uppercase tracking-wider">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm" style={{ background: "#22d3ee" }} /> <span className="t-text-mute">Success</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm" style={{ background: "#fb7185" }} /> <span className="t-text-mute">Failed</span>
          </span>
        </div>
      </div>
      <div className="flex items-end gap-1 h-40" data-testid="usage-volume-chart">
        {daily.map((d) => {
          const total = d.runs || 0;
          const sH = total ? (d.success / max) * 100 : 0;
          const fH = total ? (d.failed / max) * 100 : 0;
          return (
            <div key={d.date} className="flex-1 flex flex-col justify-end group relative">
              {total === 0 && (
                <div className="absolute inset-x-0 bottom-0 h-[2px] rounded-sm" style={{ background: "var(--border)" }} />
              )}
              {d.failed > 0 && (
                <div className="w-full rounded-t-sm" style={{ background: "#fb7185", height: `${fH}%` }} />
              )}
              {d.success > 0 && (
                <div className="w-full" style={{ background: "#22d3ee", height: `${sH}%`, borderTopLeftRadius: d.failed ? 0 : 2, borderTopRightRadius: d.failed ? 0 : 2 }} />
              )}
              <div className="absolute -top-7 left-1/2 -translate-x-1/2 hidden group-hover:block text-[10px] font-mono whitespace-nowrap px-2 py-0.5 rounded-sm pointer-events-none"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                {d.date}: {total} runs
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[9px] t-text-dim font-mono">
        <span>{daily[0]?.date.slice(5)}</span>
        <span>{daily[Math.floor(daily.length / 2)]?.date.slice(5)}</span>
        <span>{daily[daily.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const ok = status === "success";
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-bold font-mono uppercase tracking-wider"
      style={{
        background: ok ? "rgba(16,185,129,0.1)" : "rgba(251,113,133,0.12)",
        color: ok ? "#34d399" : "#fb7185",
        border: `1px solid ${ok ? "rgba(16,185,129,0.3)" : "rgba(251,113,133,0.3)"}`,
      }}
    >
      {ok ? <CheckCircle2 size={9} /> : <XCircle size={9} />} {status}
    </span>
  );
}

function RunsTable({ runs }) {
  if (!runs.length) {
    return (
      <div className="t-card rounded-sm p-8 text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <Activity size={20} className="t-text-dim mx-auto mb-2" />
        <div className="text-[12px] t-text font-medium mb-1">No executions yet</div>
        <div className="text-[11px] t-text-dim">Hit "Run Now" to log your first execution.</div>
      </div>
    );
  }
  return (
    <div className="t-card rounded-sm overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <table className="w-full" data-testid="usage-runs-table">
        <thead>
          <tr className="text-[9px] font-mono uppercase tracking-[0.2em] t-text-dim" style={{ borderBottom: "1px solid var(--border)" }}>
            <th className="text-left px-4 py-2.5 font-semibold">Run ID</th>
            <th className="text-left px-4 py-2.5 font-semibold">Status</th>
            <th className="text-left px-4 py-2.5 font-semibold">Trigger</th>
            <th className="text-right px-4 py-2.5 font-semibold">Duration</th>
            <th className="text-right px-4 py-2.5 font-semibold">Credits</th>
            <th className="text-right px-4 py-2.5 font-semibold">Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.id}
              data-testid={`run-row-${r.id}`}
              className="text-[11px] font-mono transition-colors hover:bg-[var(--bg-card-hover)]"
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <td className="px-4 py-2.5 t-text-sub truncate">{r.id.slice(0, 12)}…</td>
              <td className="px-4 py-2.5"><StatusPill status={r.status} /></td>
              <td className="px-4 py-2.5 t-text-mute uppercase tracking-wide">{r.trigger || "manual"}</td>
              <td className="px-4 py-2.5 text-right t-text">{r.duration_ms}ms</td>
              <td className="px-4 py-2.5 text-right t-text-sub">{r.credits_spent}</td>
              <td className="px-4 py-2.5 text-right t-text-dim">{new Date(r.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function UsageMonitor() {
  const { id } = useParams();
  const { token } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const [running, setRunning] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    try {
      const [a, r] = await Promise.all([
        fetch(`${API}/api/deployments/${id}/analytics?days=30`, { headers }).then((res) => res.json()),
        fetch(`${API}/api/deployments/${id}/runs?limit=50`, { headers }).then((res) => res.json()),
      ]);
      if (a.detail) {
        toast.error(a.detail);
      } else {
        setAnalytics(a);
        setRuns(r.runs || []);
      }
    } catch (e) {
      toast.error("Failed to load analytics.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!live) return;
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, [live, load]);

  const triggerRun = async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API}/api/deployments/${id}/run`, { method: "POST", headers });
      const data = await res.json();
      if (data.allowed) {
        toast.success(`Run ${data.success ? "succeeded" : "failed"} · ${data.duration_ms}ms`);
        load();
      } else {
        toast.error(data.message || "Run limit reached.");
      }
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen t-bg flex items-center justify-center">
        <div className="text-[12px] t-text-dim font-mono tracking-widest uppercase animate-pulse">Loading analytics…</div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="min-h-screen t-bg px-4 sm:px-8 py-8">
        <div className="max-w-3xl mx-auto t-card rounded-sm p-8 text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <AlertCircle size={24} className="text-rose-400 mx-auto mb-3" />
          <div className="text-[14px] t-text font-medium mb-1">Deployment not found</div>
          <Link to="/my-deployments" className="text-[11px] text-cyan-400 hover:underline">← Back to My Deployments</Link>
        </div>
      </div>
    );
  }

  const t = analytics.totals;
  const l = analytics.latency_ms;
  const q = analytics.monthly_quota;
  const quotaPct = q.limit ? Math.min(100, (q.used / q.limit) * 100) : 0;
  const quotaNear = quotaPct >= 80;

  return (
    <div data-testid="usage-monitor-page" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
          <div>
            <Link to="/my-deployments" data-testid="back-to-deployments"
              className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.2em] t-text-dim hover:text-cyan-400 mb-3">
              <ArrowLeft size={11} /> My Deployments
            </Link>
            <h1 className="text-3xl font-bold t-text tracking-tight">
              {analytics.deployment_name || "Deployment"}
            </h1>
            <div className="text-[11px] t-text-mute mt-1 font-mono">
              Usage Monitor · Last {analytics.window_days} days · {t.runs} executions
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              data-testid="usage-monitor-live-toggle"
              onClick={() => setLive((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-3 py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm transition-all ${
                live ? "text-black" : "t-text-sub"
              }`}
              style={{
                background: live ? "#10b981" : "var(--bg-card)",
                border: `1px solid ${live ? "#10b981" : "var(--border)"}`,
                fontWeight: live ? 700 : 500,
              }}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${live ? "animate-pulse" : ""}`}
                style={{ background: live ? "#000" : "#71717a" }} />
              {live ? "LIVE" : "PAUSED"}
            </button>
            <button
              data-testid="usage-monitor-refresh"
              onClick={load}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm t-text-sub hover:t-text"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <RefreshCw size={11} /> Refresh
            </button>
            <button
              data-testid="usage-monitor-run-now"
              onClick={triggerRun}
              disabled={running}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm bg-cyan-400 text-black font-bold hover:bg-cyan-300 disabled:opacity-50"
            >
              <Play size={11} /> {running ? "Running…" : "Run Now"}
            </button>
          </div>
        </div>

        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard
            testid="kpi-total-runs"
            label="Total Runs"
            value={t.runs.toLocaleString()}
            sub={`${t.successes} ok · ${t.failures} failed`}
            icon={Activity}
            accent="#22d3ee"
          />
          <StatCard
            testid="kpi-success-rate"
            label="Success Rate"
            value={`${t.success_rate}%`}
            sub={t.success_rate >= 95 ? "Healthy" : t.success_rate >= 80 ? "Watch" : "At risk"}
            icon={CheckCircle2}
            accent={t.success_rate >= 95 ? "#10b981" : t.success_rate >= 80 ? "#fbbf24" : "#fb7185"}
          />
          <StatCard
            testid="kpi-p95-latency"
            label="P95 Latency"
            value={`${l.p95}ms`}
            sub={`P50 ${l.p50}ms · P99 ${l.p99}ms`}
            icon={Zap}
            accent="#a78bfa"
          />
          <StatCard
            testid="kpi-credits-spent"
            label="Credits Spent"
            value={t.credits_spent.toLocaleString()}
            sub={`${analytics.window_days}-day window`}
            icon={Coins}
            accent="#fbbf24"
          />
        </div>

        {/* Volume Chart + Quota */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-6">
          <div className="lg:col-span-2">
            <DailyBarChart daily={analytics.daily} />
          </div>
          <div className="t-card rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mb-1">Monthly Quota</div>
            <div className="text-[12px] t-text font-medium mb-4">{q.used.toLocaleString()} / {q.limit.toLocaleString()} runs</div>
            <div className="h-2 rounded-sm overflow-hidden" style={{ background: "var(--bg-elevated)" }}>
              <div
                data-testid="quota-bar-fill"
                className="h-full transition-all"
                style={{ width: `${quotaPct}%`, background: quotaNear ? "#fb7185" : "#22d3ee" }}
              />
            </div>
            <div className="flex justify-between mt-1.5 text-[9px] font-mono t-text-dim">
              <span>{quotaPct.toFixed(1)}%</span>
              <span>{q.remaining.toLocaleString()} left</span>
            </div>
            {quotaNear && (
              <div className="mt-3 text-[10px] text-rose-400 flex items-start gap-1 font-mono">
                <AlertCircle size={10} className="shrink-0 mt-0.5" />
                Near monthly limit — upgrade this deployment to keep running.
              </div>
            )}

            <div className="mt-6 pt-4 border-t" style={{ borderColor: "var(--border)" }}>
              <div className="text-[9px] uppercase tracking-[0.2em] font-mono t-text-dim mb-2">Latency Distribution</div>
              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                <div>
                  <div className="t-text-dim">avg</div>
                  <div className="t-text">{l.avg}ms</div>
                </div>
                <div>
                  <div className="t-text-dim">max</div>
                  <div className="t-text">{l.max}ms</div>
                </div>
                <div>
                  <div className="t-text-dim">min</div>
                  <div className="t-text">{l.min}ms</div>
                </div>
                <div>
                  <div className="t-text-dim">P99</div>
                  <div className="t-text" style={{ color: l.p99 > 5000 ? "#fb7185" : undefined }}>{l.p99}ms</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Errors */}
        {analytics.recent_errors?.length > 0 && (
          <div className="t-card rounded-sm p-4 mb-6" style={{ background: "rgba(251,113,133,0.04)", border: "1px solid rgba(251,113,133,0.25)" }}>
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle size={12} className="text-rose-400" />
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-rose-400">Recent Errors</span>
            </div>
            <ul className="space-y-1.5 text-[11px] font-mono t-text-sub">
              {analytics.recent_errors.map((e, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Clock size={9} className="t-text-dim shrink-0 mt-1" />
                  <div className="flex-1">
                    <span className="t-text-dim">{new Date(e.started_at).toLocaleString()} · </span>
                    <span>{e.error}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Execution Log Table */}
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[12px] font-mono uppercase tracking-[0.2em] t-text-sub flex items-center gap-2">
            <TrendingUp size={11} /> Execution Log
          </h2>
          <span className="text-[10px] font-mono t-text-dim">{runs.length} of {t.runs}</span>
        </div>
        <RunsTable runs={runs} />
      </div>
    </div>
  );
}

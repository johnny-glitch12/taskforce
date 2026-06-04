/**
 * EconomicsDashboard — owner-only platform economics view (/admin/economics).
 *
 * Pulls /api/admin/economics and renders revenue vs cost vs margin in $$ and %.
 * Per-model breakdown table, platform-vs-BYOK split, top spenders, and a daily
 * revenue/cost line for the selected window.
 */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import {
  DollarSign, TrendingUp, Activity, Users, Zap, Cpu,
  ArrowUpRight, ArrowDownRight, Loader2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const WINDOW_OPTIONS = [
  { id: 7,   label: "7d"   },
  { id: 30,  label: "30d"  },
  { id: 90,  label: "90d"  },
  { id: 365, label: "1y"   },
];

function StatCard({ label, value, sub, icon: Icon, accent, testId }) {
  return (
    <div
      data-testid={testId}
      className="rounded-sm p-5"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-mono uppercase tracking-[0.18em] t-text-mute">{label}</span>
        <Icon size={14} style={{ color: accent || "var(--cyan)" }} />
      </div>
      <div className="text-2xl font-bold t-text font-mono" style={{ color: accent || "var(--text)" }}>
        {value}
      </div>
      {sub && <div className="text-[11px] font-mono t-text-dim mt-2">{sub}</div>}
    </div>
  );
}

function fmtUsd(n) {
  if (n === null || n === undefined) return "$0.00";
  const v = Number(n);
  if (Math.abs(v) >= 1000) return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (Math.abs(v) >= 1) return `$${v.toFixed(2)}`;
  return `$${v.toFixed(4)}`;
}

function fmtInt(n) {
  return (n ?? 0).toLocaleString();
}

function ProgressBar({ value, total, color }) {
  const pct = total > 0 ? Math.min(100, (value / total) * 100) : 0;
  return (
    <div className="h-1.5 rounded-sm overflow-hidden" style={{ background: "var(--bg-card-hover)" }}>
      <div className="h-full transition-all" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export default function EconomicsDashboard() {
  const { token, isOwner } = useAuth();
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/api/admin/economics?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json().then((j) => ({ ok: r.ok, status: r.status, body: j })))
      .then(({ ok, body }) => {
        if (cancelled) return;
        if (!ok) {
          setError(body?.detail?.message || body?.detail || "Failed to load");
          setData(null);
        } else {
          setData(body);
          setError(null);
        }
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [days, token]);

  if (!isOwner) {
    return (
      <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-6">
        <div data-testid="economics-owner-only" className="t-text-mute font-mono text-sm">Owner only.</div>
      </div>
    );
  }

  return (
    <div data-testid="economics-dashboard" className="min-h-[calc(100vh-56px)] px-6 lg:px-10 py-10">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
          <div>
            <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Activity size={11} className="text-cyan-400" />
              <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">OWNER ECONOMICS</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight t-text">Platform Economics</h1>
            <p className="text-sm t-text-sub mt-2">
              Dynamic credit revenue vs API cost. Platform charges {data ? data.platform_margin.toFixed(1) : "—"}× provider cost on platform-key calls (≈60% gross margin).
            </p>
          </div>

          <div data-testid="economics-window-toggle" className="inline-flex rounded-sm overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            {WINDOW_OPTIONS.map((w) => (
              <button
                key={w.id}
                data-testid={`econ-window-${w.id}`}
                onClick={() => setDays(w.id)}
                className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-[0.12em] transition-all"
                style={{
                  background: days === w.id ? "var(--cyan)" : "transparent",
                  color: days === w.id ? "#000" : "var(--text-sub)",
                  fontWeight: days === w.id ? 700 : 500,
                  borderLeft: days === w.id ? "none" : "1px solid var(--border)",
                }}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin t-text-mute" size={24} />
          </div>
        )}
        {error && (
          <div data-testid="economics-error" className="t-text rounded-sm p-4" style={{ background: "rgba(244,63,94,0.06)", border: "1px solid rgba(244,63,94,0.3)" }}>
            <div className="text-rose-400 font-mono text-sm">{error}</div>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Top Stat Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <StatCard
                testId="econ-card-revenue"
                label="Revenue"
                value={fmtUsd(data.window.total_revenue_usd)}
                sub={`${fmtInt(data.window.total_credits_spent)} credits spent`}
                icon={DollarSign}
                accent="#22d3ee"
              />
              <StatCard
                testId="econ-card-cost"
                label="API Cost"
                value={fmtUsd(data.window.total_api_cost_usd)}
                sub={`${fmtInt(data.window.calls)} calls`}
                icon={Cpu}
                accent="#f43f5e"
              />
              <StatCard
                testId="econ-card-margin"
                label="Gross Margin"
                value={fmtUsd(data.window.gross_margin_usd)}
                sub={`${data.window.gross_margin_pct.toFixed(1)}% margin`}
                icon={TrendingUp}
                accent="#10b981"
              />
              <StatCard
                testId="econ-card-users"
                label="Active Users"
                value={fmtInt(data.window.active_users)}
                sub={`${fmtInt(data.window.input_tokens + data.window.output_tokens)} tokens`}
                icon={Users}
                accent="#a855f7"
              />
            </div>

            {/* Lifetime Strip */}
            <div data-testid="econ-lifetime" className="rounded-sm p-4 mb-6" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] t-text-mute mb-3">Lifetime</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono">
                <div>
                  <div className="text-[10px] t-text-dim uppercase tracking-wider">Revenue</div>
                  <div data-testid="econ-lifetime-revenue" className="text-lg font-bold text-cyan-400">{fmtUsd(data.lifetime.revenue_usd)}</div>
                </div>
                <div>
                  <div className="text-[10px] t-text-dim uppercase tracking-wider">API Cost</div>
                  <div className="text-lg font-bold text-rose-400">{fmtUsd(data.lifetime.api_cost_usd)}</div>
                </div>
                <div>
                  <div className="text-[10px] t-text-dim uppercase tracking-wider">Credits</div>
                  <div className="text-lg font-bold t-text">{fmtInt(data.lifetime.credits)}</div>
                </div>
                <div>
                  <div className="text-[10px] t-text-dim uppercase tracking-wider">Calls</div>
                  <div className="text-lg font-bold t-text">{fmtInt(data.lifetime.calls)}</div>
                </div>
              </div>
            </div>

            {/* Per-Model Breakdown */}
            <div data-testid="econ-per-model" className="rounded-sm mb-6" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
                <Zap size={12} className="text-cyan-400" />
                <span className="text-[11px] font-mono uppercase tracking-[0.18em] t-text">Per-Model Breakdown</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[12px] font-mono">
                  <thead>
                    <tr className="t-text-mute uppercase tracking-wider text-[10px]" style={{ borderBottom: "1px solid var(--border)" }}>
                      <th className="px-4 py-2 text-left">Model</th>
                      <th className="px-4 py-2 text-right">Calls</th>
                      <th className="px-4 py-2 text-right">Tokens (in/out)</th>
                      <th className="px-4 py-2 text-right">API Cost</th>
                      <th className="px-4 py-2 text-right">Revenue</th>
                      <th className="px-4 py-2 text-right">Margin</th>
                      <th className="px-4 py-2 text-left w-32">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.per_model.length === 0 ? (
                      <tr><td colSpan="7" className="px-4 py-6 text-center t-text-dim">No dynamic-billed calls yet in this window.</td></tr>
                    ) : data.per_model.map((row) => {
                      const margin = row.revenue_usd - row.api_cost_usd;
                      const pct = data.window.total_revenue_usd > 0 ? (row.revenue_usd / data.window.total_revenue_usd) * 100 : 0;
                      return (
                        <tr key={row.model} data-testid={`econ-model-row-${row.model}`} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td className="px-4 py-3 t-text">{row.model}</td>
                          <td className="px-4 py-3 text-right t-text">{fmtInt(row.calls)}</td>
                          <td className="px-4 py-3 text-right t-text-sub text-[11px]">{fmtInt(row.input_tokens)} / {fmtInt(row.output_tokens)}</td>
                          <td className="px-4 py-3 text-right text-rose-400">{fmtUsd(row.api_cost_usd)}</td>
                          <td className="px-4 py-3 text-right text-cyan-400">{fmtUsd(row.revenue_usd)}</td>
                          <td className="px-4 py-3 text-right text-emerald-400">{fmtUsd(margin)}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="flex-1"><ProgressBar value={row.revenue_usd} total={data.window.total_revenue_usd} color="#22d3ee" /></div>
                              <span className="text-[10px] t-text-dim w-10 text-right">{pct.toFixed(0)}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Key Source split + Top Spenders */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              {/* Key Source */}
              <div data-testid="econ-key-source" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] t-text mb-4">Platform vs BYOK</div>
                {Object.keys(data.by_key_source).length === 0 ? (
                  <div className="text-[12px] t-text-dim font-mono">No calls in window.</div>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(data.by_key_source).map(([src, v]) => (
                      <div key={src} data-testid={`econ-key-source-${src}`}>
                        <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                          <span className="t-text uppercase tracking-wider">{src}</span>
                          <span className="t-text-sub">{fmtInt(v.calls)} calls · {fmtUsd(v.revenue_usd)} rev</span>
                        </div>
                        <ProgressBar
                          value={v.revenue_usd}
                          total={data.window.total_revenue_usd}
                          color={src === "byok" ? "#a855f7" : "#22d3ee"}
                        />
                        <div className="flex items-center justify-between text-[10px] font-mono t-text-dim mt-1.5">
                          <span><ArrowDownRight size={10} className="inline mr-1 text-rose-400" />API cost {fmtUsd(v.api_cost_usd)}</span>
                          <span><ArrowUpRight size={10} className="inline mr-1 text-emerald-400" />Margin {fmtUsd(v.revenue_usd - v.api_cost_usd)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Top Spenders */}
              <div data-testid="econ-top-spenders" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] t-text mb-4">Top Spenders ({days}d)</div>
                {data.top_spenders.length === 0 ? (
                  <div className="text-[12px] t-text-dim font-mono">No spend yet.</div>
                ) : (
                  <div className="space-y-2 max-h-[280px] overflow-y-auto">
                    {data.top_spenders.slice(0, 10).map((u, i) => (
                      <div key={u.email + i} data-testid={`econ-top-${i}`} className="flex items-center justify-between text-[11px] font-mono px-2 py-1.5 rounded-sm" style={{ background: "var(--bg-card-hover)" }}>
                        <span className="t-text truncate max-w-[200px]" title={u.email}>{u.email}</span>
                        <span className="text-cyan-400 font-bold">{fmtInt(u.credits)}cr</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Daily Sparkline (text-based to avoid heavy chart libs) */}
            <div data-testid="econ-daily" className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="text-[11px] font-mono uppercase tracking-[0.18em] t-text mb-4">Daily Revenue / Cost</div>
              {data.daily.length === 0 ? (
                <div className="text-[12px] t-text-dim font-mono">No activity in window.</div>
              ) : (
                <DailyBars rows={data.daily} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function DailyBars({ rows }) {
  const maxRev = Math.max(...rows.map((r) => r.revenue_usd), 0.0001);
  return (
    <div className="flex items-end gap-1 h-[140px] overflow-x-auto">
      {rows.map((r) => {
        const revH = Math.max(2, (r.revenue_usd / maxRev) * 120);
        const costH = Math.max(0, (r.api_cost_usd / maxRev) * 120);
        return (
          <div key={r.date} className="flex flex-col items-center gap-1 min-w-[18px]" title={`${r.date}: rev ${r.revenue_usd}, cost ${r.api_cost_usd}`}>
            <div className="flex items-end gap-[1px]">
              <div className="w-[7px] rounded-sm" style={{ height: revH, background: "#22d3ee" }} />
              <div className="w-[7px] rounded-sm" style={{ height: costH, background: "#f43f5e" }} />
            </div>
            <div className="text-[8px] t-text-dim font-mono">{r.date.slice(-2)}</div>
          </div>
        );
      })}
    </div>
  );
}

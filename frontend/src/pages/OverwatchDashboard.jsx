import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  DollarSign, Users, BarChart3, Cpu, RefreshCw,
  AlertTriangle, Skull, Shield, Activity, Zap,
  TrendingUp, TrendingDown, Loader2,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Mock data generators (real APIs would replace these) ─── */
function generateRevenueData() {
  const days = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date(); d.setDate(d.getDate() - i);
    days.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      subscriptions: Math.round(800 + Math.random() * 600),
      marketplace: Math.round(200 + Math.random() * 400),
    });
  }
  return days;
}

const CATEGORY_DATA = [
  { name: "Web3 Trackers", value: 34, color: "#22d3ee" },
  { name: "Lead Generation", value: 28, color: "#10b981" },
  { name: "Customer Support", value: 19, color: "#8b5cf6" },
  { name: "Data Analysis", value: 12, color: "#f59e0b" },
  { name: "Code Review", value: 7, color: "#ef4444" },
];

const TOP_AGENTS = [
  { id: 1, name: "DeFi Whale Tracker", creator: "@DataWiz", executions: 4287, yield: 1243.50, status: "running" },
  { id: 2, name: "Outbound SDR v3", creator: "@SalesForge", executions: 3891, yield: 987.20, status: "running" },
  { id: 3, name: "CSAT Auto-Resolver", creator: "@CXMaster", executions: 2456, yield: 734.80, status: "running" },
  { id: 4, name: "ETL Pipeline Bot", creator: "@DataWiz", executions: 1893, yield: 567.90, status: "running" },
  { id: 5, name: "Code Reviewer Pro", creator: "@CodePilot", executions: 1567, yield: 423.10, status: "running" },
];

/* ─── KPI Card ─── */
function KPICard({ label, value, icon: Icon, color, trend, trendValue, prefix = "" }) {
  const isUp = trend === "up";
  return (
    <div
      data-testid={`kpi-${label.toLowerCase().replace(/\s/g, "-")}`}
      className="rounded-sm p-5"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1a1a1e" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-zinc-500">{label}</span>
        <Icon size={14} style={{ color }} />
      </div>
      <p className="text-2xl font-bold font-mono" style={{ color }}>
        {prefix}{typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {trendValue && (
        <div className="flex items-center gap-1 mt-2">
          {isUp ? <TrendingUp size={11} className="text-emerald-400" /> : <TrendingDown size={11} className="text-red-400" />}
          <span className={`text-[10px] font-mono ${isUp ? "text-emerald-400" : "text-red-400"}`}>
            {trendValue}
          </span>
          <span className="text-[10px] font-mono text-zinc-600">vs last period</span>
        </div>
      )}
    </div>
  );
}

/* ─── Custom Tooltip ─── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-black border border-zinc-800 rounded-sm px-3 py-2 shadow-xl">
      <p className="text-[10px] font-mono text-zinc-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-[11px] font-mono">
          <div className="w-2 h-2 rounded-none" style={{ background: p.color }} />
          <span className="text-zinc-400">{p.name}:</span>
          <span className="text-zinc-200 font-semibold">${p.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── Donut Label ─── */
function DonutLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  if (percent < 0.08) return null;
  return (
    <text x={x} y={y} fill="#e4e4e7" textAnchor="middle" dominantBaseline="central" fontSize={10} fontFamily="JetBrains Mono, monospace">
      {(percent * 100).toFixed(0)}%
    </text>
  );
}

export default function OverwatchDashboard() {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [revenueData] = useState(generateRevenueData);
  const [agents, setAgents] = useState(TOP_AGENTS);
  const [securityStats, setSecurityStats] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/security/stats`, { headers });
      if (res.ok) setSecurityStats(await res.json());
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) fetchData(); }, [token, fetchData]);

  const killAgent = (id) => {
    setAgents((prev) => prev.map((a) => a.id === id ? { ...a, status: "killed" } : a));
    toast.success("Agent terminated.", { icon: <Skull size={14} className="text-red-400" /> });
  };

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-52px)] flex items-center justify-center bg-black">
        <Loader2 size={24} className="text-cyan-400 animate-spin" />
      </div>
    );
  }

  const totalSub = revenueData.reduce((s, d) => s + d.subscriptions, 0);
  const totalMkt = revenueData.reduce((s, d) => s + d.marketplace, 0);
  const dailyNet = Math.round((totalSub + totalMkt) / 30);
  const computeBurn = Math.round(dailyNet * 0.31);

  return (
    <div data-testid="overwatch-dashboard" className="min-h-[calc(100vh-52px)] bg-black px-4 sm:px-6 lg:px-8 py-6">
      <div className="max-w-7xl mx-auto">
        {/* ── Header ── */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-2 h-2 bg-cyan-400 animate-pulse" />
              <h1 data-testid="overwatch-title" className="text-xl sm:text-2xl font-bold text-zinc-200 tracking-tight font-mono uppercase">
                Overwatch
              </h1>
              <span className="text-[9px] font-mono tracking-[0.2em] text-cyan-400 bg-cyan-400/8 border border-cyan-400/15 px-2 py-0.5 rounded-sm">
                LIVE
              </span>
            </div>
            <p className="text-[12px] font-mono text-zinc-600">
              Master analytics command center — {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </p>
          </div>
          <button
            onClick={fetchData}
            data-testid="refresh-overwatch-btn"
            className="px-4 py-2 rounded-sm text-[11px] font-mono font-bold tracking-wide uppercase flex items-center gap-2 text-zinc-400 hover:text-cyan-400 hover:border-cyan-400/30 transition-all"
            style={{ background: "transparent", border: "1px solid #27272a" }}
          >
            <RefreshCw size={12} /> Refresh Intel
          </button>
        </div>

        {/* ═══ ROW 1: Executive KPIs ═══ */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <KPICard label="Daily Net Income" value={dailyNet} icon={DollarSign} color="#22d3ee" prefix="$" trend="up" trendValue="+12.4%" />
          <KPICard label="Active Subscriptions" value={847} icon={Users} color="#a1a1aa" trend="up" trendValue="+23 this week" />
          <KPICard label="Exchange Volume (20%)" value={Math.round(totalMkt * 0.2)} icon={BarChart3} color="#10b981" prefix="$" trend="up" trendValue="+8.7%" />
          <KPICard label="Compute Burn Rate" value={computeBurn} icon={Cpu} color={computeBurn > dailyNet * 0.4 ? "#ef4444" : "#10b981"} prefix="$" trend="down" trendValue="-3.2%" />
        </div>

        {/* ═══ ROW 2: Charts ═══ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-6">
          {/* Revenue Split — 30 Day Stacked Bar */}
          <div
            data-testid="revenue-chart"
            className="lg:col-span-2 rounded-sm p-5"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1a1a1e" }}
          >
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-[13px] font-mono font-bold text-zinc-200 tracking-wide uppercase">Revenue Split</h3>
                <p className="text-[10px] font-mono text-zinc-600 mt-0.5">Subscriptions vs Exchange — Last 30 Days</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500">
                  <div className="w-2.5 h-2.5 rounded-none bg-cyan-400" /> Subscriptions
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500">
                  <div className="w-2.5 h-2.5 rounded-none bg-emerald-500" /> Exchange
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={revenueData} barGap={1}>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#52525b", fontFamily: "JetBrains Mono" }} tickLine={false} axisLine={{ stroke: "#1a1a1e" }} interval={4} />
                <YAxis tick={{ fontSize: 9, fill: "#52525b", fontFamily: "JetBrains Mono" }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}`} width={50} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(34,211,238,0.03)" }} />
                <Bar dataKey="subscriptions" name="Subscriptions" stackId="rev" fill="#22d3ee" radius={[1, 1, 0, 0]} />
                <Bar dataKey="marketplace" name="Exchange" stackId="rev" fill="#10b981" radius={[1, 1, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Top Categories Donut */}
          <div
            data-testid="category-chart"
            className="rounded-sm p-5"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1a1a1e" }}
          >
            <h3 className="text-[13px] font-mono font-bold text-zinc-200 tracking-wide uppercase mb-1">Top Categories</h3>
            <p className="text-[10px] font-mono text-zinc-600 mb-4">Highest renting agent categories</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={CATEGORY_DATA}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  labelLine={false}
                  label={DonutLabel}
                >
                  {CATEGORY_DATA.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2">
              {CATEGORY_DATA.map((c) => (
                <div key={c.name} className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500">
                  <div className="w-2 h-2 rounded-none" style={{ background: c.color }} /> {c.name}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══ ROW 3: Live Execution Feed ═══ */}
        <div
          data-testid="live-feed"
          className="rounded-sm overflow-hidden"
          style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1a1a1e" }}
        >
          <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid #1a1a1e" }}>
            <div className="flex items-center gap-2">
              <Activity size={13} className="text-cyan-400" />
              <span className="text-[12px] font-mono font-bold text-zinc-200 tracking-wide uppercase">Live Execution Feed</span>
              <span className="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/15 px-1.5 py-0.5 rounded-sm">
                {agents.filter(a => a.status === "running").length} ACTIVE
              </span>
            </div>
            {securityStats && (
              <div className="flex items-center gap-3 text-[10px] font-mono">
                <span className="text-zinc-500 flex items-center gap-1"><Shield size={10} className="text-cyan-400" /> {securityStats.total_audits} audits</span>
                <span className="text-zinc-500 flex items-center gap-1"><AlertTriangle size={10} className="text-amber-400" /> {securityStats.blocked} blocked</span>
              </div>
            )}
          </div>

          {/* Table Header */}
          <div className="grid grid-cols-12 gap-2 px-5 py-2.5 text-[9px] font-mono tracking-[0.15em] uppercase text-zinc-600" style={{ borderBottom: "1px solid #1a1a1e" }}>
            <div className="col-span-1">#</div>
            <div className="col-span-3">Agent Name</div>
            <div className="col-span-2">Creator</div>
            <div className="col-span-2 text-right">Executions Today</div>
            <div className="col-span-2 text-right">Gross Yield</div>
            <div className="col-span-2 text-right">Override</div>
          </div>

          {/* Rows */}
          {agents.map((agent, i) => (
            <div
              key={agent.id}
              data-testid={`agent-row-${agent.id}`}
              className={`grid grid-cols-12 gap-2 px-5 py-3 items-center transition-all ${
                agent.status === "killed" ? "opacity-30" : "hover:bg-white/[0.02]"
              }`}
              style={i < agents.length - 1 ? { borderBottom: "1px solid rgba(26,26,30,0.8)" } : {}}
            >
              <div className="col-span-1">
                <span className="text-[11px] font-mono text-zinc-600">{String(i + 1).padStart(2, "0")}</span>
              </div>
              <div className="col-span-3 flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-none ${agent.status === "running" ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
                <span className="text-[12px] font-mono text-zinc-200 truncate">{agent.name}</span>
              </div>
              <div className="col-span-2">
                <span className="text-[11px] font-mono text-zinc-500">{agent.creator}</span>
              </div>
              <div className="col-span-2 text-right">
                <span className="text-[12px] font-mono text-zinc-300">{agent.executions.toLocaleString()}</span>
              </div>
              <div className="col-span-2 text-right">
                <span className="text-[12px] font-mono text-emerald-400 font-semibold">${agent.yield.toLocaleString()}</span>
              </div>
              <div className="col-span-2 text-right">
                {agent.status === "running" ? (
                  <button
                    onClick={() => killAgent(agent.id)}
                    data-testid={`kill-agent-${agent.id}`}
                    className="px-2.5 py-1 text-[9px] font-mono font-bold tracking-[0.1em] uppercase text-red-400 rounded-sm hover:bg-red-500/15 hover:text-red-300 transition-all"
                    style={{ border: "1px solid rgba(239,68,68,0.25)" }}
                  >
                    <span className="flex items-center gap-1"><Skull size={10} /> KILL AGENT</span>
                  </button>
                ) : (
                  <span className="text-[10px] font-mono text-red-500/50 tracking-wide">TERMINATED</span>
                )}
              </div>
            </div>
          ))}

          {/* Summary bar */}
          <div className="px-5 py-3 flex items-center justify-between" style={{ borderTop: "1px solid #1a1a1e", background: "rgba(34,211,238,0.02)" }}>
            <span className="text-[10px] font-mono text-zinc-600">
              <Zap size={10} className="inline text-cyan-400 mr-1" />
              Total Executions: <span className="text-zinc-300 font-semibold">{agents.reduce((s, a) => s + a.executions, 0).toLocaleString()}</span>
            </span>
            <span className="text-[10px] font-mono text-zinc-600">
              Total Yield: <span className="text-emerald-400 font-semibold">${agents.reduce((s, a) => s + a.yield, 0).toLocaleString()}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

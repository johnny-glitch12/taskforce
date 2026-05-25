import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/App";
import { Link } from "react-router-dom";
import {
  BarChart3, Package, Zap, DollarSign, Shield, Clock,
  TrendingUp, RefreshCw, Loader2, Plus, ExternalLink,
  GitBranch, CheckCircle2, FileText, Eye, Trash2,
} from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_STYLES = {
  published: { color: "text-emerald-400", bg: "bg-emerald-500/10", label: "Published" },
  draft: { color: "text-amber-400", bg: "bg-amber-500/10", label: "Draft" },
  archived: { color: "text-zinc-400", bg: "bg-zinc-500/10", label: "Archived" },
};

function StatCard({ label, value, icon: Icon, color, sub }) {
  return (
    <div className="rounded-xl p-4 lg:p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] t-text-sub tracking-wide">{label}</span>
        <Icon size={14} style={{ color }} />
      </div>
      <p className="text-2xl font-semibold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>{value}</p>
      {sub && <p className="text-[11px] t-text-dim mt-1">{sub}</p>}
    </div>
  );
}

function AgentRow({ agent, onDelete, token }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const style = STATUS_STYLES[agent.status] || STATUS_STYLES.draft;

  const loadDetail = async () => {
    if (detail) { setExpanded(!expanded); return; }
    try {
      const res = await fetch(`${API}/api/published-agents/${agent.agent_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) { setDetail(await res.json()); setExpanded(true); }
    } catch {}
  };

  return (
    <div data-testid={`creator-agent-${agent.agent_id}`} style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="px-4 lg:px-5 py-4 flex items-center gap-4 cursor-pointer" onClick={loadDetail}>
        <div className="w-9 h-9 rounded-lg bg-cyan-400/10 flex items-center justify-center shrink-0">
          <Package size={16} className="text-cyan-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] t-text font-medium truncate">{agent.name}</p>
          <div className="flex items-center gap-3 mt-1 text-[11px] t-text-dim">
            <span className="flex items-center gap-1"><GitBranch size={10} /> v{agent.version}</span>
            <span className="flex items-center gap-1"><Zap size={10} /> {agent.execution_count} runs</span>
            <span className="flex items-center gap-1"><Shield size={10} /> {agent.trust_score}</span>
          </div>
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-sm ${style.bg} ${style.color}`}>
          {style.label}
        </span>
        <span className="text-[12px] t-text-dim hidden sm:inline">{new Date(agent.updated_at).toLocaleDateString()}</span>
        <Eye size={14} className="t-text-dim shrink-0" />
      </div>

      {expanded && detail && (
        <div className="px-4 lg:px-5 pb-4 space-y-3">
          {/* Version History */}
          <div className="rounded-lg p-3" style={{ background: 'var(--bg-secondary)' }}>
            <p className="text-[11px] t-text-sub font-medium mb-2 flex items-center gap-1.5">
              <GitBranch size={11} /> Version History
            </p>
            <div className="space-y-1.5">
              {(detail.version_history || []).map((v, i) => (
                <div key={i} className="flex items-center gap-3 text-[11px]">
                  <span className="t-text font-mono font-medium">v{v.version}</span>
                  <span className="t-text-dim">{v.node_count} nodes, {v.edge_count} edges</span>
                  <span className="ml-auto t-text-dim">{new Date(v.published_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Manifest Preview */}
          <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            <div className="px-3 py-2 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
              <FileText size={11} className="t-text-sub" />
              <span className="text-[11px] t-text-sub">Manifest (v{detail.version})</span>
            </div>
            <pre className="p-3 text-[10px] font-mono t-text-mute leading-relaxed max-h-[150px] overflow-auto" style={{ background: '#0d0d0f' }}>
              {JSON.stringify(detail.manifest, null, 2)}
            </pre>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(agent.agent_id); }}
              data-testid={`delete-published-${agent.agent_id}`}
              className="px-3 py-1.5 text-[11px] text-red-400 rounded-lg hover:bg-red-500/10 transition-colors flex items-center gap-1.5"
              style={{ border: '1px solid rgba(239,68,68,0.2)' }}
            >
              <Trash2 size={11} /> Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CreatorDashboard() {
  const { token } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/creator/analytics`, { headers });
      if (res.ok) setAnalytics(await res.json());
    } catch (e) { console.error("Failed to load creator analytics", e); }
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) fetchData(); }, [token, fetchData]);

  const deleteAgent = async (agentId) => {
    try {
      const res = await fetch(`${API}/api/published-agents/${agentId}`, { method: "DELETE", headers });
      if (res.ok) { toast.success("Agent deleted."); fetchData(); }
      else toast.error("Failed to delete agent.");
    } catch { toast.error("Network error."); }
  };

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-60px)] flex items-center justify-center">
        <Loader2 size={24} className="text-cyan-400 animate-spin" />
      </div>
    );
  }

  const stats = analytics || { total_agents: 0, published: 0, drafts: 0, total_executions: 0, total_revenue: 0, avg_trust_score: 0, total_versions: 0, agents: [] };

  return (
    <div data-testid="creator-dashboard" className="min-h-[calc(100vh-60px)] t-bg px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold t-text tracking-tight flex items-center gap-3" style={{ fontFamily: "'Outfit', sans-serif" }}>
              <BarChart3 size={24} className="text-cyan-400" /> Creator Dashboard
            </h1>
            <p className="text-[13px] t-text-sub mt-1">Manage your published agents and track performance</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              data-testid="refresh-creator-btn"
              className="px-4 py-2 rounded-sm text-[13px] font-medium flex items-center gap-2 t-text-sub hover:t-text transition-colors"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <Link
              to="/studio"
              data-testid="goto-studio-btn"
              className="px-4 py-2 bg-cyan-400 text-white text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] flex items-center gap-2"
            >
              <Plus size={13} /> Build Agent
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          <StatCard label="Total Agents" value={stats.total_agents} icon={Package} color="#22d3ee" sub={`${stats.published} published, ${stats.drafts} drafts`} />
          <StatCard label="Total Executions" value={stats.total_executions} icon={Zap} color="#06b6d4" />
          <StatCard label="Avg Trust Score" value={stats.avg_trust_score} icon={Shield} color="#34d399" />
          <StatCard label="Total Versions" value={stats.total_versions} icon={GitBranch} color="#60a5fa" sub="Across all agents" />
        </div>

        {/* Agents List */}
        <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 lg:px-5 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2">
              <Package size={13} className="text-cyan-400" />
              <span className="text-[12px] t-text-sub font-medium">Your Agents</span>
            </div>
            <span className="text-[11px] t-text-dim">{stats.agents.length} total</span>
          </div>

          {stats.agents.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Package size={32} className="t-text-dim mx-auto mb-3" />
              <p className="text-[14px] t-text-sub mb-1">No published agents yet</p>
              <p className="text-[12px] t-text-dim mb-4">Build your first agent in The Armory and publish it to the marketplace.</p>
              <Link
                to="/studio"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-cyan-400 text-white text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all"
              >
                <Plus size={14} /> Go to Studio
              </Link>
            </div>
          ) : (
            <div>
              {stats.agents.map((agent) => (
                <AgentRow key={agent.agent_id} agent={agent} onDelete={deleteAgent} token={token} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

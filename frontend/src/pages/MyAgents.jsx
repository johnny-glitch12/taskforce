/* eslint-disable react/prop-types */
/**
 * MyAgents — unified Agent Operations Hub list view (Prompt 31 Phase 2).
 *
 * Aggregates the user's bot_projects + agent_packages from
 * GET /api/agents/mine and renders a card grid with pause/resume/delete
 * actions. The top stats row pulls GET /api/agents/stats/overview.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Bot, Plus, Pause, Play, MoreVertical, Search, Loader2,
  AlertTriangle, BarChart3, Edit3, Trash2, Download, Copy,
  ExternalLink, Activity,
} from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";
const STATES = ["all", "active", "paused", "draft", "archived"];

function timeAgo(iso) {
  if (!iso) return "Never";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 0) return "just now";
    const m = Math.floor(ms / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  } catch {
    return "Never";
  }
}

function StateDot({ agent }) {
  const map = {
    active: agent.errors_24h > 3 ? "bg-amber-400" : "bg-emerald-400",
    paused: "bg-rose-400",
    draft: "bg-zinc-500",
    archived: "bg-zinc-700",
  };
  const cls = map[agent.agent_state] || "bg-zinc-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />;
}

function StateBadge({ state }) {
  const colors = {
    active: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
    paused: "text-rose-400 border-rose-500/30 bg-rose-500/5",
    draft: "text-zinc-400 border-zinc-500/30 bg-zinc-500/5",
    archived: "text-zinc-500 border-zinc-600/30 bg-zinc-600/5",
  };
  const cls = colors[state] || colors.draft;
  return (
    <span className={`px-1.5 py-0.5 text-[9px] tracking-[0.15em] uppercase font-mono rounded-sm border ${cls}`}>
      {state}
    </span>
  );
}

function OverviewCard({ label, value, testid }) {
  return (
    <div
      data-testid={testid}
      className="rounded-sm p-4"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="text-[10px] uppercase tracking-[0.15em] t-text-mute font-mono mb-1">
        {label}
      </div>
      <div className="text-2xl font-bold t-text font-mono">
        {value === null || value === undefined ? "—" : value}
      </div>
    </div>
  );
}

function MoreMenu({ agent, onDelete, onDuplicate, onExport, isOpen, onClose }) {
  if (!isOpen) return null;
  return (
    <div
      data-testid={`agent-more-menu-${agent.id}`}
      className="absolute right-0 top-full mt-1 w-40 rounded-sm py-1 shadow-2xl z-30"
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      onClick={(e) => e.stopPropagation()}
    >
      {agent.exchange_status === "published" && (
        <Link
          to={`/listing/${agent.id}`}
          className="flex items-center gap-2 px-3 py-1.5 text-[11px] t-text-sub hover:bg-cyan-500/5 hover:t-text"
        >
          <ExternalLink size={11} /> View on Exchange
        </Link>
      )}
      <button
        onClick={onDuplicate}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] t-text-sub hover:bg-cyan-500/5 hover:t-text text-left"
      >
        <Copy size={11} /> Duplicate
      </button>
      <button
        onClick={onExport}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] t-text-sub hover:bg-cyan-500/5 hover:t-text text-left"
      >
        <Download size={11} /> Export .zip
      </button>
      <button
        data-testid={`agent-delete-btn-${agent.id}`}
        onClick={onDelete}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-rose-400 hover:bg-rose-500/5 text-left"
      >
        <Trash2 size={11} /> Delete
      </button>
    </div>
  );
}

function AgentCard({ agent, onPauseToggle, onDelete, onDuplicate, onExport, navigate }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div
      data-testid={`agent-card-${agent.id}`}
      className="relative rounded-sm p-5 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-cyan-500/5"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <StateDot agent={agent} />
          <div className="min-w-0 flex-1">
            <div className="t-text font-medium truncate" title={agent.name}>{agent.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <StateBadge state={agent.agent_state} />
              {agent.category && (
                <span className="text-[9px] uppercase tracking-[0.12em] t-text-mute font-mono">
                  {agent.category}
                </span>
              )}
              <span className="text-[9px] uppercase tracking-[0.12em] t-text-mute font-mono">
                {agent.credits_per_run} cr/run
              </span>
            </div>
          </div>
        </div>
        <div className="relative">
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="p-1 t-text-mute hover:t-text"
            aria-label="More actions"
          >
            <MoreVertical size={14} />
          </button>
          <MoreMenu
            agent={agent}
            isOpen={menuOpen}
            onClose={() => setMenuOpen(false)}
            onDelete={() => { setMenuOpen(false); onDelete(agent); }}
            onDuplicate={() => { setMenuOpen(false); onDuplicate(agent); }}
            onExport={() => { setMenuOpen(false); onExport(agent); }}
          />
        </div>
      </div>

      <div className="flex items-center gap-3 text-[11px] t-text-sub mb-3 font-mono">
        <span>{agent.runs_24h} runs today</span>
        <span>·</span>
        <span>Last run: {timeAgo(agent.last_run_at)}</span>
      </div>

      {agent.errors_24h > 0 && (
        <div className="flex items-center gap-1.5 mb-3 px-2 py-1 rounded-sm bg-amber-500/10 border border-amber-500/30 text-[10px] text-amber-400">
          <AlertTriangle size={10} /> {agent.errors_24h} error{agent.errors_24h === 1 ? "" : "s"} in last 24h
        </div>
      )}

      <div className="flex items-center gap-2 pt-2 border-t" style={{ borderColor: "var(--border)" }}>
        <button
          data-testid={`agent-pause-btn-${agent.id}`}
          onClick={(e) => { e.stopPropagation(); onPauseToggle(agent); }}
          disabled={agent.agent_state === "draft" || agent.agent_state === "archived"}
          className={`flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] uppercase tracking-wide font-mono transition-colors ${
            agent.agent_state === "paused"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/15"
              : "bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/15"
          } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          {agent.agent_state === "paused" ? <><Play size={10} /> Resume</> : <><Pause size={10} /> Pause</>}
        </button>
        <button
          onClick={() => navigate(`/my-agents/${agent.id}`)}
          className="flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] uppercase tracking-wide font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15"
        >
          <BarChart3 size={10} /> Dashboard
        </button>
        <button
          onClick={() => navigate(`/armory?agent_id=${agent.id}`)}
          className="flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] uppercase tracking-wide font-mono bg-zinc-500/10 t-text-sub border border-zinc-500/30 hover:bg-zinc-500/15"
        >
          <Edit3 size={10} /> Edit
        </button>
      </div>
    </div>
  );
}

function DeleteModal({ agent, onConfirm, onCancel, deleting }) {
  const [typed, setTyped] = useState("");
  const enabled = typed.toLowerCase() === "delete";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onCancel} />
      <div
        data-testid="agent-delete-modal"
        className="relative w-full max-w-md rounded-sm p-6"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle size={16} className="text-rose-400" />
          <h3 className="t-text font-bold">Delete agent?</h3>
        </div>
        <p className="text-[12px] t-text-sub mb-4">
          This will permanently delete <span className="t-text font-medium">{agent?.name}</span> and ALL
          associated runs, logs, and listings. This cannot be undone.
        </p>
        <p className="text-[11px] t-text-mute mb-2 font-mono uppercase tracking-wide">
          Type <span className="text-rose-400">delete</span> to confirm:
        </p>
        <input
          data-testid="agent-delete-confirm-input"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoFocus
          className="w-full px-3 py-2 rounded-sm text-[12px] font-mono mb-4"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }}
          placeholder="delete"
        />
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-sm text-[11px] uppercase tracking-wider font-mono t-text-sub hover:t-text"
          >
            Cancel
          </button>
          <button
            data-testid="agent-delete-confirm-btn"
            disabled={!enabled || deleting}
            onClick={onConfirm}
            className="px-3 py-1.5 rounded-sm text-[11px] uppercase tracking-wider font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/15 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {deleting ? <Loader2 size={11} className="animate-spin inline" /> : "Delete agent"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MyAgents() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stateFilter, setStateFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  }), [token]);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 200);
    return () => clearTimeout(t);
  }, [search]);

  const load = async () => {
    setLoading(true);
    try {
      const [agentsRes, overviewRes] = await Promise.all([
        fetch(`${API}/api/agents/mine`, { headers }),
        fetch(`${API}/api/agents/stats/overview`, { headers }),
      ]);
      if (!agentsRes.ok) throw new Error(`agents/mine: ${agentsRes.status}`);
      if (!overviewRes.ok) throw new Error(`stats/overview: ${overviewRes.status}`);
      const data = await agentsRes.json();
      const ov = await overviewRes.json();
      setAgents(data.agents || []);
      setOverview(ov);
    } catch (e) {
      toast.error(`Failed to load agents: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (token) load(); }, [token]); // eslint-disable-line

  const filtered = useMemo(() => {
    let list = agents;
    if (stateFilter !== "all") list = list.filter((a) => a.agent_state === stateFilter);
    if (debouncedSearch.trim()) {
      const q = debouncedSearch.toLowerCase();
      list = list.filter((a) =>
        (a.name || "").toLowerCase().includes(q) ||
        (a.description || "").toLowerCase().includes(q)
      );
    }
    return list;
  }, [agents, stateFilter, debouncedSearch]);

  const handlePauseToggle = async (agent) => {
    const action = agent.agent_state === "paused" ? "resume" : "pause";
    try {
      const res = await fetch(`${API}/api/agents/${agent.id}/${action}`, {
        method: "POST", headers, body: "{}",
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success(`Agent ${action}d`);
      load();
    } catch (e) {
      toast.error(`Failed to ${action}: ${e.message || e}`);
    }
  };

  const handleDuplicate = async (agent) => {
    try {
      const res = await fetch(`${API}/api/agents/${agent.id}/duplicate`, {
        method: "POST", headers, body: "{}",
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Agent duplicated");
      load();
    } catch (e) {
      toast.error(`Failed to duplicate: ${e.message || e}`);
    }
  };

  const handleExport = (agent) => {
    const url = `${API}/api/agents/${agent.id}/export`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error(`Export ${r.status}`);
        const blob = await r.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${agent.slug || agent.id}.zip`;
        a.click();
        toast.success("Export downloaded");
      })
      .catch((e) => toast.error(`Export failed: ${e.message || e}`));
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API}/api/agents/${deleteTarget.id}`, {
        method: "DELETE", headers, body: JSON.stringify({ confirm: "DELETE_AGENT" }),
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success("Agent deleted");
      setDeleteTarget(null);
      load();
    } catch (e) {
      toast.error(`Failed to delete: ${e.message || e}`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div data-testid="my-agents-page" className="min-h-[calc(100vh-56px)] px-4 sm:px-6 lg:px-10 py-8 lg:py-12">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Bot size={11} className="text-cyan-400" />
              <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">AGENT OPERATIONS HUB</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight t-text">My Agents</h1>
            <p className="text-sm t-text-sub mt-2 max-w-2xl">
              Every agent you&apos;ve built. Pause, monitor, and operate them from a single surface.
            </p>
          </div>
          <Link
            to="/armory"
            data-testid="build-new-agent-btn"
            className="flex items-center gap-2 px-4 py-2 rounded-sm bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 text-[11px] uppercase tracking-[0.15em] font-mono whitespace-nowrap"
          >
            <Plus size={12} /> Build New Agent
          </Link>
        </div>

        {/* Stats row */}
        <div
          data-testid="agent-stats-overview"
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6"
        >
          <OverviewCard label="Total Agents" value={overview?.total_agents} testid="stat-total-agents" />
          <OverviewCard label="Active Now" value={overview?.active_now} testid="stat-active-now" />
          <OverviewCard label="Runs Today" value={overview?.runs_today} testid="stat-runs-today" />
          <OverviewCard label="Credits Used" value={overview?.credits_used_today} testid="stat-credits-used" />
        </div>

        {/* Filter row */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-6">
          <div data-testid="state-filter" className="flex items-center gap-1 p-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            {STATES.map((s) => (
              <button
                key={s}
                onClick={() => setStateFilter(s)}
                data-testid={`state-filter-${s}`}
                className={`px-3 py-1 text-[10px] uppercase tracking-[0.12em] font-mono rounded-sm transition-colors ${
                  stateFilter === s
                    ? "bg-cyan-500/15 text-cyan-400"
                    : "t-text-sub hover:t-text"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="relative flex-1 max-w-md">
            <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 t-text-mute" />
            <input
              data-testid="search-input"
              type="text"
              placeholder="Search by name or description…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-2 rounded-sm text-[12px] font-mono"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }}
            />
          </div>
        </div>

        {/* Cards */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="rounded-sm p-5 animate-pulse" style={{ background: "var(--bg-card)", border: "1px solid var(--border)", height: 180 }} />
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div data-testid="my-agents-empty" className="text-center py-16 rounded-sm" style={{ background: "var(--bg-card)", border: "1px dashed var(--border)" }}>
            <Bot size={28} className="text-cyan-400 mx-auto mb-3 opacity-60" />
            <div className="t-text font-medium mb-1">You haven&apos;t built any agents yet.</div>
            <div className="text-[12px] t-text-sub mb-4">Spin up your first agent in the Armory builder.</div>
            <Link
              to="/armory"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 text-[11px] uppercase tracking-[0.15em] font-mono"
            >
              <Plus size={12} /> Build Your First Agent
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 t-text-sub text-[12px]">
            <Activity size={20} className="text-cyan-400 mx-auto mb-2 opacity-60" />
            No agents match your filters.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onPauseToggle={handlePauseToggle}
                onDelete={(a) => setDeleteTarget(a)}
                onDuplicate={handleDuplicate}
                onExport={handleExport}
                navigate={navigate}
              />
            ))}
          </div>
        )}
      </div>

      {deleteTarget && (
        <DeleteModal
          agent={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
          deleting={deleting}
        />
      )}
    </div>
  );
}

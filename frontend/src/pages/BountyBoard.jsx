/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Target, Plus, Clock, Users, Trophy, ArrowRight,
  Loader2, Sparkles, Filter, ChevronDown,
} from "lucide-react";
import PostBountyModal from "@/components/PostBountyModal";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "customer_support", label: "Customer Support" },
  { id: "sales", label: "Sales" },
  { id: "data_analysis", label: "Data Analysis" },
  { id: "coding", label: "Coding" },
  { id: "creative", label: "Creative" },
  { id: "finance", label: "Finance" },
  { id: "automation", label: "Automation" },
  { id: "other", label: "Other" },
];

const STATUSES = [
  { id: "all", label: "All", color: "#94a3b8" },
  { id: "open", label: "Open", color: "#22c55e" },
  { id: "in_review", label: "In Review", color: "#fbbf24" },
  { id: "awarded", label: "Awarded", color: "#22d3ee" },
  { id: "expired", label: "Expired", color: "#64748b" },
];

const SORTS = [
  { id: "newest", label: "Newest" },
  { id: "highest_reward", label: "Highest Reward" },
  { id: "ending_soon", label: "Ending Soon" },
  { id: "most_submissions", label: "Most Submissions" },
];

export function fmtRemaining(seconds) {
  if (!seconds || seconds <= 0) return "Ended";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  if (d >= 1) return `${d}d ${h}h`;
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function BountyBoard() {
  const { token, user } = useAuth() || {};
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({ active: 0, awarded_count: 0, credits_paid_out: 0 });
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("newest");
  const [showModal, setShowModal] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const url = new URL(`${API}/api/bounties`);
      if (category !== "all") url.searchParams.set("category", category);
      if (status !== "all") url.searchParams.set("status", status);
      url.searchParams.set("sort", sort);
      const r = await fetch(url.toString());
      const body = await r.json();
      setItems(body.items || []);
      setStats(body.stats || { active: 0, awarded_count: 0, credits_paid_out: 0 });
    } catch (e) {
      console.error("bounty list failed:", e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { refresh(); }, [category, status, sort]); // eslint-disable-line

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-7xl mx-auto px-6 py-10" data-testid="bounty-board-page">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4 mb-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim mb-2">
              Task Force AI / Demand-Side
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold t-text flex items-center gap-3 mb-2">
              <Target className="text-cyan-400" size={36} />
              The Bounty Board
            </h1>
            <p className="text-sm t-text-mute max-w-xl">
              Post what you need. Creators compete to build it. Winners take the bounty
              and earn a permanent listing on The Exchange.
            </p>
          </div>
          <button
            data-testid="post-bounty-btn"
            onClick={() => {
              if (!token) { navigate("/login"); return; }
              setShowModal(true);
            }}
            className="px-5 py-3 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2 transition-all"
            style={{ background: "#22d3ee", color: "#0a0e1a" }}
          >
            <Plus size={14} /> Post a bounty
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6 mb-8">
          <StatTile icon={Target} label="Active bounties" value={stats.active} accent="#22d3ee" testid="stat-active" />
          <StatTile icon={Trophy} label="Total awarded" value={stats.awarded_count} accent="#a855f7" testid="stat-awarded" />
          <StatTile icon={Sparkles} label="Credits paid out" value={`${stats.credits_paid_out.toLocaleString()} cr`} accent="#fbbf24" testid="stat-paid" />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Filter size={12} className="t-text-dim" />
          <span className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mr-2">Category</span>
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              data-testid={`filter-cat-${c.id}`}
              onClick={() => setCategory(c.id)}
              className="px-3 py-1 text-[11px] font-mono rounded-sm transition-all"
              style={{
                background: category === c.id ? "#22d3ee" : "transparent",
                color: category === c.id ? "#0a0e1a" : "var(--text-mute)",
                border: `1px solid ${category === c.id ? "#22d3ee" : "var(--border)"}`,
              }}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-8">
          <span className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mr-2">Status</span>
          {STATUSES.map((s) => (
            <button
              key={s.id}
              data-testid={`filter-status-${s.id}`}
              onClick={() => setStatus(s.id)}
              className="px-3 py-1 text-[11px] font-mono rounded-sm transition-all inline-flex items-center gap-1.5"
              style={{
                background: status === s.id ? `${s.color}22` : "transparent",
                color: status === s.id ? s.color : "var(--text-mute)",
                border: `1px solid ${status === s.id ? `${s.color}88` : "var(--border)"}`,
              }}
            >
              <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: s.color }} />
              {s.label}
            </button>
          ))}

          <div className="ml-auto inline-flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim">Sort</span>
            <div className="relative">
              <select
                data-testid="sort-select"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="appearance-none pl-3 pr-8 py-1.5 text-[11px] font-mono rounded-sm"
                style={{
                  background: "var(--bg-input)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                }}
              >
                {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
              <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none t-text-dim" />
            </div>
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="text-center py-20 t-text-mute text-sm" data-testid="bounty-loading">
            <Loader2 className="animate-spin inline-block mr-2" size={14} /> Loading bounties…
          </div>
        ) : items.length === 0 ? (
          <div className="t-card rounded-sm p-12 text-center" data-testid="empty-state">
            <Target className="mx-auto mb-3 t-text-dim" size={28} />
            <div className="text-sm t-text mb-1">No bounties match your filters.</div>
            <div className="text-xs t-text-mute">Be the first to post — creators are watching.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="bounty-grid">
            {items.map((b) => <BountyCard key={b.id} b={b} />)}
          </div>
        )}
      </div>

      {showModal && (
        <PostBountyModal
          onClose={() => setShowModal(false)}
          onPosted={(b) => {
            setShowModal(false);
            toast.success("Bounty posted!");
            navigate(`/bounties/${b.id}`);
          }}
        />
      )}
    </div>
  );
}

function StatTile({ icon: Icon, label, value, accent, testid }) {
  return (
    <div data-testid={testid} className="t-card rounded-sm p-4 flex items-center gap-3">
      <div
        className="w-10 h-10 rounded-sm flex items-center justify-center shrink-0"
        style={{ background: `${accent}1a`, border: `1px solid ${accent}55` }}
      >
        <Icon size={18} style={{ color: accent }} />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim">{label}</div>
        <div className="text-xl font-bold t-text">{value}</div>
      </div>
    </div>
  );
}

function BountyCard({ b }) {
  const status = STATUSES.find((s) => s.id === b.status) || STATUSES[1];
  const cat = CATEGORIES.find((c) => c.id === b.category) || CATEGORIES[0];
  const remaining = b.seconds_remaining || 0;
  const urgent = remaining > 0 && remaining < 86400; // < 24h
  return (
    <Link
      to={`/bounties/${b.id}`}
      data-testid={`bounty-card-${b.id}`}
      className="t-card rounded-sm p-5 hover:border-cyan-500/40 transition-all flex flex-col"
      style={{ minHeight: 240 }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span
          className="px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.15em] rounded-sm shrink-0"
          style={{ background: `${status.color}22`, color: status.color, border: `1px solid ${status.color}55` }}
        >
          {status.label}
        </span>
        <span className="text-[10px] font-mono t-text-dim shrink-0">{cat.label}</span>
      </div>

      <div className="text-base font-semibold t-text mb-2 line-clamp-2" style={{
        display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
      }}>
        {b.title}
      </div>
      <div className="text-xs t-text-mute mb-4 flex-1" style={{
        display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden",
      }}>
        {b.description}
      </div>

      <div className="flex items-end justify-between gap-2">
        <div>
          <div className="text-[9px] uppercase tracking-[0.15em] font-mono t-text-dim mb-0.5">Reward</div>
          <div className="text-2xl font-bold text-cyan-400 leading-none">{b.reward_amount.toLocaleString()}<span className="text-xs t-text-mute ml-1">cr</span></div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-[0.15em] font-mono t-text-dim mb-0.5 inline-flex items-center gap-1 justify-end">
            <Clock size={9} /> {urgent ? "URGENT" : "Ends"}
          </div>
          <div className="text-xs font-mono" style={{ color: urgent ? "#fb923c" : "var(--text)" }}>
            {fmtRemaining(remaining)}
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-[color:var(--border)] flex items-center justify-between text-[11px] t-text-mute font-mono">
        <span className="inline-flex items-center gap-1">
          <Users size={11} /> {b.submission_count || 0}/{b.max_submissions} submissions
        </span>
        <ArrowRight size={12} className="text-cyan-400" />
      </div>
    </Link>
  );
}

/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Target, Plus, Clock, Users, ArrowRight,
  Loader2, Filter, ChevronDown,
} from "lucide-react";
import PostBountyModal from "@/components/PostBountyModal";

const API = process.env.REACT_APP_BACKEND_URL || "";

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

export function fmtReward(b) {
  if (b?.reward_type === "cash") {
    return { value: `$${Number(b.reward_amount || 0).toFixed(2)}`, unit: "USD", color: "#22c55e" };
  }
  return { value: Number(b?.reward_amount || 0).toLocaleString(), unit: "cr", color: "#22d3ee" };
}

export default function BountyBoard() {
  const { token, user } = useAuth() || {};
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState({ active: 0, awarded_count: 0, credits_paid_out: 0, cash_paid_out: 0 });
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
      setStats(body.stats || { active: 0, awarded_count: 0, credits_paid_out: 0, cash_paid_out: 0 });
    } catch (e) {
      console.error("bounty list failed:", e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { refresh(); }, [category, status, sort]); // eslint-disable-line

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-5xl mx-auto px-6 py-12" data-testid="bounty-board-page">
        {/* Hero header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 mb-5 px-3 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <Target size={11} className="text-cyan-400" />
            <span className="text-[10px] tracking-[0.25em] uppercase font-mono" style={{ color: "rgba(255,255,255,0.55)" }}>
              Demand-Side · Open Contracts
            </span>
          </div>
          <h1
            data-testid="bounty-title"
            className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-[-0.02em] leading-[1.05] t-text mb-3"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            The <span className="text-gradient-cyan">Bounty Board</span>
          </h1>
          <p className="text-base t-text-sub max-w-xl mx-auto leading-relaxed mb-6">
            Post what you need. Creators compete to build it. Winners take the bounty
            and earn a permanent listing on The Exchange.
          </p>

          {/* Stats bar */}
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4 mb-6">
            <BountyStat value={stats.active} label="Open" testid="stat-active" />
            <BountyStat
              value={`${(stats.credits_paid_out || 0).toLocaleString()} cr`}
              label="Credits Awarded"
              testid="stat-paid"
            />
            <BountyStat value={stats.awarded_count} label="Completed" testid="stat-awarded" />
          </div>

          <button
            data-testid="post-bounty-btn"
            onClick={() => {
              if (!token) { navigate("/login"); return; }
              setShowModal(true);
            }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-sm text-[11px] font-bold font-mono uppercase tracking-[0.18em] transition-all"
            style={{ background: "#22d3ee", color: "#0a0e1a", boxShadow: "0 0 24px rgba(34,211,238,0.25)" }}
          >
            <Plus size={12} /> Post a bounty
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <Filter size={11} className="t-text-dim mr-1" />
          <span className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mr-2">Category</span>
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              data-testid={`filter-cat-${c.id}`}
              onClick={() => setCategory(c.id)}
              className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.12em] rounded-sm transition-all"
              style={{
                background: category === c.id ? "rgba(34,211,238,0.1)" : "rgba(255,255,255,0.02)",
                color: category === c.id ? "#22d3ee" : "var(--text-mute)",
                border: `1px solid ${category === c.id ? "rgba(34,211,238,0.6)" : "var(--border)"}`,
              }}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mb-8">
          <span className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mr-2">Status</span>
          {STATUSES.map((s) => (
            <button
              key={s.id}
              data-testid={`filter-status-${s.id}`}
              onClick={() => setStatus(s.id)}
              className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.12em] rounded-sm transition-all inline-flex items-center gap-1.5"
              style={{
                background: status === s.id ? `${s.color}1a` : "rgba(255,255,255,0.02)",
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

        {/* Stacked list with urgency stripe */}
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
          <div className="flex flex-col gap-3" data-testid="bounty-grid">
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

function BountyStat({ value, label, testid }) {
  return (
    <div className="text-center" data-testid={testid}>
      <div className="text-2xl sm:text-[28px] font-bold font-mono tabular-nums text-cyan-400 leading-none">
        {value}
      </div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.2em] font-mono" style={{ color: "rgba(255,255,255,0.4)" }}>
        {label}
      </div>
    </div>
  );
}

function BountyCard({ b }) {
  const status = STATUSES.find((s) => s.id === b.status) || STATUSES[1];
  const cat = CATEGORIES.find((c) => c.id === b.category) || CATEGORIES[0];
  const remaining = b.seconds_remaining || 0;
  const urgent = remaining > 0 && remaining < 86400; // < 24h

  // Map remaining time → urgency stripe color
  const stripeColor = urgent
    ? "#ef4444"
    : remaining < 3 * 86400
      ? "#fb923c"
      : "#22d3ee";

  return (
    <Link
      to={`/bounties/${b.id}`}
      data-testid={`bounty-card-${b.id}`}
      className="t-card rounded-sm overflow-hidden flex transition-all duration-300 hover:border-cyan-400/30 hover:translate-x-1 hover:shadow-[-4px_0_20px_rgba(34,211,238,0.06)]"
    >
      {/* Urgency stripe */}
      <div
        aria-hidden="true"
        className="w-1 shrink-0"
        style={{ background: stripeColor, boxShadow: urgent ? "0 0 12px rgba(239,68,68,0.5)" : "none" }}
      />

      <div className="flex-1 p-4 sm:p-5">
        {/* Row 1: status + category + deadline */}
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <span
            className="px-2 py-0.5 text-[9px] font-mono font-bold uppercase tracking-[0.15em] rounded-sm shrink-0"
            style={{ background: `${status.color}1a`, color: status.color, border: `1px solid ${status.color}66` }}
          >
            {status.label}
          </span>
          <span className="text-[10px] font-mono uppercase tracking-[0.12em] t-text-dim">
            {cat.label}
          </span>
          <span
            className="ml-auto text-[10px] font-mono inline-flex items-center gap-1"
            style={{ color: urgent ? "#fb923c" : "var(--text-mute)" }}
          >
            <Clock size={10} /> {urgent ? "URGENT · " : ""}{fmtRemaining(remaining)}
          </span>
        </div>

        {/* Row 2: title */}
        <div className="text-[15px] sm:text-base font-semibold t-text mb-1.5 leading-snug" style={{
          display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>
          {b.title}
        </div>

        {/* Row 3: description */}
        <div className="text-[12.5px] t-text-mute mb-4 leading-relaxed" style={{
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>
          {b.description}
        </div>

        {/* Row 4: reward + submissions + CTA */}
        <div className="flex items-center gap-4 flex-wrap pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div>
            <div className="text-[9px] uppercase tracking-[0.18em] font-mono t-text-dim mb-0.5">Reward</div>
            {(() => {
              const r = fmtReward(b);
              return (
                <div className="text-xl font-bold leading-none tabular-nums" style={{ color: r.color }}>
                  {r.value}<span className="text-[11px] t-text-mute ml-1 font-normal">{r.unit}</span>
                </div>
              );
            })()}
          </div>
          <div className="text-[11px] t-text-mute font-mono inline-flex items-center gap-1">
            <Users size={11} /> {b.submission_count || 0}/{b.max_submissions} submissions
          </div>
          <span
            className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono font-bold tracking-[0.18em] uppercase rounded-sm transition-all"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.7)",
            }}
          >
            View Bounty <ArrowRight size={11} className="text-cyan-400" />
          </span>
        </div>
      </div>
    </Link>
  );
}

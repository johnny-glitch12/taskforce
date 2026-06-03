import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Coins, Zap, ArrowUpRight, Sparkles, TrendingUp,
  Gift, Loader2, Check, RefreshCw, Infinity as InfinityIcon,
  AlertTriangle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function CircularRing({ value, max, color = "#22d3ee", label, sublabel, testid }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const radius = 52;
  const stroke = 6;
  const circ = 2 * Math.PI * radius;
  const dash = (pct / 100) * circ;

  return (
    <div data-testid={testid} className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: 130, height: 130 }}>
        <svg width={130} height={130} className="-rotate-90">
          <circle cx={65} cy={65} r={radius} stroke="var(--border)" strokeWidth={stroke} fill="none" />
          <circle
            cx={65} cy={65} r={radius}
            stroke={color}
            strokeWidth={stroke}
            fill="none"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.3s" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-2xl font-bold font-mono t-text leading-none">{value.toLocaleString()}</div>
          <div className="text-[9px] font-mono uppercase tracking-widest t-text-dim mt-1">/ {max.toLocaleString()}</div>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mb-1">{label}</div>
        <div className="text-[12px] t-text-sub font-mono">{sublabel}</div>
      </div>
    </div>
  );
}

function TopupPoolCard({ value, testid }) {
  return (
    <div data-testid={testid} className="flex items-center gap-5">
      <div className="shrink-0 w-[130px] h-[130px] flex items-center justify-center"
        style={{ background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.25)", borderRadius: 2 }}>
        <div className="text-center">
          <Coins size={20} className="text-amber-400 mx-auto mb-1" />
          <div className="text-2xl font-bold font-mono t-text leading-none">{value.toLocaleString()}</div>
          <div className="text-[9px] font-mono uppercase tracking-widest t-text-dim mt-1">credits</div>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mb-1">Top-Up Credits</div>
        <div className="text-[12px] t-text-sub font-mono flex items-center gap-1.5">
          <InfinityIcon size={11} className="text-amber-400" /> Never expire
        </div>
      </div>
    </div>
  );
}

function ActionCostsList({ costs }) {
  const labelMap = {
    vibe_chat: "AI chat (vibe)",
    build_bot: "Build bot",
    workflow_run: "Workflow run",
    bot_deploy: "Bot deploy",
    agent_run: "Agent run",
    external_agent_run: "External agent",
    publish_listing: "Publish listing",
  };
  return (
    <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Zap size={12} className="text-cyan-400" />
        <span className="text-[10px] uppercase tracking-[0.2em] t-text-sub font-mono">Action Costs</span>
      </div>
      <ul data-testid="action-costs" className="space-y-1.5 text-[11px] font-mono">
        {Object.entries(costs || {}).map(([k, v]) => (
          <li key={k} className="flex items-center justify-between gap-2">
            <span className="t-text-mute">{labelMap[k] || k.replace(/_/g, " ")}</span>
            <span className={v === 0 ? "text-emerald-400" : "text-cyan-400"}>
              {v === 0 ? "free" : `${v} cr`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Credits() {
  const { token } = useAuth();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [promoCode, setPromoCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/credits/me`, { headers: { Authorization: `Bearer ${token}` } });
      setInfo(await res.json());
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!token) return;
    load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("topup") === "success" && params.get("session_id")) {
      fetch(`${API}/api/credits/topup/poll/${params.get("session_id")}`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      }).then((r) => r.json()).then((d) => {
        if (d.credits_added) toast.success(`+${d.credits_added} credits added.`);
        load();
      });
    }
    // eslint-disable-next-line
  }, [token]);

  const buy = async (packId) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/credits/topup/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ pack: packId, promo_code: promoCode || undefined }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
      else toast.error(data.detail || "Checkout failed.");
    } catch { toast.error("Network error."); }
    setBusy(false);
  };

  const redeem = async () => {
    if (!promoCode.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/promo/redeem`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ code: promoCode.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.granted) toast.success(`+${data.granted} credits added to your top-up balance.`);
        else toast.success(data.message || "Code applied at next checkout.");
        load();
      } else {
        toast.error(data.detail || "Invalid code.");
      }
    } catch { toast.error("Network error."); }
    setBusy(false);
  };

  if (loading || !info) {
    return <div className="min-h-screen t-bg flex items-center justify-center"><Loader2 className="animate-spin text-cyan-400" /></div>;
  }

  const subPct = info.subscription_credits_max > 0
    ? (info.subscription_credits / info.subscription_credits_max) * 100
    : 0;
  const lowSub = !info.unlimited && subPct < 10 && info.subscription_credits_max > 0;
  const resetDate = info.credit_reset_date
    ? new Date(info.credit_reset_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : null;
  const daysUntilReset = info.credit_reset_date
    ? Math.max(0, Math.ceil((new Date(info.credit_reset_date) - new Date()) / (1000 * 60 * 60 * 24)))
    : null;

  return (
    <div data-testid="credits-page" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <Coins size={20} className="text-cyan-400" />
          <h1 className="text-2xl md:text-3xl tracking-wide t-text" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: "0.04em" }}>
            CREDIT WALLET
          </h1>
        </div>
        <p className="text-[12px] t-text-dim mb-6 uppercase tracking-widest font-mono">
          Dual-pool credits · {info.tier?.toUpperCase()} TIER
        </p>

        {/* Low credit banner */}
        {lowSub && (
          <div
            data-testid="low-credit-warning"
            className="rounded-sm p-3 mb-4 flex items-center gap-3"
            style={{ background: "rgba(251,113,133,0.05)", border: "1px solid rgba(251,113,133,0.3)" }}
          >
            <AlertTriangle size={14} className="text-rose-400 shrink-0" />
            <div className="flex-1 text-[11px] font-mono">
              <span className="text-rose-400 font-bold">Running low on monthly credits.</span>{" "}
              <span className="t-text-sub">Top up to keep building — {info.subscription_credits} of {info.subscription_credits_max} left.</span>
            </div>
          </div>
        )}

        {/* Dual-pool balance cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <div
            data-testid="subscription-pool-card"
            className="rounded-sm p-5 relative overflow-hidden"
            style={{ background: "var(--bg-card)", border: "1px solid rgba(34,211,238,0.25)" }}
          >
            <div className="absolute inset-0 pointer-events-none opacity-30"
              style={{ background: "radial-gradient(circle at 80% 0%, rgba(34,211,238,0.2), transparent 60%)" }} />
            <div className="relative">
              {info.unlimited ? (
                <div className="flex items-center gap-5">
                  <div className="shrink-0 w-[130px] h-[130px] flex items-center justify-center rounded-sm"
                    style={{ background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.3)" }}>
                    <InfinityIcon size={48} className="text-cyan-400" />
                  </div>
                  <div className="flex-1">
                    <div className="text-[10px] uppercase tracking-[0.2em] font-mono t-text-dim mb-1">Monthly Credits</div>
                    <div className="text-[12px] t-text-sub font-mono">Unlimited · Admin tier</div>
                  </div>
                </div>
              ) : (
                <CircularRing
                  testid="subscription-ring"
                  value={info.subscription_credits}
                  max={info.subscription_credits_max}
                  color={lowSub ? "#fb7185" : "#22d3ee"}
                  label="Monthly Credits"
                  sublabel={
                    resetDate
                      ? <>Resets <span className="text-cyan-400">{resetDate}</span>{daysUntilReset !== null && <span className="t-text-dim"> · in {daysUntilReset}d</span>}</>
                      : "Renews each billing cycle"
                  }
                />
              )}
            </div>
          </div>

          <div
            className="rounded-sm p-5"
            style={{ background: "var(--bg-card)", border: "1px solid rgba(251,191,36,0.2)" }}
          >
            <TopupPoolCard testid="topup-pool" value={info.unlimited ? "∞" : info.topup_credits} />
          </div>
        </div>

        {/* Combined total */}
        <div
          data-testid="combined-total"
          className="rounded-sm p-3 mb-6 text-center font-mono text-[12px] t-text-sub"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
        >
          <span className="uppercase tracking-[0.18em] text-[10px] t-text-dim mr-2">Total Available</span>
          <span className="text-cyan-400 font-bold text-[14px]" data-testid="total-balance-value">
            {info.unlimited ? "∞" : info.balance.toLocaleString()}
          </span>
          <span className="t-text-dim ml-1">credits</span>
        </div>

        {/* Promo + Costs + Packs */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-6">
          {/* Promo card */}
          <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center gap-2 mb-3">
              <Gift size={13} className="text-cyan-400" />
              <span className="text-[10px] uppercase tracking-[0.2em] t-text-sub font-mono">Promo Code</span>
            </div>
            <input
              data-testid="promo-input"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
              placeholder="ENTER CODE"
              className="w-full px-3 py-2 text-[12px] rounded-sm mb-2 font-mono uppercase tracking-wider"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <button
              data-testid="promo-redeem-btn"
              onClick={redeem}
              disabled={!promoCode || busy}
              className="w-full px-3 py-2 text-[11px] font-bold tracking-[0.18em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-30 flex items-center justify-center gap-1.5"
            >
              {busy ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              Redeem
            </button>
            <div className="text-[10px] t-text-dim mt-2 leading-relaxed">
              Credits go to your top-up pool — they never expire.
            </div>
          </div>

          <ActionCostsList costs={info.action_costs} />

          {/* Inline pack callout */}
          <div className="rounded-sm p-4 flex flex-col justify-center"
            style={{ background: "rgba(34,211,238,0.04)", border: "1px solid rgba(34,211,238,0.2)" }}>
            <div className="flex items-center gap-2 mb-2">
              <RefreshCw size={12} className="text-cyan-400" />
              <span className="text-[10px] uppercase tracking-[0.2em] t-text-sub font-mono">How it works</span>
            </div>
            <p className="text-[11px] t-text-mute leading-relaxed">
              Subscription credits reset each cycle. Top-up credits never expire and kick in only when your monthly pool runs dry.
            </p>
          </div>
        </div>

        {/* Top-up packs */}
        <div className="mb-3 flex items-center gap-2">
          <Sparkles size={12} className="text-cyan-400" />
          <span className="text-[10px] uppercase tracking-[0.2em] t-text-sub font-mono">Top-Up Packs · never expire</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {Object.entries(info.packs || {}).map(([packId, p]) => (
            <button
              key={packId}
              data-testid={`pack-${packId}`}
              onClick={() => buy(packId)}
              disabled={busy}
              className="rounded-sm p-4 text-left transition-all hover:border-cyan-400/60 hover:translate-y-[-1px] disabled:opacity-50 group"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-start justify-between mb-3">
                <Sparkles size={14} className="text-cyan-400" />
                <span className="font-mono text-[9px] uppercase tracking-[0.2em] t-text-dim">{packId}</span>
              </div>
              <div className="font-mono text-2xl t-text">{p.credits.toLocaleString()}</div>
              <div className="text-[10px] uppercase tracking-widest t-text-dim mt-0.5 font-mono">credits</div>
              <div className="text-[9px] t-text-mute mt-2 font-mono">
                ${(p.price / p.credits).toFixed(3)}/credit
              </div>
              <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                <span className="font-mono text-cyan-400 text-[16px] font-bold">${p.price.toFixed(2)}</span>
                <ArrowUpRight size={12} className="t-text-mute group-hover:text-cyan-400 transition-colors" />
              </div>
            </button>
          ))}
        </div>

        {/* Transactions */}
        <div className="rounded-sm overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-2.5 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
            <TrendingUp size={12} className="text-cyan-400" />
            <span className="text-[10px] uppercase tracking-[0.2em] t-text-sub font-mono">Recent Transactions</span>
          </div>
          {(info.transactions || []).length === 0 && (
            <div className="px-4 py-8 text-center t-text-dim text-[11px] font-mono">— no transactions yet —</div>
          )}
          {(info.transactions || []).map((tx, i) => {
            const isDebit = tx.delta < 0;
            const subPart = tx.sub_deducted || 0;
            const topPart = tx.topup_deducted || 0;
            return (
              <div key={i} data-testid={`txn-row-${i}`}
                className="px-4 py-2 flex items-center gap-3 text-[11px] font-mono"
                style={{ borderBottom: "1px solid var(--border)" }}>
                <span className={isDebit ? "text-rose-400" : "text-emerald-400"} style={{ width: 60 }}>
                  {isDebit ? "" : "+"}{tx.delta}cr
                </span>
                <span className="t-text-sub" style={{ width: 130 }}>{tx.kind}</span>
                <div className="flex-1 truncate">
                  <span className="t-text-mute">{tx.note}</span>
                  {isDebit && (subPart > 0 || topPart > 0) && (
                    <span className="ml-2 text-[9px] t-text-dim">
                      {subPart > 0 && <span className="text-cyan-400/70">sub −{subPart}</span>}
                      {subPart > 0 && topPart > 0 && " · "}
                      {topPart > 0 && <span className="text-amber-400/70">top −{topPart}</span>}
                    </span>
                  )}
                  {!isDebit && tx.pool && (
                    <span className="ml-2 text-[9px] t-text-dim">→ {tx.pool}</span>
                  )}
                </div>
                <span className="t-text-dim text-[10px]">{tx.created_at?.slice(0, 16).replace("T", " ")}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* eslint-disable react/prop-types */
/**
 * CreditCounter — persistent credit balance pill in the navbar.
 *
 * • Always visible when signed in (every page).
 * • Color shifts: cyan (healthy) → amber (low) → red (critical).
 * • Click opens the TopUpModal.
 * • Polls /api/credits/balance every 30s via useCredits().
 * • Admin / unlimited accounts render an infinity glyph instead of the number.
 *
 * SMART ALLOWANCE (Phase 65):
 * • A thin cyan progress ring around the coin icon shows how much of the
 *   monthly subscription pool is still available (cyan fills clockwise).
 * • Hover the pill to surface a tooltip with the dual-pool breakdown:
 *     Subscription: 320 / 500 remaining (resets Mar 14)
 *     Top-up: 187 cr (never expire)
 * • The ring stays subtle — no big bar that would distract from the pill
 *   itself, but it answers "how much of my plan do I have left?" in one glance.
 */
import { useState, useRef } from "react";
import { Coins, Plus, Infinity as InfinityIcon } from "lucide-react";
import { useCredits } from "@/lib/credits";
import TopUpModal from "@/components/TopUpModal";

export default function CreditCounter() {
  const { credits, loading } = useCredits();
  const [showTopup, setShowTopup] = useState(false);
  const [showTip, setShowTip] = useState(false);
  const hoverTimer = useRef(null);

  if (loading || !credits) return null;

  const total = credits.total || 0;
  const unlimited = !!credits.unlimited;
  const subscription = credits.subscription || 0;
  const topup = credits.topup || 0;
  const subscriptionMax = credits.subscription_max || 0;
  // Server-computed pct (0..100); falls back to client calc for safety.
  const subscriptionPct = typeof credits.subscription_pct === "number"
    ? credits.subscription_pct
    : (subscriptionMax > 0 ? Math.max(0, Math.min(100, Math.round(subscription / subscriptionMax * 100))) : 0);

  // Color buckets — kept neutral inside the navbar's mono aesthetic.
  let color = "text-cyan-400";
  let borderColor = "rgba(34,211,238,0.25)";
  let glow = "rgba(34,211,238,0.10)";
  let ringStroke = "rgba(34,211,238,0.85)";
  if (!unlimited && total <= 5) {
    color = "text-rose-400";
    borderColor = "rgba(244,63,94,0.35)";
    glow = "rgba(244,63,94,0.12)";
    ringStroke = "rgba(244,63,94,0.85)";
  } else if (!unlimited && total <= 50) {
    color = "text-amber-300";
    borderColor = "rgba(251,191,36,0.35)";
    glow = "rgba(251,191,36,0.10)";
    ringStroke = "rgba(251,191,36,0.85)";
  }

  const display = unlimited ? "∞" : total.toLocaleString();
  // SVG ring math — circumference = 2 * π * r. We use r=8 so c ≈ 50.27.
  // The dashOffset shrinks as more of the pool is filled.
  const R = 8;
  const C = 2 * Math.PI * R;
  const filled = unlimited ? C : (subscriptionPct / 100) * C;
  const dashOffset = C - filled;

  // Build a friendly reset-date label.
  const resetLabel = (() => {
    if (!credits.reset_date) return "";
    try {
      const d = new Date(credits.reset_date);
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch { return ""; }
  })();

  const onEnter = () => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setShowTip(true), 250);
  };
  const onLeave = () => {
    clearTimeout(hoverTimer.current);
    setShowTip(false);
  };

  return (
    <div className="relative" onMouseEnter={onEnter} onMouseLeave={onLeave}>
      <button
        data-testid="navbar-credit-counter"
        onClick={() => setShowTopup(true)}
        title="Top up credits"
        className="group flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm transition-all"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${borderColor}`,
          boxShadow: `0 0 0 0 ${glow}`,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.boxShadow = `0 0 14px 0 ${glow}`; }}
        onMouseLeave={(e) => { e.currentTarget.style.boxShadow = `0 0 0 0 ${glow}`; }}
      >
        {/* Icon + Smart Allowance ring (svg overlay) */}
        <span className="relative flex items-center justify-center" style={{ width: 18, height: 18 }}>
          {/* Subtle background track */}
          {!unlimited && subscriptionMax > 0 && (
            <svg
              data-testid="navbar-allowance-ring"
              width="18" height="18" viewBox="0 0 20 20"
              className="absolute inset-0"
              style={{ transform: "rotate(-90deg)" }}
              aria-hidden="true"
            >
              <circle cx="10" cy="10" r={R}
                fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" />
              <circle cx="10" cy="10" r={R}
                fill="none" stroke={ringStroke} strokeWidth="1.5"
                strokeDasharray={C}
                strokeDashoffset={dashOffset}
                strokeLinecap="round"
                style={{ transition: "stroke-dashoffset 0.6s ease" }}
              />
            </svg>
          )}
          {unlimited ? (
            <InfinityIcon size={11} className={color} />
          ) : (
            <Coins size={10} className={color} />
          )}
        </span>
        <span data-testid="navbar-credit-amount" className={`font-mono font-bold text-[12px] tabular-nums ${color}`}>
          {display}
        </span>
        <span
          className="w-4 h-4 rounded-sm flex items-center justify-center transition-all opacity-70 group-hover:opacity-100"
          style={{ background: "rgba(34,211,238,0.10)" }}
        >
          <Plus size={9} className="text-cyan-300" strokeWidth={3} />
        </span>
      </button>

      {/* Smart Allowance tooltip — only renders on hover, only when not unlimited */}
      {showTip && !unlimited && (
        <div
          data-testid="navbar-allowance-tooltip"
          className="absolute right-0 mt-2 z-50 w-[240px] rounded-sm p-3 text-[11px] font-mono"
          style={{
            background: "rgba(10,10,10,0.98)",
            border: "1px solid rgba(34,211,238,0.25)",
            boxShadow: "0 8px 30px -8px rgba(34,211,238,0.20), 0 4px 12px rgba(0,0,0,0.5)",
            backdropFilter: "blur(8px)",
          }}
        >
          <div className="text-cyan-300 uppercase tracking-[0.18em] text-[9px] font-bold mb-2">
            Smart Allowance
          </div>
          <div className="flex items-center justify-between text-zinc-300 mb-1">
            <span>Subscription</span>
            <span className="text-cyan-300 tabular-nums">
              {subscription.toLocaleString()}{subscriptionMax > 0 ? ` / ${subscriptionMax.toLocaleString()}` : ""}
            </span>
          </div>
          {subscriptionMax > 0 && (
            <div className="h-1 rounded-full overflow-hidden mb-2" style={{ background: "rgba(255,255,255,0.08)" }}>
              <div
                className="h-full transition-all"
                style={{
                  width: `${subscriptionPct}%`,
                  background: "linear-gradient(90deg, #22d3ee, #06b6d4)",
                }}
              />
            </div>
          )}
          <div className="flex items-center justify-between text-zinc-300 mb-1">
            <span>Top-up</span>
            <span className="text-emerald-300 tabular-nums">{topup.toLocaleString()}</span>
          </div>
          <div className="text-zinc-500 text-[10px] mt-2 pt-2 border-t border-zinc-800">
            {resetLabel ? <>Subscription resets {resetLabel} · Top-up never expires</> : <>Top-up credits never expire</>}
          </div>
        </div>
      )}

      {showTopup && <TopUpModal onClose={() => setShowTopup(false)} />}
    </div>
  );
}

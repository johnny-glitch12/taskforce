/* eslint-disable react/prop-types */
/**
 * CreditCounter — persistent credit balance pill in the navbar.
 *
 * • Always visible when signed in (every page).
 * • Color shifts: cyan (healthy) → amber (low) → red (critical).
 * • Click opens the TopUpModal.
 * • Polls /api/credits/balance every 30s via useCredits().
 * • Admin / unlimited accounts render an infinity glyph instead of the number.
 */
import { useState } from "react";
import { Coins, Plus, Infinity as InfinityIcon } from "lucide-react";
import { useCredits } from "@/lib/credits";
import TopUpModal from "@/components/TopUpModal";

export default function CreditCounter() {
  const { credits, loading } = useCredits();
  const [showTopup, setShowTopup] = useState(false);

  if (loading || !credits) return null;

  const total = credits.total || 0;
  const unlimited = !!credits.unlimited;

  // Color buckets — kept neutral inside the navbar's mono aesthetic.
  let color = "text-cyan-400";
  let borderColor = "rgba(34,211,238,0.25)";
  let glow = "rgba(34,211,238,0.10)";
  if (!unlimited && total <= 5) { color = "text-rose-400"; borderColor = "rgba(244,63,94,0.35)"; glow = "rgba(244,63,94,0.12)"; }
  else if (!unlimited && total <= 50) { color = "text-amber-300"; borderColor = "rgba(251,191,36,0.35)"; glow = "rgba(251,191,36,0.10)"; }

  const display = unlimited ? "∞" : total.toLocaleString();

  return (
    <>
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
        {unlimited ? (
          <InfinityIcon size={11} className={color} />
        ) : (
          <Coins size={11} className={color} />
        )}
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
      {showTopup && <TopUpModal onClose={() => setShowTopup(false)} />}
    </>
  );
}

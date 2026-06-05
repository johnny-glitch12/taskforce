/* eslint-disable react/prop-types */
/**
 * TopUpModal — two tabs: preset Credit Packs + Custom Amount.
 *
 * • Packs → POST /api/credits/topup/checkout {pack}                 → Stripe
 * • Custom → POST /api/credits/topup/custom    {amount_usd}         → Stripe
 *
 * After Stripe → returns to /credits?session_id=...&topup=success
 * which polls the session and credits the wallet via the existing webhook.
 */
import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X, Loader2, Coins, Zap, Sparkles, Wallet, Check } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";

const PACKS = [
  { id: "starter",  name: "Starter",  price: 5,   credits: 200,    blurb: "Try a few builds",   perCredit: "0.025" },
  { id: "builder",  name: "Builder",  price: 19,  credits: 1000,   blurb: "Ship a real bot",    perCredit: "0.019", popular: true },
  { id: "operator", name: "Operator", price: 79,  credits: 5000,   blurb: "Scale your team",    perCredit: "0.016" },
  { id: "agency",   name: "Agency",   price: 299, credits: 25000,  blurb: "Run a fleet",        perCredit: "0.012" },
];

const CUSTOM_RATE = 0.019; // $/credit, matches Builder pack
const QUICK_AMOUNTS = [5, 10, 25, 50, 100];

export default function TopUpModal({ onClose }) {
  const { token } = useAuth();
  const [mode, setMode] = useState("packs"); // 'packs' | 'custom'
  const [packBusy, setPackBusy] = useState(null);
  const [customAmount, setCustomAmount] = useState("");
  const [customBusy, setCustomBusy] = useState(false);

  // Close on Esc
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const buyPack = async (pack) => {
    if (!token) { toast.error("Sign in to top up."); return; }
    setPackBusy(pack.id);
    try {
      const res = await fetch(`${API}/api/credits/topup/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ pack: pack.id }),
      });
      const data = await res.json();
      if (res.ok && data.url) { window.location.href = data.url; return; }
      toast.error(data.detail || "Could not start checkout.");
    } catch { toast.error("Network error."); }
    setPackBusy(null);
  };

  const customCredits = customAmount && !Number.isNaN(parseFloat(customAmount))
    ? Math.floor(parseFloat(customAmount) / CUSTOM_RATE)
    : 0;
  const customValid = customAmount !== "" && parseFloat(customAmount) >= 1 && parseFloat(customAmount) <= 1000;

  const buyCustom = async () => {
    if (!token) { toast.error("Sign in to top up."); return; }
    if (!customValid) return;
    setCustomBusy(true);
    try {
      const res = await fetch(`${API}/api/credits/topup/custom`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ amount_usd: parseFloat(customAmount) }),
      });
      const data = await res.json();
      if (res.ok && data.url) { window.location.href = data.url; return; }
      toast.error(data.detail || "Could not start checkout.");
    } catch { toast.error("Network error."); }
    setCustomBusy(false);
  };

  const modal = (
    <div
      data-testid="topup-modal-backdrop"
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(6px)" }}
      onClick={onClose}
    >
      <div
        data-testid="topup-modal"
        className="w-full max-w-xl rounded-sm overflow-hidden animate-fade-in"
        style={{ background: "#0c0c10", border: "1px solid #1c1c22", boxShadow: "0 20px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(34,211,238,0.06)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid #1a1a1e" }}>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-sm flex items-center justify-center" style={{ background: "rgba(34,211,238,0.12)" }}>
              <Wallet size={13} className="text-cyan-400" />
            </div>
            <div>
              <div className="text-[14px] font-bold tracking-tight text-zinc-100">Top Up Credits</div>
              <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500">Stripe · never expires</div>
            </div>
          </div>
          <button
            data-testid="topup-close"
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-sm text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-5 pt-4">
          <button
            data-testid="topup-tab-packs"
            onClick={() => setMode("packs")}
            className={`flex-1 py-2 text-[10px] font-mono uppercase tracking-[0.18em] rounded-sm transition-all ${
              mode === "packs" ? "text-cyan-300" : "text-zinc-500 hover:text-zinc-300"
            }`}
            style={{
              background: mode === "packs" ? "rgba(34,211,238,0.08)" : "transparent",
              border: `1px solid ${mode === "packs" ? "rgba(34,211,238,0.4)" : "transparent"}`,
            }}
          >
            <Coins size={10} className="inline mr-1.5 -mt-px" />
            Credit Packs
          </button>
          <button
            data-testid="topup-tab-custom"
            onClick={() => setMode("custom")}
            className={`flex-1 py-2 text-[10px] font-mono uppercase tracking-[0.18em] rounded-sm transition-all ${
              mode === "custom" ? "text-cyan-300" : "text-zinc-500 hover:text-zinc-300"
            }`}
            style={{
              background: mode === "custom" ? "rgba(34,211,238,0.08)" : "transparent",
              border: `1px solid ${mode === "custom" ? "rgba(34,211,238,0.4)" : "transparent"}`,
            }}
          >
            <Sparkles size={10} className="inline mr-1.5 -mt-px" />
            Custom Amount
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {mode === "packs" ? (
            <div data-testid="topup-packs-grid" className="grid grid-cols-2 gap-2.5">
              {PACKS.map((p) => (
                <button
                  key={p.id}
                  data-testid={`topup-pack-${p.id}`}
                  onClick={() => buyPack(p)}
                  disabled={packBusy === p.id}
                  className="relative text-left rounded-sm p-3.5 transition-all hover:border-cyan-400/40 disabled:opacity-50"
                  style={{
                    background: p.popular ? "rgba(34,211,238,0.04)" : "rgba(255,255,255,0.015)",
                    border: `1px solid ${p.popular ? "rgba(34,211,238,0.3)" : "#1a1a1e"}`,
                  }}
                >
                  {p.popular && (
                    <span className="absolute top-1.5 right-1.5 text-[8px] font-mono font-bold tracking-[0.12em] uppercase text-cyan-300 px-1.5 py-0.5 rounded-sm" style={{ background: "rgba(34,211,238,0.12)", border: "1px solid rgba(34,211,238,0.4)" }}>
                      BEST VALUE
                    </span>
                  )}
                  <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 mb-1">{p.name}</div>
                  <div className="text-[22px] font-bold font-mono text-cyan-400 leading-none mb-0.5 tabular-nums">
                    {p.credits.toLocaleString()}
                  </div>
                  <div className="text-[9px] uppercase tracking-widest font-mono text-zinc-500 mb-3">credits</div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-[14px] font-bold font-mono text-zinc-100">${p.price}</span>
                    <span className="text-[9px] font-mono text-zinc-500">${p.perCredit}/cr</span>
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-1">{p.blurb}</div>
                  {packBusy === p.id && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-sm" style={{ background: "rgba(0,0,0,0.6)" }}>
                      <Loader2 size={16} className="text-cyan-400 animate-spin" />
                    </div>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div data-testid="topup-custom-panel">
              <label className="block text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500 mb-2">
                Enter amount in USD
              </label>
              <div className="flex gap-2 mb-3">
                <div className="relative flex-1">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 font-mono">$</span>
                  <input
                    data-testid="topup-custom-amount-input"
                    type="number"
                    min="1"
                    max="1000"
                    step="1"
                    value={customAmount}
                    onChange={(e) => setCustomAmount(e.target.value)}
                    placeholder="25"
                    className="w-full pl-7 pr-3 py-2.5 rounded-sm font-mono text-[15px] text-zinc-100 tabular-nums focus:outline-none transition-colors"
                    style={{
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid #2a2a30",
                    }}
                  />
                </div>
                <button
                  data-testid="topup-custom-buy"
                  onClick={buyCustom}
                  disabled={customBusy || !customValid}
                  className="px-5 py-2.5 rounded-sm bg-cyan-400 text-black text-[11px] font-bold font-mono tracking-[0.15em] uppercase hover:bg-cyan-300 transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  {customBusy ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
                  Top Up
                </button>
              </div>

              {customAmount && customValid && (
                <div data-testid="topup-custom-receipt" className="rounded-sm p-3 mb-3" style={{ background: "rgba(34,211,238,0.04)", border: "1px solid rgba(34,211,238,0.18)" }}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-zinc-400">You&apos;ll receive</span>
                    <span data-testid="topup-custom-credits-preview" className="text-cyan-300 font-mono font-bold tabular-nums">
                      ~{customCredits.toLocaleString()} credits
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] mt-1.5 font-mono">
                    <span className="text-zinc-500">Rate</span>
                    <span className="text-zinc-400">${CUSTOM_RATE}/credit</span>
                  </div>
                </div>
              )}

              {/* Quick amount chips */}
              <div className="flex gap-1.5">
                {QUICK_AMOUNTS.map((amt) => (
                  <button
                    key={amt}
                    data-testid={`topup-quick-${amt}`}
                    onClick={() => setCustomAmount(String(amt))}
                    className={`flex-1 py-2 text-[11px] font-mono font-bold rounded-sm transition ${
                      parseFloat(customAmount) === amt
                        ? "text-cyan-300"
                        : "text-zinc-500 hover:text-zinc-200"
                    }`}
                    style={{
                      background: parseFloat(customAmount) === amt ? "rgba(34,211,238,0.08)" : "rgba(255,255,255,0.02)",
                      border: `1px solid ${parseFloat(customAmount) === amt ? "rgba(34,211,238,0.4)" : "#1a1a1e"}`,
                    }}
                  >
                    ${amt}
                  </button>
                ))}
              </div>

              <div className="mt-4 text-[10px] text-zinc-500 leading-relaxed">
                Min $1 · Max $1,000 per purchase. Stack as many top-ups as you need — they never expire.
              </div>
            </div>
          )}
        </div>

        {/* Footer note */}
        <div className="px-5 py-3 text-center text-[10px] text-zinc-500 font-mono tracking-wide" style={{ borderTop: "1px solid #1a1a1e" }}>
          <Check size={9} className="inline -mt-px mr-1 text-emerald-500" />
          Top-up credits never expire · Powered by Stripe
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}

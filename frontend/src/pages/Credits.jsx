import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Coins, Zap, ArrowUpRight, Sparkles, Crown, TrendingUp,
  Gift, ShoppingCart, Loader2, Check, Tag,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function Credits() {
  const { token, user } = useAuth();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [promoCode, setPromoCode] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/credits/me`, { headers: { Authorization: `Bearer ${token}` } });
      setInfo(await res.json());
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!token) return;
    load();
    // Handle Stripe success redirect → poll the session
    const params = new URLSearchParams(window.location.search);
    if (params.get("topup") === "success" && params.get("session_id")) {
      fetch(`${API}/api/credits/topup/poll/${params.get("session_id")}`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      }).then((r) => r.json()).then((d) => {
        if (d.credits_added) toast.success(`+${d.credits_added} credits added.`);
        load();
      });
    }
  }, [token]); // eslint-disable-line

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
        if (data.granted) toast.success(`+${data.granted} credits redeemed.`);
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

  return (
    <div data-testid="credits-page" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-5xl mx-auto">
        {/* Hero */}
        <div className="flex items-center gap-3 mb-2">
          <Coins size={20} className="text-cyan-400" />
          <h1 className="text-2xl md:text-3xl tracking-wide t-text" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: '0.04em' }}>
            CREDIT WALLET
          </h1>
        </div>
        <p className="text-[12px] t-text-dim mb-6 uppercase tracking-widest">
          Credits power The Armory · {info.tier?.toUpperCase()} TIER
        </p>

        {/* Balance card */}
        <div
          data-testid="credit-balance-card"
          className="rounded-sm p-6 mb-6 relative overflow-hidden"
          style={{ background: 'var(--bg-card)', border: '1px solid rgba(34,211,238,0.3)' }}
        >
          <div className="absolute inset-0 pointer-events-none opacity-30"
            style={{ background: 'radial-gradient(circle at 90% 0%, rgba(34,211,238,0.2), transparent 50%)' }} />
          <div className="relative flex items-end justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest t-text-dim font-mono mb-1">Available Balance</div>
              <div className="font-mono text-5xl t-text" data-testid="credit-balance-value">
                {info.unlimited ? "∞" : info.balance.toLocaleString()}
              </div>
              <div className="text-[11px] t-text-mute mt-2 font-mono">
                Monthly tier grant: {info.unlimited ? "Unlimited" : `${info.monthly_grant.toLocaleString()} credits`}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest t-text-dim font-mono mb-1.5">Action Costs</div>
              <div className="space-y-0.5 font-mono text-[11px]">
                {Object.entries(info.action_costs || {}).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 justify-end">
                    <span className="t-text-mute">{k.replace(/_/g, " ")}</span>
                    <span className="text-cyan-400">{v}cr</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Promo + topup */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Promo card */}
          <div className="rounded-sm p-4 col-span-1" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Gift size={13} className="text-cyan-400" />
              <span className="text-[11px] uppercase tracking-widest t-text font-mono">Promo Code</span>
            </div>
            <input
              data-testid="promo-input"
              value={promoCode}
              onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
              placeholder="ENTER CODE"
              className="w-full px-3 py-2 text-[12px] rounded-sm mb-2 font-mono uppercase tracking-wider"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }}
            />
            <button
              data-testid="promo-redeem-btn"
              onClick={redeem}
              disabled={!promoCode || busy}
              className="w-full px-3 py-2 text-[11px] font-medium tracking-widest uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-30 flex items-center justify-center gap-1.5"
            >
              {busy ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              REDEEM
            </button>
            <div className="text-[10px] t-text-dim mt-2 leading-relaxed">
              Apply at top-up checkout for % discount, or redeem standalone for credit codes.
            </div>
          </div>

          {/* Top-up packs */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.entries(info.packs || {}).map(([packId, p]) => (
              <button
                key={packId}
                data-testid={`pack-${packId}`}
                onClick={() => buy(packId)}
                disabled={busy}
                className="rounded-sm p-4 text-left transition-all hover:border-cyan-400/50 disabled:opacity-50 group"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-start justify-between mb-2">
                  <Sparkles size={14} className="text-cyan-400" />
                  <span className="font-mono text-[10px] uppercase tracking-widest t-text-dim">{packId}</span>
                </div>
                <div className="font-mono text-2xl t-text">{p.credits.toLocaleString()}</div>
                <div className="text-[10px] uppercase tracking-widest t-text-dim mt-0.5">CREDITS</div>
                <div className="flex items-center justify-between mt-3 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                  <span className="font-mono text-cyan-400 text-[14px]">${p.price.toFixed(2)}</span>
                  <ArrowUpRight size={12} className="t-text-mute group-hover:text-cyan-400 transition-colors" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Recent transactions */}
        <div className="mt-6 rounded-sm overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 py-2.5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
            <TrendingUp size={12} className="text-cyan-400" />
            <span className="text-[10px] uppercase tracking-widest t-text font-mono">Recent Transactions</span>
          </div>
          {(info.transactions || []).length === 0 && (
            <div className="px-4 py-8 text-center t-text-dim text-[11px] font-mono">— no transactions yet —</div>
          )}
          {(info.transactions || []).map((tx, i) => (
            <div key={i} className="px-4 py-2 flex items-center gap-3 text-[11px] font-mono" style={{ borderBottom: '1px solid var(--border)' }}>
              <span className={tx.delta > 0 ? "text-emerald-400" : "text-rose-400"} style={{ width: 60 }}>
                {tx.delta > 0 ? "+" : ""}{tx.delta}cr
              </span>
              <span className="t-text-mute" style={{ width: 110 }}>{tx.kind}</span>
              <span className="t-text-mute flex-1 truncate">{tx.note}</span>
              <span className="t-text-dim text-[10px]">{tx.created_at?.slice(0, 16).replace("T", " ")}</span>
              <span className="t-text-dim">bal {tx.balance_after}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

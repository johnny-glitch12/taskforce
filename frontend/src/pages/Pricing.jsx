/**
 * Pricing — public pricing page.
 *
 * Three sections:
 *   1. Subscription tier grid (existing TIERS, unchanged behaviour)
 *   2. Dynamic Per-Model Cost Table (pulled from /api/credits/estimate)
 *   3. Top-up packs strip (cards) + BYOK savings panel
 *
 * Everything is single-page, scrollable, with smooth section transitions.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Check, Zap, GraduationCap, Shield, Crown, Key, Lock,
  ArrowRight, BadgeCheck, Loader2, Coins, Sparkles, Cpu, Wallet,
  TrendingDown,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const TIERS = [
  { id: "recruit",  name: "RECRUIT",  backendTier: null,        tagline: "Start building and learning the basics.",
    monthlyPrice: 0,   cta: "Get Started Free",   ctaStyle: "outline", icon: GraduationCap,
    features: ["50 sub credits / mo", "Access to all 6 models", "Command Prompt access", "List on The Exchange (renters pay compute)"] },
  { id: "cadet",    name: "CADET",    backendTier: "cadet",     tagline: "Ad-free advanced learning and expanded testing.",
    monthlyPrice: 19,  cta: "Start 7-Day Trial",  ctaStyle: "outline", icon: Shield,
    features: ["500 sub credits / mo", "100% Ad-Free Academy", "Advanced Masterclass Modules", "Priority Support"] },
  { id: "operator", name: "OPERATOR", backendTier: "operator",  tagline: "For serious builders engineering complex logic.",
    monthlyPrice: 99,  popular: true, cta: "Upgrade to Operator", ctaStyle: "primary", icon: Zap,
    features: ["2,000 sub credits / mo", "Full React Flow Node Builder", "BYOK rebate (platform min only)", "Private Mastermind Access"] },
  { id: "command",  name: "COMMAND",  backendTier: null,        tagline: "High-volume infrastructure for agencies.",
    monthlyPrice: null, cta: "Contact Sales", ctaStyle: "outline", icon: Crown,
    features: ["10,000+ sub credits / mo", "White-label UI", "Dedicated IP Routing", "Custom SLAs"] },
];

const TOPUP_PACKS = [
  { id: "starter",   name: "Starter",  credits: 200,    price: 5,   blurb: "Try a few builds" },
  { id: "builder",   name: "Builder",  credits: 1000,   price: 19,  blurb: "Ship a real bot" },
  { id: "operator",  name: "Operator", credits: 5000,   price: 79,  blurb: "Scale your team" },
  { id: "agency",    name: "Agency",   credits: 25000,  price: 299, blurb: "Run a fleet" },
];

const ACTION_LABELS = {
  vibe_chat:  "Chat",
  vibe_build: "Build (vibe)",
  build_bot:  "Build (armory)",
  agent_run:  "Run agent",
};

function BillingToggle({ annual, setAnnual }) {
  return (
    <div data-testid="billing-toggle" className="flex items-center justify-center gap-4 mb-10">
      <span className={`text-[13px] font-mono tracking-wide uppercase transition-colors ${!annual ? "t-text" : "t-text-dim"}`}>Monthly</span>
      <button
        onClick={() => setAnnual(!annual)}
        data-testid="billing-toggle-btn"
        className="relative w-[48px] h-[24px] rounded-sm transition-all duration-300 focus:outline-none"
        style={{ background: annual ? "#22d3ee" : "var(--border)", border: annual ? "none" : "1px solid var(--border)" }}
      >
        <div className="absolute top-[2px] w-[20px] h-[20px] rounded-sm bg-black transition-transform duration-300" style={{ transform: annual ? "translateX(26px)" : "translateX(2px)" }} />
      </button>
      <span className={`text-[13px] font-mono tracking-wide uppercase transition-colors ${annual ? "t-text" : "t-text-dim"}`}>Annual</span>
      {annual && (
        <span className="text-[10px] font-bold font-mono tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/15 px-2 py-0.5 rounded-sm animate-fade-in">
          SAVE 20%
        </span>
      )}
    </div>
  );
}

function PricingCard({ tier, annual, onSubscribe, subscribing }) {
  const isPopular = tier.popular;
  const price = tier.monthlyPrice === null ? null : annual ? Math.round(tier.monthlyPrice * 0.8) : tier.monthlyPrice;
  const isLoading = subscribing === tier.id;

  return (
    <div
      data-testid={`pricing-card-${tier.id}`}
      className={`relative rounded-sm p-[1px] transition-all duration-500 ${isPopular ? "lg:scale-105" : ""}`}
      style={isPopular ? {
        background: "linear-gradient(180deg, #22d3ee, #0891b2, #22d3ee)",
        backgroundSize: "200% 200%", animation: "gradient-shift 4s ease infinite",
        boxShadow: "0 0 40px rgba(34,211,238,0.12), 0 0 80px rgba(34,211,238,0.04)",
      } : {}}
    >
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <span data-testid="popular-badge" className="text-[10px] font-bold font-mono tracking-[0.15em] text-black px-3 py-1 rounded-sm bg-cyan-400 shadow-[0_4px_20px_rgba(34,211,238,0.3)]">
            MOST POPULAR
          </span>
        </div>
      )}

      <div className={`h-full rounded-sm p-6 flex flex-col ${isPopular ? "pt-8" : ""}`} style={{ background: isPopular ? "var(--bg-primary)" : "var(--bg-card)", border: isPopular ? "none" : "1px solid var(--border)" }}>
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-sm flex items-center justify-center" style={{ background: isPopular ? "rgba(34,211,238,0.1)" : "var(--bg-card-hover)" }}>
            <tier.icon size={16} className={isPopular ? "text-cyan-400" : "t-text-mute"} />
          </div>
          <h3 data-testid={`tier-name-${tier.id}`} className="text-[15px] font-bold tracking-[0.08em] t-text font-mono">{tier.name}</h3>
        </div>

        <p className="text-[12px] t-text-sub leading-relaxed mb-5 min-h-[36px]">{tier.tagline}</p>

        <div className="mb-5">
          {price === null ? (
            <span className="text-2xl font-bold t-text font-mono">Custom</span>
          ) : (
            <div>
              <div className="flex items-baseline gap-1">
                <span data-testid={`tier-price-${tier.id}`} className="text-3xl font-bold t-text font-mono">${price}</span>
                <span className="text-[12px] t-text-dim font-mono">/ mo</span>
              </div>
              {annual && tier.monthlyPrice > 0 && (
                <p className="text-[10px] text-emerald-400 font-mono mt-1">
                  ${price * 12}/yr — <span className="line-through t-text-dim">${tier.monthlyPrice * 12}/yr</span>
                </p>
              )}
            </div>
          )}
        </div>

        {tier.ctaStyle === "primary" ? (
          <button
            onClick={() => tier.backendTier && onSubscribe(tier.id, tier.backendTier)}
            data-testid={`cta-${tier.id}`}
            disabled={isLoading}
            className="w-full py-3 text-[13px] font-bold tracking-wide uppercase rounded-sm transition-all flex items-center justify-center gap-2 mb-6 text-black bg-cyan-400 hover:bg-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.2)] disabled:opacity-50"
          >
            {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            {isLoading ? "Processing..." : tier.cta}
          </button>
        ) : (
          <button
            onClick={tier.backendTier ? () => onSubscribe(tier.id, tier.backendTier) : undefined}
            data-testid={`cta-${tier.id}`}
            disabled={isLoading}
            className="w-full py-3 text-[13px] font-bold tracking-wide uppercase rounded-sm transition-all flex items-center justify-center gap-2 mb-6 t-text hover:text-cyan-400 hover:border-cyan-400/40 disabled:opacity-50"
            style={{ background: "transparent", border: "1px solid var(--border)" }}
          >
            {isLoading ? <Loader2 size={14} className="animate-spin" /> : tier.monthlyPrice === null ? <ArrowRight size={14} /> : <Zap size={14} />}
            {isLoading ? "Processing..." : tier.cta}
          </button>
        )}

        <div className="h-px mb-5" style={{ background: "var(--border)" }} />

        <div className="space-y-3 flex-1">
          {tier.features.map((feat, i) => (
            <div key={i} data-testid={`feature-${tier.id}-${i}`} className="flex items-start gap-2.5">
              <Check size={12} className={isPopular ? "text-cyan-400 mt-0.5 shrink-0" : "text-emerald-500 mt-0.5 shrink-0"} strokeWidth={3} />
              <span className="text-[12px] t-text-sub leading-snug">{feat}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ModelCostMatrix({ matrix, models, actions, margin }) {
  if (!matrix || !matrix.length) return null;
  return (
    <div data-testid="model-cost-matrix" className="rounded-sm overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="px-5 py-4 flex items-center gap-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <Cpu size={14} className="text-cyan-400" />
        <div className="flex-1">
          <div className="text-[12px] font-mono uppercase tracking-[0.18em] t-text">Per-Model Credit Cost (Typical Usage)</div>
          <div className="text-[11px] font-mono t-text-dim mt-0.5">
            1 credit = $0.01 · platform charges {margin.toFixed(1)}× provider cost (60% gross margin) · BYOK pays only the floor
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] font-mono">
          <thead>
            <tr className="t-text-mute uppercase text-[10px] tracking-wider" style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="px-4 py-3 text-left">Model</th>
              {actions.map((a) => (
                <th key={a} className="px-4 py-3 text-right">{ACTION_LABELS[a] || a}</th>
              ))}
              <th className="px-4 py-3 text-right text-purple-400">BYOK</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => {
              const rows = matrix.filter((r) => r.model === m);
              if (!rows.length) return null;
              const byok = rows[0].byok_cost;
              return (
                <tr key={m} data-testid={`model-row-${m}`} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 t-text">{m}</td>
                  {actions.map((a) => {
                    const r = rows.find((x) => x.action === a);
                    return (
                      <td key={a} className="px-4 py-3 text-right" data-testid={`cell-${m}-${a}`}>
                        {r ? (
                          <span>
                            <span className="text-cyan-400 font-bold">{r.typical}</span>
                            <span className="t-text-dim">cr</span>
                            <span className="t-text-dim text-[10px] ml-1">({r.low}–{r.high})</span>
                          </span>
                        ) : <span className="t-text-dim">—</span>}
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-right text-purple-400 font-bold">{byok}cr</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-5 py-3 text-[10px] font-mono t-text-dim" style={{ borderTop: "1px solid var(--border)" }}>
        Numbers are "typical (range)" — final charge depends on real token counts after each call.
      </div>
    </div>
  );
}

function TopupPack({ pack, onBuy, busy }) {
  const perCredit = pack.price / pack.credits;
  return (
    <div data-testid={`topup-${pack.id}`} className="rounded-sm p-5 transition-all hover:border-cyan-400/40" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Coins size={12} className="text-amber-400" />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] t-text-mute">{pack.name}</span>
      </div>
      <div className="text-2xl font-bold t-text font-mono mb-1">{pack.credits.toLocaleString()}<span className="text-[12px] t-text-dim ml-1">cr</span></div>
      <div className="text-[11px] t-text-dim font-mono mb-3">${perCredit.toFixed(3)}/credit · {pack.blurb}</div>
      <button
        onClick={() => onBuy(pack)}
        disabled={busy === pack.id}
        data-testid={`topup-cta-${pack.id}`}
        className="w-full py-2 text-[11px] font-bold font-mono uppercase tracking-[0.15em] rounded-sm transition-all flex items-center justify-center gap-2"
        style={{ background: "var(--cyan)", color: "#000" }}
      >
        {busy === pack.id ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
        ${pack.price}
      </button>
    </div>
  );
}

export default function Pricing() {
  const [annual, setAnnual] = useState(false);
  const [subscribing, setSubscribing] = useState(null);
  const [topupBusy, setTopupBusy] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const { user, token } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // /credits/estimate requires auth — fall back gracefully if anon.
    fetch(`${API}/api/credits/estimate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({}),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setEstimate(d))
      .catch(() => {});
  }, [token]);

  const handleSubscribe = async (tierId, backendTier) => {
    if (!user) {
      toast.error("Please sign in first.");
      navigate("/login");
      return;
    }
    setSubscribing(tierId);
    try {
      const res = await fetch(`${API}/api/subscriptions/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ tier: backendTier, origin_url: window.location.origin }),
      });
      if (res.ok) {
        const data = await res.json();
        window.location.href = data.url;
      } else {
        const err = await res.json();
        toast.error(err.detail || "Checkout failed.");
      }
    } catch { toast.error("Network error."); }
    setSubscribing(null);
  };

  const handleTopup = async (pack) => {
    if (!user) {
      toast.error("Sign in to buy credits.");
      navigate("/login");
      return;
    }
    setTopupBusy(pack.id);
    try {
      const res = await fetch(`${API}/api/credits/topup/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ pack: pack.id, origin_url: window.location.origin }),
      });
      if (res.ok) {
        const data = await res.json();
        window.location.href = data.url;
      } else {
        const err = await res.json();
        toast.error(err.detail || "Top-up failed.");
      }
    } catch { toast.error("Network error."); }
    setTopupBusy(null);
  };

  const sortedModels = useMemo(() => {
    if (!estimate?.matrix) return [];
    // Keep gemini/openai/claude order from the API response.
    return estimate.models;
  }, [estimate]);

  return (
    <div data-testid="pricing-page" className="min-h-[calc(100vh-56px)] px-6 lg:px-8 py-16 md:py-20 relative overflow-hidden">
      <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] rounded-full bg-cyan-500/[0.02] blur-[140px] pointer-events-none t-orb" />

      <div className="max-w-6xl mx-auto relative">
        {/* Hero */}
        <div className="text-center mb-4">
          <div className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <Sparkles size={11} className="text-cyan-400" />
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">Pay only for what you use</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-[-0.02em] leading-[1.08] t-text mb-5">
            Smart, Dynamic <span className="text-gradient-cyan">Pricing</span>
          </h1>
          <p className="text-base md:text-lg t-text-sub max-w-2xl mx-auto leading-relaxed mb-10">
            Credits are charged on real token usage — not flat fees. Bring your own API key and pay only the platform minimum.
          </p>
        </div>

        <BillingToggle annual={annual} setAnnual={setAnnual} />

        {/* Tier grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-20 items-start">
          {TIERS.map((tier) => (
            <PricingCard key={tier.id} tier={tier} annual={annual} onSubscribe={handleSubscribe} subscribing={subscribing} />
          ))}
        </div>

        {/* Dynamic model cost matrix */}
        <div className="mb-20">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Cpu size={11} className="text-cyan-400" />
              <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">Per-Model Cost</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight t-text mb-2">What does each call cost?</h2>
            <p className="text-sm t-text-sub max-w-lg mx-auto">
              We re-price every call against actual provider rates. Pick a cheap model for simple jobs, a strong model when it matters.
            </p>
          </div>
          {estimate ? (
            <ModelCostMatrix matrix={estimate.matrix} models={sortedModels} actions={estimate.actions} margin={estimate.platform_margin} />
          ) : (
            <div className="rounded-sm p-8 text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Loader2 className="animate-spin mx-auto mb-3 t-text-mute" size={20} />
              <div className="text-[11px] font-mono t-text-dim">
                {token ? "Loading cost matrix…" : "Sign in to see dynamic per-model pricing."}
              </div>
            </div>
          )}
        </div>

        {/* Top-up packs */}
        <div className="mb-20">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Wallet size={11} className="text-amber-400" />
              <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">Top-Up Packs</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight t-text mb-2">Need more credits?</h2>
            <p className="text-sm t-text-sub max-w-lg mx-auto">One-time top-ups never expire. Stack as much as you need.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {TOPUP_PACKS.map((p) => (
              <TopupPack key={p.id} pack={p} onBuy={handleTopup} busy={topupBusy} />
            ))}
          </div>
        </div>

        {/* BYOK panel */}
        <div data-testid="byok-panel" className="rounded-sm p-6 mb-12" style={{ background: "linear-gradient(135deg, rgba(168,85,247,0.06), rgba(34,211,238,0.04))", border: "1px solid rgba(168,85,247,0.25)" }}>
          <div className="flex items-start gap-4 flex-wrap">
            <div className="w-12 h-12 rounded-sm flex items-center justify-center shrink-0" style={{ background: "rgba(168,85,247,0.15)" }}>
              <Key size={18} className="text-purple-400" />
            </div>
            <div className="flex-1 min-w-[260px]">
              <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-purple-400 mb-2">BRING YOUR OWN KEY</div>
              <h3 className="text-xl font-bold t-text mb-2">Pay only the platform floor when you bring your own API key</h3>
              <p className="text-sm t-text-sub mb-3">
                Add your OpenAI or Anthropic key in the Vault and every call routes through your key. You pay only the platform's minimum action fee.
                Typical savings of <span className="text-emerald-400 font-bold">60–95%</span> per call vs platform-key pricing.
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate("/credentials")}
                  data-testid="byok-cta"
                  className="inline-flex items-center gap-2 px-4 py-2 text-[11px] font-bold font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
                  style={{ background: "rgba(168,85,247,0.2)", color: "#c084fc", border: "1px solid rgba(168,85,247,0.4)" }}
                >
                  <Lock size={11} /> Set up BYOK
                </button>
                <div className="text-[10px] font-mono t-text-dim ml-2 inline-flex items-center gap-1.5">
                  <TrendingDown size={11} className="text-emerald-400" />
                  Avg call drops from <span className="text-cyan-400 mx-0.5">3–5cr</span> → <span className="text-purple-400 mx-0.5">1–2cr</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Trust bar */}
        <div className="text-center">
          <div className="inline-flex flex-wrap items-center justify-center gap-6 px-6 py-3 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            {[
              { icon: Lock, text: "256-BIT ENCRYPTION" },
              { icon: Shield, text: "SOC 2 COMPLIANT" },
              { icon: BadgeCheck, text: "99.9% UPTIME SLA" },
            ].map((item) => (
              <div key={item.text} className="flex items-center gap-2 text-[10px] font-mono tracking-wide t-text-dim">
                <item.icon size={12} className="text-cyan-400" /> {item.text}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

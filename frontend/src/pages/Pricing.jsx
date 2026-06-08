/**
 * Pricing — public pricing page.
 *
 * Sections:
 *   1. Hero
 *   2. Subscription tier grid
 *   3. Top-up packs strip
 *   4. BYOK savings panel
 *   5. Trust bar
 *
 * Per-action / per-model credit pricing is intentionally hidden. The user buys
 * a plan or top-up; the platform handles the rest behind the scenes.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Check, Zap, GraduationCap, Shield, Crown, Key, Lock,
  ArrowRight, BadgeCheck, Loader2, Coins, Sparkles, Wallet,
  Infinity as InfinityIcon,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const TIERS = [
  { id: "recruit",  name: "RECRUIT",  backendTier: null,        tagline: "Start building and learning the basics.",
    monthlyPrice: 0,   cta: "Get Started Free",   ctaStyle: "outline", icon: GraduationCap,
    features: ["Includes a generous starter allowance", "Access to all 6 models", "Command Prompt access", "List on The Exchange"] },
  { id: "cadet",    name: "CADET",    backendTier: "cadet",     tagline: "Ad-free advanced learning and expanded testing.",
    monthlyPrice: 19,  cta: "Start 7-Day Trial",  ctaStyle: "outline", icon: Shield,
    features: ["Higher monthly allowance", "100% Ad-Free Academy", "Advanced Masterclass Modules", "Priority Support"] },
  { id: "operator", name: "OPERATOR", backendTier: "operator",  tagline: "For serious builders engineering complex logic.",
    monthlyPrice: 99,  popular: true, cta: "Upgrade to Operator", ctaStyle: "primary", icon: Zap,
    features: ["Pro-grade monthly allowance", "Full Visual Node Builder", "BYOK key support (deep discount)", "Private Mastermind Access"] },
  { id: "command",  name: "COMMAND",  backendTier: null,        tagline: "High-volume infrastructure for agencies.",
    monthlyPrice: null, cta: "Contact Sales", ctaStyle: "outline", icon: Crown,
    features: ["Custom allowance & SLA", "White-label UI", "Dedicated IP Routing", "Custom integrations"] },
];

const TOPUP_PACKS = [
  { id: "starter",   name: "Starter",  credits: 200,    price: 5,   blurb: "Try a few builds" },
  { id: "builder",   name: "Builder",  credits: 1000,   price: 19,  blurb: "Ship a real bot" },
  { id: "operator",  name: "Operator", credits: 5000,   price: 79,  blurb: "Scale your team" },
  { id: "agency",    name: "Agency",   credits: 25000,  price: 299, blurb: "Run a fleet" },
];

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

function TopupPack({ pack, onBuy, busy }) {
  return (
    <div data-testid={`topup-${pack.id}`} className="rounded-sm p-5 transition-all hover:border-cyan-400/40" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Coins size={12} className="text-amber-400" />
        <span className="text-[10px] font-mono uppercase tracking-[0.15em] t-text-mute">{pack.name}</span>
      </div>
      <div className="text-2xl font-bold t-text font-mono mb-1">{pack.credits.toLocaleString()}<span className="text-[12px] t-text-dim ml-1">cr</span></div>
      <div className="text-[11px] t-text-dim font-mono mb-3">{pack.blurb}</div>
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

function ValueProps() {
  const items = [
    { icon: InfinityIcon, title: "Monthly allowance",
      text: "Every plan ships with a generous monthly allowance — chat, build, and run agents without watching a meter." },
    { icon: Sparkles, title: "Top-ups never expire",
      text: "Need a sprint of extra builds? Add a top-up pack any time. They stay in your wallet forever." },
    { icon: Key, title: "Bring your own keys",
      text: "Drop in your OpenAI or Anthropic key and your usage goes deep-discount. Models stay the same." },
  ];
  return (
    <div data-testid="value-props" className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-16">
      {items.map((it) => (
        <div key={it.title} className="rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2 mb-2">
            <it.icon size={14} className="text-cyan-400" />
            <span className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-mute">{it.title}</span>
          </div>
          <p className="text-[12px] t-text-sub leading-relaxed">{it.text}</p>
        </div>
      ))}
    </div>
  );
}

export default function Pricing() {
  const [annual, setAnnual] = useState(false);
  const [subscribing, setSubscribing] = useState(null);
  const [topupBusy, setTopupBusy] = useState(null);
  const { user, token } = useAuth();
  const navigate = useNavigate();

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

  return (
    <div data-testid="pricing-page" className="min-h-[calc(100vh-56px)] px-6 lg:px-8 py-16 md:py-20 relative overflow-hidden">
      <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] rounded-full bg-cyan-500/[0.02] blur-[140px] pointer-events-none t-orb" />

      <div className="max-w-6xl mx-auto relative">
        {/* Hero */}
        <div className="text-center mb-4">
          <div className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <Sparkles size={11} className="text-cyan-400" />
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">One subscription. Build anything.</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-[-0.02em] leading-[1.08] t-text mb-5">
            Simple, predictable <span className="text-gradient-cyan">pricing</span>
          </h1>
          <p className="text-base md:text-lg t-text-sub max-w-2xl mx-auto leading-relaxed mb-10">
            Pick a plan that fits your workflow. Build, chat, and run AI agents with a single monthly allowance — no per-call math, no surprise bills.
          </p>
        </div>

        <BillingToggle annual={annual} setAnnual={setAnnual} />

        {/* Tier grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-20 items-start">
          {TIERS.map((tier) => (
            <PricingCard key={tier.id} tier={tier} annual={annual} onSubscribe={handleSubscribe} subscribing={subscribing} />
          ))}
        </div>

        {/* Value props */}
        <ValueProps />

        {/* Top-up packs */}
        <div className="mb-20">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <Wallet size={11} className="text-amber-400" />
              <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">Top-Up Packs</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight t-text mb-2">Need more headroom?</h2>
            <p className="text-sm t-text-sub max-w-lg mx-auto">One-time top-ups never expire. Stack as much as you need on top of your plan.</p>
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
              <h3 className="text-xl font-bold t-text mb-2">Already paying OpenAI or Anthropic? Drop your key in.</h3>
              <p className="text-sm t-text-sub mb-3">
                Add a personal key in the Vault and the platform uses it for your calls.
                You pay the API directly and your TaskForce allowance lasts dramatically longer.
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
              </div>
            </div>
          </div>
        </div>

        {/* Trust bar — removed at launch.
            Re-enable once we have real, verifiable certifications (SOC 2 audit,
            published uptime metrics). Until then ship nothing > ship lies. */}
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Check, Zap, GraduationCap, Shield, Terminal,
  Crown, Users, Server, Globe, Key, Lock,
  Headphones, ArrowRight, BadgeCheck, Sparkles,
} from "lucide-react";

const TIERS = [
  {
    id: "recruit",
    name: "RECRUIT",
    tagline: "Start building and learning the basics.",
    monthlyPrice: 0,
    cta: "Get Started Free",
    ctaStyle: "outline",
    icon: GraduationCap,
    features: [
      "Ad-supported Academy Courses",
      "100 Test Executions / mo",
      "Command Prompt access",
      "List on The Exchange (Renters pay compute)",
    ],
  },
  {
    id: "cadet",
    name: "CADET",
    tagline: "Ad-free advanced learning and expanded testing.",
    monthlyPrice: 19,
    cta: "Start 7-Day Trial",
    ctaStyle: "outline",
    icon: Shield,
    features: [
      "100% Ad-Free Academy",
      "Advanced Masterclass Modules",
      "500 Test Executions / mo",
      "Priority Support",
    ],
  },
  {
    id: "operator",
    name: "OPERATOR",
    tagline: "For serious builders engineering complex logic.",
    monthlyPrice: 99,
    popular: true,
    cta: "Upgrade to Operator",
    ctaStyle: "primary",
    icon: Zap,
    features: [
      "Full React Flow Node Builder in The Armory",
      "Bring Your Own Keys (BYOK)",
      "2,000 Executions / mo (Pay as you scale)",
      "Private Mastermind Access",
    ],
  },
  {
    id: "command",
    name: "COMMAND",
    tagline: "High-volume infrastructure for agencies.",
    monthlyPrice: null,
    cta: "Contact Sales",
    ctaStyle: "outline",
    icon: Crown,
    features: [
      "White-label UI",
      "Dedicated IP Routing",
      "X/Discord Integrations",
      "Custom SLAs",
    ],
  },
];

function BillingToggle({ annual, setAnnual }) {
  return (
    <div data-testid="billing-toggle" className="flex items-center justify-center gap-4 mb-14">
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

function PricingCard({ tier, annual }) {
  const isPopular = tier.popular;
  const price = tier.monthlyPrice === null ? null : annual ? Math.round(tier.monthlyPrice * 0.8) : tier.monthlyPrice;

  return (
    <div
      data-testid={`pricing-card-${tier.id}`}
      className={`relative rounded-sm p-[1px] transition-all duration-500 ${isPopular ? "lg:scale-105" : ""}`}
      style={isPopular ? {
        background: "linear-gradient(180deg, #22d3ee, #0891b2, #22d3ee)",
        backgroundSize: "200% 200%",
        animation: "gradient-shift 4s ease infinite",
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
        {/* Tier */}
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-sm flex items-center justify-center" style={{ background: isPopular ? "rgba(34,211,238,0.1)" : "var(--bg-card-hover)" }}>
            <tier.icon size={16} className={isPopular ? "text-cyan-400" : "t-text-mute"} />
          </div>
          <h3 data-testid={`tier-name-${tier.id}`} className="text-[15px] font-bold tracking-[0.08em] t-text font-mono">{tier.name}</h3>
        </div>

        <p className="text-[12px] t-text-sub leading-relaxed mb-5 min-h-[36px]">{tier.tagline}</p>

        {/* Price */}
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

        {/* CTA */}
        {tier.ctaStyle === "primary" ? (
          <Link to="/login" data-testid={`cta-${tier.id}`} className="w-full py-3 text-[13px] font-bold tracking-wide uppercase rounded-sm transition-all flex items-center justify-center gap-2 mb-6 text-black bg-cyan-400 hover:bg-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.2)]">
            <Zap size={14} /> {tier.cta}
          </Link>
        ) : (
          <Link to={tier.monthlyPrice === null ? "#" : "/login"} data-testid={`cta-${tier.id}`} className="w-full py-3 text-[13px] font-bold tracking-wide uppercase rounded-sm transition-all flex items-center justify-center gap-2 mb-6 t-text hover:text-cyan-400 hover:border-cyan-400/40" style={{ background: "transparent", border: "1px solid var(--border)" }}>
            {tier.monthlyPrice === null ? <ArrowRight size={14} /> : <Zap size={14} />} {tier.cta}
          </Link>
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

export default function Pricing() {
  const [annual, setAnnual] = useState(false);

  return (
    <div data-testid="pricing-page" className="min-h-[calc(100vh-56px)] px-6 lg:px-8 py-16 md:py-20 relative overflow-hidden">
      <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] rounded-full bg-cyan-500/[0.02] blur-[140px] pointer-events-none t-orb" />

      <div className="max-w-6xl mx-auto relative">
        <div className="text-center mb-4">
          <div className="inline-flex items-center gap-2 mb-6 px-3 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <Zap size={11} className="text-cyan-400" />
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">Subscription Matrix</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-[-0.02em] leading-[1.08] t-text mb-5">
            Choose Your <span className="text-gradient-cyan">Mission Tier</span>
          </h1>
          <p className="text-base md:text-lg t-text-sub max-w-lg mx-auto leading-relaxed mb-10">
            From solo operators to full-scale agencies. Scale your AI agent infrastructure on your terms.
          </p>
        </div>

        <BillingToggle annual={annual} setAnnual={setAnnual} />

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-16 items-start">
          {TIERS.map((tier) => <PricingCard key={tier.id} tier={tier} annual={annual} />)}
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

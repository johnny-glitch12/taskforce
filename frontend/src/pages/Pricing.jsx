import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Check, Zap, GraduationCap, Shield, Terminal,
  Crown, Users, Server, Globe, Key, Lock,
  Headphones, Sparkles, ArrowRight, BadgeCheck,
} from "lucide-react";

const TIERS = [
  {
    id: "recruit",
    name: "Recruit",
    tagline: "Start building and learning the basics.",
    monthlyPrice: 0,
    cta: "Get Started Free",
    ctaStyle: "outline",
    icon: GraduationCap,
    features: [
      { text: "Ad-supported Beginner/Medium Courses", icon: GraduationCap },
      { text: "100 Test Executions / mo", icon: Terminal },
      { text: "Standard Vibe-Coding", icon: Sparkles },
      { text: "List on Marketplace", icon: Globe },
    ],
  },
  {
    id: "cadet",
    name: "Cadet",
    tagline: "Ad-free advanced learning and expanded testing.",
    monthlyPrice: 19,
    cta: "Start 7-Day Trial",
    ctaStyle: "outline",
    icon: Shield,
    features: [
      { text: "Unlocked Advanced Training Modules", icon: GraduationCap },
      { text: "100% Ad-Free Academy Experience", icon: BadgeCheck },
      { text: "500 Test Executions / mo", icon: Terminal },
      { text: "Priority Support", icon: Headphones },
    ],
  },
  {
    id: "operator",
    name: "Operator",
    tagline: "For serious builders engineering complex logic.",
    monthlyPrice: 99,
    popular: true,
    cta: "Upgrade to Operator",
    ctaStyle: "primary",
    icon: Zap,
    features: [
      { text: "Full React Flow Visual Builder", icon: Sparkles },
      { text: "Bring Your Own Keys (BYOK)", icon: Key },
      { text: "2,000 Executions / mo (Pay as you scale)", icon: Terminal },
      { text: "Private Mastermind Discord", icon: Users },
    ],
  },
  {
    id: "command",
    name: "Command",
    tagline: "High-volume infrastructure for agencies.",
    monthlyPrice: null,
    cta: "Contact Sales",
    ctaStyle: "outline",
    icon: Crown,
    features: [
      { text: "White-label Interface", icon: Globe },
      { text: "Dedicated IP Routing", icon: Server },
      { text: "Custom SLAs", icon: Lock },
      { text: "Team Onboarding", icon: Users },
    ],
  },
];

function BillingToggle({ annual, setAnnual }) {
  return (
    <div data-testid="billing-toggle" className="flex items-center justify-center gap-4 mb-14">
      <span className={`text-[14px] font-medium transition-colors ${!annual ? "t-text" : "t-text-dim"}`}>
        Monthly
      </span>
      <button
        onClick={() => setAnnual(!annual)}
        data-testid="billing-toggle-btn"
        className="relative w-[52px] h-[28px] rounded-full transition-all duration-300 focus:outline-none"
        style={{
          background: annual
            ? "linear-gradient(135deg, #8B5CF6, #6D28D9)"
            : "var(--bg-card-hover)",
          border: annual ? "none" : "1px solid var(--border)",
        }}
        aria-label={annual ? "Switch to monthly" : "Switch to annual"}
      >
        <div
          className="absolute top-[3px] w-[22px] h-[22px] rounded-full bg-white shadow-md transition-transform duration-300"
          style={{ transform: annual ? "translateX(27px)" : "translateX(3px)" }}
        />
      </button>
      <span className={`text-[14px] font-medium transition-colors ${annual ? "t-text" : "t-text-dim"}`}>
        Annual
      </span>
      {annual && (
        <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full animate-fade-in">
          Save 20%
        </span>
      )}
    </div>
  );
}

function PricingCard({ tier, annual }) {
  const isPopular = tier.popular;
  const price = tier.monthlyPrice === null
    ? null
    : annual
      ? Math.round(tier.monthlyPrice * 0.8)
      : tier.monthlyPrice;

  return (
    <div
      data-testid={`pricing-card-${tier.id}`}
      className={`relative rounded-2xl p-[1px] transition-all duration-500 ${
        isPopular ? "scale-[1.02] lg:scale-105" : ""
      }`}
      style={isPopular ? {
        background: "linear-gradient(135deg, #8B5CF6, #6D28D9, #8B5CF6)",
        backgroundSize: "200% 200%",
        animation: "gradient-shift 4s ease infinite",
        boxShadow: "0 0 40px rgba(139,92,246,0.2), 0 0 80px rgba(139,92,246,0.08)",
      } : {}}
    >
      {/* Popular badge */}
      {isPopular && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
          <span
            data-testid="popular-badge"
            className="text-[11px] font-semibold text-white tracking-wide px-4 py-1.5 rounded-full"
            style={{
              background: "linear-gradient(135deg, #8B5CF6, #6D28D9)",
              boxShadow: "0 4px 20px rgba(139,92,246,0.4)",
            }}
          >
            MOST POPULAR
          </span>
        </div>
      )}

      <div
        className={`h-full rounded-2xl p-6 lg:p-7 flex flex-col ${isPopular ? "pt-9" : ""}`}
        style={{
          background: isPopular ? "var(--bg-primary)" : "var(--bg-card)",
          border: isPopular ? "none" : "1px solid var(--border)",
        }}
      >
        {/* Tier Icon + Name */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{
              background: isPopular ? "rgba(139,92,246,0.15)" : "var(--bg-card-hover)",
            }}
          >
            <tier.icon size={18} className={isPopular ? "text-[#A78BFA]" : "t-text-mute"} />
          </div>
          <div>
            <h3
              data-testid={`tier-name-${tier.id}`}
              className="text-[16px] font-semibold t-text"
              style={{ fontFamily: "'Outfit', sans-serif" }}
            >
              {tier.name}
            </h3>
          </div>
        </div>

        {/* Tagline */}
        <p className="text-[13px] t-text-sub leading-relaxed mb-6 min-h-[40px]">
          {tier.tagline}
        </p>

        {/* Price */}
        <div className="mb-6">
          {price === null ? (
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
                Custom
              </span>
            </div>
          ) : price === 0 ? (
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
                $0
              </span>
              <span className="text-[13px] t-text-dim">/ month</span>
            </div>
          ) : (
            <div>
              <div className="flex items-baseline gap-1">
                <span
                  data-testid={`tier-price-${tier.id}`}
                  className="text-3xl font-bold t-text"
                  style={{ fontFamily: "'Outfit', sans-serif" }}
                >
                  ${price}
                </span>
                <span className="text-[13px] t-text-dim">/ month</span>
              </div>
              {annual && tier.monthlyPrice > 0 && (
                <p className="text-[11px] text-emerald-400 mt-1">
                  ${price * 12}/yr — <span className="line-through t-text-dim">${tier.monthlyPrice * 12}/yr</span>
                </p>
              )}
            </div>
          )}
        </div>

        {/* CTA */}
        {tier.ctaStyle === "primary" ? (
          <Link
            to={tier.monthlyPrice === null ? "#" : "/login"}
            data-testid={`cta-${tier.id}`}
            className="w-full py-3 text-[14px] font-medium rounded-full transition-all duration-300 flex items-center justify-center gap-2 mb-7 text-white"
            style={{
              background: "linear-gradient(135deg, #8B5CF6, #6D28D9)",
              boxShadow: "0 0 25px rgba(139,92,246,0.3), inset 0 1px 0 rgba(255,255,255,0.1)",
            }}
          >
            <Zap size={14} /> {tier.cta}
          </Link>
        ) : (
          <Link
            to={tier.monthlyPrice === null ? "#" : tier.monthlyPrice === 0 ? "/login" : "/login"}
            data-testid={`cta-${tier.id}`}
            className="w-full py-3 text-[14px] font-medium rounded-full transition-all duration-300 flex items-center justify-center gap-2 mb-7 t-text hover:border-[#8B5CF6]/40"
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
            }}
          >
            {tier.monthlyPrice === null ? <ArrowRight size={14} /> : <Zap size={14} />}
            {tier.cta}
          </Link>
        )}

        {/* Divider */}
        <div className="h-px mb-5" style={{ background: "var(--border)" }} />

        {/* Features */}
        <div className="space-y-3.5 flex-1">
          {tier.features.map((feat, i) => (
            <div key={i} data-testid={`feature-${tier.id}-${i}`} className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-md flex items-center justify-center shrink-0 mt-0.5" style={{ background: isPopular ? "rgba(139,92,246,0.12)" : "var(--bg-card-hover)" }}>
                <Check size={11} className={isPopular ? "text-[#A78BFA]" : "text-emerald-400"} strokeWidth={3} />
              </div>
              <span className="text-[13px] t-text-sub leading-snug">{feat.text}</span>
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
    <div data-testid="pricing-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-16 md:py-20 relative overflow-hidden">
      {/* Ambient orbs */}
      <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] rounded-full bg-[#8B5CF6]/[0.04] blur-[140px] pointer-events-none t-orb" />
      <div className="absolute bottom-[0%] right-[10%] w-[400px] h-[400px] rounded-full bg-[#6D28D9]/[0.03] blur-[120px] pointer-events-none t-orb" />

      <div className="max-w-6xl mx-auto relative">
        {/* Header */}
        <div className="text-center mb-4">
          <div
            className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            <Zap size={12} className="text-[#8B5CF6]" />
            <span className="text-[11px] tracking-[0.15em] t-text-sub">PRICING</span>
          </div>
          <h1
            className="text-4xl sm:text-5xl lg:text-[4rem] font-bold tracking-[-0.03em] leading-[1.08] t-text mb-5"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            Choose Your{" "}
            <span className="text-gradient-purple">Mission Tier</span>
          </h1>
          <p className="text-base md:text-lg t-text-sub max-w-lg mx-auto leading-relaxed mb-10">
            From solo operators to full-scale agencies. Scale your AI agent infrastructure on your terms.
          </p>
        </div>

        {/* Toggle */}
        <BillingToggle annual={annual} setAnnual={setAnnual} />

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 lg:gap-4 mb-20 items-start">
          {TIERS.map((tier) => (
            <PricingCard key={tier.id} tier={tier} annual={annual} />
          ))}
        </div>

        {/* Bottom trust bar */}
        <div className="text-center">
          <div
            className="inline-flex flex-wrap items-center justify-center gap-6 px-8 py-4 rounded-2xl"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            {[
              { icon: Lock, text: "256-bit SSL Encryption" },
              { icon: Shield, text: "SOC 2 Compliant" },
              { icon: BadgeCheck, text: "99.9% Uptime SLA" },
            ].map((item) => (
              <div key={item.text} className="flex items-center gap-2 text-[12px] t-text-sub">
                <item.icon size={13} className="text-[#8B5CF6]" />
                {item.text}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

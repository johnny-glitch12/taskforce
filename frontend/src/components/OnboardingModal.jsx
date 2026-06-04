import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { Sparkles, Coins, Bot, Zap, ArrowRight, X, Check } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STEPS = [
  {
    icon: Coins,
    accent: "#fbbf24",
    title: "Welcome, operative.",
    body: "You're starting with 100 credits — 50 monthly (resets each cycle) plus 50 lifetime top-up credits as a welcome bonus.",
    cta: { label: "Show me what I can do", action: "next" },
  },
  {
    icon: Bot,
    accent: "#22d3ee",
    title: "Build a bot in plain English.",
    body: "Head to BUILD, describe what you want, and watch the AI plan + generate a complete agent. Conversation costs 1cr per AI reply, code generation costs 2-5cr depending on the model you pick.",
    cta: { label: "Continue", action: "next" },
  },
  {
    icon: Sparkles,
    accent: "#a78bfa",
    title: "Six AI models. Always unlocked.",
    body: "Gemini Flash / Pro, GPT-4o / Mini, Claude Sonnet / Haiku — all available immediately. Not sure which to pick? Hit the AUTO button and we'll route you to the right one based on your task.",
    cta: { label: "Continue", action: "next" },
  },
  {
    icon: Zap,
    accent: "#34d399",
    title: "Ready when you are.",
    body: "Tip: try a simple prompt first like 'a bot that posts trending HackerNews stories to my Slack channel every hour' — you'll see how fast the platform compiles real, runnable code.",
    cta: { label: "Let's build →", action: "start" },
  },
];

export default function OnboardingModal({ onClose }) {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const dismiss = async () => {
    try {
      await fetch(`${API}/api/onboarding/complete`, { method: "POST", headers });
    } catch { /* non-fatal — they'll just see it once more */ }
    onClose?.();
  };

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));

  const launch = async () => {
    await dismiss();
    navigate("/build");
  };

  const s = STEPS[step];
  const Icon = s.icon;

  return (
    <div
      data-testid="onboarding-modal"
      className="fixed inset-0 z-[100] flex items-center justify-center px-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
    >
      <div
        className="relative w-full max-w-md rounded-sm overflow-hidden"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
      >
        {/* Top accent bar */}
        <div className="h-[3px] w-full" style={{ background: s.accent }} />

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono uppercase tracking-[0.22em] t-text-dim">
              Step {step + 1} of {STEPS.length}
            </span>
          </div>
          <button
            data-testid="onboarding-skip"
            onClick={dismiss}
            className="t-text-dim hover:t-text text-[10px] font-mono uppercase tracking-widest flex items-center gap-1"
          >
            Skip <X size={11} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 text-center">
          <div
            className="w-14 h-14 rounded-sm flex items-center justify-center mx-auto mb-4"
            style={{ background: `${s.accent}18`, border: `1px solid ${s.accent}55` }}
          >
            <Icon size={22} style={{ color: s.accent }} />
          </div>
          <h2 className="text-xl font-bold t-text mb-2 tracking-tight" style={{ fontFamily: "'Rajdhani', sans-serif" }}>
            {s.title}
          </h2>
          <p className="text-[12px] t-text-sub leading-relaxed font-mono">
            {s.body}
          </p>
        </div>

        {/* Step dots */}
        <div className="flex items-center justify-center gap-1.5 pb-2">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className="h-1 rounded-full transition-all"
              style={{
                width: i === step ? 18 : 6,
                background: i === step ? s.accent : "var(--border)",
              }}
            />
          ))}
        </div>

        {/* CTA */}
        <div className="px-5 pb-5 pt-2">
          <button
            data-testid="onboarding-cta"
            onClick={s.cta.action === "start" ? launch : next}
            className="w-full py-3 text-[11px] font-bold tracking-[0.18em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 flex items-center justify-center gap-1.5"
          >
            {s.cta.action === "start" ? <Check size={11} /> : null}
            {s.cta.label}
            {s.cta.action !== "start" && <ArrowRight size={11} />}
          </button>
        </div>
      </div>
    </div>
  );
}

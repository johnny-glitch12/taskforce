/**
 * Academy — placeholder Coming Soon experience while curriculum is in production.
 *
 * Three locked-course teaser cards (matched to TaskForce's actual workflow:
 * build → monetize → integrate) + a waitlist email signup hitting the existing
 * /api/waitlist endpoint with source="academy" so we can segment leads.
 */
import { useState } from "react";
import usePageTitle from "@/hooks/usePageTitle";
import {
  GraduationCap, Lock, Rocket, Coins, Plug, Loader2, Check, ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COURSES = [
  {
    n: "01",
    Icon: Rocket,
    title: "Build Your First Agent",
    blurb: "From zero to deployed in 30 minutes. Vibe coding, model picking, deployment basics.",
  },
  {
    n: "02",
    Icon: Coins,
    title: "Agent Monetization",
    blurb: "List, price, and sell on The Exchange. Credits, payouts, and the 90/10 split explained.",
  },
  {
    n: "03",
    Icon: Plug,
    title: "Advanced Integrations",
    blurb: "Gmail, Stripe, Slack, custom webhooks — wire your agent into anything.",
  },
];

function EmailSignup() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    const value = email.trim();
    if (!value || !/.+@.+\..+/.test(value)) {
      toast.error("Enter a valid email.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: value, source: "academy" }),
      });
      if (res.ok) {
        setDone(true);
        toast.success("You're on the list. We'll email you when courses unlock.");
      } else {
        const body = await res.json().catch(() => ({}));
        toast.error(body.detail || "Could not add you to the list.");
      }
    } catch {
      toast.error("Network error.");
    }
    setBusy(false);
  };

  if (done) {
    return (
      <div
        data-testid="academy-signup-success"
        className="inline-flex items-center gap-2 px-4 py-3 rounded-sm text-[12px] font-mono uppercase tracking-[0.15em]"
        style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.35)", color: "#10b981" }}
      >
        <Check size={13} /> You&apos;re on the list
      </div>
    );
  }

  return (
    <form
      onSubmit={submit}
      data-testid="academy-signup-form"
      className="flex items-stretch gap-2 max-w-md mx-auto"
    >
      <input
        data-testid="academy-email-input"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        autoComplete="email"
        className="flex-1 px-3.5 py-3 rounded-sm text-[13px] focus:outline-none transition-colors"
        style={{
          background: "var(--input-bg)",
          border: "1px solid var(--input-border)",
          color: "var(--text-primary)",
        }}
      />
      <button
        type="submit"
        data-testid="academy-notify-btn"
        disabled={busy}
        className="px-5 py-3 text-[11px] font-bold font-mono tracking-[0.18em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition disabled:opacity-50 flex items-center gap-2"
      >
        {busy ? <Loader2 size={12} className="animate-spin" /> : <ArrowRight size={12} />}
        Notify Me
      </button>
    </form>
  );
}

export default function Academy() {
  usePageTitle("The Academy");
  return (
    <div data-testid="academy-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 md:py-20 relative overflow-hidden">
      {/* Background orb */}
      <div className="absolute top-[18%] left-1/2 -translate-x-1/2 w-[480px] h-[480px] rounded-full bg-cyan-400/[0.05] blur-[140px] pointer-events-none t-orb" />

      <div className="max-w-4xl mx-auto relative text-center">
        {/* Icon + Title */}
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-sm mb-6"
          style={{
            background: "linear-gradient(135deg, rgba(34,211,238,0.15), rgba(34,211,238,0.04))",
            border: "1px solid rgba(34,211,238,0.4)",
            boxShadow: "0 0 30px rgba(34,211,238,0.15)",
          }}
        >
          <GraduationCap size={28} className="text-cyan-400" />
        </div>

        <div className="inline-flex items-center gap-2 mb-5 px-3 py-1 rounded-sm"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <span
            data-testid="academy-badge"
            className="text-[10px] tracking-[0.25em] uppercase font-mono"
            style={{ color: "var(--accent)" }}
          >
            COMING SOON
          </span>
        </div>

        <h1
          className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-[-0.02em] leading-[1.05] t-text mb-4"
          data-testid="academy-title"
        >
          The <span className="text-gradient-cyan">Academy</span>
        </h1>

        <p
          data-testid="academy-subtitle"
          className="text-base md:text-lg t-text-sub max-w-xl mx-auto leading-relaxed mb-14"
        >
          Master AI agent development — from first build to scaled, monetized deployments.
        </p>

        {/* 3 locked course teasers */}
        <div data-testid="academy-courses" className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-16 text-left">
          {COURSES.map((c) => (
            <div
              key={c.n}
              data-testid={`academy-course-${c.n}`}
              className="relative rounded-sm p-5 transition-transform duration-300 hover:-translate-y-1"
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--accent-border)",
              }}
            >
              <span
                className="absolute top-3 right-3 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[8px] font-mono font-bold tracking-[0.15em] uppercase"
                style={{ background: "var(--accent-bg)", border: "1px solid var(--accent-border)", color: "var(--accent)" }}
              >
                <Lock size={8} /> Locked
              </span>
              <div className="text-[28px] font-bold font-mono leading-none mb-3" style={{ color: "var(--accent)", opacity: 0.45 }}>
                {c.n}
              </div>
              <div className="flex items-center gap-2 mb-2">
                <c.Icon size={13} className="text-cyan-400" />
                <h3 className="text-[14px] font-semibold t-text">{c.title}</h3>
              </div>
              <p className="text-[12px] leading-relaxed t-text-sub">
                {c.blurb}
              </p>
            </div>
          ))}
        </div>

        {/* Email signup */}
        <div className="mb-3">
          <p className="text-[11px] uppercase tracking-[0.2em] font-mono mb-4 t-text-mute">
            Want early access? Drop your email.
          </p>
          <EmailSignup />
        </div>
      </div>
    </div>
  );
}

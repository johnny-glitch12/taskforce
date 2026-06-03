import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Mail, Lock, Check, Twitter, MessageSquare, Github } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ComingSoonLanding() {
  const [email, setEmail] = useState("");
  const [count, setCount] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  // Live count of operatives enlisted
  useEffect(() => {
    fetch(`${API}/api/waitlist/count`)
      .then((r) => r.json())
      .then((d) => setCount(d.count ?? 0))
      .catch(() => setCount(0));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!EMAIL_RE.test(email.trim())) {
      setError("Enter a valid email.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Could not join waitlist");
      }
      setSuccess(true);
      // Optimistic + actual count refresh
      fetch(`${API}/api/waitlist/count`).then((r) => r.json()).then((d) => setCount(d.count));
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      data-testid="coming-soon-landing"
      className="min-h-screen flex flex-col relative overflow-hidden"
      style={{ background: "#0A0A0A", color: "#e4e4e7" }}
    >
      {/* Background grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.18]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(34,211,238,0.18) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,0.18) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse at center, black 35%, transparent 85%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, black 35%, transparent 85%)",
        }}
      />
      {/* Subtle glow */}
      <div
        className="absolute inset-x-0 top-1/3 pointer-events-none"
        style={{
          height: 400,
          background: "radial-gradient(ellipse at center, rgba(34,211,238,0.12) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />

      {/* Logo header */}
      <header className="relative z-10 px-6 sm:px-10 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-cyan-400" />
          <span className="text-[13px] font-bold tracking-[0.18em] uppercase font-mono">
            Task<span className="text-cyan-400">Force</span>
          </span>
          <span
            className="ml-1 px-1.5 py-0.5 text-[8px] font-bold tracking-[0.15em] uppercase font-mono rounded-sm text-cyan-300"
            style={{ background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.35)" }}
          >
            Beta
          </span>
        </div>
        <Link
          to="/login"
          data-testid="cs-already-have-access"
          className="text-[11px] font-mono uppercase tracking-[0.18em] text-zinc-500 hover:text-cyan-400 transition-colors flex items-center gap-1.5"
        >
          <Lock size={11} /> Sign In
        </Link>
      </header>

      {/* Main */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-2xl text-center">
          {/* Eyebrow */}
          <div
            data-testid="cs-eyebrow"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-sm mb-8"
            style={{ background: "rgba(34,211,238,0.06)", border: "1px solid rgba(34,211,238,0.25)" }}
          >
            <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse" />
            <span className="text-[10px] font-bold tracking-[0.22em] uppercase font-mono text-cyan-400">
              Autonomous Agent Infrastructure
            </span>
          </div>

          {/* Heading */}
          <h1
            data-testid="cs-heading"
            className="text-5xl sm:text-6xl lg:text-7xl font-bold leading-[0.95] tracking-tight mb-6"
            style={{ fontFamily: "'Rajdhani', 'Inter', sans-serif" }}
          >
            <span className="text-white block">Something Big Is</span>
            <span className="text-cyan-400 block">Deploying.</span>
          </h1>

          {/* Subtext */}
          <p className="text-[14px] sm:text-[15px] text-zinc-400 max-w-lg mx-auto mb-10 leading-relaxed">
            The AI Execution Economy is coming. Build, deploy, and monetize autonomous agents — all from a single command-line-grade IDE.
          </p>

          {/* Form */}
          {!success ? (
            <form
              onSubmit={handleSubmit}
              data-testid="cs-waitlist-form"
              className="max-w-md mx-auto"
            >
              <div className="flex flex-col sm:flex-row gap-2 sm:gap-0 items-stretch">
                <div className="relative flex-1">
                  <Mail
                    size={14}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none"
                  />
                  <input
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    data-testid="cs-waitlist-email"
                    aria-label="Email address"
                    required
                    className="w-full pl-10 pr-3 py-3.5 text-[13px] font-mono text-white bg-transparent rounded-sm sm:rounded-r-none focus:outline-none transition-all"
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid #27272a",
                      borderRight: "1px solid #27272a",
                    }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  data-testid="cs-waitlist-submit"
                  className="px-6 py-3.5 text-[11px] font-bold tracking-[0.18em] uppercase font-mono bg-cyan-400 text-black rounded-sm sm:rounded-l-none hover:bg-cyan-300 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-[0_0_20px_rgba(34,211,238,0.2)]"
                >
                  {submitting ? "Enlisting…" : "Join Waitlist"}
                  {!submitting && <ArrowRight size={13} />}
                </button>
              </div>
              {error && (
                <p data-testid="cs-waitlist-error" className="text-[11px] text-rose-400 font-mono mt-2 text-left">
                  {error}
                </p>
              )}
            </form>
          ) : (
            <div
              data-testid="cs-waitlist-success"
              className="max-w-md mx-auto px-5 py-5 rounded-sm flex items-start gap-3 animate-fade-in"
              style={{
                background: "rgba(16,185,129,0.06)",
                border: "1px solid rgba(16,185,129,0.3)",
              }}
            >
              <div className="w-7 h-7 rounded-sm flex items-center justify-center shrink-0"
                style={{ background: "rgba(16,185,129,0.18)" }}>
                <Check size={14} className="text-emerald-400" />
              </div>
              <div className="text-left">
                <p className="text-[13px] text-emerald-300 font-medium mb-0.5">
                  You're on the list, operative.
                </p>
                <p className="text-[11px] text-zinc-500 font-mono">
                  We'll notify you when it's go time.
                </p>
              </div>
            </div>
          )}

          {/* Counter */}
          {count !== null && (
            <div data-testid="cs-counter" className="mt-8 text-[11px] font-mono tracking-[0.18em] uppercase text-zinc-600">
              <span className="text-cyan-400 font-bold">{count.toLocaleString()}</span> operatives enlisted
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer
        data-testid="cs-footer"
        className="relative z-10 px-6 sm:px-10 py-6 flex items-center justify-between flex-wrap gap-3"
        style={{ borderTop: "1px solid #1a1a1e" }}
      >
        <p className="text-[10px] font-mono tracking-wide text-zinc-700">
          &copy; 2026 Task Force AI Development Services L.L.C. All rights reserved.
        </p>
        <div className="flex items-center gap-3">
          <a href="https://twitter.com" target="_blank" rel="noopener noreferrer"
            data-testid="cs-social-twitter"
            className="text-zinc-600 hover:text-cyan-400 transition-colors">
            <Twitter size={14} />
          </a>
          <a href="https://discord.com" target="_blank" rel="noopener noreferrer"
            data-testid="cs-social-discord"
            className="text-zinc-600 hover:text-cyan-400 transition-colors">
            <MessageSquare size={14} />
          </a>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer"
            data-testid="cs-social-github"
            className="text-zinc-600 hover:text-cyan-400 transition-colors">
            <Github size={14} />
          </a>
        </div>
      </footer>
    </div>
  );
}

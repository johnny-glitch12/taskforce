import { useState, useEffect } from "react";
import { toast } from "sonner";
import { ArrowRight, Users } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function Home() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [waitlistCount, setWaitlistCount] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/waitlist/count`)
      .then((r) => r.json())
      .then((d) => setWaitlistCount(d.count))
      .catch(() => {});
  }, []);

  const handleJoinWaitlist = async (e) => {
    e.preventDefault();
    if (!email.trim()) { toast.error("Please enter your email."); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        toast.success("You're on the list.");
        setEmail("");
        setWaitlistCount((c) => c + 1);
      } else {
        toast.error("Something went wrong. Try again.");
      }
    } catch {
      toast.error("Network error. Try again.");
    }
    setSubmitting(false);
  };

  return (
    <div className="relative min-h-[calc(100vh-60px)] flex items-center justify-center overflow-hidden">
      {/* Subtle gradient orbs */}
      <div className="absolute top-[-20%] left-[10%] w-[500px] h-[500px] rounded-full bg-[#8B5CF6]/[0.07] blur-[120px] pointer-events-none t-orb" />
      <div className="absolute bottom-[-10%] right-[15%] w-[400px] h-[400px] rounded-full bg-[#6D28D9]/[0.05] blur-[100px] pointer-events-none t-orb" />

      {/* Content */}
      <div className="relative z-10 max-w-3xl mx-auto px-6 lg:px-8 text-center">
        {/* Label */}
        <div
          className="inline-block mb-10 opacity-0 animate-fade-in-up"
          style={{ animationDelay: "0ms", animationFillMode: "forwards" }}
        >
          <span
            data-testid="hero-label"
            className="text-[11px] tracking-[0.15em] t-text-sub t-card px-4 py-1.5 rounded-full"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', display: 'inline-block' }}
          >
            Autonomous Agent Infrastructure
          </span>
        </div>

        {/* Headline */}
        <h1
          data-testid="hero-headline"
          aria-label="The AI Agent Economy Is Broken. We Are Fixing It."
          className="text-4xl sm:text-5xl lg:text-[4.25rem] font-bold tracking-[-0.03em] leading-[1.08] t-text mb-7 opacity-0 animate-fade-in-up"
          style={{ fontFamily: "'Outfit', sans-serif", animationDelay: "100ms", animationFillMode: "forwards" }}
        >
          The AI Agent Economy
          <br />
          Is Broken.{" "}
          <span className="text-gradient-purple">We Are Fixing It.</span>
        </h1>

        {/* Sub-headline */}
        <p
          data-testid="hero-subheadline"
          className="text-base md:text-lg t-text-sub mb-14 max-w-md mx-auto leading-relaxed opacity-0 animate-fade-in-up"
          style={{ animationDelay: "200ms", animationFillMode: "forwards" }}
        >
          Learn, build, monetize, and trust autonomous agents.
        </p>

        {/* Waitlist CTA */}
        <form
          id="waitlist"
          onSubmit={handleJoinWaitlist}
          data-testid="waitlist-form"
          className="max-w-md mx-auto flex flex-col sm:flex-row items-stretch gap-3 opacity-0 animate-fade-in-up"
          style={{ animationDelay: "300ms", animationFillMode: "forwards" }}
        >
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            data-testid="waitlist-email-input"
            className="flex-1 t-input focus:outline-none focus:border-[#8B5CF6]/50 transition-all px-5 py-3.5 text-[15px] rounded-full"
            style={{ border: '1px solid var(--input-border)' }}
          />
          <button
            type="submit"
            data-testid="waitlist-submit-btn"
            className="group px-7 py-3.5 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_35px_rgba(139,92,246,0.45)] flex items-center justify-center gap-2"
          >
            Join Waitlist
            <ArrowRight size={15} className="transition-transform duration-300 group-hover:translate-x-0.5" />
          </button>
        </form>

        {/* Social Proof */}
        {waitlistCount > 0 && (
          <div
            data-testid="waitlist-counter"
            className="mt-8 inline-flex items-center gap-2.5 text-[13px] t-text-sub opacity-0 animate-fade-in-up"
            style={{ animationDelay: "450ms", animationFillMode: "forwards" }}
          >
            <div
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
              <Users size={13} className="text-[#8B5CF6]" />
              <span className="t-text font-medium">{waitlistCount.toLocaleString()}</span>
              <span className="t-text-sub">on the waitlist</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

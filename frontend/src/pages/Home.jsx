import { useState } from "react";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";

const HERO_BG = "https://static.prod-images.emergentagent.com/jobs/1f4bc532-c54c-43b5-acf6-c5b708fa0240/images/2464b225b435e3ff705aa4795199708e87a8d886d30fb4b1d5631b4e81e925b6.png";

export default function Home() {
  const [email, setEmail] = useState("");

  const handleJoinWaitlist = (e) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Please enter your email.");
      return;
    }
    toast.success("You're on the list.");
    setEmail("");
  };

  return (
    <div className="relative min-h-[calc(100vh-64px)] flex items-center justify-center overflow-hidden">
      {/* Background image */}
      <div className="absolute inset-0 z-0">
        <img
          src={HERO_BG}
          alt=""
          className="w-full h-full object-cover opacity-20"
        />
        <div className="absolute inset-0 bg-zinc-950/70" />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 lg:px-8 text-center">
        {/* Label */}
        <div
          className="inline-block mb-8 opacity-0 animate-fade-in-up"
          style={{ animationDelay: "0ms", animationFillMode: "forwards" }}
        >
          <span
            data-testid="hero-label"
            className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 border border-zinc-800 px-4 py-2"
          >
            Autonomous Agent Infrastructure
          </span>
        </div>

        {/* Headline */}
        <h1
          data-testid="hero-headline"
          className="text-5xl md:text-6xl lg:text-[5rem] font-black tracking-tighter leading-none text-white mb-8 opacity-0 animate-fade-in-up"
          style={{ fontFamily: "'Outfit', sans-serif", animationDelay: "100ms", animationFillMode: "forwards" }}
        >
          The AI Agent Economy
          <br />
          Is Broken.{" "}
          <span className="text-[#00E5FF]">We Are Fixing It.</span>
        </h1>

        {/* Sub-headline */}
        <p
          data-testid="hero-subheadline"
          className="text-base md:text-lg text-zinc-400 mb-16 max-w-xl mx-auto opacity-0 animate-fade-in-up"
          style={{ animationDelay: "200ms", animationFillMode: "forwards" }}
        >
          Learn, build, monetize, and trust autonomous agents.
        </p>

        {/* Waitlist CTA */}
        <form
          id="waitlist"
          onSubmit={handleJoinWaitlist}
          data-testid="waitlist-form"
          className="max-w-lg mx-auto flex flex-col sm:flex-row items-stretch gap-4 opacity-0 animate-fade-in-up"
          style={{ animationDelay: "300ms", animationFillMode: "forwards" }}
        >
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            data-testid="waitlist-email-input"
            className="flex-1 bg-transparent border-b-2 border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#00E5FF] transition-colors px-0 py-4 text-lg font-light"
          />
          <button
            type="submit"
            data-testid="waitlist-submit-btn"
            className="group px-8 py-4 bg-[#00E5FF] text-black text-sm font-semibold uppercase tracking-wider hover:bg-[#B900FF] hover:text-white transition-all duration-300 shadow-[0_0_15px_rgba(0,229,255,0.2)] hover:shadow-[0_0_20px_rgba(185,0,255,0.5)] flex items-center justify-center gap-2"
          >
            Join Waitlist
            <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-1" />
          </button>
        </form>
      </div>
    </div>
  );
}

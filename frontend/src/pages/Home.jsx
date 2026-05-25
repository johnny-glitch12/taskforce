import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { ArrowRight, Users, Play, Zap, Shield, Terminal, Globe, Code2, GitBranch, Lock } from "lucide-react";
import { motion, useInView, useScroll, useTransform } from "framer-motion";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Scroll-triggered section wrapper ─── */
function Reveal({ children, delay = 0, className = "" }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 40 }}
      transition={{ duration: 0.6, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ─── Animated counter ─── */
function Counter({ value, suffix = "" }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const end = value;
    const duration = 1500;
    const step = Math.ceil(end / (duration / 16));
    const timer = setInterval(() => {
      start += step;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(start);
    }, 16);
    return () => clearInterval(timer);
  }, [isInView, value]);

  return <span ref={ref} className="font-mono">{count.toLocaleString()}{suffix}</span>;
}

/* ─── Animated grid lines (background) ─── */
function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Base grid */}
      <div className="absolute inset-0" style={{
        backgroundImage: `
          linear-gradient(rgba(34,211,238,0.07) 1px, transparent 1px),
          linear-gradient(90deg, rgba(34,211,238,0.07) 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }} />

      {/* Horizontal scan line — bright and wide */}
      <motion.div
        className="absolute left-0 right-0 h-[2px]"
        style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(34,211,238,0.5) 20%, rgba(34,211,238,0.8) 50%, rgba(34,211,238,0.5) 80%, transparent 100%)', boxShadow: '0 0 30px 8px rgba(34,211,238,0.15)' }}
        animate={{ y: [-20, 2000] }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      />

      {/* Second scan line — offset, dimmer */}
      <motion.div
        className="absolute left-0 right-0 h-[1px]"
        style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(16,185,129,0.4) 30%, rgba(16,185,129,0.6) 50%, rgba(16,185,129,0.4) 70%, transparent 100%)', boxShadow: '0 0 20px 4px rgba(16,185,129,0.1)' }}
        animate={{ y: [1500, -20] }}
        transition={{ duration: 9, repeat: Infinity, ease: "linear" }}
      />

      {/* Vertical scan line — left to right */}
      <motion.div
        className="absolute top-0 bottom-0 w-[1px]"
        style={{ background: 'linear-gradient(180deg, transparent 0%, rgba(34,211,238,0.35) 30%, rgba(34,211,238,0.6) 50%, rgba(34,211,238,0.35) 70%, transparent 100%)', boxShadow: '0 0 20px 4px rgba(34,211,238,0.08)' }}
        animate={{ x: [-20, 2000] }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
      />

      {/* Pulsing corner nodes */}
      {[
        { top: '15%', left: '10%', delay: 0 },
        { top: '30%', right: '8%', delay: 1.5 },
        { top: '60%', left: '18%', delay: 3 },
        { top: '75%', right: '15%', delay: 0.8 },
        { top: '45%', left: '50%', delay: 2.2 },
      ].map((pos, i) => (
        <motion.div
          key={i}
          className="absolute"
          style={{ ...pos }}
          animate={{ opacity: [0, 0.8, 0], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 3, repeat: Infinity, delay: pos.delay, ease: "easeInOut" }}
        >
          <div className="w-1.5 h-1.5 bg-cyan-400" style={{ boxShadow: '0 0 12px 4px rgba(34,211,238,0.3)' }} />
        </motion.div>
      ))}

      {/* Animated connection lines between nodes */}
      <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.15 }}>
        <motion.line
          x1="10%" y1="15%" x2="50%" y2="45%"
          stroke="#22d3ee" strokeWidth="1"
          strokeDasharray="8 6"
          animate={{ strokeDashoffset: [0, -100] }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        />
        <motion.line
          x1="50%" y1="45%" x2="85%" y2="30%"
          stroke="#22d3ee" strokeWidth="1"
          strokeDasharray="8 6"
          animate={{ strokeDashoffset: [0, -100] }}
          transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
        />
        <motion.line
          x1="18%" y1="60%" x2="50%" y2="45%"
          stroke="#10b981" strokeWidth="1"
          strokeDasharray="8 6"
          animate={{ strokeDashoffset: [0, -80] }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        />
        <motion.line
          x1="85%" y1="75%" x2="50%" y2="45%"
          stroke="#10b981" strokeWidth="1"
          strokeDasharray="8 6"
          animate={{ strokeDashoffset: [0, -80] }}
          transition={{ duration: 4.5, repeat: Infinity, ease: "linear" }}
        />
      </svg>

      {/* Large ambient glow orbs */}
      <motion.div
        className="absolute top-[10%] left-[5%] w-[350px] h-[350px] rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(34,211,238,0.06) 0%, transparent 70%)' }}
        animate={{ opacity: [0.4, 0.8, 0.4], scale: [0.9, 1.1, 0.9] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[5%] right-[5%] w-[400px] h-[400px] rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.05) 0%, transparent 70%)' }}
        animate={{ opacity: [0.3, 0.7, 0.3], scale: [1, 1.15, 1] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
    </div>
  );
}

/* ─── Feature cards ─── */
const FEATURES = [
  { icon: Terminal, title: "Command Prompt", desc: "Describe your agent in plain English. AI builds the logic.", color: "#22d3ee" },
  { icon: GitBranch, title: "The Armory", desc: "Visual React Flow node builder for complex multi-step agents.", color: "#10b981" },
  { icon: Globe, title: "The Exchange", desc: "Publish, rent, or acquire agent IP on the marketplace.", color: "#06b6d4" },
  { icon: Shield, title: "Security Firewall", desc: "Triple-layer protection: Semantic audit, rate limits, SSRF blocking.", color: "#f59e0b" },
  { icon: Code2, title: "Version Control", desc: "Every publish tracked. Roll back, compare, iterate.", color: "#8b5cf6" },
  { icon: Lock, title: "Sandboxed Execution", desc: "RestrictedPython runtime. No filesystem, no network escape.", color: "#ef4444" },
];

/* ─── Stats bar ─── */
const STATS = [
  { label: "Agents Deployed", value: 2400 },
  { label: "Executions / Day", value: 18000 },
  { label: "Avg Trust Score", value: 96, suffix: "%" },
  { label: "Uptime", value: 99, suffix: ".9%" },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [waitlistCount, setWaitlistCount] = useState(0);
  const heroRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.95]);

  useEffect(() => {
    fetch(`${API}/api/waitlist/count`).then((r) => r.json()).then((d) => setWaitlistCount(d.count)).catch(() => {});
  }, []);

  const handleJoinWaitlist = async (e) => {
    e.preventDefault();
    if (!email.trim()) { toast.error("Enter your email."); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/waitlist`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      if (res.ok) { toast.success("You're on the list."); setEmail(""); setWaitlistCount((c) => c + 1); }
      else toast.error("Something went wrong.");
    } catch { toast.error("Network error."); }
    setSubmitting(false);
  };

  return (
    <div className="relative overflow-hidden">
      <GridBackground />

      {/* ═══ HERO ═══ */}
      <motion.section
        ref={heroRef}
        style={{ opacity: heroOpacity, scale: heroScale }}
        className="relative min-h-[calc(100vh-56px)] flex flex-col items-center justify-center px-6 lg:px-8"
      >
        <div className="absolute top-[-15%] left-[15%] w-[500px] h-[500px] rounded-full bg-cyan-500/[0.03] blur-[150px] pointer-events-none t-orb" />

        <div className="relative z-10 max-w-4xl mx-auto text-center">
          {/* Tag */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="inline-block mb-8"
          >
            <span data-testid="hero-label" className="text-[10px] tracking-[0.2em] uppercase font-mono text-cyan-400 px-3 py-1.5 rounded-sm" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              Autonomous Agent Infrastructure
            </span>
          </motion.div>

          {/* H1 */}
          <motion.h1
            data-testid="hero-headline"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-4xl sm:text-5xl lg:text-[4.5rem] font-bold tracking-[-0.03em] leading-[1.05] t-text mb-6"
          >
            The AI Execution
            <br />
            <span className="text-gradient-cyan">Economy.</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            data-testid="hero-subheadline"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.35 }}
            className="text-base md:text-lg t-text-sub mb-10 max-w-lg mx-auto leading-relaxed"
          >
            Build, deploy, and monetize autonomous agents. Stop coding. Start deploying.
          </motion.p>

          {/* Waitlist CTA */}
          <motion.form
            id="waitlist"
            onSubmit={handleJoinWaitlist}
            data-testid="waitlist-form"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.45 }}
            className="max-w-md mx-auto flex flex-col sm:flex-row items-stretch gap-2"
          >
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              data-testid="waitlist-email-input"
              className="flex-1 t-input focus:outline-none transition-all px-4 py-3 text-[14px] rounded-sm font-mono"
              style={{ border: '1px solid var(--border)' }}
            />
            <button
              type="submit" data-testid="waitlist-submit-btn"
              className="group px-6 py-3 bg-cyan-400 text-black text-[13px] font-bold tracking-wide uppercase rounded-sm hover:bg-cyan-300 transition-all flex items-center justify-center gap-2"
            >
              Enlist Now <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
            </button>
          </motion.form>

          {/* Counter */}
          {waitlistCount > 0 && (
            <motion.div
              data-testid="waitlist-counter"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-6 inline-flex items-center gap-2 text-[12px] t-text-sub"
            >
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                <Users size={12} className="text-cyan-400" />
                <span className="t-text font-mono font-semibold">{waitlistCount.toLocaleString()}</span>
                <span className="t-text-mute">operatives enlisted</span>
              </div>
            </motion.div>
          )}

          {/* Hero Video — 30-Second High-Tempo Loop */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.65 }}
            className="mt-10 mx-auto max-w-3xl rounded-sm overflow-hidden"
            style={{ border: '1px solid var(--border)', boxShadow: '0 0 40px rgba(34,211,238,0.08)' }}
            data-testid="hero-video"
          >
            <video
              autoPlay
              loop
              muted
              playsInline
              className="w-full aspect-video object-cover"
              src="https://customer-assets.emergentagent.com/job_dark-mode-nova/artifacts/rzrr061t_c3dde6e0-599a-4612-9294-65ac300e7471_720p_mp4_30_16-9%20%281%29.mp4"
            />
          </motion.div>
        </div>
      </motion.section>

      {/* ═══ STATS BAR ═══ */}
      <section className="py-10 px-6 lg:px-8 relative" style={{ borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-5xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-6">
          {STATS.map((stat, i) => (
            <Reveal key={stat.label} delay={i * 0.1} className="text-center">
              <p className="text-3xl lg:text-4xl font-bold t-text mb-1">
                <Counter value={stat.value} suffix={stat.suffix || ""} />
              </p>
              <p className="text-[11px] font-mono tracking-widest uppercase t-text-mute">{stat.label}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ FEATURES GRID ═══ */}
      <section className="py-14 px-6 lg:px-8 relative">
        <div className="max-w-5xl mx-auto">
          <Reveal className="text-center mb-10">
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono text-cyan-400 px-3 py-1 rounded-sm inline-block mb-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              Capabilities
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight t-text mb-3">
              Built for <span className="text-gradient-cyan">Operators</span>
            </h2>
            <p className="text-[15px] t-text-sub max-w-md mx-auto">Every tool you need to build, deploy, and scale autonomous agents.</p>
          </Reveal>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {FEATURES.map((feat, i) => (
              <Reveal key={feat.title} delay={i * 0.08}>
                <motion.div
                  whileHover={{ y: -4, borderColor: feat.color + "30" }}
                  className="h-full p-5 rounded-sm transition-all group flex flex-col"
                  style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background: feat.color + "10", border: `1px solid ${feat.color}20` }}>
                      <feat.icon size={16} style={{ color: feat.color }} />
                    </div>
                    <h3 className="text-[13px] font-bold t-text font-mono tracking-wide">{feat.title}</h3>
                  </div>
                  <p className="text-[12px] t-text-sub leading-relaxed flex-1">{feat.desc}</p>
                </motion.div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="py-14 px-6 lg:px-8 relative" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="max-w-4xl mx-auto">
          <Reveal className="text-center mb-10">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight t-text mb-3">
              Three Steps to <span className="text-gradient-cyan">Deployment</span>
            </h2>
          </Reveal>

          <div className="space-y-0">
            {[
              { step: "01", title: "Describe or Build", desc: "Use the Command Prompt for natural language, or the visual node builder in The Armory for complex logic." },
              { step: "02", title: "Test & Certify", desc: "Run your agent through the compliance linter. Get a trust score. Fix flagged issues before deployment." },
              { step: "03", title: "Deploy & Monetize", desc: "Publish to The Exchange. Set your pricing model — rent per output or sell the full IP outright." },
            ].map((item, i) => (
              <Reveal key={item.step} delay={i * 0.15}>
                <div className="flex items-start gap-5 py-5" style={i < 2 ? { borderBottom: '1px solid var(--border)' } : {}}>
                  <motion.div
                    whileHover={{ scale: 1.1 }}
                    className="w-11 h-11 rounded-sm flex items-center justify-center shrink-0 font-mono text-[15px] font-bold text-cyan-400"
                    style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.12)' }}
                  >
                    {item.step}
                  </motion.div>
                  <div>
                    <h3 className="text-[15px] font-bold t-text mb-1">{item.title}</h3>
                    <p className="text-[13px] t-text-sub leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="py-14 px-6 lg:px-8 relative" style={{ borderTop: '1px solid var(--border)' }}>
        <Reveal className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight t-text mb-3">
            Ready to <span className="text-gradient-cyan">Deploy</span>?
          </h2>
          <p className="text-[15px] t-text-sub mb-7 max-w-md mx-auto">
            Join thousands of operators already building on Task Force AI.
          </p>
          <motion.a
            href="#waitlist"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-cyan-400 text-black text-[14px] font-bold tracking-wide uppercase rounded-sm hover:bg-cyan-300 transition-colors"
            style={{ boxShadow: '0 0 30px rgba(34,211,238,0.15)' }}
          >
            <Zap size={16} /> Start Building — Free
          </motion.a>
        </Reveal>
      </section>
    </div>
  );
}

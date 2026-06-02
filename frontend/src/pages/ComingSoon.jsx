import { Link } from "react-router-dom";
import { Lock, ArrowLeft, Mail } from "lucide-react";

export default function ComingSoon({ feature = "This feature", subtitle = "is locked while we polish the public release." }) {
  return (
    <div data-testid="coming-soon-page" className="min-h-[calc(100vh-120px)] flex items-center justify-center px-4 py-12 t-bg">
      <div className="max-w-md w-full text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-sm mb-5"
          style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.3)' }}>
          <Lock size={20} className="text-cyan-400" />
        </div>
        <div className="text-[10px] tracking-[0.25em] uppercase t-text-dim mb-2 font-mono">RESTRICTED ACCESS</div>
        <h1 className="text-2xl md:text-3xl t-text mb-3" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: '0.04em' }}>
          {feature} is coming soon
        </h1>
        <p className="text-[13px] t-text-mute mb-7 leading-relaxed">{subtitle}</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-2">
          <Link to="/" data-testid="cs-back-home"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono tracking-[0.1em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition-all">
            <ArrowLeft size={11} /> Back to Home
          </Link>
          <Link to="/exchange"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono tracking-[0.1em] uppercase rounded-sm t-text-sub hover:text-cyan-400 transition-all"
            style={{ border: '1px solid var(--border)' }}>
            <Mail size={11} /> Browse The Exchange
          </Link>
        </div>
      </div>
    </div>
  );
}

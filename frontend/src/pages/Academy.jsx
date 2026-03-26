import { GraduationCap } from "lucide-react";

export default function Academy() {
  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-6">
      <div
        data-testid="academy-page"
        className="text-center animate-fade-in-up"
        style={{ animationFillMode: "forwards" }}
      >
        {/* Badge */}
        <div className="inline-flex items-center gap-2 mb-8 border border-zinc-800 px-4 py-2">
          <GraduationCap size={14} className="text-[#00E5FF]" />
          <span
            data-testid="academy-badge"
            className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500"
          >
            Coming Soon
          </span>
        </div>

        {/* Title */}
        <h1
          className="text-5xl md:text-6xl lg:text-[5rem] font-black tracking-tighter leading-none text-white mb-6"
          style={{ fontFamily: "'Outfit', sans-serif" }}
        >
          Nova <span className="text-[#00E5FF]">Academy</span>
        </h1>

        {/* Subtext */}
        <p
          data-testid="academy-subtext"
          className="text-base md:text-lg text-zinc-400 max-w-md mx-auto"
        >
          The premier free AI education platform.
        </p>
      </div>
    </div>
  );
}

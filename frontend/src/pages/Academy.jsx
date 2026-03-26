import { GraduationCap } from "lucide-react";

export default function Academy() {
  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6 relative">
      <div className="absolute top-[15%] left-1/2 -translate-x-1/2 w-[350px] h-[350px] rounded-full bg-[#8B5CF6]/[0.05] blur-[100px] pointer-events-none" />

      <div
        data-testid="academy-page"
        className="relative text-center animate-fade-in-up"
        style={{ animationFillMode: "forwards" }}
      >
        {/* Badge */}
        <div className="inline-flex items-center gap-2 mb-10 bg-white/[0.04] border border-white/[0.08] px-4 py-1.5 rounded-full">
          <GraduationCap size={13} className="text-[#8B5CF6]" />
          <span
            data-testid="academy-badge"
            className="text-[11px] tracking-[0.15em] text-zinc-500"
          >
            Coming Soon
          </span>
        </div>

        {/* Title */}
        <h1
          className="text-4xl sm:text-5xl lg:text-[4.25rem] font-bold tracking-[-0.03em] leading-[1.08] text-white mb-5"
          style={{ fontFamily: "'Outfit', sans-serif" }}
        >
          Nova <span className="text-gradient-purple">Academy</span>
        </h1>

        {/* Subtext */}
        <p
          data-testid="academy-subtext"
          className="text-base md:text-lg text-zinc-500 max-w-sm mx-auto leading-relaxed"
        >
          The premier free AI education platform.
        </p>
      </div>
    </div>
  );
}

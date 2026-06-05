import { Trophy, Zap, Crown, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export default function Leaderboard() {
  const placeholderRows = [
    { rank: 1, op: "operative_zero", builds: "—", deploys: "—", revenue: "—" },
    { rank: 2, op: "ghost.protocol", builds: "—", deploys: "—", revenue: "—" },
    { rank: 3, op: "neon_runner",    builds: "—", deploys: "—", revenue: "—" },
    { rank: 4, op: "cipher_six",     builds: "—", deploys: "—", revenue: "—" },
    { rank: 5, op: "void.architect", builds: "—", deploys: "—", revenue: "—" },
  ];

  return (
    <div data-testid="leaderboard-page" className="min-h-[calc(100vh-60px)] t-bg">
      <div className="max-w-5xl mx-auto px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <Trophy size={24} className="text-cyan-400" />
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Operator Leaderboard
          </h1>
          <span
            className="ml-2 px-2 py-0.5 text-[10px] font-bold tracking-[0.15em] uppercase font-mono rounded-sm text-amber-300"
            style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.35)' }}
          >
            Coming Soon
          </span>
        </div>
        <p className="text-[14px] t-text-mute mb-10 max-w-2xl">
          A real-time scoreboard of the top Task Force AI operators — ranked by bots compiled,
          deploys received from forks, and revenue routed through The Exchange's 90/10 share.
        </p>

        {/* Feature tease */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-10">
          <FeatureTile icon={Zap} label="Bots Compiled" desc="Live count of bots you've forged in The Armory" />
          <FeatureTile icon={Crown} label="Forks Earned" desc="When others fork your work, you climb the ranks" />
          <FeatureTile icon={Trophy} label="Revenue Share" desc="90/10 royalty earnings on every fork-deploy" />
        </div>

        {/* Placeholder table */}
        <div
          className="rounded-sm overflow-hidden"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <div
            className="px-4 py-2.5 grid grid-cols-12 gap-4 text-[10px] uppercase tracking-[0.15em] t-text-dim font-mono"
            style={{ borderBottom: '1px solid var(--border)' }}
          >
            <div className="col-span-1">#</div>
            <div className="col-span-5">Operator</div>
            <div className="col-span-2 text-right">Builds</div>
            <div className="col-span-2 text-right">Deploys</div>
            <div className="col-span-2 text-right">Revenue</div>
          </div>
          {placeholderRows.map((r) => (
            <div
              key={r.rank}
              data-testid={`leaderboard-row-${r.rank}`}
              className="px-4 py-3 grid grid-cols-12 gap-4 text-[12px] t-text-mute"
              style={{ borderBottom: '1px solid var(--border)', opacity: 0.45 }}
            >
              <div className="col-span-1 font-mono">{r.rank}</div>
              <div className="col-span-5 font-mono truncate">{r.op}</div>
              <div className="col-span-2 text-right font-mono">{r.builds}</div>
              <div className="col-span-2 text-right font-mono">{r.deploys}</div>
              <div className="col-span-2 text-right font-mono">{r.revenue}</div>
            </div>
          ))}
          <div className="px-4 py-6 text-center text-[11px] t-text-dim font-mono">
            Leaderboard goes live with the next major release.
          </div>
        </div>

        <div className="mt-8 flex items-center gap-3">
          <Link
            to="/armory"
            data-testid="leaderboard-back-armory"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono tracking-[0.1em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition-all"
          >
            <ArrowLeft size={11} /> Back to The Armory
          </Link>
          <Link
            to="/exchange"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono tracking-[0.1em] uppercase rounded-sm t-text-sub hover:text-cyan-400 transition-all"
            style={{ border: '1px solid var(--border)' }}
          >
            Browse The Exchange
          </Link>
        </div>
      </div>
    </div>
  );
}

function FeatureTile({ icon: Icon, label, desc }) {
  return (
    <div
      className="rounded-sm p-4"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <Icon size={16} className="text-cyan-400 mb-2.5" />
      <div className="text-[12px] t-text font-medium uppercase tracking-wider font-mono mb-1">{label}</div>
      <div className="text-[11px] t-text-mute leading-relaxed">{desc}</div>
    </div>
  );
}

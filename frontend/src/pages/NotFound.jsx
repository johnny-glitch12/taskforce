/**
 * NotFound — 404 catch-all page (Prompt 31 Phase 5).
 *
 * Mounted as `<Route path="*" />` inside App.js's main <Routes>. Stays
 * deliberately small — same dark-card aesthetic as the rest of the app,
 * one CTA. Unauthed visitors are nudged to "/"; authed users to /my-agents.
 */
import { Link } from "react-router-dom";
import { Compass, ArrowRight } from "lucide-react";
import { useAuth } from "@/App";

export default function NotFound() {
  const { user } = useAuth() || {};
  const target = user ? "/my-agents" : "/";
  const targetLabel = user ? "Back to My Agents" : "Back to Home";

  return (
    <div
      data-testid="not-found-page"
      className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4 py-12"
    >
      <div
        className="w-full max-w-md rounded-sm p-8 text-center"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
      >
        <div
          className="inline-flex items-center justify-center w-12 h-12 rounded-sm mb-4"
          style={{ background: "rgba(34,211,238,0.06)", border: "1px solid rgba(34,211,238,0.25)" }}
        >
          <Compass size={20} className="text-cyan-400" />
        </div>
        <div className="text-[10px] uppercase tracking-[0.2em] font-mono text-cyan-400 mb-2">
          404 · Off the map
        </div>
        <h1 data-testid="not-found-title" className="text-2xl sm:text-3xl font-bold t-text mb-2">
          Page not found
        </h1>
        <p className="text-[13px] t-text-sub mb-6">
          The route you tried doesn&apos;t exist — it may have moved or never existed.
        </p>
        <Link
          to={target}
          data-testid="not-found-cta"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-sm bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/15 text-[11px] uppercase tracking-[0.15em] font-mono transition-colors duration-200"
        >
          {targetLabel} <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  );
}

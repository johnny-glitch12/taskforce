/* eslint-disable react/prop-types */
/**
 * MyApps — listing page for the user's hosted agent mini-apps.
 * Each card opens AppViewer (iframe-hosted React mini-app).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layers, ExternalLink, Loader2, Sparkles, ArrowUpRight, Activity } from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL;

export default function MyApps() {
  const { token } = useAuth();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/api/my-apps`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => setApps(d.apps || []))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div data-testid="my-apps-page" className="min-h-[calc(100vh-56px)] px-4 sm:px-6 lg:px-10 py-8 lg:py-12">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 lg:mb-10">
          <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <Layers size={11} className="text-cyan-400" />
            <span className="text-[10px] tracking-[0.2em] uppercase font-mono t-text-sub">HOSTED MINI APPS</span>
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight t-text">My Apps</h1>
          <p className="text-sm t-text-sub mt-2 max-w-2xl">
            Every agent you built with a UI lives here. Click an app to launch it. Each run debits credits from your wallet.
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin t-text-mute" size={24} />
          </div>
        )}

        {error && (
          <div className="text-rose-400 font-mono text-sm py-4">{error}</div>
        )}

        {!loading && !error && apps.length === 0 && (
          <div data-testid="my-apps-empty" className="text-center py-16 px-4 rounded-sm" style={{ background: "var(--bg-card)", border: "1px dashed var(--border)" }}>
            <Sparkles className="mx-auto mb-4 text-cyan-400" size={28} />
            <div className="text-lg font-bold t-text mb-1">No mini-apps yet</div>
            <div className="text-sm t-text-sub mb-4 max-w-md mx-auto">
              When you build an agent and tell the Builder you want a UI ("a dashboard for ...", "a form to ...", etc.) we'll generate a React mini-app you can launch from here.
            </div>
            <Link to="/armory" data-testid="my-apps-cta" className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-400 text-black text-[11px] font-bold uppercase tracking-widest font-mono rounded-sm hover:bg-cyan-300">
              Open the Armory <ArrowUpRight size={11} />
            </Link>
          </div>
        )}

        {!loading && apps.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {apps.map((a) => (
              <AppCard key={a.id} app={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AppCard({ app }) {
  const primary = app.manifest?.primary_color || "#22d3ee";
  return (
    <div
      data-testid={`my-app-card-${app.slug || app.id}`}
      className="rounded-sm p-4 hover:translate-y-[-1px] transition-all"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <div
          className="w-10 h-10 rounded-sm flex items-center justify-center font-mono text-[18px] font-bold"
          style={{ background: `${primary}22`, color: primary, border: `1px solid ${primary}55` }}
        >
          {(app.name || "?").slice(0, 1).toUpperCase()}
        </div>
        <span className="text-[10px] font-mono uppercase tracking-wider t-text-mute inline-flex items-center gap-1">
          <Activity size={9} className="text-emerald-400" /> {app.run_count} runs
        </span>
      </div>
      <div className="text-[14px] t-text font-bold truncate" title={app.name}>{app.name}</div>
      <div className="text-[12px] t-text-sub line-clamp-2 mt-1 min-h-[32px]">{app.description || "—"}</div>
      <div className="flex items-center gap-2 mt-3">
        <Link
          to={`/apps/${app.slug || app.id}`}
          data-testid={`launch-app-${app.slug || app.id}`}
          className="flex-1 inline-flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-sm bg-cyan-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono hover:bg-cyan-300"
        >
          Launch <ExternalLink size={10} />
        </Link>
      </div>
    </div>
  );
}

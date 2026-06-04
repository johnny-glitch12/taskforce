/* eslint-disable react/prop-types */
/**
 * AppViewer — sandboxed iframe shell that hosts an AI-generated React mini-app.
 *
 * The actual app HTML is served by GET /api/apps/:slug/render which returns a
 * standalone HTML page with Babel-standalone transpiling the AI's App.jsx + a
 * window.tfApi bridge that calls back to /api/apps/:id/run.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Loader2, Code2, RefreshCw, Wand2, Activity, ExternalLink, Send } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL;

export default function AppViewer() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [app, setApp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [iframeBust, setIframeBust] = useState(0);
  const [showRedesign, setShowRedesign] = useState(false);
  const [redesignPrompt, setRedesignPrompt] = useState("");
  const [redesigning, setRedesigning] = useState(false);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState("preview"); // preview | runs

  useEffect(() => {
    if (!token || !slug) return;
    setLoading(true);
    fetch(`${API}/api/apps/${slug}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.text()).slice(0, 200));
        return r.json();
      })
      .then(setApp)
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [token, slug, iframeBust]);

  useEffect(() => {
    if (!token || !slug || tab !== "runs") return;
    fetch(`${API}/api/apps/${slug}/runs?limit=25`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => setRuns(d.runs || []))
      .catch(() => {});
  }, [token, slug, tab, iframeBust]);

  const handleRedesign = async () => {
    if (redesignPrompt.trim().length < 5) {
      toast.error("Describe the change you want first.");
      return;
    }
    setRedesigning(true);
    try {
      const r = await fetch(`${API}/api/apps/${slug}/redesign`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: redesignPrompt.trim() }),
      });
      const j = await r.json();
      if (!r.ok) {
        toast.error(j.detail || `Redesign failed (${r.status})`);
        return;
      }
      toast.success(`UI updated · −${j.credits_used}cr`);
      setShowRedesign(false);
      setRedesignPrompt("");
      setIframeBust((n) => n + 1);
    } catch {
      toast.error("Network error.");
    } finally {
      setRedesigning(false);
    }
  };

  const iframeUrl = app && token
    ? `${API}/api/apps/${app.slug || app.id}/render?token=${encodeURIComponent(token)}&v=${iframeBust}`
    : null;

  return (
    <div data-testid="app-viewer-page" className="min-h-[calc(100vh-56px)] flex flex-col" style={{ background: "var(--bg)" }}>
      {/* Header */}
      <div className="border-b" style={{ borderColor: "var(--border)" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3 flex-wrap">
          <button
            data-testid="app-viewer-back"
            onClick={() => navigate("/my-apps")}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-sm hover:bg-white/5 text-[11px] font-mono uppercase tracking-[0.12em] t-text-sub"
          >
            <ChevronLeft size={12} /> My Apps
          </button>
          {app && (
            <>
              <div className="h-4 w-px" style={{ background: "var(--border)" }} />
              <div className="text-[13px] font-bold t-text truncate flex-1 min-w-0" title={app.name}>
                {app.name}
              </div>
              <span className="text-[10px] font-mono uppercase tracking-wider t-text-mute hidden sm:inline">
                /apps/{app.slug || app.id}
              </span>
              <div className="flex items-center gap-1 flex-wrap">
                <TabBtn id="preview" active={tab === "preview"} onClick={() => setTab("preview")}>
                  <Code2 size={11} /> Preview
                </TabBtn>
                <TabBtn id="runs" active={tab === "runs"} onClick={() => setTab("runs")}>
                  <Activity size={11} /> Runs
                </TabBtn>
                <button
                  data-testid="app-viewer-refresh"
                  onClick={() => setIframeBust((n) => n + 1)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-sm hover:bg-white/5 text-[10px] font-mono uppercase tracking-wider t-text-sub"
                  title="Reload mini-app"
                >
                  <RefreshCw size={10} />
                </button>
                <button
                  data-testid="app-viewer-redesign-toggle"
                  onClick={() => setShowRedesign((s) => !s)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border text-[10px] font-bold uppercase tracking-widest font-mono text-purple-300 hover:bg-purple-400/10"
                  style={{ borderColor: "rgba(168,85,247,0.3)" }}
                >
                  <Wand2 size={10} /> Redesign
                </button>
              </div>
            </>
          )}
        </div>

        {showRedesign && (
          <div className="border-t" style={{ borderColor: "var(--border)" }}>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-2 flex-wrap">
              <input
                data-testid="app-viewer-redesign-input"
                type="text"
                value={redesignPrompt}
                onChange={(e) => setRedesignPrompt(e.target.value)}
                placeholder="e.g. Make the header purple and add a stats row above the input"
                className="flex-1 min-w-[260px] px-3 py-1.5 rounded-sm text-[12px] font-mono"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)" }}
                disabled={redesigning}
              />
              <button
                data-testid="app-viewer-redesign-submit"
                onClick={handleRedesign}
                disabled={redesigning}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm bg-purple-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono disabled:opacity-50"
              >
                {redesigning ? <Loader2 size={10} className="animate-spin" /> : <Send size={10} />}
                Apply
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="animate-spin t-text-mute" size={24} />
          </div>
        )}
        {error && (
          <div className="m-8 p-4 rounded-sm text-rose-400 font-mono text-sm" style={{ background: "rgba(244,63,94,0.06)", border: "1px solid rgba(244,63,94,0.3)" }}>
            {error}
          </div>
        )}
        {!loading && !error && app && tab === "preview" && iframeUrl && (
          <iframe
            key={iframeBust}
            data-testid="app-viewer-iframe"
            src={iframeUrl}
            title={app.name}
            className="w-full"
            style={{ height: "calc(100vh - 110px)", border: "none", background: "#0a0a0a" }}
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
        )}
        {!loading && !error && app && tab === "runs" && (
          <RunsTable runs={runs} />
        )}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children, id }) {
  return (
    <button
      data-testid={`app-viewer-tab-${id}`}
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] font-bold uppercase tracking-widest font-mono"
      style={{
        background: active ? "var(--bg-card)" : "transparent",
        border: `1px solid ${active ? "var(--cyan)" : "var(--border)"}`,
        color: active ? "var(--cyan)" : "var(--text-sub)",
      }}
    >
      {children}
    </button>
  );
}

function RunsTable({ runs }) {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <h3 className="text-[12px] font-mono uppercase tracking-[0.18em] t-text-sub mb-3">Recent Executions</h3>
      {runs.length === 0 ? (
        <div className="text-center py-16 t-text-sub text-sm">No runs yet — launch the app to generate one.</div>
      ) : (
        <div className="rounded-sm overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="font-mono uppercase tracking-wider text-[10px] t-text-mute">
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2 hidden sm:table-cell">Duration</th>
                <th className="px-3 py-2 hidden sm:table-cell">Credits</th>
                <th className="px-3 py-2">Output / Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r, i) => (
                <tr key={r.id || i} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2">
                    <span className={`text-[10px] font-mono uppercase tracking-wider font-bold ${r.success ? "text-emerald-400" : "text-rose-400"}`}>
                      {r.success ? "OK" : "FAIL"}
                    </span>
                  </td>
                  <td className="px-3 py-2 t-text-sub">{(r.created_at || "").slice(0, 19).replace("T", " ")}</td>
                  <td className="px-3 py-2 hidden sm:table-cell t-text-sub">{r.duration_ms}ms</td>
                  <td className="px-3 py-2 hidden sm:table-cell t-text-sub">{r.credits_used}cr</td>
                  <td className="px-3 py-2 t-text-sub max-w-md truncate" title={JSON.stringify(r.output || r.error)}>
                    {r.success ? JSON.stringify(r.output).slice(0, 80) : (r.error || "—").slice(0, 80)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

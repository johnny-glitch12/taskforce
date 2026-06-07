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
import { ChevronLeft, Loader2, Code2, RefreshCw, Wand2, Activity, ExternalLink, Send, Share2, Copy, Globe, Lock, History, Undo2, Sparkles, Palette } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/App";
import MiniAppCustomize from "@/components/MiniAppCustomize";

const API = process.env.REACT_APP_BACKEND_URL || "";

// Quick-prompt suggestions for the Redesign panel — clicking pre-fills the textarea.
const REDESIGN_SUGGESTIONS = [
  "Make it darker with a moody black & cyan palette",
  "Add a sidebar with quick navigation links",
  "Switch the layout to a card grid with 3 columns",
  "Bigger headings and more breathing room between sections",
  "Add a stats row showing total runs at the top",
  "Use a softer pastel color scheme with rounded corners",
];

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
  const [history, setHistory] = useState([]);
  const [reverting, setReverting] = useState(null); // version_id while in-flight
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState("preview"); // preview | runs
  const [showShare, setShowShare] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);

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

  // Fetch redesign history whenever the panel opens OR after a successful redesign/revert.
  useEffect(() => {
    if (!token || !slug || !showRedesign) return;
    fetch(`${API}/api/apps/${slug}/redesign-history`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : { history: [] })
      .then((d) => setHistory(d.history || []))
      .catch(() => setHistory([]));
  }, [token, slug, showRedesign, iframeBust]);

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
        toast.error(j.detail || j.error || `Redesign failed (${r.status})`);
        return;
      }
      const credits = j.credits_charged ?? 0;
      toast.success(credits > 0 ? `UI updated · ${credits} cr` : "UI updated");
      setRedesignPrompt("");
      setIframeBust((n) => n + 1);
    } catch {
      toast.error("Network error.");
    } finally {
      setRedesigning(false);
    }
  };

  const handleRevert = async (versionId, promptPreview) => {
    if (!versionId) return;
    if (!window.confirm(`Revert UI to the version before:\n\n"${(promptPreview || "").slice(0, 120)}"`)) return;
    setReverting(versionId);
    try {
      const r = await fetch(`${API}/api/apps/${slug}/revert`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ version_id: versionId }),
      });
      const j = await r.json();
      if (!r.ok) {
        toast.error(j.detail || `Revert failed (${r.status})`);
        return;
      }
      toast.success("UI reverted — refresh preview to see changes");
      setIframeBust((n) => n + 1);
    } catch {
      toast.error("Network error.");
    } finally {
      setReverting(null);
    }
  };

  const handleToggleShare = async (makePublic) => {
    setSharing(true);
    try {
      const r = await fetch(`${API}/api/apps/${slug}/share`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ is_public: makePublic }),
      });
      const j = await r.json();
      if (!r.ok) {
        toast.error(j.detail || `Share toggle failed (${r.status})`);
        return;
      }
      setApp((a) => a ? { ...a, is_public: j.is_public } : a);
      toast.success(makePublic ? "App is now public — share away" : "App set back to private");
    } catch {
      toast.error("Network error.");
    } finally {
      setSharing(false);
    }
  };

  const publicUrl = app ? `${window.location.origin}/apps/${app.slug || app.id}` : "";
  const embedSnippet = app
    ? `<iframe src="${API}/api/apps/${app.slug || app.id}/render" width="600" height="700" frameborder="0" style="border:1px solid #1e1e2e; border-radius:12px;" sandbox="allow-scripts allow-same-origin"></iframe>`
    : "";

  const copyToClipboard = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Couldn't access clipboard");
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
                  data-testid="app-viewer-share-toggle"
                  onClick={() => setShowShare((s) => !s)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border text-[10px] font-bold uppercase tracking-widest font-mono"
                  style={{
                    borderColor: app.is_public ? "rgba(16,185,129,0.4)" : "var(--border)",
                    color: app.is_public ? "#34d399" : "var(--text-sub)",
                    background: app.is_public ? "rgba(16,185,129,0.08)" : "transparent",
                  }}
                  title={app.is_public ? "Public — anyone can launch" : "Private — only you can launch"}
                >
                  {app.is_public ? <Globe size={10} /> : <Share2 size={10} />}
                  Share
                </button>
                <button
                  data-testid="app-viewer-customize-toggle"
                  onClick={() => setShowCustomize(true)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-sm border text-[10px] font-bold uppercase tracking-widest font-mono text-cyan-300 hover:bg-cyan-400/10"
                  style={{ borderColor: "rgba(34,211,238,0.3)" }}
                  title="Branding, layout, embed code & QR"
                >
                  <Palette size={10} /> Customize
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
          <div data-testid="app-viewer-redesign-panel" className="border-t" style={{ borderColor: "var(--border)" }}>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-4">
              {/* Header row */}
              <div className="flex items-center gap-2 flex-wrap">
                <Wand2 size={14} className="text-purple-300" />
                <span className="text-[11px] font-mono uppercase tracking-[0.18em] text-purple-300">
                  Redesign with AI
                </span>
                <span className="text-[10px] font-mono t-text-mute">
                  Re-runs the UI Builder. Costs a few credits per call.
                </span>
              </div>

              {/* Quick suggestion chips */}
              <div data-testid="redesign-suggestions" className="flex items-center gap-2 flex-wrap">
                <Sparkles size={11} className="t-text-mute" />
                <span className="text-[10px] font-mono uppercase tracking-wider t-text-mute">Try:</span>
                {REDESIGN_SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    data-testid={`redesign-suggestion-${i}`}
                    onClick={() => setRedesignPrompt(s)}
                    disabled={redesigning}
                    className="px-2.5 py-1 rounded-sm text-[11px] font-mono hover:bg-purple-400/10 hover:text-purple-200 disabled:opacity-40 transition-colors"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)" }}
                  >
                    {s}
                  </button>
                ))}
              </div>

              {/* Multi-line textarea + submit */}
              <div className="flex items-start gap-2 flex-wrap">
                <textarea
                  data-testid="app-viewer-redesign-input"
                  value={redesignPrompt}
                  onChange={(e) => setRedesignPrompt(e.target.value)}
                  placeholder="Describe the change you want — e.g. 'Add a dark header with a logo, make the run button purple, and show a stats row with total runs.'"
                  rows={3}
                  className="flex-1 min-w-[260px] px-3 py-2 rounded-sm text-[12px] font-mono"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text)", resize: "vertical" }}
                  disabled={redesigning}
                  onKeyDown={(e) => {
                    // Cmd/Ctrl+Enter submits
                    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                      e.preventDefault();
                      handleRedesign();
                    }
                  }}
                />
                <button
                  data-testid="app-viewer-redesign-submit"
                  onClick={handleRedesign}
                  disabled={redesigning || redesignPrompt.trim().length < 5}
                  className="inline-flex items-center gap-1 px-4 py-2 rounded-sm bg-purple-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono disabled:opacity-50 self-stretch"
                >
                  {redesigning ? (
                    <>
                      <Loader2 size={11} className="animate-spin" /> Redesigning…
                    </>
                  ) : (
                    <>
                      <Send size={11} /> Apply
                    </>
                  )}
                </button>
              </div>
              {redesigning && (
                <div data-testid="redesign-progress" className="text-[11px] font-mono t-text-sub flex items-center gap-2">
                  <Loader2 size={11} className="animate-spin text-purple-300" />
                  Building new UI with Gemini Flash — usually 5-15s. Hang tight…
                </div>
              )}

              {/* History strip */}
              {history.length > 0 && (
                <div data-testid="redesign-history" className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <History size={12} className="t-text-mute" />
                    <span className="text-[10px] font-mono uppercase tracking-[0.18em] t-text-mute">
                      Recent versions · {history.length}
                    </span>
                  </div>
                  <div className="space-y-1.5 max-h-[180px] overflow-y-auto pr-2">
                    {history.map((h) => (
                      <div
                        key={h.version_id}
                        data-testid={`history-row-${h.version_id}`}
                        className="flex items-center gap-3 px-2 py-1.5 rounded-sm"
                        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                      >
                        <span className="text-[10px] font-mono t-text-mute whitespace-nowrap">
                          {(h.created_at || "").slice(5, 16).replace("T", " ")}
                        </span>
                        <span className="text-[11px] t-text-sub flex-1 min-w-0 truncate" title={h.prompt}>
                          {h.prompt || "(no prompt)"}
                        </span>
                        <button
                          data-testid={`history-revert-${h.version_id}`}
                          onClick={() => handleRevert(h.version_id, h.prompt)}
                          disabled={!!reverting}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-sm text-[10px] font-mono uppercase tracking-wider hover:bg-purple-400/10 hover:text-purple-200 disabled:opacity-40"
                          style={{ color: "var(--text-sub)", border: "1px solid var(--border)" }}
                          title="Restore the UI as it was before this prompt"
                        >
                          {reverting === h.version_id ? (
                            <Loader2 size={10} className="animate-spin" />
                          ) : (
                            <Undo2 size={10} />
                          )}
                          Revert
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {showShare && app && (
          <div data-testid="app-viewer-share-panel" className="border-t" style={{ borderColor: "var(--border)" }}>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-3">
              {/* Visibility toggle */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-[11px] font-mono uppercase tracking-[0.15em] t-text-sub">Visibility:</span>
                <button
                  data-testid="app-share-public"
                  onClick={() => handleToggleShare(true)}
                  disabled={sharing || app.is_public}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-widest font-mono disabled:opacity-50"
                  style={{
                    background: app.is_public ? "rgba(16,185,129,0.15)" : "transparent",
                    border: `1px solid ${app.is_public ? "rgba(16,185,129,0.5)" : "var(--border)"}`,
                    color: app.is_public ? "#34d399" : "var(--text-sub)",
                  }}
                >
                  <Globe size={11} /> Public
                </button>
                <button
                  data-testid="app-share-private"
                  onClick={() => handleToggleShare(false)}
                  disabled={sharing || !app.is_public}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-widest font-mono disabled:opacity-50"
                  style={{
                    background: !app.is_public ? "rgba(251,191,36,0.10)" : "transparent",
                    border: `1px solid ${!app.is_public ? "rgba(251,191,36,0.4)" : "var(--border)"}`,
                    color: !app.is_public ? "#fbbf24" : "var(--text-sub)",
                  }}
                >
                  <Lock size={11} /> Private
                </button>
                <span className="text-[11px] t-text-mute font-mono">
                  {app.is_public
                    ? "Anyone with the link can launch this. Runs are billed to your wallet."
                    : "Only you can run this app."}
                </span>
              </div>

              {/* Direct URL */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono uppercase tracking-[0.15em] t-text-sub w-20">URL:</span>
                <input
                  readOnly
                  data-testid="app-share-url"
                  value={publicUrl}
                  onClick={(e) => e.target.select()}
                  className="flex-1 min-w-[260px] px-3 py-1.5 rounded-sm text-[11px] font-mono"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)" }}
                />
                <button
                  data-testid="app-share-url-copy"
                  onClick={() => copyToClipboard(publicUrl, "URL")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm bg-cyan-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono"
                >
                  <Copy size={10} /> Copy
                </button>
              </div>

              {/* Embed snippet */}
              <div className="flex items-start gap-2 flex-wrap">
                <span className="text-[11px] font-mono uppercase tracking-[0.15em] t-text-sub w-20 pt-2">Embed:</span>
                <textarea
                  readOnly
                  data-testid="app-share-embed"
                  value={embedSnippet}
                  onClick={(e) => e.target.select()}
                  rows={3}
                  className="flex-1 min-w-[260px] px-3 py-2 rounded-sm text-[11px] font-mono"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)", resize: "vertical" }}
                />
                <button
                  data-testid="app-share-embed-copy"
                  onClick={() => copyToClipboard(embedSnippet, "Embed code")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm bg-cyan-400 text-black text-[10px] font-bold uppercase tracking-widest font-mono"
                >
                  <Copy size={10} /> Copy
                </button>
              </div>

              {/* Quick share to socials */}
              {app.is_public && (
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <span className="text-[11px] font-mono uppercase tracking-[0.15em] t-text-sub w-20">Share:</span>
                  <a
                    data-testid="app-share-twitter"
                    href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(`I built "${app.name}" on Task Force AI — try it: ${publicUrl}`)}`}
                    target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-widest font-mono"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)" }}
                  >
                    <ExternalLink size={10} /> Twitter / X
                  </a>
                  <a
                    data-testid="app-share-linkedin"
                    href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(publicUrl)}`}
                    target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-widest font-mono"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)" }}
                  >
                    <ExternalLink size={10} /> LinkedIn
                  </a>
                </div>
              )}
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
            sandbox="allow-scripts allow-same-origin"
          />
        )}
        {!loading && !error && app && tab === "runs" && (
          <RunsTable runs={runs} />
        )}
      </div>

      {showCustomize && (
        <MiniAppCustomize
          slug={slug}
          onClose={() => setShowCustomize(false)}
          onSaved={() => setIframeBust((n) => n + 1)}
        />
      )}
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

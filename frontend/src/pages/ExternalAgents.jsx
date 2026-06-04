import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Upload, Package, Play, Trash2, RefreshCw, Terminal, Clock,
  CheckCircle2, AlertTriangle, Loader2, ShieldCheck, FileCode,
  ChevronDown, ChevronRight, ListTree,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_BADGE = {
  ready:         { label: "Ready",         color: "#22c55e", icon: CheckCircle2 },
  installing:    { label: "Installing…",   color: "#fbbf24", icon: Loader2 },
  failed:        { label: "Failed",        color: "#ef4444", icon: AlertTriangle },
  not_installed: { label: "Not installed", color: "#94a3b8", icon: Package },
};

function StatusPill({ status }) {
  const s = STATUS_BADGE[status] || STATUS_BADGE.not_installed;
  const Icon = s.icon;
  return (
    <span
      data-testid={`pkg-status-${status}`}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[10px] font-mono uppercase tracking-[0.15em]"
      style={{
        background: `${s.color}1a`,
        color: s.color,
        border: `1px solid ${s.color}55`,
      }}
    >
      <Icon size={11} className={status === "installing" ? "animate-spin" : ""} />
      {s.label}
    </span>
  );
}

function useAuthHeader() {
  const { token } = useAuth() || {};
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function ExternalAgents() {
  const auth = useAuth() || {};
  const authHeader = useAuthHeader();
  const [packages, setPackages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState({});
  const fileRef = useRef(null);
  const pollRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/external-agents/packages`, { headers: authHeader });
      if (!r.ok) throw new Error(`status ${r.status}`);
      const body = await r.json();
      setPackages(body.packages || []);
    } catch (e) {
      console.error("refresh failed:", e);
    } finally {
      setLoading(false);
    }
  }, [authHeader]);

  useEffect(() => { refresh(); }, [refresh]);

  // Background poll while any package is installing
  useEffect(() => {
    const installing = packages.some(p => p.install_status === "installing");
    if (installing && !pollRef.current) {
      pollRef.current = setInterval(refresh, 3000);
    }
    if (!installing && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [packages, refresh]);

  async function uploadFile(file) {
    if (!file) return;
    if (!/\.(tfagent|zip)$/i.test(file.name)) {
      toast.error("File must end in .tfagent or .zip");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${API}/api/external-agents/upload`, {
        method: "POST",
        headers: authHeader,
        body: fd,
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || "Upload failed");
        return;
      }
      if (!body.package_id) {
        toast.error(body.scan_result?.message || "Package rejected by security scan");
        return;
      }
      toast.success(`Uploaded ${body.manifest?.display_name || body.manifest?.name}`);
      refresh();
    } catch (e) {
      toast.error(`Upload failed: ${e.message}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function installPackage(pkgId) {
    try {
      const r = await fetch(`${API}/api/external-agents/packages/${pkgId}/install`, {
        method: "POST", headers: authHeader,
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || "Install failed");
        return;
      }
      toast.success(body.message || `Install ${body.install_status}`);
      refresh();
    } catch (e) {
      toast.error(`Install failed: ${e.message}`);
    }
  }

  async function deletePackage(pkgId) {
    if (!window.confirm("Delete this package? The on-disk venv will be removed.")) return;
    try {
      const r = await fetch(`${API}/api/external-agents/packages/${pkgId}`, {
        method: "DELETE", headers: authHeader,
      });
      if (!r.ok) {
        toast.error("Delete failed");
        return;
      }
      toast.success("Package deleted");
      refresh();
    } catch (e) {
      toast.error(`Delete failed: ${e.message}`);
    }
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-6xl mx-auto px-6 py-10" data-testid="external-agents-page">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim">
              Task Force AI / Armory
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold t-text mb-2">External Agents</h1>
          <p className="text-sm t-text-mute max-w-2xl">
            Upload your own <code className="text-cyan-400">.tfagent</code> packages. We AST-scan
            every file, validate dependencies against the whitelist, and run each agent in its
            own isolated pip venv.
          </p>
        </div>

        {/* Upload zone */}
        <div
          data-testid="upload-zone"
          className="t-card rounded-sm p-6 mb-8 transition-all hover:border-cyan-500/40 cursor-pointer"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer?.files?.[0];
            if (f) uploadFile(f);
          }}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".tfagent,.zip"
            className="hidden"
            data-testid="upload-file-input"
            onChange={(e) => uploadFile(e.target.files?.[0])}
          />
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-sm flex items-center justify-center shrink-0"
              style={{ background: "#22d3ee1a", border: "1px solid #22d3ee55" }}
            >
              {uploading
                ? <Loader2 size={20} className="animate-spin text-cyan-400" />
                : <Upload size={20} className="text-cyan-400" />}
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium t-text">
                {uploading ? "Uploading & scanning…" : "Drop a .tfagent file or click to browse"}
              </div>
              <div className="text-xs t-text-mute mt-0.5 font-mono">
                Max 50MB · AST scanned · whitelisted deps only
              </div>
            </div>
            <button
              data-testid="upload-btn"
              className="px-4 py-2 rounded-sm text-xs uppercase tracking-[0.15em] font-mono"
              style={{
                background: "#22d3ee",
                color: "#0a0e1a",
                opacity: uploading ? 0.5 : 1,
              }}
              disabled={uploading}
              onClick={(e) => { e.stopPropagation(); fileRef.current?.click(); }}
            >
              Upload
            </button>
          </div>
        </div>

        {/* Package list */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold t-text">Your packages</h2>
          <button
            data-testid="refresh-btn"
            onClick={refresh}
            className="text-xs t-text-mute hover:text-cyan-400 inline-flex items-center gap-1.5 font-mono"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="t-card rounded-sm p-8 text-center text-sm t-text-mute" data-testid="loading-state">
            <Loader2 className="animate-spin inline-block mr-2" size={14} /> Loading packages…
          </div>
        ) : packages.length === 0 ? (
          <div
            data-testid="empty-state"
            className="t-card rounded-sm p-10 text-center"
          >
            <Package className="mx-auto mb-3 t-text-dim" size={28} />
            <div className="text-sm t-text mb-1">No external agents yet</div>
            <div className="text-xs t-text-mute">
              Upload a <code className="text-cyan-400">.tfagent</code> zip to get started.
            </div>
          </div>
        ) : (
          <div className="space-y-3" data-testid="packages-list">
            {packages.map((pkg) => (
              <PackageRow
                key={pkg.id}
                pkg={pkg}
                expanded={!!expanded[pkg.id]}
                onToggle={() => setExpanded((m) => ({ ...m, [pkg.id]: !m[pkg.id] }))}
                onInstall={() => installPackage(pkg.id)}
                onDelete={() => deletePackage(pkg.id)}
                onRefresh={refresh}
                authHeader={authHeader}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PackageRow({ pkg, expanded, onToggle, onInstall, onDelete, onRefresh, authHeader }) {
  const manifest = pkg.manifest || {};
  const Icon = expanded ? ChevronDown : ChevronRight;
  return (
    <div
      data-testid={`package-row-${pkg.id}`}
      className="t-card rounded-sm overflow-hidden"
    >
      <div className="flex items-center gap-4 p-4">
        <button
          data-testid={`pkg-expand-${pkg.id}`}
          onClick={onToggle}
          className="t-text-mute hover:text-cyan-400"
        >
          <Icon size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <div className="text-sm font-medium t-text truncate">
              {manifest.display_name || manifest.name || pkg.id.slice(0, 8)}
            </div>
            <StatusPill status={pkg.install_status || "not_installed"} />
          </div>
          <div className="text-xs t-text-mute font-mono truncate">
            {manifest.name}@{manifest.version} · {manifest.entry_point} → {manifest.entry_function}()
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {pkg.install_status === "ready" ? (
            <span
              className="px-2 py-1 rounded-sm text-[10px] font-mono uppercase tracking-[0.1em] inline-flex items-center gap-1"
              style={{ color: "#22c55e", background: "#22c55e1a", border: "1px solid #22c55e55" }}
              data-testid={`pkg-ready-${pkg.id}`}
            >
              <ShieldCheck size={11} /> Ready
            </span>
          ) : (
            <button
              data-testid={`pkg-install-btn-${pkg.id}`}
              onClick={onInstall}
              disabled={pkg.install_status === "installing"}
              className="px-3 py-1.5 rounded-sm text-[11px] uppercase tracking-[0.12em] font-mono"
              style={{
                background: "#22d3ee",
                color: "#0a0e1a",
                opacity: pkg.install_status === "installing" ? 0.5 : 1,
              }}
            >
              {pkg.install_status === "installing" ? "Installing…" : "Install"}
            </button>
          )}
          <button
            data-testid={`pkg-delete-btn-${pkg.id}`}
            onClick={onDelete}
            className="p-1.5 rounded-sm text-rose-400 hover:bg-rose-400/10"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[color:var(--border)] p-4 space-y-4" data-testid={`pkg-expanded-${pkg.id}`}>
          <PackageDetails pkg={pkg} authHeader={authHeader} onRefresh={onRefresh} />
        </div>
      )}
    </div>
  );
}

function PackageDetails({ pkg, authHeader, onRefresh }) {
  const [tab, setTab] = useState("run");
  const [input, setInput] = useState('{"hello": "world"}');
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState(null);
  const manifest = pkg.manifest || {};

  async function loadRuns() {
    try {
      const r = await fetch(`${API}/api/external-agents/packages/${pkg.id}/runs`, { headers: authHeader });
      if (!r.ok) return;
      const body = await r.json();
      setRuns(body.runs || []);
    } catch { /* ignore */ }
  }
  useEffect(() => { if (tab === "runs") loadRuns(); }, [tab]); // eslint-disable-line

  async function runAgent() {
    setError(null);
    setRunning(true);
    setLastRun(null);
    let parsed;
    try {
      parsed = input.trim() ? JSON.parse(input) : {};
    } catch (e) {
      setError(`Invalid JSON: ${e.message}`);
      setRunning(false);
      return;
    }
    try {
      const r = await fetch(`${API}/api/external-agents/packages/${pkg.id}/run`, {
        method: "POST",
        headers: { ...authHeader, "Content-Type": "application/json" },
        body: JSON.stringify({ input: parsed }),
      });
      const body = await r.json();
      if (!r.ok) {
        setError(body.detail?.message || body.detail || `HTTP ${r.status}`);
        setLastRun(null);
      } else {
        setLastRun(body);
        toast.success(body.success ? "Run succeeded" : "Run failed");
        if (tab === "runs") loadRuns();
        onRefresh?.();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-[color:var(--border)]">
        {["run", "logs", "runs", "manifest"].map((t) => (
          <button
            key={t}
            data-testid={`pkg-tab-${t}-${pkg.id}`}
            onClick={() => setTab(t)}
            className="px-3 py-1.5 text-[11px] uppercase tracking-[0.12em] font-mono"
            style={{
              color: tab === t ? "#22d3ee" : "var(--text-mute)",
              borderBottom: tab === t ? "2px solid #22d3ee" : "2px solid transparent",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "run" && (
        <div className="space-y-3">
          {pkg.install_status !== "ready" ? (
            <div className="text-xs t-text-mute font-mono">
              Install the package first to enable runs.
            </div>
          ) : (
            <>
              <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-1">
                Input JSON
              </div>
              <textarea
                data-testid={`run-input-${pkg.id}`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={4}
                spellCheck={false}
                className="w-full font-mono text-xs t-text rounded-sm p-3 outline-none"
                style={{
                  background: "var(--bg-input)",
                  border: "1px solid var(--border)",
                  resize: "vertical",
                }}
              />
              <div className="flex items-center gap-3">
                <button
                  data-testid={`run-btn-${pkg.id}`}
                  onClick={runAgent}
                  disabled={running}
                  className="px-4 py-2 rounded-sm text-xs uppercase tracking-[0.15em] font-mono inline-flex items-center gap-2"
                  style={{ background: "#22d3ee", color: "#0a0e1a", opacity: running ? 0.5 : 1 }}
                >
                  {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                  {running ? "Running…" : "Run agent"}
                </button>
                <span className="text-[10px] font-mono t-text-dim">
                  Cost: 2 credits · Max {manifest.max_execution_time_seconds || 30}s
                </span>
              </div>
              {error && (
                <div
                  data-testid={`run-error-${pkg.id}`}
                  className="text-xs font-mono rounded-sm p-3"
                  style={{ background: "#ef44441a", border: "1px solid #ef444455", color: "#fca5a5" }}
                >
                  {error}
                </div>
              )}
              {lastRun && (
                <div
                  data-testid={`run-result-${pkg.id}`}
                  className="rounded-sm p-3 text-xs font-mono"
                  style={{
                    background: "var(--bg-input)",
                    border: `1px solid ${lastRun.success ? "#22c55e55" : "#ef444455"}`,
                  }}
                >
                  <div
                    className="flex items-center gap-2 mb-2"
                    style={{ color: lastRun.success ? "#22c55e" : "#ef4444" }}
                  >
                    {lastRun.success ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                    <span className="uppercase tracking-[0.12em]">
                      {lastRun.success ? "Success" : "Failed"}
                    </span>
                    <span className="t-text-mute ml-auto">{lastRun.duration_ms}ms</span>
                  </div>
                  {lastRun.success ? (
                    <pre className="t-text whitespace-pre-wrap break-all">
                      {JSON.stringify(lastRun.result, null, 2)}
                    </pre>
                  ) : (
                    <pre className="text-rose-400 whitespace-pre-wrap break-all">
                      {lastRun.error}
                    </pre>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "logs" && (
        <div>
          <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-2 flex items-center gap-2">
            <Terminal size={11} /> Install log (tail)
          </div>
          {pkg.install_status === "failed" && pkg.install_error && (
            <div
              data-testid={`install-error-${pkg.id}`}
              className="text-xs font-mono rounded-sm p-3 mb-3"
              style={{ background: "#ef44441a", border: "1px solid #ef444455", color: "#fca5a5" }}
            >
              {pkg.install_error}
            </div>
          )}
          <pre
            data-testid={`install-log-${pkg.id}`}
            className="text-[11px] font-mono whitespace-pre-wrap break-all rounded-sm p-3 max-h-80 overflow-auto"
            style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
          >
            {pkg.install_log || "(no log yet)"}
          </pre>
        </div>
      )}

      {tab === "runs" && (
        <div data-testid={`runs-list-${pkg.id}`}>
          {runs.length === 0 ? (
            <div className="text-xs t-text-mute font-mono">No runs yet.</div>
          ) : (
            <div className="space-y-1.5">
              {runs.slice(0, 25).map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-3 px-3 py-2 rounded-sm text-xs font-mono"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
                >
                  {r.success
                    ? <CheckCircle2 size={11} className="text-green-400 shrink-0" />
                    : <AlertTriangle size={11} className="text-rose-400 shrink-0" />}
                  <span className="t-text-mute">{r.started_at?.slice(0, 19).replace("T", " ")}</span>
                  <span className="t-text-mute ml-auto">
                    <Clock size={9} className="inline mr-1" />{r.duration_ms}ms
                  </span>
                  <span style={{ color: r.success ? "#22c55e" : "#ef4444" }}>
                    {r.success ? "ok" : "failed"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "manifest" && (
        <div>
          <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-2 flex items-center gap-2">
            <FileCode size={11} /> manifest.json
          </div>
          <pre
            data-testid={`manifest-display-${pkg.id}`}
            className="text-[11px] font-mono t-text whitespace-pre-wrap break-all rounded-sm p-3"
            style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
          >
            {JSON.stringify(manifest, null, 2)}
          </pre>
          {pkg.install_deps_pinned?.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-1 flex items-center gap-2">
                <ListTree size={11} /> Pinned dependencies
              </div>
              <div className="flex flex-wrap gap-1.5">
                {pkg.install_deps_pinned.map((d) => (
                  <span
                    key={d}
                    className="px-2 py-0.5 text-[10px] font-mono rounded-sm"
                    style={{ background: "#22d3ee1a", color: "#22d3ee", border: "1px solid #22d3ee55" }}
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

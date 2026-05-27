import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/App";
import { Link } from "react-router-dom";
import {
  Server, Wifi, WifiOff, Settings, Play, Trash2, Plus, Download,
  RefreshCw, Loader2, Shield, Key, Eye, EyeOff, Copy, ExternalLink,
  Zap, GitBranch, Clock, ChevronDown, ChevronRight, AlertTriangle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { parseComputeLimit, ComputeLimitModal } from "./ComputeLimitModal";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Engine Status Badge ─── */
function StatusBadge({ connected }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-none ${connected ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
      <span className={`text-[10px] font-mono tracking-wide ${connected ? "text-emerald-400" : "text-red-400"}`}>
        {connected ? "ENGINE ONLINE" : "ENGINE OFFLINE"}
      </span>
    </div>
  );
}

/* ─── Setup Guide (shown when n8n not connected) ─── */
function SetupGuide({ guide }) {
  return (
    <div className="flex-1 overflow-y-auto p-6 lg:p-10">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-sm flex items-center justify-center" style={{ background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.15)" }}>
            <Server size={22} className="text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold t-text font-mono tracking-wide uppercase">{guide.title}</h2>
            <p className="text-[12px] t-text-mute">One-time setup to enable full workflow execution</p>
          </div>
        </div>

        <div className="space-y-4 mb-8">
          {guide.steps.map((step) => (
            <div key={step.step} className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-3 mb-2">
                <span className="w-7 h-7 rounded-sm flex items-center justify-center text-[12px] font-mono font-bold text-cyan-400" style={{ background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.12)" }}>
                  {step.step}
                </span>
                <h3 className="text-[14px] font-bold t-text font-mono">{step.title}</h3>
              </div>
              <div className="ml-10">
                <pre className="text-[11px] font-mono text-cyan-300 rounded-sm p-3 mb-2 whitespace-pre-wrap leading-relaxed" style={{ background: "#0a0a0c", border: "1px solid #1a1a1e" }}>
                  {step.command}
                </pre>
                <p className="text-[11px] t-text-mute">{step.note}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-sm p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <h4 className="text-[12px] font-mono font-bold t-text-sub tracking-wide uppercase mb-3">Hosting Options</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {guide.alternatives.map((alt) => (
              <a key={alt.platform} href={alt.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 p-3 rounded-sm hover:border-cyan-400/30 transition-all" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                <ExternalLink size={12} className="text-cyan-400 shrink-0" />
                <div>
                  <p className="text-[12px] font-mono t-text font-medium">{alt.platform}</p>
                  <p className="text-[10px] t-text-dim">{alt.cost}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Workflow Card ─── */
function WorkflowCard({ wf, onExecute, onDelete, executing }) {
  const [expanded, setExpanded] = useState(false);
  const nodeCount = wf.nodes?.length || 0;
  const isRunning = executing === wf.id;

  return (
    <div data-testid={`n8n-workflow-${wf.id}`} className="rounded-sm overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="p-4 flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background: "rgba(34,211,238,0.06)", border: "1px solid rgba(34,211,238,0.1)" }}>
          <GitBranch size={15} className="text-cyan-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-mono t-text font-medium truncate">{wf.name || `Workflow #${wf.id}`}</p>
          <p className="text-[10px] font-mono t-text-dim">{nodeCount} nodes | Updated {wf.updatedAt ? new Date(wf.updatedAt).toLocaleDateString() : "—"}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); onExecute(wf.id); }}
            disabled={isRunning}
            data-testid={`run-n8n-${wf.id}`}
            className="px-3 py-1.5 text-[10px] font-mono font-bold tracking-wide uppercase rounded-sm flex items-center gap-1.5 bg-cyan-400/10 text-cyan-400 border border-cyan-400/20 hover:bg-cyan-400/20 transition-all disabled:opacity-50"
          >
            {isRunning ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
            {isRunning ? "Running..." : "Execute"}
          </button>
          <button onClick={(e) => { e.stopPropagation(); onDelete(wf.id); }} className="p-1.5 text-zinc-600 hover:text-red-400 transition-colors">
            <Trash2 size={13} />
          </button>
          {expanded ? <ChevronDown size={14} className="t-text-dim" /> : <ChevronRight size={14} className="t-text-dim" />}
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
            <div className="px-4 pb-4" style={{ borderTop: "1px solid var(--border)" }}>
              <pre className="mt-3 text-[10px] font-mono t-text-mute rounded-sm p-3 max-h-[200px] overflow-auto leading-relaxed" style={{ background: "#0a0a0c", border: "1px solid #1a1a1e" }}>
                {JSON.stringify(wf, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── BYOK Credential Manager ─── */
function CredentialManager({ token }) {
  const [creds, setCreds] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("apiKey");
  const [key, setKey] = useState("");

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/n8n/credentials`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setCreds(d.credentials || []); }
    } catch {}
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!name || !key) { toast.error("Name and key required."); return; }
    try {
      await fetch(`${API}/api/n8n/credentials`, { method: "POST", headers, body: JSON.stringify({ name, type, data: { apiKey: key } }) });
      toast.success("Credential saved.");
      setName(""); setKey(""); setShowAdd(false); load();
    } catch { toast.error("Failed to save."); }
  };

  const remove = async (credName) => {
    await fetch(`${API}/api/n8n/credentials/${credName}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    toast.success("Credential deleted."); load();
  };

  return (
    <div className="rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2">
          <Key size={13} className="text-cyan-400" />
          <span className="text-[12px] font-mono font-medium t-text tracking-wide uppercase">BYOK Vault</span>
        </div>
        <button onClick={() => setShowAdd(!showAdd)} className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
          <Plus size={11} /> Add Key
        </button>
      </div>

      {showAdd && (
        <div className="px-4 py-3 space-y-2" style={{ borderBottom: "1px solid var(--border)" }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Credential name (e.g. OpenAI)" className="w-full t-input rounded-sm px-3 py-2 text-[12px] font-mono focus:outline-none" style={{ border: "1px solid var(--border)" }} />
          <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="API key or secret" type="password" className="w-full t-input rounded-sm px-3 py-2 text-[12px] font-mono focus:outline-none" style={{ border: "1px solid var(--border)" }} />
          <button onClick={save} className="px-4 py-1.5 bg-cyan-400 text-black text-[11px] font-mono font-bold rounded-sm">Save</button>
        </div>
      )}

      {creds.length === 0 && !showAdd ? (
        <div className="px-4 py-6 text-center">
          <Key size={20} className="t-text-dim mx-auto mb-2" />
          <p className="text-[11px] font-mono t-text-mute">No credentials stored yet.</p>
          <p className="text-[10px] t-text-dim mt-1">Add your API keys to enable workflow integrations.</p>
        </div>
      ) : (
        <div>
          {creds.map((c) => (
            <div key={c.name} className="px-4 py-2.5 flex items-center gap-3" style={{ borderBottom: "1px solid var(--border)" }}>
              <Shield size={12} className="text-emerald-400 shrink-0" />
              <span className="text-[12px] font-mono t-text flex-1 truncate">{c.name}</span>
              <span className="text-[10px] font-mono t-text-dim">{c.type}</span>
              <button onClick={() => remove(c.name)} className="text-zinc-600 hover:text-red-400"><Trash2 size={11} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══ MAIN EXPORT ═══ */
export default function ArmoryEditor({ visible }) {
  const { token } = useAuth();
  const [engineStatus, setEngineStatus] = useState(null);
  const [guide, setGuide] = useState(null);
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(null);
  const [computeLimit, setComputeLimit] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/n8n/status`, { headers });
      if (res.ok) setEngineStatus(await res.json());
    } catch {}
  }, [token]);

  const loadGuide = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/n8n/setup-guide`, { headers });
      if (res.ok) setGuide(await res.json());
    } catch {}
  }, [token]);

  const loadWorkflows = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/n8n/workflows`, { headers });
      if (res.ok) { const d = await res.json(); setWorkflows(d.workflows || []); }
    } catch {}
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const init = async () => {
      setLoading(true);
      await checkStatus();
      await loadGuide();
      await loadWorkflows();
      setLoading(false);
    };
    init();
  }, [token]);

  const executeWorkflow = async (wfId) => {
    setExecuting(wfId);
    try {
      const res = await fetch(`${API}/api/n8n/workflows/${wfId}/execute`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: "{}",
      });
      const data = await res.json();
      const limitData = parseComputeLimit(res.status, data);
      if (limitData) { setComputeLimit(limitData); setExecuting(null); return; }
      if (data.success) toast.success("Workflow executed successfully.");
      else toast.error("Execution failed.");
    } catch { toast.error("Execution error."); }
    setExecuting(null);
  };

  const deleteWorkflow = async (wfId) => {
    try {
      await fetch(`${API}/api/n8n/workflows/${wfId}`, { method: "DELETE", headers });
      toast.success("Workflow deleted."); loadWorkflows();
    } catch { toast.error("Failed to delete."); }
  };

  if (!visible) return null;

  const isConnected = engineStatus?.connected === true;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center t-bg">
        <Loader2 size={20} className="text-cyan-400 animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="armory-editor" className="flex-1 flex flex-col t-bg h-full overflow-hidden">
      {/* Header bar */}
      <div className="px-4 py-3 flex items-center justify-between shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <StatusBadge connected={isConnected} />
        <div className="flex items-center gap-2">
          <button onClick={async () => { await checkStatus(); await loadWorkflows(); }} className="p-1.5 t-text-dim hover:text-cyan-400 transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Main content */}
      {!isConnected ? (
        guide ? <SetupGuide guide={guide} /> : <div className="flex-1 flex items-center justify-center t-text-dim text-[13px] font-mono">Loading setup guide...</div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar: Workflows + Credentials */}
          <div className="w-[300px] min-w-[300px] flex flex-col overflow-y-auto" style={{ borderRight: "1px solid var(--border)" }}>
            {/* Workflows */}
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold t-text tracking-[0.1em] uppercase">My Workflows</span>
                <span className="text-[10px] font-mono t-text-dim">{workflows.length}</span>
              </div>
              {workflows.length === 0 ? (
                <div className="text-center py-8">
                  <GitBranch size={24} className="t-text-dim mx-auto mb-2" />
                  <p className="text-[11px] font-mono t-text-mute">No workflows yet</p>
                  <p className="text-[10px] t-text-dim mt-1">Acquire templates from The Exchange</p>
                  <Link to="/exchange" className="inline-flex items-center gap-1 mt-3 text-[10px] font-mono text-cyan-400 hover:text-cyan-300">
                    <ExternalLink size={10} /> Browse The Exchange
                  </Link>
                </div>
              ) : (
                <div className="space-y-2">
                  {workflows.map((wf) => (
                    <WorkflowCard key={wf.id} wf={wf} onExecute={executeWorkflow} onDelete={deleteWorkflow} executing={executing} />
                  ))}
                </div>
              )}
            </div>

            {/* Credential Vault */}
            <div className="p-4 mt-auto">
              <CredentialManager token={token} />
            </div>
          </div>

          {/* Main editor area: n8n iframe/proxy */}
          <div className="flex-1 flex items-center justify-center" style={{ background: "#000" }}>
            <div className="text-center max-w-md px-6">
              <motion.div
                animate={{ boxShadow: ["0 0 20px rgba(34,211,238,0.1)", "0 0 40px rgba(34,211,238,0.2)", "0 0 20px rgba(34,211,238,0.1)"] }}
                transition={{ duration: 3, repeat: Infinity }}
                className="w-16 h-16 rounded-sm flex items-center justify-center mx-auto mb-5"
                style={{ background: "rgba(34,211,238,0.06)", border: "1px solid rgba(34,211,238,0.12)" }}
              >
                <Zap size={28} className="text-cyan-400" />
              </motion.div>
              <h3 className="text-[16px] font-mono font-bold t-text uppercase tracking-wide mb-2">Execution Engine Connected</h3>
              <p className="text-[12px] t-text-mute leading-relaxed mb-4">
                Your workflow engine is online. Select a workflow from the sidebar to execute, or browse The Exchange to acquire templates.
              </p>
              <div className="flex items-center justify-center gap-3">
                <Link to="/exchange" className="px-4 py-2 bg-cyan-400 text-black text-[11px] font-mono font-bold tracking-wide uppercase rounded-sm hover:bg-cyan-300 transition-all flex items-center gap-1.5">
                  <Download size={12} /> Get Templates
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      <ComputeLimitModal limitData={computeLimit} onClose={() => setComputeLimit(null)} />
    </div>
  );
}

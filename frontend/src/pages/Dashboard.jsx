import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  Plus, Play, Square, Trash2, Copy, ExternalLink, Clock,
  CheckCircle2, XCircle, ChevronDown, ChevronUp, Zap, Shield,
  Code, Globe, Terminal, RotateCw, Loader2, ArrowUpRight,
  Package, Webhook, Settings, AlertTriangle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const SAMPLE_AGENTS = [
  {
    name: "Echo Bot",
    description: "Returns whatever you send it — great for testing webhooks.",
    code: `# Echo Bot - Returns the input data
data = INPUT
print(f"Received: {json.dumps(data)}")
RESULT = {"echo": data, "status": "ok"}`,
  },
  {
    name: "Data Cruncher",
    description: "Processes a list of numbers and returns statistics.",
    code: `# Data Cruncher - Analyze numbers
import math

numbers = INPUT.get("numbers", [])
if not numbers:
    RESULT = {"error": "No numbers provided"}
else:
    total = sum(numbers)
    avg = total / len(numbers)
    sorted_nums = sorted(numbers)
    median = sorted_nums[len(sorted_nums) // 2]
    print(f"Processed {len(numbers)} numbers")
    RESULT = {
        "count": len(numbers),
        "total": total,
        "average": round(avg, 2),
        "median": median,
        "min": min(numbers),
        "max": max(numbers),
    }`,
  },
  {
    name: "JSON Transformer",
    description: "Transforms and reshapes JSON data.",
    code: `# JSON Transformer
import json

data = INPUT
keys = list(data.keys()) if isinstance(data, dict) else []
print(f"Transforming {len(keys)} fields")
RESULT = {
    "fields": keys,
    "field_count": len(keys),
    "data_types": {k: type(v).__name__ for k, v in data.items()} if isinstance(data, dict) else {},
    "original": data,
}`,
  },
];

/* ─── Stat Card ─── */
function StatCard({ label, value, max, icon: Icon, color }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div data-testid={`stat-${label.toLowerCase().replace(/\s/g, "-")}`} className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-4 sm:p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[12px] text-zinc-500 tracking-wide">{label}</span>
        <Icon size={14} style={{ color }} />
      </div>
      <p className="text-2xl font-semibold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>
        {value}{max ? <span className="text-[14px] text-zinc-600">/{max}</span> : ""}
      </p>
      {max && (
        <div className="mt-3 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${pct}%`, background: pct >= 90 ? "#EF4444" : color }}
          />
        </div>
      )}
    </div>
  );
}

/* ─── Agent Card ─── */
function AgentCard({ agent, onRun, onToggle, onDelete, onViewLogs, onCopyWebhook, webhookBase, expanded, onToggleExpand }) {
  const isReady = agent.status === "ready";
  return (
    <div data-testid={`agent-card-${agent.id}`} className="bg-white/[0.03] border border-white/[0.07] rounded-xl overflow-hidden transition-all hover:border-white/[0.12]">
      <div className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <div className={`w-2 h-2 rounded-full shrink-0 ${isReady ? "bg-emerald-400" : "bg-zinc-600"}`} />
              <h3 className="text-[14px] font-medium text-white truncate">{agent.name}</h3>
            </div>
            <p className="text-[12px] text-zinc-500 line-clamp-1">{agent.description || "No description"}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => onRun(agent.id)}
              data-testid={`run-agent-${agent.id}`}
              disabled={!isReady}
              className="p-2 rounded-lg bg-[#8B5CF6]/10 text-[#8B5CF6] hover:bg-[#8B5CF6]/20 transition-colors disabled:opacity-30"
              title="Run"
            >
              <Play size={14} />
            </button>
            <button
              onClick={() => onToggle(agent.id, agent.status)}
              data-testid={`toggle-agent-${agent.id}`}
              className={`p-2 rounded-lg transition-colors ${isReady ? "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20" : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"}`}
              title={isReady ? "Disable" : "Enable"}
            >
              {isReady ? <Square size={14} /> : <Play size={14} />}
            </button>
            <button
              onClick={() => onDelete(agent.id)}
              data-testid={`delete-agent-${agent.id}`}
              className="p-2 rounded-lg bg-red-500/5 text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              title="Delete"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-4 mt-3.5 text-[11px] text-zinc-600">
          <span className="flex items-center gap-1"><Clock size={10} /> {agent.run_count} runs</span>
          {agent.last_result && (
            <span className={`flex items-center gap-1 ${agent.last_result === "success" ? "text-emerald-500" : "text-red-400"}`}>
              {agent.last_result === "success" ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
              Last: {agent.last_result}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Globe size={10} />
            {agent.trigger_type === "both" ? "Manual + Webhook" : agent.trigger_type === "webhook" ? "Webhook" : "Manual"}
          </span>
        </div>

        {/* Webhook URL */}
        {(agent.trigger_type === "webhook" || agent.trigger_type === "both") && (
          <div className="mt-3 flex items-center gap-2">
            <div className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-[11px] text-zinc-500 font-mono truncate">
              {webhookBase}/api/webhook/agent/{agent.webhook_key}
            </div>
            <button
              onClick={() => onCopyWebhook(agent.webhook_key)}
              data-testid={`copy-webhook-${agent.id}`}
              className="p-2 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
              title="Copy webhook URL"
            >
              <Copy size={12} />
            </button>
          </div>
        )}

        {/* Expand toggle */}
        <button
          onClick={() => onToggleExpand(agent.id)}
          className="mt-3 flex items-center gap-1 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? "Hide code" : "Show code"}
        </button>
      </div>

      {/* Expanded code view */}
      {expanded && (
        <div className="border-t border-white/[0.06] bg-zinc-900/50 p-4 max-h-[200px] overflow-y-auto">
          <pre className="text-[11px] text-zinc-400 leading-relaxed whitespace-pre-wrap font-mono">{agent.code}</pre>
        </div>
      )}
    </div>
  );
}

/* ─── Create/Run Agent Modal ─── */
function AgentModal({ mode, agent, onClose, onSubmit, templates }) {
  const [name, setName] = useState(agent?.name || "");
  const [description, setDescription] = useState(agent?.description || "");
  const [code, setCode] = useState(agent?.code || "# Write your agent code here\n# Access input via INPUT dict\n# Access env vars via ENV dict\n# Set RESULT to return output\n# Safe imports: json, math, re, datetime, collections, random, string, hashlib, base64\n\ndata = INPUT\nprint(f\"Received: {data}\")\nRESULT = {\"status\": \"ok\", \"data\": data}\n");
  const [envVars, setEnvVars] = useState(agent?.env_vars ? Object.entries(agent.env_vars).map(([k, v]) => ({ k, v })) : []);
  const [triggerType, setTriggerType] = useState(agent?.trigger_type || "both");
  const [inputData, setInputData] = useState("{}");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const isRun = mode === "run";

  const handleSubmit = async () => {
    if (!isRun && !name.trim()) { toast.error("Name is required."); return; }
    if (!isRun && !code.trim()) { toast.error("Code is required."); return; }
    setSubmitting(true);

    if (isRun) {
      let parsed;
      try { parsed = JSON.parse(inputData); } catch { toast.error("Invalid JSON input."); setSubmitting(false); return; }
      const res = await onSubmit({ input_data: parsed });
      if (res) setResult(res);
    } else {
      const envObj = {};
      envVars.forEach(({ k, v }) => { if (k.trim()) envObj[k.trim()] = v; });
      await onSubmit({ name, description, code, env_vars: envObj, trigger_type: triggerType });
    }
    setSubmitting(false);
  };

  const loadTemplate = (tmpl) => {
    setName(tmpl.name);
    setDescription(tmpl.description);
    setCode(tmpl.code);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        data-testid="agent-modal"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[90vh] bg-zinc-900 border border-white/[0.08] rounded-2xl overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between">
          <h3 className="text-[15px] font-semibold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {isRun ? `Run: ${agent?.name}` : agent ? "Edit Agent" : "Deploy New Agent"}
          </h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 transition-colors"><XCircle size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {isRun ? (
            <>
              <div>
                <label className="block text-[12px] text-zinc-500 mb-2">Input Payload (JSON)</label>
                <textarea
                  value={inputData} onChange={(e) => setInputData(e.target.value)}
                  data-testid="run-input-textarea"
                  className="w-full h-28 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-[13px] text-white font-mono placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 resize-none"
                  placeholder='{"key": "value"}'
                />
              </div>
              {result && (
                <div data-testid="run-result" className={`border rounded-xl p-4 ${result.success ? "bg-emerald-500/5 border-emerald-500/20" : "bg-red-500/5 border-red-500/20"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    {result.success ? <CheckCircle2 size={14} className="text-emerald-400" /> : <XCircle size={14} className="text-red-400" />}
                    <span className="text-[13px] font-medium text-white">{result.success ? "Success" : "Error"}</span>
                    <span className="ml-auto text-[11px] text-zinc-500">{result.duration_ms}ms</span>
                  </div>
                  {result.output && (
                    <div className="mb-2">
                      <p className="text-[10px] text-zinc-500 mb-1">Output:</p>
                      <pre className="text-[12px] text-zinc-300 bg-black/30 rounded-lg p-3 whitespace-pre-wrap max-h-[100px] overflow-y-auto font-mono">{result.output}</pre>
                    </div>
                  )}
                  {result.result != null && (
                    <div className="mb-2">
                      <p className="text-[10px] text-zinc-500 mb-1">RESULT:</p>
                      <pre className="text-[12px] text-emerald-300 bg-black/30 rounded-lg p-3 whitespace-pre-wrap max-h-[100px] overflow-y-auto font-mono">{JSON.stringify(result.result, null, 2)}</pre>
                    </div>
                  )}
                  {result.error && (
                    <div>
                      <p className="text-[10px] text-zinc-500 mb-1">Error:</p>
                      <pre className="text-[12px] text-red-300 bg-black/30 rounded-lg p-3 whitespace-pre-wrap max-h-[100px] overflow-y-auto font-mono">{result.error}</pre>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              {/* Templates */}
              {!agent && (
                <div>
                  <p className="text-[12px] text-zinc-500 mb-2">Quick Start Templates</p>
                  <div className="flex flex-wrap gap-2">
                    {templates.map((t, i) => (
                      <button key={i} onClick={() => loadTemplate(t)} data-testid={`template-${i}`} className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.06] text-[11px] text-zinc-400 rounded-lg hover:border-[#8B5CF6]/30 hover:text-zinc-200 transition-all">
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[12px] text-zinc-500 mb-2">Name</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} data-testid="agent-name-input" placeholder="My Agent" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50" />
                </div>
                <div>
                  <label className="block text-[12px] text-zinc-500 mb-2">Trigger</label>
                  <select value={triggerType} onChange={(e) => setTriggerType(e.target.value)} data-testid="agent-trigger-select" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-[13px] text-white focus:outline-none focus:border-[#8B5CF6]/50 appearance-none">
                    <option value="manual" className="bg-zinc-900">Manual Only</option>
                    <option value="webhook" className="bg-zinc-900">Webhook Only</option>
                    <option value="both" className="bg-zinc-900">Manual + Webhook</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[12px] text-zinc-500 mb-2">Description</label>
                <input value={description} onChange={(e) => setDescription(e.target.value)} data-testid="agent-desc-input" placeholder="What does this agent do?" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50" />
              </div>

              <div>
                <label className="block text-[12px] text-zinc-500 mb-2">Agent Code (Python)</label>
                <textarea
                  value={code} onChange={(e) => setCode(e.target.value)}
                  data-testid="agent-code-textarea"
                  className="w-full h-48 bg-black/40 border border-white/[0.08] rounded-xl px-4 py-3 text-[12px] text-emerald-300 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/50 resize-none leading-relaxed"
                  spellCheck={false}
                />
                <div className="mt-1.5 flex items-center gap-3 text-[10px] text-zinc-600">
                  <span className="flex items-center gap-1"><Shield size={9} /> Sandboxed Execution</span>
                  <span>Allowed: json, math, re, datetime, collections, random, hashlib, base64</span>
                </div>
              </div>

              {/* Env Vars */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-[12px] text-zinc-500">Environment Variables</label>
                  <button onClick={() => setEnvVars([...envVars, { k: "", v: "" }])} className="text-[11px] text-[#A78BFA] hover:text-[#C084FC] transition-colors flex items-center gap-1">
                    <Plus size={10} /> Add
                  </button>
                </div>
                {envVars.map((pair, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input value={pair.k} onChange={(e) => { const arr = [...envVars]; arr[i].k = e.target.value; setEnvVars(arr); }} placeholder="KEY" className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[12px] text-white font-mono focus:outline-none focus:border-[#8B5CF6]/50" />
                    <input value={pair.v} onChange={(e) => { const arr = [...envVars]; arr[i].v = e.target.value; setEnvVars(arr); }} placeholder="value" className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[12px] text-white font-mono focus:outline-none focus:border-[#8B5CF6]/50" />
                    <button onClick={() => setEnvVars(envVars.filter((_, j) => j !== i))} className="p-2 text-zinc-600 hover:text-red-400"><Trash2 size={12} /></button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/[0.06] flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-5 py-2.5 text-[13px] text-zinc-400 hover:text-zinc-200 transition-colors">Cancel</button>
          <button
            onClick={handleSubmit}
            data-testid={isRun ? "execute-agent-btn" : "deploy-agent-btn"}
            disabled={submitting}
            className="px-6 py-2.5 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] disabled:opacity-50 flex items-center gap-2"
          >
            {submitting ? <Loader2 size={13} className="animate-spin" /> : isRun ? <Play size={13} /> : <Zap size={13} />}
            {isRun ? "Execute" : agent ? "Update" : "Deploy Agent"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Execution Log ─── */
function ExecutionLog({ executions }) {
  if (!executions.length) return null;
  return (
    <div data-testid="execution-log" className="bg-white/[0.03] border border-white/[0.07] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
        <Terminal size={13} className="text-zinc-500" />
        <span className="text-[12px] text-zinc-500">Recent Executions</span>
      </div>
      <div className="max-h-[300px] overflow-y-auto divide-y divide-white/[0.04]">
        {executions.map((ex) => (
          <div key={ex.id} className="px-4 py-3 flex items-center gap-3 text-[12px]">
            {ex.success ? <CheckCircle2 size={12} className="text-emerald-400 shrink-0" /> : <XCircle size={12} className="text-red-400 shrink-0" />}
            <span className="text-zinc-300 font-medium truncate">{ex.trigger}</span>
            <span className="text-zinc-600">{ex.duration_ms}ms</span>
            {ex.result && <span className="text-zinc-500 truncate hidden sm:inline max-w-[200px]">{JSON.stringify(ex.result).slice(0, 60)}</span>}
            <span className="ml-auto text-zinc-700 shrink-0">{new Date(ex.created_at).toLocaleTimeString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main Dashboard ─── */
export default function Dashboard() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [agents, setAgents] = useState([]);
  const [purchased, setPurchased] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [modalMode, setModalMode] = useState(null); // "create" | "edit" | "run" | null
  const [modalAgent, setModalAgent] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("agents");

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchData = useCallback(async () => {
    try {
      const [s, a, p] = await Promise.all([
        fetch(`${API}/api/dashboard/stats`, { headers }).then((r) => r.json()),
        fetch(`${API}/api/dashboard/agents`, { headers }).then((r) => r.json()),
        fetch(`${API}/api/dashboard/purchased`, { headers }).then((r) => r.json()),
      ]);
      setStats(s);
      setAgents(Array.isArray(a) ? a : []);
      setPurchased(Array.isArray(p) ? p : []);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) fetchData(); }, [token, fetchData]);

  const loadExecutions = async (agentId) => {
    try {
      const data = await fetch(`${API}/api/dashboard/agents/${agentId}/executions`, { headers }).then((r) => r.json());
      setExecutions(Array.isArray(data) ? data : []);
    } catch {}
  };

  const createAgent = async (data) => {
    try {
      const res = await fetch(`${API}/api/dashboard/agents`, { method: "POST", headers, body: JSON.stringify(data) });
      if (res.ok) {
        toast.success("Agent deployed!");
        setModalMode(null);
        fetchData();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Deploy failed.");
      }
    } catch { toast.error("Network error."); }
  };

  const runAgent = async (data) => {
    if (!modalAgent) return null;
    try {
      const res = await fetch(`${API}/api/dashboard/agents/${modalAgent.id}/run`, { method: "POST", headers, body: JSON.stringify(data) });
      if (res.ok) {
        const result = await res.json();
        fetchData();
        loadExecutions(modalAgent.id);
        return result;
      } else {
        const err = await res.json();
        toast.error(err.detail || "Execution failed.");
      }
    } catch { toast.error("Network error."); }
    return null;
  };

  const toggleAgent = async (id, currentStatus) => {
    const endpoint = currentStatus === "ready" ? "stop" : "start";
    try {
      await fetch(`${API}/api/dashboard/agents/${id}/${endpoint}`, { method: "POST", headers });
      fetchData();
    } catch { toast.error("Failed to toggle agent."); }
  };

  const deleteAgent = async (id) => {
    try {
      await fetch(`${API}/api/dashboard/agents/${id}`, { method: "DELETE", headers });
      toast.success("Agent deleted.");
      fetchData();
      if (expandedId === id) setExpandedId(null);
    } catch { toast.error("Failed to delete."); }
  };

  const copyWebhook = (key) => {
    navigator.clipboard.writeText(`${API}/api/webhook/agent/${key}`);
    toast.success("Webhook URL copied.");
  };

  const openRun = (id) => {
    const agent = agents.find((a) => a.id === id);
    if (agent) { setModalAgent(agent); setModalMode("run"); loadExecutions(id); }
  };

  if (loading) return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center">
      <Loader2 size={24} className="text-[#8B5CF6] animate-spin" />
    </div>
  );

  return (
    <div data-testid="dashboard-page" className="min-h-[calc(100vh-60px)] bg-zinc-950 px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Dashboard
            </h1>
            <p className="text-[13px] text-zinc-500 mt-1">Manage and monitor your deployed agents</p>
          </div>
          <button
            onClick={() => { setModalAgent(null); setModalMode("create"); }}
            data-testid="create-agent-btn"
            disabled={stats && stats.agent_count >= stats.agent_limit}
            className="px-5 py-2.5 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] flex items-center gap-2 disabled:opacity-50"
          >
            <Plus size={14} /> Deploy Agent
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
          <StatCard label="Agents" value={stats?.agent_count || 0} max={stats?.agent_limit || 3} icon={Package} color="#8B5CF6" />
          <StatCard label="Total Runs" value={stats?.total_runs || 0} icon={Play} color="#A78BFA" />
          <StatCard label="Purchased" value={stats?.purchased_agents || 0} icon={ArrowUpRight} color="#7C3AED" />
          <StatCard label="Tier" value={stats?.tier?.toUpperCase() || "FREE"} icon={Shield} color={stats?.tier === "pro" ? "#A78BFA" : "#6B7280"} />
        </div>

        {/* Upgrade banner */}
        {stats && stats.agent_count >= stats.agent_limit && stats.tier === "free" && (
          <div data-testid="upgrade-banner" className="mb-6 bg-gradient-to-r from-[#8B5CF6]/10 to-[#6D28D9]/10 border border-[#8B5CF6]/20 rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
            <AlertTriangle size={18} className="text-[#A78BFA] shrink-0" />
            <div className="flex-1">
              <p className="text-[13px] text-white font-medium">Agent limit reached ({stats.agent_count}/{stats.agent_limit})</p>
              <p className="text-[12px] text-zinc-500 mt-0.5">Upgrade to Pro for unlimited agents, priority execution, and advanced analytics.</p>
            </div>
            <button className="px-5 py-2 bg-[#8B5CF6] text-white text-[12px] font-medium rounded-full hover:bg-[#A78BFA] transition-all whitespace-nowrap">
              Upgrade to Pro
            </button>
          </div>
        )}

        {/* Tab toggle */}
        <div className="flex items-center gap-1 mb-6 bg-white/[0.03] border border-white/[0.07] rounded-full p-1 w-fit">
          {[
            { id: "agents", label: "My Agents", icon: Code },
            { id: "purchased", label: "Purchased", icon: Package },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-testid={`tab-${t.id}`}
              className={`flex items-center gap-1.5 px-4 py-2 text-[12px] rounded-full transition-all ${
                activeTab === t.id ? "bg-[#8B5CF6] text-white" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <t.icon size={12} /> {t.label}
            </button>
          ))}
        </div>

        {/* Agents Tab */}
        {activeTab === "agents" && (
          <div className="space-y-4">
            {agents.length === 0 ? (
              <div className="text-center py-16 border border-dashed border-white/[0.08] rounded-2xl">
                <Zap size={32} className="text-zinc-700 mx-auto mb-3" />
                <p className="text-[14px] text-zinc-500 mb-1">No agents deployed yet</p>
                <p className="text-[12px] text-zinc-600 mb-4">Deploy your first custom AI agent to get started.</p>
                <button
                  onClick={() => { setModalAgent(null); setModalMode("create"); }}
                  className="px-5 py-2.5 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all"
                >
                  Deploy Agent
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {agents.map((a) => (
                  <AgentCard
                    key={a.id}
                    agent={a}
                    onRun={openRun}
                    onToggle={toggleAgent}
                    onDelete={deleteAgent}
                    onViewLogs={loadExecutions}
                    onCopyWebhook={copyWebhook}
                    webhookBase={API}
                    expanded={expandedId === a.id}
                    onToggleExpand={(id) => setExpandedId(expandedId === id ? null : id)}
                  />
                ))}
              </div>
            )}

            {/* Execution log */}
            {executions.length > 0 && <ExecutionLog executions={executions} />}
          </div>
        )}

        {/* Purchased Tab */}
        {activeTab === "purchased" && (
          <div className="space-y-4">
            {purchased.length === 0 ? (
              <div className="text-center py-16 border border-dashed border-white/[0.08] rounded-2xl">
                <Package size={32} className="text-zinc-700 mx-auto mb-3" />
                <p className="text-[14px] text-zinc-500">No purchased agents yet</p>
                <p className="text-[12px] text-zinc-600 mt-1">Browse the marketplace to find agents for your needs.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {purchased.map((tx) => (
                  <div key={tx.id} className="bg-white/[0.03] border border-white/[0.07] rounded-xl p-4 sm:p-5 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-[#8B5CF6]/10 flex items-center justify-center shrink-0">
                      <Package size={16} className="text-[#8B5CF6]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-white truncate">{tx.agent_name}</p>
                      <p className="text-[11px] text-zinc-500 mt-0.5">{tx.plan === "rent" ? "Monthly Rental" : "Full Purchase"} — ${tx.amount}</p>
                    </div>
                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal */}
      {modalMode && (
        <AgentModal
          mode={modalMode}
          agent={modalAgent}
          templates={SAMPLE_AGENTS}
          onClose={() => { setModalMode(null); setModalAgent(null); }}
          onSubmit={modalMode === "run" ? runAgent : createAgent}
        />
      )}
    </div>
  );
}

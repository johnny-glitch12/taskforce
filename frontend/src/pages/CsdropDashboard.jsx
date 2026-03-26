import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  Play, Square, Terminal, Code, Zap, Shield, Clock,
  CheckCircle2, XCircle, Loader2, Plus, Trash2, Copy,
  RefreshCw, ChevronDown, ChevronUp, Send, Layers,
  Globe, ArrowUpRight, Activity, Bot, Wrench, Heart,
  AlertTriangle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Theme tokens ─── */
const T = {
  bg: "#0a0a1a",
  surface: "rgba(30, 27, 75, 0.4)",
  surfaceBorder: "rgba(99, 102, 241, 0.12)",
  surfaceHover: "rgba(99, 102, 241, 0.18)",
  accent: "#06b6d4",
  accentLight: "#22d3ee",
  accentGlow: "rgba(6, 182, 212, 0.25)",
  indigo: "#6366f1",
  indigoGlow: "rgba(99, 102, 241, 0.3)",
  text: "#e0e7ff",
  textMuted: "#94a3b8",
  textDim: "#475569",
};

/* ─── Stat Card ─── */
function Stat({ label, value, icon: Icon, accent = false }) {
  return (
    <div className="cs-card p-4 sm:p-5" data-testid={`cs-stat-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-[11px] tracking-widest uppercase" style={{ color: T.textDim }}>{label}</span>
        <Icon size={14} style={{ color: accent ? T.accent : T.indigo }} />
      </div>
      <p className="text-2xl font-bold" style={{ color: T.text, fontFamily: "'Outfit', sans-serif" }}>
        {value}
      </p>
    </div>
  );
}

/* ─── Code Editor ─── */
function CodeEditor({ value, onChange, readOnly = false }) {
  return (
    <div className="relative">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readOnly}
        data-testid="cs-code-editor"
        spellCheck={false}
        className="w-full h-52 sm:h-64 rounded-xl px-4 py-3 text-[12px] leading-relaxed font-mono focus:outline-none resize-none"
        style={{
          background: "rgba(6, 6, 26, 0.8)",
          border: `1px solid ${T.surfaceBorder}`,
          color: T.accentLight,
          caretColor: T.accent,
        }}
        placeholder="# Write your Python code here...&#10;# INPUT = webhook/trigger payload&#10;# RESULT = your return value&#10;&#10;data = INPUT&#10;RESULT = {'status': 'ok'}"
      />
      <div className="absolute bottom-2 right-3 flex items-center gap-2 text-[10px]" style={{ color: T.textDim }}>
        <Shield size={9} /> Sandboxed
      </div>
    </div>
  );
}

/* ─── Run Result Panel ─── */
function RunResult({ result }) {
  if (!result) return null;
  const ok = result.success;
  return (
    <div
      data-testid="cs-run-result"
      className="rounded-xl p-4 mt-4 space-y-3"
      style={{
        background: ok ? "rgba(6, 182, 212, 0.05)" : "rgba(239, 68, 68, 0.05)",
        border: `1px solid ${ok ? "rgba(6, 182, 212, 0.2)" : "rgba(239, 68, 68, 0.2)"}`,
      }}
    >
      <div className="flex items-center gap-2">
        {ok ? <CheckCircle2 size={14} style={{ color: T.accent }} /> : <XCircle size={14} className="text-red-400" />}
        <span className="text-[13px] font-medium" style={{ color: T.text }}>{ok ? "Success" : "Error"}</span>
        <span className="ml-auto text-[11px]" style={{ color: T.textDim }}>{result.duration_ms}ms</span>
      </div>
      {result.output && (
        <div>
          <p className="text-[10px] mb-1" style={{ color: T.textDim }}>Output:</p>
          <pre className="text-[11px] rounded-lg p-3 whitespace-pre-wrap max-h-24 overflow-y-auto font-mono" style={{ background: "rgba(0,0,0,0.3)", color: T.textMuted }}>{result.output}</pre>
        </div>
      )}
      {result.result != null && (
        <div>
          <p className="text-[10px] mb-1" style={{ color: T.textDim }}>RESULT:</p>
          <pre className="text-[11px] rounded-lg p-3 whitespace-pre-wrap max-h-24 overflow-y-auto font-mono" style={{ background: "rgba(0,0,0,0.3)", color: T.accentLight }}>{JSON.stringify(result.result, null, 2)}</pre>
        </div>
      )}
      {result.error && (
        <div>
          <p className="text-[10px] mb-1" style={{ color: T.textDim }}>Error:</p>
          <pre className="text-[11px] rounded-lg p-3 whitespace-pre-wrap max-h-24 overflow-y-auto font-mono" style={{ background: "rgba(0,0,0,0.3)", color: "#f87171" }}>{result.error}</pre>
        </div>
      )}
    </div>
  );
}

/* ─── System Health Panel ─── */
function SystemHealth({ health, onRepair, repairLogs, repairing }) {
  if (!health) return null;
  const { status, ready, python_path, repair_running } = health;
  const isRepairing = repairing || repair_running;

  return (
    <div className="cs-card overflow-hidden mb-4">
      <div className="px-5 py-3.5 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
        <div className="flex items-center gap-2.5">
          <Heart size={14} style={{ color: ready ? T.accent : "#f87171" }} />
          <span className="text-[13px] font-medium" style={{ color: T.text }}>System Health</span>
          <div
            data-testid="cs-health-indicator"
            className={`ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold ${ready ? "" : "animate-pulse"}`}
            style={{
              background: ready ? "rgba(6, 182, 212, 0.1)" : "rgba(239, 68, 68, 0.1)",
              color: ready ? T.accent : "#f87171",
              border: `1px solid ${ready ? "rgba(6,182,212,0.2)" : "rgba(239,68,68,0.2)"}`,
            }}
          >
            {ready ? "ALL SYSTEMS GO" : "NEEDS REPAIR"}
          </div>
        </div>
        {!ready && !isRepairing && (
          <button
            onClick={onRepair}
            data-testid="cs-repair-btn"
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[12px] font-medium transition-all"
            style={{
              background: "rgba(251, 146, 60, 0.1)",
              color: "#fb923c",
              border: "1px solid rgba(251, 146, 60, 0.25)",
            }}
          >
            <Wrench size={12} /> Repair Environment
          </button>
        )}
        {isRepairing && (
          <div className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[12px]" style={{ color: "#fb923c" }}>
            <Loader2 size={12} className="animate-spin" /> Repairing...
          </div>
        )}
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {Object.entries(status).map(([mod, state]) => (
            <div
              key={mod}
              data-testid={`cs-dep-${mod}`}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-mono"
              style={{
                background: state === "OK" ? "rgba(6,182,212,0.05)" : "rgba(239,68,68,0.05)",
                border: `1px solid ${state === "OK" ? "rgba(6,182,212,0.12)" : "rgba(239,68,68,0.15)"}`,
              }}
            >
              {state === "OK"
                ? <CheckCircle2 size={11} style={{ color: T.accent }} />
                : <XCircle size={11} className="text-red-400" />}
              <span style={{ color: state === "OK" ? T.textMuted : "#f87171" }}>{mod}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 text-[10px] font-mono" style={{ color: T.textDim }}>
          Python: {python_path || "detecting..."}
        </div>

        {/* Repair Logs */}
        {repairLogs.length > 0 && (
          <div className="mt-3">
            <div className="flex items-center gap-2 mb-1.5">
              <Terminal size={11} style={{ color: T.textDim }} />
              <span className="text-[10px]" style={{ color: T.textDim }}>Repair Log</span>
            </div>
            <div
              data-testid="cs-repair-logs"
              className="h-28 rounded-lg p-2.5 overflow-y-auto font-mono text-[10px] leading-relaxed"
              style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${T.surfaceBorder}` }}
            >
              {repairLogs.map((line, i) => (
                <div key={i} style={{ color: line.includes("error") || line.includes("Error") ? "#f87171" : line.includes("succeeded") || line.includes("success") || line.includes("Complete") ? T.accent : T.textMuted }}>
                  {line}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Bot Control Panel ─── */
function BotPanel({ headers, botRunning, setBotRunning, envReady }) {
  const [promo, setPromo] = useState("https://csdrop.com/r/ABBAS");
  const [batch, setBatch] = useState("10");
  const [logs, setLogs] = useState([]);
  const [launching, setLaunching] = useState(false);
  const logsRef = useRef(null);
  const pollRef = useRef(null);

  const pollLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/csdrop/bot-logs`, { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
        setBotRunning(data.running);
        if (!data.running) clearInterval(pollRef.current);
      }
    } catch {}
  }, [headers, setBotRunning]);

  useEffect(() => {
    if (botRunning) {
      pollRef.current = setInterval(pollLogs, 2000);
      return () => clearInterval(pollRef.current);
    }
  }, [botRunning, pollLogs]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  const handleLaunch = async () => {
    setLaunching(true);
    try {
      const res = await fetch(`${API}/api/csdrop/launch`, {
        method: "POST", headers,
        body: JSON.stringify({ promo, batch: parseInt(batch) || 10 }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Sovereign bot launched.");
        setBotRunning(true);
        pollLogs();
      } else {
        toast.error(data.message);
      }
    } catch { toast.error("Launch failed."); }
    setLaunching(false);
  };

  const handleStop = async () => {
    try {
      const res = await fetch(`${API}/api/csdrop/stop`, { method: "POST", headers });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Bot terminated.");
        setBotRunning(false);
        pollLogs();
      } else {
        toast.error(data.message);
      }
    } catch { toast.error("Stop failed."); }
  };

  return (
    <div className="cs-card overflow-hidden">
      <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
        <div className="flex items-center gap-2.5">
          <Bot size={15} style={{ color: T.accent }} />
          <span className="text-[13px] font-medium" style={{ color: T.text }}>Sovereign Bot</span>
          <div className={`w-2 h-2 rounded-full ${botRunning ? "bg-emerald-400 animate-pulse" : ""}`} style={{ background: botRunning ? undefined : T.textDim }} />
        </div>
        {botRunning ? (
          <button onClick={handleStop} data-testid="cs-stop-bot-btn" className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[12px] font-medium transition-all" style={{ background: "rgba(239, 68, 68, 0.1)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
            <Square size={12} /> Stop
          </button>
        ) : !envReady ? (
          <div className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[11px]" style={{ background: "rgba(239, 68, 68, 0.06)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.15)" }}>
            <AlertTriangle size={11} /> Env Not Ready
          </div>
        ) : (
          <button onClick={handleLaunch} disabled={launching} data-testid="cs-launch-bot-btn" className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[12px] font-medium transition-all disabled:opacity-50" style={{ background: T.accentGlow, color: T.accent, border: `1px solid rgba(6, 182, 212, 0.3)` }}>
            {launching ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />} Launch
          </button>
        )}
      </div>

      <div className="p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] mb-1.5 block" style={{ color: T.textDim }}>Promo Link</label>
            <input value={promo} onChange={(e) => setPromo(e.target.value)} data-testid="cs-promo-input" className="w-full rounded-lg px-3 py-2.5 text-[12px] font-mono focus:outline-none" style={{ background: "rgba(6, 6, 26, 0.6)", border: `1px solid ${T.surfaceBorder}`, color: T.text }} />
          </div>
          <div>
            <label className="text-[11px] mb-1.5 block" style={{ color: T.textDim }}>Batch Size</label>
            <input type="number" value={batch} onChange={(e) => setBatch(e.target.value)} data-testid="cs-batch-input" className="w-full rounded-lg px-3 py-2.5 text-[12px] font-mono focus:outline-none" style={{ background: "rgba(6, 6, 26, 0.6)", border: `1px solid ${T.surfaceBorder}`, color: T.text }} />
          </div>
        </div>

        {/* Bot Logs */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Terminal size={12} style={{ color: T.textDim }} />
            <span className="text-[11px]" style={{ color: T.textDim }}>Live Logs</span>
            <button onClick={pollLogs} className="ml-auto p-1 transition-colors" style={{ color: T.textDim }}><RefreshCw size={11} /></button>
          </div>
          <div ref={logsRef} data-testid="cs-bot-logs" className="h-40 rounded-xl p-3 overflow-y-auto font-mono text-[11px] leading-relaxed" style={{ background: "rgba(0, 0, 0, 0.4)", border: `1px solid ${T.surfaceBorder}` }}>
            {logs.length === 0 ? (
              <span style={{ color: T.textDim }}>No logs yet. Launch the bot to see output.</span>
            ) : (
              logs.map((line, i) => (
                <div key={i} style={{ color: line.includes("Error") || line.includes("error") ? "#f87171" : line.includes("Success") || line.includes("success") ? T.accent : T.textMuted }}>
                  {line}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Execution History ─── */
function ExecHistory({ executions }) {
  if (!executions.length) return null;
  return (
    <div className="cs-card overflow-hidden">
      <div className="px-5 py-3 flex items-center gap-2" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
        <Activity size={13} style={{ color: T.textDim }} />
        <span className="text-[12px]" style={{ color: T.textDim }}>Execution History</span>
      </div>
      <div className="max-h-60 overflow-y-auto divide-y" style={{ borderColor: T.surfaceBorder }}>
        {executions.map((ex) => (
          <div key={ex.id} className="px-4 py-2.5 flex items-center gap-3 text-[11px]" style={{ borderColor: `${T.surfaceBorder}` }}>
            {ex.success ? <CheckCircle2 size={11} style={{ color: T.accent }} /> : <XCircle size={11} className="text-red-400" />}
            <span className="truncate max-w-[200px] font-mono" style={{ color: T.textMuted }}>{ex.code?.slice(0, 50) || "agent run"}</span>
            <span style={{ color: T.textDim }}>{ex.duration_ms}ms</span>
            <span className="ml-auto" style={{ color: T.textDim }}>{new Date(ex.created_at).toLocaleTimeString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main CSDROP Dashboard ─── */
export default function CsdropDashboard() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [code, setCode] = useState(`# CSDROP Agent Code
import json

data = INPUT
print(f"Processing {len(data)} items...")

RESULT = {
    "status": "ok",
    "processed": True,
    "input_keys": list(data.keys()) if isinstance(data, dict) else [],
}
`);
  const [inputJson, setInputJson] = useState("{}");
  const [runResult, setRunResult] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [executions, setExecutions] = useState([]);
  const [botRunning, setBotRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("execute");
  const [health, setHealth] = useState(null);
  const [repairing, setRepairing] = useState(false);
  const [repairLogs, setRepairLogs] = useState([]);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // Verify access
  useEffect(() => {
    if (user && user.client_id !== "csdrop" && user.role !== "client") {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate]);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/csdrop/health`, { headers });
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
        if (data.repair_running) setRepairing(true);
        else setRepairing(false);
      }
    } catch {}
  }, [token]);

  // Poll repair status while repairing
  useEffect(() => {
    if (!repairing) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/admin/repair-status`, { headers });
        if (res.ok) {
          const data = await res.json();
          setRepairLogs(data.logs || []);
          if (!data.running) {
            setRepairing(false);
            fetchHealth();
          }
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [repairing]);

  const handleRepair = async () => {
    setRepairing(true);
    setRepairLogs(["Starting repair..."]);
    try {
      const res = await fetch(`${API}/api/admin/repair`, { method: "POST", headers });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Repair started in background.");
      } else if (data.status === "busy") {
        toast.info("Repair already in progress.");
      } else {
        toast.error("Failed to start repair.");
        setRepairing(false);
      }
    } catch {
      toast.error("Network error starting repair.");
      setRepairing(false);
    }
  };

  const fetchData = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([
        fetch(`${API}/api/csdrop/dashboard`, { headers }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/csdrop/executions`, { headers }).then((r) => r.ok ? r.json() : []),
      ]);
      if (s) { setStats(s); setBotRunning(s.bot_running); }
      setExecutions(Array.isArray(e) ? e : []);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) { fetchData(); fetchHealth(); } }, [token, fetchData, fetchHealth]);

  const handleExecute = async () => {
    let parsed;
    try { parsed = JSON.parse(inputJson); } catch { toast.error("Invalid JSON input."); return; }
    setExecuting(true);
    setRunResult(null);
    try {
      const res = await fetch(`${API}/api/csdrop/execute`, {
        method: "POST", headers,
        body: JSON.stringify({ code, input_data: parsed }),
      });
      if (res.ok) {
        const data = await res.json();
        setRunResult(data);
        fetchData();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Execution failed.");
      }
    } catch { toast.error("Network error."); }
    setExecuting(false);
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: T.bg }}>
      <Loader2 size={24} style={{ color: T.accent }} className="animate-spin" />
    </div>
  );

  return (
    <div data-testid="csdrop-dashboard" className="min-h-[calc(100vh-60px)]" style={{ background: T.bg }}>
      {/* Ambient glow */}
      <div className="fixed top-[-15%] right-[10%] w-[500px] h-[500px] rounded-full pointer-events-none" style={{ background: T.indigoGlow, filter: "blur(150px)" }} />
      <div className="fixed bottom-[-10%] left-[20%] w-[400px] h-[400px] rounded-full pointer-events-none" style={{ background: T.accentGlow, filter: "blur(120px)" }} />

      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: T.accentGlow, border: `1px solid rgba(6,182,212,0.3)` }}>
                <Layers size={16} style={{ color: T.accent }} />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: T.text, fontFamily: "'Outfit', sans-serif" }}>
                CSDROP <span style={{ color: T.accent }}>Portal</span>
              </h1>
            </div>
            <p className="text-[13px] mt-1" style={{ color: T.textDim }}>Private client execution environment</p>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[11px]" style={{ background: T.surface, border: `1px solid ${T.surfaceBorder}`, color: T.textMuted }}>
            <Shield size={11} style={{ color: T.accent }} />
            Client-Isolated Sandbox
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mb-8">
          <Stat label="Agents" value={stats?.agent_count || 0} icon={Code} accent />
          <Stat label="Total Runs" value={stats?.total_runs || 0} icon={Zap} />
          <Stat label="Bot Status" value={botRunning ? "LIVE" : "OFF"} icon={Activity} accent={botRunning} />
          <Stat label="Logs" value={stats?.bot_log_count || 0} icon={Terminal} />
          <Stat label="Env Health" value={health?.ready ? "OK" : "ISSUE"} icon={Heart} accent={health?.ready} />
        </div>

        {/* System Health */}
        <SystemHealth health={health} onRepair={handleRepair} repairLogs={repairLogs} repairing={repairing} />

        {/* Tabs */}
        <div className="flex items-center gap-1 mb-6 p-1 rounded-full w-fit" style={{ background: T.surface, border: `1px solid ${T.surfaceBorder}` }}>
          {[
            { id: "execute", label: "Code Runner", icon: Code },
            { id: "bot", label: "Sovereign Bot", icon: Bot },
            { id: "history", label: "History", icon: Activity },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-testid={`cs-tab-${t.id}`}
              className="flex items-center gap-1.5 px-4 py-2 text-[12px] rounded-full transition-all"
              style={{
                background: activeTab === t.id ? T.accent : "transparent",
                color: activeTab === t.id ? "#0a0a1a" : T.textMuted,
                fontWeight: activeTab === t.id ? 600 : 400,
              }}
            >
              <t.icon size={12} /> <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>

        {/* Code Runner Tab */}
        {activeTab === "execute" && (
          <div className="space-y-4">
            <div className="cs-card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Code size={14} style={{ color: T.accent }} />
                  <span className="text-[13px] font-medium" style={{ color: T.text }}>Execution Panel</span>
                </div>
                <span className="text-[10px] px-2.5 py-1 rounded-full" style={{ background: T.accentGlow, color: T.accent, border: `1px solid rgba(6,182,212,0.2)` }}>
                  30s timeout • Sandboxed
                </span>
              </div>

              <CodeEditor value={code} onChange={setCode} />

              <div>
                <label className="text-[11px] mb-1.5 block" style={{ color: T.textDim }}>Input Payload (JSON)</label>
                <textarea
                  value={inputJson}
                  onChange={(e) => setInputJson(e.target.value)}
                  data-testid="cs-input-json"
                  className="w-full h-20 rounded-xl px-4 py-3 text-[12px] font-mono focus:outline-none resize-none"
                  style={{ background: "rgba(6, 6, 26, 0.6)", border: `1px solid ${T.surfaceBorder}`, color: T.textMuted, caretColor: T.accent }}
                  placeholder='{"key": "value"}'
                />
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  data-testid="cs-execute-btn"
                  className="flex items-center gap-2 px-6 py-2.5 rounded-full text-[13px] font-semibold transition-all disabled:opacity-50"
                  style={{
                    background: `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
                    color: "#0a0a1a",
                    boxShadow: `0 0 20px ${T.accentGlow}`,
                  }}
                >
                  {executing ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  {executing ? "Running..." : "Execute"}
                </button>
                <button
                  onClick={() => { setCode(""); setRunResult(null); }}
                  className="px-4 py-2.5 rounded-full text-[12px] transition-all"
                  style={{ background: T.surface, border: `1px solid ${T.surfaceBorder}`, color: T.textMuted }}
                >
                  Clear
                </button>
              </div>

              <RunResult result={runResult} />
            </div>
          </div>
        )}

        {/* Sovereign Bot Tab */}
        {activeTab === "bot" && (
          <BotPanel headers={headers} botRunning={botRunning} setBotRunning={setBotRunning} envReady={health?.ready || false} />
        )}

        {/* History Tab */}
        {activeTab === "history" && (
          <ExecHistory executions={executions} />
        )}
      </div>

      {/* Scoped styles */}
      <style>{`
        [data-testid="csdrop-dashboard"] .cs-card {
          background: ${T.surface};
          border: 1px solid ${T.surfaceBorder};
          border-radius: 16px;
          backdrop-filter: blur(12px);
        }
        [data-testid="csdrop-dashboard"] .cs-card:hover {
          border-color: ${T.surfaceHover};
        }
        [data-testid="csdrop-dashboard"] ::selection {
          background: ${T.accent};
          color: ${T.bg};
        }
      `}</style>
    </div>
  );
}

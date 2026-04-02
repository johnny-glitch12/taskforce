import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  Play, Square, Terminal, Code, Zap, Shield, Clock,
  CheckCircle2, XCircle, Loader2, Plus, Trash2, Copy,
  RefreshCw, ChevronDown, ChevronUp, Send, Layers,
  Globe, ArrowUpRight, Activity, Bot, Wrench, Heart,
  AlertTriangle, Monitor, Satellite, QrCode, X, Key,
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

/* ─── Live Satellite Feed ─── */
function LiveFeed({ botRunning }) {
  const [feedUrl, setFeedUrl] = useState(null);
  const [feedAvailable, setFeedAvailable] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const imgRef = useRef(null);

  useEffect(() => {
    if (!botRunning) {
      setFeedAvailable(false);
      return;
    }
    // Refresh image every 5 seconds by busting the cache
    const interval = setInterval(() => {
      const ts = Date.now();
      setFeedUrl(`${API}/api/csdrop/live-feed/image?t=${ts}`);
      setFeedAvailable(true);
      setLastUpdated(new Date().toLocaleTimeString());
    }, 5000);
    // Immediately set a first frame
    setFeedUrl(`${API}/api/csdrop/live-feed/image?t=${Date.now()}`);
    setFeedAvailable(true);
    setLastUpdated(new Date().toLocaleTimeString());
    return () => clearInterval(interval);
  }, [botRunning]);

  return (
    <div
      data-testid="cs-live-feed"
      className="rounded-2xl overflow-hidden"
      style={{
        background: "rgba(0, 0, 0, 0.5)",
        border: `1px solid ${botRunning ? "rgba(99, 102, 241, 0.3)" : T.surfaceBorder}`,
      }}
    >
      <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
        <div className="flex items-center gap-2">
          <Satellite size={13} style={{ color: botRunning ? T.indigo : T.textDim }} />
          <span className="text-[11px] uppercase tracking-widest font-bold" style={{ color: botRunning ? T.indigo : T.textDim }}>
            Live Satellite Feed
          </span>
          {botRunning && (
            <div className="flex items-center gap-1 ml-2">
              <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-[9px] font-mono text-red-400">REC</span>
            </div>
          )}
        </div>
        {lastUpdated && (
          <span className="text-[9px] font-mono" style={{ color: T.textDim }}>
            Last frame: {lastUpdated}
          </span>
        )}
      </div>
      <div className="relative" style={{ minHeight: 200 }}>
        {feedAvailable && feedUrl ? (
          <img
            ref={imgRef}
            src={feedUrl}
            alt="Live Bot View"
            data-testid="cs-live-feed-img"
            className="w-full object-contain transition-opacity"
            style={{ opacity: botRunning ? 0.9 : 0.4, maxHeight: 440 }}
            onError={() => setFeedAvailable(false)}
            onLoad={() => setFeedAvailable(true)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Monitor size={28} style={{ color: T.textDim }} />
            <p className="text-[12px]" style={{ color: T.textDim }}>
              {botRunning ? "Waiting for first frame..." : "Feed activates when the bot is running"}
            </p>
          </div>
        )}
        {/* Scanline overlay for style */}
        {botRunning && feedAvailable && (
          <div className="absolute inset-0 pointer-events-none" style={{
            background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(99, 102, 241, 0.03) 2px, rgba(99, 102, 241, 0.03) 4px)",
          }} />
        )}
      </div>
    </div>
  );
}

/* ─── QR Session Sync Modal ─── */
function SyncSessionModal({ open, onClose, headers }) {
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState("idle"); // idle, syncing, success, timeout
  const [qrUrl, setQrUrl] = useState(null);
  const [logs, setLogs] = useState([]);
  const [countdown, setCountdown] = useState(120);
  const pollRef = useRef(null);
  const countdownRef = useRef(null);
  const logsEndRef = useRef(null);

  const startSync = async () => {
    setSyncing(true);
    setSyncStatus("syncing");
    setLogs(["Starting session sync..."]);
    setCountdown(120);
    try {
      const res = await fetch(`${API}/api/csdrop/sync-session`, { method: "POST", headers });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Scan the QR code with Discord mobile app.");
      } else {
        toast.error(data.message);
        setSyncing(false);
        setSyncStatus("idle");
      }
    } catch {
      toast.error("Failed to start sync.");
      setSyncing(false);
      setSyncStatus("idle");
    }
  };

  const stopSync = async () => {
    try {
      await fetch(`${API}/api/csdrop/sync-stop`, { method: "POST", headers });
      toast.info("Sync cancelled.");
    } catch {}
    setSyncing(false);
    setSyncStatus("idle");
    setQrUrl(null);
  };

  // Poll sync status + QR image
  useEffect(() => {
    if (!syncing || !open) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/csdrop/sync-status`, { headers });
        if (res.ok) {
          const data = await res.json();
          setLogs(data.logs || []);
          if (data.qr_available) {
            setQrUrl(`${API}/api/csdrop/sync-qr?t=${Date.now()}`);
          }
          if (data.status === "success") {
            setSyncing(false);
            setSyncStatus("success");
            toast.success("Session Secured! Discord login successful.");
            clearInterval(pollRef.current);
          } else if (data.status === "timeout") {
            setSyncing(false);
            setSyncStatus("timeout");
            toast.error("Timed out. No scan detected.");
            clearInterval(pollRef.current);
          } else if (data.status !== "syncing") {
            setSyncing(false);
            clearInterval(pollRef.current);
          }
        }
      } catch {}
    }, 2000);
    return () => clearInterval(pollRef.current);
  }, [syncing, open]);

  // Countdown timer
  useEffect(() => {
    if (!syncing) return;
    countdownRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(countdownRef.current); return 0; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(countdownRef.current);
  }, [syncing]);

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollTop = logsEndRef.current.scrollHeight;
  }, [logs]);

  // Clean up on close
  const handleClose = () => {
    if (syncing) stopSync();
    setSyncStatus("idle");
    setQrUrl(null);
    setLogs([]);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)" }}>
      <div
        data-testid="cs-sync-modal"
        className="relative w-full max-w-md mx-4 rounded-2xl overflow-hidden"
        style={{ background: T.bg, border: `1px solid ${T.surfaceBorder}` }}
      >
        {/* Header */}
        <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
          <div className="flex items-center gap-2.5">
            <QrCode size={16} style={{ color: T.indigo }} />
            <span className="text-[14px] font-semibold" style={{ color: T.text }}>Discord Session Sync</span>
          </div>
          <button onClick={handleClose} className="p-1.5 rounded-lg transition-colors" style={{ color: T.textDim }}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* QR Code Display */}
          <div className="rounded-xl overflow-hidden" style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${syncing ? "rgba(99,102,241,0.3)" : T.surfaceBorder}` }}>
            {syncing && qrUrl ? (
              <div className="relative">
                <img
                  src={qrUrl}
                  alt="Discord QR Code"
                  data-testid="cs-qr-image"
                  className="w-full object-contain"
                  style={{ maxHeight: 340 }}
                  onError={(e) => { e.target.style.display = "none"; }}
                />
                {/* Scanline overlay */}
                <div className="absolute inset-0 pointer-events-none" style={{
                  background: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(99,102,241,0.04) 3px, rgba(99,102,241,0.04) 6px)",
                }} />
                {/* REC + Countdown */}
                <div className="absolute top-3 left-3 flex items-center gap-2">
                  <div className="flex items-center gap-1 px-2 py-0.5 rounded-full" style={{ background: "rgba(0,0,0,0.6)" }}>
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-[9px] font-mono text-red-400">LIVE</span>
                  </div>
                </div>
                <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full text-[10px] font-mono" style={{ background: "rgba(0,0,0,0.6)", color: countdown < 30 ? "#f87171" : T.textMuted }}>
                  {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, "0")}
                </div>
              </div>
            ) : syncing && !qrUrl ? (
              /* Loading spinner while browser is launching and navigating */
              <div className="flex flex-col items-center justify-center py-14 gap-4">
                <div className="relative w-16 h-16">
                  <div className="absolute inset-0 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: T.indigo, borderRightColor: T.accent }} />
                  <div className="absolute inset-2 rounded-full border-2 border-transparent animate-spin" style={{ borderBottomColor: T.indigo, animationDirection: "reverse", animationDuration: "1.5s" }} />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Globe size={18} style={{ color: T.indigo }} />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-[13px] font-medium" style={{ color: T.text }}>Launching Browser...</p>
                  <p className="text-[10px] mt-1" style={{ color: T.textDim }}>Navigating to Discord — QR code will appear shortly</p>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono" style={{ background: "rgba(99,102,241,0.08)", color: T.indigo, border: "1px solid rgba(99,102,241,0.15)" }}>
                  <Loader2 size={10} className="animate-spin" />
                  {countdown > 110 ? "Starting Chromium..." : countdown > 100 ? "Loading Discord..." : "Rendering QR code..."}
                </div>
              </div>
            ) : syncStatus === "success" ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)" }}>
                  <CheckCircle2 size={28} style={{ color: T.accent }} />
                </div>
                <p className="text-[14px] font-semibold" style={{ color: T.accent }}>Session Secured</p>
                <p className="text-[11px]" style={{ color: T.textDim }}>Discord session saved. The bot is ready to go.</p>
              </div>
            ) : syncStatus === "timeout" ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  <Clock size={28} className="text-red-400" />
                </div>
                <p className="text-[14px] font-semibold text-red-400">Timed Out</p>
                <p className="text-[11px]" style={{ color: T.textDim }}>No scan detected within 2 minutes. Try again.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <QrCode size={36} style={{ color: T.textDim }} />
                <p className="text-[12px] text-center" style={{ color: T.textDim }}>
                  Click "Start Sync" to generate a Discord QR code.<br />
                  Scan it with your Discord mobile app to link the session.
                </p>
              </div>
            )}
          </div>

          {/* Sync Logs */}
          {logs.length > 0 && (
            <div ref={logsEndRef} className="h-20 rounded-lg p-2.5 overflow-y-auto font-mono text-[10px] leading-relaxed" style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${T.surfaceBorder}` }}>
              {logs.map((line, i) => (
                <div key={i} style={{ color: line.includes("SUCCESS") ? T.accent : line.includes("TIMEOUT") || line.includes("Failed") ? "#f87171" : T.textMuted }}>
                  {line}
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3">
            {syncStatus === "idle" || syncStatus === "timeout" ? (
              <button
                onClick={startSync}
                data-testid="cs-start-sync-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-semibold transition-all"
                style={{ background: `linear-gradient(135deg, ${T.indigo}, ${T.accent})`, color: "#0a0a1a" }}
              >
                <QrCode size={14} /> Start Sync
              </button>
            ) : syncing ? (
              <button
                onClick={stopSync}
                data-testid="cs-cancel-sync-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-medium transition-all"
                style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <Square size={12} /> Cancel Sync
              </button>
            ) : (
              <button
                onClick={handleClose}
                data-testid="cs-close-sync-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-medium transition-all"
                style={{ background: T.accentGlow, color: T.accent, border: `1px solid rgba(6,182,212,0.3)` }}
              >
                <CheckCircle2 size={12} /> Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Bot Control Panel ─── */
function BotPanel({ headers, botRunning, setBotRunning, envReady, onOpenSync }) {
  const [promo, setPromo] = useState("https://csdrop.com/r/ABBAS");
  const [batch, setBatch] = useState("10");
  const [logs, setLogs] = useState([]);
  const [launching, setLaunching] = useState(false);
  const logsRef = useRef(null);
  const pollRef = useRef(null);

  const pollLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/csdrop/logs?lines=80`, { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
        setBotRunning(data.running);
        if (!data.running && logs.length > 0) clearInterval(pollRef.current);
      }
    } catch {}
  }, [headers, setBotRunning]);

  useEffect(() => {
    if (botRunning) {
      pollRef.current = setInterval(pollLogs, 1500);
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
        <div className="flex items-center gap-2">
          <button onClick={onOpenSync} data-testid="cs-sync-session-btn" className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all" style={{ background: "rgba(99,102,241,0.08)", color: T.indigo, border: "1px solid rgba(99,102,241,0.2)" }}>
            <Key size={11} /> Sync Session
          </button>
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

        {/* Bot Logs — Real-Time Terminal */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Terminal size={12} style={{ color: T.accent }} />
            <span className="text-[11px] font-semibold tracking-wide" style={{ color: T.accent }}>LIVE TERMINAL</span>
            {botRunning && (
              <div className="flex items-center gap-1 ml-1">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[9px] font-mono text-emerald-400">STREAMING</span>
              </div>
            )}
            <button onClick={pollLogs} className="ml-auto p-1 transition-colors" style={{ color: T.textDim }}><RefreshCw size={11} /></button>
          </div>
          <div
            ref={logsRef}
            data-testid="cs-bot-logs"
            className="h-56 rounded-xl p-3.5 overflow-y-auto font-mono text-[11px] leading-[1.7]"
            style={{
              background: "#0a0a0f",
              border: `1px solid ${botRunning ? "rgba(6,182,212,0.2)" : T.surfaceBorder}`,
              boxShadow: botRunning ? "inset 0 0 30px rgba(6,182,212,0.03)" : "none",
            }}
          >
            {logs.length === 0 ? (
              <div className="flex items-center gap-2 h-full justify-center" style={{ color: T.textDim }}>
                <Terminal size={14} />
                <span>No logs yet. Launch the bot to see output.</span>
              </div>
            ) : (
              logs.map((line, i) => {
                const lower = line.toLowerCase();
                let color = "#8b9dc3"; // default: muted blue-grey
                let bg = "transparent";
                let fontWeight = "normal";

                // Error / Fatal / Critical — red
                if (lower.includes("error") || lower.includes("fatal") || lower.includes("critical") || lower.includes("banned") || lower.includes("failed") || lower.includes("timeout")) {
                  color = "#f87171"; bg = "rgba(239,68,68,0.06)";
                }
                // Success / Sent / Saved — green
                else if (lower.includes("sent") || lower.includes("success") || lower.includes("saved") || lower.includes("secured") || lower.includes("complete")) {
                  color = "#34d399"; bg = "rgba(52,211,153,0.06)";
                }
                // Bot phase headers — cyan bold
                else if (lower.includes("phase") || lower.includes("cycle") || lower.includes("initialized") || lower.includes("===")) {
                  color = T.accent; fontWeight = "bold";
                }
                // Debug / Boot — dim
                else if (lower.includes("[debug]") || lower.includes("[boot]")) {
                  color = "#6b7280";
                }
                // Hook / Strike / Hammer — indigo
                else if (lower.includes("hook") || lower.includes("strike") || lower.includes("hammer") || lower.includes("pending targets")) {
                  color = "#818cf8";
                }
                // Warning — amber
                else if (lower.includes("warning") || lower.includes("[!]") || lower.includes("refuel")) {
                  color = "#fbbf24"; bg = "rgba(251,191,36,0.04)";
                }
                // System / Screenshot — dim cyan
                else if (lower.includes("[system]") || lower.includes("screenshot")) {
                  color = "#64748b";
                }

                return (
                  <div
                    key={i}
                    className="px-1.5 rounded-sm"
                    style={{ color, background: bg, fontWeight }}
                  >
                    {line}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Live Satellite Feed */}
        <LiveFeed botRunning={botRunning} />
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
  const [syncModalOpen, setSyncModalOpen] = useState(false);

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
          <BotPanel headers={headers} botRunning={botRunning} setBotRunning={setBotRunning} envReady={health?.ready || false} onOpenSync={() => setSyncModalOpen(true)} />
        )}

        {/* Session Sync Modal */}
        <SyncSessionModal open={syncModalOpen} onClose={() => setSyncModalOpen(false)} headers={headers} />

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

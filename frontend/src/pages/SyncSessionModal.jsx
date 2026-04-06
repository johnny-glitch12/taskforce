import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import {
  QrCode, X, CheckCircle2, Clock, Loader2, Globe,
  Monitor, Square, Key, Shield, Eye, EyeOff, Lock,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Theme tokens (mirrored from CsdropDashboard) ─── */
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

const POLL_INTERVAL = 2000; // 2s for sync-status polling

/* ─── Tab Button ─── */
function TabBtn({ active, icon: Icon, label, onClick, testId }) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-medium transition-all"
      style={{
        background: active ? T.indigo : "transparent",
        color: active ? "#fff" : T.textDim,
        border: `1px solid ${active ? T.indigo : T.surfaceBorder}`,
      }}
    >
      <Icon size={12} />
      {label}
    </button>
  );
}

/* ─── Sync Logs Panel (shared) ─── */
function SyncLogs({ logs }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  if (!logs.length) return null;
  return (
    <div
      ref={ref}
      data-testid="cs-sync-logs"
      className="h-20 rounded-lg p-2.5 overflow-y-auto font-mono text-[10px] leading-relaxed"
      style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${T.surfaceBorder}` }}
    >
      {logs.map((line, i) => (
        <div key={i} style={{
          color: line.includes("SUCCESS") ? T.accent
            : line.includes("TIMEOUT") || line.includes("Failed") || line.includes("LOGIN FAILED") ? "#f87171"
            : line.includes("2FA") ? "#fbbf24"
            : T.textMuted,
        }}>
          {line}
        </div>
      ))}
    </div>
  );
}

/* ─── Result Screen (success / timeout / login_failed) ─── */
function ResultScreen({ status }) {
  if (status === "success") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)" }}>
          <CheckCircle2 size={28} style={{ color: T.accent }} />
        </div>
        <p className="text-[14px] font-semibold" style={{ color: T.accent }}>Session Secured</p>
        <p className="text-[11px]" style={{ color: T.textDim }}>Discord session saved. The bot is ready to go.</p>
      </div>
    );
  }
  if (status === "timeout") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
          <Clock size={28} className="text-red-400" />
        </div>
        <p className="text-[14px] font-semibold text-red-400">Timed Out</p>
        <p className="text-[11px]" style={{ color: T.textDim }}>No response within the time limit. Try again.</p>
      </div>
    );
  }
  if (status === "login_failed") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
          <Shield size={28} className="text-red-400" />
        </div>
        <p className="text-[14px] font-semibold text-red-400">Login Failed</p>
        <p className="text-[11px]" style={{ color: T.textDim }}>Discord rejected the credentials. Check email/password and try again.</p>
      </div>
    );
  }
  return null;
}

export default function SyncSessionModal({ open, onClose, headers }) {
  const [mode, setMode] = useState("qr"); // "qr" | "manual"
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState("idle"); // idle, syncing, 2fa_required, success, timeout, login_failed
  const [qrUrl, setQrUrl] = useState(null);
  const [logs, setLogs] = useState([]);
  const [countdown, setCountdown] = useState(120);

  // Manual login fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [twoFaCode, setTwoFaCode] = useState("");
  const [submitting2fa, setSubmitting2fa] = useState(false);

  const pollRef = useRef(null);
  const countdownRef = useRef(null);

  /* ── Shared: Poll sync-status ── */
  useEffect(() => {
    if (!syncing || !open) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/csdrop/sync-status`, { headers });
        if (!res.ok) return;
        const data = await res.json();
        setLogs(data.logs || []);

        if (mode === "qr" && data.qr_available) {
          setQrUrl(`${API}/api/csdrop/sync-qr?t=${Date.now()}`);
        }

        if (data.status === "success") {
          setSyncing(false);
          setSyncStatus("success");
          toast.success("Session Secured! Discord login successful.");
          clearInterval(pollRef.current);
          setTimeout(() => onClose(), 2000);
        } else if (data.status === "timeout") {
          setSyncing(false);
          setSyncStatus("timeout");
          toast.error("Timed out. No response detected.");
          clearInterval(pollRef.current);
        } else if (data.status === "login_failed") {
          setSyncing(false);
          setSyncStatus("login_failed");
          toast.error("Login failed. Check your credentials.");
          clearInterval(pollRef.current);
        } else if (data.status === "2fa_required") {
          setSyncStatus("2fa_required");
        } else if (data.status !== "syncing") {
          setSyncing(false);
          clearInterval(pollRef.current);
        }
      } catch {}
    }, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [syncing, open, mode]);

  /* ── Countdown timer ── */
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

  /* ── QR: Start ── */
  const startQrSync = async () => {
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

  /* ── Manual: Start ── */
  const startManualLogin = async () => {
    if (!email.trim() || !password.trim()) {
      toast.error("Email and password are required.");
      return;
    }
    setSyncing(true);
    setSyncStatus("syncing");
    setLogs(["Starting manual login..."]);
    setCountdown(120);
    setTwoFaCode("");
    try {
      const res = await fetch(`${API}/api/csdrop/manual-login`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Logging in... Bot is entering credentials.");
      } else {
        toast.error(data.message);
        setSyncing(false);
        setSyncStatus("idle");
      }
    } catch {
      toast.error("Failed to start manual login.");
      setSyncing(false);
      setSyncStatus("idle");
    }
  };

  /* ── 2FA: Submit code ── */
  const submit2fa = async () => {
    const code = twoFaCode.trim();
    if (!code || code.length < 4) {
      toast.error("Enter a valid verification code.");
      return;
    }
    setSubmitting2fa(true);
    try {
      const res = await fetch(`${API}/api/csdrop/submit-2fa`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        toast.success("Code submitted. Verifying...");
        setSyncStatus("syncing"); // go back to syncing while bot processes the code
      } else {
        toast.error(data.message);
      }
    } catch {
      toast.error("Failed to submit 2FA code.");
    }
    setSubmitting2fa(false);
  };

  /* ── Shared: Stop sync ── */
  const stopSync = async () => {
    try {
      await fetch(`${API}/api/csdrop/sync-stop`, { method: "POST", headers });
    } catch {}
    setSyncing(false);
    setSyncStatus("idle");
    setQrUrl(null);
  };

  const cancelSync = async () => {
    await stopSync();
    toast.info("Sync cancelled.");
  };

  const killSyncProcess = async () => {
    try {
      await fetch(`${API}/api/csdrop/sync-stop`, { method: "POST", headers });
    } catch {}
  };

  /* ── Close handler ── */
  const handleClose = () => {
    if (syncing) {
      cancelSync();
    } else {
      killSyncProcess();
    }
    setSyncStatus("idle");
    setQrUrl(null);
    setLogs([]);
    setTwoFaCode("");
    onClose();
  };

  /* ── Tab switch (only when idle) ── */
  const switchMode = (m) => {
    if (syncing) return; // can't switch while active
    setMode(m);
    setSyncStatus("idle");
    setLogs([]);
    setQrUrl(null);
  };

  if (!open) return null;

  const isTerminal = ["success", "timeout", "login_failed"].includes(syncStatus);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)" }}>
      <div
        data-testid="cs-sync-modal"
        className="relative w-full max-w-2xl mx-4 rounded-2xl overflow-hidden"
        style={{ background: T.bg, border: `1px solid ${T.surfaceBorder}` }}
      >
        {/* ── Header ── */}
        <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: `1px solid ${T.surfaceBorder}` }}>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <QrCode size={16} style={{ color: T.indigo }} />
              <span className="text-[14px] font-semibold" style={{ color: T.text }}>Discord Session Sync</span>
            </div>
            {/* Tab switcher */}
            <div className="flex items-center gap-1.5 ml-2">
              <TabBtn
                active={mode === "qr"}
                icon={QrCode}
                label="QR Code"
                onClick={() => switchMode("qr")}
                testId="cs-sync-tab-qr"
              />
              <TabBtn
                active={mode === "manual"}
                icon={Key}
                label="Manual Login"
                onClick={() => switchMode("manual")}
                testId="cs-sync-tab-manual"
              />
            </div>
          </div>
          <button onClick={handleClose} data-testid="cs-sync-close-btn" className="p-1.5 rounded-lg transition-colors" style={{ color: T.textDim }}>
            <X size={16} />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="p-5 space-y-4">

          {/* ────── QR MODE ────── */}
          {mode === "qr" && (
            <div className="rounded-xl overflow-hidden" style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${syncing ? "rgba(99,102,241,0.3)" : T.surfaceBorder}` }}>
              {syncing && qrUrl ? (
                <div className="relative">
                  <img
                    src={qrUrl}
                    alt="Discord QR Code"
                    data-testid="cs-qr-image"
                    className="w-full object-contain"
                    style={{ maxHeight: 480 }}
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                  <div className="absolute inset-0 pointer-events-none" style={{
                    background: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(99,102,241,0.04) 3px, rgba(99,102,241,0.04) 6px)",
                  }} />
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
              ) : isTerminal ? (
                <ResultScreen status={syncStatus} />
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
          )}

          {/* ────── MANUAL MODE ────── */}
          {mode === "manual" && (
            <div className="rounded-xl overflow-hidden" style={{ background: "rgba(0,0,0,0.4)", border: `1px solid ${syncing ? "rgba(99,102,241,0.3)" : T.surfaceBorder}` }}>

              {/* Terminal results (success / timeout / login_failed) */}
              {isTerminal ? (
                <ResultScreen status={syncStatus} />

              /* 2FA Challenge */
              ) : syncStatus === "2fa_required" ? (
                <div className="flex flex-col items-center justify-center py-10 gap-4 px-6">
                  <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.25)" }}>
                    <Lock size={24} style={{ color: "#fbbf24" }} />
                  </div>
                  <div className="text-center">
                    <p className="text-[14px] font-semibold" style={{ color: "#fbbf24" }}>Verification Required</p>
                    <p className="text-[11px] mt-1" style={{ color: T.textDim }}>
                      Discord is asking for a 2FA / verification code.<br />
                      Check your authenticator app or email.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 w-full max-w-xs">
                    <input
                      data-testid="cs-2fa-input"
                      type="text"
                      inputMode="numeric"
                      maxLength={8}
                      value={twoFaCode}
                      onChange={(e) => setTwoFaCode(e.target.value.replace(/[^0-9]/g, ""))}
                      onKeyDown={(e) => e.key === "Enter" && submit2fa()}
                      placeholder="Enter code"
                      className="flex-1 rounded-lg px-3 py-2.5 text-center text-[16px] font-mono tracking-[0.3em] focus:outline-none"
                      style={{
                        background: "rgba(0,0,0,0.5)",
                        border: `1px solid rgba(251,191,36,0.3)`,
                        color: T.text,
                        caretColor: "#fbbf24",
                      }}
                      autoFocus
                    />
                    <button
                      data-testid="cs-submit-2fa-btn"
                      onClick={submit2fa}
                      disabled={submitting2fa || twoFaCode.length < 4}
                      className="px-4 py-2.5 rounded-lg text-[12px] font-semibold transition-all disabled:opacity-40"
                      style={{ background: "#fbbf24", color: "#0a0a1a" }}
                    >
                      {submitting2fa ? <Loader2 size={14} className="animate-spin" /> : "Submit"}
                    </button>
                  </div>
                  {/* Countdown */}
                  <div className="text-[10px] font-mono" style={{ color: countdown < 30 ? "#f87171" : T.textDim }}>
                    {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, "0")} remaining
                  </div>
                </div>

              /* Syncing (logging in, waiting) */
              ) : syncing ? (
                <div className="flex flex-col items-center justify-center py-14 gap-4">
                  <div className="relative w-16 h-16">
                    <div className="absolute inset-0 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: T.indigo, borderRightColor: T.accent }} />
                    <div className="absolute inset-2 rounded-full border-2 border-transparent animate-spin" style={{ borderBottomColor: T.indigo, animationDirection: "reverse", animationDuration: "1.5s" }} />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Key size={18} style={{ color: T.indigo }} />
                    </div>
                  </div>
                  <div className="text-center">
                    <p className="text-[13px] font-medium" style={{ color: T.text }}>Logging In...</p>
                    <p className="text-[10px] mt-1" style={{ color: T.textDim }}>Bot is entering your credentials into Discord</p>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono" style={{ background: "rgba(99,102,241,0.08)", color: T.indigo, border: "1px solid rgba(99,102,241,0.15)" }}>
                    <Loader2 size={10} className="animate-spin" />
                    {countdown > 110 ? "Starting Chromium..." : countdown > 100 ? "Opening Discord..." : "Entering credentials..."}
                  </div>
                </div>

              /* Idle — Email/Password form */
              ) : (
                <div className="p-5 space-y-4">
                  <div className="text-center mb-2">
                    <p className="text-[12px]" style={{ color: T.textDim }}>
                      Enter your Discord credentials. The bot will type them into a headless browser.
                    </p>
                    <p className="text-[10px] mt-1" style={{ color: T.textDim }}>
                      Credentials are used once and never stored.
                    </p>
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider uppercase" style={{ color: T.textDim }}>Discord Email</label>
                    <input
                      data-testid="cs-manual-email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="w-full rounded-lg px-3 py-2.5 text-[13px] focus:outline-none"
                      style={{
                        background: "rgba(0,0,0,0.5)",
                        border: `1px solid ${T.surfaceBorder}`,
                        color: T.text,
                        caretColor: T.accent,
                      }}
                    />
                  </div>

                  {/* Password */}
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider uppercase" style={{ color: T.textDim }}>Discord Password</label>
                    <div className="relative">
                      <input
                        data-testid="cs-manual-password"
                        type={showPass ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && startManualLogin()}
                        placeholder="Your password"
                        className="w-full rounded-lg px-3 py-2.5 pr-10 text-[13px] focus:outline-none"
                        style={{
                          background: "rgba(0,0,0,0.5)",
                          border: `1px solid ${T.surfaceBorder}`,
                          color: T.text,
                          caretColor: T.accent,
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPass(!showPass)}
                        data-testid="cs-toggle-password"
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded"
                        style={{ color: T.textDim }}
                      >
                        {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>

                  {/* Security note */}
                  <div className="flex items-start gap-2 p-2.5 rounded-lg" style={{ background: "rgba(99,102,241,0.06)", border: `1px solid rgba(99,102,241,0.1)` }}>
                    <Shield size={12} className="mt-0.5 flex-shrink-0" style={{ color: T.indigo }} />
                    <p className="text-[10px] leading-relaxed" style={{ color: T.textDim }}>
                      Your credentials are sent directly to the bot process and deleted immediately after use. They are never written to any database.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Sync Logs (shared) ── */}
          <SyncLogs logs={logs} />

          {/* ── Actions ── */}
          <div className="flex items-center gap-3">
            {syncStatus === "idle" || syncStatus === "timeout" || syncStatus === "login_failed" ? (
              <button
                onClick={mode === "qr" ? startQrSync : startManualLogin}
                data-testid="cs-start-sync-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-semibold transition-all"
                style={{ background: `linear-gradient(135deg, ${T.indigo}, ${T.accent})`, color: "#0a0a1a" }}
              >
                {mode === "qr" ? <QrCode size={14} /> : <Key size={14} />}
                {mode === "qr" ? "Start Sync" : "Start Login"}
              </button>
            ) : syncing || syncStatus === "2fa_required" ? (
              <button
                onClick={cancelSync}
                data-testid="cs-cancel-sync-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-medium transition-all"
                style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <Square size={12} /> Cancel
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

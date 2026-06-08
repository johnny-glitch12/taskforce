/**
 * UsernameField — input with live availability check.
 *
 * Calls GET /api/auth/check-username?username=... debounced 500ms via
 * AbortController so rapid typing doesn't pile up in-flight requests.
 *
 * Reports status via the `onStatus` callback so the parent form can gate the
 * submit button on `{ available: true }`.
 */
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const USERNAME_RE = /^[a-zA-Z][a-zA-Z0-9_]{2,19}$/;
const DEBOUNCE_MS = 500;

const REASON_LABEL = {
  too_short: "Too short (min 3 characters)",
  reserved: "That username is reserved",
  invalid: "Letters, numbers, underscores only — must start with a letter",
  taken: "Username taken",
  ok: "Available",
};

export default function UsernameField({ value, onChange, onStatus }) {
  // status: "idle" | "invalid" | "checking" | "ok" | "taken" | "reserved" | "too_short"
  const [status, setStatus] = useState("idle");
  const abortRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    const v = (value || "").trim();
    // Local fast-fail rules first — skip the network call if obviously invalid.
    if (!v) {
      setStatus("idle");
      onStatus?.({ available: false, reason: "idle" });
      return;
    }
    if (v.length < 3) {
      setStatus("too_short");
      onStatus?.({ available: false, reason: "too_short" });
      return;
    }
    if (!USERNAME_RE.test(v)) {
      setStatus("invalid");
      onStatus?.({ available: false, reason: "invalid" });
      return;
    }

    // Debounce the network call.
    clearTimeout(timerRef.current);
    abortRef.current?.abort?.();
    setStatus("checking");
    timerRef.current = setTimeout(() => {
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      fetch(`${API}/api/auth/check-username?username=${encodeURIComponent(v)}`, { signal: ctrl.signal })
        .then((r) => r.json())
        .then((d) => {
          const reason = d.reason || (d.available ? "ok" : "taken");
          setStatus(reason);
          onStatus?.({ available: !!d.available, reason });
        })
        .catch((e) => {
          if (e?.name === "AbortError") return;
          setStatus("idle");
          onStatus?.({ available: false, reason: "network" });
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timerRef.current);
      abortRef.current?.abort?.();
    };
  }, [value, onStatus]);

  const isOk = status === "ok";
  const isBad = ["taken", "reserved", "invalid", "too_short"].includes(status);
  const isChecking = status === "checking";

  return (
    <div className="relative">
      <input
        id="s-username"
        data-testid="signup-username-input"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, 20))}
        placeholder="your_username"
        autoCapitalize="off"
        autoComplete="username"
        className="w-full px-4 py-3 bg-zinc-900/50 rounded-sm focus:outline-none focus:ring-2 focus:ring-cyan-400/30 t-text font-mono text-[14px]"
        style={{ border: `1px solid ${isOk ? "rgba(52,211,153,0.5)" : isBad ? "rgba(244,63,94,0.5)" : "var(--input-border)"}` }}
        required
        maxLength={20}
        minLength={3}
      />
      {/* Right-side icon — checkmark / cross / spinner */}
      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
        {isChecking && <Loader2 size={14} className="animate-spin text-zinc-500" />}
        {isOk && <CheckCircle2 size={14} className="text-emerald-400" />}
        {isBad && <XCircle size={14} className="text-rose-400" />}
      </div>
      {/* Status line */}
      {status !== "idle" && (
        <p
          data-testid="signup-username-status"
          data-status={status}
          className={`text-[10px] font-mono mt-1.5 tracking-wide ${
            isOk ? "text-emerald-400" : isBad ? "text-rose-400" : "text-zinc-500"
          }`}
        >
          {isChecking ? "Checking availability…" : REASON_LABEL[status] || ""}
        </p>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Brain, X } from "lucide-react";
import { Link } from "react-router-dom";

const STORAGE_KEY = "taskforce_memory_notice_seen";

/**
 * One-shot notice modal that informs the user about the Builder Memory
 * system the first time they land on /armory after the system shipped.
 *
 * Stores `taskforce_memory_notice_seen=1` in localStorage on dismissal so
 * it never reappears. Caller should mount this anywhere inside the /armory
 * route — the modal self-gates on localStorage.
 */
export default function MemoryFirstTimeNotice() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const seen = window.localStorage.getItem(STORAGE_KEY);
      if (!seen) setOpen(true);
    } catch {
      /* localStorage blocked — don't show the modal, keep things quiet */
    }
  }, []);

  if (!open) return null;

  const dismiss = () => {
    try { window.localStorage.setItem(STORAGE_KEY, "1"); } catch { /* no-op */ }
    setOpen(false);
  };

  return (
    <div
      data-testid="memory-first-time-notice"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={dismiss}
    >
      <div
        className="w-full max-w-md rounded-sm p-5"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-sm flex items-center justify-center" style={{ background: "rgba(34,211,238,0.1)" }}>
            <Brain size={14} className="text-cyan-400" />
          </div>
          <span className="text-[12px] tracking-widest uppercase t-text">Now Learning From You</span>
          <button onClick={dismiss} className="ml-auto t-text-mute hover:t-text" aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <p className="text-[12px] t-text leading-relaxed mb-3">
          Your Builder AI now learns from your conversations to give better results over time.
        </p>
        <p className="text-[11px] t-text-dim leading-relaxed mb-4">
          You can view and manage what it remembers at any time in{" "}
          <Link
            to="/settings/memory"
            onClick={dismiss}
            className="text-cyan-400 hover:text-cyan-300 underline-offset-2 hover:underline"
          >
            Settings → Builder Memory
          </Link>
          .
        </p>
        <div className="flex items-center justify-end">
          <button
            data-testid="memory-notice-dismiss-btn"
            onClick={dismiss}
            className="px-4 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300"
          >
            GOT IT
          </button>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Zap, ArrowRight, X, Shield, Cpu } from "lucide-react";

/**
 * Parses a 403 response and returns compute limit data if it's a COMPUTE_LIMIT_REACHED error.
 * Returns null if it's a different kind of 403.
 */
export function parseComputeLimit(status, data) {
  if (!data) return null;
  // Check for compute limit in response body (returned as 200 with error flag)
  if (data.error === "COMPUTE_LIMIT_REACHED" && data.allowed === false) return data;
  // Also check nested detail for backwards compat
  const detail = data?.detail;
  if (detail && typeof detail === "object" && detail.error === "COMPUTE_LIMIT_REACHED") return detail;
  return null;
}

/**
 * Full-screen tactical modal shown when compute credits are exhausted.
 */
export function ComputeLimitModal({ limitData, onClose }) {
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(null);

  if (!limitData) return null;

  const pct = Math.min(100, (limitData.used / limitData.limit) * 100);
  const tierLabel = (limitData.tier || "recruit").toUpperCase();

  const handleUpgrade = () => {
    onClose();
    navigate("/pricing");
  };

  return (
    <AnimatePresence>
      <motion.div
        key="compute-limit-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center p-4"
        data-testid="compute-limit-modal"
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="relative w-full max-w-md rounded-sm overflow-hidden"
          style={{ background: "#0a0a0c", border: "1px solid #1a1a1e" }}
        >
          {/* Top warning bar — pulsing red */}
          <motion.div
            className="h-1 w-full"
            style={{ background: "linear-gradient(90deg, #ef4444, #f59e0b, #ef4444)" }}
            animate={{ backgroundPosition: ["0% 50%", "200% 50%"] }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          />

          {/* Close button */}
          <button
            onClick={onClose}
            data-testid="close-compute-modal"
            className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center text-zinc-600 hover:text-zinc-300 transition-colors rounded-sm"
            style={{ border: "1px solid #27272a" }}
          >
            <X size={14} />
          </button>

          {/* Content */}
          <div className="px-6 pt-8 pb-6">
            {/* Icon */}
            <div className="flex items-center justify-center mb-6">
              <motion.div
                animate={{ boxShadow: ["0 0 20px rgba(239,68,68,0.15)", "0 0 40px rgba(239,68,68,0.3)", "0 0 20px rgba(239,68,68,0.15)"] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="w-16 h-16 rounded-sm flex items-center justify-center"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <AlertTriangle size={28} className="text-red-400" />
              </motion.div>
            </div>

            {/* Title */}
            <h2
              data-testid="compute-limit-title"
              className="text-center text-lg font-bold text-zinc-100 mb-2 font-mono tracking-wide uppercase"
            >
              Compute Limit Reached
            </h2>

            <p className="text-center text-[13px] text-zinc-500 mb-6 leading-relaxed">
              Your <span className="text-red-400 font-mono font-bold">{tierLabel}</span> plan has used all allocated executions this month.
            </p>

            {/* Usage meter */}
            <div className="rounded-sm p-4 mb-6" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid #1a1a1e" }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono tracking-[0.15em] uppercase text-zinc-500">
                  <Cpu size={10} className="inline mr-1" /> Monthly Usage
                </span>
                <span className="text-[12px] font-mono font-bold text-red-400">
                  {limitData.used.toLocaleString()} / {limitData.limit.toLocaleString()}
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-2 rounded-none overflow-hidden" style={{ background: "#1a1a1e" }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className="h-full"
                  style={{
                    background: pct >= 100
                      ? "linear-gradient(90deg, #ef4444, #dc2626)"
                      : pct >= 80
                      ? "linear-gradient(90deg, #f59e0b, #d97706)"
                      : "linear-gradient(90deg, #22d3ee, #06b6d4)",
                  }}
                />
              </div>
              <p className="text-[10px] font-mono text-zinc-600 mt-2">
                Resets on the 1st of next month
              </p>
            </div>

            {/* Upgrade tiers */}
            <div className="space-y-2 mb-6">
              {[
                { tier: "CADET", price: "$19", execs: "500", color: "#22d3ee" },
                { tier: "OPERATOR", price: "$99", execs: "2,000", color: "#10b981", recommended: true },
              ].map((t) => (
                <motion.div
                  key={t.tier}
                  whileHover={{ borderColor: t.color + "40" }}
                  className="flex items-center gap-3 p-3 rounded-sm cursor-pointer transition-all"
                  style={{
                    background: t.recommended ? "rgba(16,185,129,0.04)" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${t.recommended ? "rgba(16,185,129,0.15)" : "#1a1a1e"}`,
                  }}
                  onClick={handleUpgrade}
                >
                  <div className="w-8 h-8 rounded-sm flex items-center justify-center shrink-0" style={{ background: t.color + "12" }}>
                    {t.recommended ? <Zap size={14} style={{ color: t.color }} /> : <Shield size={14} style={{ color: t.color }} />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-mono font-bold text-zinc-200 tracking-wide">{t.tier}</span>
                      {t.recommended && (
                        <span className="text-[8px] font-mono font-bold tracking-[0.15em] px-1.5 py-0.5 rounded-sm" style={{ background: t.color + "15", color: t.color }}>
                          RECOMMENDED
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] font-mono text-zinc-500">{t.execs} executions/mo</span>
                  </div>
                  <span className="text-[14px] font-mono font-bold text-zinc-300">{t.price}<span className="text-[10px] text-zinc-600">/mo</span></span>
                </motion.div>
              ))}
            </div>

            {/* CTA */}
            <motion.button
              onClick={handleUpgrade}
              data-testid="upgrade-cta-btn"
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3.5 bg-cyan-400 text-black text-[13px] font-bold tracking-[0.1em] uppercase font-mono rounded-sm flex items-center justify-center gap-2 transition-all"
              style={{ boxShadow: "0 0 25px rgba(34,211,238,0.2)" }}
            >
              <Zap size={14} /> Upgrade Now <ArrowRight size={14} />
            </motion.button>

            <button
              onClick={onClose}
              className="w-full mt-3 py-2 text-[11px] font-mono tracking-wide uppercase text-zinc-600 hover:text-zinc-400 transition-colors text-center"
            >
              Continue on {tierLabel} plan
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

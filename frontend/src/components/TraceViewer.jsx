import { useEffect, useRef } from "react";
import { X, Check, AlertCircle, Loader2, Play, Clock, Terminal } from "lucide-react";

/**
 * TraceViewer — Bottom slide-up panel showing topological step-by-step
 * execution trace from POST /api/workflows/{id}/execute response.
 */
export default function TraceViewer({ open, onClose, trace, executing }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [trace]);

  if (!open) return null;

  const results = trace?.node_results || [];
  const allOk = trace && trace.success;

  return (
    <div
      data-testid="trace-viewer"
      className="absolute bottom-0 left-0 right-0 flex flex-col z-30"
      style={{
        height: 280,
        background: 'var(--bg-card)',
        borderTop: '2px solid var(--border)',
        boxShadow: '0 -8px 24px rgba(0,0,0,0.4)',
      }}
    >
      {/* Header */}
      <div className="px-4 py-2.5 flex items-center gap-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <Terminal size={13} className="text-cyan-400" />
        <span className="text-[12px] tracking-wide t-text-sub uppercase">Execution Trace</span>

        {executing && (
          <span className="flex items-center gap-1.5 text-[10px] text-cyan-300 bg-cyan-400/10 px-2 py-0.5 rounded-sm border border-cyan-400/20">
            <Loader2 size={9} className="animate-spin" /> Running...
          </span>
        )}

        {!executing && trace && (
          <span className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-sm border ${
            allOk
              ? "text-emerald-400 bg-emerald-500/5 border-emerald-500/20"
              : "text-red-400 bg-red-500/5 border-red-500/20"
          }`}>
            {allOk ? <Check size={10} /> : <AlertCircle size={10} />}
            {allOk ? "Success" : "Failed"}
          </span>
        )}

        {!executing && trace && (
          <>
            <span className="text-[10px] t-text-dim flex items-center gap-1">
              <Clock size={9} /> {trace.duration_ms}ms
            </span>
            <span className="text-[10px] t-text-dim">{results.length} node{results.length !== 1 ? "s" : ""}</span>
          </>
        )}

        <button
          data-testid="close-trace-btn"
          onClick={onClose}
          className="ml-auto p-1 rounded-sm hover:bg-[var(--bg-card-hover)]"
        >
          <X size={13} className="t-text-mute" />
        </button>
      </div>

      {/* Trace list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 font-mono text-[11px] leading-relaxed">
        {!trace && !executing && (
          <div className="text-center py-6 t-text-dim text-[11px]">
            Click <Play size={10} className="inline" /> EXECUTE to run the workflow.
          </div>
        )}

        {executing && (
          <div className="text-cyan-400 text-[11px]">
            <span className="animate-pulse">▸</span> Dispatching workflow to native execution engine...
          </div>
        )}

        {results.map((r, i) => (
          <div
            key={i}
            data-testid={`trace-step-${i}`}
            className="flex items-start gap-2 py-1"
          >
            <span className="t-text-dim w-6 shrink-0">{String(i + 1).padStart(2, "0")}</span>
            <StatusBadge status={r.status} />
            <span className="t-text-sub uppercase tracking-wider text-[10px] w-24 shrink-0">{r.type}</span>
            <span className="t-text flex-1 min-w-0 truncate">
              {r.label && <span className="text-cyan-400">[{r.label}] </span>}
              {r.log || "(no log)"}
              {r.branch && <span className="ml-2 text-amber-400">→ branch:{r.branch}</span>}
            </span>
            <span className="t-text-dim text-[10px] shrink-0">{r.duration_ms}ms</span>
          </div>
        ))}

        {trace?.final_output !== undefined && trace.final_output !== null && (
          <div className="mt-3 pt-2" style={{ borderTop: '1px dashed var(--border)' }}>
            <div className="text-[10px] tracking-widest uppercase t-text-dim mb-1">Final Output</div>
            <pre className="text-[10px] p-2 rounded-sm overflow-x-auto" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
              {JSON.stringify(trace.final_output, null, 2)}
            </pre>
          </div>
        )}

        {trace?.error && (
          <div className="mt-3 text-[11px] text-red-400 p-2 rounded-sm" style={{ background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.2)' }}>
            {trace.error}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === "ok") return <Check size={11} className="text-emerald-400 shrink-0 mt-0.5" />;
  if (status === "error") return <AlertCircle size={11} className="text-red-400 shrink-0 mt-0.5" />;
  if (status === "skipped") return <span className="text-amber-400 text-[10px] shrink-0 mt-0.5">●</span>;
  return <Loader2 size={11} className="text-cyan-400 animate-spin shrink-0 mt-0.5" />;
}

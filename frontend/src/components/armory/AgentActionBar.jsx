/* eslint-disable react/prop-types */
/**
 * AgentActionBar — Sticky bottom of the AgentPreview panel.
 * Test Run · Deploy · Publish to Exchange · Export
 */
import { Zap, Rocket, Upload, Download, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

export default function AgentActionBar({
  project, onTestRun, onDeploy, onPublish, onExport, testRunResult, busyAction,
}) {
  const disabled = !project;
  const trustScore = project?.trust_score;
  return (
    <div className="shrink-0 px-3 py-3" style={{ borderTop: "1px solid var(--armory-border)", background: "var(--armory-panel)" }}>
      {/* Trust score line */}
      {trustScore != null && (
        <div className="flex items-center gap-1.5 px-2 py-1.5 mb-2 rounded-sm" style={{ background: "var(--armory-card)", border: "1px solid var(--armory-border)" }}>
          <CheckCircle2 size={11} style={{ color: trustScore >= 80 ? "var(--armory-success)" : "var(--armory-text-mute)" }} />
          <span className="text-[10px] font-mono uppercase tracking-[0.15em]" style={{ color: "var(--armory-text-mute)" }}>
            Trust Score
          </span>
          <span className="text-[11px] font-mono ml-auto" style={{ color: "var(--armory-text)" }}>
            {trustScore} {trustScore >= 80 && <span style={{ color: "var(--armory-success)" }}>Certified ✓</span>}
          </span>
        </div>
      )}

      {/* Test run result inline */}
      {testRunResult && (
        <div
          data-testid="armory-test-run-result"
          className="px-2 py-1.5 mb-2 rounded-sm text-[10.5px] font-mono leading-relaxed"
          style={{
            background: testRunResult.success ? "var(--armory-success-bg)" : "var(--armory-error-bg)",
            color: testRunResult.success ? "var(--armory-success)" : "var(--armory-error)",
            borderLeft: `2px solid ${testRunResult.success ? "var(--armory-success)" : "var(--armory-error)"}`,
          }}
        >
          {testRunResult.success ? (
            <>
              <CheckCircle2 size={10} className="inline -mt-0.5 mr-1" />
              <span>Run OK · {testRunResult.duration_ms}ms</span>
              {testRunResult.output && (
                <div className="mt-1 opacity-80 break-all" style={{ color: "var(--armory-text-mute)" }}>
                  {String(testRunResult.output).slice(0, 280)}
                </div>
              )}
            </>
          ) : (
            <>
              <AlertCircle size={10} className="inline -mt-0.5 mr-1" />
              <span>Run failed</span>
              {testRunResult.error && (
                <div className="mt-1 opacity-80 break-all" style={{ color: "var(--armory-text-mute)" }}>
                  {String(testRunResult.error).slice(0, 280)}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <ActionBtn
          testid="armory-action-test"
          label="Test Run"
          Icon={Zap}
          accent="#f59e0b"
          onClick={onTestRun}
          disabled={disabled || busyAction === "test"}
          busy={busyAction === "test"}
        />
        <ActionBtn
          testid="armory-action-deploy"
          label="Deploy"
          Icon={Rocket}
          accent="var(--armory-accent)"
          onClick={onDeploy}
          disabled={disabled || busyAction === "deploy"}
          busy={busyAction === "deploy"}
          primary
        />
        <ActionBtn
          testid="armory-action-publish"
          label="Publish"
          Icon={Upload}
          accent="#a855f7"
          onClick={onPublish}
          disabled={disabled || busyAction === "publish"}
          busy={busyAction === "publish"}
        />
        <ActionBtn
          testid="armory-action-export"
          label="Export"
          Icon={Download}
          accent="var(--armory-text-mute)"
          onClick={onExport}
          disabled={disabled || busyAction === "export"}
          busy={busyAction === "export"}
        />
      </div>
    </div>
  );
}

function ActionBtn({ testid, label, Icon, accent, onClick, disabled, busy, primary }) {
  return (
    <button
      data-testid={testid}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
      style={{
        background: primary && !disabled ? accent : "transparent",
        color: primary && !disabled ? "#0a0a0a" : (disabled ? "var(--armory-text-dim)" : "var(--armory-text)"),
        border: primary ? "none" : `1px solid ${disabled ? "var(--armory-border)" : accent}`,
        fontWeight: primary ? 600 : 500,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {busy ? <Loader2 size={10} className="animate-spin" /> : <Icon size={10} />}
      {label}
    </button>
  );
}

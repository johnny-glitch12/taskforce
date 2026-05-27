import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  Settings, X, Save, Brain, Globe, Filter,
  Code, Zap, Database as DbIcon, FileText, Mail,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * NodeConfigPanel — Right-side panel that lets the user configure
 * the selected canvas node's data fields (url/code/condition/prompt/etc).
 * Persists updates via PATCH /api/workflows/{wfId}/nodes/{nodeId}
 * AND mutates the in-memory canvas state via onUpdate.
 */
const TYPE_META = {
  trigger:      { icon: Mail,    color: "#22d3ee", title: "Trigger" },
  llm:          { icon: Brain,   color: "#06b6d4", title: "LLM" },
  condition:    { icon: Filter,  color: "#0891b2", title: "Condition" },
  action:       { icon: FileText, color: "#0e7490", title: "Action (v1 stub)" },
  http_request: { icon: Globe,   color: "#5B21B6", title: "HTTP Request" },
  webhook:      { icon: Zap,     color: "#C084FC", title: "Webhook" },
  database:     { icon: DbIcon,  color: "#4C1D95", title: "Database (v1 stub)" },
  transform:    { icon: Code,    color: "#9333EA", title: "Transform" },
};

export default function NodeConfigPanel({ node, onUpdate, onClose, runtimeWorkflowId, token }) {
  const [data, setData] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setData(node?.data || {});
  }, [node?.id]);

  if (!node) return null;
  const meta = TYPE_META[node.type] || TYPE_META.action;
  const Icon = meta.icon;

  const updateField = (key, value) => {
    setData((prev) => ({ ...prev, [key]: value }));
  };

  const persist = async () => {
    setSaving(true);
    // Always mutate local canvas state first
    onUpdate?.(node.id, data);

    // Persist to backend if we have a runtime workflow id
    if (runtimeWorkflowId && token) {
      try {
        const res = await fetch(`${API}/api/workflows/${runtimeWorkflowId}/nodes/${node.id}`, {
          method: "PATCH",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ data }),
        });
        if (!res.ok) toast.error("Saved locally — backend sync failed.");
        else toast.success("Node updated.");
      } catch {
        toast.error("Saved locally — backend sync failed.");
      }
    } else {
      toast.success("Node updated (local). Save the workflow to persist.");
    }
    setSaving(false);
  };

  return (
    <div
      data-testid="node-config-panel"
      className="flex flex-col h-full shrink-0"
      style={{
        width: 320,
        borderLeft: '1px solid var(--border)',
        background: 'var(--bg-card)',
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="w-7 h-7 rounded-sm flex items-center justify-center" style={{ background: `${meta.color}15` }}>
          <Icon size={13} style={{ color: meta.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] tracking-widest uppercase t-text-dim">{meta.title}</div>
          <div className="text-[12px] t-text font-medium truncate">{node.sub || node.label}</div>
        </div>
        <button data-testid="close-config-panel" onClick={onClose} className="p-1 rounded-sm hover:bg-[var(--bg-card-hover)]">
          <X size={12} className="t-text-mute" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        <FieldsForType type={node.type} data={data} onChange={updateField} />

        {/* Raw JSON (for advanced/unsupported fields) */}
        <details className="text-[10px]">
          <summary className="cursor-pointer t-text-dim tracking-widest uppercase">Raw JSON</summary>
          <pre className="mt-2 p-2 rounded-sm text-[10px] overflow-x-auto" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </details>
      </div>

      {/* Footer */}
      <div className="px-3 py-2 shrink-0 flex items-center gap-2" style={{ borderTop: '1px solid var(--border)' }}>
        <button
          data-testid="save-node-config-btn"
          onClick={persist}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50"
        >
          <Save size={11} /> {saving ? "Saving..." : "APPLY"}
        </button>
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────── */
function FieldsForType({ type, data, onChange }) {
  if (type === "http_request") {
    return (
      <>
        <Field label="URL" testid="config-url">
          <input
            type="text"
            value={data.url || ""}
            onChange={(e) => onChange("url", e.target.value)}
            placeholder="https://api.example.com/endpoint"
            className="config-input"
          />
        </Field>
        <Field label="Method" testid="config-method">
          <select
            value={data.method || "GET"}
            onChange={(e) => onChange("method", e.target.value)}
            className="config-input"
          >
            {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Headers (JSON)" testid="config-headers">
          <textarea
            value={typeof data.headers === "string" ? data.headers : JSON.stringify(data.headers || {}, null, 2)}
            onChange={(e) => {
              try { onChange("headers", JSON.parse(e.target.value)); }
              catch { onChange("headers", e.target.value); }
            }}
            rows={3}
            className="config-input font-mono text-[10px]"
            placeholder='{"Authorization": "Bearer ..."}'
          />
        </Field>
      </>
    );
  }

  if (type === "llm") {
    return (
      <>
        <Field label="Prompt" testid="config-prompt">
          <textarea
            value={data.prompt || ""}
            onChange={(e) => onChange("prompt", e.target.value)}
            rows={5}
            placeholder="Analyze the input and produce a structured JSON summary."
            className="config-input"
          />
        </Field>
        <Field label="Temperature" testid="config-temperature">
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={data.temperature ?? 0.3}
            onChange={(e) => onChange("temperature", parseFloat(e.target.value))}
            className="config-input"
          />
        </Field>
        <div className="text-[10px] t-text-dim p-2 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
          Engine: Gemini 2.5 Flash (platform-managed, no BYOK in v1)
        </div>
      </>
    );
  }

  if (type === "condition") {
    return (
      <Field label="Condition expression" testid="config-condition">
        <input
          type="text"
          value={data.condition || ""}
          onChange={(e) => onChange("condition", e.target.value)}
          placeholder="INPUT.get('score', 0) > 50"
          className="config-input font-mono"
        />
        <p className="mt-1 text-[10px] t-text-dim">
          Safe Python expression. Available: <code className="text-cyan-400">INPUT</code> (previous node's output).
        </p>
      </Field>
    );
  }

  if (type === "transform") {
    return (
      <Field label="Python Code (sandboxed)" testid="config-code">
        <textarea
          value={data.code || "RESULT = INPUT"}
          onChange={(e) => onChange("code", e.target.value)}
          rows={10}
          className="config-input font-mono text-[10px]"
          placeholder="RESULT = {'doubled': INPUT.get('value', 0) * 2}"
        />
        <p className="mt-1 text-[10px] t-text-dim">
          Set <code className="text-cyan-400">RESULT</code> to your output. 30s timeout. No file/network/process access.
        </p>
      </Field>
    );
  }

  if (type === "webhook") {
    return (
      <>
        <Field label="Outbound URL (leave blank for inbound)" testid="config-webhook-url">
          <input
            type="text"
            value={data.url || ""}
            onChange={(e) => onChange("url", e.target.value)}
            placeholder="https://hooks.zapier.com/..."
            className="config-input"
          />
        </Field>
        <Field label="Method" testid="config-webhook-method">
          <select
            value={data.method || "POST"}
            onChange={(e) => onChange("method", e.target.value)}
            className="config-input"
          >
            {["POST", "PUT"].map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
      </>
    );
  }

  if (type === "trigger") {
    return (
      <Field label="Source" testid="config-source">
        <select
          value={data.source || "manual"}
          onChange={(e) => onChange("source", e.target.value)}
          className="config-input"
        >
          {["manual", "schedule", "webhook", "email", "crm"].map((s) => <option key={s}>{s}</option>)}
        </select>
      </Field>
    );
  }

  // action / database / unknown
  return (
    <div className="text-[11px] t-text-dim p-3 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
      <p className="font-medium text-amber-400 mb-1">v1 Stub Node</p>
      <p>This node type is logged but not executed in v1. Coming soon: BYOK action handlers.</p>
    </div>
  );
}

function Field({ label, testid, children }) {
  return (
    <div data-testid={testid}>
      <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">{label}</label>
      {children}
    </div>
  );
}

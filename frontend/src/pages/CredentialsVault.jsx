import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Key, Trash2, Plus, Shield, X, Zap, CheckCircle2, AlertCircle, Loader2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const SERVICES = [
  { id: "slack",     label: "Slack",       hint: "Incoming Webhook URL — https://hooks.slack.com/services/..." },
  { id: "sendgrid",  label: "SendGrid",    hint: "SG.xxxxxxxxxx... (also set extra.from_email)" },
  { id: "gmail",     label: "Gmail",       hint: "OAuth access token (use /api/workflows/credentials/gmail/exchange for full OAuth)" },
  { id: "telegram",  label: "Telegram",    hint: "Bot token (123456:ABC-...). Optional extra={default_chat_id}" },
  { id: "discord",   label: "Discord",     hint: "Webhook URL — https://discord.com/api/webhooks/{id}/{token}" },
  { id: "stripe",    label: "Stripe",      hint: "sk_test_... or sk_live_... secret key" },
  { id: "notion",    label: "Notion",      hint: "Integration secret — secret_..." },
  { id: "gsheets",   label: "Google Sheets", hint: "OAuth access token with sheets.googleapis.com scope" },
  { id: "twilio",    label: "Twilio SMS",  hint: "Auth Token. REQUIRED extra={account_sid, from_number}" },
  { id: "github",    label: "GitHub",      hint: "Personal access token (ghp_...) with repo + write:issues scope" },
  { id: "openai",    label: "OpenAI",      hint: "sk-... API key" },
  { id: "anthropic", label: "Anthropic",   hint: "sk-ant-... API key (Claude)" },
  { id: "instagram", label: "Instagram",   hint: "Long-lived access token. REQUIRED extra={ig_user_id}" },
  { id: "postgres",  label: "Postgres",    hint: "DSN: postgres://user:pass@host:5432/db" },
  { id: "mongodb",   label: "MongoDB",     hint: "Connection URI: mongodb+srv://user:pass@cluster/" },
];

const SERVICE_LABEL = Object.fromEntries(SERVICES.map((s) => [s.id, s.label]));

export default function CredentialsVault() {
  const { token } = useAuth();
  const [creds, setCreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ service: "slack", api_key: "", extra: "{}" });
  const [testing, setTesting] = useState(null); // service slug currently being probed

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/workflows/credentials`, { headers });
      const data = await res.json();
      setCreds(data.credentials || []);
    } catch {
      toast.error("Failed to load credentials.");
    }
    setLoading(false);
  };

  useEffect(() => { if (token) load(); }, [token]);

  const save = async () => {
    let extra = {};
    try { extra = JSON.parse(form.extra || "{}"); }
    catch { toast.error("Invalid JSON in extra."); return; }
    try {
      const res = await fetch(`${API}/api/workflows/credentials`, {
        method: "POST", headers,
        body: JSON.stringify({ service: form.service, api_key: form.api_key, extra }),
      });
      if (res.ok) {
        toast.success("Credential saved.");
        setOpen(null);
        setForm({ service: "slack", api_key: "", extra: "{}" });
        load();
      } else {
        const e = await res.json();
        const msg = Array.isArray(e.detail) ? e.detail[0]?.msg : (e.detail || "Save failed.");
        toast.error(msg);
      }
    } catch { toast.error("Save failed."); }
  };

  const del = async (service) => {
    if (!confirm(`Delete ${service} credential?`)) return;
    try {
      const res = await fetch(`${API}/api/workflows/credentials/${service}`, { method: "DELETE", headers });
      if (res.ok) { toast.success("Deleted."); load(); }
    } catch { toast.error("Delete failed."); }
  };

  const testConnection = async (service) => {
    setTesting(service);
    try {
      const res = await fetch(`${API}/api/workflows/credentials/${service}/test`, {
        method: "POST", headers,
      });
      const data = await res.json();
      if (data.ok) {
        toast.success(`${SERVICE_LABEL[service] || service} OK · ${data.detail} (${data.latency_ms}ms)`);
      } else {
        toast.error(`${SERVICE_LABEL[service] || service} FAILED · ${data.detail || `HTTP ${data.status_code}`}`);
      }
      // Refresh to surface last_probe badge
      load();
    } catch {
      toast.error("Probe request failed.");
    }
    setTesting(null);
  };

  const renderProbeBadge = (last) => {
    if (!last) {
      return (
        <span className="text-[9px] tracking-widest uppercase t-text-dim px-1.5 py-0.5 rounded-sm" style={{ border: '1px solid var(--border)' }}>
          UNTESTED
        </span>
      );
    }
    const ok = last.ok;
    return (
      <span
        title={`${last.detail || ''} · ${last.latency_ms}ms · ${last.checked_at?.slice(0,16).replace('T',' ')}`}
        className="flex items-center gap-1 text-[9px] tracking-widest uppercase px-1.5 py-0.5 rounded-sm font-mono"
        style={{
          background: ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${ok ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          color: ok ? '#34d399' : '#f87171',
        }}
      >
        {ok ? <CheckCircle2 size={9} /> : <AlertCircle size={9} />}
        {ok ? "LIVE" : "DEAD"}
      </span>
    );
  };

  return (
    <div data-testid="credentials-vault" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-sm flex items-center justify-center" style={{ background: 'rgba(34,211,238,0.1)' }}>
            <Shield size={18} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl tracking-wide t-text" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: '0.05em' }}>
              CREDENTIAL VAULT
            </h1>
            <p className="text-[12px] t-text-dim uppercase tracking-widest">Bring Your Own Keys · Encrypted Storage · 15 Services</p>
          </div>
        </div>
        <div className="text-[11px] t-text-dim mb-6 max-w-2xl">
          Store API keys for Slack / SendGrid / Gmail / Telegram / Discord / Stripe / Notion / Sheets / Twilio / GitHub /
          OpenAI / Claude / Instagram / Postgres / MongoDB to power action nodes in your workflows. Keys are stored
          masked and never returned in plain text after save. Click <Zap size={10} className="inline text-cyan-400 -mt-0.5" /> TEST
          on any row to fire a 1-call sanity probe.
        </div>

        <button
          data-testid="add-credential-btn"
          onClick={() => setOpen("new")}
          className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 mb-6"
        >
          <Plus size={13} /> ADD CREDENTIAL
        </button>

        {loading && <div className="t-text-dim text-[12px]">Loading...</div>}
        {!loading && creds.length === 0 && (
          <div className="t-text-dim text-[12px] p-6 rounded-sm text-center" style={{ background: 'var(--bg-card)', border: '1px dashed var(--border)' }}>
            No credentials yet. Add keys to unlock action nodes in The Armory.
          </div>
        )}
        <div className="space-y-2">
          {creds.map((c) => (
            <div
              key={c.service}
              data-testid={`credential-row-${c.service}`}
              className="flex items-center gap-3 p-3 rounded-sm"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
              <div className="w-9 h-9 rounded-sm flex items-center justify-center" style={{ background: 'rgba(34,211,238,0.08)' }}>
                <Key size={14} className="text-cyan-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] t-text font-medium uppercase tracking-wider">{c.service}</span>
                  {renderProbeBadge(c.last_probe)}
                </div>
                <div className="text-[10px] t-text-dim font-mono">{c.api_key_masked}</div>
              </div>
              {c.extra && Object.keys(c.extra).length > 0 && (
                <span className="text-[10px] t-text-mute px-2 py-0.5 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
                  +{Object.keys(c.extra).length} extra
                </span>
              )}
              <span className="text-[10px] t-text-dim hidden sm:inline">{c.updated_at?.slice(0, 10)}</span>
              <button
                data-testid={`test-credential-${c.service}`}
                onClick={() => testConnection(c.service)}
                disabled={testing === c.service}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] tracking-widest font-medium uppercase rounded-sm text-cyan-300 hover:bg-cyan-400/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ border: '1px solid rgba(34,211,238,0.3)' }}
                title="Fire a sanity probe against this credential"
              >
                {testing === c.service ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
                TEST
              </button>
              <button
                data-testid={`delete-credential-${c.service}`}
                onClick={() => del(c.service)}
                className="p-1.5 text-zinc-600 hover:text-red-400"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        {/* Add modal */}
        {open === "new" && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={() => setOpen(null)}>
            <div
              className="w-full max-w-md rounded-sm p-5"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 mb-4">
                <Key size={14} className="text-cyan-400" />
                <span className="text-[12px] tracking-widest uppercase t-text">New Credential</span>
                <button className="ml-auto t-text-mute" onClick={() => setOpen(null)}><X size={14} /></button>
              </div>

              <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">Service</label>
              <select
                data-testid="cred-service-select"
                className="config-input mb-3"
                value={form.service}
                onChange={(e) => setForm({ ...form, service: e.target.value })}
              >
                {SERVICES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>

              <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">API Key / Token / URL / DSN</label>
              <input
                data-testid="cred-api-key-input"
                type="password"
                className="config-input mb-1 font-mono"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder={SERVICES.find((s) => s.id === form.service)?.hint || ""}
              />
              <p className="text-[10px] t-text-dim mb-3 leading-relaxed">
                {SERVICES.find((s) => s.id === form.service)?.hint}
              </p>

              <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">Extra (JSON)</label>
              <textarea
                data-testid="cred-extra-input"
                rows={3}
                className="config-input font-mono text-[10px] mb-4"
                value={form.extra}
                onChange={(e) => setForm({ ...form, extra: e.target.value })}
                placeholder='{"account_sid":"AC...","from_number":"+1..."}'
              />

              <div className="flex items-center gap-2">
                <button onClick={() => setOpen(null)} className="px-3 py-2 text-[11px] t-text-mute rounded-sm" style={{ border: '1px solid var(--border)' }}>
                  CANCEL
                </button>
                <button
                  data-testid="save-credential-btn"
                  onClick={save}
                  disabled={!form.api_key}
                  className="flex-1 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50"
                >
                  STORE KEY
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

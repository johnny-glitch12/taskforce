import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import { Key, Trash2, Plus, Shield, X } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const SERVICES = [
  { id: "slack",    label: "Slack",     hint: "Incoming Webhook URL (https://hooks.slack.com/...)" },
  { id: "sendgrid", label: "SendGrid",  hint: "SG.xxxxxxxxxx... (also set extra.from_email)" },
  { id: "gmail",    label: "Gmail",     hint: "OAuth access token (v1 — manual refresh)" },
];

export default function CredentialsVault() {
  const { token } = useAuth();
  const [creds, setCreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ service: "slack", api_key: "", extra: "{}" });

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
      if (res.ok) { toast.success("Credential saved."); setOpen(null); setForm({ service: "slack", api_key: "", extra: "{}" }); load(); }
      else { const e = await res.json(); toast.error(e.detail || "Save failed."); }
    } catch { toast.error("Save failed."); }
  };

  const del = async (service) => {
    if (!confirm(`Delete ${service} credential?`)) return;
    try {
      const res = await fetch(`${API}/api/workflows/credentials/${service}`, { method: "DELETE", headers });
      if (res.ok) { toast.success("Deleted."); load(); }
    } catch { toast.error("Delete failed."); }
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
            <p className="text-[12px] t-text-dim uppercase tracking-widest">Bring Your Own Keys · Encrypted Storage</p>
          </div>
        </div>
        <div className="text-[11px] t-text-dim mb-6 max-w-2xl">
          Store API keys for Slack / SendGrid / Gmail to power action nodes in your workflows. Keys are stored masked and never returned in plain text after save. SSRF guards apply to all outbound calls.
        </div>

        {/* Add button */}
        <button
          data-testid="add-credential-btn"
          onClick={() => setOpen("new")}
          className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 mb-6"
        >
          <Plus size={13} /> ADD CREDENTIAL
        </button>

        {/* List */}
        {loading && <div className="t-text-dim text-[12px]">Loading...</div>}
        {!loading && creds.length === 0 && (
          <div className="t-text-dim text-[12px] p-6 rounded-sm text-center" style={{ background: 'var(--bg-card)', border: '1px dashed var(--border)' }}>
            No credentials yet. Add Slack / SendGrid / Gmail keys to unlock action nodes in The Armory.
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
                <div className="text-[13px] t-text font-medium uppercase tracking-wider">{c.service}</div>
                <div className="text-[10px] t-text-dim font-mono">{c.api_key_masked}</div>
              </div>
              {c.extra && Object.keys(c.extra).length > 0 && (
                <span className="text-[10px] t-text-mute px-2 py-0.5 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
                  +{Object.keys(c.extra).length} extra
                </span>
              )}
              <span className="text-[10px] t-text-dim">{c.updated_at?.slice(0, 10)}</span>
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

              <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">API Key / Token / URL</label>
              <input
                data-testid="cred-api-key-input"
                type="password"
                className="config-input mb-1 font-mono"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder={SERVICES.find((s) => s.id === form.service)?.hint || ""}
              />
              <p className="text-[10px] t-text-dim mb-3">{SERVICES.find((s) => s.id === form.service)?.hint}</p>

              <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">Extra (JSON)</label>
              <textarea
                data-testid="cred-extra-input"
                rows={3}
                className="config-input font-mono text-[10px] mb-4"
                value={form.extra}
                onChange={(e) => setForm({ ...form, extra: e.target.value })}
                placeholder='{"from_email":"you@example.com"}'
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

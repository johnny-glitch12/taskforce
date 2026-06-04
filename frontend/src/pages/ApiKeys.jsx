/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import { Key, Plus, Copy, Trash2, AlertTriangle, Code2, BookOpen, Loader2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function ApiKeys() {
  const { token } = useAuth() || {};
  const auth = { Authorization: `Bearer ${token}` };
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [minting, setMinting] = useState(false);
  const [name, setName] = useState("");
  const [freshKey, setFreshKey] = useState(null); // the ONE-TIME plaintext key after minting

  async function refresh() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/keys`, { headers: auth });
      const d = await r.json();
      setKeys(d.items || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  async function mint() {
    if (!name.trim()) { toast.error("Give your key a name"); return; }
    setMinting(true);
    try {
      const r = await fetch(`${API}/api/keys`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      const body = await r.json();
      if (!r.ok) { toast.error(body.detail || "Failed to mint key"); return; }
      setFreshKey(body);
      setName("");
      refresh();
    } catch (e) { toast.error(e.message); }
    finally { setMinting(false); }
  }

  async function revoke(id) {
    if (!window.confirm("Revoke this key? Any apps using it will stop working immediately.")) return;
    try {
      const r = await fetch(`${API}/api/keys/${id}`, { method: "DELETE", headers: auth });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        toast.error(b.detail || "Revoke failed");
        return;
      }
      toast.success("Key revoked");
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-4xl mx-auto px-6 py-10" data-testid="api-keys-page">
        <div className="mb-8">
          <div className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim mb-2">
            Task Force AI / Developer
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold t-text flex items-center gap-3 mb-2">
            <Key className="text-cyan-400" size={36} /> API Keys
          </h1>
          <p className="text-sm t-text-mute max-w-2xl">
            Programmatically run your deployments and fetch run history. Each key is rate-limited to 60 requests/minute.
          </p>
        </div>

        {/* Fresh-key reveal panel */}
        {freshKey && (
          <div data-testid="fresh-key-card" className="t-card rounded-sm p-5 mb-6"
               style={{ borderColor: "#22c55e88", background: "rgba(34,197,94,0.06)" }}>
            <div className="flex items-start gap-3 mb-4">
              <AlertTriangle size={18} className="text-amber-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-sm font-semibold t-text mb-1">Copy this key now</div>
                <div className="text-xs t-text-mute">
                  This is the only time we'll show it in full. If you lose it, revoke and create a new one.
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 rounded-sm font-mono text-xs t-text break-all"
                 style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}>
              <span className="flex-1" data-testid="fresh-key-value">{freshKey.key}</span>
              <button
                data-testid="copy-fresh-key"
                onClick={() => { navigator.clipboard?.writeText(freshKey.key); toast.success("Key copied"); }}
                className="shrink-0 px-2 py-1 rounded-sm inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-[0.12em]"
                style={{ background: "#22d3ee", color: "#0a0e1a" }}
              >
                <Copy size={11} /> Copy
              </button>
            </div>
            <button
              onClick={() => setFreshKey(null)}
              className="mt-3 text-[10px] font-mono uppercase tracking-[0.12em] t-text-mute hover:t-text"
            >
              I've saved it — dismiss
            </button>
          </div>
        )}

        {/* Mint form */}
        <div className="t-card rounded-sm p-5 mb-6">
          <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-2">New key</div>
          <div className="flex gap-2">
            <input
              data-testid="key-name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              placeholder="e.g. Production webhook, Zapier integration"
              className="flex-1 px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
            />
            <button
              data-testid="mint-key-btn"
              onClick={mint}
              disabled={minting || !name.trim()}
              className="px-4 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
              style={{
                background: name.trim() ? "#22d3ee" : "var(--bg-input)",
                color: name.trim() ? "#0a0e1a" : "var(--text-mute)",
                opacity: minting ? 0.5 : 1,
              }}
            >
              {minting ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />} Create key
            </button>
          </div>
        </div>

        {/* Existing keys */}
        <div className="t-card rounded-sm">
          <div className="flex items-center justify-between p-4 border-b border-[color:var(--border)]">
            <h2 className="text-lg font-semibold t-text">Your keys</h2>
            <span className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim">
              {keys.length} active
            </span>
          </div>
          {loading ? (
            <div className="text-center py-10 t-text-mute text-sm" data-testid="keys-loading">
              <Loader2 className="animate-spin inline-block mr-2" size={14} /> Loading…
            </div>
          ) : !keys.length ? (
            <div className="text-center py-12 text-sm t-text-mute" data-testid="empty-keys">
              No API keys yet. Create one above to start using the public API.
            </div>
          ) : (
            <div className="divide-y divide-[color:var(--border)]" data-testid="keys-list">
              {keys.map((k) => (
                <div key={k.id} data-testid={`key-row-${k.id}`} className="flex items-center gap-3 p-4">
                  <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0"
                       style={{ background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.4)" }}>
                    <Key size={14} className="text-cyan-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm t-text mb-0.5">{k.name}</div>
                    <div className="text-[10px] font-mono t-text-mute">
                      {k.key_prefix}…{`••••`}{`•`}{`•`} · created {k.created_at?.slice(0, 10)} · {k.call_count || 0} calls
                      {k.last_used_at && ` · last ${k.last_used_at.slice(0, 16).replace("T", " ")}`}
                    </div>
                  </div>
                  <button
                    data-testid={`revoke-${k.id}`}
                    onClick={() => revoke(k.id)}
                    className="shrink-0 px-3 py-1.5 rounded-sm text-[10px] font-mono uppercase tracking-[0.12em] inline-flex items-center gap-1.5"
                    style={{ color: "#ef4444", border: "1px solid #ef444455" }}
                  >
                    <Trash2 size={10} /> Revoke
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Docs */}
        <div className="t-card rounded-sm p-5 mt-6" data-testid="api-docs">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={14} className="text-cyan-400" />
            <h3 className="text-sm font-semibold t-text">Quick start</h3>
          </div>
          <div className="text-[11px] font-mono t-text-mute mb-3">
            Replace <span className="t-text">{`<KEY>`}</span> with your key and{" "}
            <span className="t-text">{`<DEPLOYMENT_ID>`}</span> with one of your deployment IDs (find them on the My Deployments page).
          </div>
          <CodeBlock>
{`# Run a deployment
curl -X POST \\
  ${API}/api/public/v1/deployments/<DEPLOYMENT_ID>/run \\
  -H "X-API-Key: <KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{"input": {"foo": "bar"}}'

# List recent runs
curl ${API}/api/public/v1/deployments/<DEPLOYMENT_ID>/runs?limit=10 \\
  -H "X-API-Key: <KEY>"`}
          </CodeBlock>
          <div className="text-[10px] font-mono t-text-mute mt-3">
            <Code2 size={10} className="inline-block mr-1 -mt-0.5" />
            Rate limit: <span className="t-text">60 req/min per key</span>. Exceeding it returns 429.
          </div>
        </div>
      </div>
    </div>
  );
}

function CodeBlock({ children }) {
  return (
    <pre className="text-[11px] font-mono p-3 rounded-sm overflow-x-auto"
         style={{ background: "var(--bg-input)", border: "1px solid var(--border)", color: "var(--text)" }}>
      {children}
    </pre>
  );
}

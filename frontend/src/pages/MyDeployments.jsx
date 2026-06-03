import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Rocket, ShoppingCart, BarChart3, Settings, ArrowUpRight, Bot, Loader2,
  Play, Clock, CheckCircle2, AlertCircle, Zap, Calendar,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function MyDeployments() {
  const { token } = useAuth();
  const [deployments, setDeployments] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/deployments/me`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setDeployments(data.deployments || []);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!token) return;
    load();
    // Handle deploy-success redirect from Stripe
    const params = new URLSearchParams(window.location.search);
    if (params.get("deploy") === "success" && params.get("session_id")) {
      fetch(`${API}/api/deployments/poll/${params.get("session_id")}`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      }).then((r) => r.json()).then((d) => {
        if (d.paid && (d.deployment_id || d.already_provisioned)) toast.success("Deployment ready.");
        load();
      });
    }
  }, [token]); // eslint-disable-line

  return (
    <div data-testid="my-deployments-page" className="min-h-screen t-bg px-4 sm:px-8 py-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-2">
          <Rocket size={20} className="text-cyan-400" />
          <h1 className="text-2xl md:text-3xl tracking-wide t-text" style={{ fontFamily: "'Rajdhani', sans-serif", letterSpacing: '0.04em' }}>
            MY DEPLOYMENTS
          </h1>
        </div>
        <p className="text-[12px] t-text-dim mb-6 uppercase tracking-widest">
          Bots you bought, rented, or deployed for free · {deployments.length} active
        </p>

        {loading && <div className="text-center py-20"><Loader2 size={20} className="animate-spin text-cyan-400 inline" /></div>}

        {!loading && deployments.length === 0 && (
          <div className="rounded-sm p-12 text-center" style={{ background: 'var(--bg-card)', border: '1px dashed var(--border)' }}>
            <ShoppingCart size={28} className="text-cyan-400 mx-auto mb-3 opacity-60" />
            <div className="text-[13px] t-text font-medium mb-1">No deployments yet</div>
            <div className="text-[11px] t-text-dim mb-4">Buy or rent a bot from The Exchange to spin up your first deployment.</div>
            <Link to="/exchange" data-testid="my-deps-browse-exchange"
              className="inline-flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono tracking-[0.1em] uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300">
              Browse The Exchange
            </Link>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {deployments.map((d) => (
            <DeploymentCard key={d.id} deployment={d} token={token} onUpdate={load} />
          ))}
        </div>
      </div>
    </div>
  );
}

function DeploymentCard({ deployment: d, token, onUpdate }) {
  const [tab, setTab] = useState("monitor"); // monitor | customize | upgrade
  const cfg = d.config || {};
  const usage = d.usage || {};
  const pct = usage.limit_per_month ? Math.min(100, (usage.run_count / usage.limit_per_month) * 100) : 0;
  const nearLimit = pct >= 80;
  const color = d.listing_avatar_color || "#22d3ee";

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const run = async () => {
    const res = await fetch(`${API}/api/deployments/${d.id}/run`, { method: "POST", headers });
    const data = await res.json();
    if (data.allowed) toast.success(`Run logged · ${data.run_count}/${data.limit}`);
    else toast.error(data.message || "Run limit reached.");
    onUpdate();
  };
  const upgrade = async () => {
    const res = await fetch(`${API}/api/deployments/${d.id}/upgrade`, { method: "POST", headers });
    const data = await res.json();
    if (data.url) window.location.href = data.url;
    else toast.error(data.detail || "Upgrade failed.");
  };

  return (
    <div
      data-testid={`deployment-${d.id}`}
      className="rounded-sm overflow-hidden"
      style={{ background: 'var(--bg-card)', border: `1px solid ${color}33` }}
    >
      <div className="p-3 flex items-center gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="w-10 h-10 rounded-sm flex items-center justify-center shrink-0 overflow-hidden"
          style={{ background: `${color}15`, border: `1px solid ${color}` }}>
          {d.listing_avatar_url
            ? <img src={`${API}${d.listing_avatar_url}`} alt="" className="w-full h-full object-cover" />
            : <Bot size={14} style={{ color }} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[12px] t-text font-medium truncate">{cfg.name || d.listing_name}</div>
          <div className="text-[9px] t-text-dim font-mono uppercase tracking-wider">
            {d.mode} · {(cfg.files || []).length} files · {(cfg.nodes || []).length} nodes
          </div>
        </div>
        <span
          className="text-[9px] uppercase tracking-widest font-mono px-1.5 py-0.5 rounded-sm"
          style={{
            color: d.mode === "buy" ? "#34d399" : d.mode === "rent" ? "#fbbf24" : "#a1a1aa",
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
          }}
        >
          {d.mode === "buy" ? "OWNED" : d.mode === "rent" ? "RENTED" : "FREE"}
        </span>
      </div>

      {/* Tabs */}
      <div className="flex" style={{ borderBottom: '1px solid var(--border)' }}>
        {[
          { id: "monitor", Icon: BarChart3, label: "MONITOR" },
          { id: "customize", Icon: Settings, label: "CUSTOMIZE" },
          { id: "schedule", Icon: Calendar, label: "SCHEDULE" },
          { id: "upgrade", Icon: ArrowUpRight, label: "UPGRADE" },
        ].map(({ id, Icon, label }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              data-testid={`dep-tab-${id}`}
              onClick={() => setTab(id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-mono tracking-widest transition-colors ${
                active ? "t-text" : "t-text-mute hover:t-text"
              }`}
              style={{ borderTop: active ? `2px solid ${color}` : '2px solid transparent', marginTop: -1 }}
            >
              <Icon size={10} style={{ color: active ? color : undefined }} />
              {label}
            </button>
          );
        })}
      </div>

      <div className="p-3">
        {tab === "monitor" && (
          <>
            <div className="mb-3">
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="text-[10px] uppercase tracking-widest t-text-dim font-mono">Usage this month</span>
                <span className="text-[11px] font-mono" style={{ color: nearLimit ? "#fb7185" : color }}>
                  {usage.run_count || 0} / {usage.limit_per_month || 0}
                </span>
              </div>
              <div className="h-1.5 rounded-sm overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                <div className="h-full transition-all"
                  style={{ width: `${pct}%`, background: nearLimit ? "#fb7185" : color }} />
              </div>
              {nearLimit && (
                <div className="text-[10px] text-rose-400 mt-1.5 flex items-center gap-1 font-mono">
                  <AlertCircle size={9} /> Near limit — upgrade to keep running.
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
              <Stat label="Last run" value={usage.last_run_at ? new Date(usage.last_run_at).toLocaleString() : "never"} />
              <Stat label="Deployed" value={new Date(d.created_at).toLocaleDateString()} />
            </div>
            <button onClick={run} data-testid={`dep-run-${d.id}`}
              className="mt-3 w-full py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm"
              style={{ background: color, color: '#000' }}>
              <Play size={9} className="inline mr-1" /> Run Now
            </button>
            <Link to={`/my-deployments/${d.id}/monitor`} data-testid={`dep-open-monitor-${d.id}`}
              className="mt-2 w-full py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm flex items-center justify-center gap-1.5 t-text-sub hover:t-text"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
              <BarChart3 size={9} /> Open Full Analytics
            </Link>
          </>
        )}

        {tab === "customize" && (
          <CustomizeTab deployment={d} token={token} onUpdate={onUpdate} color={color} />
        )}

        {tab === "schedule" && (
          <ScheduleTab deployment={d} token={token} onUpdate={onUpdate} color={color} />
        )}

        {tab === "upgrade" && (
          <>
            {d.mode === "buy" ? (
              <div className="text-center py-4">
                <CheckCircle2 size={20} className="text-emerald-400 mx-auto mb-2" />
                <div className="text-[11px] t-text">You own this bot — no further upgrade needed.</div>
                <div className="text-[10px] t-text-dim mt-1 font-mono">Run limit: {usage.limit_per_month?.toLocaleString()}/mo</div>
              </div>
            ) : (
              <>
                <div className="text-[11px] t-text mb-2">
                  Upgrade to <span className="text-cyan-400 font-mono">OWNED</span> to lift the monthly run cap and lock in your customizations forever.
                </div>
                <div className="text-[10px] t-text-dim mb-3 font-mono">
                  Current: {usage.limit_per_month}/mo · After upgrade: 10,000/mo · Paid so far: ${(d.amount_paid || 0).toFixed(2)}
                </div>
                <button onClick={upgrade} data-testid={`dep-upgrade-${d.id}`}
                  className="w-full py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300">
                  <Zap size={9} className="inline mr-1" /> Upgrade to Owned
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-sm p-2" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
      <div className="text-[9px] uppercase tracking-widest t-text-dim">{label}</div>
      <div className="t-text truncate mt-0.5">{value}</div>
    </div>
  );
}

function CustomizeTab({ deployment, token, onUpdate, color }) {
  const cfg = deployment.config || {};
  const [name, setName] = useState(cfg.name || "");
  const [vars, setVars] = useState(JSON.stringify(cfg.vars || {}, null, 2));
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      let parsedVars = {};
      try { parsedVars = JSON.parse(vars || "{}"); } catch { toast.error("vars must be valid JSON."); setBusy(false); return; }
      const res = await fetch(`${API}/api/deployments/${deployment.id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ name, vars: parsedVars }),
      });
      if (res.ok) { toast.success("Saved."); onUpdate(); } else toast.error("Save failed.");
    } catch { toast.error("Save failed."); }
    setBusy(false);
  };
  return (
    <>
      <label className="block text-[9px] uppercase tracking-widest t-text-dim mb-1 font-mono">Name</label>
      <input data-testid={`dep-custom-name-${deployment.id}`}
        value={name} onChange={(e) => setName(e.target.value)}
        className="w-full px-2 py-1.5 text-[11px] rounded-sm mb-3"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }} />
      <label className="block text-[9px] uppercase tracking-widest t-text-dim mb-1 font-mono">Environment Vars (JSON)</label>
      <textarea data-testid={`dep-custom-vars-${deployment.id}`}
        value={vars} onChange={(e) => setVars(e.target.value)}
        rows={5}
        className="w-full px-2 py-1.5 text-[10px] rounded-sm font-mono"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }} />
      {(cfg.required_integrations || []).length > 0 && (
        <div className="mt-2 text-[10px] t-text-dim font-mono">
          Required BYOK: {cfg.required_integrations.join(", ")}
        </div>
      )}
      <button onClick={save} disabled={busy} data-testid={`dep-save-${deployment.id}`}
        className="mt-3 w-full py-2 text-[10px] font-mono tracking-widest uppercase rounded-sm disabled:opacity-50"
        style={{ background: color, color: '#000' }}>
        {busy ? <Loader2 size={9} className="animate-spin inline" /> : "Save Customization"}
      </button>
    </>
  );
}

const PRESET_OPTIONS = [
  { id: "hourly",  label: "Every hour" },
  { id: "6h",      label: "Every 6 hours" },
  { id: "daily",   label: "Once a day" },
  { id: "weekly",  label: "Once a week" },
];

function ScheduleTab({ deployment, token, onUpdate, color }) {
  const [sched, setSched] = useState(deployment.schedule || { enabled: false, preset: null });
  const [busy, setBusy] = useState(false);
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const enabled = !!sched?.enabled;
  const preset = sched?.preset || "daily";

  const save = async (next) => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/deployments/${deployment.id}/schedule`, {
        method: "PUT", headers,
        body: JSON.stringify(next),
      });
      const body = await res.json();
      if (!res.ok) { toast.error(body.detail || "Save failed"); return; }
      setSched(body.schedule);
      toast.success(next.enabled ? "Schedule enabled" : "Schedule disabled");
      onUpdate();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };

  return (
    <>
      <div className="text-[10px] uppercase tracking-widest t-text-dim mb-2 font-mono inline-flex items-center gap-1">
        <Calendar size={9} /> Auto-run schedule
      </div>
      <div className="rounded-sm p-2 mb-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
        <label className="flex items-center justify-between cursor-pointer mb-2">
          <span className="text-[11px] t-text">Enable scheduled runs</span>
          <input
            type="checkbox"
            data-testid={`sched-toggle-${deployment.id}`}
            checked={enabled}
            disabled={busy}
            onChange={(e) => save({ enabled: e.target.checked, preset: e.target.checked ? preset : null })}
            className="accent-cyan-400"
          />
        </label>
        {enabled && (
          <>
            <div className="grid grid-cols-2 gap-1.5" data-testid={`sched-presets-${deployment.id}`}>
              {PRESET_OPTIONS.map((p) => (
                <button
                  key={p.id}
                  data-testid={`sched-preset-${deployment.id}-${p.id}`}
                  disabled={busy}
                  onClick={() => save({ enabled: true, preset: p.id })}
                  className="px-2 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] rounded-sm transition-all"
                  style={{
                    background: preset === p.id ? color : 'transparent',
                    color: preset === p.id ? '#0a0e1a' : 'var(--text-mute)',
                    border: `1px solid ${preset === p.id ? color : 'var(--border)'}`,
                    opacity: busy ? 0.5 : 1,
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="mt-2 text-[10px] t-text-dim font-mono space-y-0.5">
              {sched?.next_run_at && (
                <div data-testid={`sched-next-${deployment.id}`}>Next run: {new Date(sched.next_run_at).toLocaleString()}</div>
              )}
              {sched?.last_run_at && (
                <div>
                  Last run: {new Date(sched.last_run_at).toLocaleString()}
                  {sched.last_run_success === true && <span className="text-emerald-400 ml-1">· ok</span>}
                  {sched.last_run_success === false && <span className="text-rose-400 ml-1">· failed</span>}
                </div>
              )}
              {sched?.last_disabled_reason === "limit_reached" && (
                <div className="text-rose-400">Auto-disabled: monthly run limit reached.</div>
              )}
            </div>
          </>
        )}
      </div>
      <div className="text-[10px] t-text-dim font-mono leading-relaxed">
        Scheduled runs consume your deployment's monthly run quota.
        If you hit the cap the schedule auto-disables — upgrade or wait for the next cycle.
      </div>
    </>
  );
}


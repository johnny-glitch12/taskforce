import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Server, Zap, ShieldCheck, ArrowUpRight, Loader2,
  Check, Sparkles, Infinity as InfinityIcon, Clock,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const ACCENT = {
  starter: "#94a3b8",
  pro:     "#22d3ee",
  growth:  "#a855f7",
  scale:   "#fbbf24",
};

export default function HostingPlans() {
  const { token } = useAuth() || {};
  const auth = { Authorization: `Bearer ${token}` };
  const [tiers, setTiers] = useState([]);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null); // tier-name while checkout call is in-flight
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [tRes, uRes] = await Promise.all([
          fetch(`${API}/api/hosting/tiers`).then((r) => r.json()),
          fetch(`${API}/api/hosting/usage`, { headers: auth }).then((r) => r.json()),
        ]);
        setTiers(tRes.tiers || []);
        setUsage(uRes);
      } catch (e) {
        toast.error(`Failed to load: ${e.message}`);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, []);

  async function checkout(tier) {
    setBusy(tier);
    try {
      const r = await fetch(`${API}/api/hosting/checkout`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ tier, origin_url: window.location.origin }),
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || "Checkout failed");
        return;
      }
      // Hand off to Stripe.
      window.location.href = body.url;
    } catch (e) {
      toast.error(`Checkout failed: ${e.message}`);
    } finally {
      setBusy(null);
    }
  }

  async function cancelSub() {
    if (!window.confirm("Cancel your hosting subscription? You'll keep access until the period ends.")) return;
    setCancelling(true);
    try {
      const r = await fetch(`${API}/api/hosting/cancel`, { method: "POST", headers: auth });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || "Cancel failed");
        return;
      }
      toast.success(body.message || "Cancelled.");
      // Refresh usage card.
      const u = await fetch(`${API}/api/hosting/usage`, { headers: auth }).then((r) => r.json());
      setUsage(u);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCancelling(false);
    }
  }

  const currentTier = usage?.tier;
  const periodEnd = usage?.period_end?.slice(0, 10);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-6xl mx-auto px-6 py-10" data-testid="hosting-plans-page">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim">
              Task Force AI / Exchange
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold t-text mb-2 flex items-center gap-3">
            <Server className="text-cyan-400" size={36} />
            Creator Hosting
          </h1>
          <p className="text-sm t-text-mute max-w-2xl">
            Pick a hosting plan to publish your agents on The Exchange. Buyers pay credits to
            run them; we handle execution, scaling, and revenue split.
          </p>
        </div>

        {/* Current plan banner */}
        {loading ? (
          <div className="t-card rounded-sm p-6 mb-8 text-center text-sm t-text-mute" data-testid="hosting-loading">
            <Loader2 className="animate-spin inline-block mr-2" size={14} /> Loading your plan…
          </div>
        ) : usage?.has_subscription ? (
          <div
            data-testid="current-plan-banner"
            className="t-card rounded-sm p-6 mb-8"
            style={{ borderColor: ACCENT[currentTier] || "var(--border)", borderWidth: 1.5 }}
          >
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-1">
                  Active hosting plan
                </div>
                <div className="text-2xl font-bold t-text">{usage.tier_label}</div>
                <div className="text-xs t-text-mute mt-1 font-mono inline-flex items-center gap-1">
                  <Clock size={11} /> Renews after {periodEnd}
                </div>
              </div>
              <div className="flex items-center gap-6 flex-wrap">
                <UsageStat
                  label="Agents"
                  used={usage.agents_used}
                  cap={usage.max_agents}
                  color={ACCENT[currentTier] || "#22d3ee"}
                  testid="usage-agents"
                />
                <UsageStat
                  label="Executions"
                  used={usage.executions_used}
                  cap={usage.max_executions}
                  color={ACCENT[currentTier] || "#22d3ee"}
                  testid="usage-executions"
                />
                <button
                  data-testid="hosting-cancel-btn"
                  onClick={cancelSub}
                  disabled={cancelling || usage.status === "cancelled"}
                  className="text-xs t-text-mute hover:text-rose-400 underline-offset-2 hover:underline disabled:opacity-50"
                >
                  {usage.status === "cancelled" ? "Cancelled" : (cancelling ? "Cancelling…" : "Cancel")}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div
            data-testid="no-plan-banner"
            className="t-card rounded-sm p-5 mb-8 inline-flex items-center gap-3"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
          >
            <Sparkles size={16} className="text-cyan-400 shrink-0" />
            <span className="text-xs t-text-mute font-mono">
              You haven't subscribed yet. Pick a plan to start publishing.
            </span>
          </div>
        )}

        {/* Tier grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="tier-grid">
          {tiers.map((t) => {
            const isCurrent = currentTier === t.tier;
            const accent = ACCENT[t.tier] || "#22d3ee";
            return (
              <div
                key={t.tier}
                data-testid={`tier-card-${t.tier}`}
                className="t-card rounded-sm p-6 relative flex flex-col"
                style={{
                  borderColor: isCurrent ? accent : (t.highlight ? `${accent}88` : "var(--border)"),
                  borderWidth: isCurrent || t.highlight ? 1.5 : 1,
                  background: t.highlight ? `linear-gradient(180deg, ${accent}0a, var(--bg-card))` : "var(--bg-card)",
                }}
              >
                {t.highlight && (
                  <span
                    className="absolute -top-2.5 right-4 px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.2em] rounded-sm"
                    style={{ background: accent, color: "#0a0e1a" }}
                  >
                    Most Popular
                  </span>
                )}
                {isCurrent && (
                  <span
                    className="absolute -top-2.5 left-4 px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.2em] rounded-sm"
                    style={{ background: accent, color: "#0a0e1a" }}
                    data-testid={`tier-current-badge-${t.tier}`}
                  >
                    Current
                  </span>
                )}

                <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-2">
                  {t.tier}
                </div>
                <div className="text-2xl font-bold t-text mb-1">{t.label.replace("Hosting · ", "")}</div>
                <div className="text-xs t-text-mute mb-4 font-mono">{t.tagline}</div>

                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-3xl font-bold t-text" style={{ color: accent }}>
                    ${t.price.toFixed(0)}
                  </span>
                  <span className="text-xs t-text-mute font-mono">/ mo</span>
                </div>

                <ul className="space-y-1.5 text-xs t-text-mute mb-6 flex-1">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check size={11} className="mt-0.5 shrink-0" style={{ color: accent }} />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <div className="text-[10px] t-text-dim font-mono mb-3">
                  {t.max_agents === 0
                    ? <><InfinityIcon size={10} className="inline mr-1" /> Unlimited agents</>
                    : `${t.max_agents} agent${t.max_agents > 1 ? "s" : ""}`}
                  {" · "}
                  {t.max_executions.toLocaleString()} runs/mo
                </div>

                <button
                  data-testid={`tier-subscribe-${t.tier}`}
                  onClick={() => !isCurrent && checkout(t.tier)}
                  disabled={busy === t.tier || isCurrent}
                  className="w-full py-2.5 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center justify-center gap-1.5 transition-all"
                  style={{
                    background: isCurrent ? "transparent" : accent,
                    color: isCurrent ? accent : "#0a0e1a",
                    border: isCurrent ? `1px solid ${accent}` : "1px solid transparent",
                    opacity: busy === t.tier ? 0.5 : 1,
                    cursor: isCurrent ? "default" : "pointer",
                  }}
                >
                  {busy === t.tier ? (
                    <><Loader2 size={11} className="animate-spin" /> Redirecting…</>
                  ) : isCurrent ? (
                    <><ShieldCheck size={11} /> Active plan</>
                  ) : (
                    <><Zap size={11} /> Subscribe<ArrowUpRight size={11} /></>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Fine print */}
        <p className="text-[10px] t-text-dim font-mono mt-8 max-w-2xl">
          Hosting subscriptions renew every {tiers.length > 0 ? 30 : "30"} days. You can cancel anytime;
          you retain publishing privileges until the period ends. Caps reset at each renewal.
        </p>
      </div>
    </div>
  );
}

function UsageStat({ label, used, cap, color, testid }) {
  const unlimited = cap === 0;
  const pct = unlimited ? 0 : Math.min(100, (used / Math.max(cap, 1)) * 100);
  return (
    <div data-testid={testid} className="text-right">
      <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim">{label}</div>
      <div className="text-base font-mono t-text">
        {used.toLocaleString()}
        <span className="t-text-mute"> / </span>
        {unlimited
          ? <InfinityIcon size={14} className="inline" />
          : cap.toLocaleString()}
      </div>
      {!unlimited && (
        <div className="w-24 h-1 rounded-sm mt-1 ml-auto" style={{ background: "var(--border)" }}>
          <div
            className="h-full rounded-sm"
            style={{ width: `${pct}%`, background: color, transition: "width 0.4s ease" }}
          />
        </div>
      )}
    </div>
  );
}

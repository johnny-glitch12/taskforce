/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Banknote, CheckCircle2, AlertTriangle, ExternalLink,
  Loader2, ShieldCheck, ArrowRight, Settings,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function Payouts() {
  const { token } = useAuth() || {};
  const navigate = useNavigate();
  const auth = { Authorization: `Bearer ${token}` };
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function refresh(forceLive = false) {
    setLoading(true);
    try {
      const url = forceLive
        ? `${API}/api/stripe-connect/refresh-status`
        : `${API}/api/stripe-connect/account`;
      const r = await (forceLive
        ? fetch(url, { method: "POST", headers: auth })
        : fetch(url, { headers: auth }));
      const body = await r.json();
      setAccount(body.account || null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  // Auto-refresh when returning from Stripe (the URL carries ?stripe_return=1).
  useEffect(() => {
    if (window.location.search.includes("stripe_return=1")) {
      refresh(true);
      // Clean the query so subsequent navigations don't double-fire.
      const u = new URL(window.location.href);
      u.searchParams.delete("stripe_return");
      window.history.replaceState({}, "", u.toString());
    }
    // eslint-disable-next-line
  }, []);

  async function startOnboarding() {
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/stripe-connect/onboard`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({
          return_url: `${window.location.origin}/payouts?stripe_return=1`,
          refresh_url: `${window.location.origin}/payouts?stripe_return=1`,
        }),
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || `Failed (${r.status})`);
        return;
      }
      // Hand off to Stripe's hosted onboarding.
      window.location.href = body.url;
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openDashboard() {
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/stripe-connect/dashboard-link`, {
        method: "POST", headers: auth,
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || `Failed (${r.status})`);
        return;
      }
      window.open(body.url, "_blank");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  const ready = !!account?.ready_for_payout;
  const partial = !!account && !ready;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-3xl mx-auto px-6 py-10" data-testid="payouts-page">
        {/* Header */}
        <div className="mb-8">
          <div className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim mb-2">
            Task Force AI / Creator Earnings
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold t-text flex items-center gap-3 mb-2">
            <Banknote className="text-cyan-400" size={36} />
            Payouts
          </h1>
          <p className="text-sm t-text-mute max-w-xl">
            Connect a payout destination to receive USD when you win cash bounties.
            We use Stripe Connect Express — onboarding takes ~2 minutes.
          </p>
        </div>

        {loading ? (
          <div className="t-card rounded-sm p-10 text-center text-sm t-text-mute" data-testid="payouts-loading">
            <Loader2 size={14} className="animate-spin inline-block mr-2" /> Loading account status…
          </div>
        ) : !account ? (
          <NoAccountCard onStart={startOnboarding} busy={busy} />
        ) : ready ? (
          <ReadyCard account={account} onOpenDashboard={openDashboard} busy={busy} />
        ) : (
          <PartialCard account={account} onResume={startOnboarding} busy={busy} />
        )}

        {/* How it works */}
        <div className="mt-8 t-card rounded-sm p-5">
          <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-3">How payouts work</div>
          <ol className="space-y-2 text-xs t-text-mute font-mono list-decimal list-inside">
            <li>Poster locks USD in escrow when they post a cash bounty.</li>
            <li>You submit your agent. When the poster picks you as the winner, we transfer the full amount to your Stripe Connect account.</li>
            <li>Stripe deposits to your bank on its standard payout schedule (usually 2 business days).</li>
            <li>No platform fee on cash bounties for v1 — 100% pass-through.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

function NoAccountCard({ onStart, busy }) {
  return (
    <div data-testid="no-account-card" className="t-card rounded-sm p-8 text-center">
      <div
        className="w-14 h-14 mx-auto rounded-sm flex items-center justify-center mb-4"
        style={{ background: "#22d3ee1a", border: "1px solid #22d3ee55" }}
      >
        <Banknote size={22} className="text-cyan-400" />
      </div>
      <h2 className="text-lg font-semibold t-text mb-1">Set up payouts</h2>
      <p className="text-sm t-text-mute mb-6 max-w-md mx-auto">
        Verify your identity and link a bank account through Stripe.
        You only need to do this once.
      </p>
      <button
        data-testid="start-onboarding-btn"
        onClick={onStart}
        disabled={busy}
        className="px-5 py-3 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
        style={{ background: "#22d3ee", color: "#0a0e1a", opacity: busy ? 0.5 : 1 }}
      >
        {busy ? <><Loader2 size={12} className="animate-spin" /> Redirecting…</>
              : <>Start onboarding <ArrowRight size={12} /></>}
      </button>
    </div>
  );
}

function ReadyCard({ account, onOpenDashboard, busy }) {
  return (
    <div data-testid="ready-card" className="t-card rounded-sm p-6"
         style={{ borderColor: "#22c55e88" }}>
      <div className="flex items-start gap-4 mb-5">
        <div
          className="w-12 h-12 rounded-sm flex items-center justify-center shrink-0"
          style={{ background: "#22c55e1a", border: "1px solid #22c55e55" }}
        >
          <CheckCircle2 size={20} className="text-green-400" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-green-400 mb-1">Active</div>
          <h2 className="text-lg font-semibold t-text">Payouts ready</h2>
          <p className="text-sm t-text-mute mt-1">
            You can receive cash bounties. Stripe payouts go to your bank on the standard schedule.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-5 text-[11px] font-mono">
        <StatusChip label="Identity" ok={account.details_submitted} />
        <StatusChip label="Charges" ok={account.charges_enabled} />
        <StatusChip label="Payouts" ok={account.payouts_enabled} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          data-testid="open-dashboard-btn"
          onClick={onOpenDashboard}
          disabled={busy}
          className="px-4 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
          style={{
            background: "transparent",
            color: "#22d3ee",
            border: "1px solid #22d3ee55",
            opacity: busy ? 0.5 : 1,
          }}
        >
          <Settings size={11} /> Stripe Dashboard <ExternalLink size={11} />
        </button>
        <span className="text-[10px] t-text-dim font-mono">
          Account: <span className="t-text">{account.stripe_account_id}</span>
        </span>
      </div>
    </div>
  );
}

function PartialCard({ account, onResume, busy }) {
  return (
    <div data-testid="partial-card" className="t-card rounded-sm p-6"
         style={{ borderColor: "#fbbf2488" }}>
      <div className="flex items-start gap-4 mb-5">
        <div
          className="w-12 h-12 rounded-sm flex items-center justify-center shrink-0"
          style={{ background: "#fbbf241a", border: "1px solid #fbbf2455" }}
        >
          <AlertTriangle size={20} className="text-amber-400" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-amber-400 mb-1">Action needed</div>
          <h2 className="text-lg font-semibold t-text">Finish onboarding</h2>
          <p className="text-sm t-text-mute mt-1">
            Stripe still needs some info before you can receive payouts.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-5 text-[11px] font-mono">
        <StatusChip label="Identity" ok={account.details_submitted} />
        <StatusChip label="Charges" ok={account.charges_enabled} />
        <StatusChip label="Payouts" ok={account.payouts_enabled} />
      </div>
      {(account.requirements_currently_due?.length || 0) > 0 && (
        <div className="text-[10px] font-mono t-text-dim mb-4">
          Still needed: <span className="t-text">
            {(account.requirements_currently_due || []).slice(0, 5).join(", ")}
          </span>
        </div>
      )}
      <button
        data-testid="resume-onboarding-btn"
        onClick={onResume}
        disabled={busy}
        className="px-5 py-2.5 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
        style={{ background: "#fbbf24", color: "#0a0e1a", opacity: busy ? 0.5 : 1 }}
      >
        {busy ? <><Loader2 size={12} className="animate-spin" /> Redirecting…</>
              : <>Resume onboarding <ArrowRight size={12} /></>}
      </button>
    </div>
  );
}

function StatusChip({ label, ok }) {
  return (
    <div
      className="rounded-sm px-3 py-2 flex items-center gap-2"
      style={{
        background: ok ? "#22c55e10" : "#fbbf2410",
        border: `1px solid ${ok ? "#22c55e55" : "#fbbf2455"}`,
      }}
      data-testid={`status-chip-${label.toLowerCase()}`}
    >
      {ok ? <CheckCircle2 size={11} className="text-green-400" />
          : <AlertTriangle size={11} className="text-amber-400" />}
      <span className="t-text-mute uppercase tracking-[0.15em]">{label}</span>
      <span className="ml-auto t-text">{ok ? "ok" : "pending"}</span>
    </div>
  );
}

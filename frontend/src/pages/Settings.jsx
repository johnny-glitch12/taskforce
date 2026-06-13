/**
 * Settings — account settings hub.
 *
 * Headline control is Developer Mode (off by default): when off, Task Force is a
 * pure no-code product — generated source, the flow graph, and the Workflows
 * editor are all hidden. Turning it on restores those surfaces for power users.
 * Also links out to the focused settings pages (Credentials, Builder Memory) and
 * carries the payout preference.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/App";
import usePageTitle from "@/hooks/usePageTitle";
import { toast } from "sonner";
import { Code2, KeyRound, Brain, Wallet, ChevronRight, Loader2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function Toggle({ checked, onChange, busy }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      data-testid="developer-mode-toggle"
      disabled={busy}
      onClick={() => onChange(!checked)}
      className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 disabled:opacity-60 shrink-0"
      style={{ background: checked ? "var(--accent)" : "var(--border)" }}
    >
      <span
        className="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200"
        style={{ transform: checked ? "translateX(24px)" : "translateX(4px)" }}
      />
    </button>
  );
}

function LinkRow({ to, icon: Icon, title, desc }) {
  return (
    <Link
      to={to}
      data-testid={`settings-link-${title.toLowerCase().replace(/\s/g, "-")}`}
      className="flex items-center gap-4 p-4 rounded-sm transition-colors hover:bg-[var(--bg-card-hover)]"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background: "var(--accent-bg)", border: "1px solid var(--accent-border)" }}>
        <Icon size={16} style={{ color: "var(--accent)" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-medium t-text">{title}</p>
        <p className="text-[12px] t-text-mute">{desc}</p>
      </div>
      <ChevronRight size={16} className="t-text-dim shrink-0" />
    </Link>
  );
}

export default function Settings() {
  usePageTitle("Settings");
  const { developerMode, setDeveloperMode, user } = useAuth() || {};
  const [busy, setBusy] = useState(false);
  const [payoutPref, setPayoutPref] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("taskforce_token");
    if (!token) return;
    fetch(`${API}/api/settings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setPayoutPref(d.payout_preference); })
      .catch(() => {});
  }, []);

  const onToggleDev = async (next) => {
    setBusy(true);
    const ok = await setDeveloperMode(next);
    setBusy(false);
    if (ok) toast.success(next ? "Developer mode on — code surfaces restored." : "Developer mode off — back to no-code.");
    else toast.error("Couldn't save that. Try again.");
  };

  const isAdmin = user?.role === "admin";

  return (
    <div data-testid="settings-page" className="min-h-[calc(100vh-56px)] max-w-2xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold t-text mb-1">Settings</h1>
      <p className="text-[14px] t-text-sub mb-10">Manage your account, keys, and how Task Force behaves.</p>

      {/* Accessibility / Developer */}
      <section className="mb-8">
        <h2 className="text-[11px] uppercase tracking-[0.2em] font-mono t-text-mute mb-3">Accessibility</h2>
        <div className="rounded-sm p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background: "var(--accent-bg)", border: "1px solid var(--accent-border)" }}>
              <Code2 size={16} style={{ color: "var(--accent)" }} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-medium t-text">Developer mode</p>
              <p className="text-[12px] t-text-mute leading-relaxed mt-0.5">
                Off by default. Task Force is no-code — you describe what you want
                and use the dashboard it builds. Turn this on to see the generated
                source, the flow graph, and the Workflows editor.
              </p>
              {isAdmin && (
                <p className="text-[11px] mt-2" style={{ color: "var(--accent)" }}>
                  Admins always have code access regardless of this setting.
                </p>
              )}
            </div>
            <div className="pt-1">
              {busy ? <Loader2 size={16} className="animate-spin t-text-mute" /> : (
                <Toggle checked={!!developerMode} onChange={onToggleDev} busy={busy} />
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Account links */}
      <section>
        <h2 className="text-[11px] uppercase tracking-[0.2em] font-mono t-text-mute mb-3">Account</h2>
        <div className="flex flex-col gap-3">
          <LinkRow to="/credentials" icon={KeyRound} title="Credentials" desc="Your API keys for connected services (encrypted)" />
          <LinkRow to="/settings/memory" icon={Brain} title="Builder Memory" desc="What the AI remembers about how you build" />
          <LinkRow to="/earnings" icon={Wallet} title="Earnings & Payout" desc={payoutPref ? `Paid out as ${payoutPref}` : "Credits or cash payout preference"} />
        </div>
      </section>
    </div>
  );
}

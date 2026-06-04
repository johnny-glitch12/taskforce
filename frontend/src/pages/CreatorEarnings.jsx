/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { Banknote, Coins, Trophy, Activity, Download, Loader2, ArrowDownRight } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function CreatorEarnings() {
  const { token } = useAuth() || {};
  const auth = { Authorization: `Bearer ${token}` };
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [sR, lR] = await Promise.all([
        fetch(`${API}/api/creator/earnings/summary?days=${days}`, { headers: auth }).then((r) => r.json()),
        fetch(`${API}/api/creator/earnings/ledger?limit=50`, { headers: auth }).then((r) => r.json()),
      ]);
      setSummary(sR);
      setLedger(lR);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [days]);

  async function downloadCsv() {
    setExporting(true);
    try {
      const r = await fetch(`${API}/api/creator/earnings/export.csv`, { headers: auth });
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `earnings_${Date.now()}.csv`;
      document.body.appendChild(a); a.click();
      a.remove(); URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
    finally { setExporting(false); }
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-6xl mx-auto px-6 py-10" data-testid="earnings-page">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4 mb-8">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] font-mono t-text-dim mb-2">
              Task Force AI / Creator Earnings
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold t-text flex items-center gap-3 mb-2">
              <Banknote className="text-cyan-400" size={36} /> Earnings
            </h1>
            <p className="text-sm t-text-mute max-w-xl">
              Revenue from Exchange listings, cash bounty wins, and credit bounty wins, rolled up across your portfolio.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1" data-testid="window-toggle">
              {[7, 30, 90, 365].map((d) => (
                <button
                  key={d}
                  data-testid={`window-${d}`}
                  onClick={() => setDays(d)}
                  className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] rounded-sm"
                  style={{
                    background: days === d ? "#22d3ee" : "transparent",
                    color: days === d ? "#0a0e1a" : "var(--text-mute)",
                    border: `1px solid ${days === d ? "#22d3ee" : "var(--border)"}`,
                  }}
                >
                  {d === 365 ? "1y" : `${d}d`}
                </button>
              ))}
            </div>
            <button
              data-testid="export-csv-btn"
              onClick={downloadCsv}
              disabled={exporting}
              className="px-3 py-1.5 rounded-sm text-[10px] font-mono uppercase tracking-[0.12em] inline-flex items-center gap-2"
              style={{ background: "var(--bg-input)", color: "var(--text)", border: "1px solid var(--border)" }}
            >
              {exporting ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />} CSV
            </button>
          </div>
        </div>

        {loading || !summary ? (
          <div className="text-center py-20 t-text-mute" data-testid="earnings-loading">
            <Loader2 className="animate-spin inline-block mr-2" size={14} /> Loading earnings…
          </div>
        ) : (
          <>
            {/* Top: lifetime hero + window stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <BigStat
                testid="lifetime-usd"
                label="Lifetime USD"
                value={`$${summary.lifetime.usd_total.toFixed(2)}`}
                sub={`$${summary.lifetime.stripe_usd.toFixed(2)} Stripe · $${summary.lifetime.cash_bounty_usd.toFixed(2)} Bounties`}
                accent="#22c55e"
                Icon={Banknote}
              />
              <BigStat
                testid="lifetime-credits"
                label="Lifetime Bounty Credits"
                value={`${summary.lifetime.credit_bounty_total.toLocaleString()} cr`}
                sub="Won from credit bounties"
                accent="#fbbf24"
                Icon={Coins}
              />
              <BigStat
                testid="window-runs"
                label={`Runs (${days}d)`}
                value={summary.window.deploy_runs.toLocaleString()}
                sub="Times your listings were executed"
                accent="#22d3ee"
                Icon={Activity}
              />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
              <MiniStat label="Stripe payouts" value={`$${summary.window.stripe_usd.toFixed(2)}`} sub={`${summary.window.stripe_tx_count} tx`} testid="window-stripe" />
              <MiniStat label="Cash bounty wins" value={`$${summary.window.cash_bounty_usd.toFixed(2)}`} sub={`${summary.window.cash_bounty_wins} won`} testid="window-cash-bounty" />
              <MiniStat label="Credit bounty wins" value={`${summary.window.credit_bounty_total.toLocaleString()} cr`} sub={`${summary.window.credit_bounty_wins} won`} testid="window-credit-bounty" />
              <MiniStat label="USD total this window" value={`$${summary.window.usd_total.toFixed(2)}`} sub={`${days}-day rolling`} testid="window-usd-total" />
            </div>

            {/* Ledger */}
            <div className="t-card rounded-sm" data-testid="earnings-ledger">
              <div className="flex items-center justify-between p-4 border-b border-[color:var(--border)]">
                <h2 className="text-lg font-semibold t-text">Recent activity</h2>
                <span className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim">
                  {ledger?.total || 0} entries
                </span>
              </div>
              {!(ledger?.items?.length) ? (
                <div className="text-center py-12 t-text-mute text-sm" data-testid="empty-ledger">
                  No revenue yet. Publish a listing on The Exchange or win a bounty to start earning.
                </div>
              ) : (
                <div className="divide-y divide-[color:var(--border)]">
                  {ledger.items.map((r) => <LedgerRow key={r.id + r.created_at} r={r} />)}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function BigStat({ label, value, sub, accent, Icon, testid }) {
  return (
    <div data-testid={testid} className="t-card rounded-sm p-5"
         style={{ borderColor: `${accent}55` }}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-sm flex items-center justify-center"
             style={{ background: `${accent}1a`, border: `1px solid ${accent}55` }}>
          <Icon size={18} style={{ color: accent }} />
        </div>
        <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim">{label}</div>
      </div>
      <div className="text-3xl font-bold t-text mb-1">{value}</div>
      <div className="text-[11px] font-mono t-text-mute">{sub}</div>
    </div>
  );
}

function MiniStat({ label, value, sub, testid }) {
  return (
    <div data-testid={testid} className="t-card rounded-sm p-3">
      <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-1">{label}</div>
      <div className="text-lg font-bold t-text">{value}</div>
      <div className="text-[10px] font-mono t-text-mute">{sub}</div>
    </div>
  );
}

function LedgerRow({ r }) {
  const isUsd = r.currency === "USD";
  const isWin = r.kind?.startsWith("bounty_won");
  const Icon = isWin ? Trophy : ArrowDownRight;
  const accent = isUsd ? "#22c55e" : "#fbbf24";
  const amountStr = isUsd ? `+$${Number(r.amount).toFixed(2)}` : `+${Number(r.amount).toLocaleString()} cr`;
  return (
    <div data-testid={`ledger-row-${r.id}`} className="flex items-center gap-3 p-4">
      <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0"
           style={{ background: `${accent}1a`, border: `1px solid ${accent}55` }}>
        <Icon size={14} style={{ color: accent }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm t-text truncate">{r.label}</div>
        <div className="text-[10px] font-mono t-text-mute">
          {r.kind.replace(/_/g, " ")} · {r.created_at?.slice(0, 16).replace("T", " ")}
        </div>
      </div>
      <div className="shrink-0 text-base font-bold font-mono" style={{ color: accent }}>{amountStr}</div>
    </div>
  );
}

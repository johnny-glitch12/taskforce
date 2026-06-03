/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  X, Loader2, Target, Coins, AlertTriangle, Banknote, ExternalLink,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  { id: "customer_support", label: "Customer Support" },
  { id: "sales", label: "Sales" },
  { id: "data_analysis", label: "Data Analysis" },
  { id: "coding", label: "Coding" },
  { id: "creative", label: "Creative" },
  { id: "finance", label: "Finance" },
  { id: "automation", label: "Automation" },
  { id: "other", label: "Other" },
];

const INTEGRATIONS_LIB = [
  "openai", "anthropic", "gemini", "slack", "gmail", "google_calendar",
  "google_sheets", "stripe", "twilio", "discord", "webhooks", "rest_api",
  "typeform", "notion", "airtable", "supabase", "hubspot",
];

const MIN_CASH = 10;
const MAX_CASH = 10_000;

export default function PostBountyModal({ onClose, onPosted }) {
  const { token } = useAuth() || {};
  const [rewardType, setRewardType] = useState("credits"); // 'credits' | 'cash'
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "automation",
    required_integrations: [],
    input_expectations: "",
    output_expectations: "",
    example_use_case: "",
    reward_amount: 500,        // credits
    cash_amount_usd: 50,       // USD
    deadline_days: 7,
    max_submissions: 10,
  });
  const [submitting, setSubmitting] = useState(false);
  const [balance, setBalance] = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/credits/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setBalance(d?.balance ?? null))
      .catch(() => {});
  }, [token]);

  function updateField(k, v) { setForm((f) => ({ ...f, [k]: v })); }
  function toggleIntegration(i) {
    setForm((f) => ({
      ...f,
      required_integrations: f.required_integrations.includes(i)
        ? f.required_integrations.filter((x) => x !== i)
        : [...f.required_integrations, i],
    }));
  }

  const canAffordCredits = balance == null || balance >= form.reward_amount;
  const cashAmount = Math.max(MIN_CASH, Math.min(MAX_CASH, Number(form.cash_amount_usd) || 0));

  async function submit() {
    if (form.title.trim().length < 8) { toast.error("Title must be at least 8 characters"); return; }
    if (form.description.trim().length < 20) { toast.error("Description must be at least 20 characters"); return; }

    let payload;
    if (rewardType === "credits") {
      if (form.reward_amount < 50) { toast.error("Reward must be at least 50 credits"); return; }
      if (!canAffordCredits) { toast.error(`Not enough credits — you have ${balance}`); return; }
      payload = {
        ...form,
        reward_type: "credits",
        reward_amount: form.reward_amount,
      };
    } else {
      if (cashAmount < MIN_CASH) { toast.error(`Cash bounties must be at least $${MIN_CASH}`); return; }
      payload = {
        ...form,
        reward_type: "cash",
        cash_amount_usd: cashAmount,
        reward_amount: 0,
        origin_url: window.location.origin,
      };
    }

    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/bounties`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const body = await r.json();
      if (!r.ok) {
        const msg = body.detail?.message || body.detail || `Failed (${r.status})`;
        toast.error(typeof msg === "string" ? msg : "Failed to post bounty");
        return;
      }
      if (rewardType === "cash" && body.checkout_url) {
        // Hand off to Stripe Checkout — frontend resumes at /payment/success?type=bounty.
        window.location.href = body.checkout_url;
        return;
      }
      onPosted?.(body.bounty);
    } catch (e) {
      toast.error(e.message || "Failed to post bounty");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      data-testid="post-bounty-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="t-card rounded-sm max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        style={{ borderColor: "#22d3ee55" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[color:var(--border)] sticky top-0 z-10" style={{ background: "var(--bg-card)" }}>
          <div className="flex items-center gap-3">
            <Target size={20} className="text-cyan-400" />
            <h2 className="text-lg font-semibold t-text">Post a bounty</h2>
          </div>
          <button data-testid="modal-close" onClick={onClose} className="t-text-mute hover:text-rose-400">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          <Field label="Title" hint="What do you need? (8–120 chars)">
            <input
              data-testid="bounty-title-input"
              value={form.title}
              onChange={(e) => updateField("title", e.target.value)}
              maxLength={120}
              placeholder="Need an agent that qualifies inbound Typeform leads"
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
            />
          </Field>

          <Field label="Description" hint="Full details — supports markdown (20–10,000 chars)">
            <textarea
              data-testid="bounty-desc-input"
              value={form.description}
              onChange={(e) => updateField("description", e.target.value)}
              rows={6}
              maxLength={10000}
              placeholder="Describe exactly what the agent should do, what inputs it'll see, what it should return, and any constraints..."
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Category">
              <select
                data-testid="bounty-category-select"
                value={form.category}
                onChange={(e) => updateField("category", e.target.value)}
                className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none"
                style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
              >
                {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </Field>

            <Field label="Deadline" hint="Days from now (3–30)">
              <input
                data-testid="bounty-deadline-input"
                type="number"
                min={3}
                max={30}
                value={form.deadline_days}
                onChange={(e) => updateField("deadline_days", parseInt(e.target.value, 10) || 7)}
                className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
                style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
              />
            </Field>
          </div>

          <Field label="Required integrations" hint="Click chips to toggle (optional)">
            <div className="flex flex-wrap gap-1.5">
              {INTEGRATIONS_LIB.map((i) => {
                const on = form.required_integrations.includes(i);
                return (
                  <button
                    key={i}
                    type="button"
                    data-testid={`integration-${i}`}
                    onClick={() => toggleIntegration(i)}
                    className="px-2.5 py-1 text-[10px] font-mono rounded-sm transition-all"
                    style={{
                      background: on ? "#22d3ee" : "transparent",
                      color: on ? "#0a0e1a" : "var(--text-mute)",
                      border: `1px solid ${on ? "#22d3ee" : "var(--border)"}`,
                    }}
                  >
                    {i}
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label="Input expectations" hint="What will you send to the agent? (optional)">
            <textarea
              data-testid="bounty-input-exp"
              value={form.input_expectations}
              onChange={(e) => updateField("input_expectations", e.target.value)}
              rows={2}
              maxLength={2000}
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
            />
          </Field>

          <Field label="Output expectations" hint="What should it return? (optional)">
            <textarea
              data-testid="bounty-output-exp"
              value={form.output_expectations}
              onChange={(e) => updateField("output_expectations", e.target.value)}
              rows={2}
              maxLength={2000}
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
            />
          </Field>

          <Field label="Example use case" hint="Walk through one real scenario (optional)">
            <textarea
              data-testid="bounty-example"
              value={form.example_use_case}
              onChange={(e) => updateField("example_use_case", e.target.value)}
              rows={2}
              maxLength={2000}
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
            />
          </Field>

          {/* Reward picker */}
          <div className="rounded-sm p-4" style={{
            background: "linear-gradient(180deg, #22d3ee0a, var(--bg-input))",
            border: "1px solid #22d3ee44",
          }}>
            <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-3 inline-flex items-center gap-1.5">
              <Coins size={11} /> Reward (held in escrow)
            </div>

            {/* Reward type toggle */}
            <div className="grid grid-cols-2 gap-2 mb-4" data-testid="reward-type-toggle">
              <button
                type="button"
                data-testid="reward-type-credits"
                onClick={() => setRewardType("credits")}
                className="py-2 text-[11px] font-mono uppercase tracking-[0.12em] rounded-sm inline-flex items-center justify-center gap-2 transition-all"
                style={{
                  background: rewardType === "credits" ? "#22d3ee" : "var(--bg-input)",
                  color: rewardType === "credits" ? "#0a0e1a" : "var(--text-mute)",
                  border: `1px solid ${rewardType === "credits" ? "#22d3ee" : "var(--border)"}`,
                }}
              >
                <Coins size={11} /> Credits
              </button>
              <button
                type="button"
                data-testid="reward-type-cash"
                onClick={() => setRewardType("cash")}
                className="py-2 text-[11px] font-mono uppercase tracking-[0.12em] rounded-sm inline-flex items-center justify-center gap-2 transition-all"
                style={{
                  background: rewardType === "cash" ? "#22c55e" : "var(--bg-input)",
                  color: rewardType === "cash" ? "#0a0e1a" : "var(--text-mute)",
                  border: `1px solid ${rewardType === "cash" ? "#22c55e" : "var(--border)"}`,
                }}
              >
                <Banknote size={11} /> Cash · USD
              </button>
            </div>

            {rewardType === "credits" ? (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex-1">
                    <input
                      data-testid="bounty-reward-input"
                      type="number"
                      min={50}
                      max={1000000}
                      step={50}
                      value={form.reward_amount}
                      onChange={(e) => updateField("reward_amount", Math.max(50, parseInt(e.target.value, 10) || 50))}
                      className="w-full px-3 py-2 text-2xl font-bold text-cyan-400 rounded-sm outline-none"
                      style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
                    />
                  </div>
                  <span className="text-sm t-text-mute font-mono">credits</span>
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="t-text-dim">Your balance: <span className="t-text">{balance != null ? balance.toLocaleString() : "—"}</span> cr</span>
                  {!canAffordCredits && (
                    <span className="text-rose-400 inline-flex items-center gap-1">
                      <AlertTriangle size={10} /> Top up needed
                    </span>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl font-bold text-green-400 font-mono">$</span>
                  <div className="flex-1">
                    <input
                      data-testid="bounty-cash-input"
                      type="number"
                      min={MIN_CASH}
                      max={MAX_CASH}
                      step={10}
                      value={form.cash_amount_usd}
                      onChange={(e) => updateField("cash_amount_usd", parseFloat(e.target.value) || MIN_CASH)}
                      className="w-full px-3 py-2 text-2xl font-bold text-green-400 rounded-sm outline-none"
                      style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
                    />
                  </div>
                  <span className="text-sm t-text-mute font-mono">USD</span>
                </div>
                <div className="text-[10px] font-mono t-text-dim leading-relaxed">
                  You&apos;ll be redirected to <span className="t-text">Stripe Checkout</span> after submit.
                  Funds are held in Stripe escrow and released to the winner&apos;s
                  Stripe Connect account on award (100% pass-through — no platform fee for v1).{" "}
                  <a href="/payouts" target="_blank" rel="noopener noreferrer"
                     className="text-cyan-400 hover:underline inline-flex items-center gap-1">
                    Creator setup <ExternalLink size={9} />
                  </a>
                </div>
                <div className="text-[10px] font-mono t-text-dim mt-2">
                  Range: ${MIN_CASH} – ${MAX_CASH.toLocaleString()}
                </div>
              </>
            )}
          </div>

          <Field label="Max submissions" hint="Cap on how many creators can submit (1–50)">
            <input
              data-testid="bounty-max-subs"
              type="number"
              min={1}
              max={50}
              value={form.max_submissions}
              onChange={(e) => updateField("max_submissions", parseInt(e.target.value, 10) || 10)}
              className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}
            />
          </Field>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-[color:var(--border)] sticky bottom-0" style={{ background: "var(--bg-card)" }}>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[10px] t-text-dim font-mono">
              {rewardType === "credits"
                ? `${form.reward_amount.toLocaleString()} credits will be held in escrow on submit.`
                : `$${cashAmount.toFixed(2)} will be charged via Stripe and held in escrow.`}
            </span>
            <div className="flex gap-2">
              <button
                data-testid="bounty-cancel-btn"
                onClick={onClose}
                className="px-4 py-2 text-xs font-mono uppercase tracking-[0.12em] t-text-mute hover:text-rose-400"
              >
                Cancel
              </button>
              <button
                data-testid="bounty-submit-btn"
                onClick={submit}
                disabled={submitting || (rewardType === "credits" && !canAffordCredits)}
                className="px-5 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
                style={{
                  background: rewardType === "cash"
                    ? "#22c55e"
                    : (canAffordCredits ? "#22d3ee" : "var(--bg-input)"),
                  color: rewardType === "cash" || canAffordCredits ? "#0a0e1a" : "var(--text-mute)",
                  opacity: submitting ? 0.5 : 1,
                  cursor: (rewardType === "credits" && !canAffordCredits) ? "not-allowed" : "pointer",
                }}
              >
                {submitting
                  ? <><Loader2 size={11} className="animate-spin" /> {rewardType === "cash" ? "Redirecting…" : "Posting…"}</>
                  : (rewardType === "cash" ? "Continue to Stripe →" : "Post bounty")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-1">{label}</div>
      {children}
      {hint && <div className="text-[10px] t-text-dim font-mono mt-1">{hint}</div>}
    </div>
  );
}

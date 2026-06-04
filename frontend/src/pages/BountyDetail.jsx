/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useParams, useNavigate, Link, useSearchParams } from "react-router-dom";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Target, Clock, Users, Trophy, ArrowLeft, Loader2,
  CheckCircle2, AlertTriangle, Coins, X, ExternalLink,
} from "lucide-react";
import SubmitToBountyModal from "@/components/SubmitToBountyModal";
import { fmtRemaining, fmtReward } from "@/pages/BountyBoard";

const API = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_COLOR = {
  open: "#22c55e",
  in_review: "#fbbf24",
  awarded: "#22d3ee",
  expired: "#64748b",
  cancelled: "#ef4444",
};

export default function BountyDetail() {
  const { id } = useParams();
  const { token, user } = useAuth() || {};
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const auth = { Authorization: `Bearer ${token}` };
  const [b, setB] = useState(null);
  const [subs, setSubs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showSubmit, setShowSubmit] = useState(false);
  const [awarding, setAwarding] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  async function refresh() {
    try {
      const r = await fetch(`${API}/api/bounties/${id}`, { headers: auth });
      if (!r.ok) {
        if (r.status === 404) { toast.error("Bounty not found"); navigate("/bounties"); return; }
        throw new Error(`HTTP ${r.status}`);
      }
      const body = await r.json();
      setB(body);
      const sR = await fetch(`${API}/api/bounties/${id}/submissions`, { headers: auth });
      if (sR.ok) setSubs(await sR.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [id]);

  // Auto-open the submit modal when arriving via ?submit=1 (e.g. from the
  // VibeBuildPage post-build CTA).
  useEffect(() => {
    if (!loading && b && search.get("submit") === "1" && !b.is_poster && !b.my_submission && b.status === "open") {
      setShowSubmit(true);
      // Clean the param so refresh doesn't keep reopening it.
      const next = new URLSearchParams(search);
      next.delete("submit");
      setSearch(next, { replace: true });
    }
    // eslint-disable-next-line
  }, [loading, b]);

  async function award(sub) {
    const isCash = b.reward_type === "cash";
    const rewardLabel = isCash
      ? `$${Number(b.reward_amount).toFixed(2)} USD`
      : `${b.reward_amount} credits`;
    if (!window.confirm(`Award ${rewardLabel} to ${sub.creator_name} for "${sub.agent_label}"?`)) return;
    setAwarding(sub.id);
    try {
      const r = await fetch(`${API}/api/bounties/${id}/award`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ submission_id: sub.id }),
      });
      const body = await r.json();
      if (!r.ok) {
        // Winner-not-onboarded case → structured error with onboarding URL.
        if (r.status === 409 && body.detail?.error === "WINNER_PAYOUTS_NOT_READY") {
          toast.error(
            `${sub.creator_name} hasn't completed Stripe payout setup yet. Ask them to visit /payouts before awarding.`,
            { duration: 6000 },
          );
          return;
        }
        toast.error(typeof body.detail === "string" ? body.detail : "Award failed");
        return;
      }
      toast.success(`Awarded ${rewardLabel} to ${sub.creator_name}!`);
      refresh();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAwarding(null);
    }
  }

  async function cancel() {
    const isCash = b.reward_type === "cash";
    const verb = isCash ? "fully refunded via Stripe" : "fully refunded to your credit wallet";
    if (!window.confirm(`Cancel this bounty? Your escrow will be ${verb}.`)) return;
    setCancelling(true);
    try {
      const r = await fetch(`${API}/api/bounties/${id}/cancel`, { method: "POST", headers: auth });
      const body = await r.json();
      if (!r.ok) { toast.error(typeof body.detail === "string" ? body.detail : "Cancel failed"); return; }
      const refundLabel = body.reward_type === "cash"
        ? `$${Number(body.refunded).toFixed(2)}`
        : `${body.refunded} cr`;
      toast.success(`Cancelled — ${refundLabel} refunded.`);
      refresh();
    } catch (e) { toast.error(e.message); }
    finally { setCancelling(false); }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <Loader2 className="animate-spin t-text-mute" size={24} />
      </div>
    );
  }
  if (!b) return null;

  const statusColor = STATUS_COLOR[b.status] || "#94a3b8";
  const canSubmit = b.status === "open" && !b.is_poster && !b.my_submission;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-5xl mx-auto px-6 py-10" data-testid="bounty-detail-page">
        <Link to="/bounties" className="text-xs t-text-mute hover:text-cyan-400 inline-flex items-center gap-1 mb-6 font-mono">
          <ArrowLeft size={12} /> Back to Bounty Board
        </Link>

        {/* Header card */}
        <div className="t-card rounded-sm p-6 mb-6">
          <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span
                  data-testid="bounty-status-pill"
                  className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm"
                  style={{ background: `${statusColor}22`, color: statusColor, border: `1px solid ${statusColor}55` }}
                >
                  {b.status.replace("_", " ")}
                </span>
                <span className="text-[10px] font-mono t-text-dim uppercase tracking-[0.15em]">{b.category}</span>
              </div>
              <h1 data-testid="bounty-title" className="text-3xl font-bold t-text mb-2">{b.title}</h1>
              <div className="text-xs t-text-mute font-mono">
                Posted by <span className="t-text">{b.poster_name}</span> · {b.poster_email}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-1">
                Reward {b.reward_type === "cash" ? "(USD)" : "(credits)"}
              </div>
              {(() => {
                const r = fmtReward(b);
                return (
                  <div className="text-4xl font-bold leading-none" style={{ color: r.color }}>
                    {r.value}<span className="text-sm t-text-mute ml-2">{r.unit}</span>
                  </div>
                );
              })()}
              {b.status === "open" && (
                <div className="text-xs t-text-mute mt-2 inline-flex items-center gap-1 justify-end">
                  <Clock size={11} /> Ends in {fmtRemaining(b.seconds_remaining)}
                </div>
              )}
              {b.status === "awarded" && (
                <div className="text-xs text-cyan-400 mt-2 inline-flex items-center gap-1 justify-end font-mono">
                  <Trophy size={11} /> Awarded
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2 mt-4">
            {canSubmit && (
              <button
                data-testid="open-submit-modal-btn"
                onClick={() => setShowSubmit(true)}
                className="px-5 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
                style={{ background: "#22d3ee", color: "#0a0e1a" }}
              >
                <Target size={12} /> Submit a solution
              </button>
            )}
            {b.is_poster && b.status === "open" && (b.submission_count || 0) === 0 && (
              <button
                data-testid="bounty-cancel-btn"
                onClick={cancel}
                disabled={cancelling}
                className="px-5 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em]"
                style={{ color: "#ef4444", border: "1px solid #ef444455", opacity: cancelling ? 0.5 : 1 }}
              >
                {cancelling ? "Cancelling…" : "Cancel & refund"}
              </button>
            )}
            {b.my_submission && (
              <span
                data-testid="my-submission-badge"
                className="px-3 py-2 text-[11px] font-mono uppercase tracking-[0.12em] rounded-sm inline-flex items-center gap-1.5"
                style={{ color: "#22c55e", background: "#22c55e1a", border: "1px solid #22c55e55" }}
              >
                <CheckCircle2 size={11} /> You submitted: {b.my_submission.agent_label}
              </span>
            )}
          </div>
        </div>

        {/* Description + Spec grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2 t-card rounded-sm p-6">
            <SectionLabel>Description</SectionLabel>
            <div data-testid="bounty-description" className="text-sm t-text whitespace-pre-wrap leading-relaxed">
              {b.description}
            </div>
          </div>
          <div className="space-y-4">
            <div className="t-card rounded-sm p-5">
              <SectionLabel>Required integrations</SectionLabel>
              {(b.required_integrations?.length || 0) === 0 ? (
                <div className="text-xs t-text-mute font-mono">None specified</div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {b.required_integrations.map((i) => (
                    <span key={i} className="px-2 py-0.5 text-[10px] font-mono rounded-sm"
                          style={{ background: "#a855f71a", color: "#c084fc", border: "1px solid #a855f755" }}>
                      {i}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <SmallBlock label="Input expected" testid="bounty-input-exp" content={b.input_expectations} />
            <SmallBlock label="Output expected" testid="bounty-output-exp" content={b.output_expectations} />
            <SmallBlock label="Example use case" testid="bounty-example" content={b.example_use_case} />
            <div className="t-card rounded-sm p-4 text-[11px] font-mono t-text-mute">
              <div className="flex items-center justify-between mb-1">
                <span>Submissions</span>
                <span className="t-text">{b.submission_count || 0}/{b.max_submissions}</span>
              </div>
              <div className="flex items-center justify-between mb-1">
                <span>Escrow</span>
                <span style={{ color: b.escrow_status === "held" ? "#22c55e" : "#94a3b8" }}>
                  {b.escrow_status}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Posted</span>
                <span className="t-text">{b.created_at?.slice(0, 10)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Submissions */}
        <div className="t-card rounded-sm p-6" data-testid="submissions-section">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold t-text">Submissions</h2>
            <span className="text-[10px] font-mono t-text-dim uppercase tracking-[0.15em]">
              {subs?.total || 0} total
              {!b.is_poster && user?.role !== "admin" && " · poster-only visibility"}
            </span>
          </div>
          {!subs?.submissions?.length ? (
            <div className="text-center py-10 t-text-mute text-sm" data-testid="no-submissions">
              {b.is_poster
                ? "No submissions yet. Creators are seeing your bounty."
                : (b.my_submission ? "Only you and the poster can see submissions." : "No submissions yet.")}
            </div>
          ) : (
            <div className="space-y-3" data-testid="submissions-list">
              {subs.submissions.map((s) => (
                <SubmissionRow
                  key={s.id}
                  s={s}
                  isPoster={b.is_poster}
                  bountyStatus={b.status}
                  rewardAmount={b.reward_amount}
                  onAward={() => award(s)}
                  awarding={awarding === s.id}
                  isAdmin={user?.role === "admin"}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {showSubmit && (
        <SubmitToBountyModal
          bounty={b}
          onClose={() => setShowSubmit(false)}
          onSubmitted={() => { setShowSubmit(false); refresh(); }}
        />
      )}
    </div>
  );
}

function SectionLabel({ children }) {
  return <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-3">{children}</div>;
}

function SmallBlock({ label, content, testid }) {
  if (!content?.trim()) return null;
  return (
    <div className="t-card rounded-sm p-4">
      <SectionLabel>{label}</SectionLabel>
      <div className="text-xs t-text-mute whitespace-pre-wrap font-mono" data-testid={testid}>{content}</div>
    </div>
  );
}

function SubmissionRow({ s, isPoster, bountyStatus, rewardAmount, rewardType, onAward, awarding, isAdmin }) {
  const isWinner = s.status === "winner";
  const isRejected = s.status === "rejected";
  const isCash = rewardType === "cash";
  const awardLabel = isCash
    ? `Award $${Number(rewardAmount).toFixed(2)}`
    : `Award ${rewardAmount} cr`;
  return (
    <div
      data-testid={`submission-${s.id}`}
      className="rounded-sm p-4 transition-all"
      style={{
        background: isWinner ? "#22d3ee0a" : "var(--bg-input)",
        border: `1px solid ${isWinner ? "#22d3ee88" : "var(--border)"}`,
        opacity: isRejected ? 0.5 : 1,
      }}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium t-text">{s.creator_name}</span>
            {isWinner && (
              <span data-testid={`winner-badge-${s.id}`}
                    className="px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.15em] rounded-sm inline-flex items-center gap-1"
                    style={{ background: "#22d3ee", color: "#0a0e1a" }}>
                <Trophy size={9} /> Winner
              </span>
            )}
            {isRejected && (
              <span className="px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.15em] rounded-sm"
                    style={{ background: "#64748b22", color: "#94a3b8", border: "1px solid #64748b55" }}>
                Not selected
              </span>
            )}
          </div>
          <div className="text-xs t-text-mute font-mono mb-2">
            Submitted {s.submitted_at?.slice(0, 16).replace("T", " ")} · {s.agent_source}: <span className="t-text">{s.agent_label}</span>
          </div>
          <div className="text-xs t-text whitespace-pre-wrap leading-relaxed">{s.pitch}</div>
        </div>
        {(isPoster || isAdmin) && bountyStatus === "open" && !isWinner && !isRejected && (
          <button
            data-testid={`award-btn-${s.id}`}
            onClick={onAward}
            disabled={awarding}
            className="px-4 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2 shrink-0"
            style={{ background: "#22d3ee", color: "#0a0e1a", opacity: awarding ? 0.5 : 1 }}
          >
            {awarding ? <><Loader2 size={11} className="animate-spin" /> Awarding…</> : <><Trophy size={11} /> {awardLabel}</>}
          </button>
        )}
        {s.agent_source === "exchange" && (
          <Link
            to={`/marketplace/${s.source_id}`}
            className="text-[11px] font-mono t-text-mute hover:text-cyan-400 inline-flex items-center gap-1 shrink-0"
          >
            View listing <ExternalLink size={10} />
          </Link>
        )}
      </div>
    </div>
  );
}

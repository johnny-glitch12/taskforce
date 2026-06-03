/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import { Star, MessageSquare, Trash2, Reply, Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ReviewsPanel({ listingId, ownerUserId }) {
  const { token, user } = useAuth() || {};
  const auth = token ? { Authorization: `Bearer ${token}` } : {};
  const isOwner = !!user && user.id === ownerUserId;

  const [reviews, setReviews] = useState([]);
  const [aggregate, setAggregate] = useState({ reviews_count: 0, reviews_avg: 0 });
  const [histogram, setHistogram] = useState({ "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 });
  const [myReview, setMyReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [replyOpen, setReplyOpen] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [replying, setReplying] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/exchange/listings/${listingId}/reviews`);
      if (r.ok) {
        const d = await r.json();
        setReviews(d.items || []);
        setAggregate(d.aggregate || { reviews_count: 0, reviews_avg: 0 });
        setHistogram(d.histogram || { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 });
      }
      if (token) {
        const myR = await fetch(`${API}/api/exchange/listings/${listingId}/reviews/my-review`, { headers: auth });
        if (myR.ok) {
          const d = await myR.json();
          setMyReview(d.review || null);
        }
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [listingId, token]);

  async function submit() {
    if (comment.trim().length < 10) { toast.error("Comment must be at least 10 characters"); return; }
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/exchange/listings/${listingId}/reviews`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ stars, comment: comment.trim() }),
      });
      const body = await r.json();
      if (!r.ok) { toast.error(typeof body.detail === "string" ? body.detail : "Submit failed"); return; }
      toast.success("Thanks for the review!");
      setComment(""); setStars(5);
      refresh();
    } catch (e) { toast.error(e.message); }
    finally { setSubmitting(false); }
  }

  async function deleteMyReview() {
    if (!myReview || !window.confirm("Delete your review?")) return;
    try {
      const r = await fetch(`${API}/api/exchange/reviews/${myReview.id}`, { method: "DELETE", headers: auth });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        toast.error(b.detail || "Delete failed");
        return;
      }
      toast.success("Review deleted");
      setMyReview(null);
      refresh();
    } catch (e) { toast.error(e.message); }
  }

  async function postReply(reviewId) {
    if (replyText.trim().length < 1) { toast.error("Type a reply"); return; }
    setReplying(true);
    try {
      const r = await fetch(`${API}/api/exchange/reviews/${reviewId}/reply`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ content: replyText.trim() }),
      });
      const body = await r.json();
      if (!r.ok) { toast.error(typeof body.detail === "string" ? body.detail : "Reply failed"); return; }
      toast.success("Reply posted");
      setReplyOpen(null); setReplyText("");
      refresh();
    } catch (e) { toast.error(e.message); }
    finally { setReplying(false); }
  }

  return (
    <div data-testid="reviews-panel" className="space-y-6">
      {/* Aggregate header */}
      <div className="t-card rounded-sm p-5 grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="flex flex-col items-center justify-center text-center">
          <div className="text-5xl font-bold t-text mb-1" data-testid="agg-avg">{aggregate.reviews_avg.toFixed(1)}</div>
          <StarBar stars={Math.round(aggregate.reviews_avg)} size={14} />
          <div className="text-[11px] font-mono t-text-mute mt-1" data-testid="agg-count">
            {aggregate.reviews_count} {aggregate.reviews_count === 1 ? "review" : "reviews"}
          </div>
        </div>
        <div className="md:col-span-2 space-y-1">
          {[5, 4, 3, 2, 1].map((s) => {
            const n = histogram[String(s)] || 0;
            const pct = aggregate.reviews_count ? (n / aggregate.reviews_count) * 100 : 0;
            return (
              <div key={s} className="flex items-center gap-2 text-[11px] font-mono t-text-mute">
                <span className="w-6">{s}★</span>
                <div className="flex-1 h-2 rounded-sm overflow-hidden" style={{ background: "var(--bg-input)" }}>
                  <div className="h-full bg-amber-400" style={{ width: `${pct}%` }} />
                </div>
                <span className="w-8 text-right">{n}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Review submit form */}
      {token && !isOwner && !myReview && (
        <div className="t-card rounded-sm p-5" data-testid="leave-review-card">
          <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-3">Leave a review</div>
          <div className="flex gap-1 mb-3" data-testid="star-picker">
            {[1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                data-testid={`star-${s}`}
                onClick={() => setStars(s)}
                aria-label={`${s} star${s > 1 ? "s" : ""}`}
              >
                <Star size={22} className={s <= stars ? "fill-amber-400 text-amber-400" : "text-zinc-600"} />
              </button>
            ))}
          </div>
          <textarea
            data-testid="review-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            maxLength={1500}
            placeholder="What did you build with it? How well does it perform?"
            className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
            style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[10px] font-mono t-text-dim">{comment.length}/1500 · min 10 chars</span>
            <button
              data-testid="submit-review-btn"
              onClick={submit}
              disabled={submitting || comment.trim().length < 10}
              className="px-4 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
              style={{
                background: comment.trim().length >= 10 ? "#22d3ee" : "var(--bg-input)",
                color: comment.trim().length >= 10 ? "#0a0e1a" : "var(--text-mute)",
                opacity: submitting ? 0.5 : 1,
              }}
            >
              {submitting ? <Loader2 size={11} className="animate-spin" /> : <MessageSquare size={11} />} Post review
            </button>
          </div>
        </div>
      )}

      {myReview && (
        <div className="t-card rounded-sm p-4 flex items-center gap-3" data-testid="my-review-summary"
             style={{ borderColor: "#22c55e55", background: "rgba(34,197,94,0.04)" }}>
          <CheckCircle2 size={16} className="text-green-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-mono t-text-dim uppercase tracking-[0.15em]">Your review</div>
            <div className="flex items-center gap-2 mt-0.5">
              <StarBar stars={myReview.stars} size={12} />
              <span className="text-xs t-text truncate">{myReview.comment}</span>
            </div>
          </div>
          <button
            data-testid="delete-my-review"
            onClick={deleteMyReview}
            className="shrink-0 text-[10px] font-mono uppercase tracking-[0.12em] t-text-mute hover:text-rose-400 inline-flex items-center gap-1"
          >
            <Trash2 size={10} /> Delete
          </button>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="text-center py-8 t-text-mute text-sm" data-testid="reviews-loading">
          <Loader2 size={14} className="animate-spin inline-block mr-2" /> Loading reviews…
        </div>
      ) : !reviews.length ? (
        <div className="text-center py-8 t-text-mute text-sm" data-testid="reviews-empty">
          No reviews yet. Be the first to leave one.
        </div>
      ) : (
        <div className="space-y-3" data-testid="reviews-list">
          {reviews.map((r) => (
            <div key={r.id} className="t-card rounded-sm p-4" data-testid={`review-${r.id}`}>
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-sm flex items-center justify-center text-xs font-bold t-text"
                       style={{ background: "rgba(34,211,238,0.15)", border: "1px solid rgba(34,211,238,0.3)" }}>
                    {(r.user_name || "U")[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-sm t-text leading-tight">{r.user_name}</div>
                    <div className="text-[10px] font-mono t-text-mute">{r.created_at?.slice(0, 10)}</div>
                  </div>
                </div>
                <StarBar stars={r.stars} size={13} />
              </div>
              <div className="text-sm t-text whitespace-pre-wrap leading-relaxed">{r.comment}</div>
              {r.owner_reply ? (
                <div className="mt-3 ml-3 pl-3 border-l-2 border-cyan-500/30">
                  <div className="text-[10px] uppercase tracking-[0.15em] font-mono text-cyan-400 mb-1 inline-flex items-center gap-1">
                    <Reply size={10} /> Reply from {r.owner_reply.author_name || "creator"}
                  </div>
                  <div className="text-xs t-text-sub whitespace-pre-wrap" data-testid={`reply-${r.id}`}>
                    {r.owner_reply.content}
                  </div>
                  <div className="text-[10px] font-mono t-text-dim mt-1">{r.owner_reply.created_at?.slice(0, 10)}</div>
                </div>
              ) : isOwner ? (
                replyOpen === r.id ? (
                  <div className="mt-3 ml-3 pl-3 border-l-2 border-cyan-500/30">
                    <textarea
                      data-testid={`reply-input-${r.id}`}
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      rows={2}
                      maxLength={1500}
                      placeholder="Address the feedback…"
                      className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
                      style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        data-testid={`reply-submit-${r.id}`}
                        onClick={() => postReply(r.id)}
                        disabled={replying || replyText.trim().length < 1}
                        className="px-3 py-1.5 rounded-sm text-[10px] font-mono uppercase tracking-[0.12em] inline-flex items-center gap-1"
                        style={{ background: "#22d3ee", color: "#0a0e1a", opacity: replying ? 0.5 : 1 }}
                      >
                        {replying ? <Loader2 size={10} className="animate-spin" /> : <Reply size={10} />} Post reply
                      </button>
                      <button
                        onClick={() => { setReplyOpen(null); setReplyText(""); }}
                        className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.12em] t-text-mute"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    data-testid={`open-reply-${r.id}`}
                    onClick={() => setReplyOpen(r.id)}
                    className="mt-2 text-[10px] font-mono uppercase tracking-[0.12em] t-text-mute hover:text-cyan-400 inline-flex items-center gap-1"
                  >
                    <Reply size={10} /> Reply
                  </button>
                )
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StarBar({ stars, size = 14 }) {
  return (
    <div className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          size={size}
          className={s <= stars ? "fill-amber-400 text-amber-400" : "text-zinc-600"}
        />
      ))}
    </div>
  );
}

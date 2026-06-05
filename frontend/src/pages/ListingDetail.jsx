/* eslint-disable react/prop-types */
/**
 * ListingDetail — single Exchange listing page with a credit-based Deploy
 * button. No more Stripe per-purchase — buyers pay from their wallet.
 */
import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useCredits } from "@/lib/credits";
import { Loader2, ArrowLeft, Bot, Trophy, Coins, Zap, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import ReviewsPanel from "@/components/ReviewsPanel";
import TopUpModal from "@/components/TopUpModal";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function ListingDetail() {
  const { id } = useParams();
  const { user, token } = useAuth() || {};
  const { credits, refreshCredits } = useCredits();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(false);
  const [showTopup, setShowTopup] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/exchange/listings/${id}`);
        if (r.ok) setListing(await r.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [id]);

  const handlePurchase = async () => {
    if (!token) { navigate("/login"); return; }
    setPurchasing(true);
    try {
      const r = await fetch(`${API}/api/exchange/purchase/${id}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await r.json();
      if (!r.ok) { toast.error(data.detail || "Purchase failed."); return; }
      if (data.error === "INSUFFICIENT_CREDITS") {
        toast.error(`Need ${data.required} credits (you have ${data.available})`);
        setShowTopup(true);
        return;
      }
      if (data.already_owned) {
        toast.info("You already own this agent.");
        navigate("/my-deployments");
        return;
      }
      toast.success(data.credits_charged > 0 ? `Deployed · −${data.credits_charged} cr` : "Deployed!");
      refreshCredits();
      navigate("/my-deployments");
    } catch { toast.error("Network error."); }
    finally { setPurchasing(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <Loader2 className="animate-spin t-text-mute" size={24} />
      </div>
    );
  }
  if (!listing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <p className="t-text-mute text-sm">Listing not found.</p>
      </div>
    );
  }
  const avatarColor = listing.avatar_color || "#22d3ee";
  const priceCredits = Number(listing.price_credits || 0);
  const isFree = priceCredits === 0;
  const isOwner = !!user && user.id === listing.user_id;
  const totalCredits = credits?.total || 0;
  const unlimited = !!credits?.unlimited;
  const canAfford = unlimited || totalCredits >= priceCredits;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-5xl mx-auto px-6 py-10" data-testid="listing-detail-page">
        <Link to="/exchange" className="text-xs t-text-mute hover:text-cyan-400 inline-flex items-center gap-1 mb-6 font-mono">
          <ArrowLeft size={12} /> Back to The Exchange
        </Link>

        <div className="t-card rounded-sm p-6 mb-6">
          <div className="flex items-start gap-5 flex-wrap">
            <div
              className="w-20 h-20 rounded-sm flex items-center justify-center shrink-0"
              style={{ background: `${avatarColor}1a`, border: `1px solid ${avatarColor}55` }}
            >
              {listing.avatar_url ? (
                <img src={`${API}${listing.avatar_url}`} alt={listing.name} className="w-full h-full object-cover rounded-sm" />
              ) : (
                <Bot size={28} style={{ color: avatarColor }} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <h1 data-testid="listing-name" className="text-2xl font-bold t-text">{listing.name}</h1>
                {listing.bounty_winner && (
                  <span className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm inline-flex items-center gap-1"
                        style={{ background: "linear-gradient(90deg, #f59e0b, #fbbf24)", color: "#0a0e1a" }}>
                    <Trophy size={10} /> Bounty Winner
                  </span>
                )}
              </div>
              <div className="text-xs t-text-mute font-mono mb-3">
                {listing.category} · by {listing.creator_name || listing.creator_email}
              </div>
              <p className="text-sm t-text whitespace-pre-wrap leading-relaxed">{listing.description}</p>
            </div>

            {/* Pricing / Deploy column */}
            <div className="shrink-0 w-full sm:w-[220px]">
              <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-1.5">Price</div>
              {isFree ? (
                <div data-testid="listing-price" className="text-2xl font-bold text-emerald-400 font-mono mb-3">FREE</div>
              ) : (
                <div data-testid="listing-price" className="flex items-baseline gap-1.5 mb-3">
                  <Coins size={14} className="text-cyan-400" />
                  <span className="text-2xl font-bold text-cyan-400 font-mono tabular-nums">{priceCredits.toLocaleString()}</span>
                  <span className="text-[11px] t-text-dim font-mono">cr</span>
                </div>
              )}

              {isOwner ? (
                <div className="text-[11px] t-text-dim font-mono">Your listing</div>
              ) : (
                <>
                  <button
                    data-testid="listing-deploy-btn"
                    onClick={handlePurchase}
                    disabled={purchasing || (!isFree && !canAfford)}
                    className={`w-full px-3 py-2.5 text-[11px] font-bold tracking-[0.18em] uppercase font-mono rounded-sm flex items-center justify-center gap-1.5 transition-all ${
                      !purchasing && (isFree || canAfford)
                        ? "bg-cyan-400 text-black hover:bg-cyan-300"
                        : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                    }`}
                  >
                    {purchasing ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
                    {purchasing ? "Deploying..." : isFree ? "Deploy Free" : `Deploy · ${priceCredits} cr`}
                  </button>
                  {!isFree && !canAfford && (
                    <button
                      data-testid="listing-topup-link"
                      onClick={() => setShowTopup(true)}
                      className="w-full mt-2 text-[10px] font-mono uppercase tracking-[0.15em] text-cyan-400 hover:text-cyan-300 inline-flex items-center justify-center gap-1"
                    >
                      <AlertTriangle size={10} /> Top up to deploy
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Reviews panel */}
        <h2 className="text-lg font-semibold t-text mb-4">Reviews</h2>
        <ReviewsPanel listingId={listing.id} ownerUserId={listing.user_id} />
      </div>

      {showTopup && <TopUpModal onClose={() => setShowTopup(false)} />}
    </div>
  );
}

/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@/App";
import { Loader2, ArrowLeft, Bot, Trophy } from "lucide-react";
import ReviewsPanel from "@/components/ReviewsPanel";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function ListingDetail() {
  const { id } = useParams();
  const { user } = useAuth() || {};
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/exchange/listings/${id}`);
        if (r.ok) setListing(await r.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [id]);

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
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="max-w-5xl mx-auto px-6 py-10" data-testid="listing-detail-page">
        <Link to="/marketplace" className="text-xs t-text-mute hover:text-cyan-400 inline-flex items-center gap-1 mb-6 font-mono">
          <ArrowLeft size={12} /> Back to Marketplace
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
                {listing.category} · by {listing.creator_email}
              </div>
              <p className="text-sm t-text whitespace-pre-wrap leading-relaxed">{listing.description}</p>
            </div>
            <div className="text-right shrink-0">
              <div className="text-[10px] uppercase tracking-[0.15em] font-mono t-text-dim mb-1">Pricing</div>
              <div className="font-mono text-xs t-text">
                ${Number(listing.rent_price || 0).toFixed(2)}/mo · ${Number(listing.buy_price || 0).toFixed(2)} own
              </div>
            </div>
          </div>
        </div>

        {/* Reviews panel */}
        <h2 className="text-lg font-semibold t-text mb-4">Reviews</h2>
        <ReviewsPanel listingId={listing.id} ownerUserId={listing.user_id} />
      </div>
    </div>
  );
}

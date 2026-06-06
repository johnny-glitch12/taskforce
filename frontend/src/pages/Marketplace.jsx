import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/App";
import { useCredits } from "@/lib/credits";
import { toast } from "sonner";
import DirectPublishModal from "../components/DirectPublishModal";
import TopUpModal from "../components/TopUpModal";
import {
  Search, Heart, Star, Shield, ChevronRight, TrendingUp,
  Sparkles, BadgeCheck, Play, Upload, Trophy,
  Headphones, BarChart3, Code2, Palette, DollarSign, MessageSquare,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const categories = [
  { id: "all", label: "All Agents", icon: Sparkles },
  { id: "support", label: "Customer Support", icon: Headphones },
  { id: "sales", label: "Sales Outreach", icon: MessageSquare },
  { id: "data", label: "Data Analysis", icon: BarChart3 },
  { id: "coding", label: "Coding", icon: Code2 },
  { id: "creative", label: "Creative", icon: Palette },
  { id: "finance", label: "Finance", icon: DollarSign },
];

function SearchHero({ searchQuery, setSearchQuery }) {
  return (
    <div className="text-center mb-10">
      <div className="inline-flex items-center gap-2 mb-5 px-3 py-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <span
          className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"
          style={{ boxShadow: "0 0 8px rgba(34,211,238,0.7)" }}
        />
        <span className="text-[10px] tracking-[0.25em] uppercase font-mono" style={{ color: "rgba(255,255,255,0.55)" }}>
          The Exchange · Live Marketplace
        </span>
      </div>
      <h1
        data-testid="marketplace-title"
        className="text-3xl sm:text-4xl lg:text-[3.25rem] font-bold tracking-[-0.02em] t-text mb-3"
        style={{ fontFamily: "'Outfit', sans-serif" }}
      >
        Production-ready <span className="text-gradient-cyan">AI agents</span>
      </h1>
      <p className="text-[15px] t-text-sub mb-8 max-w-md mx-auto">
        Discover, deploy, and earn. Buy with credits — instant, no checkout.
      </p>
      <div className="max-w-xl mx-auto relative" data-testid="marketplace-search">
        <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 t-text-mute" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search agents…"
          data-testid="marketplace-search-input"
          className="w-full t-input focus:outline-none focus:border-cyan-400/40 transition-all pl-12 pr-5 py-4 text-[15px] rounded-sm"
          style={{ border: '1px solid var(--input-border)' }}
        />
      </div>
    </div>
  );
}

function CategoryPills({ activeCategory, setActiveCategory }) {
  return (
    <div data-testid="category-pills" className="flex gap-2 overflow-x-auto pb-2 mb-10 scrollbar-hide">
      {categories.map((cat) => {
        const Icon = cat.icon;
        const isActive = activeCategory === cat.id;
        return (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            data-testid={`category-${cat.id}`}
            className={`flex items-center gap-2 px-4 py-2 text-[13px] rounded-sm whitespace-nowrap transition-all duration-200 ${
              isActive
                ? "bg-cyan-400 text-black font-bold shadow-[0_0_15px_rgba(34,211,238,0.35)]"
                : "t-text-sub"
            }`}
            style={!isActive ? { background: 'var(--bg-card)', border: '1px solid var(--border)' } : {}}
          >
            <Icon size={13} />
            {cat.label}
          </button>
        );
      })}
    </div>
  );
}

function CreatorSpotlight() {
  const [creators, setCreators] = useState([]);
  useEffect(() => {
    fetch(`${API}/api/creators`).then(r => r.json()).then(setCreators).catch(() => {});
  }, []);
  if (!creators.length) return null;
  return (
    <section className="mb-14" data-testid="creator-spotlight">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
          Top Operators
        </h2>
        <span className="text-[12px] t-text-dim">Top-rated creators</span>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-3 scrollbar-hide">
        {creators.map((c) => (
          <Link
            to={`/creator/${c.id}`}
            key={c.id}
            data-testid={`creator-card-${c.id}`}
            className="min-w-[260px] rounded-sm p-5 transition-all duration-300 hover:border-cyan-400/30 hover:shadow-lg group flex-shrink-0"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-sm flex items-center justify-center text-white text-sm font-semibold" style={{ background: c.color }}>
                {c.initial}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[14px] font-medium t-text truncate">{c.name}</span>
                  {c.verified && <BadgeCheck size={13} className="text-cyan-400 flex-shrink-0" />}
                </div>
                <span className="text-[12px] t-text-sub">{c.username}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] bg-cyan-400/10 text-cyan-400 px-2 py-0.5 rounded-sm font-mono font-medium">Operator</span>
              <span className="text-[11px] t-text-sub flex items-center gap-1"><Shield size={10} /> {c.trustScore}</span>
            </div>
            <p className="text-[13px] t-text-mute mb-3">{c.heroStat}</p>
            <div className="flex gap-1.5">
              {c.agentPreviews.map((a, i) => (
                <span key={i} className="text-[10px] t-text-sub px-2 py-1 rounded-md truncate" style={{ background: 'var(--bg-card-hover)' }}>{a}</span>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-1 text-[12px] text-cyan-400 group-hover:text-cyan-300 transition-colors">
              View Portfolio <ChevronRight size={12} />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function AgentCard({ agent, index }) {
  const [saved, setSaved] = useState(false);
  const creator = {
    id: agent.creator_id,
    initial: agent.creator_initial,
    color: agent.creator_color,
    username: agent.creator_username,
    verified: agent.creator_verified,
  };

  return (
    <div
      data-testid={`agent-card-${agent.id}`}
      className="agent-card-glow rounded-sm overflow-hidden transition-all duration-300 hover:border-cyan-400/30 hover:-translate-y-1 hover:shadow-[0_12px_40px_rgba(0,0,0,0.35),0_0_30px_rgba(34,211,238,0.05)] group opacity-0 animate-fade-in-up relative"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: `${index * 60}ms`, animationFillMode: "forwards" }}
    >
      {/* Animated top-border glow on hover */}
      <span
        aria-hidden="true"
        className="absolute top-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.6), transparent)" }}
      />
      {/* Image / Gradient */}
      <div className="h-36 relative overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
        {agent.image ? (
          <img src={agent.image} alt={agent.shortTitle} className="w-full h-full object-cover opacity-40 group-hover:opacity-55 group-hover:scale-105 transition-all duration-700" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-violet-950/80 to-zinc-950 opacity-60" />
        )}
        {agent.isOfficial && (
          <span
            data-testid={`official-badge-${agent.id}`}
            title="TaskForce Official agent"
            className="absolute top-3 left-3 text-[10px] backdrop-blur-sm px-2.5 py-1 rounded-sm font-bold flex items-center gap-1"
            style={{
              background: "linear-gradient(90deg, #22d3ee, #06b6d4)",
              color: "#0a0e1a",
              boxShadow: "0 0 14px rgba(34,211,238,0.35)",
            }}
          >
            <BadgeCheck size={10} className="shrink-0" />
            <span className="font-mono uppercase tracking-[0.1em]">Official</span>
          </span>
        )}
        {agent.trendingLabel && !agent.isOfficial && (
          <span className="absolute top-3 left-3 text-[10px] bg-cyan-400/90 backdrop-blur-sm text-black px-2.5 py-1 rounded-sm font-bold flex items-center gap-1">
            <TrendingUp size={10} /> {agent.trendingLabel}
          </span>
        )}
        {agent.bountyWinner && (
          <span
            data-testid={`bounty-winner-badge-${agent.id}`}
            title={agent.bountyTitle ? `Bounty: ${agent.bountyTitle}` : "Bounty winner"}
            className="absolute bottom-3 left-3 text-[10px] backdrop-blur-sm px-2.5 py-1 rounded-sm font-bold flex items-center gap-1 max-w-[80%]"
            style={{
              background: "linear-gradient(90deg, #fbbf24, #f59e0b)",
              color: "#0a0e1a",
              boxShadow: "0 0 12px rgba(251,191,36,0.3)",
            }}
          >
            <Trophy size={10} className="shrink-0" />
            <span className="truncate font-mono uppercase tracking-[0.1em]">Bounty Winner</span>
          </span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); setSaved(!saved); }}
          data-testid={`agent-save-${agent.id}`}
          className="absolute top-3 right-3 w-8 h-8 rounded-sm bg-black/40 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-black/60"
        >
          <Heart size={14} className={saved ? "fill-[#8B5CF6] text-cyan-400" : "text-white/60"} />
        </button>
      </div>

      {/* Creator row */}
      <div className="px-4 pt-4 pb-0">
        <Link
          to={`/creator/${creator.id}`}
          onClick={(e) => e.stopPropagation()}
          data-testid={`agent-creator-link-${agent.id}`}
          className="flex items-center gap-2 mb-2.5 group/creator"
        >
          <div className="w-6 h-6 rounded-sm flex items-center justify-center text-[10px] text-white font-medium" style={{ background: creator.color }}>
            {creator.initial}
          </div>
          <span className="text-[12px] t-text-sub group-hover/creator:text-cyan-300 transition-colors">{creator.username}</span>
          {creator.verified && <BadgeCheck size={11} className="text-cyan-400" />}
        </Link>
      </div>

      {/* Content */}
      <div className="px-4 pb-4">
        <Link to={`/listing/${agent.id}`} data-testid={`agent-title-link-${agent.id}`}>
          <h3 className="text-[14px] font-medium t-text leading-snug mb-2.5 line-clamp-2 hover:text-cyan-300 transition-colors cursor-pointer" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {agent.title}
          </h3>
        </Link>

        <div className="flex items-center gap-3 mb-3">
          <span className="flex items-center gap-1 text-[12px]">
            <Star size={12} className="fill-amber-400 text-amber-400" />
            <span className="t-text font-medium">{agent.rating}</span>
            <span className="t-text-dim">({agent.reviews})</span>
          </span>
          <span className="flex items-center gap-1 text-[12px] t-text-sub">
            <Shield size={11} className="text-emerald-500" /> {agent.trustScore}
          </span>
        </div>

        <div className="pt-3 flex items-center justify-between gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2 min-w-0">
            {agent.priceCredits > 0 ? (
              <span data-testid={`agent-price-${agent.id}`} className="text-[15px] font-semibold text-cyan-400 font-mono tabular-nums">
                {agent.priceCredits}
                <span className="text-[10px] t-text-dim font-normal ml-1">cr</span>
              </span>
            ) : (
              <span data-testid={`agent-price-${agent.id}`} className="text-[13px] font-bold text-emerald-400 font-mono uppercase tracking-wide">
                Free
              </span>
            )}
          </div>
          <button
            data-testid={`agent-deploy-${agent.id}`}
            onClick={(e) => { e.stopPropagation(); window.deployFromCard?.(agent); }}
            className="flex items-center gap-1 px-3 py-1.5 text-[10px] tracking-widest uppercase font-mono rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition-colors"
          >
            <Play size={10} /> Deploy
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Marketplace() {
  const { token } = useAuth();
  const { refreshCredits } = useCredits();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPublish, setShowPublish] = useState(false);
  const [showTopup, setShowTopup] = useState(false);

  // Make the card-level Deploy button work by attaching a global handler the
  // grid's MarketplaceCard delegates to. Cleaned up on unmount.
  useEffect(() => {
    window.deployFromCard = async (agent) => {
      if (!token) {
        toast.error("Sign in to deploy.");
        window.location.href = "/login";
        return;
      }
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL || ""}/api/exchange/purchase/${agent.id}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        });
        const data = await res.json();
        if (!res.ok) { toast.error(data.detail || "Deploy failed."); return; }
        if (data.error === "INSUFFICIENT_CREDITS") {
          toast.error(`Need ${data.required} credits (you have ${data.available})`);
          setShowTopup(true);
          return;
        }
        if (data.already_owned) {
          toast.info("You already own this agent.", { duration: 3000 });
          setTimeout(() => { window.location.href = "/my-deployments"; }, 900);
          return;
        }
        toast.success(data.credits_charged > 0 ? `Deployed · −${data.credits_charged} cr` : "Deployed!");
        refreshCredits();
        window.location.href = "/my-deployments";
      } catch { toast.error("Network error."); }
    };
    return () => { delete window.deployFromCard; };
  }, [token, refreshCredits]);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeCategory !== "all") params.set("category", activeCategory);
      if (searchQuery) params.set("search", searchQuery);
      // Query the Exchange listings endpoint (user-published bots/agents with media+pricing)
      const res = await fetch(`${API}/api/exchange/listings?${params}`);
      if (res.ok) {
        const data = await res.json();
        // Map exchange listing schema → marketplace card schema
        const listings = (data.listings || []).map((l) => ({
          id: l.id,
          title: l.name,
          shortTitle: l.name,
          description: l.description,
          category: l.category,
          price: l.rent_price,
          buyPrice: l.buy_price,
          priceCredits: l.price_credits || 0,
          isOfficial: !!l.is_official,
          image: l.video_url ? `${API}${l.video_url}` : (l.photo_urls?.[0] ? `${API}${l.photo_urls[0]}` : null),
          videoUrl: l.video_url ? `${API}${l.video_url}` : null,
          photoUrls: (l.photo_urls || []).map((u) => `${API}${u}`),
          rating: l.rating || 4.5,
          reviews: 0,
          trustScore: l.trust_score,
          deployCount: l.deploy_count || 0,
          creator: l.creator_name,
          trending: (l.deploy_count || 0) > 10,
          tags: l.tags || [],
          bountyWinner: l.bounty_winner === true,
          bountyTitle: l.bounty_winner_title,
          bountyId: l.bounty_winner_id,
        }));
        setAgents(listings);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [activeCategory, searchQuery]);

  useEffect(() => {
    const timer = setTimeout(fetchAgents, searchQuery ? 300 : 0);
    return () => clearTimeout(timer);
  }, [fetchAgents, searchQuery]);

  const trending = agents.filter((a) => a.trending).sort((a, b) => b.deployCount - a.deployCount);

  return (
    <div data-testid="marketplace-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 md:py-16 relative">
      <div className="absolute top-0 right-[10%] w-[400px] h-[400px] rounded-sm bg-cyan-400/[0.03] blur-[120px] pointer-events-none t-orb" />
      <div className="max-w-6xl mx-auto relative">
        <SearchHero searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

        {/* Floating "Publish Your Bot" CTA — direct upload bypasses The Armory */}
        {token && (
          <div className="flex items-center justify-end mb-6">
            <button
              data-testid="publish-bot-cta"
              onClick={() => setShowPublish(true)}
              className="flex items-center gap-2 px-4 py-2 text-[11px] font-medium tracking-[0.1em] uppercase font-mono rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition-all shadow-lg shadow-cyan-400/20"
            >
              <Upload size={12} /> Publish Your Bot
            </button>
          </div>
        )}

        <CategoryPills activeCategory={activeCategory} setActiveCategory={setActiveCategory} />
        <CreatorSpotlight />

        {/* Trending */}
        <section className="mb-14" data-testid="trending-section">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold t-text flex items-center gap-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
              <TrendingUp size={18} className="text-cyan-400" /> Most Deployed This Week
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {trending.map((agent, i) => (
              <AgentCard key={agent.id} agent={agent} index={i} />
            ))}
          </div>
        </section>

        {/* Full grid */}
        <section data-testid="all-agents-section">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
              {activeCategory === "all" ? "All Agents" : categories.find(c => c.id === activeCategory)?.label}
            </h2>
            <span className="text-[13px] t-text-dim">{agents.length} agents</span>
          </div>
          {loading ? (
            <div className="text-center py-20 t-text-dim text-[14px]">Loading agents...</div>
          ) : agents.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent, i) => (
                <AgentCard key={agent.id} agent={agent} index={i} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20 t-text-dim text-[14px]">
              No agents found. Try a different search or category.
            </div>
          )}
        </section>
      </div>

      <DirectPublishModal
        open={showPublish}
        onClose={() => setShowPublish(false)}
        onPublished={() => { setShowPublish(false); fetchAgents(); }}
      />
      {showTopup && <TopUpModal onClose={() => setShowTopup(false)} />}
    </div>
  );
}

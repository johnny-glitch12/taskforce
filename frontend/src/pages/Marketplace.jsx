import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Search, Heart, Star, Shield, ChevronRight, TrendingUp,
  Sparkles, BadgeCheck, Play,
  Headphones, BarChart3, Code2, Palette, DollarSign, MessageSquare,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

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
      <h1
        data-testid="marketplace-title"
        className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-[-0.03em] t-text mb-3"
        style={{ fontFamily: "'Outfit', sans-serif" }}
      >
        Nova <span className="text-gradient-purple">Marketplace</span>
      </h1>
      <p className="text-[15px] t-text-sub mb-8 max-w-md mx-auto">
        Discover, rent, and deploy production-ready AI agents.
      </p>
      <div className="max-w-xl mx-auto relative" data-testid="marketplace-search">
        <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 t-text-mute" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="What kind of agent do you need today?"
          data-testid="marketplace-search-input"
          className="w-full t-input focus:outline-none focus:border-[#8B5CF6]/40 transition-all pl-12 pr-5 py-4 text-[15px] rounded-2xl"
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
            className={`flex items-center gap-2 px-4 py-2 text-[13px] rounded-full whitespace-nowrap transition-all duration-200 ${
              isActive
                ? "bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.25)]"
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
          Meet the Supernovas
        </h2>
        <span className="text-[12px] t-text-dim">Top-rated creators</span>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-3 scrollbar-hide">
        {creators.map((c) => (
          <Link
            to={`/creator/${c.id}`}
            key={c.id}
            data-testid={`creator-card-${c.id}`}
            className="min-w-[260px] rounded-2xl p-5 transition-all duration-300 hover:border-[#8B5CF6]/30 hover:shadow-lg group flex-shrink-0"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-semibold" style={{ background: c.color }}>
                {c.initial}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[14px] font-medium t-text truncate">{c.name}</span>
                  {c.verified && <BadgeCheck size={13} className="text-[#8B5CF6] flex-shrink-0" />}
                </div>
                <span className="text-[12px] t-text-sub">{c.username}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] bg-[#8B5CF6]/15 text-[#A78BFA] px-2 py-0.5 rounded-full font-medium">Supernova</span>
              <span className="text-[11px] t-text-sub flex items-center gap-1"><Shield size={10} /> {c.trustScore}</span>
            </div>
            <p className="text-[13px] t-text-mute mb-3">{c.heroStat}</p>
            <div className="flex gap-1.5">
              {c.agentPreviews.map((a, i) => (
                <span key={i} className="text-[10px] t-text-sub px-2 py-1 rounded-md truncate" style={{ background: 'var(--bg-card-hover)' }}>{a}</span>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-1 text-[12px] text-[#8B5CF6] group-hover:text-[#A78BFA] transition-colors">
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
      className="rounded-2xl overflow-hidden transition-all duration-300 hover:border-[#8B5CF6]/25 hover:shadow-lg group opacity-0 animate-fade-in-up"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', animationDelay: `${index * 60}ms`, animationFillMode: "forwards" }}
    >
      {/* Image / Gradient */}
      <div className="h-36 relative overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
        {agent.image ? (
          <img src={agent.image} alt={agent.shortTitle} className="w-full h-full object-cover opacity-40 group-hover:opacity-55 group-hover:scale-105 transition-all duration-700" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-violet-950/80 to-zinc-950 opacity-60" />
        )}
        {agent.trendingLabel && (
          <span className="absolute top-3 left-3 text-[10px] bg-[#8B5CF6]/80 backdrop-blur-sm text-white px-2.5 py-1 rounded-full font-medium flex items-center gap-1">
            <TrendingUp size={10} /> {agent.trendingLabel}
          </span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); setSaved(!saved); }}
          data-testid={`agent-save-${agent.id}`}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-black/60"
        >
          <Heart size={14} className={saved ? "fill-[#8B5CF6] text-[#8B5CF6]" : "text-white/60"} />
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
          <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] text-white font-medium" style={{ background: creator.color }}>
            {creator.initial}
          </div>
          <span className="text-[12px] t-text-sub group-hover/creator:text-[#A78BFA] transition-colors">{creator.username}</span>
          {creator.verified && <BadgeCheck size={11} className="text-[#8B5CF6]" />}
        </Link>
      </div>

      {/* Content */}
      <div className="px-4 pb-4">
        <Link to={`/agent/${agent.id}`} data-testid={`agent-title-link-${agent.id}`}>
          <h3 className="text-[14px] font-medium t-text leading-snug mb-2.5 line-clamp-2 hover:text-[#A78BFA] transition-colors cursor-pointer" style={{ fontFamily: "'Outfit', sans-serif" }}>
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

        <div className="pt-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
          <Link
            to={`/agent/${agent.id}?demo=true`}
            data-testid={`agent-live-demo-${agent.id}`}
            className="flex items-center gap-1.5 text-[12px] text-[#8B5CF6] hover:text-[#A78BFA] transition-colors font-medium"
          >
            <Play size={11} /> Live Demo
          </Link>
          <span className="text-[15px] font-semibold t-text">${agent.price}<span className="text-[12px] t-text-sub font-normal">/mo</span></span>
        </div>
      </div>
    </div>
  );
}

export default function Marketplace() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeCategory !== "all") params.set("category", activeCategory);
      if (searchQuery) params.set("search", searchQuery);
      const res = await fetch(`${API}/api/agents?${params}`);
      if (res.ok) setAgents(await res.json());
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
      <div className="absolute top-0 right-[10%] w-[400px] h-[400px] rounded-full bg-[#8B5CF6]/[0.03] blur-[120px] pointer-events-none t-orb" />
      <div className="max-w-6xl mx-auto relative">
        <SearchHero searchQuery={searchQuery} setSearchQuery={setSearchQuery} />
        <CategoryPills activeCategory={activeCategory} setActiveCategory={setActiveCategory} />
        <CreatorSpotlight />

        {/* Trending */}
        <section className="mb-14" data-testid="trending-section">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold t-text flex items-center gap-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
              <TrendingUp size={18} className="text-[#8B5CF6]" /> Most Deployed This Week
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
    </div>
  );
}

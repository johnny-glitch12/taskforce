import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Search, Heart, Star, Shield, ChevronRight, TrendingUp,
  Sparkles, BadgeCheck, ArrowRight, Play,
  Headphones, BarChart3, Code2, Palette, DollarSign, MessageSquare,
} from "lucide-react";

/* ─── Data ─── */
const categories = [
  { id: "all", label: "All Agents", icon: Sparkles },
  { id: "support", label: "Customer Support", icon: Headphones },
  { id: "sales", label: "Sales Outreach", icon: MessageSquare },
  { id: "data", label: "Data Analysis", icon: BarChart3 },
  { id: "coding", label: "Coding", icon: Code2 },
  { id: "creative", label: "Creative", icon: Palette },
  { id: "finance", label: "Finance", icon: DollarSign },
];

const creators = [
  { id: "datawiz", name: "Sarah Chen", username: "@DataWiz", initial: "S", color: "#8B5CF6", verified: true, trustScore: 99, heroStat: "1.2k+ Agents Deployed", topCategory: "Top Rated in Data", agentPreviews: ["Data Analyst", "ETL Pipeline", "Anomaly Detector"] },
  { id: "salesforge", name: "Marcus Rivera", username: "@SalesForge", initial: "M", color: "#6D28D9", verified: true, trustScore: 97, heroStat: "890+ Agents Deployed", topCategory: "Top Rated in Sales", agentPreviews: ["Sales Dev Rep", "Lead Qualifier", "Outbound Pro"] },
  { id: "cxmaster", name: "Priya Sharma", username: "@CXMaster", initial: "P", color: "#7C3AED", verified: true, trustScore: 98, heroStat: "1.5k+ Agents Deployed", topCategory: "#1 in Support", agentPreviews: ["Customer Service Pro", "Ticket Triage", "CSAT Analyst"] },
  { id: "codepilot", name: "Alex Dubois", username: "@CodePilot", initial: "A", color: "#A78BFA", verified: true, trustScore: 96, heroStat: "640+ Agents Deployed", topCategory: "Top Rated in Coding", agentPreviews: ["Code Reviewer", "CI/CD Agent", "Bug Triager"] },
  { id: "financeai", name: "James Okonkwo", username: "@FinanceAI", initial: "J", color: "#5B21B6", verified: true, trustScore: 99, heroStat: "720+ Agents Deployed", topCategory: "#1 in Finance", agentPreviews: ["Finance Auditor", "Expense Tracker", "Risk Scorer"] },
];

const agents = [
  { id: 1, title: "I will deploy a Customer Service Pro agent trained on your docs", shortTitle: "Customer Service Pro", description: "Handles tickets, resolves issues, escalates edge cases with empathy.", image: "https://images.unsplash.com/photo-1744324480866-1794a1bf193c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwzfHxmdXR1cmlzdGljJTIwYWklMjBicmFpbiUyMGRhcmt8ZW58MHx8fHwxNzc0NDg1NjE4fDA&ixlib=rb-4.1.0&q=85", creator: creators[2], rating: 4.9, reviews: 124, trustScore: 98, price: 49, category: "support", trending: true, trendingLabel: "#1 in Support", deployCount: 847 },
  { id: 2, title: "I will build an AI Sales Dev Rep that books meetings on autopilot", shortTitle: "Sales Dev Rep", description: "Qualifies leads, personalizes outreach, and books meetings automatically.", image: "https://images.pexels.com/photos/5181148/pexels-photo-5181148.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", creator: creators[1], rating: 4.8, reviews: 89, trustScore: 96, price: 79, category: "sales", trending: true, trendingLabel: "#1 in Sales", deployCount: 612 },
  { id: 3, title: "I will create a Data Analyst agent for automated reporting", shortTitle: "Data Analyst", description: "Turns raw datasets into insights with anomaly detection and trend analysis.", image: "https://images.unsplash.com/photo-1697899001862-59699946ea29?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMDNkJTIwZ2VvbWV0cmljJTIwc2hhcGUlMjBkYXJrJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzQ0ODU2MTR8MA&ixlib=rb-4.1.0&q=85", creator: creators[0], rating: 4.9, reviews: 201, trustScore: 99, price: 99, category: "data", trending: true, trendingLabel: "Trending", deployCount: 1034 },
  { id: 4, title: "I will deploy an AI Code Reviewer for your pull requests", shortTitle: "Code Reviewer", description: "Reviews PRs, catches bugs, suggests improvements, enforces standards.", image: null, creator: creators[3], rating: 4.7, reviews: 67, trustScore: 95, price: 59, category: "coding", trending: false, trendingLabel: null, deployCount: 389 },
  { id: 5, title: "I will build a Finance Auditor agent for compliance checks", shortTitle: "Finance Auditor", description: "Automates audit trails, flags anomalies, ensures regulatory compliance.", image: null, creator: creators[4], rating: 4.9, reviews: 156, trustScore: 99, price: 129, category: "finance", trending: true, trendingLabel: "#1 in Finance", deployCount: 523 },
  { id: 6, title: "I will create a Lead Qualifier agent that scores and routes leads", shortTitle: "Lead Qualifier", description: "Scores inbound leads by intent, routes hot leads to reps instantly.", image: null, creator: creators[1], rating: 4.8, reviews: 112, trustScore: 97, price: 69, category: "sales", trending: false, trendingLabel: null, deployCount: 445 },
];

/* ─── Components ─── */

function SearchHero({ searchQuery, setSearchQuery }) {
  return (
    <div className="text-center mb-10">
      <h1
        data-testid="marketplace-title"
        className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-[-0.03em] text-white mb-3"
        style={{ fontFamily: "'Outfit', sans-serif" }}
      >
        Nova <span className="text-gradient-purple">Marketplace</span>
      </h1>
      <p className="text-[15px] text-zinc-500 mb-8 max-w-md mx-auto">
        Discover, rent, and deploy production-ready AI agents.
      </p>
      <div className="max-w-xl mx-auto relative" data-testid="marketplace-search">
        <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 text-zinc-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="What kind of agent do you need today?"
          data-testid="marketplace-search-input"
          className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/40 transition-all pl-12 pr-5 py-4 text-[15px] rounded-2xl"
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
                : "bg-white/[0.04] text-zinc-500 border border-white/[0.06] hover:border-[#8B5CF6]/30 hover:text-zinc-300"
            }`}
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
  return (
    <section className="mb-14" data-testid="creator-spotlight">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>
          Meet the Supernovas
        </h2>
        <span className="text-[12px] text-zinc-600">Top-rated creators</span>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-3 scrollbar-hide">
        {creators.map((c) => (
          <Link
            to={`/creator/${c.id}`}
            key={c.id}
            data-testid={`creator-card-${c.id}`}
            className="min-w-[260px] bg-white/[0.03] border border-white/[0.07] rounded-2xl p-5 transition-all duration-300 hover:border-[#8B5CF6]/30 hover:shadow-[0_0_25px_rgba(139,92,246,0.06)] group flex-shrink-0"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-semibold" style={{ background: c.color }}>
                {c.initial}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[14px] font-medium text-white truncate">{c.name}</span>
                  {c.verified && <BadgeCheck size={13} className="text-[#8B5CF6] flex-shrink-0" />}
                </div>
                <span className="text-[12px] text-zinc-500">{c.username}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] bg-[#8B5CF6]/15 text-[#A78BFA] px-2 py-0.5 rounded-full font-medium">Supernova</span>
              <span className="text-[11px] text-zinc-500 flex items-center gap-1"><Shield size={10} /> {c.trustScore}</span>
            </div>
            <p className="text-[13px] text-zinc-400 mb-3">{c.heroStat}</p>
            <div className="flex gap-1.5">
              {c.agentPreviews.map((a, i) => (
                <span key={i} className="text-[10px] bg-white/[0.04] text-zinc-500 px-2 py-1 rounded-md truncate">{a}</span>
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
  const gradients = [
    "from-violet-950/80 to-zinc-950",
    "from-purple-950/80 to-zinc-950",
    "from-indigo-950/80 to-zinc-950",
  ];

  return (
    <div
      data-testid={`agent-card-${agent.id}`}
      className="bg-white/[0.03] border border-white/[0.07] rounded-2xl overflow-hidden transition-all duration-300 hover:border-[#8B5CF6]/25 hover:shadow-[0_0_30px_rgba(139,92,246,0.07)] group opacity-0 animate-fade-in-up"
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "forwards" }}
    >
      {/* Image / Gradient */}
      <div className="h-36 relative overflow-hidden">
        {agent.image ? (
          <img src={agent.image} alt={agent.shortTitle} className="w-full h-full object-cover opacity-40 group-hover:opacity-55 group-hover:scale-105 transition-all duration-700" />
        ) : (
          <div className={`w-full h-full bg-gradient-to-br ${gradients[agent.id % 3]} opacity-60`} />
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
          to={`/creator/${agent.creator.id}`}
          onClick={(e) => e.stopPropagation()}
          data-testid={`agent-creator-link-${agent.id}`}
          className="flex items-center gap-2 mb-2.5 group/creator"
        >
          <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] text-white font-medium" style={{ background: agent.creator.color }}>
            {agent.creator.initial}
          </div>
          <span className="text-[12px] text-zinc-500 group-hover/creator:text-[#A78BFA] transition-colors">{agent.creator.username}</span>
          {agent.creator.verified && <BadgeCheck size={11} className="text-[#8B5CF6]" />}
        </Link>
      </div>

      {/* Content */}
      <div className="px-4 pb-4">
        <Link to={`/agent/${agent.id}`} data-testid={`agent-title-link-${agent.id}`}>
          <h3 className="text-[14px] font-medium text-white leading-snug mb-2.5 line-clamp-2 hover:text-[#A78BFA] transition-colors cursor-pointer" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {agent.title}
          </h3>
        </Link>

        {/* Social proof */}
        <div className="flex items-center gap-3 mb-3">
          <span className="flex items-center gap-1 text-[12px]">
            <Star size={12} className="fill-amber-400 text-amber-400" />
            <span className="text-white font-medium">{agent.rating}</span>
            <span className="text-zinc-600">({agent.reviews})</span>
          </span>
          <span className="flex items-center gap-1 text-[12px] text-zinc-500">
            <Shield size={11} className="text-emerald-500" /> {agent.trustScore}
          </span>
        </div>

        {/* Actions */}
        <div className="pt-3 border-t border-white/[0.05] flex items-center justify-between">
          <Link
            to={`/agent/${agent.id}?demo=true`}
            data-testid={`agent-live-demo-${agent.id}`}
            className="flex items-center gap-1.5 text-[12px] text-[#8B5CF6] hover:text-[#A78BFA] transition-colors font-medium"
          >
            <Play size={11} /> Live Demo
          </Link>
          <span className="text-[15px] font-semibold text-white">${agent.price}<span className="text-[12px] text-zinc-500 font-normal">/mo</span></span>
        </div>
      </div>
    </div>
  );
}

/* ─── Main ─── */
export default function Marketplace() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");

  const filtered = agents.filter((a) => {
    const matchCat = activeCategory === "all" || a.category === activeCategory;
    const matchSearch = a.title.toLowerCase().includes(searchQuery.toLowerCase()) || a.shortTitle.toLowerCase().includes(searchQuery.toLowerCase());
    return matchCat && matchSearch;
  });

  const trending = agents.filter((a) => a.trending).sort((a, b) => b.deployCount - a.deployCount);

  return (
    <div data-testid="marketplace-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 md:py-16 relative">
      <div className="absolute top-0 right-[10%] w-[400px] h-[400px] rounded-full bg-[#8B5CF6]/[0.03] blur-[120px] pointer-events-none" />
      <div className="max-w-6xl mx-auto relative">
        <SearchHero searchQuery={searchQuery} setSearchQuery={setSearchQuery} />
        <CategoryPills activeCategory={activeCategory} setActiveCategory={setActiveCategory} />
        <CreatorSpotlight />

        {/* Trending row */}
        <section className="mb-14" data-testid="trending-section">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
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
            <h2 className="text-lg font-semibold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>
              {activeCategory === "all" ? "All Agents" : categories.find(c => c.id === activeCategory)?.label}
            </h2>
            <span className="text-[13px] text-zinc-600">{filtered.length} agents</span>
          </div>
          {filtered.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((agent, i) => (
                <AgentCard key={agent.id} agent={agent} index={i} />
              ))}
            </div>
          ) : (
            <div className="text-center py-20 text-zinc-600 text-[14px]">
              No agents found. Try a different search or category.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

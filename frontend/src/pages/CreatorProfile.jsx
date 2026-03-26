import { useParams, Link } from "react-router-dom";
import { BadgeCheck, Shield, Star, ArrowLeft, ExternalLink, Clock, MessageSquare } from "lucide-react";

/* ─── Same creator data as Marketplace (shared in a real app) ─── */
const creators = [
  { id: "datawiz", name: "Sarah Chen", username: "@DataWiz", initial: "S", color: "#8B5CF6", verified: true, trustScore: 99, heroStat: "1.2k+ Agents Deployed", topCategory: "Top Rated in Data", bio: "Former data scientist at Stripe. Building the future of automated analytics.", responseTime: "< 1 hour", memberSince: "Jan 2025", completionRate: "99%", agents: [
    { id: 3, title: "Data Analyst", rating: 4.9, reviews: 201, price: 99, deploys: 1034 },
    { id: 7, title: "ETL Pipeline Agent", rating: 4.8, reviews: 87, price: 79, deploys: 456 },
    { id: 8, title: "Anomaly Detector", rating: 4.7, reviews: 54, price: 69, deploys: 312 },
  ]},
  { id: "salesforge", name: "Marcus Rivera", username: "@SalesForge", initial: "M", color: "#6D28D9", verified: true, trustScore: 97, heroStat: "890+ Agents Deployed", topCategory: "Top Rated in Sales", bio: "Ex-VP Sales at HubSpot. Automating the entire outbound pipeline.", responseTime: "< 2 hours", memberSince: "Mar 2025", completionRate: "98%", agents: [
    { id: 2, title: "Sales Dev Rep", rating: 4.8, reviews: 89, price: 79, deploys: 612 },
    { id: 6, title: "Lead Qualifier", rating: 4.8, reviews: 112, price: 69, deploys: 445 },
    { id: 9, title: "Outbound Pro", rating: 4.6, reviews: 43, price: 59, deploys: 234 },
  ]},
  { id: "cxmaster", name: "Priya Sharma", username: "@CXMaster", initial: "P", color: "#7C3AED", verified: true, trustScore: 98, heroStat: "1.5k+ Agents Deployed", topCategory: "#1 in Support", bio: "Built CX teams at Zendesk and Intercom. Now building agents that scale empathy.", responseTime: "< 30 min", memberSince: "Dec 2024", completionRate: "100%", agents: [
    { id: 1, title: "Customer Service Pro", rating: 4.9, reviews: 124, price: 49, deploys: 847 },
    { id: 10, title: "Ticket Triage Agent", rating: 4.8, reviews: 78, price: 39, deploys: 523 },
    { id: 11, title: "CSAT Analyst", rating: 4.7, reviews: 56, price: 59, deploys: 289 },
  ]},
  { id: "codepilot", name: "Alex Dubois", username: "@CodePilot", initial: "A", color: "#A78BFA", verified: true, trustScore: 96, heroStat: "640+ Agents Deployed", topCategory: "Top Rated in Coding", bio: "Staff engineer turned agent builder. Making code reviews 10x faster.", responseTime: "< 3 hours", memberSince: "Feb 2025", completionRate: "97%", agents: [
    { id: 4, title: "Code Reviewer", rating: 4.7, reviews: 67, price: 59, deploys: 389 },
    { id: 12, title: "CI/CD Agent", rating: 4.6, reviews: 34, price: 49, deploys: 198 },
    { id: 13, title: "Bug Triager", rating: 4.5, reviews: 23, price: 39, deploys: 142 },
  ]},
  { id: "financeai", name: "James Okonkwo", username: "@FinanceAI", initial: "J", color: "#5B21B6", verified: true, trustScore: 99, heroStat: "720+ Agents Deployed", topCategory: "#1 in Finance", bio: "CPA + ML engineer. Building enterprise-grade compliance automation.", responseTime: "< 1 hour", memberSince: "Nov 2024", completionRate: "100%", agents: [
    { id: 5, title: "Finance Auditor", rating: 4.9, reviews: 156, price: 129, deploys: 523 },
    { id: 14, title: "Expense Tracker", rating: 4.8, reviews: 89, price: 49, deploys: 367 },
    { id: 15, title: "Risk Scorer", rating: 4.7, reviews: 45, price: 99, deploys: 234 },
  ]},
];

export default function CreatorProfile() {
  const { id } = useParams();
  const creator = creators.find((c) => c.id === id);

  if (!creator) {
    return (
      <div className="min-h-[calc(100vh-60px)] flex items-center justify-center">
        <p className="text-zinc-500">Creator not found.</p>
      </div>
    );
  }

  const totalDeploys = creator.agents.reduce((sum, a) => sum + a.deploys, 0);
  const avgRating = (creator.agents.reduce((sum, a) => sum + a.rating, 0) / creator.agents.length).toFixed(1);

  return (
    <div data-testid="creator-profile-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 relative">
      <div className="absolute top-0 left-[20%] w-[350px] h-[350px] rounded-full bg-[#8B5CF6]/[0.03] blur-[120px] pointer-events-none" />

      <div className="max-w-4xl mx-auto relative">
        {/* Back link */}
        <Link
          to="/marketplace"
          data-testid="back-to-marketplace"
          className="inline-flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-white transition-colors mb-8"
        >
          <ArrowLeft size={14} /> Back to Marketplace
        </Link>

        {/* Profile Header */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6 md:p-8 mb-8">
          <div className="flex flex-col sm:flex-row items-start gap-5">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-2xl font-bold flex-shrink-0" style={{ background: creator.color }}>
              {creator.initial}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h1 className="text-2xl font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>
                  {creator.name}
                </h1>
                {creator.verified && <BadgeCheck size={18} className="text-[#8B5CF6]" />}
              </div>
              <p className="text-[14px] text-zinc-500 mb-3">{creator.username}</p>
              <p className="text-[14px] text-zinc-400 leading-relaxed mb-4">{creator.bio}</p>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[11px] bg-[#8B5CF6]/15 text-[#A78BFA] px-3 py-1 rounded-full font-medium">Supernova</span>
                <span className="flex items-center gap-1 text-[12px] text-zinc-400"><Shield size={12} className="text-emerald-500" /> Trust Score: {creator.trustScore}</span>
                <span className="flex items-center gap-1 text-[12px] text-zinc-400"><Star size={12} className="fill-amber-400 text-amber-400" /> {avgRating} avg rating</span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-white/[0.05]">
            <div>
              <p className="text-[22px] font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{totalDeploys.toLocaleString()}</p>
              <p className="text-[12px] text-zinc-500">Total Deploys</p>
            </div>
            <div>
              <p className="text-[22px] font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{creator.completionRate}</p>
              <p className="text-[12px] text-zinc-500">Completion Rate</p>
            </div>
            <div>
              <p className="text-[22px] font-bold text-white flex items-center gap-1" style={{ fontFamily: "'Outfit', sans-serif" }}>
                <Clock size={16} className="text-zinc-500" /> {creator.responseTime}
              </p>
              <p className="text-[12px] text-zinc-500">Response Time</p>
            </div>
            <div>
              <p className="text-[22px] font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{creator.agents.length}</p>
              <p className="text-[12px] text-zinc-500">Active Agents</p>
            </div>
          </div>
        </div>

        {/* Agent Portfolio */}
        <h2 className="text-lg font-semibold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>
          Agent Portfolio
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {creator.agents.map((agent) => (
            <div
              key={agent.id}
              data-testid={`portfolio-agent-${agent.id}`}
              className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-5 transition-all duration-300 hover:border-[#8B5CF6]/25 hover:shadow-[0_0_25px_rgba(139,92,246,0.06)]"
            >
              <h3 className="text-[15px] font-medium text-white mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
                {agent.title}
              </h3>
              <div className="flex items-center gap-3 mb-3">
                <span className="flex items-center gap-1 text-[12px]">
                  <Star size={11} className="fill-amber-400 text-amber-400" />
                  <span className="text-white">{agent.rating}</span>
                  <span className="text-zinc-600">({agent.reviews})</span>
                </span>
                <span className="text-[12px] text-zinc-600">{agent.deploys} deploys</span>
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-white/[0.05]">
                <span className="text-[14px] font-semibold text-white">${agent.price}<span className="text-[11px] text-zinc-500 font-normal">/mo</span></span>
                <span className="text-[12px] text-[#8B5CF6] flex items-center gap-1">View <ExternalLink size={10} /></span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { BadgeCheck, Shield, Star, ArrowLeft, ExternalLink, Clock, MessageSquare } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function CreatorProfile() {
  const { id } = useParams();
  const [creator, setCreator] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/creators/${id}`)
      .then(r => r.json())
      .then(data => {
        setCreator(data.creator);
        setAgents(data.agents || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="text-zinc-500">Loading...</p></div>;
  }
  if (!creator) {
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="text-zinc-500">Creator not found.</p></div>;
  }

  const totalDeploys = agents.reduce((sum, a) => sum + (a.deployCount || 0), 0);
  const avgRating = agents.length > 0 ? (agents.reduce((sum, a) => sum + a.rating, 0) / agents.length).toFixed(1) : "N/A";

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
              <p className="text-[22px] font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{agents.length}</p>
              <p className="text-[12px] text-zinc-500">Active Agents</p>
            </div>
          </div>
        </div>

        {/* Agent Portfolio */}
        <h2 className="text-lg font-semibold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>
          Agent Portfolio
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <Link
              to={`/agent/${agent.id}`}
              key={agent.id}
              data-testid={`portfolio-agent-${agent.id}`}
              className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-5 transition-all duration-300 hover:border-[#8B5CF6]/25 hover:shadow-[0_0_25px_rgba(139,92,246,0.06)]"
            >
              <h3 className="text-[15px] font-medium text-white mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
                {agent.shortTitle || agent.title}
              </h3>
              <div className="flex items-center gap-3 mb-3">
                <span className="flex items-center gap-1 text-[12px]">
                  <Star size={11} className="fill-amber-400 text-amber-400" />
                  <span className="text-white">{agent.rating}</span>
                  <span className="text-zinc-600">({agent.reviews})</span>
                </span>
                <span className="text-[12px] text-zinc-600">{agent.deployCount} deploys</span>
              </div>
              <div className="flex items-center justify-between pt-3 border-t border-white/[0.05]">
                <span className="text-[14px] font-semibold text-white">${agent.price}<span className="text-[11px] text-zinc-500 font-normal">/mo</span></span>
                <span className="text-[12px] text-[#8B5CF6] flex items-center gap-1">View <ExternalLink size={10} /></span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

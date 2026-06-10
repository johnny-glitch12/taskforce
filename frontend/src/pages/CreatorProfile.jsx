import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { BadgeCheck, Shield, Star, ArrowLeft, ExternalLink, Clock, MessageSquare } from "lucide-react";
import usePageTitle from "@/hooks/usePageTitle";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function CreatorProfile() {
  const { id } = useParams();
  const [creator, setCreator] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  usePageTitle(creator?.name);

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
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="t-text-mute">Loading...</p></div>;
  }
  if (!creator) {
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="t-text-mute">Creator not found.</p></div>;
  }

  const totalDeploys = agents.reduce((sum, a) => sum + (a.deployCount || 0), 0);
  const avgRating = agents.length > 0 ? (agents.reduce((sum, a) => sum + a.rating, 0) / agents.length).toFixed(1) : "N/A";

  return (
    <div data-testid="creator-profile-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 relative">
      <div className="absolute top-0 left-[20%] w-[350px] h-[350px] rounded-sm bg-cyan-400/[0.03] blur-[120px] pointer-events-none" />

      <div className="max-w-4xl mx-auto relative">
        {/* Back link */}
        <Link
          to="/marketplace"
          data-testid="back-to-marketplace"
          className="inline-flex items-center gap-1.5 text-[13px] t-text-mute hover:text-cyan-400 transition-colors mb-8"
        >
          <ArrowLeft size={14} /> Back to Marketplace
        </Link>

        {/* Profile Header */}
        <div className="rounded-sm p-6 md:p-8 mb-8" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="flex flex-col sm:flex-row items-start gap-5">
            <div className="w-16 h-16 rounded-sm flex items-center justify-center text-white text-2xl font-bold flex-shrink-0" style={{ background: creator.color }}>
              {creator.initial}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h1 className="text-2xl font-bold t-text">
                  {creator.name}
                </h1>
                {creator.verified && <BadgeCheck size={18} className="text-cyan-400" />}
              </div>
              <p className="text-[14px] t-text-mute mb-3">{creator.username}</p>
              <p className="text-[14px] t-text-sub leading-relaxed mb-4">{creator.bio}</p>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[11px] px-3 py-1 rounded-sm font-medium" style={{ background: "var(--accent-bg)", color: "var(--accent)" }}>Supernova</span>
                <span className="flex items-center gap-1 text-[12px] t-text-sub"><Shield size={12} className="text-emerald-500" /> Trust Score: {creator.trustScore}</span>
                <span className="flex items-center gap-1 text-[12px] t-text-sub"><Star size={12} className="fill-amber-400 text-amber-400" /> {avgRating} avg rating</span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6" style={{ borderTop: "1px solid var(--border)" }}>
            <div>
              <p className="text-[22px] font-bold t-text">{totalDeploys.toLocaleString()}</p>
              <p className="text-[12px] t-text-mute">Total Deploys</p>
            </div>
            <div>
              <p className="text-[22px] font-bold t-text">{creator.completionRate}</p>
              <p className="text-[12px] t-text-mute">Completion Rate</p>
            </div>
            <div>
              <p className="text-[22px] font-bold t-text flex items-center gap-1">
                <Clock size={16} className="t-text-mute" /> {creator.responseTime}
              </p>
              <p className="text-[12px] t-text-mute">Response Time</p>
            </div>
            <div>
              <p className="text-[22px] font-bold t-text">{agents.length}</p>
              <p className="text-[12px] t-text-mute">Active Agents</p>
            </div>
          </div>
        </div>

        {/* Agent Portfolio */}
        <h2 className="text-lg font-semibold t-text mb-5">
          Agent Portfolio
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <Link
              to={`/agent/${agent.id}`}
              key={agent.id}
              data-testid={`portfolio-agent-${agent.id}`}
              className="rounded-sm p-5 transition-[border-color,box-shadow] duration-200 hover:border-cyan-400/25 hover:shadow-[0_0_25px_rgba(34,211,238,0.06)]"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <h3 className="text-[15px] font-medium t-text mb-2">
                {agent.shortTitle || agent.title}
              </h3>
              <div className="flex items-center gap-3 mb-3">
                <span className="flex items-center gap-1 text-[12px]">
                  <Star size={11} className="fill-amber-400 text-amber-400" />
                  <span className="t-text">{agent.rating}</span>
                  <span className="t-text-dim">({agent.reviews})</span>
                </span>
                <span className="text-[12px] t-text-dim">{agent.deployCount} deploys</span>
              </div>
              <div className="flex items-center justify-between pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                <span className="text-[14px] font-semibold t-text">${agent.price}<span className="text-[11px] t-text-mute font-normal">/mo</span></span>
                <span className="text-[12px] text-cyan-400 flex items-center gap-1">View <ExternalLink size={10} /></span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

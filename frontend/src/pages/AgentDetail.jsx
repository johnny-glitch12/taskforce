import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  ArrowLeft, Star, Shield, BadgeCheck, Play, Send, X,
  Zap, Clock, Users, CheckCircle2, ShoppingCart, Tag, Bot, Loader2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Demo Chat Simulation ─── */
const demoResponses = {
  1: ["I'll look into that refund for you right away. Can you share the order ID?", "The refund has been processed. You should see it in 3-5 business days. Is there anything else I can help with?", "I understand your frustration. Let me escalate this to our senior support team who can expedite the resolution."],
  2: ["I found 3 highly qualified prospects matching your ICP. Let me draft personalized outreach sequences.", "Based on their LinkedIn activity, the best approach is a value-first email referencing their recent product launch.", "Meeting booked! I've sent calendar invites to both parties and added the prospect notes to your CRM."],
  3: ["I've analyzed your dataset. Revenue is trending up 12% MoM, but I've detected an anomaly in Q3 expenses.", "The spike in expenses correlates with a 340% increase in marketing spend. Here's the breakdown by channel.", "Report generated and sent to your Slack channel. Key insight: your CAC has decreased 18% while LTV increased."],
  4: ["I've reviewed the PR. Found 2 potential bugs: a null reference on line 42 and an unhandled promise on line 87.", "I also noticed a security issue — the API key is hardcoded on line 156. I recommend using environment variables.", "Code quality score: 8.2/10. Main suggestion: extract the duplicate logic in lines 23-45 into a shared utility."],
  5: ["I've completed the compliance scan. 3 transactions flagged for manual review due to threshold violations.", "All flagged items are documented with audit trails. SOX compliance score: 97%. One finding needs attention.", "The quarterly audit report is ready. All critical controls passed. One advisory finding regarding vendor payments."],
  6: ["New lead scored: 87/100. High intent signals detected — they visited pricing 3 times and downloaded the whitepaper.", "This lead matches your ideal customer profile. Routing to your top AE via Slack now.", "Lead enrichment complete: Series B startup, 50-100 employees, $12M ARR. Decision maker confirmed as VP of Engineering."],
};

function LiveDemoModal({ agent, onClose }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: agent.demoGreeting }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEnd = useRef(null);
  const responseIndex = useRef(0);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    const userMsg = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsTyping(true);

    const responses = demoResponses[agent.id] || ["That's a great question! Let me analyze that for you..."];
    const reply = responses[responseIndex.current % responses.length];
    responseIndex.current += 1;

    setTimeout(() => {
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
      setIsTyping(false);
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="live-demo-modal">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-zinc-900 border border-white/[0.08] rounded-2xl flex flex-col h-[70vh] max-h-[600px] overflow-hidden animate-fade-in-up" style={{ animationFillMode: "forwards" }}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#8B5CF6]/15 flex items-center justify-center">
              <Bot size={16} className="text-[#8B5CF6]" />
            </div>
            <div>
              <p className="text-[14px] font-medium text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{agent.shortTitle}</p>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Live Demo</p>
            </div>
          </div>
          <button onClick={onClose} data-testid="close-demo-modal" className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-zinc-500 hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} data-testid={`demo-message-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-xl ${
                msg.role === "user"
                  ? "bg-[#8B5CF6]/15 text-zinc-200 border border-[#8B5CF6]/20"
                  : "bg-white/[0.04] text-zinc-300 border border-white/[0.06]"
              }`}>{msg.content}</div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl px-4 py-3 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="px-5 py-3 border-t border-white/[0.06] flex gap-2">
          <input
            type="text" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Try asking something..."
            data-testid="demo-chat-input"
            className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-xl px-4 py-2.5 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#8B5CF6]/40 transition-all"
          />
          <button type="submit" data-testid="demo-send-btn" className="px-4 py-2.5 bg-[#8B5CF6] text-white rounded-xl hover:bg-[#A78BFA] transition-all text-[13px] font-medium flex items-center gap-1.5">
            <Send size={13} /> Send
          </button>
        </form>
      </div>
    </div>
  );
}

/* ─── Main Component ─── */
export default function AgentDetail() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { user, token } = useAuth();
  const [agent, setAgent] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDemo, setShowDemo] = useState(searchParams.get("demo") === "true");
  const [activeTab, setActiveTab] = useState("overview");
  const [checkingOut, setCheckingOut] = useState(null); // "rent" | "buy" | null

  useEffect(() => {
    const load = async () => {
      try {
        const [agentRes, reviewsRes] = await Promise.all([
          fetch(`${API}/api/agents/${id}`),
          fetch(`${API}/api/agents/${id}/reviews`),
        ]);
        if (agentRes.ok) setAgent(await agentRes.json());
        if (reviewsRes.ok) setReviews(await reviewsRes.json());
      } catch { /* ignore */ }
      setLoading(false);
    };
    load();
  }, [id]);

  if (loading) {
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="text-zinc-500">Loading...</p></div>;
  }
  if (!agent) {
    return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="text-zinc-500">Agent not found.</p></div>;
  }

  const gradients = ["from-violet-950/60 to-zinc-950", "from-purple-950/60 to-zinc-950", "from-indigo-950/60 to-zinc-950"];

  return (
    <div data-testid="agent-detail-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-10 relative">
      <div className="absolute top-0 left-[30%] w-[400px] h-[400px] rounded-full bg-[#8B5CF6]/[0.03] blur-[120px] pointer-events-none" />
      <div className="max-w-5xl mx-auto relative">
        <Link to="/marketplace" data-testid="back-to-marketplace" className="inline-flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-white transition-colors mb-6">
          <ArrowLeft size={14} /> Back to Marketplace
        </Link>

        {/* Hero */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-10">
          {/* Left: Image + Demo */}
          <div className="lg:col-span-3">
            <div className="h-64 rounded-2xl overflow-hidden relative mb-4">
              {agent.image ? (
                <img src={agent.image} alt={agent.shortTitle} className="w-full h-full object-cover opacity-50" />
              ) : (
                <div className={`w-full h-full bg-gradient-to-br ${gradients[agent.id % 3]}`} />
              )}
              <button
                onClick={() => setShowDemo(true)}
                data-testid="agent-demo-btn"
                className="absolute bottom-4 left-4 flex items-center gap-2 px-5 py-2.5 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all shadow-[0_0_20px_rgba(139,92,246,0.3)]"
              >
                <Play size={14} /> Live Demo
              </button>
            </div>

            {/* Video placeholder */}
            <div data-testid="demo-video-placeholder" className="rounded-2xl bg-white/[0.03] border border-white/[0.07] h-48 flex items-center justify-center">
              <div className="text-center">
                <div className="w-14 h-14 rounded-full bg-white/[0.04] flex items-center justify-center mx-auto mb-3">
                  <Play size={24} className="text-zinc-500 ml-1" />
                </div>
                <p className="text-[13px] text-zinc-500">Demo video coming soon</p>
              </div>
            </div>
          </div>

          {/* Right: Details + Checkout */}
          <div className="lg:col-span-2">
            <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6 sticky top-24">
              {/* Creator */}
              <Link to={`/creator/${agent.creator_id}`} className="flex items-center gap-2.5 mb-4 group">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-[12px] text-white font-medium" style={{ background: agent.creator_color }}>
                  {agent.creator_initial}
                </div>
                <span className="text-[13px] text-zinc-400 group-hover:text-[#A78BFA] transition-colors">{agent.creator_username}</span>
                {agent.creator_verified && <BadgeCheck size={13} className="text-[#8B5CF6]" />}
              </Link>

              <h1 data-testid="agent-detail-title" className="text-xl font-bold text-white mb-3 leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
                {agent.shortTitle}
              </h1>

              {/* Ratings */}
              <div className="flex items-center gap-3 mb-4">
                <span className="flex items-center gap-1 text-[13px]">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  <span className="text-white font-medium">{agent.rating}</span>
                  <span className="text-zinc-500">({agent.reviews} reviews)</span>
                </span>
                <span className="flex items-center gap-1 text-[13px] text-zinc-400">
                  <Shield size={13} className="text-emerald-500" /> {agent.trustScore}
                </span>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div className="bg-white/[0.03] rounded-xl p-3 text-center">
                  <Zap size={14} className="text-[#8B5CF6] mx-auto mb-1" />
                  <p className="text-[12px] text-zinc-500">{agent.deployCount} deploys</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3 text-center">
                  <Clock size={14} className="text-[#8B5CF6] mx-auto mb-1" />
                  <p className="text-[12px] text-zinc-500">{agent.setupTime}</p>
                </div>
                <div className="bg-white/[0.03] rounded-xl p-3 text-center">
                  <Users size={14} className="text-[#8B5CF6] mx-auto mb-1" />
                  <p className="text-[12px] text-zinc-500">{agent.reviews} users</p>
                </div>
              </div>

              {/* Pricing */}
              <div className="border-t border-white/[0.05] pt-5 mb-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-[12px] text-zinc-500 mb-1">Rent</p>
                    <p className="text-2xl font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>${agent.price}<span className="text-[14px] text-zinc-500 font-normal">/mo</span></p>
                  </div>
                  <div className="text-right">
                    <p className="text-[12px] text-zinc-500 mb-1">Buy</p>
                    <p className="text-2xl font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>${agent.buyPrice}</p>
                  </div>
                </div>
                <div className="flex gap-2.5">
                  <button
                    onClick={async () => {
                      if (!user) { toast.error("Please log in to continue."); return; }
                      setCheckingOut("rent");
                      try {
                        const res = await fetch(`${API}/api/payments/checkout`, {
                          method: "POST",
                          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                          body: JSON.stringify({ agent_id: agent.id, plan: "rent", origin_url: window.location.origin }),
                        });
                        if (res.ok) { const d = await res.json(); window.location.href = d.url; }
                        else { const e = await res.json(); toast.error(e.detail || "Checkout failed."); }
                      } catch { toast.error("Network error."); }
                      setCheckingOut(null);
                    }}
                    data-testid="rent-agent-btn"
                    disabled={checkingOut === "rent"}
                    className="flex-1 py-3 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {checkingOut === "rent" ? <Loader2 size={13} className="animate-spin" /> : <Tag size={13} />} Rent
                  </button>
                  <button
                    onClick={async () => {
                      if (!user) { toast.error("Please log in to continue."); return; }
                      setCheckingOut("buy");
                      try {
                        const res = await fetch(`${API}/api/payments/checkout`, {
                          method: "POST",
                          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                          body: JSON.stringify({ agent_id: agent.id, plan: "buy", origin_url: window.location.origin }),
                        });
                        if (res.ok) { const d = await res.json(); window.location.href = d.url; }
                        else { const e = await res.json(); toast.error(e.detail || "Checkout failed."); }
                      } catch { toast.error("Network error."); }
                      setCheckingOut(null);
                    }}
                    data-testid="buy-agent-btn"
                    disabled={checkingOut === "buy"}
                    className="flex-1 py-3 bg-white/[0.06] text-white text-[13px] font-medium rounded-full border border-white/[0.08] hover:bg-white/[0.1] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {checkingOut === "buy" ? <Loader2 size={13} className="animate-spin" /> : <ShoppingCart size={13} />} Buy
                  </button>
                </div>
              </div>

              <button
                onClick={() => setShowDemo(true)}
                data-testid="try-demo-sidebar-btn"
                className="w-full py-3 text-[13px] text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-full hover:bg-[#8B5CF6]/10 transition-all flex items-center justify-center gap-2"
              >
                <Play size={13} /> Try Live Demo
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/[0.03] border border-white/[0.06] rounded-full p-1 w-fit" data-testid="agent-tabs">
          {["overview", "reviews"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              data-testid={`tab-${tab}`}
              className={`px-5 py-2 text-[13px] rounded-full transition-all capitalize ${
                activeTab === tab ? "bg-[#8B5CF6] text-white" : "text-zinc-500 hover:text-white"
              }`}
            >{tab}</button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === "overview" && (
          <div data-testid="overview-tab-content" className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-16">
            <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6">
              <h3 className="text-[16px] font-semibold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>About this agent</h3>
              <p className="text-[14px] text-zinc-400 leading-relaxed">{agent.longDescription}</p>
            </div>
            <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6">
              <h3 className="text-[16px] font-semibold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>Features</h3>
              <div className="space-y-3">
                {agent.features.map((f, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className="text-[14px] text-zinc-400">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "reviews" && (
          <div data-testid="reviews-tab-content" className="max-w-2xl mb-16">
            <div className="flex items-center gap-4 mb-6">
              <span className="text-3xl font-bold text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>{agent.rating}</span>
              <div>
                <div className="flex items-center gap-0.5 mb-1">
                  {[1,2,3,4,5].map((s) => <Star key={s} size={16} className={s <= Math.round(agent.rating) ? "fill-amber-400 text-amber-400" : "text-zinc-700"} />)}
                </div>
                <p className="text-[13px] text-zinc-500">{agent.reviews} reviews</p>
              </div>
            </div>
            <div className="space-y-4">
              {reviews.map((r) => (
                <div key={r.id} data-testid={`review-${r.id}`} className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center text-[11px] text-zinc-400 font-medium">{r.user_name[0]}</div>
                      <span className="text-[13px] text-white font-medium">{r.user_name}</span>
                    </div>
                    <span className="text-[12px] text-zinc-600">{r.date}</span>
                  </div>
                  <div className="flex items-center gap-0.5 mb-2">
                    {[1,2,3,4,5].map((s) => <Star key={s} size={12} className={s <= r.rating ? "fill-amber-400 text-amber-400" : "text-zinc-700"} />)}
                  </div>
                  <p className="text-[13px] text-zinc-400 leading-relaxed">{r.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Live Demo Modal */}
      {showDemo && <LiveDemoModal agent={agent} onClose={() => setShowDemo(false)} />}
    </div>
  );
}

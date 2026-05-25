import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  ArrowLeft, Star, Shield, BadgeCheck, Play, Send, X,
  Zap, Clock, Users, CheckCircle2, ShoppingCart, Tag, Bot, Loader2,
  CreditCard, Lock, Code2, Server, FileKey, Cpu,
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
  const [messages, setMessages] = useState([{ role: "assistant", content: agent.demoGreeting }]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEnd = useRef(null);
  const responseIndex = useRef(0);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

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
    setTimeout(() => { setMessages((prev) => [...prev, { role: "assistant", content: reply }]); setIsTyping(false); }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="live-demo-modal">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-sm flex flex-col h-[70vh] max-h-[600px] overflow-hidden animate-fade-in-up" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', animationFillMode: "forwards" }}>
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-400/15 flex items-center justify-center"><Bot size={16} className="text-cyan-400" /></div>
            <div>
              <p className="text-[14px] font-medium t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>{agent.shortTitle}</p>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-sm bg-emerald-400" /> Live Demo</p>
            </div>
          </div>
          <button onClick={onClose} data-testid="close-demo-modal" className="w-8 h-8 rounded-lg flex items-center justify-center t-text-sub hover:t-text transition-colors" style={{ background: 'var(--bg-card)' }}><X size={16} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} data-testid={`demo-message-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-sm ${msg.role === "user" ? "bg-cyan-400/15 t-text border border-cyan-400/20" : "t-text-sub border"}`} style={msg.role !== "user" ? { background: 'var(--bg-card)', borderColor: 'var(--border)' } : {}}>{msg.content}</div>
            </div>
          ))}
          {isTyping && (<div className="flex justify-start"><div className="rounded-sm px-4 py-3 flex items-center gap-1" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}><span className="w-1.5 h-1.5 rounded-sm bg-zinc-500 animate-bounce" style={{ animationDelay: "0ms" }} /><span className="w-1.5 h-1.5 rounded-sm bg-zinc-500 animate-bounce" style={{ animationDelay: "150ms" }} /><span className="w-1.5 h-1.5 rounded-sm bg-zinc-500 animate-bounce" style={{ animationDelay: "300ms" }} /></div></div>)}
          <div ref={messagesEnd} />
        </div>
        <form onSubmit={handleSend} className="px-5 py-3 flex gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Try asking something..." data-testid="demo-chat-input" className="flex-1 t-input rounded-sm px-4 py-2.5 text-[13px] focus:outline-none focus:border-cyan-400/40 transition-all" style={{ border: '1px solid var(--input-border)' }} />
          <button type="submit" data-testid="demo-send-btn" className="px-4 py-2.5 bg-cyan-400 text-white rounded-sm hover:bg-cyan-300 transition-all text-[13px] font-medium flex items-center gap-1.5"><Send size={13} /> Send</button>
        </form>
      </div>
    </div>
  );
}

/* ─── Split Purchasing Panel ─── */
function PurchasePanel({ agent, user, token, checkingOut, setCheckingOut }) {
  const [purchaseMode, setPurchaseMode] = useState("rent");
  const [outputCount, setOutputCount] = useState(500);
  const pricePerHundred = Math.max(5, Math.round((agent.price || 49) * 0.3));
  const rentPrice = Math.round((outputCount / 100) * pricePerHundred);
  const acquirePrice = agent.buyPrice ? agent.buyPrice * 6 : 2999;

  const handleCheckout = async (plan) => {
    if (!user) { toast.error("Please log in to continue."); return; }
    setCheckingOut(plan);
    try {
      const res = await fetch(`${API}/api/payments/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agent.id, plan, origin_url: window.location.origin }),
      });
      if (res.ok) { const d = await res.json(); window.location.href = d.url; }
      else { const e = await res.json(); toast.error(e.detail || "Checkout failed."); }
    } catch { toast.error("Network error."); }
    setCheckingOut(null);
  };

  return (
    <div className="rounded-sm overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      {/* Tab Header */}
      <div className="flex" style={{ borderBottom: '1px solid var(--border)' }}>
        {[
          { id: "rent", label: "Rent", icon: Tag, sub: "Per output" },
          { id: "acquire", label: "Acquire", icon: FileKey, sub: "Full IP" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPurchaseMode(tab.id)}
            data-testid={`purchase-tab-${tab.id}`}
            className={`flex-1 flex items-center justify-center gap-2 py-4 text-[13px] font-medium transition-all relative ${
              purchaseMode === tab.id ? "t-text" : "t-text-mute"
            }`}
          >
            <tab.icon size={14} />
            <span>{tab.label}</span>
            <span className={`text-[10px] font-normal ${purchaseMode === tab.id ? "t-text-sub" : "t-text-dim"}`}>{tab.sub}</span>
            {purchaseMode === tab.id && (
              <div className="absolute bottom-0 left-[15%] right-[15%] h-[2px] bg-cyan-400 rounded-sm" />
            )}
          </button>
        ))}
      </div>

      {/* Rent State */}
      {purchaseMode === "rent" && (
        <div className="p-5 space-y-5" data-testid="rent-panel">
          {/* Output Slider */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[12px] t-text-sub font-medium">Output Volume</span>
              <span className="text-[13px] t-text font-semibold font-mono">{outputCount.toLocaleString()} outputs</span>
            </div>
            <input
              type="range"
              min={100}
              max={10000}
              step={100}
              value={outputCount}
              onChange={(e) => setOutputCount(Number(e.target.value))}
              data-testid="output-slider"
              className="w-full h-1.5 rounded-sm appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #22d3ee ${((outputCount - 100) / 9900) * 100}%, var(--border) ${((outputCount - 100) / 9900) * 100}%)`,
                accentColor: '#22d3ee',
              }}
            />
            <div className="flex justify-between mt-1.5 text-[10px] t-text-dim">
              <span>100</span>
              <span>2,500</span>
              <span>5,000</span>
              <span>10,000</span>
            </div>
          </div>

          {/* Price Breakdown */}
          <div className="rounded-sm p-4 space-y-2" style={{ background: 'var(--bg-secondary)' }}>
            <div className="flex justify-between text-[12px]">
              <span className="t-text-sub">{outputCount.toLocaleString()} outputs x ${pricePerHundred}/100</span>
              <span className="t-text font-medium">${rentPrice}</span>
            </div>
            <div className="flex justify-between text-[12px]">
              <span className="t-text-sub">Platform fee</span>
              <span className="t-text font-medium">$0</span>
            </div>
            <div className="pt-2 flex justify-between" style={{ borderTop: '1px solid var(--border)' }}>
              <span className="text-[13px] t-text font-semibold">Total</span>
              <span className="text-xl font-bold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>${rentPrice}</span>
            </div>
          </div>

          {/* Rent CTA */}
          <button
            onClick={() => handleCheckout("rent")}
            data-testid="rent-agent-btn"
            disabled={checkingOut === "rent"}
            className="w-full py-3.5 bg-cyan-400 text-white text-[14px] font-medium rounded-sm hover:bg-cyan-300 transition-all shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_30px_rgba(139,92,246,0.4)] flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {checkingOut === "rent" ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Rent Now — ${rentPrice}
          </button>

          {/* Payment Badges */}
          <div className="flex items-center justify-center gap-3">
            <div className="flex items-center gap-1.5 text-[10px] t-text-dim px-2.5 py-1 rounded-sm" style={{ background: 'var(--bg-secondary)' }}>
              <CreditCard size={10} /> Stripe
            </div>
            <div className="flex items-center gap-1.5 text-[10px] t-text-dim px-2.5 py-1 rounded-sm" style={{ background: 'var(--bg-secondary)' }}>
              <Lock size={10} /> Crypto
            </div>
            <span className="text-[10px] t-text-dim">256-bit encrypted</span>
          </div>
        </div>
      )}

      {/* Acquire State */}
      {purchaseMode === "acquire" && (
        <div className="p-5 space-y-5" data-testid="acquire-panel">
          {/* Price Hero */}
          <div className="text-center py-3">
            <p className="text-[11px] t-text-dim tracking-widest uppercase mb-2">One-time acquisition</p>
            <p className="text-4xl font-bold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
              ${acquirePrice.toLocaleString()}
            </p>
            <p className="text-[12px] t-text-sub mt-1">Lifetime ownership. No recurring costs.</p>
          </div>

          {/* Value Props */}
          <div className="space-y-3">
            {[
              { icon: FileKey, label: "Full IP Ownership", desc: "Complete intellectual property transfer. The agent is yours." },
              { icon: Code2, label: "Edit Node Logic", desc: "Full access to underlying workflow nodes. Modify, extend, rebrand." },
              { icon: Server, label: "Your Own Compute", desc: "Deploy on your infrastructure with no platform rate limits." },
              { icon: Cpu, label: "Unlimited Outputs", desc: "No metering. Run as many outputs as your infrastructure allows." },
            ].map((prop) => (
              <div key={prop.label} className="flex items-start gap-3 p-3 rounded-sm transition-all" style={{ background: 'var(--bg-secondary)' }}>
                <div className="w-8 h-8 rounded-lg bg-cyan-400/10 flex items-center justify-center shrink-0 mt-0.5">
                  <prop.icon size={14} className="text-cyan-400" />
                </div>
                <div>
                  <p className="text-[13px] t-text font-medium">{prop.label}</p>
                  <p className="text-[11px] t-text-sub leading-relaxed">{prop.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Acquire CTA */}
          <button
            onClick={() => handleCheckout("buy")}
            data-testid="buy-agent-btn"
            disabled={checkingOut === "buy"}
            className="w-full py-3.5 text-[14px] font-medium rounded-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            style={{
              background: 'linear-gradient(135deg, #22d3ee, #0891b2)',
              color: 'white',
              boxShadow: '0 0 25px rgba(139,92,246,0.3), inset 0 1px 0 rgba(255,255,255,0.1)',
            }}
          >
            {checkingOut === "buy" ? <Loader2 size={14} className="animate-spin" /> : <ShoppingCart size={14} />}
            Buy Outright — ${acquirePrice.toLocaleString()}
          </button>

          {/* Payment Badges */}
          <div className="flex items-center justify-center gap-3">
            <div className="flex items-center gap-1.5 text-[10px] t-text-dim px-2.5 py-1 rounded-sm" style={{ background: 'var(--bg-secondary)' }}>
              <CreditCard size={10} /> Stripe
            </div>
            <div className="flex items-center gap-1.5 text-[10px] t-text-dim px-2.5 py-1 rounded-sm" style={{ background: 'var(--bg-secondary)' }}>
              <Lock size={10} /> Crypto
            </div>
            <span className="text-[10px] t-text-dim">80/20 Revenue Split</span>
          </div>
        </div>
      )}
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
  const [checkingOut, setCheckingOut] = useState(null);

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

  if (loading) return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><Loader2 size={24} className="text-cyan-400 animate-spin" /></div>;
  if (!agent) return <div className="min-h-[calc(100vh-60px)] flex items-center justify-center"><p className="t-text-sub">Agent not found.</p></div>;

  return (
    <div data-testid="agent-detail-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-10 relative">
      <div className="absolute top-0 left-[30%] w-[400px] h-[400px] rounded-sm bg-cyan-400/[0.03] blur-[120px] pointer-events-none t-orb" />
      <div className="max-w-5xl mx-auto relative">
        <Link to="/exchange" data-testid="back-to-marketplace" className="inline-flex items-center gap-1.5 text-[13px] t-text-sub hover:t-text transition-colors mb-6">
          <ArrowLeft size={14} /> Back to The Exchange
        </Link>

        {/* Hero */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-10">
          {/* Left: Image + Demo */}
          <div className="lg:col-span-3">
            <div className="h-64 rounded-sm overflow-hidden relative mb-4" style={{ background: 'var(--bg-secondary)' }}>
              {agent.image ? (
                <img src={agent.image} alt={agent.shortTitle} className="w-full h-full object-cover opacity-50" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-violet-950/60 to-zinc-950" />
              )}
              <button onClick={() => setShowDemo(true)} data-testid="agent-demo-btn" className="absolute bottom-4 left-4 flex items-center gap-2 px-5 py-2.5 bg-cyan-400 text-white text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all shadow-[0_0_20px_rgba(139,92,246,0.3)]">
                <Play size={14} /> Live Demo
              </button>
            </div>

            {/* Video placeholder */}
            <div data-testid="demo-video-placeholder" className="rounded-sm h-48 flex items-center justify-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <div className="text-center">
                <div className="w-14 h-14 rounded-sm flex items-center justify-center mx-auto mb-3" style={{ background: 'var(--bg-card-hover)' }}>
                  <Play size={24} className="t-text-mute ml-1" />
                </div>
                <p className="text-[13px] t-text-sub">Demo video coming soon</p>
              </div>
            </div>
          </div>

          {/* Right: Details + Purchase Panel */}
          <div className="lg:col-span-2 space-y-4">
            {/* Agent Info Card */}
            <div className="rounded-sm p-6" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              {/* Creator */}
              <Link to={`/creator/${agent.creator_id}`} className="flex items-center gap-2.5 mb-4 group">
                <div className="w-8 h-8 rounded-sm flex items-center justify-center text-[12px] text-white font-medium" style={{ background: agent.creator_color }}>
                  {agent.creator_initial}
                </div>
                <span className="text-[13px] t-text-sub group-hover:text-cyan-300 transition-colors">{agent.creator_username}</span>
                {agent.creator_verified && <BadgeCheck size={13} className="text-cyan-400" />}
              </Link>

              <h1 data-testid="agent-detail-title" className="text-xl font-bold t-text mb-3 leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
                {agent.shortTitle}
              </h1>

              {/* Ratings */}
              <div className="flex items-center gap-3 mb-4">
                <span className="flex items-center gap-1 text-[13px]">
                  <Star size={14} className="fill-amber-400 text-amber-400" />
                  <span className="t-text font-medium">{agent.rating}</span>
                  <span className="t-text-sub">({agent.reviews} reviews)</span>
                </span>
                <span className="flex items-center gap-1 text-[13px] t-text-sub">
                  <Shield size={13} className="text-emerald-500" /> {agent.trustScore}
                </span>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                {[
                  { icon: Zap, label: `${agent.deployCount} deploys` },
                  { icon: Clock, label: agent.setupTime },
                  { icon: Users, label: `${agent.reviews} users` },
                ].map((s) => (
                  <div key={s.label} className="rounded-sm p-3 text-center" style={{ background: 'var(--bg-secondary)' }}>
                    <s.icon size={14} className="text-cyan-400 mx-auto mb-1" />
                    <p className="text-[11px] t-text-sub">{s.label}</p>
                  </div>
                ))}
              </div>

              <button onClick={() => setShowDemo(true)} data-testid="try-demo-sidebar-btn" className="w-full py-3 text-[13px] text-cyan-400 border border-cyan-400/30 rounded-sm hover:bg-cyan-400/10 transition-all flex items-center justify-center gap-2">
                <Play size={13} /> Try Live Demo
              </button>
            </div>

            {/* Purchase Panel */}
            <PurchasePanel agent={agent} user={user} token={token} checkingOut={checkingOut} setCheckingOut={setCheckingOut} />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 rounded-sm p-1 w-fit" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} data-testid="agent-tabs">
          {["overview", "reviews"].map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)} data-testid={`tab-${tab}`} className={`px-5 py-2 text-[13px] rounded-sm transition-all capitalize ${activeTab === tab ? "bg-cyan-400 text-white" : "t-text-sub hover:t-text"}`}>{tab}</button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === "overview" && (
          <div data-testid="overview-tab-content" className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-16">
            <div className="rounded-sm p-6" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <h3 className="text-[16px] font-semibold t-text mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>About this agent</h3>
              <p className="text-[14px] t-text-sub leading-relaxed">{agent.longDescription}</p>
            </div>
            <div className="rounded-sm p-6" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <h3 className="text-[16px] font-semibold t-text mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>Features</h3>
              <div className="space-y-3">
                {agent.features.map((f, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className="text-[14px] t-text-sub">{f}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "reviews" && (
          <div data-testid="reviews-tab-content" className="max-w-2xl mb-16">
            <div className="flex items-center gap-4 mb-6">
              <span className="text-3xl font-bold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>{agent.rating}</span>
              <div>
                <div className="flex items-center gap-0.5 mb-1">
                  {[1,2,3,4,5].map((s) => <Star key={s} size={16} className={s <= Math.round(agent.rating) ? "fill-amber-400 text-amber-400" : "t-text-dim"} />)}
                </div>
                <p className="text-[13px] t-text-sub">{agent.reviews} reviews</p>
              </div>
            </div>
            <div className="space-y-4">
              {reviews.map((r) => (
                <div key={r.id} data-testid={`review-${r.id}`} className="rounded-sm p-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-sm flex items-center justify-center text-[11px] t-text-sub font-medium" style={{ background: 'var(--bg-secondary)' }}>{r.user_name[0]}</div>
                      <span className="text-[13px] t-text font-medium">{r.user_name}</span>
                    </div>
                    <span className="text-[12px] t-text-dim">{r.date}</span>
                  </div>
                  <div className="flex items-center gap-0.5 mb-2">
                    {[1,2,3,4,5].map((s) => <Star key={s} size={12} className={s <= r.rating ? "fill-amber-400 text-amber-400" : "t-text-dim"} />)}
                  </div>
                  <p className="text-[13px] t-text-sub leading-relaxed">{r.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {showDemo && <LiveDemoModal agent={agent} onClose={() => setShowDemo(false)} />}
    </div>
  );
}

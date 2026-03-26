import { Store, ShoppingCart, Tag } from "lucide-react";

const agentCards = [
  {
    id: 1,
    title: "Customer Service Pro",
    description: "Autonomous agent that handles support tickets, resolves issues, and escalates edge cases with human-like empathy.",
    image: "https://images.unsplash.com/photo-1744324480866-1794a1bf193c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwzfHxmdXR1cmlzdGljJTIwYWklMjBicmFpbiUyMGRhcmt8ZW58MHx8fHwxNzc0NDg1NjE4fDA&ixlib=rb-4.1.0&q=85",
    price: "$49/mo",
  },
  {
    id: 2,
    title: "Sales Dev Rep",
    description: "AI-powered outbound prospecting agent that qualifies leads, personalizes outreach, and books meetings.",
    image: "https://images.pexels.com/photos/5181148/pexels-photo-5181148.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    price: "$79/mo",
  },
  {
    id: 3,
    title: "Data Analyst",
    description: "Turns raw datasets into actionable insights with automated reporting, anomaly detection, and trend analysis.",
    image: "https://images.unsplash.com/photo-1697899001862-59699946ea29?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMDNkJTIwZ2VvbWV0cmljJTIwc2hhcGUlMjBkYXJrJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzQ0ODU2MTR8MA&ixlib=rb-4.1.0&q=85",
    price: "$99/mo",
  },
];

export default function Marketplace() {
  return (
    <div className="min-h-[calc(100vh-64px)] px-6 lg:px-8 py-16 md:py-24">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div
          className="text-center mb-16 animate-fade-in-up"
          style={{ animationFillMode: "forwards" }}
        >
          <div className="inline-flex items-center gap-2 mb-8 border border-zinc-800 px-4 py-2">
            <Store size={14} className="text-[#00E5FF]" />
            <span
              data-testid="marketplace-badge"
              className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500"
            >
              Coming Soon
            </span>
          </div>
          <h1
            className="text-5xl md:text-6xl lg:text-[5rem] font-black tracking-tighter leading-none text-white mb-6"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            Nova <span className="text-[#B900FF]">Marketplace</span>
          </h1>
          <p className="text-base md:text-lg text-zinc-400 max-w-lg mx-auto">
            Discover, rent, and deploy production-ready AI agents.
          </p>
        </div>

        {/* Agent Cards Grid */}
        <div
          data-testid="agent-cards-grid"
          className="grid grid-cols-1 md:grid-cols-3 gap-6"
        >
          {agentCards.map((agent, index) => (
            <div
              key={agent.id}
              data-testid={`agent-card-${agent.id}`}
              className="bg-zinc-900 border border-zinc-800 overflow-hidden transition-all duration-300 hover:border-[#B900FF] hover:shadow-[0_0_20px_rgba(185,0,255,0.1)] group opacity-0 animate-fade-in-up"
              style={{ animationDelay: `${index * 100 + 200}ms`, animationFillMode: "forwards" }}
            >
              {/* Image */}
              <div className="h-48 overflow-hidden">
                <img
                  src={agent.image}
                  alt={agent.title}
                  className="w-full h-full object-cover opacity-60 group-hover:opacity-80 transition-opacity duration-500 group-hover:scale-105 transition-transform"
                />
              </div>

              {/* Content */}
              <div className="p-6">
                <div className="flex items-center justify-between mb-3">
                  <h3
                    className="text-lg font-bold text-white tracking-tight"
                    style={{ fontFamily: "'Outfit', sans-serif" }}
                  >
                    {agent.title}
                  </h3>
                  <span className="text-xs font-mono text-[#00E5FF]">
                    {agent.price}
                  </span>
                </div>
                <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
                  {agent.description}
                </p>

                {/* Disabled Buttons */}
                <div className="flex gap-3">
                  <button
                    disabled
                    data-testid={`agent-rent-btn-${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-2 py-3 opacity-50 cursor-not-allowed bg-zinc-800 text-zinc-500 border border-zinc-700 text-xs font-semibold uppercase tracking-wider"
                  >
                    <Tag size={12} />
                    Rent
                  </button>
                  <button
                    disabled
                    data-testid={`agent-buy-btn-${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-2 py-3 opacity-50 cursor-not-allowed bg-zinc-800 text-zinc-500 border border-zinc-700 text-xs font-semibold uppercase tracking-wider"
                  >
                    <ShoppingCart size={12} />
                    Buy
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

import { Store, ShoppingCart, Tag } from "lucide-react";

const agentCards = [
  {
    id: 1,
    title: "Customer Service Pro",
    description: "Handles support tickets, resolves issues, and escalates edge cases with human-like empathy.",
    image: "https://images.unsplash.com/photo-1744324480866-1794a1bf193c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwzfHxmdXR1cmlzdGljJTIwYWklMjBicmFpbiUyMGRhcmt8ZW58MHx8fHwxNzc0NDg1NjE4fDA&ixlib=rb-4.1.0&q=85",
    price: "$49/mo",
  },
  {
    id: 2,
    title: "Sales Dev Rep",
    description: "AI-powered outbound prospecting that qualifies leads, personalizes outreach, and books meetings.",
    image: "https://images.pexels.com/photos/5181148/pexels-photo-5181148.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    price: "$79/mo",
  },
  {
    id: 3,
    title: "Data Analyst",
    description: "Turns raw datasets into actionable insights with automated reporting and anomaly detection.",
    image: "https://images.unsplash.com/photo-1697899001862-59699946ea29?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2ODh8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMDNkJTIwZ2VvbWV0cmljJTIwc2hhcGUlMjBkYXJrJTIwYmFja2dyb3VuZHxlbnwwfHx8fDE3NzQ0ODU2MTR8MA&ixlib=rb-4.1.0&q=85",
    price: "$99/mo",
  },
];

export default function Marketplace() {
  return (
    <div className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-20 md:py-28 relative">
      <div className="absolute top-[5%] right-[20%] w-[350px] h-[350px] rounded-full bg-[#8B5CF6]/[0.04] blur-[100px] pointer-events-none" />

      <div className="max-w-5xl mx-auto relative">
        {/* Header */}
        <div
          className="text-center mb-16 animate-fade-in-up"
          style={{ animationFillMode: "forwards" }}
        >
          <div className="inline-flex items-center gap-2 mb-10 bg-white/[0.04] border border-white/[0.08] px-4 py-1.5 rounded-full">
            <Store size={13} className="text-[#8B5CF6]" />
            <span
              data-testid="marketplace-badge"
              className="text-[11px] tracking-[0.15em] text-zinc-500"
            >
              Coming Soon
            </span>
          </div>
          <h1
            className="text-4xl sm:text-5xl lg:text-[4.25rem] font-bold tracking-[-0.03em] leading-[1.08] text-white mb-5"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            Nova <span className="text-gradient-purple">Marketplace</span>
          </h1>
          <p className="text-base md:text-lg text-zinc-500 max-w-sm mx-auto leading-relaxed">
            Discover, rent, and deploy production-ready AI agents.
          </p>
        </div>

        {/* Agent Cards Grid */}
        <div
          data-testid="agent-cards-grid"
          className="grid grid-cols-1 md:grid-cols-3 gap-5"
        >
          {agentCards.map((agent, index) => (
            <div
              key={agent.id}
              data-testid={`agent-card-${agent.id}`}
              className="bg-white/[0.03] border border-white/[0.07] rounded-2xl overflow-hidden transition-all duration-300 hover:border-[#8B5CF6]/30 hover:shadow-[0_0_30px_rgba(139,92,246,0.08)] group opacity-0 animate-fade-in-up"
              style={{ animationDelay: `${index * 100 + 200}ms`, animationFillMode: "forwards" }}
            >
              {/* Image */}
              <div className="h-44 overflow-hidden">
                <img
                  src={agent.image}
                  alt={agent.title}
                  className="w-full h-full object-cover opacity-50 group-hover:opacity-70 group-hover:scale-105 transition-all duration-700"
                />
              </div>

              {/* Content */}
              <div className="p-5">
                <div className="flex items-center justify-between mb-2.5">
                  <h3
                    className="text-[15px] font-semibold text-white tracking-tight"
                    style={{ fontFamily: "'Outfit', sans-serif" }}
                  >
                    {agent.title}
                  </h3>
                  <span className="text-[12px] text-[#A78BFA] font-medium">
                    {agent.price}
                  </span>
                </div>
                <p className="text-[13px] text-zinc-500 mb-5 leading-relaxed">
                  {agent.description}
                </p>

                {/* Disabled Buttons */}
                <div className="flex gap-2.5">
                  <button
                    disabled
                    data-testid={`agent-rent-btn-${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 opacity-40 cursor-not-allowed bg-white/[0.04] text-zinc-500 border border-white/[0.08] text-[12px] font-medium rounded-lg"
                  >
                    <Tag size={11} />
                    Rent
                  </button>
                  <button
                    disabled
                    data-testid={`agent-buy-btn-${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 opacity-40 cursor-not-allowed bg-white/[0.04] text-zinc-500 border border-white/[0.08] text-[12px] font-medium rounded-lg"
                  >
                    <ShoppingCart size={11} />
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

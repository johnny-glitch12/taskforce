import { useState } from "react";
import { toast } from "sonner";
import {
  Send,
  Rocket,
  Bot,
  Zap,
  Mail,
  Brain,
  FileText,
  ChevronRight,
} from "lucide-react";

/* ─── Mock Data ─── */
const mockMessages = [
  {
    role: "user",
    content: "Build an agent that handles customer refunds",
  },
  {
    role: "assistant",
    content:
      "I'll create a refund agent with email trigger, sentiment analysis, and automated reply drafting. Setting up 3 nodes...",
  },
  {
    role: "user",
    content: "Add a condition to escalate if refund > $500",
  },
  {
    role: "assistant",
    content:
      "Added a conditional branch node. Refunds over $500 will route to human review. The flow is now: Trigger -> Analyze -> Branch -> Draft Reply / Escalate.",
  },
];

const mockCode = `{
  "agent": "refund-handler-v1",
  "version": "0.3.0",
  "nodes": [
    {
      "id": "trigger_001",
      "type": "trigger",
      "config": {
        "source": "email",
        "filter": "subject:refund"
      }
    },
    {
      "id": "llm_001",
      "type": "llm",
      "config": {
        "model": "nova-7b",
        "task": "sentiment_analysis",
        "temperature": 0.2
      }
    },
    {
      "id": "action_001",
      "type": "action",
      "config": {
        "type": "draft_reply",
        "template": "refund_approved",
        "tone": "empathetic"
      }
    }
  ],
  "edges": [
    { "from": "trigger_001", "to": "llm_001" },
    { "from": "llm_001", "to": "action_001" }
  ]
}`;

/* ─── Canvas Nodes ─── */
const nodes = [
  { id: "n1", label: "Trigger", sub: "Email Received", icon: Mail, x: 60, y: 80 },
  { id: "n2", label: "LLM", sub: "Analyze Sentiment", icon: Brain, x: 320, y: 50 },
  { id: "n3", label: "Condition", sub: "Refund > $500?", icon: Zap, x: 580, y: 120 },
  { id: "n4", label: "Action", sub: "Draft Reply", icon: FileText, x: 840, y: 60 },
];

const edges = [
  { from: "n1", to: "n2" },
  { from: "n2", to: "n3" },
  { from: "n3", to: "n4" },
];

/* ─── Helpers ─── */
function getNodeCenter(node) {
  return { x: node.x + 100, y: node.y + 36 };
}

/* ─── Components ─── */

function ChatPane() {
  const [input, setInput] = useState("");

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    toast.success("Prompt sent to agent builder.");
    setInput("");
  };

  return (
    <div
      data-testid="studio-chat-pane"
      className="w-full lg:w-1/4 border-r border-white/[0.06] bg-zinc-950 flex flex-col h-full"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
        <Bot size={14} className="text-[#8B5CF6]" />
        <span className="text-[12px] tracking-wide text-zinc-500">
          Vibe Chat
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {mockMessages.map((msg, i) => (
          <div
            key={i}
            data-testid={`chat-message-${i}`}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-xl ${
                msg.role === "user"
                  ? "bg-[#8B5CF6]/10 text-zinc-200 border border-[#8B5CF6]/20"
                  : "bg-white/[0.03] text-zinc-400 border border-white/[0.06]"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSend}
        data-testid="chat-input-form"
        className="px-4 py-3 border-t border-white/[0.06] flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe your agent..."
          data-testid="chat-input"
          className="flex-1 bg-transparent text-[13px] text-white placeholder:text-zinc-600 focus:outline-none"
        />
        <button
          type="submit"
          data-testid="chat-send-btn"
          className="p-2 text-[#8B5CF6] hover:text-[#A78BFA] transition-colors"
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}

function CanvasPane() {
  const [activeNode, setActiveNode] = useState("n2");

  return (
    <div
      data-testid="studio-canvas-pane"
      className="hidden lg:block w-1/2 bg-zinc-950 relative overflow-hidden canvas-grid"
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 px-4 py-3 bg-zinc-950/80 backdrop-blur-sm border-b border-white/[0.06] flex items-center gap-2 z-20">
        <Zap size={14} className="text-[#A78BFA]" />
        <span className="text-[12px] tracking-wide text-zinc-500">
          Visual Canvas
        </span>
      </div>

      {/* SVG Lines */}
      <svg className="absolute inset-0 w-full h-full z-0 pointer-events-none" style={{ marginTop: '48px' }}>
        {edges.map((edge) => {
          const fromNode = nodes.find((n) => n.id === edge.from);
          const toNode = nodes.find((n) => n.id === edge.to);
          const from = getNodeCenter(fromNode);
          const to = getNodeCenter(toNode);
          const isActive = edge.from === activeNode || edge.to === activeNode;
          const midX = (from.x + to.x) / 2;
          return (
            <path
              key={`${edge.from}-${edge.to}`}
              d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
              className={`fill-none animate-line-draw ${
                isActive
                  ? "stroke-[#8B5CF6] stroke-[2px]"
                  : "stroke-zinc-800 stroke-[1.5px]"
              }`}
              style={{
                filter: isActive ? "drop-shadow(0 0 8px rgba(139,92,246,0.4))" : "none",
              }}
            />
          );
        })}
      </svg>

      {/* Nodes */}
      {nodes.map((node) => {
        const Icon = node.icon;
        const isActive = node.id === activeNode;
        return (
          <div
            key={node.id}
            data-testid={`canvas-node-${node.id}`}
            onClick={() => setActiveNode(node.id)}
            className={`absolute z-10 min-w-[200px] p-4 cursor-pointer rounded-xl transition-all duration-300 ${
              isActive
                ? "bg-white/[0.05] border border-[#8B5CF6]/50 shadow-[0_0_20px_rgba(139,92,246,0.15)]"
                : "bg-white/[0.03] border border-white/[0.07] hover:border-[#8B5CF6]/30 hover:shadow-[0_0_15px_rgba(139,92,246,0.08)]"
            }`}
            style={{ left: node.x, top: node.y + 48 }}
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-8 h-8 flex items-center justify-center rounded-lg ${
                  isActive ? "bg-[#8B5CF6]/15" : "bg-white/[0.04]"
                }`}
              >
                <Icon
                  size={14}
                  className={isActive ? "text-[#8B5CF6]" : "text-zinc-500"}
                />
              </div>
              <div>
                <p
                  className={`text-[11px] tracking-wider ${
                    isActive ? "text-[#A78BFA]" : "text-zinc-600"
                  }`}
                >
                  {node.label}
                </p>
                <p className="text-[13px] text-white font-medium">{node.sub}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CodePane() {
  const handleDeploy = () => {
    toast.success("Agent deployed successfully.");
  };

  return (
    <div
      data-testid="studio-code-pane"
      className="w-full lg:w-1/4 border-l border-white/[0.06] bg-zinc-900/50 flex flex-col h-full"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-zinc-500" />
          <span className="text-[12px] tracking-wide text-zinc-500">
            agent.json
          </span>
        </div>
        <button
          onClick={handleDeploy}
          data-testid="deploy-agent-btn"
          className="flex items-center gap-1.5 px-4 py-1.5 bg-[#8B5CF6] text-white text-[12px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_15px_rgba(139,92,246,0.2)] hover:shadow-[0_0_25px_rgba(139,92,246,0.35)]"
        >
          <Rocket size={11} />
          Deploy
        </button>
      </div>

      {/* Code */}
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="text-xs leading-relaxed" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {mockCode.split("\n").map((line, i) => (
            <div key={i} className="flex">
              <span className="w-8 text-right pr-4 text-zinc-700 select-none">{i + 1}</span>
              <span>
                {colorize(line)}
              </span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

/* Syntax highlighting helper */
function colorize(line) {
  const parts = [];
  let remaining = line;
  let key = 0;

  // Highlight strings
  const stringRegex = /"([^"]*)"/g;
  let match;
  let lastIndex = 0;

  while ((match = stringRegex.exec(remaining)) !== null) {
    // Text before match
    if (match.index > lastIndex) {
      parts.push(
        <span key={key++} className="text-zinc-400">
          {remaining.slice(lastIndex, match.index)}
        </span>
      );
    }

    // Check if it's a key (followed by :)
    const afterMatch = remaining.slice(match.index + match[0].length);
    if (afterMatch.trimStart().startsWith(":")) {
      parts.push(
        <span key={key++} className="text-zinc-300">
          "{match[1]}"
        </span>
      );
    } else {
      parts.push(
        <span key={key++} className="text-[#A78BFA]">
          "{match[1]}"
        </span>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < remaining.length) {
    const rest = remaining.slice(lastIndex);
    // Highlight numbers
    const numHighlighted = rest.replace(/\b(\d+\.?\d*)\b/g, '___NUM___$1___ENDNUM___');
    const numParts = numHighlighted.split(/(___NUM___[\d.]+___ENDNUM___)/);
    numParts.forEach((part) => {
      const numMatch = part.match(/___NUM___([\d.]+)___ENDNUM___/);
      if (numMatch) {
        parts.push(
          <span key={key++} className="text-cyan-300">
            {numMatch[1]}
          </span>
        );
      } else {
        // Highlight brackets and braces
        const bracketHighlighted = part.split(/([{}[\],:])/);
        bracketHighlighted.forEach((bp) => {
          if (/^[{}[\],:]$/.test(bp)) {
            parts.push(
              <span key={key++} className="text-zinc-600">
                {bp}
              </span>
            );
          } else {
            parts.push(
              <span key={key++} className="text-zinc-400">
                {bp}
              </span>
            );
          }
        });
      }
    });
  }

  return parts;
}

/* ─── Main Studio ─── */
export default function Studio() {
  return (
    <div
      data-testid="studio-page"
      className="flex flex-col lg:flex-row h-[calc(100vh-60px)] w-full bg-zinc-950 overflow-hidden"
    >
      <ChatPane />
      <CanvasPane />
      <CodePane />
    </div>
  );
}

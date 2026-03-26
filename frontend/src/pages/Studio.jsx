import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  Send, Rocket, Bot, Zap, Mail, Brain, FileText,
  MessageCircle, GitBranch, Sparkles, Plus, Save,
  Trash2, ChevronDown, Shield, AlertTriangle, Check,
  X, GripVertical, Copy, Download,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const NODE_TYPES = [
  { type: "trigger", label: "Trigger", icon: "Mail", color: "#8B5CF6" },
  { type: "llm", label: "LLM", icon: "Brain", color: "#A78BFA" },
  { type: "condition", label: "Condition", icon: "Zap", color: "#6D28D9" },
  { type: "action", label: "Action", icon: "FileText", color: "#7C3AED" },
  { type: "http_request", label: "HTTP Request", icon: "Zap", color: "#5B21B6" },
  { type: "webhook", label: "Webhook", icon: "Zap", color: "#C084FC" },
];

const ICON_MAP = { Mail, Brain, Zap, FileText, MessageCircle, GitBranch };

function getIcon(iconName) {
  return ICON_MAP[iconName] || Zap;
}

/* ─── Mode Toggle ─── */
function ModeToggle({ mode, setMode }) {
  return (
    <div data-testid="mode-toggle" className="flex items-center justify-center gap-1 bg-white/[0.03] border border-white/[0.07] rounded-full p-1">
      <button
        onClick={() => setMode("vibe")}
        data-testid="vibe-mode-btn"
        className={`flex items-center gap-2 px-5 py-2 text-[13px] rounded-full transition-all duration-300 ${
          mode === "vibe"
            ? "bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.25)]"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        <MessageCircle size={14} /> Vibe Mode
      </button>
      <button
        onClick={() => setMode("node")}
        data-testid="node-mode-btn"
        className={`flex items-center gap-2 px-5 py-2 text-[13px] rounded-full transition-all duration-300 ${
          mode === "node"
            ? "bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.25)]"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        <GitBranch size={14} /> Node Mode
      </button>
    </div>
  );
}

/* ─── Chat Pane (Vibe Mode) ─── */
function ChatPane({ expanded, messages, onSend }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div
      data-testid="studio-chat-pane"
      className={`border-r border-white/[0.06] bg-zinc-950 flex flex-col h-full transition-all duration-500 ease-in-out ${
        expanded ? "w-full lg:w-3/4" : "w-full lg:w-1/4"
      }`}
    >
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
        <Bot size={14} className="text-[#8B5CF6]" />
        <span className="text-[12px] tracking-wide text-zinc-500">Vibe Chat</span>
        {expanded && (
          <span className="ml-auto text-[11px] text-zinc-600 bg-white/[0.04] px-2.5 py-0.5 rounded-full">
            Describe your agent in plain English
          </span>
        )}
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
            <Bot size={32} className="text-zinc-700 mb-3" />
            <p className="text-[13px] text-zinc-600">Start describing your agent.</p>
            <p className="text-[11px] text-zinc-700 mt-1">e.g. "Build an agent that handles customer refunds"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} data-testid={`chat-message-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-xl ${
              msg.role === "user"
                ? "bg-[#8B5CF6]/10 text-zinc-200 border border-[#8B5CF6]/20"
                : "bg-white/[0.03] text-zinc-400 border border-white/[0.06]"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={handleSend} data-testid="chat-input-form" className="px-4 py-3 border-t border-white/[0.06] flex gap-2">
        <input
          type="text" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={expanded ? "Tell me what your agent should do..." : "Describe your agent..."}
          data-testid="chat-input"
          className="flex-1 bg-transparent text-[13px] text-white placeholder:text-zinc-600 focus:outline-none"
        />
        <button type="submit" data-testid="chat-send-btn" className="p-2 text-[#8B5CF6] hover:text-[#A78BFA] transition-colors">
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}

/* ─── Canvas Pane (Node Mode) ─── */
function CanvasPane({ expanded, nodes, edges, activeNode, setActiveNode, onUpdateNode, onAddNode, onDeleteNode }) {
  const [showNodeMenu, setShowNodeMenu] = useState(false);
  const canvasRef = useRef(null);

  function getNodeCenter(node) {
    return { x: node.x + 100, y: node.y + 36 };
  }

  const handleAddNode = (type) => {
    const newNode = {
      id: `node_${Date.now()}`,
      type: type.type,
      label: type.label,
      sub: "Configure me",
      icon: type.icon,
      x: 60 + (nodes.length % 4) * 260,
      y: 80 + Math.floor(nodes.length / 4) * 120,
      data: {},
    };
    onAddNode(newNode);
    setShowNodeMenu(false);
  };

  return (
    <div
      data-testid="studio-canvas-pane"
      className={`hidden lg:block bg-zinc-950 relative overflow-hidden canvas-grid transition-all duration-500 ease-in-out ${
        expanded ? "w-3/4 opacity-100" : "w-0 opacity-0 pointer-events-none overflow-hidden"
      }`}
      ref={canvasRef}
    >
      <div className="absolute top-0 left-0 right-0 px-4 py-3 bg-zinc-950/80 backdrop-blur-sm border-b border-white/[0.06] flex items-center gap-2 z-20">
        <Zap size={14} className="text-[#A78BFA]" />
        <span className="text-[12px] tracking-wide text-zinc-500">Node Canvas</span>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <button
              data-testid="add-node-btn"
              onClick={() => setShowNodeMenu(!showNodeMenu)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-400 text-[11px] rounded-lg hover:border-[#8B5CF6]/30 transition-all"
            >
              <Plus size={12} /> Add Node
            </button>
            {showNodeMenu && (
              <div data-testid="node-type-menu" className="absolute right-0 top-full mt-1 w-48 bg-zinc-900 border border-white/[0.08] rounded-xl p-1.5 z-50 shadow-xl">
                {NODE_TYPES.map((nt) => (
                  <button
                    key={nt.type}
                    data-testid={`add-node-${nt.type}`}
                    onClick={() => handleAddNode(nt)}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-zinc-300 hover:bg-white/[0.06] rounded-lg transition-colors"
                  >
                    <div className="w-5 h-5 rounded flex items-center justify-center" style={{ background: `${nt.color}20` }}>
                      <Zap size={10} style={{ color: nt.color }} />
                    </div>
                    {nt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SVG Edges */}
      <svg className="absolute inset-0 w-full h-full z-0 pointer-events-none" style={{ marginTop: "48px" }}>
        {edges.map((edge, i) => {
          const fromNode = nodes.find((n) => n.id === (edge.from || edge.source));
          const toNode = nodes.find((n) => n.id === (edge.to || edge.target));
          if (!fromNode || !toNode) return null;
          const from = getNodeCenter(fromNode);
          const to = getNodeCenter(toNode);
          const isActive = (edge.from || edge.source) === activeNode || (edge.to || edge.target) === activeNode;
          const midX = (from.x + to.x) / 2;
          return (
            <path
              key={i}
              d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
              className={`fill-none animate-line-draw ${isActive ? "stroke-[#8B5CF6] stroke-[2px]" : "stroke-zinc-800 stroke-[1.5px]"}`}
              style={{ filter: isActive ? "drop-shadow(0 0 8px rgba(139,92,246,0.4))" : "none" }}
            />
          );
        })}
      </svg>

      {/* Nodes */}
      {nodes.map((node) => {
        const Icon = getIcon(node.icon);
        const isActive = node.id === activeNode;
        return (
          <div
            key={node.id}
            data-testid={`canvas-node-${node.id}`}
            onClick={() => setActiveNode(node.id)}
            className={`absolute z-10 min-w-[200px] p-4 cursor-pointer rounded-xl transition-all duration-300 group ${
              isActive
                ? "bg-white/[0.05] border border-[#8B5CF6]/50 shadow-[0_0_20px_rgba(139,92,246,0.15)]"
                : "bg-white/[0.03] border border-white/[0.07] hover:border-[#8B5CF6]/30 hover:shadow-[0_0_15px_rgba(139,92,246,0.08)]"
            }`}
            style={{ left: node.x, top: node.y + 48 }}
          >
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${isActive ? "bg-[#8B5CF6]/15" : "bg-white/[0.04]"}`}>
                <Icon size={14} className={isActive ? "text-[#8B5CF6]" : "text-zinc-500"} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-[11px] tracking-wider ${isActive ? "text-[#A78BFA]" : "text-zinc-600"}`}>{node.label}</p>
                <p className="text-[13px] text-white font-medium truncate">{node.sub}</p>
              </div>
              {isActive && (
                <button
                  data-testid={`delete-node-${node.id}`}
                  onClick={(e) => { e.stopPropagation(); onDeleteNode(node.id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-zinc-600 hover:text-red-400 transition-all"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>
        );
      })}

      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ marginTop: "48px" }}>
          <div className="text-center opacity-50">
            <GitBranch size={32} className="text-zinc-700 mx-auto mb-3" />
            <p className="text-[13px] text-zinc-600">No nodes yet. Click "Add Node" to begin.</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Code Pane with Linter ─── */
function CodePane({ codeJson, onDeploy, linterResult, onRunLinter, saving }) {
  const lines = codeJson ? codeJson.split("\n") : ["// No workflow data yet"];

  const handleCopy = () => {
    navigator.clipboard.writeText(codeJson || "");
    toast.success("Copied to clipboard.");
  };

  return (
    <div data-testid="studio-code-pane" className="w-full lg:w-1/4 border-l border-white/[0.06] bg-zinc-900/50 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-zinc-500" />
          <span className="text-[12px] tracking-wide text-zinc-500">agent.json</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            data-testid="copy-code-btn"
            className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Copy"
          >
            <Copy size={12} />
          </button>
          <button
            onClick={onRunLinter}
            data-testid="run-linter-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-400 text-[11px] rounded-full hover:border-[#8B5CF6]/30 transition-all"
          >
            <Shield size={11} /> Scan
          </button>
          <button
            onClick={onDeploy}
            data-testid="deploy-agent-btn"
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-[#8B5CF6] text-white text-[12px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_15px_rgba(139,92,246,0.2)] hover:shadow-[0_0_25px_rgba(139,92,246,0.35)] disabled:opacity-50"
          >
            <Rocket size={11} /> {saving ? "Saving..." : "Deploy"}
          </button>
        </div>
      </div>

      {/* Linter Result Banner */}
      {linterResult && (
        <div
          data-testid="linter-result"
          className={`px-4 py-2.5 border-b flex items-center gap-2 text-[12px] ${
            linterResult.status === "certified"
              ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
              : linterResult.status === "flagged"
              ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
              : "bg-red-500/5 border-red-500/20 text-red-400"
          }`}
        >
          {linterResult.status === "certified" ? <Check size={13} /> : <AlertTriangle size={13} />}
          <span>Trust Score: <strong>{linterResult.trust_score}</strong></span>
          <span className="mx-1 text-zinc-700">|</span>
          <span className="capitalize">{linterResult.status}</span>
          {linterResult.flags.length > 0 && (
            <span className="text-zinc-500 ml-auto">{linterResult.flags.length} issue{linterResult.flags.length > 1 ? "s" : ""}</span>
          )}
        </div>
      )}

      {/* Linter Flags */}
      {linterResult && linterResult.flags.length > 0 && (
        <div className="px-4 py-2 border-b border-white/[0.04] max-h-[120px] overflow-y-auto">
          {linterResult.flags.map((flag, i) => (
            <div key={i} data-testid={`linter-flag-${i}`} className="flex items-start gap-2 py-1.5 text-[11px]">
              <span className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
                flag.level === "critical" ? "bg-red-400" : flag.level === "warning" ? "bg-amber-400" : "bg-blue-400"
              }`} />
              <span className="text-zinc-500">{flag.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        <pre className="text-xs leading-relaxed" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {lines.map((line, i) => (
            <div key={i} className="flex">
              <span className="w-8 text-right pr-4 text-zinc-700 select-none">{i + 1}</span>
              <span>{colorize(line)}</span>
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
  let key = 0;
  const stringRegex = /"([^"]*)"/g;
  let match;
  let lastIndex = 0;
  while ((match = stringRegex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++} className="text-zinc-400">{line.slice(lastIndex, match.index)}</span>);
    }
    const after = line.slice(match.index + match[0].length);
    if (after.trimStart().startsWith(":")) {
      parts.push(<span key={key++} className="text-zinc-300">"{match[1]}"</span>);
    } else {
      parts.push(<span key={key++} className="text-[#A78BFA]">"{match[1]}"</span>);
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < line.length) {
    const rest = line.slice(lastIndex);
    const numHighlighted = rest.replace(/\b(\d+\.?\d*)\b/g, "___NUM___$1___ENDNUM___");
    numHighlighted.split(/(___NUM___[\d.]+___ENDNUM___)/).forEach((part) => {
      const numMatch = part.match(/___NUM___([\d.]+)___ENDNUM___/);
      if (numMatch) {
        parts.push(<span key={key++} className="text-cyan-300">{numMatch[1]}</span>);
      } else {
        part.split(/([{}[\],:])/).forEach((bp) => {
          if (/^[{}[\],:]$/.test(bp)) {
            parts.push(<span key={key++} className="text-zinc-600">{bp}</span>);
          } else {
            parts.push(<span key={key++} className="text-zinc-400">{bp}</span>);
          }
        });
      }
    });
  }
  return parts;
}

/* ─── Workflow Selector ─── */
function WorkflowSelector({ workflows, activeId, onSelect, onCreate, onDelete }) {
  const [open, setOpen] = useState(false);
  const active = workflows.find((w) => w.id === activeId);

  return (
    <div className="relative">
      <button
        data-testid="workflow-selector-btn"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-300 text-[12px] rounded-lg hover:border-[#8B5CF6]/30 transition-all max-w-[200px]"
      >
        <FileText size={12} />
        <span className="truncate">{active?.name || "No workflow"}</span>
        <ChevronDown size={12} className="text-zinc-600 shrink-0" />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-56 bg-zinc-900 border border-white/[0.08] rounded-xl p-1.5 z-50 shadow-xl">
          {workflows.map((wf) => (
            <div key={wf.id} className="flex items-center group">
              <button
                data-testid={`select-workflow-${wf.id}`}
                onClick={() => { onSelect(wf.id); setOpen(false); }}
                className={`flex-1 text-left px-3 py-2 text-[12px] rounded-lg transition-colors truncate ${
                  wf.id === activeId ? "text-white bg-[#8B5CF6]/10" : "text-zinc-400 hover:bg-white/[0.06]"
                }`}
              >
                {wf.name}
              </button>
              <button
                onClick={() => onDelete(wf.id)}
                className="opacity-0 group-hover:opacity-100 p-1 text-zinc-600 hover:text-red-400 transition-all mr-1"
              >
                <X size={11} />
              </button>
            </div>
          ))}
          <div className="border-t border-white/[0.06] mt-1 pt-1">
            <button
              data-testid="create-workflow-btn"
              onClick={() => { onCreate(); setOpen(false); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-[#A78BFA] hover:bg-white/[0.06] rounded-lg transition-colors"
            >
              <Plus size={12} /> New Workflow
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main Studio ─── */
export default function Studio() {
  const { token } = useAuth();
  const [mode, setMode] = useState("vibe");
  const [workflows, setWorkflows] = useState([]);
  const [activeWorkflowId, setActiveWorkflowId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [codeJson, setCodeJson] = useState("");
  const [activeNode, setActiveNode] = useState(null);
  const [linterResult, setLinterResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const autoSaveRef = useRef(null);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // Generate code JSON from nodes/edges
  const generateCodeJson = useCallback((n, e) => {
    if (n.length === 0) return "";
    const workflow = {
      agent: "custom-agent-v1",
      version: "1.0.0",
      nodes: n.map((node) => ({
        id: node.id,
        type: node.type,
        config: {
          label: node.label,
          description: node.sub,
          ...node.data,
        },
      })),
      edges: e.map((edge) => ({
        from: edge.from || edge.source,
        to: edge.to || edge.target,
      })),
    };
    return JSON.stringify(workflow, null, 2);
  }, []);

  // Load workflows on mount
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/studio/workflows`, { headers })
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setWorkflows(data);
          loadWorkflow(data[0]);
        }
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, [token]);

  const loadWorkflow = (wf) => {
    setActiveWorkflowId(wf.id);
    setMessages(wf.vibe_messages || []);
    setNodes(wf.nodes || []);
    setEdges(wf.edges || []);
    setCodeJson(wf.code_json || generateCodeJson(wf.nodes || [], wf.edges || []));
    setMode(wf.mode || "vibe");
    setLinterResult(wf.trust_score != null ? { trust_score: wf.trust_score, status: wf.linter_status || "unknown", flags: [] } : null);
    setActiveNode(null);
  };

  // Auto-save workflow
  const saveWorkflow = useCallback(async (overrideData = {}) => {
    if (!activeWorkflowId || !token) return;
    setSaving(true);
    const payload = {
      mode,
      vibe_messages: messages,
      nodes,
      edges,
      code_json: codeJson || generateCodeJson(nodes, edges),
      ...overrideData,
    };
    try {
      const res = await fetch(`${API}/api/studio/workflows/${activeWorkflowId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const updated = await res.json();
        setWorkflows((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
      }
    } catch {}
    setSaving(false);
  }, [activeWorkflowId, token, mode, messages, nodes, edges, codeJson, generateCodeJson]);

  // Debounced auto-save
  useEffect(() => {
    if (!activeWorkflowId || !loaded) return;
    clearTimeout(autoSaveRef.current);
    autoSaveRef.current = setTimeout(() => saveWorkflow(), 2000);
    return () => clearTimeout(autoSaveRef.current);
  }, [messages, nodes, edges, mode]);

  // Create new workflow
  const createWorkflow = async () => {
    try {
      const res = await fetch(`${API}/api/studio/workflows`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name: `Workflow ${workflows.length + 1}`, mode: "vibe" }),
      });
      if (res.ok) {
        const wf = await res.json();
        setWorkflows((prev) => [wf, ...prev]);
        loadWorkflow(wf);
        toast.success("New workflow created.");
      }
    } catch {
      toast.error("Failed to create workflow.");
    }
  };

  // Delete workflow
  const deleteWorkflow = async (wfId) => {
    try {
      await fetch(`${API}/api/studio/workflows/${wfId}`, { method: "DELETE", headers });
      const remaining = workflows.filter((w) => w.id !== wfId);
      setWorkflows(remaining);
      if (wfId === activeWorkflowId) {
        if (remaining.length > 0) loadWorkflow(remaining[0]);
        else { setActiveWorkflowId(null); setMessages([]); setNodes([]); setEdges([]); setCodeJson(""); }
      }
      toast.success("Workflow deleted.");
    } catch {
      toast.error("Failed to delete.");
    }
  };

  // Select workflow
  const selectWorkflow = (wfId) => {
    const wf = workflows.find((w) => w.id === wfId);
    if (wf) loadWorkflow(wf);
  };

  // Chat send handler — simulates AI response and auto-generates nodes
  const handleChatSend = (text) => {
    const newMessages = [...messages, { role: "user", content: text }];
    // Simulate an AI assistant response that builds nodes
    const response = generateAssistantResponse(text, nodes);
    newMessages.push({ role: "assistant", content: response.message });
    setMessages(newMessages);

    if (response.newNodes.length > 0 || response.newEdges.length > 0) {
      const updatedNodes = [...nodes, ...response.newNodes];
      const updatedEdges = [...edges, ...response.newEdges];
      setNodes(updatedNodes);
      setEdges(updatedEdges);
      setCodeJson(generateCodeJson(updatedNodes, updatedEdges));
    }
  };

  // Node operations
  const addNode = (node) => {
    const newNodes = [...nodes, node];
    // Auto-connect to last node
    let newEdges = [...edges];
    if (nodes.length > 0) {
      newEdges.push({ from: nodes[nodes.length - 1].id, to: node.id });
    }
    setNodes(newNodes);
    setEdges(newEdges);
    setCodeJson(generateCodeJson(newNodes, newEdges));
    setActiveNode(node.id);
  };

  const deleteNode = (nodeId) => {
    const newNodes = nodes.filter((n) => n.id !== nodeId);
    const newEdges = edges.filter((e) => (e.from || e.source) !== nodeId && (e.to || e.target) !== nodeId);
    setNodes(newNodes);
    setEdges(newEdges);
    setCodeJson(generateCodeJson(newNodes, newEdges));
    if (activeNode === nodeId) setActiveNode(null);
  };

  // Run Compliance Linter
  const runLinter = async () => {
    try {
      const res = await fetch(`${API}/api/linter/scan`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          workflow_id: activeWorkflowId,
          nodes,
          edges,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setLinterResult(result);
        if (result.status === "certified") {
          toast.success(`Trust Score: ${result.trust_score} — Certified`);
        } else if (result.status === "flagged") {
          toast.warning(`Trust Score: ${result.trust_score} — ${result.flags.length} issue(s) found`);
        } else {
          toast.error(`Trust Score: ${result.trust_score} — Rejected`);
        }
      }
    } catch {
      toast.error("Linter scan failed.");
    }
  };

  // Deploy (save + lint)
  const handleDeploy = async () => {
    await saveWorkflow();
    await runLinter();
    toast.success("Workflow saved and scanned.");
  };

  // Create initial workflow if none exist
  useEffect(() => {
    if (loaded && workflows.length === 0 && token) {
      createWorkflow();
    }
  }, [loaded, token]);

  return (
    <div data-testid="studio-page" className="flex flex-col h-[calc(100vh-60px)] w-full bg-zinc-950 overflow-hidden">
      {/* Toggle Bar */}
      <div data-testid="studio-toggle-bar" className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06] bg-zinc-950/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <Sparkles size={14} className="text-[#8B5CF6]" />
          <span className="text-[13px] font-medium text-white" style={{ fontFamily: "'Outfit', sans-serif" }}>Nova Studio</span>
          <WorkflowSelector
            workflows={workflows}
            activeId={activeWorkflowId}
            onSelect={selectWorkflow}
            onCreate={createWorkflow}
            onDelete={deleteWorkflow}
          />
          {saving && <span className="text-[10px] text-zinc-600 animate-pulse">Saving...</span>}
        </div>
        <ModeToggle mode={mode} setMode={setMode} />
        <div className="hidden lg:flex items-center gap-3">
          <button
            data-testid="save-workflow-btn"
            onClick={() => saveWorkflow()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Save size={12} /> Save
          </button>
          <p className="text-[11px] text-zinc-600 max-w-[220px] text-right leading-relaxed">
            {mode === "vibe"
              ? "Describe what you want. We'll build it."
              : "Wire the logic visually."}
          </p>
        </div>
      </div>

      {/* Main Panes */}
      <div className="flex-1 flex flex-row overflow-hidden">
        <ChatPane
          expanded={mode === "vibe"}
          messages={messages}
          onSend={handleChatSend}
        />
        <CanvasPane
          expanded={mode === "node"}
          nodes={nodes}
          edges={edges}
          activeNode={activeNode}
          setActiveNode={setActiveNode}
          onAddNode={addNode}
          onDeleteNode={deleteNode}
        />
        <CodePane
          codeJson={codeJson}
          onDeploy={handleDeploy}
          linterResult={linterResult}
          onRunLinter={runLinter}
          saving={saving}
        />
      </div>
    </div>
  );
}

/* ─── AI Response Simulator ─── */
function generateAssistantResponse(userText, existingNodes) {
  const text = userText.toLowerCase();
  const newNodes = [];
  const newEdges = [];
  let message = "";

  if (text.includes("refund") || text.includes("customer") || text.includes("support")) {
    if (existingNodes.length === 0) {
      newNodes.push(
        { id: `t_${Date.now()}`, type: "trigger", label: "Trigger", sub: "Email Received", icon: "Mail", x: 60, y: 80, data: { source: "email", filter: "subject:refund" } },
        { id: `l_${Date.now()}`, type: "llm", label: "LLM", sub: "Analyze Sentiment", icon: "Brain", x: 320, y: 50, data: { model: "nova-7b", task: "sentiment_analysis", temperature: 0.2 } },
        { id: `a_${Date.now()}`, type: "action", label: "Action", sub: "Draft Reply", icon: "FileText", x: 580, y: 120, data: { type: "draft_reply", template: "refund_approved", tone: "empathetic" } },
      );
      newEdges.push(
        { from: newNodes[0].id, to: newNodes[1].id },
        { from: newNodes[1].id, to: newNodes[2].id },
      );
      message = "I've created a 3-node workflow: Email Trigger -> Sentiment Analysis (LLM) -> Draft Reply. The agent will automatically handle refund requests with empathy-driven responses.";
    } else {
      message = "Your workflow already has nodes. I can add a condition node to handle escalation. Try asking: 'Add escalation for refunds over $500'.";
    }
  } else if (text.includes("escalat") || text.includes("condition") || text.includes("branch")) {
    const lastNode = existingNodes[existingNodes.length - 1];
    const condNode = { id: `c_${Date.now()}`, type: "condition", label: "Condition", sub: "Amount > $500?", icon: "Zap", x: (lastNode?.x || 300) + 260, y: (lastNode?.y || 80), data: { condition: "amount > 500", true_action: "escalate", false_action: "auto_approve" } };
    newNodes.push(condNode);
    if (lastNode) newEdges.push({ from: lastNode.id, to: condNode.id });
    message = "Added a conditional branch node. Amounts over $500 will escalate to human review. Everything else gets auto-approved.";
  } else if (text.includes("api") || text.includes("http") || text.includes("webhook")) {
    const lastNode = existingNodes[existingNodes.length - 1];
    const apiNode = { id: `h_${Date.now()}`, type: "http_request", label: "HTTP Request", sub: "External API Call", icon: "Zap", x: (lastNode?.x || 300) + 260, y: (lastNode?.y || 80), data: { method: "POST", url: "https://api.example.com/webhook" } };
    newNodes.push(apiNode);
    if (lastNode) newEdges.push({ from: lastNode.id, to: apiNode.id });
    message = "Added an HTTP Request node for external API integration. Configure the endpoint URL and payload in the node settings.";
  } else if (text.includes("sales") || text.includes("lead") || text.includes("outbound")) {
    if (existingNodes.length === 0) {
      newNodes.push(
        { id: `t_${Date.now()}`, type: "trigger", label: "Trigger", sub: "New Lead Received", icon: "Mail", x: 60, y: 80, data: { source: "crm", event: "new_lead" } },
        { id: `l_${Date.now()}`, type: "llm", label: "LLM", sub: "Research & Personalize", icon: "Brain", x: 320, y: 50, data: { model: "nova-7b", task: "lead_research" } },
        { id: `a_${Date.now()}`, type: "action", label: "Action", sub: "Send Outreach Email", icon: "FileText", x: 580, y: 120, data: { type: "send_email", channel: "smtp" } },
      );
      newEdges.push(
        { from: newNodes[0].id, to: newNodes[1].id },
        { from: newNodes[1].id, to: newNodes[2].id },
      );
      message = "Built a sales outbound workflow: CRM Trigger -> Lead Research (LLM) -> Personalized Email. It'll automatically research and reach out to new leads.";
    } else {
      message = "I see you already have a workflow in progress. You can add specific sales nodes manually in Node Mode, or ask me to add a specific step.";
    }
  } else {
    message = `I understand you want to build an agent for "${userText}". Here are some things you can ask me:\n\n- "Build an agent that handles customer refunds"\n- "Add escalation for high-value requests"\n- "Add an API webhook node"\n- "Build a sales outbound workflow"`;
  }

  return { message, newNodes, newEdges };
}

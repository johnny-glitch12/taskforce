import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { useAuth } from "@/App";
import {
  Send, Rocket, Bot, Zap, Mail, Brain, FileText,
  MessageCircle, GitBranch, Sparkles, Plus, Save,
  Trash2, ChevronDown, Shield, AlertTriangle, Check,
  X, Copy, ZoomIn, ZoomOut, Maximize2, Move,
  Database, Globe, Filter, Code, Layers,
} from "lucide-react";

import { useAgentTerminal } from "../hooks/useAgentTerminal";

const API = process.env.REACT_APP_BACKEND_URL;

const NODE_TYPES = [
  { type: "trigger", label: "Trigger", icon: "Mail", color: "#8B5CF6" },
  { type: "llm", label: "LLM", icon: "Brain", color: "#A78BFA" },
  { type: "condition", label: "Condition", icon: "Filter", color: "#6D28D9" },
  { type: "action", label: "Action", icon: "FileText", color: "#7C3AED" },
  { type: "http_request", label: "HTTP Request", icon: "Globe", color: "#5B21B6" },
  { type: "webhook", label: "Webhook", icon: "Zap", color: "#C084FC" },
  { type: "database", label: "Database", icon: "Database", color: "#4C1D95" },
  { type: "transform", label: "Transform", icon: "Code", color: "#9333EA" },
];

const ICON_MAP = { Mail, Brain, Zap, FileText, MessageCircle, GitBranch, Database, Globe, Filter, Code, Layers };
function getIcon(name) { return ICON_MAP[name] || Zap; }

/* ─── Mode Toggle ─── */
function ModeToggle({ mode, setMode, isMobile }) {
  return (
    <div data-testid="mode-toggle" className="flex items-center gap-1 bg-white/[0.03] border border-white/[0.07] rounded-full p-1">
      {["vibe", "node", ...(isMobile ? ["code"] : [])].map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          data-testid={`${m}-mode-btn`}
          className={`flex items-center gap-1.5 px-3 sm:px-5 py-2 text-[12px] sm:text-[13px] rounded-full transition-all duration-300 ${
            mode === m
              ? "bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.25)]"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {m === "vibe" && <MessageCircle size={13} />}
          {m === "node" && <GitBranch size={13} />}
          {m === "code" && <Code size={13} />}
          <span className="hidden sm:inline">{m === "vibe" ? "Vibe" : m === "node" ? "Node" : "Code"}</span>
        </button>
      ))}
    </div>
  );
}

/* ─── Chat Pane (wired to /api/run-agent + live terminal) ─── */
function ChatPane({ messages, onSend, visible, agentStatus, terminalHistory }) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);
  const termRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [terminalHistory]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };

  const isProcessing = agentStatus === "queued" || agentStatus === "processing";

  if (!visible) return null;

  return (
    <div data-testid="studio-chat-pane" className="flex-1 lg:border-r border-white/[0.06] bg-zinc-950 flex flex-col h-full min-w-0">
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
        <Bot size={14} className="text-[#8B5CF6]" />
        <span className="text-[12px] tracking-wide text-zinc-500">Vibe Chat</span>
        {isProcessing && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] text-[#A78BFA] bg-[#8B5CF6]/10 px-2.5 py-0.5 rounded-full border border-[#8B5CF6]/20">
            <span className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6] animate-pulse" />
            Agent Thinking...
          </span>
        )}
        {!isProcessing && (
          <span className="ml-auto text-[11px] text-zinc-600 bg-white/[0.04] px-2.5 py-0.5 rounded-full hidden sm:inline">
            Describe your agent in plain English
          </span>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
            <Bot size={28} className="text-zinc-700 mb-3" />
            <p className="text-[13px] text-zinc-600">Start describing your agent.</p>
            <p className="text-[11px] text-zinc-700 mt-1">e.g. "Build an agent that handles customer refunds"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} data-testid={`chat-message-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-xl whitespace-pre-wrap ${
              msg.role === "user"
                ? "bg-[#8B5CF6]/10 text-zinc-200 border border-[#8B5CF6]/20"
                : "bg-white/[0.03] text-zinc-400 border border-white/[0.06]"
            }`}>{msg.content}</div>
          </div>
        ))}
        {isProcessing && (
          <div className="flex justify-start">
            <div className="max-w-[85%] px-3.5 py-3 text-[13px] rounded-xl bg-white/[0.03] border border-[#8B5CF6]/20">
              <div className="flex items-center gap-2 text-[#A78BFA]">
                <Zap size={12} className="animate-pulse" />
                <span className="text-[12px]">Agent executing...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Terminal History (nidoai useAgentTerminal equivalent) */}
      {terminalHistory.length > 0 && (
        <div
          ref={termRef}
          data-testid="agent-terminal"
          className="h-28 mx-3 mb-2 rounded-lg overflow-y-auto font-mono text-[10px] leading-relaxed border border-white/[0.06]"
          style={{ background: "rgba(0,0,0,0.5)" }}
        >
          <div className="sticky top-0 px-2.5 py-1 bg-black/80 border-b border-white/[0.05] flex items-center gap-1.5 z-10">
            <div className={`w-1.5 h-1.5 rounded-full ${isProcessing ? "bg-emerald-400 animate-pulse" : agentStatus === "success" ? "bg-emerald-400" : agentStatus === "failed" ? "bg-red-400" : "bg-zinc-600"}`} />
            <span className="text-zinc-500 text-[9px] tracking-wider uppercase">Agent Terminal</span>
          </div>
          <div className="p-2.5 space-y-0.5">
            {terminalHistory.map((line, i) => {
              const lower = line.toLowerCase();
              const color = lower.includes("success") || lower.includes("completed")
                ? "#4ade80"
                : lower.includes("failed") || lower.includes("error")
                ? "#f87171"
                : lower.includes("processing") || lower.includes("reasoning")
                ? "#a78bfa"
                : lower.includes("init") || lower.includes("queued")
                ? "#60a5fa"
                : "#71717a";
              return <div key={i} style={{ color }}>{line}</div>;
            })}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} data-testid="chat-input-form" className="px-4 py-3 border-t border-white/[0.06] flex gap-2">
        <input
          type="text" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={isProcessing ? "Waiting for agent..." : "Tell me what your agent should do..."}
          disabled={isProcessing}
          data-testid="chat-input"
          className="flex-1 bg-transparent text-[13px] text-white placeholder:text-zinc-600 focus:outline-none disabled:opacity-40"
        />
        <button
          type="submit"
          disabled={isProcessing}
          data-testid="chat-send-btn"
          className="p-2 text-[#8B5CF6] hover:text-[#A78BFA] transition-colors disabled:opacity-30"
        >
          {isProcessing ? <Rocket size={15} className="animate-pulse" /> : <Send size={15} />}
        </button>
      </form>
    </div>
  );
}

/* ─── Draggable Canvas ─── */
function CanvasPane({ visible, nodes, edges, activeNode, setActiveNode, onMoveNode, onAddNode, onDeleteNode, onAddEdge }) {
  const canvasRef = useRef(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [dragging, setDragging] = useState(null); // { nodeId, startX, startY, nodeStartX, nodeStartY }
  const [panning, setPanning] = useState(null); // { startX, startY, panStartX, panStartY }
  const [showNodeMenu, setShowNodeMenu] = useState(false);
  const [connecting, setConnecting] = useState(null); // { fromId, mouseX, mouseY }

  const NODE_W = 200;
  const NODE_H = 72;
  const HEADER_H = 48;

  function getNodeCenter(node) {
    return { x: node.x + NODE_W / 2, y: node.y + NODE_H / 2 };
  }

  // Mouse/Touch handlers for dragging nodes
  const handleNodePointerDown = (e, nodeId) => {
    e.stopPropagation();
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    setDragging({ nodeId, startX: clientX, startY: clientY, nodeStartX: node.x, nodeStartY: node.y });
    setActiveNode(nodeId);
  };

  const handleCanvasPointerDown = (e) => {
    if (e.target !== canvasRef.current && !e.target.closest("[data-canvas-bg]")) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    setPanning({ startX: clientX, startY: clientY, panStartX: pan.x, panStartY: pan.y });
  };

  const handlePointerMove = useCallback((e) => {
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    if (dragging) {
      const dx = (clientX - dragging.startX) / scale;
      const dy = (clientY - dragging.startY) / scale;
      onMoveNode(dragging.nodeId, dragging.nodeStartX + dx, dragging.nodeStartY + dy);
    } else if (panning) {
      const dx = clientX - panning.startX;
      const dy = clientY - panning.startY;
      setPan({ x: panning.panStartX + dx, y: panning.panStartY + dy });
    }

    if (connecting) {
      setConnecting((prev) => prev ? { ...prev, mouseX: clientX, mouseY: clientY } : null);
    }
  }, [dragging, panning, connecting, scale, onMoveNode]);

  const handlePointerUp = useCallback(() => {
    setDragging(null);
    setPanning(null);
    setConnecting(null);
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    window.addEventListener("touchmove", handlePointerMove, { passive: false });
    window.addEventListener("touchend", handlePointerUp);
    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
      window.removeEventListener("touchmove", handlePointerMove);
      window.removeEventListener("touchend", handlePointerUp);
    };
  }, [handlePointerMove, handlePointerUp]);

  // Wheel zoom
  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.08 : 0.08;
    setScale((s) => Math.max(0.3, Math.min(2.5, s + delta)));
  };

  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  const handleAddNode = (type) => {
    // Place new node in center of visible viewport
    const rect = canvasRef.current?.getBoundingClientRect();
    const cx = rect ? (rect.width / 2 - pan.x) / scale : 300;
    const cy = rect ? (rect.height / 2 - pan.y - HEADER_H) / scale : 200;
    const newNode = {
      id: `node_${Date.now()}`,
      type: type.type,
      label: type.label,
      sub: "Configure me",
      icon: type.icon,
      x: cx - NODE_W / 2,
      y: cy - NODE_H / 2,
      data: {},
    };
    onAddNode(newNode);
    setShowNodeMenu(false);
  };

  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setScale(1);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="studio-canvas-pane"
      ref={canvasRef}
      className="flex-1 bg-zinc-950 relative overflow-hidden touch-none select-none"
      onMouseDown={handleCanvasPointerDown}
      onTouchStart={handleCanvasPointerDown}
      style={{ cursor: panning ? "grabbing" : "grab" }}
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 px-4 py-3 bg-zinc-950/90 backdrop-blur-sm border-b border-white/[0.06] flex items-center gap-2 z-20">
        <Zap size={14} className="text-[#A78BFA]" />
        <span className="text-[12px] tracking-wide text-zinc-500 hidden sm:inline">Node Canvas</span>
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => setScale((s) => Math.min(2.5, s + 0.2))} data-testid="zoom-in-btn" className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors" title="Zoom In"><ZoomIn size={14} /></button>
          <span className="text-[10px] text-zinc-600 w-10 text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale((s) => Math.max(0.3, s - 0.2))} data-testid="zoom-out-btn" className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors" title="Zoom Out"><ZoomOut size={14} /></button>
          <button onClick={resetView} data-testid="reset-view-btn" className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors" title="Reset View"><Maximize2 size={14} /></button>
          <div className="w-px h-4 bg-white/[0.06] mx-1" />
          <div className="relative">
            <button data-testid="add-node-btn" onClick={() => setShowNodeMenu(!showNodeMenu)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-400 text-[11px] rounded-lg hover:border-[#8B5CF6]/30 transition-all">
              <Plus size={12} /> <span className="hidden sm:inline">Add Node</span>
            </button>
            {showNodeMenu && (
              <div data-testid="node-type-menu" className="absolute right-0 top-full mt-1 w-52 bg-zinc-900 border border-white/[0.08] rounded-xl p-1.5 z-50 shadow-xl max-h-[320px] overflow-y-auto">
                {NODE_TYPES.map((nt) => {
                  const Icon = getIcon(nt.icon);
                  return (
                    <button key={nt.type} data-testid={`add-node-${nt.type}`} onClick={() => handleAddNode(nt)} className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-zinc-300 hover:bg-white/[0.06] rounded-lg transition-colors">
                      <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: `${nt.color}15` }}>
                        <Icon size={12} style={{ color: nt.color }} />
                      </div>
                      {nt.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Canvas content with pan+zoom */}
      <div
        data-canvas-bg="true"
        className="absolute inset-0 canvas-grid"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          transformOrigin: "0 0",
          marginTop: HEADER_H,
        }}
      >
        {/* SVG Edges */}
        <svg className="absolute pointer-events-none" style={{ left: 0, top: 0, width: "5000px", height: "5000px", overflow: "visible" }}>
          {edges.map((edge, i) => {
            const fromNode = nodes.find((n) => n.id === (edge.from || edge.source));
            const toNode = nodes.find((n) => n.id === (edge.to || edge.target));
            if (!fromNode || !toNode) return null;
            const from = getNodeCenter(fromNode);
            const to = getNodeCenter(toNode);
            const isActive = (edge.from || edge.source) === activeNode || (edge.to || edge.target) === activeNode;
            const dx = Math.abs(to.x - from.x) * 0.5;
            return (
              <path key={i}
                d={`M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`}
                className={`fill-none ${isActive ? "stroke-[#8B5CF6]" : "stroke-zinc-800"}`}
                strokeWidth={isActive ? 2 : 1.5}
                style={{ filter: isActive ? "drop-shadow(0 0 6px rgba(139,92,246,0.4))" : "none" }}
              />
            );
          })}
        </svg>

        {/* Nodes */}
        {nodes.map((node) => {
          const Icon = getIcon(node.icon);
          const isActive = node.id === activeNode;
          const nodeType = NODE_TYPES.find((nt) => nt.type === node.type);
          const color = nodeType?.color || "#8B5CF6";
          return (
            <div
              key={node.id}
              data-testid={`canvas-node-${node.id}`}
              onMouseDown={(e) => handleNodePointerDown(e, node.id)}
              onTouchStart={(e) => handleNodePointerDown(e, node.id)}
              className={`absolute z-10 p-4 rounded-xl transition-shadow duration-200 group touch-none ${
                dragging?.nodeId === node.id ? "cursor-grabbing" : "cursor-grab"
              } ${isActive
                ? "bg-white/[0.06] border-2 shadow-[0_0_24px_rgba(139,92,246,0.2)]"
                : "bg-white/[0.03] border border-white/[0.07] hover:border-[#8B5CF6]/30"
              }`}
              style={{
                left: node.x,
                top: node.y,
                width: NODE_W,
                borderColor: isActive ? color : undefined,
              }}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 flex items-center justify-center rounded-lg shrink-0" style={{ background: `${color}15` }}>
                  <Icon size={16} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] tracking-widest uppercase" style={{ color }}>{node.label}</p>
                  <p className="text-[13px] text-white font-medium truncate">{node.sub}</p>
                </div>
                <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    data-testid={`delete-node-${node.id}`}
                    onMouseDown={(e) => { e.stopPropagation(); }}
                    onClick={(e) => { e.stopPropagation(); onDeleteNode(node.id); }}
                    className="p-1 text-zinc-600 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
              {/* Connection dot */}
              <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-zinc-700 bg-zinc-900 opacity-0 group-hover:opacity-100 transition-opacity cursor-crosshair"
                onMouseDown={(e) => {
                  e.stopPropagation();
                  const rect = canvasRef.current?.getBoundingClientRect();
                  if (!rect) return;
                  setConnecting({ fromId: node.id, mouseX: e.clientX, mouseY: e.clientY });
                }}
              />
              <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-zinc-700 bg-zinc-900 opacity-0 group-hover:opacity-100 transition-opacity"
                onMouseUp={() => {
                  if (connecting && connecting.fromId !== node.id) {
                    onAddEdge({ from: connecting.fromId, to: node.id });
                    setConnecting(null);
                  }
                }}
              />
            </div>
          );
        })}

        {nodes.length === 0 && (
          <div className="absolute flex items-center justify-center" style={{ left: "40%", top: "35%" }}>
            <div className="text-center opacity-50">
              <GitBranch size={32} className="text-zinc-700 mx-auto mb-3" />
              <p className="text-[13px] text-zinc-600">Click "Add Node" to start building</p>
            </div>
          </div>
        )}
      </div>

      {/* Mini-map info */}
      <div className="absolute bottom-3 left-3 text-[10px] text-zinc-700 z-20 flex items-center gap-2">
        <Move size={10} /> Drag to pan | Scroll to zoom | {nodes.length} node{nodes.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

/* ─── Code Pane ─── */
function CodePane({ visible, codeJson, onDeploy, linterResult, onRunLinter, saving }) {
  const lines = codeJson ? codeJson.split("\n") : ["// No workflow data yet"];

  if (!visible) return null;

  return (
    <div data-testid="studio-code-pane" className="w-full lg:w-[280px] lg:min-w-[280px] border-l border-white/[0.06] bg-zinc-900/50 flex flex-col h-full">
      <div className="px-3 py-3 border-b border-white/[0.06] flex items-center justify-between gap-1 flex-wrap">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-zinc-500" />
          <span className="text-[12px] text-zinc-500">agent.json</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => { navigator.clipboard.writeText(codeJson || ""); toast.success("Copied."); }} data-testid="copy-code-btn" className="p-1.5 text-zinc-500 hover:text-zinc-300" title="Copy"><Copy size={12} /></button>
          <button onClick={onRunLinter} data-testid="run-linter-btn" className="flex items-center gap-1 px-2.5 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-400 text-[11px] rounded-full hover:border-[#8B5CF6]/30 transition-all">
            <Shield size={11} /> Scan
          </button>
          <button onClick={onDeploy} data-testid="deploy-agent-btn" disabled={saving} className="flex items-center gap-1 px-3 py-1.5 bg-[#8B5CF6] text-white text-[11px] font-medium rounded-full hover:bg-[#A78BFA] transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] disabled:opacity-50">
            <Rocket size={11} /> {saving ? "..." : "Deploy"}
          </button>
        </div>
      </div>

      {linterResult && (
        <div data-testid="linter-result" className={`px-3 py-2 border-b flex items-center gap-2 text-[11px] ${
          linterResult.status === "certified" ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
            : linterResult.status === "flagged" ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
            : "bg-red-500/5 border-red-500/20 text-red-400"
        }`}>
          {linterResult.status === "certified" ? <Check size={12} /> : <AlertTriangle size={12} />}
          Score: <strong>{linterResult.trust_score}</strong>
          <span className="capitalize">{linterResult.status}</span>
        </div>
      )}

      {linterResult?.flags?.length > 0 && (
        <div className="px-3 py-2 border-b border-white/[0.04] max-h-[100px] overflow-y-auto">
          {linterResult.flags.map((f, i) => (
            <div key={i} data-testid={`linter-flag-${i}`} className="flex items-start gap-2 py-1 text-[10px]">
              <span className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${f.level === "critical" ? "bg-red-400" : f.level === "warning" ? "bg-amber-400" : "bg-blue-400"}`} />
              <span className="text-zinc-500">{f.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3">
        <pre className="text-[11px] leading-relaxed" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {lines.map((line, i) => (
            <div key={i} className="flex">
              <span className="w-7 text-right pr-3 text-zinc-700 select-none">{i + 1}</span>
              <span>{colorize(line)}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

function colorize(line) {
  const parts = [];
  let key = 0;
  const regex = /"([^"]*)"/g;
  let m, last = 0;
  while ((m = regex.exec(line)) !== null) {
    if (m.index > last) parts.push(<span key={key++} className="text-zinc-400">{line.slice(last, m.index)}</span>);
    const after = line.slice(m.index + m[0].length);
    parts.push(<span key={key++} className={after.trimStart().startsWith(":") ? "text-zinc-300" : "text-[#A78BFA]"}>"{m[1]}"</span>);
    last = m.index + m[0].length;
  }
  if (last < line.length) {
    line.slice(last).split(/([{}[\],:])/).forEach((p) => {
      if (/^[{}[\],:]$/.test(p)) parts.push(<span key={key++} className="text-zinc-600">{p}</span>);
      else if (/^\d+\.?\d*$/.test(p.trim())) parts.push(<span key={key++} className="text-cyan-300">{p}</span>);
      else parts.push(<span key={key++} className="text-zinc-400">{p}</span>);
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
      <button data-testid="workflow-selector-btn" onClick={() => setOpen(!open)} className="flex items-center gap-2 px-2.5 py-1.5 bg-white/[0.04] border border-white/[0.07] text-zinc-300 text-[12px] rounded-lg hover:border-[#8B5CF6]/30 transition-all max-w-[160px] sm:max-w-[200px]">
        <FileText size={12} />
        <span className="truncate">{active?.name || "No workflow"}</span>
        <ChevronDown size={12} className="text-zinc-600 shrink-0" />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-56 bg-zinc-900 border border-white/[0.08] rounded-xl p-1.5 z-50 shadow-xl">
          {workflows.map((wf) => (
            <div key={wf.id} className="flex items-center group">
              <button data-testid={`select-workflow-${wf.id}`} onClick={() => { onSelect(wf.id); setOpen(false); }} className={`flex-1 text-left px-3 py-2 text-[12px] rounded-lg truncate ${wf.id === activeId ? "text-white bg-[#8B5CF6]/10" : "text-zinc-400 hover:bg-white/[0.06]"}`}>{wf.name}</button>
              <button onClick={() => onDelete(wf.id)} className="opacity-0 group-hover:opacity-100 p-1 text-zinc-600 hover:text-red-400 mr-1"><X size={11} /></button>
            </div>
          ))}
          <div className="border-t border-white/[0.06] mt-1 pt-1">
            <button data-testid="create-workflow-btn" onClick={() => { onCreate(); setOpen(false); }} className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-[#A78BFA] hover:bg-white/[0.06] rounded-lg"><Plus size={12} /> New Workflow</button>
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
  const [isMobile, setIsMobile] = useState(false);
  const autoSaveRef = useRef(null);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const generateCodeJson = useCallback((n, e) => {
    if (n.length === 0) return "";
    return JSON.stringify({
      agent: "custom-agent-v1", version: "1.0.0",
      nodes: n.map((nd) => ({ id: nd.id, type: nd.type, config: { label: nd.label, description: nd.sub, ...nd.data } })),
      edges: e.map((ed) => ({ from: ed.from || ed.source, to: ed.to || ed.target })),
    }, null, 2);
  }, []);

  // Load workflows
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

  const saveWorkflow = useCallback(async (overrideData = {}) => {
    if (!activeWorkflowId || !token) return;
    setSaving(true);
    const payload = { mode, vibe_messages: messages, nodes, edges, code_json: codeJson || generateCodeJson(nodes, edges), ...overrideData };
    try {
      const res = await fetch(`${API}/api/studio/workflows/${activeWorkflowId}`, { method: "PUT", headers, body: JSON.stringify(payload) });
      if (res.ok) {
        const updated = await res.json();
        setWorkflows((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
      }
    } catch {}
    setSaving(false);
  }, [activeWorkflowId, token, mode, messages, nodes, edges, codeJson, generateCodeJson]);

  useEffect(() => {
    if (!activeWorkflowId || !loaded) return;
    clearTimeout(autoSaveRef.current);
    autoSaveRef.current = setTimeout(() => saveWorkflow(), 2000);
    return () => clearTimeout(autoSaveRef.current);
  }, [messages, nodes, edges, mode]);

  const createWorkflow = async () => {
    try {
      const res = await fetch(`${API}/api/studio/workflows`, { method: "POST", headers, body: JSON.stringify({ name: `Workflow ${workflows.length + 1}`, mode: "vibe" }) });
      if (res.ok) { const wf = await res.json(); setWorkflows((prev) => [wf, ...prev]); loadWorkflow(wf); toast.success("New workflow created."); }
    } catch { toast.error("Failed to create workflow."); }
  };

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
    } catch { toast.error("Failed to delete."); }
  };

  const selectWorkflow = (wfId) => { const wf = workflows.find((w) => w.id === wfId); if (wf) loadWorkflow(wf); };

  const [activeLogId, setActiveLogId] = useState(null);

  // Supabase Realtime — replaces manual polling (nidoai useAgentTerminal)
  const { history: terminalHistory, status: agentStatus, isLive, outputResult } = useAgentTerminal(activeLogId);

  // When agent finishes, push the result into chat
  const prevStatusRef = useRef(null);
  useEffect(() => {
    if (prevStatusRef.current === agentStatus) return;
    prevStatusRef.current = agentStatus;

    if (agentStatus === "success" && outputResult) {
      setMessages((prev) => [...prev, { role: "assistant", content: outputResult }]);
      // Also apply node suggestions from pattern matcher
      const response = generateAssistantResponse(outputResult, nodes);
      if (response.newNodes.length > 0) {
        const updatedNodes = [...nodes, ...response.newNodes];
        const updatedEdges = [...edges, ...response.newEdges];
        setNodes(updatedNodes);
        setEdges(updatedEdges);
        setCodeJson(generateCodeJson(updatedNodes, updatedEdges));
      }
    } else if (agentStatus === "failed") {
      setMessages((prev) => [...prev, { role: "assistant", content: `Agent error: Check the terminal for details.` }]);
    }
  }, [agentStatus, outputResult]);

  const handleChatSend = async (text) => {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setActiveLogId(null); // Reset to re-trigger hook

    try {
      const res = await fetch(`${API}/api/run-agent`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          user_message: text,
          system_prompt: "You are Nova AI, an expert AI agent architect. Help the user design, build, and configure AI agents. Be concise but thorough. When describing agent configurations, use structured output with clear sections.",
        }),
      });
      const data = await res.json();
      if (data.success && data.logId) {
        setActiveLogId(data.logId);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: `Failed to start agent: ${data.message || "Unknown error"}` }]);
      }
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Network error. Could not reach the agent API." }]);
    }
  };

  const addNode = (node) => {
    const newNodes = [...nodes, node];
    let newEdges = [...edges];
    if (nodes.length > 0) newEdges.push({ from: nodes[nodes.length - 1].id, to: node.id });
    setNodes(newNodes);
    setEdges(newEdges);
    setCodeJson(generateCodeJson(newNodes, newEdges));
    setActiveNode(node.id);
  };

  const moveNode = useCallback((nodeId, x, y) => {
    setNodes((prev) => prev.map((n) => n.id === nodeId ? { ...n, x, y } : n));
  }, []);

  const deleteNode = (nodeId) => {
    const newNodes = nodes.filter((n) => n.id !== nodeId);
    const newEdges = edges.filter((e) => (e.from || e.source) !== nodeId && (e.to || e.target) !== nodeId);
    setNodes(newNodes);
    setEdges(newEdges);
    setCodeJson(generateCodeJson(newNodes, newEdges));
    if (activeNode === nodeId) setActiveNode(null);
  };

  const addEdge = (edge) => {
    const exists = edges.some((e) => (e.from || e.source) === edge.from && (e.to || e.target) === edge.to);
    if (!exists) {
      const newEdges = [...edges, edge];
      setEdges(newEdges);
      setCodeJson(generateCodeJson(nodes, newEdges));
    }
  };

  const runLinter = async () => {
    try {
      const res = await fetch(`${API}/api/linter/scan`, { method: "POST", headers, body: JSON.stringify({ workflow_id: activeWorkflowId, nodes, edges }) });
      if (res.ok) {
        const result = await res.json();
        setLinterResult(result);
        if (result.status === "certified") toast.success(`Trust Score: ${result.trust_score} — Certified`);
        else if (result.status === "flagged") toast.warning(`Trust Score: ${result.trust_score} — ${result.flags.length} issue(s)`);
        else toast.error(`Trust Score: ${result.trust_score} — Rejected`);
      }
    } catch { toast.error("Linter scan failed."); }
  };

  const handleDeploy = async () => { await saveWorkflow(); await runLinter(); toast.success("Workflow saved and scanned."); };

  useEffect(() => {
    if (loaded && workflows.length === 0 && token) createWorkflow();
  }, [loaded, token]);

  // Regenerate code when nodes change (after drag)
  useEffect(() => {
    if (nodes.length > 0) setCodeJson(generateCodeJson(nodes, edges));
  }, [nodes, edges, generateCodeJson]);

  // Determine which panes are visible
  const showChat = isMobile ? mode === "vibe" : true;
  const showCanvas = isMobile ? mode === "node" : mode === "node";
  const showCode = isMobile ? mode === "code" : true;

  return (
    <div data-testid="studio-page" className="flex flex-col h-[calc(100vh-60px)] w-full bg-zinc-950 overflow-hidden">
      {/* Toggle Bar */}
      <div data-testid="studio-toggle-bar" className="flex items-center justify-between px-3 sm:px-5 py-2.5 border-b border-white/[0.06] bg-zinc-950/80 backdrop-blur-sm gap-2">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Sparkles size={14} className="text-[#8B5CF6] shrink-0" />
          <span className="text-[13px] font-medium text-white hidden sm:inline" style={{ fontFamily: "'Outfit', sans-serif" }}>Nova Studio</span>
          <WorkflowSelector workflows={workflows} activeId={activeWorkflowId} onSelect={selectWorkflow} onCreate={createWorkflow} onDelete={deleteWorkflow} />
          {saving && <span className="text-[10px] text-zinc-600 animate-pulse hidden sm:inline">Saving...</span>}
        </div>
        <ModeToggle mode={mode} setMode={setMode} isMobile={isMobile} />
        <div className="hidden lg:flex items-center gap-2">
          <button data-testid="save-workflow-btn" onClick={() => saveWorkflow()} className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-zinc-400 hover:text-zinc-200">
            <Save size={12} /> Save
          </button>
        </div>
      </div>

      {/* Main Panes */}
      <div className="flex-1 flex flex-row overflow-hidden">
        {/* Desktop: Vibe chat is a sidebar when in node mode */}
        {!isMobile && mode === "vibe" && <ChatPane messages={messages} onSend={handleChatSend} visible={true} agentStatus={agentStatus} terminalHistory={terminalHistory} />}
        {!isMobile && mode === "vibe" && <CodePane visible={true} codeJson={codeJson} onDeploy={handleDeploy} linterResult={linterResult} onRunLinter={runLinter} saving={saving} />}

        {!isMobile && mode === "node" && (
          <>
            <CanvasPane visible={true} nodes={nodes} edges={edges} activeNode={activeNode} setActiveNode={setActiveNode} onMoveNode={moveNode} onAddNode={addNode} onDeleteNode={deleteNode} onAddEdge={addEdge} />
            <CodePane visible={true} codeJson={codeJson} onDeploy={handleDeploy} linterResult={linterResult} onRunLinter={runLinter} saving={saving} />
          </>
        )}

        {/* Mobile: Single pane */}
        {isMobile && <ChatPane messages={messages} onSend={handleChatSend} visible={showChat} agentStatus={agentStatus} terminalHistory={terminalHistory} />}
        {isMobile && <CanvasPane visible={showCanvas} nodes={nodes} edges={edges} activeNode={activeNode} setActiveNode={setActiveNode} onMoveNode={moveNode} onAddNode={addNode} onDeleteNode={deleteNode} onAddEdge={addEdge} />}
        {isMobile && <CodePane visible={showCode} codeJson={codeJson} onDeploy={handleDeploy} linterResult={linterResult} onRunLinter={runLinter} saving={saving} />}
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
        { id: `t_${Date.now()}`, type: "trigger", label: "Trigger", sub: "Email Received", icon: "Mail", x: 60, y: 100, data: { source: "email", filter: "subject:refund" } },
        { id: `l_${Date.now()}`, type: "llm", label: "LLM", sub: "Analyze Sentiment", icon: "Brain", x: 340, y: 80, data: { model: "nova-7b", task: "sentiment_analysis", temperature: 0.2 } },
        { id: `a_${Date.now()}`, type: "action", label: "Action", sub: "Draft Reply", icon: "FileText", x: 620, y: 140, data: { type: "draft_reply", template: "refund_approved", tone: "empathetic" } },
      );
      newEdges.push({ from: newNodes[0].id, to: newNodes[1].id }, { from: newNodes[1].id, to: newNodes[2].id });
      message = "I've created a 3-node workflow: Email Trigger -> Sentiment Analysis (LLM) -> Draft Reply. The agent will automatically handle refund requests with empathy-driven responses.";
    } else {
      message = "Your workflow already has nodes. Try: 'Add escalation for refunds over $500'.";
    }
  } else if (text.includes("escalat") || text.includes("condition") || text.includes("branch")) {
    const last = existingNodes[existingNodes.length - 1];
    const node = { id: `c_${Date.now()}`, type: "condition", label: "Condition", sub: "Amount > $500?", icon: "Filter", x: (last?.x || 300) + 280, y: (last?.y || 100), data: { condition: "amount > 500" } };
    newNodes.push(node);
    if (last) newEdges.push({ from: last.id, to: node.id });
    message = "Added a conditional branch. Amounts over $500 escalate to human review.";
  } else if (text.includes("api") || text.includes("http") || text.includes("webhook")) {
    const last = existingNodes[existingNodes.length - 1];
    const node = { id: `h_${Date.now()}`, type: "http_request", label: "HTTP Request", sub: "External API Call", icon: "Globe", x: (last?.x || 300) + 280, y: (last?.y || 100), data: { method: "POST", url: "https://api.example.com/webhook" } };
    newNodes.push(node);
    if (last) newEdges.push({ from: last.id, to: node.id });
    message = "Added an HTTP Request node. Configure the endpoint in node settings.";
  } else if (text.includes("sales") || text.includes("lead") || text.includes("outbound")) {
    if (existingNodes.length === 0) {
      newNodes.push(
        { id: `t_${Date.now()}`, type: "trigger", label: "Trigger", sub: "New Lead Received", icon: "Mail", x: 60, y: 100, data: { source: "crm", event: "new_lead" } },
        { id: `l_${Date.now()}`, type: "llm", label: "LLM", sub: "Research & Personalize", icon: "Brain", x: 340, y: 80, data: { model: "nova-7b", task: "lead_research" } },
        { id: `a_${Date.now()}`, type: "action", label: "Action", sub: "Send Outreach Email", icon: "FileText", x: 620, y: 140, data: { type: "send_email" } },
      );
      newEdges.push({ from: newNodes[0].id, to: newNodes[1].id }, { from: newNodes[1].id, to: newNodes[2].id });
      message = "Built a sales workflow: CRM Trigger -> Lead Research (LLM) -> Personalized Email.";
    } else {
      message = "You already have a workflow. Ask me to add specific steps.";
    }
  } else {
    message = `I can help build "${userText}". Try:\n- "Build a customer refund agent"\n- "Add escalation for high-value requests"\n- "Add an API webhook node"\n- "Build a sales outbound workflow"`;
  }
  return { message, newNodes, newEdges };
}

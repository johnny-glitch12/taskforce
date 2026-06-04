import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { useAuth } from "@/App";
import { parseComputeLimit, ComputeLimitModal } from "../components/ComputeLimitModal";
import WorkflowTemplatesGrid from "../components/WorkflowTemplatesGrid";
import MyWorkflowsGrid from "../components/MyWorkflowsGrid";
import PublishToExchangeModal from "../components/PublishToExchangeModal";
import NodeConfigPanel from "../components/NodeConfigPanel";
import TraceViewer from "../components/TraceViewer";
import BotProjectPanel from "../components/BotProjectPanel";
import { NODE_CATALOG, CATEGORIES, findCatalogEntry } from "../data/nodeCatalog";
import {
  Send, Rocket, Bot, Zap, Mail, Brain, FileText,
  MessageCircle, GitBranch, Sparkles, Plus, Save,
  Trash2, ChevronDown, Shield, AlertTriangle, Check,
  X, Copy, ZoomIn, ZoomOut, Maximize2, Move,
  Database, Globe, Filter, Code, Layers, Play,
  Calendar, FileInput, Rss, FolderOpen, CreditCard, FunctionSquare,
  PencilLine, Split, Combine, Repeat, Timer, Circle, Server, Atom,
  BookOpen, Mic, Volume2, Image, Film, Hash, Users, Phone, Trello,
  CheckSquare, Bug, Building2, Cloud, Headphones, Twitter, Linkedin,
  Facebook, Instagram, Youtube, Video, AtSign, ShoppingBag, Flame,
  Snowflake, Cog, Container, Activity, Bitcoin, FileDown, FileUp,
  Archive, Table, ScanText, Languages, Smile, AlignLeft, Tags,
  Braces, Lock, Binary, Clock, Calculator, Fingerprint, QrCode,
  Github, Gitlab, MessageSquare, Search, ChevronRight,
} from "lucide-react";

import { useAgentTerminal } from "../hooks/useAgentTerminal";

const API = process.env.REACT_APP_BACKEND_URL || "";

// Bridge from catalog `icon` string → real lucide component
const ICON_MAP = {
  Mail, Brain, Zap, FileText, MessageCircle, GitBranch, Database, Globe,
  Filter, Code, Layers, Play, Calendar, FileInput, Rss, FolderOpen,
  CreditCard, FunctionSquare, PencilLine, Split, Combine, Repeat, Timer,
  Circle, Sparkles, Server, Bot, Atom, BookOpen, Mic, Volume2, Image, Film,
  Send, Hash, Users, Phone, MessageSquare, Table, FileDown, FileUp, Trello,
  CheckSquare, Bug, Building2, Cloud, Headphones, Twitter, Linkedin,
  Facebook, Instagram, Youtube, Video, AtSign, ShoppingBag, Flame,
  Snowflake, Cog, Container, Activity, AlertTriangle, Bitcoin, Archive,
  ScanText, Languages, Smile, AlignLeft, Tags, Braces, Lock, Binary, Clock,
  Calculator, Fingerprint, QrCode, Github, Gitlab,
  // Aliases the catalog might reference that map to something we already have:
  Lemon: ShoppingBag, HardDrive: Server,
};
function getIcon(name) { return ICON_MAP[name] || Zap; }

/* ─── Mode Toggle ─── */
function ModeToggle({ mode, setMode, isMobile }) {
  return (
    <div data-testid="mode-toggle" className="flex items-center gap-1 rounded-sm p-1" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      {["vibe", "node", ...(isMobile ? ["code"] : [])].map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          data-testid={`${m}-mode-btn`}
          className={`flex items-center gap-1.5 px-3 sm:px-5 py-2 text-[12px] sm:text-[13px] rounded-sm transition-all duration-300 ${
            mode === m
              ? "bg-cyan-400 text-black font-bold shadow-[0_0_15px_rgba(139,92,246,0.25)]"
              : "t-text-sub hover:t-text"
          }`}
        >
          {m === "vibe" && <MessageCircle size={13} />}
          {m === "node" && <GitBranch size={13} />}
          {m === "code" && <Code size={13} />}
          <span className="hidden sm:inline">{m === "vibe" ? "Command" : m === "node" ? "Workflows" : "Code"}</span>
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

  // Strip markdown noise (**, __, leading #/-) from assistant output so titles stay clean.
  const sanitize = (s) => String(s || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^[\s-]*#{1,6}\s*/gm, "")
    .trim();

  const isProcessing = agentStatus === "queued" || agentStatus === "processing";

  if (!visible) return null;

  return (
    <div data-testid="studio-chat-pane" className="flex-1 t-bg flex flex-col h-full min-w-0" style={{ borderRight: '1px solid var(--border)' }}>
      <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <Bot size={14} className="text-cyan-400" />
        <span className="text-[12px] tracking-wide t-text-sub">Command Prompt</span>
        {isProcessing && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] text-cyan-300 bg-cyan-400/10 px-2.5 py-0.5 rounded-sm border border-cyan-400/20">
            <span className="w-1.5 h-1.5 rounded-sm bg-cyan-400 animate-pulse" />
            Agent Thinking...
          </span>
        )}
        {!isProcessing && (
          <span className="ml-auto text-[11px] t-text-dim px-2.5 py-0.5 rounded-sm hidden sm:inline" style={{ background: 'var(--bg-card)' }}>
            Describe your agent in plain English
          </span>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
            <Bot size={28} className="t-text-dim mb-3" />
            <p className="text-[13px] t-text-mute">Start describing your agent.</p>
            <p className="text-[11px] t-text-dim mt-1">e.g. "Build an agent that handles customer refunds"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} data-testid={`chat-message-${i}`} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-xl whitespace-pre-wrap ${
              msg.role === "user"
                ? "bg-cyan-400/10 text-[var(--text-primary)] border border-cyan-400/20"
                : "t-text-sub border"
            }`} style={msg.role !== "user" ? { background: 'var(--bg-card)', borderColor: 'var(--border)' } : {}}>{msg.role === "user" ? msg.content : sanitize(msg.content)}</div>
          </div>
        ))}
        {isProcessing && (
          <div className="flex justify-start">
            <div className="max-w-[85%] px-3.5 py-3 text-[13px] rounded-xl border border-cyan-400/20" style={{ background: 'var(--bg-card)' }}>
              <div className="flex items-center gap-2 text-cyan-300">
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
          className="h-28 mx-3 mb-2 rounded-lg overflow-y-auto font-mono text-[10px] leading-relaxed"
          style={{ background: "#0d0d0f", border: "1px solid var(--border)" }}
        >
          <div className="sticky top-0 px-2.5 py-1 bg-black/80 flex items-center gap-1.5 z-10" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <div className={`w-1.5 h-1.5 rounded-sm ${isProcessing ? "bg-emerald-400 animate-pulse" : agentStatus === "success" ? "bg-emerald-400" : agentStatus === "failed" ? "bg-red-400" : "bg-zinc-600"}`} />
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
                : lower.includes("firewall")
                ? "#22d3ee"
                : lower.includes("init") || lower.includes("queued")
                ? "#60a5fa"
                : "#71717a";
              return <div key={i} style={{ color }}>{line}</div>;
            })}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} data-testid="chat-input-form" className="px-4 py-3 flex gap-2" style={{ borderTop: '1px solid var(--border)' }}>
        <input
          type="text" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={isProcessing ? "Waiting for agent..." : "Tell me what your agent should do..."}
          disabled={isProcessing}
          data-testid="chat-input"
          className="flex-1 bg-transparent text-[13px] t-text placeholder:text-[var(--text-dim)] focus:outline-none disabled:opacity-40"
        />
        <button
          type="submit"
          disabled={isProcessing}
          data-testid="chat-send-btn"
          className="p-2 text-cyan-400 hover:text-cyan-300 transition-colors disabled:opacity-30"
        >
          {isProcessing ? <Rocket size={15} className="animate-pulse" /> : <Send size={15} />}
        </button>
      </form>
    </div>
  );
}

/* ─── Draggable Canvas ─── */
function CanvasPane({ visible, nodes, edges, activeNode, setActiveNode, onMoveNode, onAddNode, onDeleteNode, onAddEdge, onExecute, executing, onPublish, canPublish }) {
  const canvasRef = useRef(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [dragging, setDragging] = useState(null); // { nodeId, startX, startY, nodeStartX, nodeStartY }
  const [panning, setPanning] = useState(null); // { startX, startY, panStartX, panStartY }
  const [showNodeMenu, setShowNodeMenu] = useState(false);
  const [nodeMenuSearch, setNodeMenuSearch] = useState("");
  const [nodeMenuCategory, setNodeMenuCategory] = useState("ALL");
  const [connecting, setConnecting] = useState(null); // { fromId, mouseX, mouseY }

  const NODE_W = 200;
  const NODE_H = 72;
  const HEADER_H = 48;

  // Strip markdown noise (** __ `) from node titles/subtitles before rendering.
  const cleanLabel = (s) => String(s || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();

  function getNodeCenter(node) {
    return { x: node.x + NODE_W / 2, y: node.y + NODE_H / 2 };
  }
  // Connection ports: right edge (source) and left edge (target) — keeps edges
  // off node bodies so the line never appears to pierce a block.
  function getNodeRightPort(node) {
    return { x: node.x + NODE_W, y: node.y + NODE_H / 2 };
  }
  function getNodeLeftPort(node) {
    return { x: node.x, y: node.y + NODE_H / 2 };
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

  const handleAddNode = (entry) => {
    // Place new node in center of visible viewport
    const rect = canvasRef.current?.getBoundingClientRect();
    const cx = rect ? (rect.width / 2 - pan.x) / scale : 300;
    const cy = rect ? (rect.height / 2 - pan.y - HEADER_H) / scale : 200;
    const newNode = {
      id: `node_${Date.now()}`,
      type: entry.type,                      // canonical executor type
      service: entry.service,                // n8n-style integration slug
      label: entry.label,
      sub: entry.desc || "Configure me",
      icon: entry.icon,
      x: cx - NODE_W / 2,
      y: cy - NODE_H / 2,
      data: { ...(entry.data || {}) },
    };
    onAddNode(newNode);
    setShowNodeMenu(false);
    setNodeMenuSearch("");
  };

  // Filtered + grouped catalog for the searchable add-node menu
  const filteredCatalog = useMemo(() => {
    const q = nodeMenuSearch.trim().toLowerCase();
    return NODE_CATALOG.filter((n) => {
      if (nodeMenuCategory !== "ALL" && n.category !== nodeMenuCategory) return false;
      if (!q) return true;
      return (
        n.label.toLowerCase().includes(q) ||
        n.service.toLowerCase().includes(q) ||
        (n.desc || "").toLowerCase().includes(q) ||
        n.category.toLowerCase().includes(q)
      );
    });
  }, [nodeMenuSearch, nodeMenuCategory]);

  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setScale(1);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="studio-canvas-pane"
      ref={canvasRef}
      className="flex-1 t-bg relative overflow-hidden touch-none select-none"
      onMouseDown={handleCanvasPointerDown}
      onTouchStart={handleCanvasPointerDown}
      style={{ cursor: panning ? "grabbing" : "grab" }}
    >
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 px-4 py-3 backdrop-blur-sm flex items-center gap-2 z-20" style={{ backgroundColor: 'var(--bg-nav)', borderBottom: '1px solid var(--border)' }}>
        <Zap size={14} className="text-cyan-300" />
        <span className="text-[12px] tracking-wide t-text-sub hidden sm:inline">Node Canvas</span>
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={() => setScale((s) => Math.min(2.5, s + 0.2))} data-testid="zoom-in-btn" className="p-1.5 t-text-sub hover:t-text transition-colors" title="Zoom In"><ZoomIn size={14} /></button>
          <span className="text-[10px] t-text-dim w-10 text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale((s) => Math.max(0.3, s - 0.2))} data-testid="zoom-out-btn" className="p-1.5 t-text-sub hover:t-text transition-colors" title="Zoom Out"><ZoomOut size={14} /></button>
          <button onClick={resetView} data-testid="reset-view-btn" className="p-1.5 t-text-sub hover:t-text transition-colors" title="Reset View"><Maximize2 size={14} /></button>
          <div className="w-px h-4 mx-1" style={{ background: 'var(--border)' }} />
          <button
            data-testid="execute-workflow-btn"
            onClick={() => onExecute?.()}
            disabled={executing || nodes.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: executing ? 'rgba(34,211,238,0.1)' : '#22d3ee',
              color: executing ? '#22d3ee' : '#000',
              border: '1px solid #22d3ee',
            }}
            title="Execute workflow"
          >
            <Play size={11} fill={executing ? "none" : "currentColor"} />
            <span className="hidden sm:inline">{executing ? "RUNNING..." : "EXECUTE"}</span>
          </button>
          <button
            data-testid="publish-to-exchange-btn"
            onClick={() => onPublish?.()}
            disabled={!canPublish}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: 'transparent',
              color: '#10b981',
              border: '1px solid #10b981',
            }}
            title={canPublish ? "Publish this workflow to The Exchange" : "Save the workflow first"}
          >
            <Rocket size={11} />
            <span className="hidden sm:inline">PUBLISH</span>
          </button>
          <div className="w-px h-4 mx-1" style={{ background: 'var(--border)' }} />
          <div className="relative">
            <button data-testid="add-node-btn" onClick={() => setShowNodeMenu(!showNodeMenu)} className="flex items-center gap-1.5 px-3 py-1.5 t-text-mute text-[11px] rounded-lg hover:border-cyan-400/30 transition-all" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <Plus size={12} /> <span className="hidden sm:inline">Add Node</span>
            </button>
            {showNodeMenu && (
              <div data-testid="node-type-menu" className="absolute right-0 top-full mt-1 w-[420px] rounded-xl z-50 shadow-2xl flex" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', height: 460 }}>
                {/* Category sidebar */}
                <div className="w-[130px] shrink-0 overflow-y-auto py-1.5" style={{ borderRight: '1px solid var(--border)' }}>
                  {["ALL", ...CATEGORIES].map((cat) => (
                    <button
                      key={cat}
                      data-testid={`node-cat-${cat.replace(/[^a-z]/gi,'')}`}
                      onClick={() => setNodeMenuCategory(cat)}
                      className={`w-full text-left px-3 py-1.5 text-[11px] transition-colors ${
                        nodeMenuCategory === cat ? "bg-cyan-400/10 text-cyan-300" : "t-text-mute hover:t-text"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
                {/* Search + list */}
                <div className="flex-1 flex flex-col min-w-0">
                  <div className="px-2.5 py-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="relative">
                      <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 t-text-dim" />
                      <input
                        data-testid="node-search-input"
                        value={nodeMenuSearch}
                        onChange={(e) => setNodeMenuSearch(e.target.value)}
                        placeholder={`Search ${NODE_CATALOG.length} nodes...`}
                        autoFocus
                        className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-sm focus:outline-none"
                        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                      />
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto p-1">
                    {filteredCatalog.length === 0 && (
                      <div className="text-center py-8 t-text-dim text-[11px]">No nodes match.</div>
                    )}
                    {filteredCatalog.map((nt) => {
                      const Icon = getIcon(nt.icon);
                      return (
                        <button
                          key={nt.service}
                          data-testid={`add-node-${nt.service}`}
                          onClick={() => handleAddNode(nt)}
                          className="w-full flex items-start gap-2.5 px-2.5 py-2 text-left rounded-sm hover:bg-[var(--bg-card-hover)] transition-colors"
                        >
                          <div className="w-6 h-6 rounded-sm flex items-center justify-center shrink-0 mt-0.5" style={{ background: `${nt.color}15` }}>
                            <Icon size={12} style={{ color: nt.color }} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-[12px] t-text truncate">{nt.label}</div>
                            <div className="text-[9px] t-text-dim truncate">{nt.desc}</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
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
        {/* SVG Edges — Lego-style orthogonal routing: right-port → out-stub → vertical → in-stub → left-port */}
        <svg className="absolute pointer-events-none" style={{ left: 0, top: 0, width: "5000px", height: "5000px", overflow: "visible" }}>
          {edges.map((edge, i) => {
            const fromNode = nodes.find((n) => n.id === (edge.from || edge.source));
            const toNode = nodes.find((n) => n.id === (edge.to || edge.target));
            if (!fromNode || !toNode) return null;
            const from = getNodeRightPort(fromNode);
            const to = getNodeLeftPort(toNode);
            const isActive = (edge.from || edge.source) === activeNode || (edge.to || edge.target) === activeNode;
            const STUB = 24;
            // If target is to the right of source → standard right-down-left elbow.
            // If target is to the left of (or overlapping) source → route OUT past the source, around, and IN to target.
            let d;
            if (to.x - from.x > STUB * 2) {
              const midX = (from.x + to.x) / 2;
              d = `M ${from.x} ${from.y} L ${midX} ${from.y} L ${midX} ${to.y} L ${to.x} ${to.y}`;
            } else {
              const outX = from.x + STUB;
              const inX = to.x - STUB;
              const aboveY = Math.min(from.y, to.y) - (NODE_H / 2 + STUB);
              d = `M ${from.x} ${from.y} L ${outX} ${from.y} L ${outX} ${aboveY} L ${inX} ${aboveY} L ${inX} ${to.y} L ${to.x} ${to.y}`;
            }
            return (
              <g key={i}>
                <path d={d}
                  className="fill-none"
                  stroke={isActive ? "#22d3ee" : "#3f3f46"}
                  strokeWidth={isActive ? 2 : 1.5}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{ filter: isActive ? "drop-shadow(0 0 6px rgba(34,211,238,0.45))" : "none" }}
                />
                {/* arrowhead */}
                <circle cx={to.x} cy={to.y} r={3} fill={isActive ? "#22d3ee" : "#52525b"} />
              </g>
            );
          })}
        </svg>

        {/* Nodes */}
        {nodes.map((node) => {
          const Icon = getIcon(node.icon);
          const isActive = node.id === activeNode;
          const nodeMeta = findCatalogEntry(node.service) || NODE_CATALOG.find((c) => c.type === node.type);
          const color = nodeMeta?.color || node.color || "#22d3ee";
          return (
            <div
              key={node.id}
              data-testid={`canvas-node-${node.id}`}
              onMouseDown={(e) => handleNodePointerDown(e, node.id)}
              onTouchStart={(e) => handleNodePointerDown(e, node.id)}
              className={`absolute z-10 p-4 rounded-xl transition-shadow duration-200 group touch-none ${
                dragging?.nodeId === node.id ? "cursor-grabbing" : "cursor-grab"
              }`}
              style={{
                left: node.x,
                top: node.y,
                width: NODE_W,
                background: isActive ? 'var(--bg-card-hover)' : 'var(--bg-card)',
                border: isActive ? `2px solid ${color}` : '1px solid var(--border)',
                boxShadow: isActive ? '0 0 24px rgba(139,92,246,0.2)' : 'none',
              }}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 flex items-center justify-center rounded-lg shrink-0" style={{ background: `${color}15` }}>
                  <Icon size={16} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] tracking-widest uppercase" style={{ color }}>{cleanLabel(node.label)}</p>
                  <p className="text-[13px] t-text font-medium truncate">{cleanLabel(node.sub)}</p>
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
              <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity cursor-crosshair"
                style={{ border: '2px solid var(--border-hover)', background: 'var(--bg-elevated)' }}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  const rect = canvasRef.current?.getBoundingClientRect();
                  if (!rect) return;
                  setConnecting({ fromId: node.id, mouseX: e.clientX, mouseY: e.clientY });
                }}
              />
              <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ border: '2px solid var(--border-hover)', background: 'var(--bg-elevated)' }}
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
              <GitBranch size={32} className="t-text-dim mx-auto mb-3" />
              <p className="text-[13px] t-text-mute">Click "Add Node" to start building</p>
            </div>
          </div>
        )}
      </div>

      {/* Mini-map info */}
      <div className="absolute bottom-3 left-3 text-[10px] t-text-dim z-20 flex items-center gap-2">
        <Move size={10} /> Drag to pan | Scroll to zoom | {nodes.length} node{nodes.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

/* ─── Code Pane ─── */
function CodePane({ visible, codeJson, onDeploy, onPublish, linterResult, onRunLinter, saving, publishing }) {
  const lines = codeJson ? codeJson.split("\n") : ["// No workflow data yet"];

  if (!visible) return null;

  return (
    <div data-testid="studio-code-pane" className="w-full lg:w-[280px] lg:min-w-[280px] flex flex-col h-full" style={{ borderLeft: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
      <div className="px-3 py-3 flex items-center justify-between gap-1 flex-wrap" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <FileText size={13} className="t-text-sub" />
          <span className="text-[12px] t-text-sub">agent.json</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => { navigator.clipboard.writeText(codeJson || ""); toast.success("Copied."); }} data-testid="copy-code-btn" className="p-1.5 t-text-sub hover:t-text" title="Copy"><Copy size={12} /></button>
          <button onClick={onRunLinter} data-testid="run-linter-btn" className="flex items-center gap-1 px-2.5 py-1.5 t-text-mute text-[11px] rounded-sm hover:border-cyan-400/30 transition-all" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <Shield size={11} /> Scan
          </button>
          <button onClick={onDeploy} data-testid="deploy-agent-btn" disabled={saving} className="flex items-center gap-1 px-3 py-1.5 bg-cyan-400 text-black font-bold text-[11px] font-medium rounded-sm hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(139,92,246,0.2)] disabled:opacity-50">
            <Rocket size={11} /> {saving ? "..." : "Deploy"}
          </button>
        </div>
      </div>

      {/* Publish to Marketplace button */}
      {codeJson && (
        <div className="px-3 py-2 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
          <button
            onClick={onPublish}
            data-testid="publish-agent-btn"
            disabled={publishing}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium rounded-lg transition-all text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50"
            style={{ border: '1px solid rgba(52,211,153,0.25)' }}
          >
            <Globe size={11} /> {publishing ? "Publishing..." : "Publish to Marketplace"}
          </button>
        </div>
      )}

      {linterResult && (
        <div data-testid="linter-result" className={`px-3 py-2 flex items-center gap-2 text-[11px] ${
          linterResult.status === "certified" ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
            : linterResult.status === "flagged" ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
            : "bg-red-500/5 border-red-500/20 text-red-400"
        }`} style={{ borderBottom: '1px solid var(--border)' }}>
          {linterResult.status === "certified" ? <Check size={12} /> : <AlertTriangle size={12} />}
          Score: <strong>{linterResult.trust_score}</strong>
          <span className="capitalize">{linterResult.status}</span>
        </div>
      )}

      {linterResult?.flags?.length > 0 && (
        <div className="px-3 py-2 max-h-[100px] overflow-y-auto" style={{ borderBottom: '1px solid var(--border)' }}>
          {linterResult.flags.map((f, i) => (
            <div key={i} data-testid={`linter-flag-${i}`} className="flex items-start gap-2 py-1 text-[10px]">
              <span className={`mt-0.5 w-1.5 h-1.5 rounded-sm shrink-0 ${f.level === "critical" ? "bg-red-400" : f.level === "warning" ? "bg-amber-400" : "bg-blue-400"}`} />
              <span className="t-text-sub">{f.message}</span>
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
    parts.push(<span key={key++} className={after.trimStart().startsWith(":") ? "text-zinc-300" : "text-cyan-300"}>"{m[1]}"</span>);
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
      <button data-testid="workflow-selector-btn" onClick={() => setOpen(!open)} className="flex items-center gap-2 px-2.5 py-1.5 t-text text-[12px] rounded-lg hover:border-cyan-400/30 transition-all max-w-[160px] sm:max-w-[200px]" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <FileText size={12} />
        <span className="truncate">{active?.name || "No workflow"}</span>
        <ChevronDown size={12} className="t-text-dim shrink-0" />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-56 rounded-xl p-1.5 z-50 shadow-xl" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
          {workflows.map((wf) => (
            <div key={wf.id} className="flex items-center group">
              <button data-testid={`select-workflow-${wf.id}`} onClick={() => { onSelect(wf.id); setOpen(false); }} className={`flex-1 text-left px-3 py-2 text-[12px] rounded-lg truncate ${wf.id === activeId ? "t-text bg-cyan-400/10" : "t-text-mute hover:bg-[var(--bg-card-hover)]"}`}>{wf.name}</button>
              <button onClick={() => onDelete(wf.id)} className="opacity-0 group-hover:opacity-100 p-1 t-text-dim hover:text-red-400 mr-1"><X size={11} /></button>
            </div>
          ))}
          <div className="mt-1 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
            <button data-testid="create-workflow-btn" onClick={() => { onCreate(); setOpen(false); }} className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-cyan-300 hover:bg-[var(--bg-card-hover)] rounded-lg"><Plus size={12} /> New Workflow</button>
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
  const [runtimeWorkflowId, setRuntimeWorkflowId] = useState(null);
  const [sourceTemplate, setSourceTemplate] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [trace, setTrace] = useState(null);
  const [showTrace, setShowTrace] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
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
      // Also sync to runtime user_workflows if we have canvas nodes (enables Execute)
      if (mode === "node" && nodes.length > 0) {
        const activeWf = workflows.find((w) => w.id === activeWorkflowId);
        try {
          const r = await fetch(`${API}/api/workflows/save`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              studio_workflow_id: activeWorkflowId,
              name: activeWf?.name || "Untitled Workflow",
              nodes,
              edges,
              source_template: sourceTemplate,
            }),
          });
          if (r.ok) {
            const data = await r.json();
            setRuntimeWorkflowId(data.workflow_id);
          }
        } catch {}
      }
    } catch {}
    setSaving(false);
  }, [activeWorkflowId, token, mode, messages, nodes, edges, codeJson, generateCodeJson, sourceTemplate, workflows]);

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

  const [computeLimit, setComputeLimit] = useState(null);
  const [activeBotProject, setActiveBotProject] = useState(null);
  const [buildingBot, setBuildingBot] = useState(false);

  // Detect "build me a ..." style prompts → trigger native AI bot builder
  // instead of the chat-only agent. This is the "stop chatting, just build it"
  // pipeline (Gemini 2.5 Pro → React Flow + Python files).
  const BUILD_TRIGGER_RX = /^\s*(build|create|make|generate|design)\s+(me\s+)?(a|an|the)?\s*/i;
  const looksLikeBuildIntent = (text) => BUILD_TRIGGER_RX.test(text) && text.length > 12;

  const buildBotFromPrompt = async (text) => {
    setBuildingBot(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "Compiling your bot with Gemini 2.5 Pro... generating files and visual nodes." }]);
    try {
      const res = await fetch(`${API}/api/armory/build-bot`, {
        method: "POST",
        headers,
        body: JSON.stringify({ prompt: text }),
      });
      const data = await res.json().catch(() => ({}));

      const limitData = parseComputeLimit(res.status, data);
      if (limitData) { setComputeLimit(limitData); setBuildingBot(false); return; }

      if (!res.ok || !data.success) {
        setMessages((prev) => [...prev, { role: "assistant", content: `Build failed: ${data.detail || "unknown error"}` }]);
        setBuildingBot(false);
        return;
      }

      const p = data.project;
      // Drop the generated nodes/edges onto the canvas + flip into node mode.
      setNodes(p.nodes || []);
      setEdges(p.edges || []);
      setCodeJson(generateCodeJson(p.nodes || [], p.edges || []));
      setActiveBotProject(p);
      setMode("node");
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Built ${p.name} — ${p.files.length} files, ${p.nodes.length} nodes. Click any block or open the Files panel on the right to edit the source.`,
      }]);
      toast.success(`Bot compiled: ${p.name}`);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Network error: ${e.message}` }]);
    }
    setBuildingBot(false);
  };

  const handleChatSend = async (text) => {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setActiveLogId(null);

    // Route "build me X" prompts straight to the AI bot compiler.
    if (looksLikeBuildIntent(text)) {
      await buildBotFromPrompt(text);
      return;
    }

    try {
      const res = await fetch(`${API}/api/run-agent`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          user_message: text,
          system_prompt: "You are Task Force AI, an expert AI agent architect. Help the user design, build, and configure AI agents. Be concise but thorough. When describing agent configurations, use structured output with clear sections.",
        }),
      });

      let data;
      try {
        const buf = await res.arrayBuffer();
        data = JSON.parse(new TextDecoder().decode(buf));
      } catch { data = {}; }

      // Check for compute limit kill switch (200 with error flag)
      const limitData = parseComputeLimit(res.status, data);
      if (limitData) {
        setComputeLimit(limitData);
        setMessages((prev) => [...prev, { role: "assistant", content: `Execution blocked — you've used all ${limitData.limit} compute credits this month. Upgrade your plan to continue.` }]);
        return;
      }

      if (res.ok && data.success && data.logId) {
        setActiveLogId(data.logId);
      } else if (res.status === 403) {
        setMessages((prev) => [...prev, { role: "assistant", content: `Blocked by security firewall. Your prompt was flagged as potentially unsafe. Try rephrasing.` }]);
      } else if (res.status === 429) {
        setMessages((prev) => [...prev, { role: "assistant", content: `Rate limit hit. ${typeof data.detail === 'string' ? data.detail : "Slow down and try again in a minute."}` }]);
      } else if (res.status === 409) {
        setMessages((prev) => [...prev, { role: "assistant", content: `An agent is already running. Wait for it to finish before sending another request.` }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: `Failed to start agent: ${data.detail || data.message || "Unknown error"}` }]);
      }
    } catch (err) {
      console.error("[CHAT SEND ERROR]", err);
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

  // Load a translated n8n template into the active canvas (replaces current nodes/edges)
  const loadTemplateIntoCanvas = (template) => {
    if (!template || !template.nodes) return;
    // Ensure each node has icon/label our canvas expects
    const tNodes = template.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      label: n.label || n.type,
      sub: n.sub || "Imported",
      icon: n.icon || "Zap",
      x: n.x ?? 60,
      y: n.y ?? 100,
      data: n.data || {},
    }));
    const tEdges = (template.edges || []).map((e) => ({
      from: e.from || e.source,
      to: e.to || e.target,
    }));
    setNodes(tNodes);
    setEdges(tEdges);
    setCodeJson(generateCodeJson(tNodes, tEdges));
    setActiveNode(null);
    setSourceTemplate(template.source_hash);
    setRuntimeWorkflowId(null);
    setTrace(null);
    toast.success(`Loaded "${template.name}" — ${tNodes.length} nodes`);
  };

  // Load one of the user's OWN runtime workflows back into the canvas
  const loadRuntimeWorkflowIntoCanvas = (wf) => {
    if (!wf) return;
    const tNodes = (wf.nodes || []).map((n) => ({
      id: n.id, type: n.type,
      label: n.label || n.type, sub: n.sub || "Node",
      icon: n.icon || "Zap",
      x: n.x ?? 60, y: n.y ?? 100, data: n.data || {},
    }));
    const tEdges = (wf.edges || []).map((e) => ({ from: e.from || e.source, to: e.to || e.target }));
    setNodes(tNodes);
    setEdges(tEdges);
    setCodeJson(generateCodeJson(tNodes, tEdges));
    setActiveNode(null);
    setRuntimeWorkflowId(wf.id);
    setSourceTemplate(wf.source_template || null);
    setTrace(null);
  };

  // Save current canvas to the runtime user_workflows collection
  // and return the runtime workflow id (used by Execute).
  const syncToRuntime = useCallback(async () => {
    if (!token || nodes.length === 0) return null;
    try {
      const activeWf = workflows.find((w) => w.id === activeWorkflowId);
      const res = await fetch(`${API}/api/workflows/save`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          studio_workflow_id: activeWorkflowId,
          name: activeWf?.name || "Untitled Workflow",
          nodes,
          edges,
          source_template: sourceTemplate,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setRuntimeWorkflowId(data.workflow_id);
        return data.workflow_id;
      }
    } catch (e) {
      console.error("[syncToRuntime]", e);
    }
    return null;
  }, [token, nodes, edges, sourceTemplate, activeWorkflowId, workflows]);

  // Patch a single node's data (called from NodeConfigPanel)
  const updateNodeData = (nodeId, newData) => {
    setNodes((prev) => prev.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n));
  };

  // Execute the workflow via native engine
  const executeWorkflow = async () => {
    if (executing) return;
    if (nodes.length === 0) {
      toast.error("Add or load some nodes first.");
      return;
    }
    setExecuting(true);
    setShowTrace(true);
    setTrace(null);

    let wfId = runtimeWorkflowId;
    if (!wfId) {
      wfId = await syncToRuntime();
      if (!wfId) {
        toast.error("Could not save workflow before execution.");
        setExecuting(false);
        return;
      }
    } else {
      // sync latest before execute
      await syncToRuntime();
    }

    try {
      const res = await fetch(`${API}/api/workflows/${wfId}/execute`, {
        method: "POST",
        headers,
        body: JSON.stringify({}),
      });
      const data = await res.json();

      // Compute-limit gate returns 200 with allowed:false
      const limitData = parseComputeLimit({ status: res.status, data });
      if (limitData) {
        setComputeLimit(limitData);
        setExecuting(false);
        return;
      }

      setTrace(data);
      if (data.success) toast.success(`Workflow executed in ${data.duration_ms}ms`);
      else toast.error(data.error || "Workflow failed");
    } catch (e) {
      toast.error("Execution failed: " + (e.message || "unknown"));
      setTrace({ success: false, error: e.message, node_results: [] });
    }
    setExecuting(false);
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

  const [publishing, setPublishing] = useState(false);
  const handlePublish = async () => {
    if (!codeJson || nodes.length === 0) { toast.error("Nothing to publish. Add some nodes first."); return; }
    setPublishing(true);
    try {
      const manifest = JSON.parse(codeJson);
      const activeWf = workflows.find(w => w.id === activeWorkflowId);
      const res = await fetch(`${API}/api/published-agents/publish`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: activeWf?.name || "My Agent",
          description: `Agent with ${nodes.length} nodes built in The Armory`,
          manifest,
          trust_score: linterResult?.trust_score || 0,
          linter_status: linterResult?.status || "unknown",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(`Agent published! v${data.version}`);
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to publish.");
      }
    } catch { toast.error("Publish failed."); }
    setPublishing(false);
  };

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
    <div data-testid="studio-page" className="flex flex-col h-[calc(100vh-60px)] w-full t-bg overflow-hidden">
      {/* Toggle Bar */}
      <div data-testid="studio-toggle-bar" className="flex items-center justify-between px-3 sm:px-5 py-2.5 backdrop-blur-sm gap-2" style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg-nav)' }}>
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Sparkles size={14} className="text-cyan-400 shrink-0" />
          <span className="text-[13px] font-medium t-text hidden sm:inline" style={{ fontFamily: "'Outfit', sans-serif" }}>The Armory</span>
          <WorkflowSelector workflows={workflows} activeId={activeWorkflowId} onSelect={selectWorkflow} onCreate={createWorkflow} onDelete={deleteWorkflow} />
          {saving && <span className="text-[10px] t-text-dim animate-pulse hidden sm:inline">Saving...</span>}
        </div>
        <ModeToggle mode={mode} setMode={setMode} isMobile={isMobile} />
        <div className="hidden lg:flex items-center gap-2">
          <button data-testid="save-workflow-btn" onClick={() => saveWorkflow()} className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] t-text-mute hover:t-text">
            <Save size={12} /> Save
          </button>
        </div>
      </div>

      {/* Main Panes */}
      <div className="flex-1 flex flex-row overflow-hidden">
        {/* Desktop: Command chat is a sidebar when in node mode */}
        {!isMobile && mode === "vibe" && <ChatPane messages={messages} onSend={handleChatSend} visible={true} agentStatus={agentStatus} terminalHistory={terminalHistory} />}
        {!isMobile && mode === "vibe" && <CodePane visible={true} codeJson={codeJson} onDeploy={handleDeploy} onPublish={handlePublish} linterResult={linterResult} onRunLinter={runLinter} saving={saving} publishing={publishing} />}

        {!isMobile && mode === "node" && (
          <>
            <MyWorkflowsGrid
              visible={true}
              onLoadWorkflow={loadRuntimeWorkflowIntoCanvas}
              onLoadTemplate={loadTemplateIntoCanvas}
              currentRuntimeId={runtimeWorkflowId}
            />
            <div className="flex-1 relative flex flex-col overflow-hidden">
              <div className="flex-1 relative flex overflow-hidden">
                <CanvasPane
                  visible={true} nodes={nodes} edges={edges}
                  activeNode={activeNode} setActiveNode={setActiveNode}
                  onMoveNode={moveNode} onAddNode={addNode}
                  onDeleteNode={deleteNode} onAddEdge={addEdge}
                  onExecute={executeWorkflow} executing={executing}
                  onPublish={() => setShowPublish(true)}
                  canPublish={!!runtimeWorkflowId && nodes.length > 0}
                />
                {activeNode && !activeBotProject && (
                  <NodeConfigPanel
                    node={nodes.find((n) => n.id === activeNode)}
                    onUpdate={updateNodeData}
                    onClose={() => setActiveNode(null)}
                    runtimeWorkflowId={runtimeWorkflowId}
                    token={token}
                  />
                )}
                {activeBotProject && (
                  <BotProjectPanel
                    project={activeBotProject}
                    onClose={() => setActiveBotProject(null)}
                    onProjectUpdate={(p) => {
                      setActiveBotProject(p);
                      if (p?.nodes) setNodes(p.nodes);
                      if (p?.edges) setEdges(p.edges);
                    }}
                    token={token}
                  />
                )}
              </div>
              <TraceViewer
                open={showTrace}
                onClose={() => setShowTrace(false)}
                trace={trace}
                executing={executing}
              />
            </div>
          </>
        )}

        {/* Mobile: Single pane */}
        {isMobile && mode === "vibe" && <ChatPane messages={messages} onSend={handleChatSend} visible={true} agentStatus={agentStatus} terminalHistory={terminalHistory} />}
        {isMobile && mode === "node" && (
          <div className="flex-1 relative flex flex-col overflow-hidden">
            <CanvasPane
              visible={true} nodes={nodes} edges={edges}
              activeNode={activeNode} setActiveNode={setActiveNode}
              onMoveNode={moveNode} onAddNode={addNode}
              onDeleteNode={deleteNode} onAddEdge={addEdge}
              onExecute={executeWorkflow} executing={executing}
            />
            <TraceViewer
              open={showTrace}
              onClose={() => setShowTrace(false)}
              trace={trace}
              executing={executing}
            />
          </div>
        )}
        {isMobile && mode === "code" && <CodePane visible={true} codeJson={codeJson} onDeploy={handleDeploy} onPublish={handlePublish} linterResult={linterResult} onRunLinter={runLinter} saving={saving} publishing={publishing} />}
      </div>

      {/* Compute Limit Modal */}
      <ComputeLimitModal limitData={computeLimit} onClose={() => setComputeLimit(null)} />

      {/* Publish to Exchange Modal */}
      <PublishToExchangeModal
        open={showPublish}
        onClose={() => setShowPublish(false)}
        runtimeWorkflowId={runtimeWorkflowId}
        workflowName={workflows.find((w) => w.id === activeWorkflowId)?.name}
        onPublished={() => setShowPublish(false)}
      />
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

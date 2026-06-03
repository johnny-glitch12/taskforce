import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Editor from "@monaco-editor/react";
import { toast } from "sonner";
import {
  Send, Sparkles, Loader2, Zap, Bot, User, Plus, Trash2,
  ChevronLeft, ChevronDown, FileCode2, Coins, Clock, ArrowRight,
  Target, X,
} from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL;

const SPEED_COLOR = { fast: "#10b981", medium: "#fbbf24", slow: "#fb7185" };
const QUALITY_COLOR = { good: "#a78bfa", excellent: "#22d3ee" };

function fileLang(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return { py: "python", js: "javascript", ts: "typescript", json: "json",
    md: "markdown", yaml: "yaml", yml: "yaml", sh: "shell", html: "html",
    css: "css", env: "plaintext", txt: "plaintext" }[ext] || "plaintext";
}

function ModelPicker({ models, selected, onSelect }) {
  return (
    <div data-testid="model-picker" className="flex gap-2 overflow-x-auto py-2">
      {models.map((m) => {
        const active = m.id === selected;
        return (
          <button
            key={m.id}
            data-testid={`model-${m.id}`}
            onClick={() => onSelect(m.id)}
            className="shrink-0 min-w-[160px] rounded-sm p-2.5 text-left transition-all hover:translate-y-[-1px] cursor-pointer"
            style={{
              background: active ? "rgba(34,211,238,0.08)" : "var(--bg-card)",
              border: `1px solid ${active ? "#22d3ee" : "var(--border)"}`,
            }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono uppercase tracking-widest t-text-dim">{m.provider}</span>
              {active && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />}
            </div>
            <div className="text-[12px] t-text font-bold truncate">{m.label}</div>
            <div className="flex items-center gap-1 mt-1 text-[9px] font-mono uppercase tracking-wider">
              <span style={{ color: SPEED_COLOR[m.speed] }}>{m.speed}</span>
              <span className="t-text-dim">·</span>
              <span style={{ color: QUALITY_COLOR[m.quality] }}>{m.quality}</span>
            </div>
            <div className="flex items-center gap-1 mt-1.5 text-[10px] font-mono">
              <Coins size={9} className="text-amber-400" />
              <span className="t-text-sub">{m.chat_cost}cr chat · {m.build_cost}cr build</span>
            </div>
            {m.using_byok && (
              <div
                data-testid={`byok-badge-${m.id}`}
                className="mt-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[8px] font-bold tracking-widest uppercase font-mono text-emerald-300"
                style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.3)" }}
              >
                ✓ Your key
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}

function SessionSidebar({ sessions, currentId, onSelect, onNew, onDelete, open, onToggle }) {
  return (
    <aside
      data-testid="session-sidebar"
      className="shrink-0 transition-all overflow-hidden flex flex-col"
      style={{
        width: open ? 240 : 36, background: "var(--bg-sub)",
        borderRight: "1px solid var(--border)",
      }}
    >
      <div className="flex items-center justify-between p-2 shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        {open && <span className="text-[10px] font-mono uppercase tracking-[0.2em] t-text-sub">Sessions</span>}
        <button onClick={onToggle} data-testid="sidebar-toggle"
          className="p-1 rounded-sm t-text-mute hover:t-text" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <ChevronLeft size={11} style={{ transform: open ? "" : "rotate(180deg)" }} />
        </button>
      </div>
      {open && (
        <>
          <button
            data-testid="new-session-btn"
            onClick={onNew}
            className="m-2 px-2 py-2 text-[10px] font-bold tracking-widest uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 flex items-center justify-center gap-1.5"
          >
            <Plus size={11} /> New Build
          </button>
          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-1.5">
            {sessions.length === 0 && (
              <div className="text-[10px] t-text-dim font-mono text-center mt-6">— no sessions yet —</div>
            )}
            {sessions.map((s) => (
              <div
                key={s.id}
                data-testid={`session-${s.id}`}
                onClick={() => onSelect(s.id)}
                className="group rounded-sm p-2 cursor-pointer transition-colors"
                style={{
                  background: s.id === currentId ? "rgba(34,211,238,0.1)" : "var(--bg-card)",
                  border: `1px solid ${s.id === currentId ? "rgba(34,211,238,0.35)" : "var(--border)"}`,
                }}
              >
                <div className="text-[11px] t-text font-medium truncate">{s.title || "Untitled"}</div>
                <div className="flex items-center gap-1 mt-1 text-[9px] font-mono t-text-dim">
                  <Clock size={8} /> {new Date(s.updated_at).toLocaleDateString()}
                  <span className="ml-auto truncate text-cyan-400/70">{s.model?.split("-")[0]}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                  data-testid={`delete-session-${s.id}`}
                  className="mt-1 opacity-0 group-hover:opacity-100 text-[9px] t-text-dim hover:text-rose-400 flex items-center gap-1"
                >
                  <Trash2 size={9} /> Delete
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  const isBuild = msg.type === "build";
  return (
    <div data-testid={`vibe-msg-${msg.role}`} className={`flex gap-2.5 mb-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className="w-7 h-7 rounded-sm flex items-center justify-center shrink-0"
        style={{ background: isUser ? "rgba(34,211,238,0.12)" : isBuild ? "rgba(251,191,36,0.12)" : "var(--bg-elevated)",
                 border: `1px solid ${isUser ? "rgba(34,211,238,0.35)" : isBuild ? "rgba(251,191,36,0.35)" : "var(--border)"}` }}
      >
        {isUser ? <User size={12} className="text-cyan-400" /> : isBuild ? <Sparkles size={12} className="text-amber-400" /> : <Bot size={12} className="t-text-mute" />}
      </div>
      <div className={`max-w-[80%] rounded-sm p-3 text-[12px] leading-relaxed whitespace-pre-wrap ${isUser ? "" : "font-mono"}`}
        style={{
          background: isUser ? "rgba(34,211,238,0.08)" : "var(--bg-card)",
          border: `1px solid ${isUser ? "rgba(34,211,238,0.25)" : "var(--border)"}`,
          color: "var(--text-primary)",
        }}>
        {msg.content}
        {msg.credits_used !== undefined && (
          <div className="mt-2 pt-2 text-[9px] font-mono t-text-dim uppercase tracking-widest" style={{ borderTop: "1px solid var(--border)" }}>
            <Coins size={9} className="inline text-amber-400 mr-1" />
            {msg.credits_used}cr · {msg.model || ""}
          </div>
        )}
      </div>
    </div>
  );
}

function FilePreview({ files }) {
  const [active, setActive] = useState(0);
  useEffect(() => { setActive(0); }, [files]);
  if (!files?.length) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <Sparkles size={28} className="text-cyan-400 mb-3 opacity-50" />
        <div className="text-[13px] t-text font-medium mb-1">No code yet</div>
        <div className="text-[11px] t-text-dim max-w-[280px] font-mono leading-relaxed">
          Chat with the AI to plan your bot. When you're ready, click <span className="text-cyan-400">GENERATE CODE</span> and the files appear here.
        </div>
      </div>
    );
  }
  const f = files[active] || files[0];
  return (
    <div className="h-full flex flex-col" data-testid="vibe-file-preview">
      <div className="flex shrink-0 overflow-x-auto" style={{ borderBottom: "1px solid var(--border)" }}>
        {files.map((file, i) => (
          <button
            key={file.path}
            data-testid={`vibe-file-tab-${i}`}
            onClick={() => setActive(i)}
            className="px-3 py-2 text-[10px] font-mono whitespace-nowrap transition-colors flex items-center gap-1.5"
            style={{
              background: i === active ? "var(--bg)" : "var(--bg-sub)",
              color: i === active ? "var(--text-primary)" : "var(--text-mute)",
              borderRight: "1px solid var(--border)",
              borderBottom: i === active ? "2px solid #22d3ee" : "2px solid transparent",
            }}
          >
            <FileCode2 size={9} style={{ color: i === active ? "#22d3ee" : undefined }} />
            {file.path}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0">
        <Editor
          value={f.content}
          language={f.language || fileLang(f.path)}
          theme="vs-dark"
          options={{
            readOnly: true, minimap: { enabled: false }, fontSize: 12,
            scrollBeyondLastLine: false, wordWrap: "on",
            renderLineHighlight: "none", fontFamily: "'JetBrains Mono', monospace",
          }}
        />
      </div>
    </div>
  );
}

export default function VibeBuildPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [models, setModels] = useState([]);
  const [model, setModel] = useState("gemini-2.5-flash");
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [previewFiles, setPreviewFiles] = useState([]);
  const [previewProject, setPreviewProject] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMode, setBusyMode] = useState(null); // "chat" | "build" | "auto"
  const [autoPickHint, setAutoPickHint] = useState(null); // {model, reason, complexity}
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [bountyPrefill, setBountyPrefill] = useState(null); // {bounty_id, title, reward_type, reward_amount} | null
  const [lastBuild, setLastBuild] = useState(null); // {project_id, name} once a build succeeds
  const chatEndRef = useRef(null);

  // On mount, read the bounty hand-off written by SubmitToBountyModal "Build in Armory" tab.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("tfai_bounty_prefill");
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data?.bounty_id && data?.title) {
        setBountyPrefill(data);
        if (!input) {
          setInput(
            `Build me an agent for the bounty "${data.title}".\n\n` +
            `${data.description ? `Spec:\n${data.description.slice(0, 1200)}\n\n` : ""}` +
            `Please give the agent a clear main.py, a README, and use any required integrations the bounty calls out.`,
          );
        }
      }
    } catch { /* ignore malformed sessionStorage */ }
    // eslint-disable-next-line
  }, []);

  // Load models + sessions
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/vibe/models`, { headers }).then((r) => r.json()).then((d) => {
      setModels(d.models || []);
      setModel(d.default || "gemini-2.5-flash");
    });
    refreshSessions();
    const sid = search.get("session");
    if (sid) loadSession(sid);
    // eslint-disable-next-line
  }, [token]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Auto-dismiss the recommend-hint after 12s — cleanup on unmount or new pick.
  useEffect(() => {
    if (!autoPickHint) return undefined;
    const t = setTimeout(() => setAutoPickHint(null), 12000);
    return () => clearTimeout(t);
  }, [autoPickHint]);

  const refreshSessions = async () => {
    const r = await fetch(`${API}/api/vibe/sessions`, { headers });
    const d = await r.json();
    setSessions(d.sessions || []);
  };

  const loadSession = useCallback(async (sid) => {
    const r = await fetch(`${API}/api/vibe/sessions/${sid}`, { headers });
    if (!r.ok) return;
    const d = await r.json();
    setCurrentSession(d);
    setMessages(d.messages || []);
    setModel(d.model || "gemini-2.5-flash");
    setPreviewFiles([]);
    setPreviewProject(d.project_id || null);
    if (d.project_id) {
      // Load the latest project files
      const pr = await fetch(`${API}/api/armory/bot-projects/${d.project_id}`, { headers });
      if (pr.ok) {
        const proj = await pr.json();
        setPreviewFiles(proj.files || []);
      }
    }
    navigate(`/build?session=${sid}`, { replace: true });
    // eslint-disable-next-line
  }, [token]);

  const newSession = () => {
    setCurrentSession(null);
    setMessages([]);
    setPreviewFiles([]);
    setPreviewProject(null);
    setInput("");
    navigate("/build", { replace: true });
  };

  const deleteSession = async (sid) => {
    if (!window.confirm("Delete this session?")) return;
    await fetch(`${API}/api/vibe/sessions/${sid}`, { method: "DELETE", headers });
    toast.success("Session deleted");
    if (sid === currentSession?.id) newSession();
    refreshSessions();
  };

  const autoPick = async () => {
    if (!input.trim() || busy) {
      toast.error("Type your idea first so the auto-picker has something to work with.");
      return;
    }
    setBusy(true); setBusyMode("auto");
    try {
      const res = await fetch(`${API}/api/vibe/recommend-model`, {
        method: "POST", headers, body: JSON.stringify({ prompt: input.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.detail || data.message || "Couldn't recommend a model");
        return;
      }
      setModel(data.model);
      setAutoPickHint({ model: data.model, reason: data.reason, complexity: data.complexity });
      toast.success(`Auto-picked ${data.label} (${data.complexity}) · -${data.credits_used}cr`);
    } catch {
      toast.error("Network error");
    } finally {
      setBusy(false); setBusyMode(null);
    }
  };

  const send = async (mode /* "chat" | "build" */) => {
    if (!input.trim() || busy) return;
    const userText = input.trim();
    setInput("");
    setBusy(true); setBusyMode(mode);
    const userMsg = { role: "user", content: userText, timestamp: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);

    try {
      const endpoint = mode === "build" ? "/api/vibe/generate" : "/api/vibe/chat";
      const body = mode === "build"
        ? { session_id: currentSession?.id, message: userText, model }
        : { session_id: currentSession?.id || null, message: userText, model };
      const res = await fetch(`${API}${endpoint}`, { method: "POST", headers, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) {
        if (data.error === "INSUFFICIENT_CREDITS") {
          toast.error(`Need ${data.cost ?? data.required} credits — you have ${data.balance ?? 0}. Top up?`);
        } else if (data.detail?.error === "BYOK_REQUIRED" || data.error === "BYOK_REQUIRED") {
          toast.error(`Add your ${data.detail?.service || data.service} API key in the Vault.`);
        } else {
          toast.error(data.detail || data.message || "Request failed");
        }
        setMessages((m) => m.slice(0, -1)); // pop the optimistic user msg
        return;
      }
      // Append AI message
      const aiMsg = {
        role: "assistant",
        content: mode === "build" ? `Generated ${data.name} — ${data.files?.length} files, ${data.nodes?.length} nodes.` : data.response,
        type: data.type,
        credits_used: data.credits_used,
        model: data.model,
        timestamp: new Date().toISOString(),
      };
      setMessages((m) => [...m, aiMsg]);
      if (!currentSession) setCurrentSession({ id: data.session_id, title: userText.slice(0, 80), model });
      else setCurrentSession((s) => ({ ...s, id: data.session_id }));
      if (mode === "build") {
        setPreviewFiles(data.files || []);
        setPreviewProject(data.project_id);
        setLastBuild({ project_id: data.project_id, name: data.name });
        toast.success(`Generated ${data.files?.length || 0} files (-${data.credits_used}cr)`);
      }
      refreshSessions();
    } catch (e) {
      toast.error("Network error");
      setMessages((m) => m.slice(0, -1));
    } finally {
      setBusy(false); setBusyMode(null);
    }
  };

  const activeModel = models.find((m) => m.id === model);
  const buildCost = activeModel?.build_cost ?? 5;

  return (
    <div data-testid="vibe-build-page" className="h-[calc(100vh-56px)] flex t-bg">
      <SessionSidebar
        sessions={sessions} currentId={currentSession?.id}
        onSelect={loadSession} onNew={newSession} onDelete={deleteSession}
        open={sidebarOpen} onToggle={() => setSidebarOpen((o) => !o)}
      />

      {/* Center: chat */}
      <div className="flex-1 flex flex-col min-w-0" style={{ borderRight: "1px solid var(--border)" }}>
        {/* Bounty context banner — shown when the user arrived from a bounty submit flow */}
        {bountyPrefill && (
          <div
            data-testid="bounty-prefill-banner"
            className="shrink-0 px-4 py-2 flex items-center gap-3"
            style={{ background: "rgba(34,211,238,0.06)", borderBottom: "1px solid rgba(34,211,238,0.3)" }}
          >
            <Target size={14} className="text-cyan-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-400 mb-0.5">Building for bounty</div>
              <div className="text-[12px] t-text font-medium truncate" title={bountyPrefill.title}>
                {bountyPrefill.title}
              </div>
            </div>
            {lastBuild && (
              <button
                data-testid="submit-to-bounty-cta"
                onClick={() => {
                  sessionStorage.removeItem("tfai_bounty_prefill");
                  navigate(`/bounties/${bountyPrefill.bounty_id}?submit=1`);
                }}
                className="shrink-0 px-3 py-1.5 rounded-sm text-[10px] font-bold uppercase tracking-[0.15em] font-mono inline-flex items-center gap-1.5"
                style={{ background: "#22d3ee", color: "#0a0e1a" }}
                title="Publish this build first, then submit it from the bounty page"
              >
                <ArrowRight size={11} /> Submit to bounty
              </button>
            )}
            <button
              data-testid="bounty-prefill-clear"
              onClick={() => { sessionStorage.removeItem("tfai_bounty_prefill"); setBountyPrefill(null); }}
              className="shrink-0 t-text-dim hover:text-rose-400"
              title="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        )}
        {/* Top bar with model picker */}
        <div className="shrink-0 px-4 py-2" style={{ background: "var(--bg-sub)", borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-cyan-400" />
              <span className="text-[11px] font-bold tracking-[0.18em] uppercase font-mono t-text">
                {currentSession?.title || "New Build Session"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                data-testid="vibe-auto-pick"
                onClick={autoPick}
                disabled={busy || !input.trim()}
                title={!input.trim() ? "Type your idea first" : "Auto-pick the best model (1cr)"}
                className="px-2.5 py-1 text-[9px] font-bold tracking-[0.18em] uppercase font-mono rounded-sm transition-all flex items-center gap-1 disabled:opacity-40"
                style={{
                  background: busyMode === "auto" ? "rgba(34,211,238,0.18)" : "rgba(34,211,238,0.06)",
                  border: "1px solid rgba(34,211,238,0.4)",
                  color: "#22d3ee",
                }}
              >
                {busyMode === "auto" ? <Loader2 size={9} className="animate-spin" /> : <Sparkles size={9} />}
                Auto · 1cr
              </button>
              <span className="text-[10px] font-mono t-text-dim">
                {messages.length} msgs · {activeModel?.label || model}
              </span>
            </div>
          </div>
          {autoPickHint && (
            <div
              data-testid="auto-pick-hint"
              className="mb-2 px-2.5 py-1.5 rounded-sm flex items-start gap-2 text-[10px] font-mono"
              style={{
                background: "rgba(34,211,238,0.06)",
                border: "1px solid rgba(34,211,238,0.3)",
              }}
            >
              <Sparkles size={10} className="text-cyan-400 mt-0.5 shrink-0" />
              <div className="flex-1 t-text-sub leading-relaxed">
                <span className="text-cyan-400 font-bold uppercase tracking-widest mr-1.5">{autoPickHint.complexity}</span>
                {autoPickHint.reason}
              </div>
              <button
                onClick={() => setAutoPickHint(null)}
                className="t-text-dim hover:t-text shrink-0"
                aria-label="Dismiss"
              >×</button>
            </div>
          )}
          <ModelPicker models={models} selected={model} onSelect={setModel} />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {messages.length === 0 && !busy && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
              <Bot size={32} className="text-cyan-400 mb-3 opacity-60" />
              <div className="text-[14px] t-text font-medium mb-2">Describe the bot you want to build.</div>
              <div className="text-[11px] t-text-dim font-mono leading-relaxed">
                Chat to plan ({models.find(m=>m.id===model)?.chat_cost || 1}cr per AI reply). Click <span className="text-cyan-400">GENERATE CODE</span> when you're ready ({buildCost}cr).
              </div>
              <div className="grid grid-cols-1 gap-2 mt-6 w-full">
                {[
                  "A bot that posts trending HackerNews articles to my Slack channel every hour",
                  "An agent that reads my Gmail inbox and summarises urgent emails to Telegram",
                  "A workflow that monitors my Stripe payments and DMs me on Discord for refunds over $100",
                ].map((s, i) => (
                  <button
                    key={i}
                    data-testid={`vibe-suggestion-${i}`}
                    onClick={() => setInput(s)}
                    className="text-left text-[11px] rounded-sm px-3 py-2 transition-colors hover:border-cyan-400/50"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-sub)" }}
                  >
                    <ArrowRight size={9} className="inline text-cyan-400 mr-1.5" /> {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
          {busy && (
            <div data-testid="vibe-loading" className="flex items-center gap-2 text-[11px] t-text-dim font-mono ml-9">
              <Loader2 size={12} className="animate-spin text-cyan-400" />
              {busyMode === "build" ? "Generating code…" : "Thinking…"}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input bar */}
        <div className="shrink-0 px-4 py-3" style={{ background: "var(--bg-sub)", borderTop: "1px solid var(--border)" }}>
          <div className="flex items-end gap-2">
            <textarea
              data-testid="vibe-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send("chat"); }
              }}
              placeholder="Describe what you want, or ask a follow-up…"
              rows={2}
              className="flex-1 px-3 py-2 text-[12px] rounded-sm font-mono resize-none focus:outline-none focus:border-cyan-400/50"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)", minHeight: 50, maxHeight: 180 }}
              disabled={busy}
            />
            <div className="flex flex-col gap-1.5">
              <button
                data-testid="vibe-send-chat"
                onClick={() => send("chat")}
                disabled={busy || !input.trim()}
                className="px-3 py-1.5 text-[10px] font-mono tracking-widest uppercase rounded-sm t-text-sub disabled:opacity-30 hover:t-text flex items-center gap-1.5"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
              >
                <Send size={10} /> Send · 1cr
              </button>
              <button
                data-testid="vibe-send-build"
                onClick={() => send("build")}
                disabled={busy || !input.trim() || !currentSession}
                title={!currentSession ? "Start the conversation first" : ""}
                className="px-3 py-1.5 text-[10px] font-bold tracking-widest uppercase rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-30 flex items-center gap-1.5"
              >
                <Zap size={10} /> Generate · {buildCost}cr
              </button>
            </div>
          </div>
          <div className="text-[9px] t-text-dim font-mono mt-1.5">
            <kbd className="px-1 py-0.5 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>Enter</kbd> to chat ·
            <kbd className="px-1 py-0.5 ml-1 rounded-sm" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>Shift+Enter</kbd> new line
          </div>
        </div>
      </div>

      {/* Right: file preview (40%) */}
      <div className="shrink-0 flex flex-col" style={{ width: "42%", background: "var(--bg-sub)" }}>
        <div className="shrink-0 px-4 py-2 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2">
            <FileCode2 size={12} className="text-cyan-400" />
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] t-text-sub">Generated Files</span>
            {previewFiles.length > 0 && (
              <span className="text-[9px] font-mono t-text-dim">· {previewFiles.length} files</span>
            )}
          </div>
          {previewProject && (
            <button
              data-testid="vibe-open-armory"
              onClick={() => navigate(`/armory?project=${previewProject}`)}
              className="text-[9px] font-mono uppercase tracking-widest text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
            >
              Open in Armory <ArrowRight size={9} />
            </button>
          )}
        </div>
        <div className="flex-1 min-h-0">
          <FilePreview files={previewFiles} />
        </div>
      </div>
    </div>
  );
}

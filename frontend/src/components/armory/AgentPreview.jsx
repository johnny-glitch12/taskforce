/* eslint-disable react/prop-types */
/**
 * AgentPreview — Right panel.
 * Header card with agent meta (name, version, status, trust score)
 * Tabs: Files | Flow | Config
 * Bottom: AgentActionBar (Test Run / Deploy / Publish / Export)
 */
import { useState, useMemo } from "react";
import {
  FileCode2, GitBranch, Settings, Bot, Shield, X, ChevronRight,
} from "lucide-react";
import Editor from "@monaco-editor/react";
import AgentActionBar from "./AgentActionBar";

const TABS = [
  { id: "files", label: "Files", Icon: FileCode2 },
  { id: "flow", label: "Flow", Icon: GitBranch },
  { id: "config", label: "Config", Icon: Settings },
];

function fileLang(path) {
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".js") || path.endsWith(".jsx")) return "javascript";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".yaml") || path.endsWith(".yml")) return "yaml";
  return "plaintext";
}

export default function AgentPreview({
  project, files, nodes, edges, onClose,
  onTestRun, onDeploy, onPublish, onExport,
  testRunResult, busyAction,
}) {
  const [tab, setTab] = useState("files");
  const [activeFileIdx, setActiveFileIdx] = useState(0);

  const trustScore = project?.trust_score;
  const status = project ? (project.deployed ? "Deployed" : "Ready") : "Draft";
  const statusColor = project?.deployed ? "var(--armory-accent)" : (project ? "var(--armory-success)" : "var(--armory-text-mute)");

  return (
    <aside
      data-testid="armory-preview"
      className="shrink-0 flex flex-col"
      style={{
        width: 380,
        background: "var(--armory-panel)",
        borderLeft: "1px solid var(--armory-border)",
      }}
    >
      {/* Agent card */}
      <header className="shrink-0 px-4 py-3" style={{ borderBottom: "1px solid var(--armory-border)" }}>
        <div className="flex items-start gap-3">
          <div
            className="w-10 h-10 rounded-sm flex items-center justify-center shrink-0"
            style={{ background: "var(--armory-card)", border: "1px solid var(--armory-accent)" }}
          >
            <Bot size={16} style={{ color: "var(--armory-accent)" }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <h2 className="text-[14px] truncate" style={{ color: "var(--armory-text)", fontFamily: "'Rajdhani', sans-serif", fontWeight: 500, letterSpacing: "-0.005em" }}>
                {project?.name || "Untitled"}
              </h2>
              {project?.version != null && (
                <span className="text-[9px] font-mono px-1.5 py-px rounded-sm shrink-0"
                      style={{ background: "var(--armory-card)", color: "var(--armory-text-mute)", border: "1px solid var(--armory-border)" }}>
                  v{project.version}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span
                data-testid="armory-preview-status"
                className="text-[9px] font-mono uppercase tracking-[0.15em] inline-flex items-center gap-1"
                style={{ color: statusColor }}
              >
                <span className="inline-block w-1.5 h-1.5 rounded-sm" style={{ background: statusColor }} />
                {status}
              </span>
              {trustScore != null && (
                <span className="text-[9px] font-mono inline-flex items-center gap-1" style={{ color: "var(--armory-text-mute)" }}>
                  <Shield size={9} /> {trustScore}
                </span>
              )}
            </div>
          </div>
          <button
            data-testid="armory-preview-close"
            onClick={onClose}
            aria-label="Close preview"
            className="p-1 rounded-sm transition-colors hover:bg-white/5"
            style={{ color: "var(--armory-text-mute)" }}
          >
            <X size={13} />
          </button>
        </div>
      </header>

      {/* Tabs */}
      <nav className="flex shrink-0" style={{ borderBottom: "1px solid var(--armory-border)" }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`armory-tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.15em] transition-all"
            style={{
              color: tab === t.id ? "var(--armory-accent)" : "var(--armory-text-mute)",
              background: tab === t.id ? "var(--armory-active-bg)" : "transparent",
              borderBottom: `2px solid ${tab === t.id ? "var(--armory-accent)" : "transparent"}`,
            }}
          >
            <t.Icon size={11} /> {t.label}
          </button>
        ))}
      </nav>

      {/* Tab body */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === "files" && (
          <FilesTab files={files} activeIdx={activeFileIdx} setActiveIdx={setActiveFileIdx} />
        )}
        {tab === "flow" && <FlowTab nodes={nodes} edges={edges} />}
        {tab === "config" && <ConfigTab project={project} />}
      </div>

      {/* Action bar */}
      <AgentActionBar
        project={project}
        onTestRun={onTestRun}
        onDeploy={onDeploy}
        onPublish={onPublish}
        onExport={onExport}
        testRunResult={testRunResult}
        busyAction={busyAction}
      />
    </aside>
  );
}

function FilesTab({ files, activeIdx, setActiveIdx }) {
  if (!files?.length) {
    return (
      <div className="h-full flex items-center justify-center p-8 text-center">
        <p className="text-[11px] font-mono" style={{ color: "var(--armory-text-dim)" }}>
          No files yet — generate code to see them here.
        </p>
      </div>
    );
  }
  const safeIdx = Math.min(activeIdx, files.length - 1);
  const f = files[safeIdx];
  return (
    <div data-testid="armory-files-tab" className="h-full flex flex-col">
      {/* File tabs */}
      <div className="flex overflow-x-auto shrink-0" style={{ borderBottom: "1px solid var(--armory-border)" }}>
        {files.map((file, i) => (
          <button
            key={file.path + i}
            data-testid={`armory-file-tab-${i}`}
            onClick={() => setActiveIdx(i)}
            className="px-3 py-1.5 text-[10px] font-mono whitespace-nowrap inline-flex items-center gap-1.5 shrink-0 transition-all"
            style={{
              background: i === safeIdx ? "var(--armory-code-bg)" : "transparent",
              color: i === safeIdx ? "var(--armory-text)" : "var(--armory-text-mute)",
              borderRight: "1px solid var(--armory-border)",
              borderBottom: `2px solid ${i === safeIdx ? "var(--armory-accent)" : "transparent"}`,
            }}
          >
            <FileCode2 size={9} style={{ color: i === safeIdx ? "var(--armory-accent)" : undefined }} />
            {file.path}
          </button>
        ))}
      </div>
      {/* Editor */}
      <div className="flex-1 min-h-0" style={{ background: "var(--armory-code-bg)" }}>
        <Editor
          value={f?.content || ""}
          language={f?.language || fileLang(f?.path || "")}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            renderLineHighlight: "none",
            padding: { top: 12, bottom: 12 },
          }}
        />
      </div>
    </div>
  );
}

function FlowTab({ nodes, edges }) {
  const layout = useMemo(() => {
    if (!nodes?.length) return null;
    const W = 360;        // panel width minus padding
    const COLS = 3;
    const NODE_W = 96;
    const NODE_H = 36;
    const GAP_X = (W - 24 - NODE_W * COLS) / (COLS - 1);
    const ROW_H = 64;
    const positioned = nodes.map((n, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      return {
        id: String(n.id ?? i),
        label: n.label || n.type || `node-${i}`,
        type: n.type,
        x: 12 + col * (NODE_W + GAP_X),
        y: 16 + row * ROW_H,
        w: NODE_W,
        h: NODE_H,
      };
    });
    const byId = new Map(positioned.map((p) => [p.id, p]));
    const edgeLines = (edges || []).map((e, i) => {
      const s = byId.get(String(e.source));
      const t = byId.get(String(e.target));
      if (!s || !t) return null;
      return {
        id: e.id || `e-${i}`,
        x1: s.x + s.w / 2,
        y1: s.y + s.h,
        x2: t.x + t.w / 2,
        y2: t.y,
      };
    }).filter(Boolean);
    const totalRows = Math.ceil(positioned.length / COLS);
    return {
      nodes: positioned,
      edges: edgeLines,
      height: Math.max(120, 32 + totalRows * ROW_H),
    };
  }, [nodes, edges]);

  if (!nodes?.length || !layout) {
    return (
      <div className="h-full flex items-center justify-center p-8 text-center">
        <p className="text-[11px] font-mono" style={{ color: "var(--armory-text-dim)" }}>
          No nodes yet — generate code to see the flow.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="armory-flow-tab" className="h-full overflow-auto p-3" style={{ background: "var(--armory-bg)" }}>
      <svg
        width="100%"
        height={layout.height}
        viewBox={`0 0 360 ${layout.height}`}
        style={{ background: "var(--armory-bg)" }}
      >
        {/* grid dots */}
        <defs>
          <pattern id="armory-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.7" fill="#222" />
          </pattern>
          <marker id="armory-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--armory-text-dim)" />
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="url(#armory-grid)" />

        {/* edges */}
        {layout.edges.map((e) => (
          <line
            key={e.id}
            x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
            stroke="var(--armory-text-dim)" strokeWidth="1.2"
            markerEnd="url(#armory-arrow)"
          />
        ))}

        {/* nodes */}
        {layout.nodes.map((n) => (
          <g key={n.id} data-testid={`armory-flow-node-${n.id}`}>
            <rect
              x={n.x} y={n.y} width={n.w} height={n.h}
              rx="2"
              fill={nodeColor(n.type)}
              stroke="rgba(0,0,0,0.2)"
              strokeWidth="1"
            />
            <text
              x={n.x + n.w / 2} y={n.y + n.h / 2 + 3}
              textAnchor="middle"
              fontSize="9"
              fontFamily="JetBrains Mono, monospace"
              fill="#0a0a0a"
              style={{ fontWeight: 600 }}
            >
              {(n.label || "").slice(0, 12)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function nodeColor(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("trigger") || t.includes("webhook") || t.includes("start")) return "#22d3ee";
  if (t.includes("llm") || t.includes("ai") || t.includes("gpt") || t.includes("claude") || t.includes("gemini")) return "#a855f7";
  if (t.includes("condition") || t.includes("if") || t.includes("filter")) return "#f59e0b";
  return "#10b981"; // default: action/green
}

function ConfigTab({ project }) {
  if (!project) {
    return (
      <div className="h-full flex items-center justify-center p-8 text-center">
        <p className="text-[11px] font-mono" style={{ color: "var(--armory-text-dim)" }}>
          No agent yet — generate code first.
        </p>
      </div>
    );
  }
  return (
    <div data-testid="armory-config-tab" className="h-full overflow-y-auto p-4 space-y-3">
      <ConfigRow label="Name" value={project.name} />
      <ConfigRow label="Language" value={project.language || "python"} />
      <ConfigRow label="Source" value={project.source || "vibe"} />
      <ConfigRow label="Version" value={`v${project.version ?? 1}`} />
      <ConfigRow label="Files" value={`${(project.files || []).length} files`} />
      <ConfigRow label="Nodes" value={`${(project.nodes || []).length} nodes`} />
      <div>
        <div className="text-[9px] font-mono uppercase tracking-[0.18em] mb-1" style={{ color: "var(--armory-text-dim)" }}>
          Description
        </div>
        <div className="text-[12px] leading-relaxed" style={{ color: "var(--armory-text)" }}>
          {project.description || <span className="opacity-50">No description yet.</span>}
        </div>
      </div>
      {project.commit_history?.length > 0 && (
        <div>
          <div className="text-[9px] font-mono uppercase tracking-[0.18em] mb-1.5" style={{ color: "var(--armory-text-dim)" }}>
            Commits ({project.commit_history.length})
          </div>
          <ul className="space-y-1">
            {project.commit_history.slice(-5).reverse().map((c) => (
              <li key={c.commit_id} className="text-[10.5px] font-mono leading-relaxed" style={{ color: "var(--armory-text-mute)" }}>
                <ChevronRight size={9} className="inline -mt-0.5 opacity-50" /> {c.message || "(no message)"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ConfigRow({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[9px] font-mono uppercase tracking-[0.18em]" style={{ color: "var(--armory-text-dim)" }}>
        {label}
      </span>
      <span className="text-[12px] font-mono truncate ml-3" style={{ color: "var(--armory-text)" }}>
        {value}
      </span>
    </div>
  );
}

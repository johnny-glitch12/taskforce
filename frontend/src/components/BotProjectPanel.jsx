import { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { toast } from "sonner";
import {
  FileText, FileCode2, FileJson2, FileType2, Save, GitFork,
  GitCommit, Loader2, X, ChevronRight, History, FolderTree, Plus,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/* Match a file extension to Monaco language + icon */
function fileMeta(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  const map = {
    py: { lang: "python", icon: FileCode2, color: "#22d3ee" },
    js: { lang: "javascript", icon: FileCode2, color: "#facc15" },
    jsx: { lang: "javascript", icon: FileCode2, color: "#22d3ee" },
    ts: { lang: "typescript", icon: FileCode2, color: "#3b82f6" },
    tsx: { lang: "typescript", icon: FileCode2, color: "#3b82f6" },
    json: { lang: "json", icon: FileJson2, color: "#10b981" },
    md: { lang: "markdown", icon: FileType2, color: "#a78bfa" },
    txt: { lang: "plaintext", icon: FileText, color: "#71717a" },
    yaml: { lang: "yaml", icon: FileText, color: "#f97316" },
    yml: { lang: "yaml", icon: FileText, color: "#f97316" },
  };
  return map[ext] || { lang: "plaintext", icon: FileText, color: "#a1a1aa" };
}

/**
 * BotProjectPanel — slides in from the right of the Armory canvas when a
 * bot project is loaded. Shows a file tree + Monaco code editor + commit
 * & fork actions.
 */
export default function BotProjectPanel({ project, onClose, onProjectUpdate, token }) {
  const [activePath, setActivePath] = useState(null);
  const [draft, setDraft] = useState({}); // path → unsaved content
  const [saving, setSaving] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [forking, setForking] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  useEffect(() => {
    if (project?.files?.length > 0 && !activePath) {
      setActivePath(project.files[0].path);
    }
  }, [project, activePath]);

  if (!project) return null;

  const activeFile = project.files.find((f) => f.path === activePath);
  const currentContent = draft[activePath] ?? activeFile?.content ?? "";
  const isDirty = draft[activePath] !== undefined && draft[activePath] !== activeFile?.content;
  const anyDirty = Object.keys(draft).some((p) => {
    const orig = project.files.find((f) => f.path === p)?.content;
    return draft[p] !== orig;
  });

  const meta = activeFile ? fileMeta(activeFile.path) : { lang: "plaintext" };

  const handleSaveFile = async () => {
    if (!isDirty) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/armory/bot-projects/${project.id}/files`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ path: activePath, content: currentContent }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Save failed.");
      } else {
        const data = await res.json();
        const updatedProject = { ...project, files: data.files };
        onProjectUpdate?.(updatedProject);
        setDraft((d) => { const nd = { ...d }; delete nd[activePath]; return nd; });
        toast.success(`Saved ${activePath}`);
      }
    } catch {
      toast.error("Network error on save.");
    }
    setSaving(false);
  };

  const handleCommit = async () => {
    const msg = prompt("Commit message:");
    if (!msg) return;
    setCommitting(true);
    try {
      // Use the in-memory drafts merged with project files
      const merged = project.files.map((f) => ({
        path: f.path,
        content: draft[f.path] ?? f.content,
        language: f.language,
      }));
      const res = await fetch(`${API}/api/armory/bot-projects/${project.id}/commit`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message: msg, files: merged, nodes: project.nodes, edges: project.edges }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Commit failed.");
      } else {
        const data = await res.json();
        onProjectUpdate?.(data.project);
        setDraft({});
        toast.success(`Committed v${data.project.version}`);
      }
    } catch {
      toast.error("Commit failed.");
    }
    setCommitting(false);
  };

  const handleFork = async () => {
    setForking(true);
    try {
      const res = await fetch(`${API}/api/armory/bot-projects/${project.id}/fork`, {
        method: "POST",
        headers,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Fork failed.");
      } else {
        const data = await res.json();
        onProjectUpdate?.(data.project);
        setDraft({});
        toast.success(`Forked → "${data.project.name}"`);
      }
    } catch {
      toast.error("Fork failed.");
    }
    setForking(false);
  };

  return (
    <div
      data-testid="bot-project-panel"
      className="flex flex-col shrink-0 h-full"
      style={{ width: 520, background: 'var(--bg-card)', borderLeft: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-3 py-2 flex items-center gap-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <FolderTree size={14} className="text-cyan-400 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-[12px] t-text font-medium truncate" data-testid="bot-project-name">{project.name}</div>
          <div className="text-[9px] t-text-dim flex items-center gap-1.5 uppercase tracking-wider">
            <span>v{project.version}</span>
            <span>·</span>
            <span>{project.files.length} files</span>
            {project.forked_from && (
              <>
                <span>·</span>
                <span className="text-cyan-400 flex items-center gap-0.5">
                  <GitFork size={8} /> forked
                </span>
              </>
            )}
          </div>
        </div>
        <button
          data-testid="bot-history-btn"
          onClick={() => setShowHistory(!showHistory)}
          className="p-1.5 t-text-mute hover:t-text"
          title="Commit history"
        >
          <History size={13} />
        </button>
        <button
          data-testid="bot-fork-btn"
          onClick={handleFork}
          disabled={forking}
          className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-sm text-cyan-300 hover:bg-cyan-400/10 transition-colors disabled:opacity-50"
          style={{ border: '1px solid rgba(34,211,238,0.3)' }}
          title="Fork this project"
        >
          {forking ? <Loader2 size={10} className="animate-spin" /> : <GitFork size={10} />}
          FORK
        </button>
        <button
          data-testid="bot-commit-btn"
          onClick={handleCommit}
          disabled={committing || !anyDirty}
          className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 transition-colors disabled:opacity-30"
          title="Commit a new version snapshot"
        >
          {committing ? <Loader2 size={10} className="animate-spin" /> : <GitCommit size={10} />}
          COMMIT
        </button>
        <button data-testid="bot-panel-close" onClick={onClose} className="p-1 t-text-mute hover:t-text">
          <X size={13} />
        </button>
      </div>

      {/* Body: file tree + editor */}
      {showHistory ? (
        <CommitHistory project={project} />
      ) : (
        <div className="flex-1 flex min-h-0">
          {/* File tree */}
          <div className="w-44 shrink-0 overflow-y-auto py-1.5" style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
            {project.files.map((f) => {
              const fm = fileMeta(f.path);
              const Icon = fm.icon;
              const active = f.path === activePath;
              const dirty = draft[f.path] !== undefined && draft[f.path] !== f.content;
              return (
                <button
                  key={f.path}
                  data-testid={`file-${f.path.replace(/[/.]/g, '-')}`}
                  onClick={() => setActivePath(f.path)}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-left transition-colors ${
                    active ? "bg-[var(--bg-card-hover)] t-text" : "t-text-mute hover:t-text"
                  }`}
                >
                  <Icon size={11} style={{ color: fm.color }} />
                  <span className="truncate flex-1">{f.path}</span>
                  {dirty && <span className="w-1.5 h-1.5 rounded-sm bg-amber-400" />}
                </button>
              );
            })}
          </div>

          {/* Editor */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="px-3 py-1.5 flex items-center gap-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
              <span className="text-[10px] t-text-dim uppercase tracking-wider flex-1 truncate">
                {activePath || "no file"} {isDirty && <span className="text-amber-400 ml-1">●</span>}
              </span>
              <button
                data-testid="save-file-btn"
                onClick={handleSaveFile}
                disabled={!isDirty || saving}
                className="flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-sm bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-30 transition-colors"
                style={{ border: '1px solid rgba(16,185,129,0.3)' }}
              >
                {saving ? <Loader2 size={9} className="animate-spin" /> : <Save size={9} />}
                Save
              </button>
            </div>
            <div className="flex-1 min-h-0">
              {activeFile && (
                <Editor
                  height="100%"
                  language={meta.lang}
                  value={currentContent}
                  theme="vs-dark"
                  options={{
                    fontSize: 12,
                    fontFamily: "'JetBrains Mono', monospace",
                    minimap: { enabled: false },
                    wordWrap: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 2,
                  }}
                  onChange={(value) => setDraft((d) => ({ ...d, [activePath]: value ?? "" }))}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CommitHistory({ project }) {
  const history = (project.commit_history || []).slice().reverse();
  return (
    <div data-testid="commit-history" className="flex-1 overflow-y-auto p-3 space-y-1.5">
      <div className="text-[10px] t-text-dim uppercase tracking-wider mb-2">
        {history.length} commit{history.length !== 1 ? "s" : ""}
      </div>
      {history.map((c) => (
        <div
          key={c.commit_id}
          data-testid={`commit-${c.commit_id}`}
          className="rounded-sm p-2.5"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-start gap-2">
            <GitCommit size={11} className="text-cyan-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="text-[11px] t-text font-medium truncate">{c.message}</div>
              <div className="text-[9px] t-text-dim mt-0.5 flex items-center gap-1.5">
                <span className="font-mono">{c.commit_id}</span>
                <span>·</span>
                <span>{c.author}</span>
                <span>·</span>
                <span>{new Date(c.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

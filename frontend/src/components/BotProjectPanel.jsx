import { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { toast } from "sonner";
import {
  FileText, FileCode2, FileJson2, FileType2, Save, GitFork,
  GitCommit, Loader2, X, History, FolderTree, Plus, ChevronDown,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/** Match a file extension to Monaco language + colored file-tab icon. */
function fileMeta(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  const map = {
    py:    { lang: "python",     icon: FileCode2, color: "#22d3ee" },
    js:    { lang: "javascript", icon: FileCode2, color: "#facc15" },
    jsx:   { lang: "javascript", icon: FileCode2, color: "#22d3ee" },
    ts:    { lang: "typescript", icon: FileCode2, color: "#3b82f6" },
    tsx:   { lang: "typescript", icon: FileCode2, color: "#3b82f6" },
    json:  { lang: "json",       icon: FileJson2, color: "#10b981" },
    md:    { lang: "markdown",   icon: FileType2, color: "#a78bfa" },
    txt:   { lang: "plaintext",  icon: FileText,  color: "#71717a" },
    yaml:  { lang: "yaml",       icon: FileText,  color: "#f97316" },
    yml:   { lang: "yaml",       icon: FileText,  color: "#f97316" },
    sh:    { lang: "shell",      icon: FileCode2, color: "#84cc16" },
    html:  { lang: "html",       icon: FileCode2, color: "#f87171" },
    css:   { lang: "css",        icon: FileCode2, color: "#60a5fa" },
    env:   { lang: "plaintext",  icon: FileText,  color: "#a3e635" },
  };
  return map[ext] || { lang: "plaintext", icon: FileText, color: "#a1a1aa" };
}

/**
 * BotProjectPanel — slides in from the right of the Armory canvas.
 *
 * UX: tabbed code editor (VS Code-style). One tab per OPEN file. Close (×)
 * removes the tab without deleting the file. The full file list is in an
 * "All Files" dropdown — click a file there to open it as a new tab.
 *
 * Whole panel collapses to a thin vertical strip when minimized so the
 * canvas reclaims its width; click the strip to re-expand.
 */
export default function BotProjectPanel({ project, onClose, onProjectUpdate, token }) {
  const [openTabs, setOpenTabs] = useState([]);   // [path, path, ...]
  const [activeTab, setActiveTab] = useState(null);
  const [draft, setDraft] = useState({});         // path → unsaved content
  const [saving, setSaving] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [forking, setForking] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showFileList, setShowFileList] = useState(false);
  const [minimized, setMinimized] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // When a new project loads, open the first file as a tab.
  useEffect(() => {
    if (project?.files?.length > 0 && openTabs.length === 0) {
      const first = project.files[0].path;
      setOpenTabs([first]);
      setActiveTab(first);
    }
  }, [project?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!project) return null;

  // Minimized strip — collapsed handle
  if (minimized) {
    return (
      <div
        data-testid="bot-project-panel-minimized"
        onClick={() => setMinimized(false)}
        className="flex flex-col items-center justify-center cursor-pointer shrink-0 hover:bg-cyan-400/5 transition-colors h-full"
        style={{ width: 28, background: 'var(--bg-card)', borderLeft: '1px solid var(--border)' }}
        title={`Open ${project.name}`}
      >
        <FolderTree size={13} className="text-cyan-400 mb-2" />
        <div
          className="text-[9px] tracking-wider uppercase t-text-mute"
          style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
        >
          {project.name}
        </div>
      </div>
    );
  }

  const openFile = (path) => {
    if (!openTabs.includes(path)) setOpenTabs((t) => [...t, path]);
    setActiveTab(path);
    setShowFileList(false);
    setShowHistory(false);
  };

  const closeTab = (e, path) => {
    e.stopPropagation();
    const nextTabs = openTabs.filter((p) => p !== path);
    setOpenTabs(nextTabs);
    if (activeTab === path) {
      setActiveTab(nextTabs.length > 0 ? nextTabs[nextTabs.length - 1] : null);
    }
    // also drop the unsaved draft for that file
    setDraft((d) => { const nd = { ...d }; delete nd[path]; return nd; });
  };

  const activeFile = project.files.find((f) => f.path === activeTab);
  const currentContent = draft[activeTab] ?? activeFile?.content ?? "";
  const isDirty = activeTab && draft[activeTab] !== undefined && draft[activeTab] !== activeFile?.content;
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
        body: JSON.stringify({ path: activeTab, content: currentContent }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Save failed.");
      } else {
        const data = await res.json();
        onProjectUpdate?.({ ...project, files: data.files });
        setDraft((d) => { const nd = { ...d }; delete nd[activeTab]; return nd; });
        toast.success(`Saved ${activeTab}`);
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
        setOpenTabs([]);
        setActiveTab(null);
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
      style={{ width: 560, background: 'var(--bg-card)', borderLeft: '1px solid var(--border)' }}
    >
      {/* Top action bar */}
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
          onClick={() => { setShowHistory(!showHistory); setShowFileList(false); }}
          className={`p-1.5 ${showHistory ? "text-cyan-300" : "t-text-mute hover:t-text"}`}
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
        <button
          data-testid="bot-minimize-btn"
          onClick={() => setMinimized(true)}
          className="p-1 t-text-mute hover:t-text"
          title="Minimize"
        >
          <ChevronDown size={13} className="-rotate-90" />
        </button>
        <button data-testid="bot-panel-close" onClick={onClose} className="p-1 t-text-mute hover:t-text" title="Close">
          <X size={13} />
        </button>
      </div>

      {/* Tab bar */}
      {!showHistory && (
        <div
          data-testid="bot-tab-bar"
          className="flex items-center shrink-0 overflow-x-auto"
          style={{ background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)' }}
        >
          {openTabs.map((path) => {
            const fm = fileMeta(path);
            const Icon = fm.icon;
            const active = path === activeTab;
            const dirty = draft[path] !== undefined && draft[path] !== project.files.find((f) => f.path === path)?.content;
            return (
              <button
                key={path}
                data-testid={`tab-${path.replace(/[/.]/g, '-')}`}
                onClick={() => { setActiveTab(path); setShowHistory(false); }}
                className={`group flex items-center gap-1.5 px-3 py-2 text-[11px] shrink-0 transition-colors ${
                  active ? "t-text" : "t-text-mute hover:t-text"
                }`}
                style={{
                  background: active ? 'var(--bg-card)' : 'transparent',
                  borderRight: '1px solid var(--border)',
                  borderTop: active ? '2px solid #22d3ee' : '2px solid transparent',
                  marginTop: -1,
                }}
              >
                <Icon size={11} style={{ color: fm.color }} />
                <span className="truncate max-w-[140px]">{path.split("/").pop()}</span>
                {dirty && <span className="w-1.5 h-1.5 rounded-sm bg-amber-400" />}
                <span
                  role="button"
                  data-testid={`tab-close-${path.replace(/[/.]/g, '-')}`}
                  onClick={(e) => closeTab(e, path)}
                  className="ml-0.5 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity cursor-pointer"
                >
                  <X size={10} />
                </span>
              </button>
            );
          })}

          {/* "All Files" picker (the + button) */}
          <div className="relative shrink-0">
            <button
              data-testid="bot-file-picker-btn"
              onClick={() => setShowFileList(!showFileList)}
              className="flex items-center gap-1 px-3 py-2 text-[11px] t-text-mute hover:t-text"
              title="Open file"
            >
              <Plus size={12} />
            </button>
            {showFileList && (
              <div
                data-testid="bot-file-picker-menu"
                className="absolute right-0 top-full mt-0.5 w-64 rounded-sm shadow-xl z-50 max-h-[300px] overflow-y-auto"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
              >
                <div className="px-2.5 py-1.5 text-[9px] uppercase tracking-wider t-text-dim" style={{ borderBottom: '1px solid var(--border)' }}>
                  Files in this project
                </div>
                {project.files.map((f) => {
                  const fm = fileMeta(f.path);
                  const Icon = fm.icon;
                  const open = openTabs.includes(f.path);
                  return (
                    <button
                      key={f.path}
                      data-testid={`file-list-${f.path.replace(/[/.]/g, '-')}`}
                      onClick={() => openFile(f.path)}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 text-[11px] text-left t-text-mute hover:bg-[var(--bg-card-hover)] hover:t-text transition-colors"
                    >
                      <Icon size={11} style={{ color: fm.color }} />
                      <span className="truncate flex-1">{f.path}</span>
                      {open && <span className="text-[9px] text-cyan-400">open</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex-1" />
          {activeTab && (
            <button
              data-testid="save-file-btn"
              onClick={handleSaveFile}
              disabled={!isDirty || saving}
              className="flex items-center gap-1 px-3 py-1.5 text-[10px] text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-30 transition-colors shrink-0"
              style={{ borderLeft: '1px solid var(--border)' }}
            >
              {saving ? <Loader2 size={9} className="animate-spin" /> : <Save size={9} />}
              Save
            </button>
          )}
        </div>
      )}

      {/* Body */}
      {showHistory ? (
        <CommitHistory project={project} />
      ) : (
        <div className="flex-1 min-h-0">
          {activeFile ? (
            <Editor
              height="100%"
              language={meta.lang}
              value={currentContent}
              theme="vs-dark"
              path={activeTab}
              options={{
                fontSize: 12,
                fontFamily: "'JetBrains Mono', monospace",
                minimap: { enabled: false },
                wordWrap: "on",
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 2,
              }}
              onChange={(value) => setDraft((d) => ({ ...d, [activeTab]: value ?? "" }))}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-center t-text-dim text-[12px]">
              <div>
                <FolderTree size={32} className="mx-auto mb-3 opacity-30" />
                No file open. Click <Plus className="inline" size={11} /> in the tab bar to open one.
              </div>
            </div>
          )}
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

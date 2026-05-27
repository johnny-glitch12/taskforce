import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Folder, Plus, Trash2, ChevronRight, Loader2, Workflow, Download, X, Search,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * MyWorkflowsGrid — Sidebar listing the user's OWN runtime workflows.
 * Includes an "Import from Exchange" button that opens a template browser modal.
 */
export default function MyWorkflowsGrid({ visible, onLoadWorkflow, onLoadTemplate, currentRuntimeId }) {
  const { token } = useAuth();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const refresh = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/workflows`, { headers });
      const data = await res.json();
      setWorkflows(data.workflows || []);
    } catch {
      toast.error("Failed to load your workflows.");
    }
    setLoading(false);
  };

  useEffect(() => { if (visible) refresh(); }, [visible, token]);

  if (!visible) return null;

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!confirm("Delete this workflow?")) return;
    try {
      const res = await fetch(`${API}/api/workflows/${id}`, { method: "DELETE", headers });
      if (res.ok) { toast.success("Deleted."); refresh(); }
    } catch { toast.error("Delete failed."); }
  };

  return (
    <>
      <div
        data-testid="my-workflows-grid"
        className="flex flex-col h-full shrink-0"
        style={{ width: 280, borderRight: '1px solid var(--border)', background: 'var(--bg-card)' }}
      >
        {/* Header */}
        <div className="px-4 py-3 flex items-center gap-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <Folder size={13} className="text-cyan-400" />
          <span className="text-[12px] tracking-wide t-text-sub uppercase">My Workflows</span>
          <span className="ml-auto text-[10px] t-text-dim px-1.5 py-0.5 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
            {workflows.length}
          </span>
        </div>

        {/* Actions */}
        <div className="px-3 py-2 shrink-0 space-y-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
          <button
            data-testid="import-from-exchange-btn"
            onClick={() => setImporting(true)}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300"
          >
            <Download size={11} /> IMPORT FROM EXCHANGE
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={14} className="animate-spin text-cyan-400" />
            </div>
          )}
          {!loading && workflows.length === 0 && (
            <div className="text-center py-6 text-[11px] t-text-dim">
              <Workflow size={20} className="mx-auto mb-2 opacity-40" />
              No workflows yet.<br />Import a template or save your canvas.
            </div>
          )}
          {workflows.map((wf) => {
            const active = wf.id === currentRuntimeId;
            return (
              <div
                key={wf.id}
                data-testid={`my-workflow-${wf.id}`}
                onClick={() => onLoadWorkflow?.(wf)}
                className="rounded-sm p-2.5 cursor-pointer group transition-colors"
                style={{
                  background: active ? 'rgba(34,211,238,0.08)' : 'var(--bg-elevated)',
                  border: `1px solid ${active ? 'rgba(34,211,238,0.3)' : 'var(--border)'}`,
                }}
              >
                <div className="flex items-start gap-2">
                  <div className="w-7 h-7 rounded-sm flex items-center justify-center shrink-0" style={{ background: 'rgba(34,211,238,0.1)' }}>
                    <Workflow size={12} className="text-cyan-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] t-text font-medium truncate">{wf.name}</div>
                    <div className="flex items-center gap-2 mt-1 text-[9px] t-text-dim uppercase tracking-wider">
                      <span>{(wf.nodes || []).length} nodes</span>
                      {wf.source_template && <span className="text-cyan-400">· forked</span>}
                    </div>
                  </div>
                  <button
                    data-testid={`delete-workflow-${wf.id}`}
                    onClick={(e) => handleDelete(wf.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 t-text-dim hover:text-red-400 transition-opacity"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="px-3 py-2 text-[9px] t-text-dim text-center shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
          YOUR PRIVATE WORKSPACE
        </div>
      </div>

      {importing && (
        <ImportTemplateModal
          onClose={() => setImporting(false)}
          onImport={(tpl) => { onLoadTemplate?.(tpl); setImporting(false); refresh(); }}
          token={token}
        />
      )}
    </>
  );
}

/* ────────────────────────────────────────── */
function ImportTemplateModal({ onClose, onImport, token }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("ALL");

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/workflows/templates?limit=400`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => { setTemplates(d.templates || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  const categories = ["ALL", ...new Set(templates.map((t) => t.category).filter(Boolean))];
  const filtered = templates.filter((t) => {
    const matchCat = category === "ALL" || t.category === category;
    const q = search.trim().toLowerCase();
    const matchSearch = !q || (t.name || "").toLowerCase().includes(q) || (t.category || "").toLowerCase().includes(q);
    return matchCat && matchSearch;
  });

  return (
    <div
      data-testid="import-template-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.8)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl rounded-sm flex flex-col"
        style={{ height: '80vh', background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3 flex items-center gap-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <Download size={14} className="text-cyan-400" />
          <span className="text-[13px] tracking-wide t-text uppercase">Import from The Exchange</span>
          <span className="text-[10px] t-text-dim ml-2">{templates.length} TEMPLATES</span>
          <button data-testid="close-import-modal" className="ml-auto p-1 t-text-mute hover:t-text" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2 shrink-0 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="relative flex-1">
            <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 t-text-dim" />
            <input
              data-testid="import-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search templates..."
              className="w-full pl-7 pr-2 py-1.5 text-[12px] rounded-sm focus:outline-none"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }}
            />
          </div>
          <select
            data-testid="import-category-select"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="text-[11px] py-1.5 px-2 rounded-sm"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }}
          >
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Grid */}
        <div className="flex-1 overflow-y-auto p-3">
          {loading && <div className="text-center py-12"><Loader2 size={16} className="animate-spin text-cyan-400 inline" /></div>}
          {!loading && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {filtered.map((tpl) => (
                <div
                  key={tpl.source_hash}
                  data-testid={`import-card-${tpl.source_hash}`}
                  className="rounded-sm p-3 cursor-pointer transition-colors group"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                  onClick={() => onImport(tpl)}
                >
                  <div className="flex items-start gap-2">
                    <div className="w-8 h-8 rounded-sm flex items-center justify-center shrink-0" style={{ background: 'rgba(34,211,238,0.1)' }}>
                      <Workflow size={13} className="text-cyan-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] t-text font-medium truncate">{tpl.name}</div>
                      <div className="text-[10px] t-text-dim truncate mt-0.5">{tpl.description}</div>
                      <div className="flex items-center gap-2 mt-1 text-[9px] uppercase tracking-wider">
                        <span className="t-text-mute">{tpl.node_count} nodes</span>
                        <span className="t-text-dim">·</span>
                        <span className={tpl.complexity === 'high' ? 'text-amber-400' : tpl.complexity === 'med' ? 'text-cyan-400' : 'text-emerald-400'}>
                          {tpl.complexity}
                        </span>
                        {tpl.category && <><span className="t-text-dim">·</span><span className="t-text-dim truncate">{tpl.category}</span></>}
                      </div>
                    </div>
                    <ChevronRight size={11} className="t-text-dim group-hover:text-cyan-400 transition-colors shrink-0 mt-1.5" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

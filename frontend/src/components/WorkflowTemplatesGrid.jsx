import { useState, useEffect } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  Workflow, Search, Download, Play, Layers,
  ChevronRight, Loader2, X,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * WorkflowTemplatesGrid — Sidebar panel that lists translated n8n templates
 * and lets the user fork them into the active canvas via onLoadTemplate(template).
 */
export default function WorkflowTemplatesGrid({ visible, onLoadTemplate }) {
  const { token } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("ALL");
  const [forking, setForking] = useState(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!visible || !token) return;
    const headers = { Authorization: `Bearer ${token}` };
    setLoading(true);
    fetch(`${API}/api/workflows/templates?limit=200`, { headers })
      .then((r) => r.json())
      .then((data) => {
        setTemplates(data.templates || []);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        toast.error("Failed to load templates.");
      });
  }, [visible, token]);

  if (!visible) return null;

  const categories = ["ALL", ...new Set(templates.map((t) => t.category).filter(Boolean))];
  const filtered = templates.filter((t) => {
    const matchCat = activeCategory === "ALL" || t.category === activeCategory;
    const q = search.trim().toLowerCase();
    const matchSearch = !q ||
      (t.name || "").toLowerCase().includes(q) ||
      (t.description || "").toLowerCase().includes(q) ||
      (t.category || "").toLowerCase().includes(q);
    return matchCat && matchSearch;
  });

  const handleFork = async (tpl) => {
    setForking(tpl.source_hash);
    try {
      onLoadTemplate?.(tpl);
      toast.success(`Loaded "${tpl.name}" — ${tpl.node_count} nodes`);
    } catch (e) {
      toast.error("Failed to load template.");
    }
    setForking(null);
  };

  if (collapsed) {
    return (
      <div
        data-testid="templates-grid-collapsed"
        className="flex flex-col items-center gap-2 py-3 px-2"
        style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-card)', width: 44 }}
      >
        <button
          data-testid="expand-templates-btn"
          onClick={() => setCollapsed(false)}
          className="p-2 rounded-sm hover:bg-[var(--bg-card-hover)]"
          title="Show templates"
        >
          <Layers size={16} className="text-cyan-400" />
        </button>
        <span className="text-[9px] tracking-widest t-text-dim writing-vertical-rl" style={{ writingMode: "vertical-rl" }}>
          TEMPLATES
        </span>
      </div>
    );
  }

  return (
    <div
      data-testid="workflow-templates-grid"
      className="flex flex-col h-full shrink-0"
      style={{
        width: 320,
        borderRight: '1px solid var(--border)',
        background: 'var(--bg-card)',
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <Workflow size={14} className="text-cyan-400" />
        <span className="text-[12px] tracking-wide t-text-sub uppercase">Template Armory</span>
        <span className="ml-auto text-[10px] t-text-dim px-1.5 py-0.5 rounded-sm" style={{ background: 'var(--bg-elevated)' }}>
          {templates.length}
        </span>
        <button
          data-testid="collapse-templates-btn"
          onClick={() => setCollapsed(true)}
          className="p-1 rounded-sm hover:bg-[var(--bg-card-hover)]"
        >
          <X size={12} className="t-text-mute" />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="relative">
          <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 t-text-dim" />
          <input
            data-testid="templates-search-input"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search templates..."
            className="w-full pl-7 pr-2 py-1.5 text-[12px] rounded-sm focus:outline-none"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
            }}
          />
        </div>
      </div>

      {/* Categories */}
      {categories.length > 1 && (
        <div className="px-3 py-2 shrink-0 flex flex-wrap gap-1" style={{ borderBottom: '1px solid var(--border)' }}>
          {categories.slice(0, 10).map((cat) => (
            <button
              key={cat}
              data-testid={`category-pill-${cat}`}
              onClick={() => setActiveCategory(cat)}
              className={`text-[10px] tracking-wide px-2 py-0.5 rounded-sm transition-colors ${
                activeCategory === cat
                  ? "bg-cyan-400/15 text-cyan-300 border border-cyan-400/30"
                  : "t-text-mute border border-transparent hover:border-zinc-700"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={16} className="animate-spin text-cyan-400" />
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-8 text-[11px] t-text-dim">
            No templates yet. Run the ingestion script:
            <pre className="mt-2 text-[10px] text-cyan-400">python scripts/ingest_templates.py</pre>
          </div>
        )}
        {filtered.map((tpl) => (
          <div
            key={tpl.source_hash}
            data-testid={`template-card-${tpl.source_hash}`}
            className="rounded-sm p-2.5 transition-colors cursor-pointer group"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            onClick={() => handleFork(tpl)}
          >
            <div className="flex items-start gap-2">
              <div className="w-8 h-8 rounded-sm flex items-center justify-center shrink-0" style={{ background: 'rgba(34,211,238,0.1)' }}>
                <Workflow size={13} className="text-cyan-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[12px] t-text font-medium truncate">{tpl.name}</div>
                <div className="text-[10px] t-text-dim truncate mt-0.5">{tpl.description}</div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[9px] tracking-wider t-text-mute uppercase">
                    {tpl.node_count} nodes
                  </span>
                  <span className="text-[9px] t-text-dim">·</span>
                  <span className={`text-[9px] uppercase tracking-wider ${
                    tpl.complexity === 'high' ? 'text-amber-400' :
                    tpl.complexity === 'med' ? 'text-cyan-400' : 'text-emerald-400'
                  }`}>
                    {tpl.complexity}
                  </span>
                  {tpl.category && (
                    <>
                      <span className="text-[9px] t-text-dim">·</span>
                      <span className="text-[9px] t-text-dim truncate">{tpl.category}</span>
                    </>
                  )}
                </div>
              </div>
              <ChevronRight size={12} className="t-text-dim group-hover:text-cyan-400 transition-colors shrink-0 mt-1" />
            </div>
            {forking === tpl.source_hash && (
              <div className="mt-2 flex items-center gap-1.5 text-[10px] text-cyan-400">
                <Loader2 size={10} className="animate-spin" /> Loading into canvas...
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-3 py-2 text-[9px] t-text-dim text-center shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        NATIVE EXECUTION ENGINE · NO N8N RUNTIME
      </div>
    </div>
  );
}

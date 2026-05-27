import { useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  X, Upload, Video, Image as ImgIcon, DollarSign, Trash2, FileCode2,
  Plus, Loader2, Rocket,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  "messaging", "email", "data", "ai-llm", "automation",
  "scraping", "analytics", "sales", "support", "devops", "other",
];

const STARTER_FILES = [
  { path: "main.py", language: "python", content: "# Entry point\nimport os\n\ndef run(input):\n    return input\n\nif __name__ == '__main__':\n    print(run({}))\n" },
  { path: "requirements.txt", language: "text", content: "" },
  { path: "README.md", language: "markdown", content: "# Bot Name\n\nDescribe what your bot does, its inputs, outputs, and required BYOK credentials.\n" },
];

/**
 * DirectPublishModal — used from The Exchange to upload + publish a finished
 * bot package without going through The Armory builder.
 *
 *   Step 1: meta (name / description / category / tags / pricing)
 *   Step 2: code files (editable; user adds source files of their bot)
 *   Step 3: media (video + photos, same upload pipeline as PublishToExchange)
 */
export default function DirectPublishModal({ open, onClose, onPublished }) {
  const { token } = useAuth();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [listing, setListing] = useState(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    category: "automation",
    tags: "",
    rent_price: 0,
    buy_price: 0,
  });
  const [files, setFiles] = useState(STARTER_FILES);
  const [activeFileIdx, setActiveFileIdx] = useState(0);

  if (!open) return null;

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  const valid1 = form.name.length >= 3 && form.description.length >= 10;
  const valid2 = files.length > 0 && files.every((f) => f.path && f.content.length > 0);

  // ── Step 2: file management ────────────────────────────────
  const addFile = () => {
    const path = prompt("File path (e.g. handlers.py, config.json):");
    if (!path) return;
    setFiles((fs) => [...fs, { path, language: guessLang(path), content: "" }]);
    setActiveFileIdx(files.length);
  };
  const updateFile = (i, content) => setFiles((fs) => fs.map((f, idx) => (idx === i ? { ...f, content } : f)));
  const renameFile = (i, path) => setFiles((fs) => fs.map((f, idx) => (idx === i ? { ...f, path, language: guessLang(path) } : f)));
  const removeFile = (i) => {
    setFiles((fs) => fs.filter((_, idx) => idx !== i));
    if (activeFileIdx >= i) setActiveFileIdx(Math.max(0, activeFileIdx - 1));
  };
  // Drop a real file from disk → add as text content (best-effort UTF-8).
  const ingestUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 200_000) { toast.error("File too large (max 200KB per source file)."); return; }
    const text = await f.text();
    setFiles((fs) => [...fs, { path: f.name, language: guessLang(f.name), content: text }]);
    setActiveFileIdx(files.length);
    e.target.value = "";
  };

  // ── Step 1 → Step 2 (validate + go forward) ────────────────
  const goStep2 = () => { if (valid1) setStep(2); };

  // ── Step 2 → Step 3: hit /exchange/listings/direct ─────────
  const createListing = async () => {
    setBusy(true);
    const tags = form.tags.split(",").map((t) => t.trim()).filter(Boolean);
    try {
      const res = await fetch(`${API}/api/exchange/listings/direct`, {
        method: "POST", headers,
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          category: form.category,
          tags,
          rent_price: parseFloat(form.rent_price) || 0,
          buy_price: parseFloat(form.buy_price) || 0,
          files: files,
          nodes: [],   // direct upload: no canvas graph required
          edges: [],
          language: "python",
        }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        toast.error(e.detail?.[0]?.msg || e.detail || "Publish failed.");
        setBusy(false);
        return;
      }
      const data = await res.json();
      setListing(data);
      setStep(3);
      toast.success("Listing created. Now add screenshots + demo video.");
    } catch {
      toast.error("Publish failed.");
    }
    setBusy(false);
  };

  // ── Step 3: media upload (reuses existing endpoints) ───────
  const handleUpload = async (file, kind) => {
    if (!file || !listing) return;
    setBusy(true);
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    try {
      const res = await fetch(`${API}/api/exchange/listings/${listing.id}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) toast.error(data.detail || "Upload failed.");
      else {
        toast.success(`${kind === "video" ? "Demo video" : "Photo"} uploaded.`);
        const fresh = await fetch(`${API}/api/exchange/listings/${listing.id}`).then((r) => r.json());
        setListing(fresh);
      }
    } catch {
      toast.error("Upload failed.");
    }
    setBusy(false);
  };
  const handleDeleteMedia = async (url) => {
    if (!listing) return;
    await fetch(`${API}/api/exchange/listings/${listing.id}/media?url=${encodeURIComponent(url)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    const fresh = await fetch(`${API}/api/exchange/listings/${listing.id}`).then((r) => r.json());
    setListing(fresh);
  };

  const finish = () => {
    onPublished?.(listing);
    onClose();
    toast.success("Live on The Exchange.");
  };

  // ──────────────────────────────────────────────────────────
  const activeFile = files[activeFileIdx];

  return (
    <div
      data-testid="direct-publish-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.85)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-sm flex flex-col"
        style={{ maxHeight: '92vh', background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3 flex items-center gap-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <Rocket size={14} className="text-cyan-400" />
          <span className="text-[13px] tracking-wide t-text uppercase">
            {step === 1 && "Upload Your Bot · Details"}
            {step === 2 && "Upload Your Bot · Code Files"}
            {step === 3 && "Upload Your Bot · Media + Go Live"}
          </span>
          <span className="text-[10px] t-text-dim ml-2">STEP {step} / 3</span>
          <button data-testid="close-direct-publish" className="ml-auto p-1 t-text-mute hover:t-text" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* ── Step 1: meta ── */}
          {step === 1 && (
            <>
              <Field label="Bot Name *">
                <input data-testid="dp-name" className="config-input" value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Shopify Order Notifier" />
              </Field>
              <Field label="Description * (what does it do?)">
                <textarea data-testid="dp-description" className="config-input" rows={5}
                  value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Inputs / Outputs / Required BYOK credentials / Use case..." />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Category">
                  <select data-testid="dp-category" className="config-input"
                    value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="Tags (comma-separated)">
                  <input data-testid="dp-tags" className="config-input" value={form.tags}
                    onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="shopify, notify, e-com" />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Rent Price ($ / run)">
                  <div className="relative">
                    <DollarSign size={11} className="absolute left-2 top-1/2 -translate-y-1/2 t-text-dim" />
                    <input data-testid="dp-rent-price" type="number" step="0.01" min="0" max="10000"
                      className="config-input pl-7" value={form.rent_price}
                      onChange={(e) => setForm({ ...form, rent_price: e.target.value })} />
                  </div>
                </Field>
                <Field label="Buy Price ($ flat)">
                  <div className="relative">
                    <DollarSign size={11} className="absolute left-2 top-1/2 -translate-y-1/2 t-text-dim" />
                    <input data-testid="dp-buy-price" type="number" step="0.01" min="0" max="100000"
                      className="config-input pl-7" value={form.buy_price}
                      onChange={(e) => setForm({ ...form, buy_price: e.target.value })} />
                  </div>
                </Field>
              </div>
              <div className="text-[10px] t-text-dim">
                Set either to 0 to disable that purchase option. Creators take 80% of revenue.
              </div>
            </>
          )}

          {/* ── Step 2: code files ── */}
          {step === 2 && (
            <div className="flex flex-col gap-2" style={{ minHeight: 360 }}>
              <div className="flex items-center gap-2">
                <span className="text-[10px] t-text-dim uppercase tracking-wider">Source files ({files.length})</span>
                <button data-testid="dp-add-file" onClick={addFile} className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-sm t-text-mute hover:t-text"
                  style={{ border: '1px solid var(--border)' }}>
                  <Plus size={10} /> New file
                </button>
                <label className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-sm cursor-pointer t-text-mute hover:t-text" style={{ border: '1px solid var(--border)' }}>
                  <Upload size={10} /> Upload
                  <input data-testid="dp-upload-file" type="file" className="hidden" accept=".py,.js,.ts,.json,.md,.txt,.yml,.yaml,.sh,.env" onChange={ingestUpload} />
                </label>
              </div>

              {/* file tabs */}
              <div className="flex items-center overflow-x-auto rounded-sm" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                {files.map((f, i) => (
                  <button key={i}
                    data-testid={`dp-tab-${i}`}
                    onClick={() => setActiveFileIdx(i)}
                    className={`group flex items-center gap-1.5 px-3 py-2 text-[11px] shrink-0 transition-colors ${
                      i === activeFileIdx ? "t-text" : "t-text-mute hover:t-text"
                    }`}
                    style={{
                      background: i === activeFileIdx ? 'var(--bg-card)' : 'transparent',
                      borderRight: '1px solid var(--border)',
                      borderTop: i === activeFileIdx ? '2px solid #22d3ee' : '2px solid transparent',
                      marginTop: -1,
                    }}>
                    <FileCode2 size={10} className="text-cyan-400" />
                    <span className="truncate max-w-[140px]">{f.path}</span>
                    {files.length > 1 && (
                      <span role="button" onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                        className="ml-0.5 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity cursor-pointer">
                        <X size={9} />
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* path rename + content editor */}
              {activeFile && (
                <>
                  <input
                    data-testid="dp-rename-file"
                    className="config-input text-[11px]"
                    value={activeFile.path}
                    onChange={(e) => renameFile(activeFileIdx, e.target.value)}
                  />
                  <textarea
                    data-testid="dp-file-content"
                    className="config-input font-mono text-[11px]"
                    style={{ minHeight: 280, lineHeight: 1.45, whiteSpace: 'pre' }}
                    value={activeFile.content}
                    onChange={(e) => updateFile(activeFileIdx, e.target.value)}
                  />
                </>
              )}
              <div className="text-[10px] t-text-dim">
                Paste, type, or drop the source for each file. Renters will get a forkable copy. Max 200KB per file, 20 files total.
              </div>
            </div>
          )}

          {/* ── Step 3: media ── */}
          {step === 3 && listing && (
            <>
              <div className="rounded-sm p-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                <div className="text-[12px] t-text font-medium">{listing.name}</div>
                <div className="text-[10px] t-text-dim mt-1">
                  Status: <span className={listing.status === "published" ? "text-emerald-400" : "text-amber-400"}>{listing.status?.toUpperCase()}</span>
                  · trust {listing.trust_score} · {files.length} files
                </div>
              </div>

              <div>
                <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">Demo Video (1, ≤50MB)</label>
                {listing.video_url ? (
                  <div className="rounded-sm p-2 flex items-center gap-2" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                    <Video size={14} className="text-cyan-400" />
                    <video src={`${API}${listing.video_url}`} controls className="rounded-sm" style={{ maxHeight: 200, maxWidth: '100%' }} />
                    <button data-testid="dp-delete-video" className="ml-auto p-1 text-zinc-600 hover:text-red-400" onClick={() => handleDeleteMedia(listing.video_url)}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                ) : (
                  <label data-testid="dp-upload-video" className="flex items-center justify-center gap-2 py-6 rounded-sm cursor-pointer border-2 border-dashed transition-colors"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-elevated)' }}>
                    <Video size={14} className="text-cyan-400" />
                    <span className="text-[11px] t-text">Click to upload demo video</span>
                    <input type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden"
                      onChange={(e) => handleUpload(e.target.files?.[0], "video")} disabled={busy} />
                  </label>
                )}
              </div>

              <div>
                <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">
                  Screenshots ({(listing.photo_urls || []).length}/5, ≤10MB each)
                </label>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  {(listing.photo_urls || []).map((u) => (
                    <div key={u} className="relative rounded-sm overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                      <img src={`${API}${u}`} alt="" className="w-full h-20 object-cover" />
                      <button onClick={() => handleDeleteMedia(u)} className="absolute top-1 right-1 p-1 rounded-sm" style={{ background: 'rgba(0,0,0,0.7)' }}>
                        <Trash2 size={10} className="text-red-400" />
                      </button>
                    </div>
                  ))}
                </div>
                {(listing.photo_urls || []).length < 5 && (
                  <label data-testid="dp-upload-photo" className="flex items-center justify-center gap-2 py-3 rounded-sm cursor-pointer border-2 border-dashed transition-colors"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-elevated)' }}>
                    <ImgIcon size={14} className="text-cyan-400" />
                    <span className="text-[11px] t-text">Click to upload photo</span>
                    <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                      onChange={(e) => handleUpload(e.target.files?.[0], "photo")} disabled={busy} />
                  </label>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 flex items-center gap-2 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
          <button onClick={onClose} className="px-3 py-2 text-[11px] t-text-mute rounded-sm" style={{ border: '1px solid var(--border)' }}>
            CANCEL
          </button>
          {step > 1 && (
            <button data-testid="dp-back-btn" onClick={() => setStep(step - 1)} className="px-3 py-2 text-[11px] t-text-mute rounded-sm" style={{ border: '1px solid var(--border)' }}>
              ← BACK
            </button>
          )}
          {step === 1 && (
            <button data-testid="dp-next-1" onClick={goStep2} disabled={!valid1}
              className="ml-auto px-4 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50">
              NEXT → CODE
            </button>
          )}
          {step === 2 && (
            <button data-testid="dp-next-2" onClick={createListing} disabled={!valid2 || busy}
              className="ml-auto px-4 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50 flex items-center gap-1.5">
              {busy ? <Loader2 size={11} className="animate-spin" /> : null}
              {busy ? "CREATING..." : "NEXT → MEDIA"}
            </button>
          )}
          {step === 3 && (
            <button data-testid="dp-finish" onClick={finish} className="ml-auto px-4 py-2 text-[11px] font-medium rounded-sm bg-emerald-500 text-black hover:bg-emerald-400">
              GO LIVE
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">{label}</label>
      {children}
    </div>
  );
}

function guessLang(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return ({
    py: "python", js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
    json: "json", md: "markdown", txt: "text", yml: "yaml", yaml: "yaml", sh: "shell", env: "text",
  })[ext] || "text";
}

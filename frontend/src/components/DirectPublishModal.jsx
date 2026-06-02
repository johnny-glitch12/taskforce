import { useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import {
  X, Upload, Video, Image as ImgIcon, DollarSign, Trash2, FileCode2,
  Plus, Loader2, Rocket, Bot, Zap, Brain, Sparkles, Shield, ShoppingBag,
  Mail, MessageCircle, Database, Code, Globe, GitBranch, Calendar, Play,
  Webhook, Cpu, BadgeCheck, CheckCircle2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = [
  "messaging", "email", "data", "ai-llm", "automation",
  "scraping", "analytics", "sales", "support", "devops", "other",
];

const AVATAR_OPTIONS = [
  { name: "Bot",          Icon: Bot },
  { name: "Zap",          Icon: Zap },
  { name: "Rocket",       Icon: Rocket },
  { name: "Brain",        Icon: Brain },
  { name: "Sparkles",     Icon: Sparkles },
  { name: "Shield",       Icon: Shield },
  { name: "ShoppingBag",  Icon: ShoppingBag },
  { name: "Mail",         Icon: Mail },
  { name: "MessageCircle",Icon: MessageCircle },
  { name: "Database",     Icon: Database },
  { name: "Code",         Icon: Code },
  { name: "Globe",        Icon: Globe },
];
const ICON_MAP = Object.fromEntries(AVATAR_OPTIONS.map((a) => [a.name, a.Icon]));

const AVATAR_COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#34d399", "#fbbf24", "#fb7185", "#60a5fa", "#f87171"];

const INTEGRATIONS = [
  "slack", "sendgrid", "gmail", "telegram", "discord", "stripe",
  "notion", "gsheets", "twilio", "github", "openai", "anthropic",
  "instagram", "postgres", "mongodb",
];

const TRIGGER_TYPES = [
  { id: "manual",   label: "Manual",   desc: "Run on demand", Icon: Play },
  { id: "webhook",  label: "Webhook",  desc: "Inbound HTTP",  Icon: Webhook },
  { id: "schedule", label: "Schedule", desc: "Cron timer",    Icon: Calendar },
];

const ENGINES = [
  { id: "gemini-flash", label: "Gemini Flash", desc: "Fast · cheap" },
  { id: "gemini-pro",   label: "Gemini Pro",   desc: "Complex · pricier" },
  { id: "byok-openai",  label: "OpenAI (BYOK)", desc: "Renter's key" },
  { id: "byok-claude",  label: "Claude (BYOK)", desc: "Renter's key" },
];

const STARTER_FILES = [
  { path: "main.py", language: "python", content: "# Entry point\nimport os\n\ndef run(input):\n    return input\n\nif __name__ == '__main__':\n    print(run({}))\n" },
  { path: "requirements.txt", language: "text", content: "" },
  { path: "README.md", language: "markdown", content: "# Bot Name\n\nDescribe what your bot does, its inputs, outputs, and required BYOK credentials.\n" },
];

/**
 * DirectPublishModal — Cyber-luxury 3-step bot uploader for The Exchange.
 *
 *   Step 1: Marketplace metadata WITH live-preview card on the right.
 *           Fields: avatar (icon + color), name, description, category, tags,
 *                   required integrations (badge multi-select), trigger type,
 *                   engine, rent/buy pricing with live 80% take-home calc.
 *   Step 2: Code files (VS-Code tabs + disk ingest).
 *   Step 3: Media (video + photos).
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
    avatar_icon: "Bot",
    avatar_color: "#22d3ee",
    required_integrations: [],
    trigger_type: "manual",
    engine: "gemini-flash",
  });
  const [files, setFiles] = useState(STARTER_FILES);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [avatarFile, setAvatarFile] = useState(null);          // File picked at Step 1
  const [avatarPreview, setAvatarPreview] = useState(null);    // local blob URL

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
          avatar_icon: form.avatar_icon,
          avatar_color: form.avatar_color,
          required_integrations: form.required_integrations,
          trigger_type: form.trigger_type,
          engine: form.engine,
          files: files,
          nodes: [],
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
      // If a custom avatar photo was picked in Step 1, upload it now before stepping forward.
      if (avatarFile) {
        const fd = new FormData();
        fd.append("kind", "avatar");
        fd.append("file", avatarFile);
        const up = await fetch(`${API}/api/exchange/listings/${data.id}/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (up.ok) {
          const fresh = await fetch(`${API}/api/exchange/listings/${data.id}`).then((r) => r.json());
          setListing(fresh);
        } else {
          toast.error("Avatar upload failed (continuing anyway).");
        }
      }
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
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        className={`w-full ${step === 1 ? 'max-w-6xl' : 'max-w-3xl'} rounded-sm flex flex-col`}
        style={{ maxHeight: '94vh', background: 'var(--bg-card)', border: '1px solid var(--border)' }}
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
          {/* ── Step 1: meta with live preview ── */}
          {step === 1 && (
            <DetailsStep
              form={form}
              setForm={setForm}
              avatarPreview={avatarPreview}
              onPickAvatar={(file) => {
                if (!file) {
                  setAvatarFile(null);
                  if (avatarPreview) URL.revokeObjectURL(avatarPreview);
                  setAvatarPreview(null);
                  return;
                }
                if (file.size > 2 * 1024 * 1024) { toast.error("Avatar must be ≤ 2MB."); return; }
                if (avatarPreview) URL.revokeObjectURL(avatarPreview);
                setAvatarFile(file);
                setAvatarPreview(URL.createObjectURL(file));
              }}
            />
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

/* ──────────────────────────────────────────────────────────────────────
   Step 1 — DetailsStep: two-column live-preview marketplace metadata form
   ────────────────────────────────────────────────────────────────────── */
function DetailsStep({ form, setForm, avatarPreview, onPickAvatar }) {
  const update = (patch) => setForm({ ...form, ...patch });
  const toggleIntegration = (id) => {
    const cur = form.required_integrations || [];
    update({ required_integrations: cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id] });
  };

  const rent = parseFloat(form.rent_price) || 0;
  const buy = parseFloat(form.buy_price) || 0;
  const rentTakeHome = (rent * 0.8).toFixed(2);
  const buyTakeHome  = (buy  * 0.8).toFixed(2);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 lg:gap-8">
      {/* ── LEFT — form ── */}
      <div className="space-y-5 min-w-0">

        {/* Avatar picker */}
        <div>
          <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-2 flex items-center gap-2">
            Bot Avatar
            <span className="t-text-mute normal-case tracking-normal">— pick an icon or upload a custom photo</span>
          </label>

          {/* Custom photo slot + icon grid */}
          <div className="flex items-stretch gap-2 mb-3">
            {/* Custom photo tile */}
            <label
              data-testid="dp-avatar-photo-upload"
              className="relative shrink-0 w-14 h-14 rounded-sm flex items-center justify-center cursor-pointer overflow-hidden transition-all"
              style={{
                background: avatarPreview ? `${form.avatar_color}10` : 'var(--bg-elevated)',
                border: `1px dashed ${avatarPreview ? form.avatar_color : 'var(--border)'}`,
                boxShadow: avatarPreview ? `0 0 0 2px ${form.avatar_color}30, 0 0 14px ${form.avatar_color}40` : 'none',
              }}
              title="Upload custom photo (max 2MB)"
            >
              {avatarPreview ? (
                <>
                  <img src={avatarPreview} alt="avatar" className="w-full h-full object-cover" />
                  <button
                    data-testid="dp-avatar-photo-remove"
                    onClick={(e) => { e.preventDefault(); onPickAvatar(null); }}
                    className="absolute top-0 right-0 p-0.5 rounded-bl-sm"
                    style={{ background: 'rgba(0,0,0,0.7)' }}
                  >
                    <Trash2 size={9} className="text-red-400" />
                  </button>
                </>
              ) : (
                <div className="flex flex-col items-center gap-0.5">
                  <Upload size={12} className="t-text-mute" />
                  <span className="text-[8px] uppercase tracking-wider t-text-dim font-mono">UPLOAD</span>
                </div>
              )}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => onPickAvatar(e.target.files?.[0])}
              />
            </label>

            {/* Icon grid */}
            <div className="grid grid-cols-6 sm:grid-cols-12 gap-1.5 flex-1">
              {AVATAR_OPTIONS.map(({ name, Icon }) => {
                const active = !avatarPreview && form.avatar_icon === name;
                return (
                  <button
                    key={name}
                    data-testid={`dp-avatar-${name}`}
                    onClick={() => update({ avatar_icon: name })}
                    className="aspect-square rounded-sm flex items-center justify-center transition-all"
                    style={{
                      background: active ? `${form.avatar_color}1f` : 'var(--bg-elevated)',
                      border: `1px solid ${active ? form.avatar_color : 'var(--border)'}`,
                      boxShadow: active ? `0 0 0 2px ${form.avatar_color}30, 0 0 12px ${form.avatar_color}40` : 'none',
                      opacity: avatarPreview ? 0.45 : 1,
                    }}
                  >
                    <Icon size={14} style={{ color: active ? form.avatar_color : 'var(--text-mute)' }} />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {AVATAR_COLORS.map((c) => {
              const active = form.avatar_color === c;
              return (
                <button
                  key={c}
                  data-testid={`dp-color-${c.replace('#','')}`}
                  onClick={() => update({ avatar_color: c })}
                  className="w-5 h-5 rounded-full transition-all"
                  style={{ background: c, boxShadow: active ? `0 0 0 2px var(--bg-card), 0 0 0 4px ${c}` : 'none' }}
                />
              );
            })}
            {avatarPreview && (
              <span className="ml-2 text-[9px] uppercase tracking-widest t-text-dim font-mono">
                Custom photo active · color tints accents only
              </span>
            )}
          </div>
        </div>

        <CyberField label="Bot Name *">
          <input
            data-testid="dp-name"
            className="cy-input"
            value={form.name}
            onChange={(e) => update({ name: e.target.value })}
            placeholder="e.g. Shopify Order Notifier"
            style={{ '--glow': form.avatar_color }}
          />
        </CyberField>

        <CyberField label="Description * (what does it do?)">
          <textarea
            data-testid="dp-description"
            rows={4}
            className="cy-input"
            value={form.description}
            onChange={(e) => update({ description: e.target.value })}
            placeholder="Inputs · Outputs · Required BYOK · Use case..."
            style={{ '--glow': form.avatar_color }}
          />
        </CyberField>

        <div className="grid grid-cols-2 gap-3">
          <CyberField label="Category">
            <select
              data-testid="dp-category"
              className="cy-input"
              value={form.category}
              onChange={(e) => update({ category: e.target.value })}
              style={{ '--glow': form.avatar_color }}
            >
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </CyberField>
          <CyberField label="Tags (comma-separated)">
            <input
              data-testid="dp-tags"
              className="cy-input"
              value={form.tags}
              onChange={(e) => update({ tags: e.target.value })}
              placeholder="shopify, notify, e-com"
              style={{ '--glow': form.avatar_color }}
            />
          </CyberField>
        </div>

        {/* Required integrations */}
        <div>
          <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-2">
            Required Integrations
            <span className="ml-1.5 t-text-mute normal-case tracking-normal">— renters need these BYOK keys</span>
          </label>
          <div className="flex flex-wrap gap-1.5">
            {INTEGRATIONS.map((s) => {
              const active = (form.required_integrations || []).includes(s);
              return (
                <button
                  key={s}
                  data-testid={`dp-int-${s}`}
                  onClick={() => toggleIntegration(s)}
                  className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-mono rounded-sm transition-all flex items-center gap-1"
                  style={{
                    background: active ? `${form.avatar_color}1f` : 'var(--bg-elevated)',
                    border: `1px solid ${active ? form.avatar_color : 'var(--border)'}`,
                    color: active ? form.avatar_color : 'var(--text-mute)',
                  }}
                >
                  {active && <CheckCircle2 size={9} />}
                  {s}
                </button>
              );
            })}
          </div>
        </div>

        {/* Trigger Type segmented */}
        <div>
          <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-2">Trigger Type</label>
          <div className="grid grid-cols-3 gap-2">
            {TRIGGER_TYPES.map(({ id, label, desc, Icon }) => {
              const active = form.trigger_type === id;
              return (
                <button
                  key={id}
                  data-testid={`dp-trigger-${id}`}
                  onClick={() => update({ trigger_type: id })}
                  className="p-3 rounded-sm text-left transition-all flex items-start gap-2"
                  style={{
                    background: active ? `${form.avatar_color}10` : 'var(--bg-elevated)',
                    border: `1px solid ${active ? form.avatar_color : 'var(--border)'}`,
                    boxShadow: active ? `0 0 0 1px ${form.avatar_color}40 inset` : 'none',
                  }}
                >
                  <Icon size={14} style={{ color: active ? form.avatar_color : 'var(--text-mute)' }} />
                  <div className="min-w-0">
                    <div className="text-[11px] t-text font-medium uppercase tracking-wider">{label}</div>
                    <div className="text-[9px] t-text-dim mt-0.5">{desc}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Engine */}
        <div>
          <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-2">Core Engine</label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {ENGINES.map(({ id, label, desc }) => {
              const active = form.engine === id;
              return (
                <button
                  key={id}
                  data-testid={`dp-engine-${id}`}
                  onClick={() => update({ engine: id })}
                  className="p-2.5 rounded-sm text-left transition-all"
                  style={{
                    background: active ? `${form.avatar_color}10` : 'var(--bg-elevated)',
                    border: `1px solid ${active ? form.avatar_color : 'var(--border)'}`,
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    <Cpu size={11} style={{ color: active ? form.avatar_color : 'var(--text-mute)' }} />
                    <span className="text-[10px] t-text font-medium uppercase tracking-wider">{label}</span>
                  </div>
                  <div className="text-[9px] t-text-dim mt-0.5">{desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Pricing */}
        <div>
          <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-2">Pricing</label>
          <div className="grid grid-cols-2 gap-3">
            <PriceInput
              dataTestId="dp-rent-price"
              label="Rent / run"
              value={form.rent_price}
              onChange={(v) => update({ rent_price: v })}
              takeHome={rentTakeHome}
              suffix="/run"
              color={form.avatar_color}
            />
            <PriceInput
              dataTestId="dp-buy-price"
              label="Buy (flat)"
              value={form.buy_price}
              onChange={(v) => update({ buy_price: v })}
              takeHome={buyTakeHome}
              suffix="one-time"
              color={form.avatar_color}
            />
          </div>
          <div className="text-[10px] t-text-dim mt-2 flex items-center gap-1.5">
            <BadgeCheck size={10} className="text-emerald-400" />
            Set either to 0 to disable that purchase option · Platform takes 20%, you keep 80%
          </div>
        </div>
      </div>

      {/* ── RIGHT — live preview card ── */}
      <div className="lg:sticky lg:top-2 self-start">
        <LivePreviewCard form={form} avatarPreview={avatarPreview} />
      </div>

      {/* scoped styling for cyber inputs (glow on focus, glass) */}
      <style>{`
        .cy-input {
          width: 100%;
          padding: 9px 12px;
          font-size: 12px;
          color: var(--text);
          background: rgba(255,255,255,0.02);
          backdrop-filter: blur(6px);
          border: 1px solid var(--border);
          border-radius: 2px;
          transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
          font-family: inherit;
        }
        .cy-input:focus {
          outline: none;
          border-color: var(--glow, #22d3ee);
          box-shadow: 0 0 0 1px var(--glow, #22d3ee), 0 0 18px 0 color-mix(in srgb, var(--glow, #22d3ee) 35%, transparent);
          background: rgba(255,255,255,0.04);
        }
        textarea.cy-input { resize: vertical; min-height: 100px; line-height: 1.5; }
        select.cy-input { appearance: none; background-image: linear-gradient(45deg, transparent 50%, var(--text-mute) 50%), linear-gradient(135deg, var(--text-mute) 50%, transparent 50%); background-position: calc(100% - 14px) 14px, calc(100% - 9px) 14px; background-size: 5px 5px, 5px 5px; background-repeat: no-repeat; padding-right: 28px; }
        .cy-price-input { font-family: 'JetBrains Mono','SF Mono',Menlo,monospace; letter-spacing: 0.02em; font-size: 14px; }
      `}</style>
    </div>
  );
}

function CyberField({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function PriceInput({ dataTestId, label, value, onChange, takeHome, suffix, color }) {
  return (
    <div>
      <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1.5">{label}</label>
      <div className="relative">
        <DollarSign size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 t-text-dim" />
        <input
          data-testid={dataTestId}
          type="number" step="0.01" min="0" max="100000"
          className="cy-input cy-price-input pl-7"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{ '--glow': color }}
        />
      </div>
      <div className="text-[10px] t-text-dim mt-1 font-mono flex items-center gap-1">
        <span style={{ color }}>${takeHome}</span> to you · {suffix}
      </div>
    </div>
  );
}

function LivePreviewCard({ form, avatarPreview }) {
  const Icon = ICON_MAP[form.avatar_icon] || Bot;
  const tagList = form.tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 4);
  const trigger = TRIGGER_TYPES.find((t) => t.id === form.trigger_type) || TRIGGER_TYPES[0];
  const TriggerIcon = trigger.Icon;
  const engine = ENGINES.find((e) => e.id === form.engine);
  const rent = parseFloat(form.rent_price) || 0;
  const buy = parseFloat(form.buy_price) || 0;
  const intList = (form.required_integrations || []).slice(0, 6);

  return (
    <div>
      <div className="text-[10px] tracking-widest uppercase t-text-dim mb-2 flex items-center gap-1.5">
        <Sparkles size={10} className="text-cyan-400" />
        Live Marketplace Preview
      </div>
      <div
        data-testid="dp-preview-card"
        className="rounded-sm overflow-hidden"
        style={{
          background: 'var(--bg-elevated)',
          border: `1px solid ${form.avatar_color}33`,
          boxShadow: `0 0 32px -8px ${form.avatar_color}33`,
        }}
      >
        {/* gradient header */}
        <div
          className="h-20 relative"
          style={{
            background: `linear-gradient(135deg, ${form.avatar_color}30 0%, transparent 60%), radial-gradient(circle at 80% 20%, ${form.avatar_color}25, transparent 50%)`,
          }}
        >
          <div className="absolute -bottom-5 left-3 w-12 h-12 rounded-sm flex items-center justify-center overflow-hidden"
            style={{
              background: 'var(--bg-card)',
              border: `1px solid ${form.avatar_color}`,
              boxShadow: `0 0 18px ${form.avatar_color}55`,
            }}
          >
            {avatarPreview ? (
              <img src={avatarPreview} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <Icon size={20} style={{ color: form.avatar_color }} />
            )}
          </div>
        </div>

        <div className="pt-7 px-3 pb-3 space-y-2">
          <div>
            <div className="text-[13px] t-text font-semibold truncate" data-testid="dp-preview-name">
              {form.name || "Untitled Bot"}
            </div>
            <div className="text-[10px] t-text-dim uppercase tracking-widest font-mono">
              {form.category}
              {tagList.length > 0 && <span> · {tagList.join(" · ")}</span>}
            </div>
          </div>

          <p className="text-[11px] t-text-mute leading-relaxed line-clamp-3 min-h-[44px]">
            {form.description || "Description will appear here as you type."}
          </p>

          {/* trigger + engine row */}
          <div className="flex items-center gap-2 pt-1.5" style={{ borderTop: '1px solid var(--border)' }}>
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider t-text-mute font-mono">
              <TriggerIcon size={9} style={{ color: form.avatar_color }} /> {trigger.label}
            </span>
            <span className="text-[9px] t-text-dim">·</span>
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider t-text-mute font-mono">
              <Cpu size={9} style={{ color: form.avatar_color }} /> {engine?.label}
            </span>
          </div>

          {/* required integrations */}
          {intList.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1.5">
              {intList.map((s) => (
                <span key={s} className="text-[9px] uppercase tracking-wider font-mono px-1.5 py-0.5 rounded-sm"
                  style={{ background: 'var(--bg-card)', color: 'var(--text-mute)', border: '1px solid var(--border)' }}>
                  {s}
                </span>
              ))}
              {(form.required_integrations || []).length > 6 && (
                <span className="text-[9px] t-text-dim">+{form.required_integrations.length - 6}</span>
              )}
            </div>
          )}

          {/* pricing */}
          <div className="flex items-end justify-between pt-2 mt-1.5" style={{ borderTop: '1px solid var(--border)' }}>
            <div>
              <div className="text-[9px] uppercase tracking-widest t-text-dim font-mono">Pricing</div>
              <div className="font-mono text-[12px] t-text mt-0.5">
                {rent > 0 && <span>${rent.toFixed(2)}<span className="t-text-dim text-[10px]">/run</span></span>}
                {rent > 0 && buy > 0 && <span className="t-text-dim mx-1">·</span>}
                {buy > 0 && <span>${buy.toFixed(2)}<span className="t-text-dim text-[10px]"> flat</span></span>}
                {rent === 0 && buy === 0 && <span className="t-text-dim text-[10px]">— free —</span>}
              </div>
            </div>
            <button
              disabled
              className="px-2.5 py-1.5 text-[10px] uppercase tracking-widest font-mono rounded-sm font-medium"
              style={{ background: form.avatar_color, color: '#000', opacity: 0.9 }}
            >
              Deploy
            </button>
          </div>
        </div>
      </div>
      <div className="text-[9px] t-text-dim mt-2 text-center uppercase tracking-widest">
        How buyers will see your bot
      </div>
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

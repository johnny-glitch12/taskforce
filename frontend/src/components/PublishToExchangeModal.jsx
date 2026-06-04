import { useState } from "react";
import { useAuth } from "@/App";
import { toast } from "sonner";
import { X, Upload, Video, Image as ImgIcon, DollarSign, Tag, Trash2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const CATEGORIES = [
  "messaging", "email", "data", "ai-llm", "automation",
  "scraping", "analytics", "sales", "support", "devops", "other",
];

/**
 * PublishToExchangeModal — opens from canvas header.
 * Step 1: meta (name/desc/category/tags/pricing)
 * Step 2: upload video + photos (multipart)
 */
export default function PublishToExchangeModal({ open, onClose, runtimeWorkflowId, workflowName, onPublished }) {
  const { token } = useAuth();
  const [step, setStep] = useState(1);
  const [listing, setListing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: workflowName || "",
    description: "",
    category: "automation",
    tags: "",
    rent_price: 0,
    buy_price: 0,
  });

  if (!open) return null;

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const handlePublish = async () => {
    if (!runtimeWorkflowId) {
      toast.error("Save the workflow first.");
      return;
    }
    setBusy(true);
    const tags = form.tags.split(",").map((t) => t.trim()).filter(Boolean);
    try {
      const res = await fetch(`${API}/api/exchange/listings`, {
        method: "POST", headers,
        body: JSON.stringify({
          workflow_id: runtimeWorkflowId,
          name: form.name,
          description: form.description,
          category: form.category,
          tags,
          rent_price: parseFloat(form.rent_price) || 0,
          buy_price: parseFloat(form.buy_price) || 0,
        }),
      });
      if (!res.ok) {
        const e = await res.json();
        toast.error(e.detail?.[0]?.msg || e.detail || "Publish failed.");
        setBusy(false);
        return;
      }
      const data = await res.json();
      setListing(data);
      setStep(2);
      toast.success("Listing created. Add media to publish.");
    } catch {
      toast.error("Publish failed.");
    }
    setBusy(false);
  };

  const handleUpload = async (file, kind) => {
    if (!file || !listing) return;
    setBusy(true);
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    try {
      const res = await fetch(`${API}/api/exchange/listings/${listing.id}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }, // no content-type for multipart
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.detail || "Upload failed.");
      } else {
        toast.success(`${kind === "video" ? "Demo video" : "Photo"} uploaded.`);
        // Refresh listing
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

  return (
    <div
      data-testid="publish-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.85)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-sm flex flex-col"
        style={{ maxHeight: '90vh', background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-3 flex items-center gap-3 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <Upload size={14} className="text-cyan-400" />
          <span className="text-[13px] tracking-wide t-text uppercase">
            {step === 1 ? "Publish to The Exchange" : "Add Media + Go Live"}
          </span>
          <span className="text-[10px] t-text-dim ml-2">STEP {step} / 2</span>
          <button data-testid="close-publish-modal" className="ml-auto p-1 t-text-mute hover:t-text" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {step === 1 && (
            <>
              <Field label="Listing Name *">
                <input data-testid="listing-name" className="config-input" value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Slack Notification Bot" />
              </Field>
              <Field label="Description * (markdown supported)">
                <textarea data-testid="listing-description" className="config-input" rows={5}
                  value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="What does it do? Inputs / Outputs / Required BYOK credentials..." />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Category">
                  <select data-testid="listing-category" className="config-input"
                    value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="Tags (comma-separated)">
                  <input data-testid="listing-tags" className="config-input" value={form.tags}
                    onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="slack, notify, automation" />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Rent Price ($ / run)">
                  <div className="relative">
                    <DollarSign size={11} className="absolute left-2 top-1/2 -translate-y-1/2 t-text-dim" />
                    <input data-testid="listing-rent-price" type="number" step="0.01" min="0" max="10000"
                      className="config-input pl-7" value={form.rent_price}
                      onChange={(e) => setForm({ ...form, rent_price: e.target.value })} />
                  </div>
                </Field>
                <Field label="Buy Price ($ flat)">
                  <div className="relative">
                    <DollarSign size={11} className="absolute left-2 top-1/2 -translate-y-1/2 t-text-dim" />
                    <input data-testid="listing-buy-price" type="number" step="0.01" min="0" max="100000"
                      className="config-input pl-7" value={form.buy_price}
                      onChange={(e) => setForm({ ...form, buy_price: e.target.value })} />
                  </div>
                </Field>
              </div>
              <div className="text-[10px] t-text-dim">
                Set either to 0 to disable that purchase option. Operators take 70% of all revenue.
              </div>
            </>
          )}

          {step === 2 && listing && (
            <>
              <div className="rounded-sm p-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                <div className="text-[12px] t-text font-medium">{listing.name}</div>
                <div className="text-[10px] t-text-dim mt-1">
                  Status: <span className={listing.status === "published" ? "text-emerald-400" : "text-amber-400"}>{listing.status?.toUpperCase()}</span>
                  · trust {listing.trust_score} · {listing.node_count} nodes
                </div>
              </div>

              {/* Video upload */}
              <div>
                <label className="block text-[10px] tracking-widest uppercase t-text-dim mb-1">Demo Video (1, ≤50MB)</label>
                {listing.video_url ? (
                  <div className="rounded-sm p-2 flex items-center gap-2" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                    <Video size={14} className="text-cyan-400" />
                    <video src={`${API}${listing.video_url}`} controls className="rounded-sm" style={{ maxHeight: 200, maxWidth: '100%' }} />
                    <button data-testid="delete-video-btn" className="ml-auto p-1 text-zinc-600 hover:text-red-400" onClick={() => handleDeleteMedia(listing.video_url)}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                ) : (
                  <label
                    data-testid="upload-video-btn"
                    className="flex items-center justify-center gap-2 py-6 rounded-sm cursor-pointer border-2 border-dashed transition-colors"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-elevated)' }}
                  >
                    <Video size={14} className="text-cyan-400" />
                    <span className="text-[11px] t-text">Click to upload demo video</span>
                    <input type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden"
                      onChange={(e) => handleUpload(e.target.files?.[0], "video")} disabled={busy} />
                  </label>
                )}
              </div>

              {/* Photo upload */}
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
                  <label
                    data-testid="upload-photo-btn"
                    className="flex items-center justify-center gap-2 py-3 rounded-sm cursor-pointer border-2 border-dashed transition-colors"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-elevated)' }}
                  >
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
          {step === 1 && (
            <button
              data-testid="next-step-btn"
              onClick={handlePublish}
              disabled={busy || !form.name || form.description.length < 10}
              className="ml-auto px-4 py-2 text-[11px] font-medium rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50"
            >
              {busy ? "CREATING..." : "NEXT → ADD MEDIA"}
            </button>
          )}
          {step === 2 && (
            <button
              data-testid="finish-publish-btn"
              onClick={finish}
              className="ml-auto px-4 py-2 text-[11px] font-medium rounded-sm bg-emerald-500 text-black hover:bg-emerald-400"
            >
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

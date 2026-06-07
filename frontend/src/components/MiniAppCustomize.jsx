/**
 * MiniAppCustomize — modal that lets the mini-app owner edit branding (colors,
 * logo, display name, border radius, show/hide chrome) and grab the embed
 * snippet + QR code for the public URL.
 *
 * Backend contract:
 *   GET   /api/apps/{slug}/theme    →  {theme, is_public, slug, name}
 *   PATCH /api/apps/{slug}/theme    →  {ok, theme}     (partial updates, hex-validated)
 *
 * The render endpoint (/api/apps/{slug}/render) injects --tf-primary, --tf-accent,
 * --tf-bg, --tf-text, --tf-radius as CSS custom properties so AI-generated apps
 * inherit branding automatically. A thin branded header bar appears when
 * `show_branding=true` and is suppressed when iframed with `?embed=1`.
 */
import { useEffect, useRef, useState } from "react";
import { X, Loader2, Save, Copy, QrCode, Globe, Lock, RotateCcw, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import QRCode from "qrcode";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";

// Same constants as backend DEFAULT_THEME — kept in sync visually only.
const DEFAULTS = {
  display_name: "",
  logo_url: "",
  primary: "#22d3ee",
  accent: "#a855f7",
  background: "#0a0a0a",
  text: "#e5e7eb",
  border_radius: "rounded",
  show_branding: true,
};

// Six curated palettes power-users can apply with one click. Each is a
// hand-tuned set of {primary, accent, background, text} chosen to look good
// together against the iframe's default sans-serif type.
const PRESETS = [
  { id: "cyber", name: "Cyber Cyan", primary: "#22d3ee", accent: "#a855f7", background: "#0a0a0a", text: "#e5e7eb" },
  { id: "sunset", name: "Sunset Glow", primary: "#fb923c", accent: "#f43f5e", background: "#1a0f0a", text: "#fef3c7" },
  { id: "forest", name: "Forest", primary: "#10b981", accent: "#34d399", background: "#0a1410", text: "#d1fae5" },
  { id: "candy", name: "Candy Pop", primary: "#ec4899", accent: "#fbbf24", background: "#1a0a14", text: "#fce7f3" },
  { id: "ice", name: "Arctic Ice", primary: "#60a5fa", accent: "#a78bfa", background: "#fafafa", text: "#0a0a0a" },
  { id: "mono", name: "Mono Paper", primary: "#525252", accent: "#171717", background: "#fafafa", text: "#171717" },
];

export default function MiniAppCustomize({ slug, onClose, onSaved }) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [theme, setTheme] = useState(DEFAULTS);
  const [isPublic, setIsPublic] = useState(false);
  const [name, setName] = useState("");
  const [qrDataUrl, setQrDataUrl] = useState(null);
  const [tab, setTab] = useState("branding"); // branding | embed
  const fileInputRef = useRef(null);

  // Public URL for this app (relative to the current origin — works for both
  // localhost dev and the deployed taskforce.run domain).
  const publicUrl = typeof window !== "undefined" ? `${window.location.origin}/apps/${slug}` : "";
  const embedUrl = typeof window !== "undefined" ? `${window.location.origin}/api/apps/${slug}/render?embed=1` : "";
  const embedSnippet = `<iframe\n  src="${embedUrl}"\n  width="100%"\n  height="640"\n  frameborder="0"\n  style="border:1px solid #222; border-radius:8px;"\n  title="${name || "Mini app"}"\n></iframe>`;

  // Fetch the current theme on open.
  useEffect(() => {
    if (!token || !slug) return;
    setLoading(true);
    fetch(`${API}/api/apps/${slug}/theme`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setTheme({ ...DEFAULTS, ...(d.theme || {}) });
        setIsPublic(!!d.is_public);
        setName(d.name || "");
      })
      .catch((e) => toast.error(`Could not load theme: ${e.message}`))
      .finally(() => setLoading(false));
  }, [token, slug]);

  // Generate QR whenever the public URL is available. Re-generated only if
  // the URL changes (which it doesn't during the modal's lifetime, so once).
  useEffect(() => {
    if (!publicUrl) return;
    QRCode.toDataURL(publicUrl, {
      width: 200,
      margin: 2,
      color: { dark: "#0a0a0a", light: "#ffffff" },
    })
      .then(setQrDataUrl)
      .catch(() => setQrDataUrl(null));
  }, [publicUrl]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await fetch(`${API}/api/apps/${slug}/theme`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(theme),
      });
      const j = await r.json();
      if (!r.ok) {
        const msg = Array.isArray(j.detail) ? j.detail[0]?.msg : (j.detail || `HTTP ${r.status}`);
        toast.error(msg);
        return;
      }
      toast.success("Branding saved");
      onSaved?.(j.theme);
    } catch {
      toast.error("Network error");
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = (p) => {
    setTheme((t) => ({ ...t, primary: p.primary, accent: p.accent, background: p.background, text: p.text }));
  };

  const resetToDefaults = () => setTheme({ ...DEFAULTS });

  const copy = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied`);
    } catch {
      toast.error("Copy failed — select and copy manually");
    }
  };

  const downloadQR = () => {
    if (!qrDataUrl) return;
    const a = document.createElement("a");
    a.href = qrDataUrl;
    a.download = `${slug}-qr.png`;
    a.click();
  };

  // Live-preview style block: applies the user's color picks to a small swatch
  // inside the modal so they see the impact before saving.
  const previewStyle = {
    background: theme.background,
    color: theme.text,
    borderColor: theme.primary,
  };

  return (
    <div
      data-testid="customize-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[760px] max-h-[88vh] overflow-hidden flex flex-col"
        style={{ background: "var(--bg-panel, #0f0f10)", border: "1px solid var(--border, #222)", borderRadius: 8 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: "var(--border, #222)" }}>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-cyan-300">App Customization</div>
            <div className="text-[13px] font-mono text-zinc-200 mt-0.5">{name || slug}</div>
          </div>
          <button
            data-testid="customize-close"
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-sm text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
          >
            <X size={14} />
          </button>
        </div>

        {/* Tab strip */}
        <div className="flex gap-1 px-5 pt-3" style={{ borderBottom: "1px solid var(--border, #222)" }}>
          {[
            { id: "branding", label: "Branding" },
            { id: "embed", label: "Share & Embed" },
          ].map((t) => (
            <button
              key={t.id}
              data-testid={`customize-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] border-b-2 -mb-px transition-colors ${
                tab === t.id ? "text-cyan-300 border-cyan-400" : "text-zinc-500 border-transparent hover:text-zinc-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-zinc-500">
              <Loader2 size={16} className="animate-spin mr-2" /> Loading…
            </div>
          ) : tab === "branding" ? (
            <BrandingTab theme={theme} setTheme={setTheme} previewStyle={previewStyle} fileInputRef={fileInputRef} />
          ) : (
            <EmbedTab
              publicUrl={publicUrl}
              embedUrl={embedUrl}
              embedSnippet={embedSnippet}
              qrDataUrl={qrDataUrl}
              isPublic={isPublic}
              copy={copy}
              downloadQR={downloadQR}
            />
          )}
        </div>

        {/* Footer (only on branding tab — embed tab has no mutable state to save) */}
        {tab === "branding" && !loading && (
          <div
            className="flex items-center justify-between gap-2 px-5 py-3 border-t"
            style={{ borderColor: "var(--border, #222)" }}
          >
            <button
              data-testid="customize-reset"
              onClick={resetToDefaults}
              className="inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-300"
            >
              <RotateCcw size={11} /> Reset to defaults
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                data-testid="customize-save"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-sm bg-cyan-400 text-black text-[10px] font-bold uppercase tracking-[0.15em] font-mono disabled:opacity-50"
              >
                {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                Save changes
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BrandingTab({ theme, setTheme, previewStyle, fileInputRef }) {
  const update = (k, v) => setTheme((t) => ({ ...t, [k]: v }));

  return (
    <div className="space-y-5">
      {/* Live preview strip */}
      <div className="rounded-sm border" style={previewStyle}>
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{ borderBottom: `1px solid ${theme.primary}30` }}
        >
          {theme.logo_url ? (
            <img alt="" src={theme.logo_url} className="w-4 h-4 object-contain rounded-sm" onError={(e) => (e.currentTarget.style.display = "none")} />
          ) : (
            <div className="w-2 h-2" style={{ background: theme.primary }} />
          )}
          <span className="text-[11px] font-mono uppercase tracking-[0.15em] font-bold" style={{ color: theme.primary }}>
            {theme.display_name || "App name"}
          </span>
          <span className="ml-auto text-[8px] opacity-40 tracking-[0.15em]">PREVIEW</span>
        </div>
        <div className="px-4 py-5 text-[12px]">
          <div className="mb-2">Sample text body</div>
          <button
            className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider"
            style={{
              background: theme.primary,
              color: theme.background,
              borderRadius: theme.border_radius === "sharp" ? 0 : theme.border_radius === "pill" ? 9999 : 8,
            }}
          >
            Primary Action
          </button>
          <button
            className="ml-2 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider"
            style={{
              background: theme.accent,
              color: theme.background,
              borderRadius: theme.border_radius === "sharp" ? 0 : theme.border_radius === "pill" ? 9999 : 8,
            }}
          >
            Accent
          </button>
        </div>
      </div>

      {/* Presets */}
      <Field label="Color Presets" hint="One-click palettes — fine-tune below.">
        <div className="grid grid-cols-3 gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              data-testid={`customize-preset-${p.id}`}
              onClick={() => setTheme((t) => ({ ...t, primary: p.primary, accent: p.accent, background: p.background, text: p.text }))}
              className="flex items-center gap-2 px-2 py-1.5 rounded-sm hover:bg-zinc-800/60 border border-zinc-800 text-left"
            >
              <span className="flex -space-x-1">
                <span className="w-3 h-3 rounded-full border border-zinc-950" style={{ background: p.primary }} />
                <span className="w-3 h-3 rounded-full border border-zinc-950" style={{ background: p.accent }} />
              </span>
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-300">{p.name}</span>
            </button>
          ))}
        </div>
      </Field>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Display Name" hint="Shown in the branded header strip.">
          <input
            data-testid="customize-display-name"
            value={theme.display_name}
            onChange={(e) => update("display_name", e.target.value.slice(0, 80))}
            placeholder="My Awesome App"
            className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-[12px] font-mono text-zinc-100 focus:outline-none focus:border-cyan-400/60"
          />
        </Field>
        <Field label="Logo URL" hint="Square PNG/SVG. Leave blank to use a color dot.">
          <input
            data-testid="customize-logo-url"
            ref={fileInputRef}
            value={theme.logo_url}
            onChange={(e) => update("logo_url", e.target.value.slice(0, 600))}
            placeholder="https://example.com/logo.png"
            className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-[11px] font-mono text-zinc-100 focus:outline-none focus:border-cyan-400/60"
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <ColorPick label="Primary" testid="primary" value={theme.primary} onChange={(v) => update("primary", v)} />
        <ColorPick label="Accent" testid="accent" value={theme.accent} onChange={(v) => update("accent", v)} />
        <ColorPick label="Background" testid="background" value={theme.background} onChange={(v) => update("background", v)} />
        <ColorPick label="Text" testid="text" value={theme.text} onChange={(v) => update("text", v)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Corner Style" hint="Applies to buttons & cards.">
          <div className="flex gap-1">
            {[
              { id: "sharp", label: "Sharp" },
              { id: "rounded", label: "Rounded" },
              { id: "pill", label: "Pill" },
            ].map((r) => (
              <button
                key={r.id}
                data-testid={`customize-radius-${r.id}`}
                onClick={() => update("border_radius", r.id)}
                className={`flex-1 py-1.5 text-[10px] font-mono uppercase tracking-wider border ${
                  theme.border_radius === r.id
                    ? "bg-cyan-400/10 text-cyan-300 border-cyan-400/40"
                    : "text-zinc-400 border-zinc-800 hover:border-zinc-600"
                }`}
                style={{ borderRadius: r.id === "sharp" ? 0 : r.id === "pill" ? 9999 : 4 }}
              >
                {r.label}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Branded Header" hint="Thin strip with your logo + name. Suppressed when embedded.">
          <button
            data-testid="customize-show-branding"
            onClick={() => update("show_branding", !theme.show_branding)}
            className="flex items-center gap-2 px-3 py-1.5 border border-zinc-800 rounded-sm text-[11px] font-mono w-full"
          >
            {theme.show_branding ? <Eye size={12} className="text-cyan-300" /> : <EyeOff size={12} className="text-zinc-500" />}
            <span className={theme.show_branding ? "text-zinc-200" : "text-zinc-500"}>
              {theme.show_branding ? "Showing branded header" : "Hidden — clean canvas"}
            </span>
          </button>
        </Field>
      </div>
    </div>
  );
}

function EmbedTab({ publicUrl, embedUrl, embedSnippet, qrDataUrl, isPublic, copy, downloadQR }) {
  return (
    <div className="space-y-5">
      {/* Public URL status */}
      <div
        className="flex items-center gap-3 px-3 py-2.5 rounded-sm"
        style={{
          background: isPublic ? "rgba(34,197,94,0.06)" : "rgba(251,191,36,0.06)",
          border: `1px solid ${isPublic ? "rgba(34,197,94,0.3)" : "rgba(251,191,36,0.3)"}`,
        }}
      >
        {isPublic ? <Globe size={14} className="text-emerald-400" /> : <Lock size={14} className="text-amber-400" />}
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-400">
            {isPublic ? "Public · anyone with the link can view" : "Private · only you can view"}
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {isPublic
              ? "Embed snippets will work on any website."
              : "Make this app public from the Share menu before embedding — embedded copies need to be viewable by visitors."}
          </div>
        </div>
      </div>

      {/* Public URL with copy */}
      <Field label="Public URL" hint="Direct link to the hosted mini-app.">
        <div className="flex gap-1">
          <input
            data-testid="customize-public-url"
            readOnly
            value={publicUrl}
            className="flex-1 px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-[11px] font-mono text-zinc-300"
            onFocus={(e) => e.target.select()}
          />
          <button
            data-testid="customize-copy-url"
            onClick={() => copy(publicUrl, "Public URL")}
            className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-zinc-400 hover:text-cyan-300 hover:border-cyan-400/40"
            title="Copy URL"
          >
            <Copy size={12} />
          </button>
        </div>
      </Field>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_220px] gap-5 items-start">
        {/* Embed snippet */}
        <Field label="Embed Snippet" hint="Paste into any HTML page. The ?embed=1 flag hides the branded header.">
          <textarea
            data-testid="customize-embed-snippet"
            readOnly
            value={embedSnippet}
            rows={7}
            className="w-full px-2.5 py-2 bg-zinc-900 border border-zinc-800 rounded-sm text-[10px] font-mono text-zinc-300 leading-relaxed"
            onFocus={(e) => e.target.select()}
          />
          <button
            data-testid="customize-copy-embed"
            onClick={() => copy(embedSnippet, "Embed snippet")}
            className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-[10px] font-mono uppercase tracking-wider text-zinc-400 hover:text-cyan-300 hover:border-cyan-400/40"
          >
            <Copy size={11} /> Copy snippet
          </button>
        </Field>

        {/* QR code */}
        <Field label="QR Code" hint="Scan to open the app on mobile.">
          <div
            className="flex flex-col items-center gap-2 p-3 bg-white rounded-sm"
            data-testid="customize-qr-block"
          >
            {qrDataUrl ? (
              <img alt="QR code for sharing this app" src={qrDataUrl} className="w-[180px] h-[180px]" />
            ) : (
              <div className="w-[180px] h-[180px] flex items-center justify-center text-zinc-500">
                <QrCode size={48} />
              </div>
            )}
          </div>
          <button
            data-testid="customize-download-qr"
            onClick={downloadQR}
            disabled={!qrDataUrl}
            className="mt-2 w-full px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-sm text-[10px] font-mono uppercase tracking-wider text-zinc-400 hover:text-cyan-300 hover:border-cyan-400/40 disabled:opacity-40"
          >
            Download PNG
          </button>
        </Field>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-300">{label}</label>
        {hint && <span className="text-[9px] text-zinc-600 ml-2 truncate">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function ColorPick({ label, testid, value, onChange }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-300 mb-1.5">{label}</div>
      <div className="flex items-center gap-1.5">
        <input
          data-testid={`customize-color-${testid}`}
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-8 h-8 rounded-sm cursor-pointer bg-transparent border border-zinc-800"
          style={{ padding: 2 }}
        />
        <input
          data-testid={`customize-color-${testid}-hex`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#22d3ee"
          maxLength={7}
          className="flex-1 px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-sm text-[10px] font-mono text-zinc-200 focus:outline-none focus:border-cyan-400/40"
        />
      </div>
    </div>
  );
}

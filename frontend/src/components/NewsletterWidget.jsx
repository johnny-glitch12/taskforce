import { useState } from "react";
import { toast } from "sonner";
import { Mail, Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function NewsletterWidget() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [subscribed, setSubscribed] = useState(false);

  const submit = async (e) => {
    e?.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/newsletter/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), source: "footer" }),
      });
      if (res.ok) {
        setSubscribed(true);
        toast.success("Subscribed to the briefing.");
      } else {
        const e = await res.json();
        toast.error(e.detail?.[0]?.msg || e.detail || "Subscribe failed.");
      }
    } catch { toast.error("Network error."); }
    setBusy(false);
  };

  if (subscribed) {
    return (
      <div data-testid="newsletter-subscribed" className="flex items-center gap-2 text-[11px] t-text-mute font-mono">
        <CheckCircle2 size={12} className="text-emerald-400" />
        You'll get the next briefing.
      </div>
    );
  }

  return (
    <form onSubmit={submit} data-testid="newsletter-form" className="flex items-stretch gap-1.5 w-full max-w-md">
      <div className="relative flex-1">
        <Mail size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 t-text-dim" />
        <input
          data-testid="newsletter-email"
          type="email" required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-sm font-mono"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text)' }}
        />
      </div>
      <button
        type="submit"
        data-testid="newsletter-submit"
        disabled={busy}
        className="px-3 py-1.5 text-[10px] tracking-widest uppercase font-mono rounded-sm bg-cyan-400 text-black hover:bg-cyan-300 disabled:opacity-50"
      >
        {busy ? <Loader2 size={10} className="animate-spin" /> : "SUBSCRIBE"}
      </button>
    </form>
  );
}

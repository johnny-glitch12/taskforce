/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { useAuth } from "@/App";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  X, Loader2, Target, ShoppingBag, Package, Wand2, ArrowRight,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function SubmitToBountyModal({ bounty, onClose, onSubmitted }) {
  const { token } = useAuth() || {};
  const navigate = useNavigate();
  const auth = { Authorization: `Bearer ${token}` };
  const [tab, setTab] = useState("exchange"); // exchange | external | build
  const [exchange, setExchange] = useState([]);
  const [external, setExternal] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [pitch, setPitch] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        // My exchange listings — filter to "published" only since draft can't be sold.
        const [eR, xR] = await Promise.all([
          fetch(`${API}/api/exchange/my-listings`, { headers: auth }).then((r) => r.json()).catch(() => ({})),
          fetch(`${API}/api/external-agents/packages`, { headers: auth }).then((r) => r.json()).catch(() => ({})),
        ]);
        setExchange((eR.listings || []).filter((l) => l.status === "published"));
        setExternal(xR.packages || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, []);

  const list = tab === "exchange" ? exchange : tab === "external" ? external : [];

  async function submit() {
    if (!selected) { toast.error("Pick an agent first"); return; }
    if (pitch.trim().length < 20) { toast.error("Pitch must be at least 20 characters"); return; }
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/bounties/${bounty.id}/submit`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_source: tab === "exchange" ? "exchange" : "external",
          source_id: selected,
          pitch: pitch.trim(),
        }),
      });
      const body = await r.json();
      if (!r.ok) {
        toast.error(body.detail || `Failed (${r.status})`);
        return;
      }
      toast.success("Submission posted!");
      onSubmitted?.(body.submission);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function jumpToArmory() {
    // Persist bounty context so the build page can pre-fill from it.
    try {
      sessionStorage.setItem("tfai_bounty_prefill", JSON.stringify({
        bounty_id: bounty.id, title: bounty.title, description: bounty.description,
        category: bounty.category, required_integrations: bounty.required_integrations,
        input_expectations: bounty.input_expectations,
        output_expectations: bounty.output_expectations,
        example_use_case: bounty.example_use_case,
      }));
    } catch { /* ignore */ }
    navigate("/armory");
  }

  return (
    <div
      data-testid="submit-bounty-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="t-card rounded-sm max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        style={{ borderColor: "#22d3ee55" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[color:var(--border)] sticky top-0 z-10" style={{ background: "var(--bg-card)" }}>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Target size={18} className="text-cyan-400" />
              <h2 className="text-lg font-semibold t-text">Submit to bounty</h2>
            </div>
            <p className="text-xs t-text-mute truncate max-w-md">{bounty.title}</p>
          </div>
          <button data-testid="submit-modal-close" onClick={onClose} className="t-text-mute hover:text-rose-400">
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[color:var(--border)]">
          {[
            { id: "exchange", label: "Exchange listing", icon: ShoppingBag },
            { id: "external", label: "External agent", icon: Package },
            { id: "build", label: "Build in Armory", icon: Wand2 },
          ].map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                data-testid={`submit-tab-${t.id}`}
                onClick={() => { setTab(t.id); setSelected(null); }}
                className="px-4 py-3 text-[11px] font-mono uppercase tracking-[0.12em] inline-flex items-center gap-2"
                style={{
                  color: tab === t.id ? "#22d3ee" : "var(--text-mute)",
                  borderBottom: tab === t.id ? "2px solid #22d3ee" : "2px solid transparent",
                }}
              >
                <Icon size={12} /> {t.label}
              </button>
            );
          })}
        </div>

        {/* Body */}
        <div className="p-5">
          {tab === "build" ? (
            <div className="text-center py-10">
              <Wand2 size={32} className="mx-auto text-cyan-400 mb-3" />
              <h3 className="text-base font-semibold t-text mb-1">Build a new agent for this bounty</h3>
              <p className="text-sm t-text-mute mb-6 max-w-md mx-auto">
                We'll send you to the Armory (Vibe Coding) with this bounty's requirements pre-filled.
                After publishing, come back here to submit.
              </p>
              <button
                data-testid="jump-to-armory-btn"
                onClick={jumpToArmory}
                className="px-5 py-2.5 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
                style={{ background: "#22d3ee", color: "#0a0e1a" }}
              >
                Open Armory <ArrowRight size={12} />
              </button>
            </div>
          ) : (
            <>
              {loading ? (
                <div className="text-center py-10 t-text-mute text-sm" data-testid="agents-loading">
                  <Loader2 size={14} className="animate-spin inline-block mr-2" /> Loading your agents…
                </div>
              ) : list.length === 0 ? (
                <div className="text-center py-10" data-testid={`no-${tab}-agents`}>
                  <div className="text-sm t-text mb-1">
                    {tab === "exchange" ? "No published listings yet." : "No external packages uploaded yet."}
                  </div>
                  <div className="text-xs t-text-mute">
                    {tab === "exchange"
                      ? "Publish an agent to The Exchange first, or upload an external package."
                      : "Upload a .tfagent package on the External Agents page."}
                  </div>
                </div>
              ) : (
                <div className="space-y-2 mb-5" data-testid={`${tab}-agents-list`}>
                  {list.map((it) => {
                    const isExch = tab === "exchange";
                    const id = it.id;
                    const label = isExch
                      ? (it.name || it.agent_name || it.title || id.slice(0, 8))
                      : (it.manifest?.display_name || it.manifest?.name || id.slice(0, 8));
                    const sub = isExch
                      ? (it.description?.slice(0, 100) || it.category)
                      : (it.manifest?.description?.slice(0, 100) || it.manifest?.runtime);
                    return (
                      <button
                        key={id}
                        type="button"
                        data-testid={`agent-pick-${id}`}
                        onClick={() => setSelected(id)}
                        className="w-full text-left p-3 rounded-sm transition-all"
                        style={{
                          background: selected === id ? "#22d3ee15" : "var(--bg-input)",
                          border: `1px solid ${selected === id ? "#22d3ee88" : "var(--border)"}`,
                        }}
                      >
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium t-text">{label}</span>
                          {selected === id && (
                            <span className="text-[9px] uppercase tracking-[0.15em] font-mono px-1.5 py-0.5 rounded-sm"
                                  style={{ background: "#22d3ee", color: "#0a0e1a" }}>
                              Selected
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] t-text-mute font-mono truncate">{sub}</div>
                      </button>
                    );
                  })}
                </div>
              )}

              {!loading && list.length > 0 && (
                <>
                  <div className="text-[10px] uppercase tracking-[0.18em] font-mono t-text-dim mb-1">Your pitch</div>
                  <textarea
                    data-testid="pitch-input"
                    value={pitch}
                    onChange={(e) => setPitch(e.target.value)}
                    rows={4}
                    maxLength={2000}
                    placeholder="Why is your agent the best fit? What proof do you have it solves the problem?"
                    className="w-full px-3 py-2 text-sm t-text rounded-sm outline-none font-mono"
                    style={{ background: "var(--bg-input)", border: "1px solid var(--border)", resize: "vertical" }}
                  />
                  <div className="text-[10px] t-text-dim font-mono mt-1">{pitch.length}/2000 · min 20 chars</div>
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {tab !== "build" && !loading && list.length > 0 && (
          <div className="p-5 border-t border-[color:var(--border)] sticky bottom-0" style={{ background: "var(--bg-card)" }}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[10px] t-text-dim font-mono">
                {selected ? "Ready to submit" : "Pick an agent above"}
              </span>
              <div className="flex gap-2">
                <button
                  data-testid="submit-cancel-btn"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-mono uppercase tracking-[0.12em] t-text-mute hover:text-rose-400"
                >
                  Cancel
                </button>
                <button
                  data-testid="submit-confirm-btn"
                  onClick={submit}
                  disabled={submitting || !selected || pitch.trim().length < 20}
                  className="px-5 py-2 rounded-sm text-xs font-mono uppercase tracking-[0.15em] inline-flex items-center gap-2"
                  style={{
                    background: (selected && pitch.trim().length >= 20) ? "#22d3ee" : "var(--bg-input)",
                    color: (selected && pitch.trim().length >= 20) ? "#0a0e1a" : "var(--text-mute)",
                    opacity: submitting ? 0.5 : 1,
                    cursor: (selected && pitch.trim().length >= 20) ? "pointer" : "not-allowed",
                  }}
                >
                  {submitting ? <><Loader2 size={11} className="animate-spin" /> Submitting…</> : "Submit solution"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

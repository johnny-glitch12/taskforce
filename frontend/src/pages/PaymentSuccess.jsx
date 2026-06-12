import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2, Server, Target } from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const type = searchParams.get("type"); // "hosting" | "bounty" | "subscription" | undefined
  const { token } = useAuth() || {};
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [hostingSub, setHostingSub] = useState(null);
  const [bounty, setBounty] = useState(null);

  useEffect(() => {
    if (!sessionId) { setStatus("error"); return; }
    let attempts = 0;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/payments/status/${sessionId}`);
        if (!res.ok) throw new Error("Not found");
        const d = await res.json();
        setData(d);
        if (d.payment_status === "paid") {
          // For hosting checkouts, also activate the subscription row.
          if (type === "hosting" && token) {
            try {
              const aRes = await fetch(`${API}/api/hosting/activate`, {
                method: "POST",
                headers: {
                  Authorization: `Bearer ${token}`,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({ session_id: sessionId }),
              });
              if (aRes.ok) {
                const aBody = await aRes.json();
                setHostingSub(aBody.subscription);
              }
            } catch { /* surfaced via the success card anyway */ }
          }
          // For cash-bounty checkouts, flip the bounty to status=open + escrow=held.
          if (type === "bounty" && token && d.bounty_id) {
            try {
              const aRes = await fetch(`${API}/api/bounties/${d.bounty_id}/activate`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
              });
              if (aRes.ok) {
                const aBody = await aRes.json();
                setBounty(aBody.bounty);
              }
            } catch { /* surfaced via the success card anyway */ }
          }
          setStatus("success");
          return;
        }
        if (d.status === "expired") { setStatus("expired"); return; }
        attempts++;
        if (attempts < 8) setTimeout(poll, 2000);
        else setStatus("timeout");
      } catch {
        attempts++;
        if (attempts < 5) setTimeout(poll, 2000);
        else setStatus("error");
      }
    };
    poll();
  }, [sessionId, type, token]);

  const successTitle = type === "hosting"
    ? "Hosting Plan Activated"
    : type === "bounty"
      ? "Bounty Funded"
      : "Payment Successful";
  const SuccessIcon = type === "hosting" ? Server : type === "bounty" ? Target : CheckCircle2;

  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6">
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-sm bg-cyan-400/[0.06] blur-[100px] pointer-events-none" />
      <div data-testid="payment-result-card" className="relative w-full max-w-md rounded-sm p-8 text-center animate-fade-in-up backdrop-blur-sm" style={{ animationFillMode: "forwards", background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        {status === "loading" && (
          <>
            <Loader2 size={40} className="text-cyan-400 animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold t-text mb-2">Processing Payment</h2>
            <p className="text-[13px] t-text-mute">Verifying your transaction...</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="w-16 h-16 rounded-sm bg-emerald-500/10 flex items-center justify-center mx-auto mb-5">
              <SuccessIcon size={32} className="text-emerald-400" />
            </div>
            <h2 data-testid="payment-success-title" className="text-xl font-semibold t-text mb-2">
              {successTitle}
            </h2>

            {type === "hosting" && (
              <>
                <p className="text-[13px] t-text-mute mb-1" data-testid="hosting-success-detail">
                  {hostingSub?.tier_meta?.label || "Your hosting plan"} is now active.
                </p>
                {hostingSub?.current_period_end && (
                  <p className="text-[12px] t-text-dim mb-6 font-mono">
                    Renews after {hostingSub.current_period_end.slice(0, 10)}
                  </p>
                )}
                <div className="flex flex-col sm:flex-row gap-3">
                  <Link to="/hosting" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-colors text-center">
                    Hosting Dashboard
                  </Link>
                  <Link to="/creator" className="flex-1 py-3 t-text text-[13px] font-medium rounded-sm hover:bg-[var(--bg-card-hover)] transition-colors text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                    Creator Dashboard
                  </Link>
                </div>
              </>
            )}

            {type === "bounty" && (
              <>
                <p className="text-[13px] t-text-mute mb-1" data-testid="bounty-success-detail">
                  {bounty?.title ? <strong className="t-text-sub">{bounty.title}</strong> : "Your cash bounty"} is now open for submissions.
                </p>
                <p className="text-[12px] t-text-dim mb-6 font-mono">
                  ${data?.amount != null ? (data.amount / 100).toFixed(2) : Number(bounty?.reward_amount || 0).toFixed(2)} held in Stripe escrow.
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                  {bounty?.id ? (
                    <Link to={`/bounties/${bounty.id}`} data-testid="go-to-bounty-btn" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-colors text-center">
                      View bounty
                    </Link>
                  ) : (
                    <Link to="/bounties" data-testid="back-to-bounties-btn" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-colors text-center">
                      Bounty Board
                    </Link>
                  )}
                  <Link to="/bounties" className="flex-1 py-3 t-text text-[13px] font-medium rounded-sm hover:bg-[var(--bg-card-hover)] transition-colors text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                    All Bounties
                  </Link>
                </div>
              </>
            )}

            {(type !== "hosting" && type !== "bounty") && (
              <>
                <p className="text-[13px] t-text-mute mb-1">
                  {data?.agent_name && <><strong className="t-text-sub">{data.agent_name}</strong> — </>}
                  {data?.plan === "rent" ? "Monthly rental" : "Full purchase"} confirmed.
                </p>
                {data?.amount != null && <p className="text-[13px] t-text-dim mb-6">${(data.amount / 100).toFixed(2)} {data.currency?.toUpperCase()}</p>}
                <div className="flex flex-col sm:flex-row gap-3">
                  <Link to="/studio" data-testid="go-to-studio-btn" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-colors text-center">
                    Open Studio
                  </Link>
                  <Link to="/marketplace" data-testid="back-to-marketplace-btn" className="flex-1 py-3 t-text text-[13px] font-medium rounded-sm hover:bg-[var(--bg-card-hover)] transition-colors text-center" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                    Marketplace
                  </Link>
                </div>
              </>
            )}
          </>
        )}
        {(status === "error" || status === "expired" || status === "timeout") && (
          <>
            <div className="w-16 h-16 rounded-sm bg-red-500/10 flex items-center justify-center mx-auto mb-5">
              <XCircle size={32} className="text-red-400" />
            </div>
            <h2 className="text-xl font-semibold t-text mb-2">
              {status === "expired" ? "Session Expired" : "Payment Issue"}
            </h2>
            <p className="text-[13px] t-text-mute mb-6">
              {status === "expired" ? "Your payment session has expired. Please try again." : "We couldn't verify your payment. Please try again or contact support."}
            </p>
            <Link to={type === "bounty" ? "/bounties" : "/marketplace"} className="inline-block py-3 px-8 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-colors">
              {type === "bounty" ? "Back to Bounties" : "Back to Marketplace"}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

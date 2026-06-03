import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2, Server } from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL;

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const type = searchParams.get("type"); // "hosting" | "subscription" | undefined
  const { token } = useAuth() || {};
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [hostingSub, setHostingSub] = useState(null);

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

  return (
    <div className="min-h-[calc(100vh-60px)] flex items-center justify-center px-6">
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-sm bg-cyan-400/[0.06] blur-[100px] pointer-events-none" />
      <div data-testid="payment-result-card" className="relative w-full max-w-md bg-white/[0.03] border border-white/[0.08] rounded-sm p-8 text-center animate-fade-in-up backdrop-blur-sm" style={{ animationFillMode: "forwards" }}>
        {status === "loading" && (
          <>
            <Loader2 size={40} className="text-cyan-400 animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-white mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>Processing Payment</h2>
            <p className="text-[13px] text-zinc-500">Verifying your transaction...</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="w-16 h-16 rounded-sm bg-emerald-500/10 flex items-center justify-center mx-auto mb-5">
              {type === "hosting"
                ? <Server size={32} className="text-emerald-400" />
                : <CheckCircle2 size={32} className="text-emerald-400" />}
            </div>
            <h2 data-testid="payment-success-title" className="text-xl font-semibold text-white mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
              {type === "hosting" ? "Hosting Plan Activated" : "Payment Successful"}
            </h2>
            {type === "hosting" ? (
              <>
                <p className="text-[13px] text-zinc-500 mb-1" data-testid="hosting-success-detail">
                  {hostingSub?.tier_meta?.label || "Your hosting plan"} is now active.
                </p>
                {hostingSub?.current_period_end && (
                  <p className="text-[12px] text-zinc-600 mb-6 font-mono">
                    Renews after {hostingSub.current_period_end.slice(0, 10)}
                  </p>
                )}
                <div className="flex flex-col sm:flex-row gap-3">
                  <Link to="/hosting" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all text-center">
                    Hosting Dashboard
                  </Link>
                  <Link to="/creator" className="flex-1 py-3 bg-white/[0.06] text-white text-[13px] font-medium rounded-sm border border-white/[0.08] hover:bg-white/[0.1] transition-all text-center">
                    Creator Dashboard
                  </Link>
                </div>
              </>
            ) : (
              <>
                <p className="text-[13px] text-zinc-500 mb-1">
                  {data?.agent_name && <><strong className="text-zinc-300">{data.agent_name}</strong> — </>}
                  {data?.plan === "rent" ? "Monthly rental" : "Full purchase"} confirmed.
                </p>
                {data?.amount != null && <p className="text-[13px] text-zinc-600 mb-6">${(data.amount / 100).toFixed(2)} {data.currency?.toUpperCase()}</p>}
                <div className="flex flex-col sm:flex-row gap-3">
                  <Link to="/studio" data-testid="go-to-studio-btn" className="flex-1 py-3 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all text-center">
                    Open Studio
                  </Link>
                  <Link to="/marketplace" data-testid="back-to-marketplace-btn" className="flex-1 py-3 bg-white/[0.06] text-white text-[13px] font-medium rounded-sm border border-white/[0.08] hover:bg-white/[0.1] transition-all text-center">
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
            <h2 className="text-xl font-semibold text-white mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
              {status === "expired" ? "Session Expired" : "Payment Issue"}
            </h2>
            <p className="text-[13px] text-zinc-500 mb-6">
              {status === "expired" ? "Your payment session has expired. Please try again." : "We couldn't verify your payment. Please try again or contact support."}
            </p>
            <Link to="/marketplace" className="inline-block py-3 px-8 bg-cyan-400 text-black font-bold text-[13px] font-medium rounded-sm hover:bg-cyan-300 transition-all">
              Back to Marketplace
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

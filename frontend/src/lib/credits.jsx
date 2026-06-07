/**
 * Credit balance context — single source of truth for the navbar counter,
 * the Credits page, and any other component that needs to know the user's
 * wallet balance.
 *
 * Polls /api/credits/balance every 30s and exposes a `refreshCredits()`
 * imperative that any component can call after an action that changes the
 * balance (purchase, top-up success, vibe build, etc.).
 *
 * ALSO: watches `cashback_lifetime` across polls. When it increases (user just
 * crossed the silent 100-credit accumulator threshold), we fire a one-off
 * celebration toast — preserves the surprise reward feel while still letting
 * the user know they earned something.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Gift } from "lucide-react";
import { useAuth } from "@/App";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 30_000;

const CreditContext = createContext({
  credits: null, loading: true, refreshCredits: () => {},
});

export function CreditProvider({ children }) {
  const { token, user } = useAuth();
  const [credits, setCredits] = useState(null);
  const [loading, setLoading] = useState(true);
  const abortRef = useRef(null);
  // Last-seen cashback total. Set on FIRST successful poll so we don't fire
  // a celebration toast on initial load for a user with existing cashback.
  const lastCashbackRef = useRef(null);

  const fetchCredits = useCallback(async () => {
    if (!token) { setCredits(null); setLoading(false); return; }
    abortRef.current?.abort?.();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(`${API}/api/credits/balance`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: ctrl.signal,
      });
      if (res.ok) {
        const data = await res.json();
        const newCashback = Number(data.cashback_lifetime || 0);
        // First poll: just record the baseline; do NOT toast.
        if (lastCashbackRef.current === null) {
          lastCashbackRef.current = newCashback;
        } else if (newCashback > lastCashbackRef.current) {
          const delta = newCashback - lastCashbackRef.current;
          lastCashbackRef.current = newCashback;
          // Variable-ratio cashback was just granted by the server.
          // Surface a friendly celebration without spoiling the surprise loop.
          toast.success(`+${delta} cashback credits earned!`, {
            description: "Spending cashback dropped into your wallet.",
            icon: <Gift size={16} className="text-emerald-300" />,
            duration: 5000,
          });
        }
        setCredits(data);
      }
    } catch { /* silent — keep stale value */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    // Reset the cashback baseline whenever the user changes (login/logout/swap).
    lastCashbackRef.current = null;
    if (!token) { setCredits(null); setLoading(false); return; }
    fetchCredits();
    const id = setInterval(fetchCredits, POLL_MS);
    // Also refresh when the tab regains focus (cheap UX win).
    const onFocus = () => fetchCredits();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
      abortRef.current?.abort?.();
    };
  }, [token, user?.id, fetchCredits]);

  return (
    <CreditContext.Provider value={{ credits, loading, refreshCredits: fetchCredits }}>
      {children}
    </CreditContext.Provider>
  );
}

export function useCredits() {
  return useContext(CreditContext);
}

/**
 * Credit balance context — single source of truth for the navbar counter,
 * the Credits page, and any other component that needs to know the user's
 * wallet balance.
 *
 * Polls /api/credits/balance every 30s and exposes a `refreshCredits()`
 * imperative that any component can call after an action that changes the
 * balance (purchase, top-up success, vibe build, etc.).
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
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
      if (res.ok) setCredits(await res.json());
    } catch { /* silent — keep stale value */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
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

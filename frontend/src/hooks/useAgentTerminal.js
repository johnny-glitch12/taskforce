import { useState, useEffect, useRef } from "react";
import { supabase } from "../lib/supabase";

/**
 * useAgentTerminal — nidoai hook ported to React.
 *
 * Subscribes to Supabase Realtime on the agent_logs table,
 * filtered by log_id. Returns live terminal history, status,
 * and the final output result.
 *
 * Falls back to polling if Realtime doesn't fire within 3s.
 */
export function useAgentTerminal(logId) {
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState("idle");
  const [lastStatus, setLastStatus] = useState(null);
  const [outputResult, setOutputResult] = useState(null);
  const channelRef = useRef(null);
  const pollRef = useRef(null);
  const realtimeFired = useRef(false);

  useEffect(() => {
    if (!logId) {
      setHistory([]);
      setStatus("idle");
      setOutputResult(null);
      return;
    }

    setStatus("queued");
    setHistory(["[INIT] Agent execution queued."]);
    setOutputResult(null);
    realtimeFired.current = false;

    const applyRow = (row) => {
      realtimeFired.current = true;
      if (row.terminal_history) setHistory(row.terminal_history);
      if (row.status) {
        setStatus(row.status);
        setLastStatus(row.status);
      }
      if (row.output_result !== undefined) setOutputResult(row.output_result);
    };

    // 1. Realtime subscription
    const channel = supabase
      .channel(`agent-log-${logId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "agent_logs",
          filter: `log_id=eq.${logId}`,
        },
        (payload) => {
          applyRow(payload.new);
        }
      )
      .subscribe();

    channelRef.current = channel;

    // 2. Fallback polling (1.5s) — covers cases where Realtime is slow
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await supabase
          .from("agent_logs")
          .select("*")
          .eq("log_id", logId)
          .single();
        if (data) applyRow(data);
        // Stop polling on terminal states
        if (data?.status === "success" || data?.status === "failed") {
          clearInterval(pollRef.current);
        }
      } catch {}
    }, 1500);

    // 3. Initial fetch
    (async () => {
      try {
        const { data } = await supabase
          .from("agent_logs")
          .select("*")
          .eq("log_id", logId)
          .single();
        if (data) applyRow(data);
      } catch {}
    })();

    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
      }
      clearInterval(pollRef.current);
    };
  }, [logId]);

  const isLive = status === "queued" || status === "processing";

  return { history, status, isLive, lastStatus, outputResult };
}

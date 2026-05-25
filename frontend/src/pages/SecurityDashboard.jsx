import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/App";
import {
  Shield, AlertTriangle, CheckCircle2, XCircle, Eye,
  RefreshCw, Filter, Clock, Loader2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const VERDICT_STYLES = {
  SAFE: { color: "text-emerald-400", bg: "bg-emerald-500/10", icon: CheckCircle2 },
  SUSPICIOUS: { color: "text-amber-400", bg: "bg-amber-500/10", icon: AlertTriangle },
  UNSAFE: { color: "text-red-400", bg: "bg-red-500/10", icon: XCircle },
};

function StatBox({ label, value, color, icon: Icon }) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] t-text-sub tracking-wide">{label}</span>
        <Icon size={14} style={{ color }} />
      </div>
      <p className="text-2xl font-semibold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>{value}</p>
    </div>
  );
}

function EventRow({ event }) {
  const [expanded, setExpanded] = useState(false);
  const style = VERDICT_STYLES[event.verdict] || VERDICT_STYLES.SAFE;
  const VerdictIcon = style.icon;
  const time = new Date(event.created_at).toLocaleString();

  return (
    <div
      data-testid={`security-event-${event.event_id}`}
      className="transition-all"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <div className="px-4 py-3 flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <VerdictIcon size={14} className={style.color} />
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${style.bg} ${style.color}`}>
          {event.verdict}
        </span>
        <span className="text-[12px] t-text-sub truncate flex-1">{event.executor_id}</span>
        {event.blocked && (
          <span className="text-[10px] bg-red-500/10 text-red-400 px-2 py-0.5 rounded-full font-medium">BLOCKED</span>
        )}
        <span className="text-[11px] t-text-dim flex items-center gap-1 shrink-0">
          <Clock size={10} /> {time}
        </span>
        <Eye size={12} className="t-text-dim shrink-0" />
      </div>
      {expanded && (
        <div className="px-4 pb-3 pt-0">
          <div className="rounded-lg p-3 text-[12px] font-mono t-text-mute leading-relaxed" style={{ background: '#0d0d0f' }}>
            {event.prompt_snippet || "No prompt captured"}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SecurityDashboard() {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filter !== "all") params.set("verdict", filter);

      const [statsRes, eventsRes] = await Promise.all([
        fetch(`${API}/api/security/stats`, { headers }).then(r => r.json()),
        fetch(`${API}/api/security/events?${params}`, { headers }).then(r => r.json()),
      ]);
      setStats(statsRes);
      setEvents(eventsRes.events || []);
    } catch (e) {
      console.error("Failed to load security data", e);
    }
    setLoading(false);
  }, [token, filter]);

  useEffect(() => { if (token) fetchData(); }, [token, fetchData]);

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-60px)] flex items-center justify-center">
        <Loader2 size={24} className="text-[#8B5CF6] animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="security-dashboard" className="min-h-[calc(100vh-60px)] t-bg px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold t-text tracking-tight flex items-center gap-3" style={{ fontFamily: "'Outfit', sans-serif" }}>
              <Shield size={24} className="text-[#8B5CF6]" /> Security Audit Log
            </h1>
            <p className="text-[13px] t-text-sub mt-1">Monitor firewall verdicts and blocked prompt injection attempts</p>
          </div>
          <button
            onClick={fetchData}
            data-testid="refresh-security-btn"
            className="px-4 py-2 rounded-full text-[13px] font-medium flex items-center gap-2 t-text-sub hover:t-text transition-colors"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-8">
            <StatBox label="Total Audits" value={stats.total_audits} color="#8B5CF6" icon={Shield} />
            <StatBox label="Safe" value={stats.safe} color="#34d399" icon={CheckCircle2} />
            <StatBox label="Suspicious" value={stats.suspicious} color="#fbbf24" icon={AlertTriangle} />
            <StatBox label="Unsafe" value={stats.unsafe} color="#f87171" icon={XCircle} />
            <StatBox label="Blocked" value={stats.blocked} color="#ef4444" icon={XCircle} />
          </div>
        )}

        {/* Filter pills */}
        <div className="flex items-center gap-2 mb-6">
          <Filter size={13} className="t-text-dim" />
          {["all", "SAFE", "SUSPICIOUS", "UNSAFE"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              data-testid={`filter-${f.toLowerCase()}`}
              className={`px-3 py-1.5 text-[12px] rounded-full transition-all ${
                filter === f ? "bg-[#8B5CF6] text-white" : "t-text-sub"
              }`}
              style={filter !== f ? { background: 'var(--bg-card)', border: '1px solid var(--border)' } : {}}
            >
              {f === "all" ? "All" : f}
            </button>
          ))}
        </div>

        {/* Events List */}
        <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
          <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
            <Shield size={13} className="text-[#8B5CF6]" />
            <span className="text-[12px] t-text-sub font-medium">Audit Events</span>
            <span className="ml-auto text-[11px] t-text-dim">{events.length} events</span>
          </div>

          {events.length === 0 ? (
            <div className="text-center py-16">
              <Shield size={32} className="t-text-dim mx-auto mb-3" />
              <p className="text-[14px] t-text-sub">No security events yet</p>
              <p className="text-[12px] t-text-dim mt-1">Events will appear here when agents are executed through the Vibe Chat.</p>
            </div>
          ) : (
            <div className="max-h-[500px] overflow-y-auto">
              {events.map((event) => (
                <EventRow key={event.event_id} event={event} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

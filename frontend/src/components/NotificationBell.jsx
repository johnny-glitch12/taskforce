/* eslint-disable react/prop-types */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/App";
import {
  Bell, BellDot, CheckCheck, Trophy, Target, XCircle, Inbox, Loader2,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const KIND_META = {
  bounty_submission_new: { icon: Target,   color: "#22d3ee", label: "New submission" },
  bounty_won:            { icon: Trophy,   color: "#fbbf24", label: "Bounty won" },
  bounty_lost:           { icon: XCircle,  color: "#94a3b8", label: "Bounty closed" },
  default:               { icon: Inbox,    color: "#22d3ee", label: "Notification" },
};

function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  const diff = Math.max(0, (Date.now() - t) / 1000);
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function payloadHref(n) {
  const p = n.payload || {};
  if (p.bounty_id) return `/bounties/${p.bounty_id}`;
  return null;
}

export default function NotificationBell() {
  const { token } = useAuth() || {};
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);
  const buttonRef = useRef(null);

  // Poll the unread badge every 30s while the page is open.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function fetchCount() {
      try {
        const r = await fetch(`${API}/api/notifications/unread-count`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok || cancelled) return;
        const body = await r.json();
        setUnread(body.unread || 0);
      } catch { /* ignore */ }
    }
    fetchCount();
    const id = setInterval(fetchCount, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [token]);

  // Close on click-outside.
  useEffect(() => {
    if (!open) return;
    function onDoc(e) {
      if (dropdownRef.current?.contains(e.target)) return;
      if (buttonRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  async function refresh() {
    if (!token) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/notifications?limit=20`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) return;
      const body = await r.json();
      setItems(body.items || []);
      setUnread(body.unread || 0);
    } finally {
      setLoading(false);
    }
  }

  async function markAllRead() {
    if (!token || unread === 0) return;
    try {
      await fetch(`${API}/api/notifications/mark-all-read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setUnread(0);
      setItems((xs) => xs.map((x) => ({ ...x, read: true })));
    } catch { /* ignore */ }
  }

  async function markOneRead(n) {
    if (n.read) return;
    try {
      await fetch(`${API}/api/notifications/${n.id}/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setUnread((u) => Math.max(0, u - 1));
      setItems((xs) => xs.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
    } catch { /* ignore */ }
  }

  function toggle() {
    setOpen((o) => {
      if (!o) refresh();
      return !o;
    });
  }

  if (!token) return null;

  const Icon = unread > 0 ? BellDot : Bell;
  return (
    <div className="relative" data-testid="notification-bell-wrap">
      <button
        ref={buttonRef}
        data-testid="notification-bell-btn"
        aria-label="Notifications"
        onClick={toggle}
        className="relative p-2 rounded-sm transition-all hover:bg-white/[0.05]"
      >
        <Icon size={17} className={unread > 0 ? "text-cyan-400" : "t-text-mute"} />
        {unread > 0 && (
          <span
            data-testid="notification-unread-badge"
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-[16px] px-1 text-[9px] font-mono font-bold rounded-full flex items-center justify-center"
            style={{ background: "#22d3ee", color: "#0a0e1a", border: "2px solid var(--bg-nav, #0a0e1a)" }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={dropdownRef}
          data-testid="notification-dropdown"
          className="absolute right-0 mt-2 w-96 max-h-[28rem] overflow-hidden rounded-sm shadow-2xl z-50 flex flex-col notif-dropdown-solid"
          style={{
            /* Solid background — the global --bg-card is rgba(.,.02) (almost
               fully transparent). --bg-elevated is fully opaque per theme. */
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            backdropFilter: "none",
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--border)]">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-[0.15em] t-text">Notifications</span>
              {unread > 0 && (
                <span
                  className="text-[9px] font-mono uppercase tracking-[0.15em] px-1.5 py-0.5 rounded-sm"
                  style={{ background: "#22d3ee22", color: "#22d3ee", border: "1px solid #22d3ee55" }}
                >
                  {unread} new
                </span>
              )}
            </div>
            {unread > 0 && (
              <button
                data-testid="mark-all-read-btn"
                onClick={markAllRead}
                className="text-[10px] font-mono t-text-mute hover:text-cyan-400 inline-flex items-center gap-1"
              >
                <CheckCheck size={11} /> Mark all read
              </button>
            )}
          </div>

          {/* Body */}
          <div className="overflow-y-auto flex-1">
            {loading ? (
              <div className="text-center py-10 t-text-mute text-xs" data-testid="notifications-loading">
                <Loader2 size={12} className="animate-spin inline-block mr-2" /> Loading…
              </div>
            ) : items.length === 0 ? (
              <div className="text-center py-10 px-4" data-testid="notifications-empty">
                <Inbox size={20} className="mx-auto t-text-dim mb-2" />
                <div className="text-xs t-text-mute font-mono">No notifications yet.</div>
                <div className="text-[10px] t-text-dim font-mono mt-1">You'll get pinged when you submit, win, or post a bounty.</div>
              </div>
            ) : (
              <ul className="divide-y divide-[color:var(--border)]" data-testid="notifications-list">
                {items.map((n) => {
                  const meta = KIND_META[n.kind] || KIND_META.default;
                  const NIcon = meta.icon;
                  const href = payloadHref(n);
                  const body = (
                    <div
                      data-testid={`notification-row-${n.id}`}
                      onClick={() => markOneRead(n)}
                      className="px-4 py-3 hover:bg-white/[0.03] transition-all flex items-start gap-3 cursor-pointer"
                      style={{ opacity: n.read ? 0.55 : 1 }}
                    >
                      <div
                        className="w-7 h-7 rounded-sm flex items-center justify-center shrink-0"
                        style={{ background: `${meta.color}1a`, border: `1px solid ${meta.color}55` }}
                      >
                        <NIcon size={13} style={{ color: meta.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] t-text-dim mb-0.5 flex items-center gap-1.5">
                          {meta.label}
                          {!n.read && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#22d3ee" }} />}
                        </div>
                        <div className="text-xs t-text leading-snug" style={{
                          display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden",
                        }}>
                          {n.message}
                        </div>
                        <div className="text-[10px] t-text-dim font-mono mt-1">{relTime(n.created_at)}</div>
                      </div>
                    </div>
                  );
                  return (
                    <li key={n.id}>
                      {href ? (
                        <Link to={href} onClick={() => setOpen(false)}>
                          {body}
                        </Link>
                      ) : body}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

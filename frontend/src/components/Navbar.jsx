import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useTheme } from "@/lib/theme";
import { Menu, X, Sun, Moon, ChevronDown, LayoutDashboard, BarChart3, Shield, LogOut, Coins, Rocket, Sparkles, Package, Server, Banknote, TrendingUp, Key, Layers, Brain, Bot } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import NotificationBell from "@/components/NotificationBell";
import CreditCounter from "@/components/CreditCounter";

const API = process.env.REACT_APP_BACKEND_URL || "";

// ── Prompt 31 Phase 2 — module-level cached agent count ─────────────────
// Cached for the browser session so the Navbar doesn't refetch on every
// render. Refreshed on focus/visibility events or explicit refresh.
let _agentCountCache = { active: null, total: null, ts: 0 };

function useAgentCount() {
  const [count, setCount] = useState(() => _agentCountCache.active);
  const location = useLocation();
  // Phase 5: refetch whenever the user navigates to ANY /my-agents* path,
  // so mutations made on those pages (pause/resume/delete) are reflected
  // immediately in the navbar badge without manual refresh.
  const isMyAgentsPath = location.pathname === "/my-agents"
    || location.pathname.startsWith("/my-agents/");
  useEffect(() => {
    const token = localStorage.getItem("taskforce_token");
    if (!token) return;
    const stale = Date.now() - _agentCountCache.ts >= 60_000;
    // Skip if cache is fresh AND we're not on a my-agents page
    if (_agentCountCache.active !== null && !stale && !isMyAgentsPath) return;
    let aborted = false;
    fetch(`${API}/api/agents/stats/overview`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (aborted || !d) return;
        _agentCountCache = { active: d.active_now, total: d.total_agents, ts: Date.now() };
        setCount(d.active_now);
      })
      .catch(() => {});
    return () => { aborted = true; };
  }, [location.pathname, isMyAgentsPath]);
  return count;
}

const CENTER_LINKS_PUBLIC = [
  { to: "/armory", label: "The Armory", accent: true, beta: true },
  { to: "/exchange", label: "The Exchange" },
  { to: "/bounties", label: "Bounty Board" },
  { to: "/leaderboard", label: "Leaderboard", soon: true },
  { to: "/academy", label: "Academy", soon: true },
  { to: "/pricing", label: "Pricing" },
];

const CENTER_LINKS_ADMIN = [
  { to: "/armory", label: "The Armory", accent: true, beta: true },
  { to: "/exchange", label: "The Exchange" },
  { to: "/bounties", label: "Bounty Board" },
  { to: "/leaderboard", label: "Leaderboard", soon: true },
  { to: "/academy", label: "Academy" },
  { to: "/pricing", label: "Pricing" },
];

function UserMenu({ user, logout, navigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const isAdmin = user?.role === "admin";
  const isOwner = isAdmin && !!user?.is_owner;

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const menuItems = [
    { to: "/dashboard", label: "Command Center", icon: LayoutDashboard },
    { to: "/my-agents", label: "My Agents", icon: Bot, accent: true },
    { to: "/credits", label: "Credits", icon: Coins },
    { to: "/my-deployments", label: "My Deployments", icon: Rocket },
    { to: "/my-apps", label: "My Apps", icon: Layers, accent: true },
    { to: "/external-agents", label: "External Agents", icon: Package },
    { to: "/hosting", label: "Hosting Plans", icon: Server },
    { to: "/payouts", label: "Payouts", icon: Banknote },
    { to: "/earnings", label: "Earnings", icon: TrendingUp },
    { to: "/keys", label: "API Keys", icon: Key },
    { to: "/credentials", label: "Credentials Vault", icon: Shield },
    { to: "/settings/memory", label: "Builder Memory", icon: Brain },
    ...(isAdmin ? [
      { to: "/overwatch", label: "Overwatch", icon: BarChart3, accent: true },
      { to: "/security", label: "Security", icon: Shield },
    ] : []),
    ...(isOwner ? [
      { to: "/admin/economics", label: "Economics", icon: TrendingUp, accent: true },
    ] : []),
  ];

  return (
    <div ref={ref} className="relative">
      <button
        data-testid="user-menu-btn"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-[11px] font-mono tracking-[0.08em] uppercase transition-all text-zinc-400 hover:text-cyan-400"
        style={{ border: '1px solid transparent' }}
      >
        <div className="w-6 h-6 rounded-sm bg-cyan-400/10 flex items-center justify-center text-[10px] font-bold text-cyan-400">
          {(user.name || user.email || "U")[0].toUpperCase()}
        </div>
        <span className="hidden lg:inline">{(user.name || user.email || "").split("@")[0]}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          data-testid="user-dropdown"
          className="absolute right-0 top-full mt-2 w-52 rounded-sm py-1.5 shadow-2xl z-50 animate-fade-in"
          style={{ background: "#0a0a0c", border: "1px solid #1a1a1e" }}
        >
          {/* User info */}
          <div className="px-3.5 py-2.5 mb-1" style={{ borderBottom: "1px solid #1a1a1e" }}>
            <p className="text-[11px] font-mono text-zinc-300 truncate">{user.name || "Operator"}</p>
            <p className="text-[10px] font-mono text-zinc-600 truncate">{user.email}</p>
          </div>

          {/* Menu items */}
          {menuItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              data-testid={`menu-${item.label.toLowerCase().replace(/\s/g, "-")}`}
              className={`flex items-center gap-2.5 px-3.5 py-2 text-[11px] font-mono tracking-wide transition-all ${
                item.accent
                  ? "text-cyan-400 hover:bg-cyan-400/5"
                  : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.03]"
              }`}
            >
              <item.icon size={13} />
              {item.label}
            </Link>
          ))}

          {/* Sign out */}
          <div style={{ borderTop: "1px solid #1a1a1e", marginTop: "4px", paddingTop: "4px" }}>
            <button
              data-testid="dropdown-logout-btn"
              onClick={() => { logout(); navigate("/"); setOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3.5 py-2 text-[11px] font-mono tracking-wide text-zinc-600 hover:text-red-400 hover:bg-red-500/5 transition-all"
            >
              <LogOut size={13} />
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const activeAgentCount = useAgentCount();

  const isArmory = location.pathname === "/armory";
  const isMyAgents = location.pathname === "/my-agents" || location.pathname.startsWith("/my-agents/");

  const MOBILE_DASHBOARD_LINKS = [
    { to: "/dashboard", label: "Command Center" },
    ...(user?.role === "admin" ? [
      { to: "/overwatch", label: "Overwatch" },
      { to: "/security", label: "Security" },
    ] : []),
  ];

  return (
    <nav
      data-testid="navbar"
      className="sticky top-0 z-50 backdrop-blur-xl"
      style={{ backgroundColor: "var(--bg-nav)", borderBottom: "1px solid var(--border)" }}
    >
      <div className={`${isArmory ? "px-4 lg:px-5" : "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"} flex items-center gap-4 lg:gap-6 h-[52px]`}>
        {/* ── Logo (Left) ── */}
        <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2 group shrink-0">
          <div className="w-[7px] h-[7px] bg-cyan-400" />
          <span className="text-[13px] font-bold tracking-[0.1em] uppercase font-mono t-text whitespace-nowrap">
            Task<span className="text-cyan-400">Force</span>
          </span>
        </Link>

        {/* ── Center Links (Desktop) ── flex-1 distributes remaining width evenly,
            no absolute positioning so the right-side controls never overlap. */}
        <div className="hidden md:flex flex-1 items-center justify-center gap-0.5 lg:gap-1 xl:gap-2 min-w-0">
          {(user?.role === "admin" ? CENTER_LINKS_ADMIN : CENTER_LINKS_PUBLIC).map((link) => {
            const isActive = location.pathname === link.to;
            return (
              <Link
                key={link.to}
                to={link.to}
                data-testid={`nav-link-${link.label.toLowerCase().replace(/\s/g, "-")}`}
                data-active={isActive || undefined}
                className={`relative px-2 lg:px-3 xl:px-4 py-1.5 text-[10px] lg:text-[11px] tracking-[0.08em] lg:tracking-[0.1em] uppercase font-medium font-mono transition-colors duration-200 flex items-center gap-1 lg:gap-1.5 whitespace-nowrap ${
                  isActive
                    ? "text-cyan-400"
                    : "text-zinc-500 hover:text-cyan-400"
                }`}
              >
                {link.accent && <Sparkles size={9} className={isActive ? "text-cyan-400" : "text-cyan-500/60"} />}
                <span>{link.label}</span>
                {link.beta && (
                  <span
                    data-testid={`nav-beta-${link.label.toLowerCase().replace(/\s/g, "-")}`}
                    className="px-1 py-0.5 text-[7px] tracking-[0.1em] font-bold rounded-sm text-cyan-300"
                    style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.35)' }}
                  >
                    BETA
                  </span>
                )}
                {link.soon && (
                  <span
                    className="px-1 py-0.5 text-[7px] tracking-[0.1em] font-bold rounded-sm text-amber-300"
                    style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.3)' }}
                  >
                    SOON
                  </span>
                )}
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="absolute left-2 right-2 lg:left-3 lg:right-3 -bottom-0.5 h-px bg-cyan-400"
                    style={{ boxShadow: "0 0 6px rgba(34,211,238,0.5)" }}
                  />
                )}
              </Link>
            );
          })}
          {/* Prompt 31 Phase 2 — My Agents with active-count badge */}
          {user && (
            <Link
              to="/my-agents"
              data-testid="nav-link-my-agents"
              data-active={isMyAgents || undefined}
              className={`relative px-2 lg:px-3 xl:px-4 py-1.5 text-[10px] lg:text-[11px] tracking-[0.08em] lg:tracking-[0.1em] uppercase font-medium font-mono transition-colors duration-200 flex items-center gap-1 lg:gap-1.5 whitespace-nowrap ${
                isMyAgents ? "text-cyan-400" : "text-zinc-500 hover:text-cyan-400"
              }`}
            >
              <Bot size={11} className={isMyAgents ? "text-cyan-400" : "text-cyan-500/60"} />
              <span>My Agents</span>
              {typeof activeAgentCount === "number" && activeAgentCount > 0 && (
                <span
                  data-testid="nav-my-agents-badge"
                  className="px-1 py-0.5 text-[8px] tracking-[0.08em] font-bold rounded-sm text-cyan-300"
                  style={{ background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.35)" }}
                >
                  {activeAgentCount}
                </span>
              )}
              {isMyAgents && (
                <span
                  className="absolute left-2 right-2 lg:left-3 lg:right-3 -bottom-0.5 h-px bg-cyan-400"
                  style={{ boxShadow: "0 0 6px rgba(34,211,238,0.5)" }}
                />
              )}
            </Link>
          )}
        </div>

        {/* ── Right Side (Desktop) ── */}
        <div className="hidden md:flex items-center gap-2 lg:gap-3 shrink-0">
          <button
            data-testid="theme-toggle-btn"
            onClick={toggle}
            className="w-8 h-8 flex items-center justify-center text-zinc-600 hover:text-cyan-400 transition-colors"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>

          {user ? (
            <>
              <CreditCounter />
              <NotificationBell />
              <UserMenu user={user} logout={logout} navigate={navigate} />
            </>
          ) : (
            <>
              <Link
                to="/login"
                data-testid="login-btn"
                className="text-[11px] tracking-[0.08em] uppercase font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/login"
                data-testid="deploy-now-btn"
                className="px-4 py-1.5 bg-cyan-400 text-black text-[11px] font-bold tracking-[0.1em] uppercase font-mono rounded-sm hover:bg-cyan-300 transition-all"
                style={{ boxShadow: "0 0 16px rgba(34,211,238,0.12)" }}
              >
                Deploy Now
              </Link>
            </>
          )}
        </div>

        {/* ── Mobile Right ── */}
        <div className="md:hidden flex items-center gap-2">
          <button
            data-testid="theme-toggle-mobile"
            onClick={toggle}
            className="w-8 h-8 flex items-center justify-center text-zinc-600 hover:text-cyan-400 transition-colors"
          >
            {isDark ? <Sun size={13} /> : <Moon size={13} />}
          </button>
          <button
            data-testid="mobile-menu-btn"
            className="text-zinc-500 hover:text-cyan-400 transition-colors"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* ── Mobile Menu ── */}
      {mobileOpen && (
        <div
          data-testid="mobile-menu"
          className="md:hidden px-6 py-5 flex flex-col gap-0.5 animate-fade-in"
          style={{ backgroundColor: "var(--bg-nav)", borderTop: "1px solid var(--border)" }}
        >
          {(user?.role === "admin" ? CENTER_LINKS_ADMIN : CENTER_LINKS_PUBLIC).map((link) => (
            <Link key={link.to} to={link.to} onClick={() => setMobileOpen(false)}
              className={`py-2.5 px-3 text-[12px] tracking-[0.1em] uppercase font-mono font-medium rounded-sm transition-all ${
                location.pathname === link.to ? "text-cyan-400 bg-cyan-400/5" : "text-zinc-500"
              }`}>
              {link.label}
            </Link>
          ))}
          {/* Prompt 31 Phase 2 — My Agents in mobile nav */}
          {user && (
            <Link
              to="/my-agents"
              data-testid="nav-link-my-agents-mobile"
              onClick={() => setMobileOpen(false)}
              className={`py-2.5 px-3 text-[12px] tracking-[0.1em] uppercase font-mono font-medium rounded-sm transition-all flex items-center justify-between ${
                isMyAgents ? "text-cyan-400 bg-cyan-400/5" : "text-zinc-500"
              }`}
            >
              <span className="flex items-center gap-2"><Bot size={12} /> My Agents</span>
              {typeof activeAgentCount === "number" && activeAgentCount > 0 && (
                <span className="px-1.5 py-0.5 text-[9px] font-bold rounded-sm text-cyan-300"
                      style={{ background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.35)" }}>
                  {activeAgentCount}
                </span>
              )}
            </Link>
          )}

          {/* Dashboard links for logged-in mobile users */}
          {user && (
            <>
              <div className="mt-2 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
                <p className="text-[9px] font-mono tracking-[0.2em] uppercase text-zinc-600 px-3 mb-1">Command Center</p>
              </div>
              {MOBILE_DASHBOARD_LINKS.map((link) => (
                <Link key={link.to} to={link.to} onClick={() => setMobileOpen(false)}
                  className={`py-2.5 px-3 text-[12px] tracking-[0.1em] uppercase font-mono font-medium rounded-sm transition-all ${
                    location.pathname === link.to ? "text-cyan-400 bg-cyan-400/5" : "text-zinc-500"
                  }`}>
                  {link.label}
                </Link>
              ))}
            </>
          )}

          <div className="mt-2 pt-3 flex flex-col gap-2" style={{ borderTop: "1px solid var(--border)" }}>
            {user ? (
              <button
                data-testid="mobile-logout-btn"
                onClick={() => { logout(); navigate("/"); setMobileOpen(false); }}
                className="text-[12px] tracking-[0.08em] uppercase font-mono text-zinc-500 text-left py-2 px-3"
              >
                Sign Out
              </button>
            ) : (
              <>
                <Link to="/login" onClick={() => setMobileOpen(false)} className="text-[12px] tracking-[0.08em] uppercase font-mono text-zinc-500 py-2 px-3">Sign In</Link>
                <Link to="/login" onClick={() => setMobileOpen(false)} className="text-center py-2.5 bg-cyan-400 text-black text-[11px] font-bold tracking-[0.1em] uppercase font-mono rounded-sm mt-1">Deploy Now</Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useTheme } from "@/lib/theme";
import { Menu, X, Sun, Moon, ChevronDown, LayoutDashboard, BarChart3, Shield, LogOut, Coins, Rocket, Sparkles, Package, Server } from "lucide-react";
import { useState, useRef, useEffect } from "react";

const CENTER_LINKS_PUBLIC = [
  { to: "/build", label: "Build", accent: true },
  { to: "/exchange", label: "The Exchange" },
  { to: "/bounties", label: "Bounty Board" },
  { to: "/armory", label: "The Armory", soon: true },
  { to: "/leaderboard", label: "Leaderboard", soon: true },
  { to: "/academy", label: "Academy", soon: true },
  { to: "/pricing", label: "Pricing" },
];

const CENTER_LINKS_ADMIN = [
  { to: "/build", label: "Build", accent: true },
  { to: "/exchange", label: "The Exchange" },
  { to: "/bounties", label: "Bounty Board" },
  { to: "/armory", label: "The Armory" },
  { to: "/leaderboard", label: "Leaderboard", soon: true },
  { to: "/academy", label: "Academy" },
  { to: "/pricing", label: "Pricing" },
];

function UserMenu({ user, logout, navigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const menuItems = [
    { to: "/dashboard", label: "Command Center", icon: LayoutDashboard },
    { to: "/credits", label: "Credits", icon: Coins },
    { to: "/my-deployments", label: "My Deployments", icon: Rocket },
    { to: "/external-agents", label: "External Agents", icon: Package },
    { to: "/hosting", label: "Hosting Plans", icon: Server },
    ...(isAdmin ? [
      { to: "/overwatch", label: "Overwatch", icon: BarChart3, accent: true },
      { to: "/security", label: "Security", icon: Shield },
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

  const isArmory = location.pathname === "/armory";

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
      <div className={`${isArmory ? "px-5" : "max-w-7xl mx-auto px-6 lg:px-8"} flex items-center justify-between h-[52px]`}>
        {/* ── Logo ── */}
        <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2 group shrink-0">
          <div className="w-[7px] h-[7px] bg-cyan-400" />
          <span className="text-[13px] font-bold tracking-[0.1em] uppercase font-mono t-text">
            Task<span className="text-cyan-400">Force</span>
          </span>
          <span
            data-testid="beta-badge"
            className="ml-1 px-1.5 py-0.5 text-[8px] font-bold tracking-[0.15em] uppercase font-mono rounded-sm text-cyan-300"
            style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.35)' }}
          >
            Beta
          </span>
        </Link>

        {/* ── Center Links (Desktop) ── */}
        <div className="hidden md:flex items-center gap-0.5 absolute left-1/2 -translate-x-1/2">
          {(user?.role === "admin" ? CENTER_LINKS_ADMIN : CENTER_LINKS_PUBLIC).map((link) => (
            <Link
              key={link.to}
              to={link.to}
              data-testid={`nav-link-${link.label.toLowerCase().replace(/\s/g, "-")}`}
              className={`px-3.5 py-1.5 text-[11px] tracking-[0.1em] uppercase font-medium font-mono transition-all duration-200 flex items-center gap-1.5 ${
                link.accent
                  ? (location.pathname === link.to ? "text-cyan-300 font-bold" : "text-cyan-400 hover:text-cyan-300 font-bold")
                  : (location.pathname === link.to ? "text-cyan-400" : "text-zinc-500 hover:text-cyan-400")
              }`}
            >
              {link.accent && <Sparkles size={9} className="text-cyan-400" />}
              {link.label}
              {link.soon && (
                <span
                  className="px-1 py-0.5 text-[7px] tracking-[0.1em] font-bold rounded-sm text-amber-300"
                  style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.3)' }}
                >
                  SOON
                </span>
              )}
              {link.accent && (
                <span
                  className="px-1 py-0.5 text-[7px] tracking-[0.1em] font-bold rounded-sm text-cyan-300"
                  style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.35)' }}
                >
                  NEW
                </span>
              )}
            </Link>
          ))}
        </div>

        {/* ── Right Side (Desktop) ── */}
        <div className="hidden md:flex items-center gap-3 shrink-0">
          <button
            data-testid="theme-toggle-btn"
            onClick={toggle}
            className="w-8 h-8 flex items-center justify-center text-zinc-600 hover:text-cyan-400 transition-colors"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>

          {user ? (
            <UserMenu user={user} logout={logout} navigate={navigate} />
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

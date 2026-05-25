import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useTheme } from "@/lib/theme";
import { Menu, X, Sun, Moon } from "lucide-react";
import { useState } from "react";

const baseNavLinks = [
  { to: "/", label: "Home" },
  { to: "/academy", label: "Academy" },
  { to: "/pricing", label: "Pricing" },
  { to: "/exchange", label: "The Exchange" },
  { to: "/armory", label: "The Armory" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isStudio = location.pathname === "/armory";
  const isAdmin = user?.role === "admin";
  const navLinks = user
    ? [...baseNavLinks, { to: "/creator", label: "Creator" }, { to: "/dashboard", label: "Dashboard" }, ...(isAdmin ? [{ to: "/security", label: "Security" }] : [])]
    : baseNavLinks;

  return (
    <nav
      data-testid="navbar"
      className="sticky top-0 z-50 backdrop-blur-xl"
      style={{ backgroundColor: 'var(--bg-nav)', borderBottom: '1px solid var(--border)' }}
    >
      <div className={`${isStudio ? 'px-5' : 'max-w-7xl mx-auto px-6 lg:px-8'} flex items-center justify-between h-[56px]`}>
        {/* Logo */}
        <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2 group">
          <div className="w-2 h-2 bg-cyan-400 rounded-none" />
          <span className="text-[14px] font-bold tracking-[0.06em] uppercase t-text font-mono">
            Task<span className="text-cyan-400">Force</span>
          </span>
        </Link>

        {/* Desktop Links */}
        <div className="hidden md:flex items-center gap-0.5">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              data-testid={`nav-link-${link.label.toLowerCase().replace(/\s/g, '-')}`}
              className={`px-3 py-1.5 text-[12px] tracking-wide uppercase font-medium rounded-sm transition-all duration-200 ${
                location.pathname === link.to
                  ? "text-cyan-400 bg-cyan-400/5"
                  : "t-text-mute hover:text-cyan-400 hover:bg-cyan-400/5"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Right side */}
        <div className="hidden md:flex items-center gap-3">
          <button data-testid="theme-toggle-btn" onClick={toggle} className="theme-toggle" aria-label="Toggle theme">
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          {user ? (
            <button data-testid="logout-btn" onClick={() => { logout(); navigate("/"); }} className="text-[12px] tracking-wide uppercase t-text-mute hover:text-cyan-400 transition-colors">
              Log out
            </button>
          ) : (
            <>
              <Link to="/login" data-testid="login-btn" className="text-[12px] tracking-wide uppercase t-text-mute hover:text-cyan-400 transition-colors">
                Log in
              </Link>
              <Link to="/#waitlist" data-testid="join-waitlist-nav-btn" className="px-4 py-1.5 bg-cyan-400 text-black text-[12px] font-bold tracking-wide uppercase rounded-sm hover:bg-cyan-300 transition-all">
                Enlist
              </Link>
            </>
          )}
        </div>

        {/* Mobile */}
        <div className="md:hidden flex items-center gap-2">
          <button data-testid="theme-toggle-mobile" onClick={toggle} className="theme-toggle" style={{ width: 30, height: 30 }}>
            {isDark ? <Sun size={13} /> : <Moon size={13} />}
          </button>
          <button data-testid="mobile-menu-btn" className="t-text-mute hover:text-cyan-400" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div data-testid="mobile-menu" className="md:hidden backdrop-blur-xl px-6 py-4 flex flex-col gap-0.5 animate-fade-in" style={{ backgroundColor: 'var(--bg-nav)', borderTop: '1px solid var(--border)' }}>
          {navLinks.map((link) => (
            <Link key={link.to} to={link.to} onClick={() => setMobileOpen(false)}
              className={`py-2 px-3 text-[12px] tracking-wide uppercase font-medium rounded-sm transition-all ${location.pathname === link.to ? "text-cyan-400 bg-cyan-400/5" : "t-text-mute"}`}>
              {link.label}
            </Link>
          ))}
          <div className="mt-2 pt-3 flex flex-col gap-2" style={{ borderTop: '1px solid var(--border)' }}>
            {user ? (
              <button data-testid="mobile-logout-btn" onClick={() => { logout(); navigate("/"); setMobileOpen(false); }} className="text-[12px] tracking-wide uppercase t-text-mute text-left py-2 px-3">
                Log out
              </button>
            ) : (
              <>
                <Link to="/login" onClick={() => setMobileOpen(false)} className="text-[12px] tracking-wide uppercase t-text-mute py-2 px-3">Log in</Link>
                <Link to="/#waitlist" onClick={() => setMobileOpen(false)} className="text-center py-2 bg-cyan-400 text-black text-[12px] font-bold tracking-wide uppercase rounded-sm mt-1">Enlist</Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

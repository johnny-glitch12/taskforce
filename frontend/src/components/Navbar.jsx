import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useTheme } from "@/lib/theme";
import { Menu, X, Sun, Moon } from "lucide-react";
import { useState } from "react";

const baseNavLinks = [
  { to: "/", label: "Home" },
  { to: "/academy", label: "Academy" },
  { to: "/pricing", label: "Pricing" },
  { to: "/marketplace", label: "Marketplace" },
  { to: "/studio", label: "Studio" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isStudio = location.pathname === "/studio";
  const isAdmin = user?.role === "admin";
  const navLinks = user
    ? [...baseNavLinks, { to: "/dashboard", label: "Dashboard" }, ...(isAdmin ? [{ to: "/security", label: "Security" }] : [])]
    : baseNavLinks;

  return (
    <nav
      data-testid="navbar"
      className="sticky top-0 z-50 backdrop-blur-xl t-border"
      style={{ backgroundColor: 'var(--bg-nav)', borderBottom: '1px solid var(--border)' }}
    >
      <div className={`${isStudio ? 'px-5' : 'max-w-7xl mx-auto px-6 lg:px-8'} flex items-center justify-between h-[60px]`}>
        {/* Logo */}
        <Link to="/" data-testid="navbar-logo" className="flex items-center group">
          <span className="text-[15px] font-semibold tracking-[0.08em] t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
            nova<span className="text-[#8B5CF6]">.</span>ai
          </span>
        </Link>

        {/* Desktop Links */}
        <div className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              data-testid={`nav-link-${link.label.toLowerCase()}`}
              className={`px-4 py-2 text-[13px] rounded-lg transition-all duration-200 ${
                location.pathname === link.to
                  ? "t-text"
                  : "t-text-sub hover:t-text"
              }`}
              style={location.pathname === link.to ? { background: 'var(--bg-card-hover)' } : {}}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Right side: Theme toggle + Auth */}
        <div className="hidden md:flex items-center gap-3">
          <button
            data-testid="theme-toggle-btn"
            onClick={toggle}
            className="theme-toggle"
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
          </button>

          {user ? (
            <button
              data-testid="logout-btn"
              onClick={() => { logout(); navigate("/"); }}
              className="text-[13px] t-text-sub hover:t-text transition-colors duration-200"
            >
              Log out
            </button>
          ) : (
            <>
              <Link to="/login" data-testid="login-btn" className="text-[13px] t-text-sub hover:t-text transition-colors duration-200">
                Log in
              </Link>
              <Link
                to="/#waitlist"
                data-testid="join-waitlist-nav-btn"
                className="px-5 py-2 bg-[#8B5CF6] text-white text-[13px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_30px_rgba(139,92,246,0.4)]"
              >
                Join Waitlist
              </Link>
            </>
          )}
        </div>

        {/* Mobile: Theme toggle + Hamburger */}
        <div className="md:hidden flex items-center gap-2">
          <button data-testid="theme-toggle-mobile" onClick={toggle} className="theme-toggle" style={{ width: 32, height: 32 }}>
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <button
            data-testid="mobile-menu-btn"
            className="t-text-sub hover:t-text"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div
          data-testid="mobile-menu"
          className="md:hidden backdrop-blur-xl px-6 py-5 flex flex-col gap-1 animate-fade-in"
          style={{ backgroundColor: 'var(--bg-nav)', borderTop: '1px solid var(--border)' }}
        >
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={`py-2.5 px-3 text-sm rounded-lg transition-all ${
                location.pathname === link.to ? "t-text" : "t-text-sub"
              }`}
              style={location.pathname === link.to ? { background: 'var(--bg-card-hover)' } : {}}
            >
              {link.label}
            </Link>
          ))}
          <div className="mt-2 pt-3 flex flex-col gap-2" style={{ borderTop: '1px solid var(--border)' }}>
            {user ? (
              <button
                data-testid="mobile-logout-btn"
                onClick={() => { logout(); navigate("/"); setMobileOpen(false); }}
                className="text-sm t-text-sub text-left py-2 px-3"
              >
                Log out
              </button>
            ) : (
              <>
                <Link to="/login" onClick={() => setMobileOpen(false)} className="text-sm t-text-sub py-2 px-3">
                  Log in
                </Link>
                <Link
                  to="/#waitlist"
                  onClick={() => setMobileOpen(false)}
                  className="text-center py-2.5 bg-[#8B5CF6] text-white text-sm font-medium rounded-full mt-1"
                >
                  Join Waitlist
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

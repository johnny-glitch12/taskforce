import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { useTheme } from "@/lib/theme";
import { Menu, X, Sun, Moon } from "lucide-react";
import { useState } from "react";

const CENTER_LINKS = [
  { to: "/exchange", label: "The Exchange" },
  { to: "/armory", label: "The Armory" },
  { to: "/academy", label: "Academy" },
  { to: "/pricing", label: "Pricing" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isArmory = location.pathname === "/armory";

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
        </Link>

        {/* ── Center Links (Desktop) ── */}
        <div className="hidden md:flex items-center gap-0.5 absolute left-1/2 -translate-x-1/2">
          {CENTER_LINKS.map((link) => {
            const isActive = location.pathname === link.to;
            return (
              <Link
                key={link.to}
                to={link.to}
                data-testid={`nav-link-${link.label.toLowerCase().replace(/\s/g, "-")}`}
                className={`px-3.5 py-1.5 text-[11px] tracking-[0.1em] uppercase font-medium font-mono transition-all duration-200 ${
                  isActive
                    ? "text-cyan-400"
                    : "text-zinc-500 hover:text-cyan-400"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>

        {/* ── Right Side (Desktop) ── */}
        <div className="hidden md:flex items-center gap-4 shrink-0">
          <button
            data-testid="theme-toggle-btn"
            onClick={toggle}
            className="w-8 h-8 flex items-center justify-center text-zinc-600 hover:text-cyan-400 transition-colors"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>

          {user ? (
            <button
              data-testid="logout-btn"
              onClick={() => { logout(); navigate("/"); }}
              className="text-[11px] tracking-[0.08em] uppercase font-mono text-zinc-500 hover:text-cyan-400 transition-colors"
            >
              Sign Out
            </button>
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
          {CENTER_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={`py-2.5 px-3 text-[12px] tracking-[0.1em] uppercase font-mono font-medium rounded-sm transition-all ${
                location.pathname === link.to ? "text-cyan-400 bg-cyan-400/5" : "text-zinc-500"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <div className="mt-3 pt-3 flex flex-col gap-2" style={{ borderTop: "1px solid var(--border)" }}>
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
                <Link to="/login" onClick={() => setMobileOpen(false)} className="text-[12px] tracking-[0.08em] uppercase font-mono text-zinc-500 py-2 px-3">
                  Sign In
                </Link>
                <Link
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="text-center py-2.5 bg-cyan-400 text-black text-[11px] font-bold tracking-[0.1em] uppercase font-mono rounded-sm mt-1"
                >
                  Deploy Now
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

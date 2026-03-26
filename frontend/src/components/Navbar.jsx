import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { Menu, X } from "lucide-react";
import { useState } from "react";

const LOGO_URL = "https://customer-assets.emergentagent.com/job_1f4bc532-c54c-43b5-acf6-c5b708fa0240/artifacts/cgt08cfq_5c02db2b-7f75-40a2-85d0-f16bbaecf95b.png";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/academy", label: "Academy" },
  { to: "/marketplace", label: "Marketplace" },
  { to: "/studio", label: "Studio" },
];

export default function Navbar() {
  const { isAdmin, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isStudio = location.pathname === "/studio";

  return (
    <nav
      data-testid="navbar"
      className="sticky top-0 z-50 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-900"
    >
      <div className={`${isStudio ? 'px-4' : 'max-w-7xl mx-auto px-6 lg:px-8'} flex items-center justify-between h-16`}>
        {/* Logo */}
        <Link
          to="/"
          data-testid="navbar-logo"
          className="flex items-center gap-3 group"
        >
          <img
            src={LOGO_URL}
            alt="Nova AI"
            className="h-8 w-8 invert transition-transform duration-300 group-hover:scale-110"
          />
          <span className="text-white font-bold text-lg tracking-wide" style={{ fontFamily: "'Outfit', sans-serif" }}>
            NOVA AI
          </span>
        </Link>

        {/* Desktop Links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              data-testid={`nav-link-${link.label.toLowerCase()}`}
              className={`text-xs font-mono uppercase tracking-[0.2em] transition-colors duration-200 ${
                location.pathname === link.to
                  ? "text-[#00E5FF]"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Auth Buttons */}
        <div className="hidden md:flex items-center gap-4">
          {isAdmin ? (
            <button
              data-testid="logout-btn"
              onClick={() => {
                logout();
                navigate("/");
              }}
              className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-400 hover:text-white transition-colors duration-200"
            >
              Log Out
            </button>
          ) : (
            <>
              <Link
                to="/login"
                data-testid="login-btn"
                className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-400 hover:text-white transition-colors duration-200"
              >
                Log In
              </Link>
              <Link
                to="/#waitlist"
                data-testid="join-waitlist-nav-btn"
                className="px-5 py-2 bg-[#00E5FF] text-black text-xs font-semibold uppercase tracking-wider hover:bg-[#B900FF] hover:text-white transition-all duration-300 shadow-[0_0_15px_rgba(0,229,255,0.2)] hover:shadow-[0_0_20px_rgba(185,0,255,0.5)]"
              >
                Join Waitlist
              </Link>
            </>
          )}
        </div>

        {/* Mobile Hamburger */}
        <button
          data-testid="mobile-menu-btn"
          className="md:hidden text-zinc-400 hover:text-white"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div
          data-testid="mobile-menu"
          className="md:hidden bg-zinc-950 border-t border-zinc-900 px-6 py-6 flex flex-col gap-4 animate-fade-in"
        >
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={`text-sm font-mono uppercase tracking-[0.15em] ${
                location.pathname === link.to
                  ? "text-[#00E5FF]"
                  : "text-zinc-400"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <div className="border-t border-zinc-900 pt-4 flex flex-col gap-3">
            {isAdmin ? (
              <button
                data-testid="mobile-logout-btn"
                onClick={() => {
                  logout();
                  navigate("/");
                  setMobileOpen(false);
                }}
                className="text-sm font-mono uppercase tracking-[0.15em] text-zinc-400 text-left"
              >
                Log Out
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="text-sm font-mono uppercase tracking-[0.15em] text-zinc-400"
                >
                  Log In
                </Link>
                <Link
                  to="/#waitlist"
                  onClick={() => setMobileOpen(false)}
                  className="inline-block text-center px-5 py-2 bg-[#00E5FF] text-black text-xs font-semibold uppercase tracking-wider"
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

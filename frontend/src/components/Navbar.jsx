import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { Menu, X } from "lucide-react";
import { useState } from "react";

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
      className="sticky top-0 z-50 bg-zinc-950/70 backdrop-blur-xl border-b border-white/[0.06]"
    >
      <div className={`${isStudio ? 'px-5' : 'max-w-7xl mx-auto px-6 lg:px-8'} flex items-center justify-between h-[60px]`}>
        {/* Logo - Text only */}
        <Link
          to="/"
          data-testid="navbar-logo"
          className="flex items-center group"
        >
          <span
            className="text-white text-[15px] font-semibold tracking-[0.08em]"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
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
                  ? "text-white bg-white/[0.06]"
                  : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04]"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Auth Buttons */}
        <div className="hidden md:flex items-center gap-3">
          {isAdmin ? (
            <button
              data-testid="logout-btn"
              onClick={() => {
                logout();
                navigate("/");
              }}
              className="text-[13px] text-zinc-500 hover:text-white transition-colors duration-200"
            >
              Log out
            </button>
          ) : (
            <>
              <Link
                to="/login"
                data-testid="login-btn"
                className="text-[13px] text-zinc-500 hover:text-white transition-colors duration-200"
              >
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
          className="md:hidden bg-zinc-950/95 backdrop-blur-xl border-t border-white/[0.06] px-6 py-5 flex flex-col gap-1 animate-fade-in"
        >
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={`py-2.5 px-3 text-sm rounded-lg transition-all ${
                location.pathname === link.to
                  ? "text-white bg-white/[0.06]"
                  : "text-zinc-500"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <div className="border-t border-white/[0.06] mt-2 pt-3 flex flex-col gap-2">
            {isAdmin ? (
              <button
                data-testid="mobile-logout-btn"
                onClick={() => {
                  logout();
                  navigate("/");
                  setMobileOpen(false);
                }}
                className="text-sm text-zinc-500 text-left py-2 px-3"
              >
                Log out
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="text-sm text-zinc-500 py-2 px-3"
                >
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

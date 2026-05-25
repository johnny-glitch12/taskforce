import { Link } from "react-router-dom";

const ECOSYSTEM = [
  { to: "/exchange", label: "The Exchange" },
  { to: "/armory", label: "The Armory" },
  { to: "/academy", label: "Academy" },
];

const COMPANY = [
  { href: "mailto:abbasinidhal@gmail.com", label: "Contact Us" },
  { href: "#", label: "Founders", badge: "COMING SOON" },
];

const LEGAL = [
  { href: "#", label: "Terms of Service" },
  { href: "#", label: "Privacy Policy" },
];

function FooterLink({ to, href, label, badge }) {
  const cls = "text-[12px] text-zinc-500 hover:text-cyan-400 transition-colors duration-200 flex items-center gap-2";

  if (to) {
    return (
      <Link to={to} data-testid={`footer-link-${label.toLowerCase().replace(/\s/g, "-")}`} className={cls}>
        {label}
        {badge && <Badge text={badge} />}
      </Link>
    );
  }

  return (
    <a href={href} data-testid={`footer-link-${label.toLowerCase().replace(/\s/g, "-")}`} className={cls}>
      {label}
      {badge && <Badge text={badge} />}
    </a>
  );
}

function Badge({ text }) {
  return (
    <span className="text-[10px] bg-zinc-900 text-cyan-400 px-1.5 py-0.5 rounded-sm font-mono leading-none">
      {text}
    </span>
  );
}

export default function Footer() {
  return (
    <footer
      data-testid="footer"
      className="bg-black px-6 lg:px-8 pt-14 pb-8"
      style={{ borderTop: "1px solid #1a1a1e" }}
    >
      <div className="max-w-7xl mx-auto">
        {/* ── Main Grid ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-12">
          {/* Brand Column */}
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-[7px] h-[7px] bg-cyan-400" />
              <span className="text-[13px] font-bold tracking-[0.1em] uppercase font-mono text-zinc-200">
                Task<span className="text-cyan-400">Force</span>
              </span>
            </div>
            <p className="text-[12px] text-zinc-600 leading-relaxed max-w-[200px]">
              Build, deploy, and monetize autonomous AI agents.
            </p>
          </div>

          {/* Ecosystem */}
          <div>
            <h4
              data-testid="footer-col-ecosystem"
              className="text-[10px] tracking-[0.2em] uppercase font-mono text-zinc-400 mb-4 font-semibold"
            >
              Ecosystem
            </h4>
            <div className="flex flex-col gap-3">
              {ECOSYSTEM.map((item) => (
                <FooterLink key={item.label} to={item.to} label={item.label} />
              ))}
            </div>
          </div>

          {/* Company */}
          <div>
            <h4
              data-testid="footer-col-company"
              className="text-[10px] tracking-[0.2em] uppercase font-mono text-zinc-400 mb-4 font-semibold"
            >
              Company
            </h4>
            <div className="flex flex-col gap-3">
              {COMPANY.map((item) => (
                <FooterLink key={item.label} href={item.href} label={item.label} badge={item.badge} />
              ))}
            </div>
          </div>

          {/* Legal */}
          <div>
            <h4
              data-testid="footer-col-legal"
              className="text-[10px] tracking-[0.2em] uppercase font-mono text-zinc-400 mb-4 font-semibold"
            >
              Legal
            </h4>
            <div className="flex flex-col gap-3">
              {LEGAL.map((item) => (
                <FooterLink key={item.label} href={item.href} label={item.label} />
              ))}
            </div>
          </div>
        </div>

        {/* ── Bottom Bar ── */}
        <div className="pt-6" style={{ borderTop: "1px solid #18181b" }}>
          <p
            data-testid="footer-copyright"
            className="text-[10px] font-mono tracking-wide text-zinc-700"
          >
            &copy; 2026 TASK FORCE AI DEVELOPMENT SERVICES L.L.C. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}

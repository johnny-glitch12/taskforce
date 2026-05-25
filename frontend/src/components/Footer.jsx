export default function Footer() {
  return (
    <footer data-testid="footer" className="t-bg px-6 lg:px-8 py-6" style={{ borderTop: '1px solid var(--border)' }}>
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-1.5 h-1.5 bg-cyan-400" />
              <span className="text-[11px] font-bold tracking-[0.08em] uppercase font-mono t-text">
                Task<span className="text-cyan-400">Force</span> AI
              </span>
            </div>
            <p className="text-[10px] t-text-dim tracking-wide">
              Operated by TASK FORCE AI DEVELOPMENT SERVICES L.L.C.
            </p>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" data-testid="footer-terms-link" className="text-[11px] t-text-dim tracking-wide uppercase hover:text-cyan-400 transition-colors">
              Terms of Service
            </a>
            <a href="#" data-testid="footer-enterprise-link" className="text-[11px] t-text-dim tracking-wide uppercase hover:text-cyan-400 transition-colors">
              Enterprise Contact
            </a>
            <a href="mailto:abbasinidhal@gmail.com" data-testid="footer-contact-link" className="text-[11px] t-text-dim tracking-wide hover:text-cyan-400 transition-colors">
              abbasinidhal@gmail.com
            </a>
          </div>
        </div>
        <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
          <p className="text-[10px] t-text-dim">&copy; 2026 Task Force AI Development Services L.L.C. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

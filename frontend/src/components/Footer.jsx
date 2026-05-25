export default function Footer() {
  return (
    <footer
      data-testid="footer"
      className="t-bg px-6 lg:px-8 py-5"
      style={{ borderTop: '1px solid var(--border)' }}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-[12px] t-text-dim tracking-wide">
          &copy; 2026 Nova AI
        </span>
        <a
          href="mailto:abbasinidhal@gmail.com"
          data-testid="footer-contact-link"
          className="text-[12px] t-text-dim tracking-wide hover:text-[#A78BFA] transition-colors duration-200"
        >
          abbasinidhal@gmail.com
        </a>
      </div>
    </footer>
  );
}

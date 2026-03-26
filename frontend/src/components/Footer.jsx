export default function Footer() {
  return (
    <footer
      data-testid="footer"
      className="border-t border-zinc-900 bg-zinc-950 px-6 lg:px-8 py-6"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-xs font-mono text-zinc-500 tracking-wider">
          &copy; 2026 Nova AI
        </span>
        <a
          href="mailto:abbasinidhal@gmail.com"
          data-testid="footer-contact-link"
          className="text-xs font-mono text-zinc-500 tracking-wider hover:text-[#00E5FF] transition-colors duration-200"
        >
          Contact: abbasinidhal@gmail.com
        </a>
      </div>
    </footer>
  );
}

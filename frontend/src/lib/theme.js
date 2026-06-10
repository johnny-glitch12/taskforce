import { createContext, useContext, useState, useEffect } from "react";

const ThemeContext = createContext(null);

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    // Key "nova_theme" must match the pre-paint script in public/index.html.
    const stored = localStorage.getItem("nova_theme");
    if (stored) return stored;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    localStorage.setItem("nova_theme", theme);
  }, [theme]);

  // Listen for system changes when no stored preference
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handler = (e) => {
      if (!localStorage.getItem("nova_theme")) {
        setTheme(e.matches ? "light" : "dark");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  const isDark = theme === "dark";

  return (
    <ThemeContext.Provider value={{ theme, toggle, isDark }}>
      {children}
    </ThemeContext.Provider>
  );
}

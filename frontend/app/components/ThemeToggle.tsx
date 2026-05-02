"use client";

import { useState, useEffect } from "react";

export function getTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return (document.documentElement.dataset.theme as "dark" | "light") ?? "dark";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setTheme(getTheme());
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
    setTheme(next);
    window.dispatchEvent(new CustomEvent("theme-change", { detail: next }));
  };

  return (
    <button className="btn theme-toggle" onClick={toggle} aria-label="Toggle theme" title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}

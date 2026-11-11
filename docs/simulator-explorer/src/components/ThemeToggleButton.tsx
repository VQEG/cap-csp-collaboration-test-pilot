import { Moon, Sun } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const THEME_STORAGE_KEY = "simulator-explorer-theme";

/** Switches between light and dark. The initial theme is set in index.html before the first paint. */
export function ThemeToggleButton() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  function toggleTheme() {
    const nextDark = !dark;
    document.documentElement.classList.toggle("dark", nextDark);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextDark ? "dark" : "light");
    } catch {
      // Storage can be blocked; the toggle still works for this visit.
    }
    setDark(nextDark);
  }

  return (
    <Button variant="outline" size="sm" onClick={toggleTheme} aria-label="Toggle theme">
      {dark ? <Sun /> : <Moon />} {dark ? "Light" : "Dark"}
    </Button>
  );
}

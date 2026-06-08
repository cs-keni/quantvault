import { create } from "zustand";

export type Theme = "dark" | "light";

const themeKey = "qv-theme";

function getStoredTheme(): Theme {
  if (typeof window === "undefined") {
    return "dark";
  }

  const stored = window.localStorage.getItem(themeKey);
  return stored === "light" ? "light" : "dark";
}

function applyTheme(theme: Theme): void {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = theme;
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(themeKey, theme);
  }
}

export interface ThemeState {
  theme: Theme;
  setTheme(theme: Theme): void;
  toggleTheme(): void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: getStoredTheme(),

  setTheme(theme) {
    applyTheme(theme);
    set({ theme });
  },

  toggleTheme() {
    const nextTheme = get().theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    set({ theme: nextTheme });
  },
}));

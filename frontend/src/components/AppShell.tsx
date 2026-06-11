import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion, type Transition } from "framer-motion";
import {
  BarChart3,
  Check,
  GitCompare,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Pencil,
  Play,
  Plus,
  Sun,
  TrendingUp,
  Wallet,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { apiClient } from "../services/apiClient";
import { useAuthStore } from "../store/authStore";
import { useThemeStore } from "../store/themeStore";
import type { PortfolioListItem } from "../types/api";

interface NavItem {
  label: string;
  href: (portfolioId: string | null) => string;
  match: (pathname: string) => boolean;
  icon: ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  {
    label: "Dashboard",
    href: (portfolioId) => (portfolioId ? `/dashboard/portfolios/${portfolioId}` : "/dashboard"),
    match: (pathname) => pathname.startsWith("/dashboard"),
    icon: LayoutDashboard,
  },
  {
    label: "Portfolios",
    href: () => "/portfolios/new",
    match: (pathname) => pathname.startsWith("/portfolios/new"),
    icon: Wallet,
  },
  {
    label: "Analysis",
    href: (portfolioId) => (portfolioId ? `/portfolios/${portfolioId}/analysis` : "/portfolios/new"),
    match: (pathname) => pathname.endsWith("/analysis"),
    icon: TrendingUp,
  },
  {
    label: "Monte Carlo",
    href: (portfolioId) => (portfolioId ? `/portfolios/${portfolioId}/simulate` : "/portfolios/new"),
    match: (pathname) => pathname.endsWith("/simulate"),
    icon: BarChart3,
  },
  {
    label: "Backtest",
    href: (portfolioId) => (portfolioId ? `/portfolios/${portfolioId}/backtest` : "/portfolios/new"),
    match: (pathname) => pathname.endsWith("/backtest"),
    icon: Play,
  },
  {
    label: "Compare",
    href: () => "/compare",
    match: (pathname) => pathname.startsWith("/compare"),
    icon: GitCompare,
  },
];

function useViewportWidth() {
  const [width, setWidth] = useState(() => (typeof window === "undefined" ? 1280 : window.innerWidth));

  useEffect(() => {
    function handleResize() {
      setWidth(window.innerWidth);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return width;
}

function selectedPortfolioRoute(pathname: string, portfolioId: string) {
  if (pathname.endsWith("/analysis")) {
    return `/portfolios/${portfolioId}/analysis`;
  }
  if (pathname.endsWith("/simulate")) {
    return `/portfolios/${portfolioId}/simulate`;
  }
  if (pathname.endsWith("/backtest")) {
    return `/portfolios/${portfolioId}/backtest`;
  }
  return `/dashboard/portfolios/${portfolioId}`;
}

function SidebarContent({
  activePortfolioId,
  collapsed,
  onNavigate,
}: {
  activePortfolioId: string | null;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);
  const theme = useThemeStore((state) => state.theme);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);
  const queryClient = useQueryClient();
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [isSavingRename, setIsSavingRename] = useState(false);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const portfoliosQuery = useQuery({
    queryKey: ["portfolios"],
    queryFn: async () => {
      const response = await apiClient.get<PortfolioListItem[]>("/portfolios");
      return response.data;
    },
  });

  const portfolios = portfoliosQuery.data ?? [];
  const fallbackPortfolioId = portfolios[0]?.id ?? null;
  const routePortfolioId = activePortfolioId ?? fallbackPortfolioId;
  const selectedPortfolioId = activePortfolioId ?? "";
  const currentPortfolioName = portfolios.find((p) => p.id === selectedPortfolioId)?.name ?? "";

  function startRenaming() {
    setRenameValue(currentPortfolioName);
    setIsRenaming(true);
    setTimeout(() => renameInputRef.current?.select(), 0);
  }

  async function handleRenameSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = renameValue.trim();
    if (!trimmed || !selectedPortfolioId) {
      setIsRenaming(false);
      return;
    }
    setIsSavingRename(true);
    try {
      await apiClient.patch(`/portfolios/${selectedPortfolioId}`, { name: trimmed });
      await queryClient.invalidateQueries({ queryKey: ["portfolios"] });
    } finally {
      setIsSavingRename(false);
      setIsRenaming(false);
    }
  }

  function handlePortfolioChange(portfolioId: string) {
    if (portfolioId === "") {
      navigate("/portfolios/new");
    } else {
      navigate(selectedPortfolioRoute(location.pathname, portfolioId));
    }
    onNavigate?.();
  }

  function handleLogout() {
    logout();
    navigate("/login");
    onNavigate?.();
  }

  return (
    <div className="flex h-full flex-col bg-sidebar text-ink">
      <div className="border-b border-border p-3">
        <div className="flex h-10 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded border border-border bg-surface text-sm font-bold text-accent">
            QV
          </div>
          {!collapsed ? <span className="text-sm font-semibold">QuantVault</span> : null}
        </div>
        {!collapsed ? (
          <div className="mt-4">
            {isRenaming ? (
              <form className="flex items-center gap-1" onSubmit={handleRenameSubmit}>
                <input
                  ref={renameInputRef}
                  className="h-10 min-w-0 flex-1 rounded-md border border-accent bg-surface px-3 text-sm text-ink outline-none ring-accent/30 focus:ring-4"
                  disabled={isSavingRename}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                />
                <button
                  aria-label="Save name"
                  className="flex h-10 w-9 shrink-0 items-center justify-center rounded-md border border-border text-muted hover:border-accent hover:text-accent disabled:opacity-50"
                  disabled={isSavingRename}
                  type="submit"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button
                  aria-label="Cancel rename"
                  className="flex h-10 w-9 shrink-0 items-center justify-center rounded-md border border-border text-muted hover:border-negative hover:text-negative"
                  type="button"
                  onClick={() => setIsRenaming(false)}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </form>
            ) : (
              <div className="flex items-center gap-1">
                <select
                  aria-label="Portfolio"
                  className="h-10 min-w-0 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-ink outline-none ring-accent/30 focus:border-accent focus:ring-4"
                  value={selectedPortfolioId}
                  onChange={(event) => handlePortfolioChange(event.target.value)}
                >
                  {portfolios.length === 0 ? (
                    <option value="">+ Add portfolio</option>
                  ) : (
                    <>
                      <option value="">+ Add portfolio</option>
                      {portfolios.map((portfolio) => (
                        <option key={portfolio.id} value={portfolio.id}>
                          {portfolio.name}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                {selectedPortfolioId ? (
                  <button
                    aria-label="Rename portfolio"
                    className="flex h-10 w-9 shrink-0 items-center justify-center rounded-md border border-border text-muted hover:border-accent hover:text-accent"
                    type="button"
                    onClick={startRenaming}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            )}
          </div>
        ) : (
          <button
            aria-label="Add portfolio"
            className="mt-4 flex h-10 w-full items-center justify-center rounded-md border border-border text-muted hover:border-accent hover:text-accent"
            type="button"
            onClick={() => handlePortfolioChange("")}
          >
            <Plus className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const active = item.match(location.pathname);
          const Icon = item.icon;
          return (
            <Link
              className={`group relative flex h-10 items-center gap-3 border-l-2 px-3 text-sm font-medium transition ${
                active
                  ? "border-accent bg-accent/10 text-ink"
                  : "border-transparent text-muted hover:bg-surface hover:text-ink"
              } ${collapsed ? "justify-center px-0" : ""}`}
              key={item.label}
              to={item.href(routePortfolioId)}
              onClick={onNavigate}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed ? <span>{item.label}</span> : null}
              {collapsed ? (
                <span className="pointer-events-none absolute left-full z-20 ml-3 hidden whitespace-nowrap border border-border bg-surface px-2 py-1 text-xs text-ink group-hover:block">
                  {item.label}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-border p-2">
        <button
          className={`flex h-10 w-full items-center gap-3 px-3 text-sm font-medium text-muted transition hover:bg-surface hover:text-ink ${
            collapsed ? "justify-center px-0" : ""
          }`}
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {!collapsed ? <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span> : null}
        </button>
        <button
          className={`flex h-10 w-full items-center gap-3 px-3 text-sm font-medium text-muted transition hover:bg-surface hover:text-ink ${
            collapsed ? "justify-center px-0" : ""
          }`}
          type="button"
          onClick={handleLogout}
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
          {!collapsed ? <span>Sign out</span> : null}
        </button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { id, portfolioId } = useParams();
  const width = useViewportWidth();
  const prefersReduced = useReducedMotion();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isMobile = width < 768;
  const collapsed = width < 1024;
  const activePortfolioId = id ?? portfolioId ?? null;
  const sidebarWidth = collapsed ? 64 : 220;
  const transition: Transition = useMemo(() => prefersReduced
    ? { duration: 0 }
    : { type: "spring", stiffness: 300, damping: 30 }, [prefersReduced]);

  const desktopSidebar = useMemo(
    () => (
      <motion.aside
        animate={{ width: sidebarWidth }}
        className="hidden shrink-0 border-r border-border bg-sidebar md:block"
        initial={false}
        transition={transition}
      >
        <SidebarContent activePortfolioId={activePortfolioId} collapsed={collapsed} />
      </motion.aside>
    ),
    [activePortfolioId, collapsed, sidebarWidth, transition],
  );

  return (
    <div className="min-h-screen bg-bg text-ink md:flex">
      {desktopSidebar}

      <header className="flex h-14 items-center justify-between border-b border-border bg-sidebar px-4 md:hidden">
        <button
          aria-label="Open navigation"
          className="rounded-md border border-border p-2 text-muted hover:text-ink"
          type="button"
          onClick={() => setDrawerOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-semibold">QuantVault</span>
        <div className="h-9 w-9" />
      </header>

      <AnimatePresence>
        {drawerOpen ? (
          <motion.div
            animate={{ opacity: 1 }}
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            transition={prefersReduced ? { duration: 0 } : { duration: 0.15 }}
          >
            <motion.aside
              animate={{ x: 0 }}
              className="h-full w-[280px] border-r border-border bg-sidebar"
              exit={{ x: -280 }}
              initial={{ x: -280 }}
              transition={transition}
            >
              <div className="flex h-12 items-center justify-end border-b border-border px-3">
                <button
                  aria-label="Close navigation"
                  className="rounded-md border border-border p-2 text-muted hover:text-ink"
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <SidebarContent
                activePortfolioId={activePortfolioId}
                collapsed={false}
                onNavigate={() => setDrawerOpen(false)}
              />
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className={`min-w-0 flex-1 ${isMobile ? "" : "md:block"}`}>{children}</div>
    </div>
  );
}

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../AppShell";
import { apiClient } from "../../services/apiClient";
import { useAuthStore } from "../../store/authStore";

vi.mock("../../services/apiClient", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const portfolios = [
  { id: "p1", name: "Core", benchmark_ticker: "SPY", holding_count: 3 },
  { id: "p2", name: "Income", benchmark_ticker: "AGG", holding_count: 4 },
];

function setViewport(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
}

function renderShell(initialEntry = "/portfolios/p1/analysis") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/portfolios/:id/analysis"
            element={
              <AppShell>
                <main>Analysis content</main>
              </AppShell>
            }
          />
          <Route
            path="/dashboard/portfolios/:portfolioId"
            element={
              <AppShell>
                <main>Dashboard content</main>
              </AppShell>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: portfolios });
  useAuthStore.setState({
    accessToken: "access",
    authReady: true,
    user: {
      id: "u1",
      email: "demo@quantvault.dev",
      full_name: "Demo User",
      is_active: true,
      default_portfolio_id: "p1",
      created_at: "2026-06-08T00:00:00Z",
    },
  });
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AppShell", () => {
  it("renders the six required nav items", async () => {
    setViewport(1280);
    renderShell();

    await waitFor(() => expect(screen.getByRole("link", { name: /Dashboard/i })).toBeTruthy());

    expect(screen.getByRole("link", { name: /Portfolios/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Analysis/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Monte Carlo/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Backtest/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Compare/i })).toBeTruthy();
  });

  it("highlights the active route", async () => {
    setViewport(1280);
    renderShell();

    const analysisLink = await screen.findByRole("link", { name: /Analysis/i });

    expect(analysisLink.className).toContain("border-accent");
    expect(analysisLink.className).toContain("bg-accent/10");
  });

  it("uses icon-only controls at narrow tablet width", async () => {
    setViewport(900);
    renderShell();

    await waitFor(() => expect(screen.getByRole("button", { name: "Add portfolio" })).toBeTruthy());

    expect(screen.queryByLabelText("Portfolio")).toBeNull();
  });

  it("opens the mobile drawer", async () => {
    setViewport(500);
    renderShell();

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));

    expect(await screen.findByRole("button", { name: "Close navigation" })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /Dashboard/i }).length).toBeGreaterThan(0);
  });
});

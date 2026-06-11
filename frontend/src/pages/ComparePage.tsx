import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { apiClient } from "../services/apiClient";
import type { PortfolioListItem, PortfolioMetricsResponse } from "../types/api";

const metricRows: {
  key: keyof PortfolioMetricsResponse;
  label: string;
  format: (value: unknown) => string;
  higherIsBetter?: boolean;
}[] = [
  { key: "annual_return", label: "Annual return", format: (value) => percent(Number(value)), higherIsBetter: true },
  { key: "annual_volatility", label: "Annual volatility", format: (value) => percent(Number(value)), higherIsBetter: false },
  { key: "sharpe_ratio", label: "Sharpe", format: (value) => Number(value).toFixed(2), higherIsBetter: true },
  { key: "sortino_ratio", label: "Sortino", format: (value) => Number(value).toFixed(2), higherIsBetter: true },
  { key: "var", label: "VaR", format: (value) => percent(Number(value)), higherIsBetter: true },
  { key: "cvar", label: "CVaR", format: (value) => percent(Number(value)), higherIsBetter: true },
  {
    key: "beta",
    label: "Beta",
    format: (value) => (value === null ? "N/A" : Number(value).toFixed(2)),
  },
  { key: "max_drawdown", label: "Max drawdown", format: (value) => percent(Number(value)), higherIsBetter: true },
];

function percent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function ComparePage() {
  const [selectedIds, setSelectedIds] = useState<string[] | null>(null);
  const portfoliosQuery = useQuery({
    queryKey: ["portfolios"],
    queryFn: async () => {
      const response = await apiClient.get<PortfolioListItem[]>("/portfolios");
      return response.data;
    },
  });

  const activeSelectedIds =
    selectedIds ?? portfoliosQuery.data?.slice(0, 2).map((portfolio) => portfolio.id) ?? [];

  const metricsQueries = useQueries({
    queries: activeSelectedIds.map((portfolioId) => ({
      enabled: activeSelectedIds.length >= 2,
      queryKey: ["compareMetrics", portfolioId],
      queryFn: async () => {
        const response = await apiClient.get<PortfolioMetricsResponse>(
          `/analysis/portfolios/${portfolioId}/metrics`,
          { params: { period: "1y" } },
        );
        return response.data;
      },
      retry: 1,
    })),
  });

  function togglePortfolio(portfolioId: string) {
    setSelectedIds((current) => {
      const active = current ?? activeSelectedIds;
      return active.includes(portfolioId)
        ? active.filter((id) => id !== portfolioId)
        : [...active, portfolioId];
    });
  }

  const selectedPortfolios =
    activeSelectedIds
      .map((portfolioId) =>
        portfoliosQuery.data?.find((portfolio) => portfolio.id === portfolioId),
      )
      .filter((portfolio): portfolio is PortfolioListItem => portfolio !== undefined) ?? [];
  const hasMetricError = metricsQueries.some((query) => query.isError);
  const isMetricLoading = metricsQueries.some((query) => query.isLoading);

  return (
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader title="Compare" />

        {portfoliosQuery.isLoading ? (
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <div className="h-14 animate-pulse rounded-lg border border-border bg-surface" key={index} />
            ))}
          </div>
        ) : portfoliosQuery.isError ? (
          <div className="mt-8 rounded-lg border border-negative/20 bg-negative/5 p-4">
            <p className="font-medium text-negative">Unable to load portfolios.</p>
            <button
              className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white"
              type="button"
              onClick={() => void portfoliosQuery.refetch()}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {portfoliosQuery.data?.map((portfolio) => (
              <label
                className={`flex items-center justify-between rounded-lg border p-4 text-sm font-medium transition ${
                  activeSelectedIds.includes(portfolio.id)
                    ? "border-accent bg-accent/5 text-accent"
                    : "border-border bg-surface text-ink"
                }`}
                key={portfolio.id}
              >
                <span>{portfolio.name}</span>
                <input
                  checked={activeSelectedIds.includes(portfolio.id)}
                  className="h-4 w-4 accent-accent"
                  onChange={() => togglePortfolio(portfolio.id)}
                  type="checkbox"
                />
              </label>
            ))}
          </div>
        )}

        {selectedPortfolios.length < 2 ? (
          <div className="mt-8 rounded-lg border border-border bg-surface p-5 text-sm text-muted">
            Select at least two portfolios to compare.
          </div>
        ) : null}

        {selectedPortfolios.length >= 2 && hasMetricError ? (
          <div className="mt-8 rounded-lg border border-negative/20 bg-negative/5 p-4">
            <p className="font-medium text-negative">Unable to load one or more metric sets.</p>
            <button
              className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white"
              type="button"
              onClick={() => metricsQueries.forEach((query) => void query.refetch())}
            >
              Retry
            </button>
          </div>
        ) : null}

        {selectedPortfolios.length >= 2 ? (
          <div className="mt-8 overflow-x-auto rounded-lg border border-border bg-surface">
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <p className="text-xs text-muted">1-year trailing period · green = better</p>
            </div>
            <table className="min-w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-bg">
                  <th className="px-4 py-3 font-semibold text-ink">Metric</th>
                  {selectedPortfolios.map((portfolio) => (
                    <th className="px-4 py-3 font-semibold text-ink" key={portfolio.id}>
                      {portfolio.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metricRows.map((row) => {
                  const rawValues = selectedPortfolios.map((_, index) => {
                    const metrics = metricsQueries[index]?.data;
                    const v = metrics ? metrics[row.key] : null;
                    return typeof v === "number" && !isNaN(v) ? v : null;
                  });
                  const validValues = rawValues.filter((v): v is number => v !== null);
                  const bestValue =
                    row.higherIsBetter !== undefined && validValues.length >= 2
                      ? row.higherIsBetter
                        ? Math.max(...validValues)
                        : Math.min(...validValues)
                      : null;
                  const winnerCount = bestValue !== null ? rawValues.filter((v) => v === bestValue).length : 0;
                  return (
                    <tr className="border-b border-border last:border-0" key={row.key}>
                      <th className="px-4 py-3 font-medium text-muted">{row.label}</th>
                      {selectedPortfolios.map((portfolio, index) => {
                        const metrics = metricsQueries[index]?.data;
                        const rawValue = rawValues[index];
                        const isWinner = winnerCount === 1 && bestValue !== null && rawValue === bestValue;
                        return (
                          <td
                            className={`px-4 py-3 font-mono ${isWinner ? "font-semibold text-positive" : "text-ink"}`}
                            key={portfolio.id}
                          >
                            {isMetricLoading ? (
                              <div className="h-4 w-16 animate-pulse rounded bg-border" />
                            ) : metrics ? (
                              row.format(metrics[row.key])
                            ) : (
                              "N/A"
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}

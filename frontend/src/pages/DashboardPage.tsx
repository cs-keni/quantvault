import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, useNavigate, useParams } from "react-router-dom";

import { axisStyle, chartColors } from "../components/chartConfig";
import { ChartTooltip } from "../components/charts";
import { MetricCard } from "../components/MetricCard";
import { MotionCardGrid } from "../components/MotionCardGrid";
import { PageHeader } from "../components/PageHeader";
import { PeriodToggle, type Period } from "../components/PeriodToggle";
import { SkeletonCard } from "../components/SkeletonCard";
import { apiClient } from "../services/apiClient";
import { useAuthStore } from "../store/authStore";
import type { PortfolioListItem, PortfolioMetricsResponse } from "../types/api";

const metricFormatters = {
  number(value: number) {
    return value.toFixed(2);
  },
  percent(value: number) {
    return `${(value * 100).toFixed(2)}%`;
  },
};

function buildHistogram(returns: number[]) {
  if (returns.length === 0) {
    return [];
  }

  const min = Math.min(...returns);
  const max = Math.max(...returns);
  if (min === max) {
    return [{ bucket: `${(min * 100).toFixed(2)}%`, count: returns.length }];
  }

  const bucketCount = 12;
  const width = (max - min) / bucketCount;
  const buckets = Array.from({ length: bucketCount }, (_, index) => ({
    bucket: `${((min + width * index) * 100).toFixed(1)}%`,
    count: 0,
  }));

  for (const dailyReturn of returns) {
    const index = Math.min(Math.floor((dailyReturn - min) / width), bucketCount - 1);
    buckets[index].count += 1;
  }

  return buckets;
}

export function DashboardPage() {
  const { portfolioId } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [period, setPeriod] = useState<Period>("1y");
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  const portfoliosQuery = useQuery({
    queryKey: ["portfolios"],
    queryFn: async () => {
      const response = await apiClient.get<PortfolioListItem[]>("/portfolios");
      return response.data;
    },
  });

  const defaultPortfolio =
    portfoliosQuery.data?.find((portfolio) => portfolio.id === user?.default_portfolio_id) ??
    portfoliosQuery.data?.[0] ??
    null;
  const activePortfolioId = portfolioId ?? selectedPortfolioId ?? defaultPortfolio?.id ?? null;

  const metricsQuery = useQuery({
    queryKey: ["portfolioMetrics", activePortfolioId, period],
    enabled: activePortfolioId !== null,
    queryFn: async () => {
      const response = await apiClient.get<PortfolioMetricsResponse>(
        `/analysis/portfolios/${activePortfolioId}/metrics`,
        { params: { period } },
      );
      return response.data;
    },
  });

  useEffect(() => {
    if (portfolioId !== undefined || activePortfolioId === null) {
      return;
    }
    navigate(`/dashboard/portfolios/${activePortfolioId}`, { replace: true });
  }, [activePortfolioId, navigate, portfolioId]);

  const selectedPortfolio = portfoliosQuery.data?.find(
    (portfolio) => portfolio.id === activePortfolioId,
  );
  const histogramData = useMemo(
    () => buildHistogram(metricsQuery.data?.daily_returns ?? []),
    [metricsQuery.data?.daily_returns],
  );

  function handlePortfolioChange(portfolioId: string) {
    setSelectedPortfolioId(portfolioId || null);
    if (portfolioId) {
      navigate(`/dashboard/portfolios/${portfolioId}`);
    }
  }

  function handlePeriodChange(nextPeriod: Period) {
    setPeriod(nextPeriod);
  }

  const metrics = metricsQuery.data;

  return (
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <PageHeader
              title="Dashboard"
              subtitle={user?.full_name ? `Signed in as ${user.full_name}` : undefined}
            />
            <h2 className="mt-6 text-xl font-semibold text-ink">
              {selectedPortfolio?.name ?? "Portfolio risk"}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {selectedPortfolio
                ? `${selectedPortfolio.holding_count} holdings - Benchmark ${selectedPortfolio.benchmark_ticker}`
                : "Select a portfolio to view metrics."}
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <select
              className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-medium text-ink outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
              value={activePortfolioId ?? ""}
              onChange={(event) => handlePortfolioChange(event.target.value)}
              disabled={portfoliosQuery.isLoading || portfoliosQuery.isError}
            >
              <option value="">Select portfolio</option>
              {portfoliosQuery.data?.map((portfolio) => (
                <option key={portfolio.id} value={portfolio.id}>
                  {portfolio.name}
                </option>
              ))}
            </select>

            <PeriodToggle value={period} onChange={handlePeriodChange} />
          </div>
        </div>

        {portfoliosQuery.isError ? (
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
        ) : null}

        {portfoliosQuery.isSuccess && portfoliosQuery.data.length === 0 ? (
          <div className="mt-8 rounded-lg border border-border bg-surface p-6">
            <h3 className="text-lg font-semibold text-ink">No portfolios yet</h3>
            <Link
              className="mt-4 inline-flex rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white"
              to="/portfolios/new"
            >
              New portfolio
            </Link>
          </div>
        ) : null}

        {metricsQuery.isLoading || portfoliosQuery.isLoading ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
            {Array.from({ length: 6 }, (_, index) => <SkeletonCard key={index} />)}
          </div>
        ) : metricsQuery.isError ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
            <div className="rounded-lg border border-negative/20 bg-negative/5 p-4 sm:col-span-2 xl:col-span-6">
              <p className="font-medium text-negative">Unable to load portfolio metrics.</p>
              <button
                className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white"
                type="button"
                onClick={() => void metricsQuery.refetch()}
              >
                Retry
              </button>
            </div>
          </div>
        ) : null}

        {metrics ? (
          <div className="mt-8">
            <MotionCardGrid>
              {[
              <MetricCard
                key="sharpe"
                label="Sharpe"
                value={metrics.sharpe_ratio}
                formatter={metricFormatters.number}
                tone={metrics.sharpe_ratio >= 0 ? "positive" : "negative"}
              />,
              <MetricCard
                key="sortino"
                label="Sortino"
                value={metrics.sortino_ratio}
                formatter={metricFormatters.number}
                tone={metrics.sortino_ratio >= 0 ? "positive" : "negative"}
              />,
              <MetricCard
                key="var"
                label="VaR"
                value={metrics.var}
                formatter={metricFormatters.percent}
                tone="negative"
              />,
              <MetricCard
                key="cvar"
                label="CVaR"
                value={metrics.cvar}
                formatter={metricFormatters.percent}
                tone="negative"
              />,
              <MetricCard
                key="beta"
                label="Beta"
                value={metrics.beta}
                formatter={metricFormatters.number}
              />,
              <MetricCard
                key="max-drawdown"
                label="Max drawdown"
                value={metrics.max_drawdown}
                formatter={metricFormatters.percent}
                tone="negative"
              />,
              ]}
            </MotionCardGrid>
          </div>
        ) : null}

        <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
          <div className="rounded-lg border border-border bg-surface p-5">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-ink">Return distribution</h3>
                <p className="mt-1 text-sm text-muted">
                  {metrics ? `${metrics.n_trading_days} trading days` : "Waiting for metrics"}
                </p>
              </div>
            </div>
            <div className="h-72">
              {histogramData.length > 0 ? (
                <ResponsiveContainer height="100%" width="100%">
                  <BarChart data={histogramData}>
                    <CartesianGrid stroke={chartColors.grid} vertical={false} />
                    <XAxis dataKey="bucket" {...axisStyle} />
                    <YAxis allowDecimals={false} width={36} {...axisStyle} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="count" fill={chartColors.portfolio} radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-md border border-border text-sm text-muted">
                  No return data available
                </div>
              )}
            </div>
          </div>

          <aside className="rounded-lg border border-border bg-surface p-5">
            <h3 className="text-base font-semibold text-ink">Risk context</h3>
            <dl className="mt-4 space-y-4 text-sm">
              <div className="flex items-center justify-between gap-4">
                <dt className="text-muted">Annual return</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.annual_return) : "—"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-muted">Annual volatility</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.annual_volatility) : "—"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-muted">Risk-free rate</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.risk_free_rate) : "—"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-muted">Beta benchmark</dt>
                <dd className="font-mono text-ink">{metrics?.beta_benchmark ?? "—"}</dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-muted">Dropped tickers</dt>
                <dd className="font-mono text-ink">{metrics?.dropped_tickers.length ?? 0}</dd>
              </div>
            </dl>
          </aside>
        </section>
      </section>
    </main>
  );
}

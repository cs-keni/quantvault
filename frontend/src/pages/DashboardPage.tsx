import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../services/apiClient";
import { useAuthStore } from "../store/authStore";
import type { PortfolioListItem, PortfolioMetricsResponse } from "../types/api";

type DashboardPeriod = "1mo" | "6mo" | "1y" | "2y" | "max";

const periods: DashboardPeriod[] = ["1mo", "6mo", "1y", "2y", "max"];

const metricFormatters = {
  number(value: number) {
    return value.toFixed(2);
  },
  percent(value: number) {
    return `${(value * 100).toFixed(2)}%`;
  },
};

function useCountUp(value: number | null, shouldAnimate: boolean) {
  const [displayValue, setDisplayValue] = useState(value ?? 0);

  useEffect(() => {
    let animationId = 0;
    if (value === null) {
      animationId = window.requestAnimationFrame(() => setDisplayValue(0));
      return () => window.cancelAnimationFrame(animationId);
    }
    if (!shouldAnimate) {
      animationId = window.requestAnimationFrame(() => setDisplayValue(value));
      return () => window.cancelAnimationFrame(animationId);
    }

    const targetValue = value;
    let frame = 0;
    const frames = 28;

    function tick() {
      frame += 1;
      const progress = Math.min(frame / frames, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplayValue(targetValue * eased);
      if (progress < 1) {
        animationId = window.requestAnimationFrame(tick);
      }
    }

    animationId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(animationId);
  }, [shouldAnimate, value]);

  return displayValue;
}

function MetricCard({
  label,
  value,
  formatter,
  tone = "neutral",
  shouldAnimate,
  delayClass,
}: {
  label: string;
  value: number | null;
  formatter: (value: number) => string;
  tone?: "neutral" | "positive" | "negative";
  shouldAnimate: boolean;
  delayClass: string;
}) {
  const displayValue = useCountUp(value, shouldAnimate);
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-ink";

  return (
    <article
      className={`rounded-lg border border-ink/10 bg-white p-4 shadow-sm ${shouldAnimate ? `animate-in fade-in slide-in-from-bottom-2 duration-500 ${delayClass}` : ""}`}
    >
      <p className="text-sm font-medium text-ink/60">{label}</p>
      <p className={`mt-3 font-mono text-2xl font-medium ${toneClass}`}>
        {value === null ? "N/A" : formatter(displayValue)}
      </p>
    </article>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
      <div className="h-4 w-24 animate-pulse rounded bg-surface" />
      <div className="mt-4 h-8 w-28 animate-pulse rounded bg-surface" />
    </div>
  );
}

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
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const [period, setPeriod] = useState<DashboardPeriod>("1y");
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);
  const hasAnimated = useRef(false);
  const [animateMetrics, setAnimateMetrics] = useState(false);

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
  const activePortfolioId = selectedPortfolioId ?? defaultPortfolio?.id ?? null;

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
    if (!metricsQuery.isSuccess || hasAnimated.current) {
      return;
    }
    hasAnimated.current = true;
    const animationId = window.requestAnimationFrame(() => setAnimateMetrics(true));
    const timeoutId = window.setTimeout(() => setAnimateMetrics(false), 800);
    return () => {
      window.cancelAnimationFrame(animationId);
      window.clearTimeout(timeoutId);
    };
  }, [activePortfolioId, metricsQuery.isSuccess, metricsQuery.dataUpdatedAt]);

  const selectedPortfolio = portfoliosQuery.data?.find(
    (portfolio) => portfolio.id === activePortfolioId,
  );
  const histogramData = useMemo(
    () => buildHistogram(metricsQuery.data?.daily_returns ?? []),
    [metricsQuery.data?.daily_returns],
  );

  function handleLogout() {
    logout();
    navigate("/login");
  }

  function handlePortfolioChange(portfolioId: string) {
    hasAnimated.current = false;
    setAnimateMetrics(false);
    setSelectedPortfolioId(portfolioId || null);
  }

  function handlePeriodChange(nextPeriod: DashboardPeriod) {
    hasAnimated.current = false;
    setAnimateMetrics(false);
    setPeriod(nextPeriod);
  }

  const metrics = metricsQuery.data;

  return (
    <main className="min-h-screen bg-bg">
      <header className="border-b border-ink/10 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
            <h1 className="mt-1 text-2xl font-semibold text-ink">Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-ink/60 sm:inline">{user?.full_name}</span>
            <button
              className="rounded-md border border-ink/10 px-3 py-2 text-sm font-medium text-ink/70 transition hover:border-ink/20 hover:text-ink"
              type="button"
              onClick={handleLogout}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col gap-4 border-b border-ink/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-ink">
              {selectedPortfolio?.name ?? "Portfolio risk"}
            </h2>
            <p className="mt-1 text-sm text-ink/60">
              {selectedPortfolio
                ? `${selectedPortfolio.holding_count} holdings - Benchmark ${selectedPortfolio.benchmark_ticker}`
                : "Select a portfolio to view metrics."}
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <select
              className="h-10 rounded-md border border-ink/10 bg-white px-3 text-sm font-medium text-ink outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
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

            <div className="grid grid-cols-5 rounded-md border border-ink/10 bg-surface p-1">
              {periods.map((periodOption) => (
                <button
                  key={periodOption}
                  className={`h-8 min-w-12 rounded px-2 text-xs font-semibold transition ${
                    period === periodOption
                      ? "bg-white text-accent shadow-sm"
                      : "text-ink/60 hover:text-ink"
                  }`}
                  type="button"
                  onClick={() => handlePeriodChange(periodOption)}
                >
                  {periodOption}
                </button>
              ))}
            </div>
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
          <div className="mt-8 rounded-lg border border-ink/10 bg-surface p-6">
            <h3 className="text-lg font-semibold text-ink">No portfolios yet</h3>
            <Link
              className="mt-4 inline-flex rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white"
              to="/portfolios/new"
            >
              New portfolio
            </Link>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          {metricsQuery.isLoading || portfoliosQuery.isLoading ? (
            Array.from({ length: 6 }, (_, index) => <SkeletonCard key={index} />)
          ) : metricsQuery.isError ? (
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
          ) : metrics ? (
            <>
              <MetricCard
                label="Sharpe"
                value={metrics.sharpe_ratio}
                formatter={metricFormatters.number}
                tone={metrics.sharpe_ratio >= 0 ? "positive" : "negative"}
                shouldAnimate={animateMetrics}
                delayClass="delay-0"
              />
              <MetricCard
                label="Sortino"
                value={metrics.sortino_ratio}
                formatter={metricFormatters.number}
                tone={metrics.sortino_ratio >= 0 ? "positive" : "negative"}
                shouldAnimate={animateMetrics}
                delayClass="delay-75"
              />
              <MetricCard
                label="VaR"
                value={metrics.var}
                formatter={metricFormatters.percent}
                tone="negative"
                shouldAnimate={animateMetrics}
                delayClass="delay-100"
              />
              <MetricCard
                label="CVaR"
                value={metrics.cvar}
                formatter={metricFormatters.percent}
                tone="negative"
                shouldAnimate={animateMetrics}
                delayClass="delay-150"
              />
              <MetricCard
                label="Beta"
                value={metrics.beta}
                formatter={metricFormatters.number}
                shouldAnimate={animateMetrics}
                delayClass="delay-200"
              />
              <MetricCard
                label="Max drawdown"
                value={metrics.max_drawdown}
                formatter={metricFormatters.percent}
                tone="negative"
                shouldAnimate={animateMetrics}
                delayClass="delay-300"
              />
            </>
          ) : null}
        </div>

        <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
          <div className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-ink">Return distribution</h3>
                <p className="mt-1 text-sm text-ink/60">
                  {metrics ? `${metrics.n_trading_days} trading days` : "Waiting for metrics"}
                </p>
              </div>
            </div>
            <div className="h-72">
              {histogramData.length > 0 ? (
                <ResponsiveContainer height="100%" width="100%">
                  <BarChart data={histogramData}>
                    <CartesianGrid stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="bucket" fontSize={12} tickLine={false} />
                    <YAxis allowDecimals={false} fontSize={12} tickLine={false} width={36} />
                    <Tooltip
                      contentStyle={{
                        border: "1px solid #e2e8f0",
                        borderRadius: 8,
                        color: "#0f172a",
                      }}
                    />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-md bg-surface text-sm text-ink/60">
                  No return data available
                </div>
              )}
            </div>
          </div>

          <aside className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
            <h3 className="text-base font-semibold text-ink">Risk context</h3>
            <dl className="mt-4 space-y-4 text-sm">
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink/60">Annual return</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.annual_return) : "N/A"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink/60">Annual volatility</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.annual_volatility) : "N/A"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink/60">Risk-free rate</dt>
                <dd className="font-mono text-ink">
                  {metrics ? metricFormatters.percent(metrics.risk_free_rate) : "N/A"}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink/60">Beta benchmark</dt>
                <dd className="font-mono text-ink">{metrics?.beta_benchmark ?? "N/A"}</dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink/60">Dropped tickers</dt>
                <dd className="font-mono text-ink">{metrics?.dropped_tickers.length ?? 0}</dd>
              </div>
            </dl>
          </aside>
        </section>
      </section>
    </main>
  );
}

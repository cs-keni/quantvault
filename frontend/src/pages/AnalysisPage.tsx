import { useMutation, useQuery } from "@tanstack/react-query";
import { Fragment, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { apiClient } from "../services/apiClient";
import type {
  FrontierPoint,
  FrontierResult,
  FrontierSubmitResponse,
  FrontierTaskStatus,
  PortfolioMetricsResponse,
  PortfolioOut,
} from "../types/api";

type AnalysisPeriod = "1mo" | "6mo" | "1y" | "2y" | "max";

const periods: AnalysisPeriod[] = ["1mo", "6mo", "1y", "2y", "max"];
const terminalStatuses = ["SUCCESS", "FAILURE"];

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number) {
  return value.toFixed(2);
}

function weightsLabel(weights: Record<string, number>) {
  return Object.entries(weights)
    .map(([ticker, weight]) => `${ticker} ${(weight * 100).toFixed(1)}%`)
    .join(", ");
}

function MetricsGrid({ metrics }: { metrics: PortfolioMetricsResponse }) {
  const cards = [
    ["Sharpe", formatNumber(metrics.sharpe_ratio)],
    ["Sortino", formatNumber(metrics.sortino_ratio)],
    ["VaR", formatPercent(metrics.var)],
    ["CVaR", formatPercent(metrics.cvar)],
    ["Beta", metrics.beta === null ? "N/A" : formatNumber(metrics.beta)],
    ["Max drawdown", formatPercent(metrics.max_drawdown)],
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      {cards.map(([label, value]) => (
        <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm" key={label}>
          <p className="text-sm font-medium text-ink/60">{label}</p>
          <p className="mt-3 font-mono text-2xl font-medium text-ink">{value}</p>
        </article>
      ))}
    </div>
  );
}

function FrontierTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  if (!active || payload === undefined || payload.length === 0) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div className="max-w-xs rounded-lg border border-ink/10 bg-white p-3 text-sm shadow-sm">
      <p className="font-semibold text-ink">{point.name}</p>
      <p className="mt-1 text-ink/70">Return {formatPercent(point.return)}</p>
      <p className="text-ink/70">Volatility {formatPercent(point.risk)}</p>
      {point.weights ? <p className="mt-2 text-ink/60">{weightsLabel(point.weights)}</p> : null}
    </div>
  );
}

interface ChartPoint {
  name: string;
  return: number;
  risk: number;
  weights?: Record<string, number>;
}

function toChartPoint(name: string, point: FrontierPoint): ChartPoint {
  return {
    name,
    return: point.annual_return,
    risk: point.annual_volatility,
    weights: point.weights,
  };
}

function FrontierChart({
  frontier,
  metrics,
}: {
  frontier: FrontierResult;
  metrics: PortfolioMetricsResponse;
}) {
  const frontierData = frontier.frontier.map((point, index) => toChartPoint(`Frontier ${index + 1}`, point));
  const currentPoint = {
    name: "Current portfolio",
    return: metrics.annual_return,
    risk: metrics.annual_volatility,
  };

  return (
    <div className="h-96">
      <ResponsiveContainer height="100%" width="100%">
        <ScatterChart margin={{ bottom: 12, left: 8, right: 20, top: 20 }}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis
            dataKey="risk"
            fontSize={12}
            name="Volatility"
            tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
            type="number"
          />
          <YAxis
            dataKey="return"
            fontSize={12}
            name="Return"
            tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
            type="number"
          />
          <ZAxis range={[80, 180]} />
          <Tooltip content={<FrontierTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={frontierData} fill="#6366f1" line lineType="joint" name="Frontier" />
          <Scatter data={[currentPoint]} fill="#0f172a" name="Current" shape="circle" />
          <Scatter data={[toChartPoint("Min variance", frontier.min_variance)]} fill="#10b981" name="Min variance" shape="star" />
          <Scatter data={[toChartPoint("Max Sharpe", frontier.max_sharpe)]} fill="#ef4444" name="Max Sharpe" shape="star" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function CorrelationHeatmap({ metrics }: { metrics: PortfolioMetricsResponse }) {
  const { tickers, matrix } = metrics.correlation;
  const gridTemplateColumns = `96px repeat(${tickers.length}, minmax(56px, 1fr))`;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max" style={{ display: "grid", gridTemplateColumns }}>
        <div />
        {tickers.map((ticker) => (
          <div className="px-2 py-2 text-center font-mono text-xs text-ink/60" key={ticker}>
            {ticker}
          </div>
        ))}
        {tickers.map((ticker, rowIndex) => (
          <Fragment key={ticker}>
            <div className="px-2 py-2 font-mono text-xs text-ink/60">
              {ticker}
            </div>
            {matrix[rowIndex].map((value, columnIndex) => {
              const intensity = Math.min(Math.abs(value), 1);
              const background =
                value >= 0
                  ? `rgba(16, 185, 129, ${0.12 + intensity * 0.5})`
                  : `rgba(239, 68, 68, ${0.12 + intensity * 0.5})`;
              return (
                <div
                  className="m-0.5 rounded p-2 text-center font-mono text-xs text-ink"
                  key={`${ticker}-${tickers[columnIndex]}`}
                  style={{ background }}
                >
                  {value.toFixed(2)}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

export function AnalysisPage() {
  const { id } = useParams();
  const [period, setPeriod] = useState<AnalysisPeriod>("1y");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [cachedFrontier, setCachedFrontier] = useState<FrontierResult | null>(null);
  const [frontierError, setFrontierError] = useState<string | null>(null);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", id],
    enabled: id !== undefined,
    queryFn: async () => {
      const response = await apiClient.get<PortfolioOut>(`/portfolios/${id}`);
      return response.data;
    },
  });

  const metricsQuery = useQuery({
    queryKey: ["portfolioMetrics", id, period],
    enabled: id !== undefined,
    queryFn: async () => {
      const response = await apiClient.get<PortfolioMetricsResponse>(
        `/analysis/portfolios/${id}/metrics`,
        { params: { period } },
      );
      return response.data;
    },
  });

  const tickers = useMemo(
    () => portfolioQuery.data?.holdings.map((holding) => holding.ticker.toUpperCase()) ?? [],
    [portfolioQuery.data?.holdings],
  );

  const submitFrontier = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<FrontierSubmitResponse>("/analysis/frontier", {
        tickers,
        period,
      });
      return response.data;
    },
    onMutate() {
      setTaskId(null);
      setCachedFrontier(null);
      setFrontierError(null);
    },
    onSuccess(response) {
      if (response.status === "SUCCESS" && response.task_id === null) {
        setCachedFrontier(response.result);
        return;
      }
      setTaskId(response.task_id);
    },
    onError() {
      setFrontierError("Unable to submit frontier analysis.");
    },
  });

  const frontierStatusQuery = useQuery({
    queryKey: ["frontierStatus", taskId],
    enabled: taskId !== null,
    queryFn: async () => {
      const response = await apiClient.get<FrontierTaskStatus>(`/analysis/frontier/${taskId}`);
      return response.data;
    },
    refetchInterval(query) {
      const status = query.state.data?.status;
      return status !== undefined && terminalStatuses.includes(status) ? false : 2000;
    },
  });

  const frontierResult = cachedFrontier ?? frontierStatusQuery.data?.result ?? null;
  const terminalFailure =
    frontierStatusQuery.data?.status === "FAILURE"
      ? frontierStatusQuery.data.error ?? "Frontier analysis failed."
      : null;
  const canRunFrontier = tickers.length >= 2 && !submitFrontier.isPending;

  return (
    <main className="min-h-screen bg-bg">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col gap-4 border-b border-ink/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
            <h1 className="mt-2 text-2xl font-semibold text-ink">
              {portfolioQuery.data?.name ?? "Analysis"}
            </h1>
          </div>
          <div className="grid grid-cols-5 rounded-md border border-ink/10 bg-surface p-1">
            {periods.map((periodOption) => (
              <button
                className={`h-8 min-w-12 rounded px-2 text-xs font-semibold transition ${
                  period === periodOption ? "bg-white text-accent shadow-sm" : "text-ink/60 hover:text-ink"
                }`}
                key={periodOption}
                type="button"
                onClick={() => setPeriod(periodOption)}
              >
                {periodOption}
              </button>
            ))}
          </div>
        </div>

        {metricsQuery.isLoading ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
            {Array.from({ length: 6 }, (_, index) => (
              <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm" key={index}>
                <div className="h-4 w-24 animate-pulse rounded bg-surface" />
                <div className="mt-4 h-8 w-28 animate-pulse rounded bg-surface" />
              </div>
            ))}
          </div>
        ) : metricsQuery.isError ? (
          <div className="mt-8 rounded-lg border border-negative/20 bg-negative/5 p-4">
            <p className="font-medium text-negative">Unable to load metrics.</p>
            <button
              className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white"
              type="button"
              onClick={() => void metricsQuery.refetch()}
            >
              Retry
            </button>
          </div>
        ) : metricsQuery.data ? (
          <div className="mt-8">
            <MetricsGrid metrics={metricsQuery.data} />
          </div>
        ) : null}

        <section className="mt-8 rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink">Efficient frontier</h2>
              <p className="mt-1 text-sm text-ink/60">
                {frontierStatusQuery.data?.status ?? submitFrontier.data?.status ?? "Ready"}
              </p>
            </div>
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              disabled={!canRunFrontier || tickers.length < 2}
              onClick={() => submitFrontier.mutate()}
            >
              {submitFrontier.isPending ? "Starting" : "Run frontier"}
            </button>
          </div>

          {tickers.length < 2 ? (
            <div className="mt-4 rounded-md bg-surface p-4 text-sm text-ink/60">
              Add at least two holdings to compute a frontier.
            </div>
          ) : null}
          {frontierError ?? terminalFailure ? (
            <div className="mt-4 rounded-md border border-negative/20 bg-negative/5 p-4 text-sm text-negative">
              {frontierError ?? terminalFailure}
            </div>
          ) : null}

          {frontierResult && metricsQuery.data ? (
            <div className="mt-6">
              <FrontierChart frontier={frontierResult} metrics={metricsQuery.data} />
            </div>
          ) : (
            <div className="mt-6 flex h-72 items-center justify-center rounded-md bg-surface text-sm text-ink/60">
              Frontier results will appear here.
            </div>
          )}
        </section>

        {metricsQuery.data ? (
          <section className="mt-8 rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-ink">Correlation heatmap</h2>
            <div className="mt-4">
              <CorrelationHeatmap metrics={metricsQuery.data} />
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}

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

import { axisStyle, chartColors } from "../components/chartConfig";
import { MetricCard } from "../components/MetricCard";
import { MotionCardGrid } from "../components/MotionCardGrid";
import { PageHeader } from "../components/PageHeader";
import { PeriodToggle, type Period } from "../components/PeriodToggle";
import { SkeletonCard } from "../components/SkeletonCard";
import { apiClient } from "../services/apiClient";
import type {
  FrontierPoint,
  FrontierResult,
  FrontierSubmitResponse,
  FrontierTaskStatus,
  PortfolioMetricsResponse,
  PortfolioOut,
} from "../types/api";

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

function FrontierTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  if (!active || payload === undefined || payload.length === 0) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div className="max-w-xs border border-border bg-[#1e1e1e] p-3 text-sm">
      <p className="font-semibold text-ink">{point.name}</p>
      <p className="mt-1 text-muted">Return {formatPercent(point.return)}</p>
      <p className="text-muted">Volatility {formatPercent(point.risk)}</p>
      {point.weights ? <p className="mt-2 text-muted">{weightsLabel(point.weights)}</p> : null}
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
          <CartesianGrid stroke={chartColors.grid} />
          <XAxis
            dataKey="risk"
            name="Volatility"
            tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
            type="number"
            {...axisStyle}
          />
          <YAxis
            dataKey="return"
            name="Return"
            tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`}
            type="number"
            {...axisStyle}
          />
          <ZAxis range={[80, 180]} />
          <Tooltip content={<FrontierTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={frontierData} fill={chartColors.portfolio} line lineType="joint" name="Frontier" />
          <Scatter data={[currentPoint]} fill={chartColors.benchmark} name="Current" shape="circle" />
          <Scatter data={[toChartPoint("Min variance", frontier.min_variance)]} fill={chartColors.positive} name="Min variance" shape="star" />
          <Scatter data={[toChartPoint("Max Sharpe", frontier.max_sharpe)]} fill="#ef4444" name="Max Sharpe" shape="star" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function correlationLabel(value: number): string {
  const abs = Math.abs(value);
  const dir = value >= 0 ? "positive" : "negative";
  if (abs >= 0.8) return `Strong ${dir}`;
  if (abs >= 0.5) return `Moderate ${dir}`;
  if (abs >= 0.2) return `Weak ${dir}`;
  return "Near zero";
}

function CorrelationHeatmap({ metrics }: { metrics: PortfolioMetricsResponse }) {
  const { tickers, matrix } = metrics.correlation;
  const gridTemplateColumns = `96px repeat(${tickers.length}, minmax(56px, 1fr))`;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max" style={{ display: "grid", gridTemplateColumns }}>
        <div />
        {tickers.map((ticker) => (
          <div className="px-2 py-2 text-center font-mono text-xs text-muted" key={ticker}>
            {ticker}
          </div>
        ))}
        {tickers.map((ticker, rowIndex) => (
          <Fragment key={ticker}>
            <div className="px-2 py-2 font-mono text-xs text-muted">
              {ticker}
            </div>
            {matrix[rowIndex].map((value, columnIndex) => {
              const intensity = Math.min(Math.abs(value), 1);
              const background =
                value >= 0
                  ? `rgba(16, 185, 129, ${0.12 + intensity * 0.5})`
                  : `rgba(239, 68, 68, ${0.12 + intensity * 0.5})`;
              const isSelf = rowIndex === columnIndex;
              return (
                <div
                  className="group relative m-0.5 cursor-default rounded p-2 text-center font-mono text-xs text-ink"
                  key={`${ticker}-${tickers[columnIndex]}`}
                  style={{ background }}
                >
                  {value.toFixed(2)}
                  {!isSelf && (
                    <div className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded border border-border bg-[#1e1e1e] px-2.5 py-1.5 text-xs text-ink shadow-lg group-hover:block">
                      <span className="font-semibold">{ticker} × {tickers[columnIndex]}</span>
                      <span className="ml-2 text-muted">{correlationLabel(value)}</span>
                    </div>
                  )}
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
  const [period, setPeriod] = useState<Period>("1y");
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
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <PageHeader title={portfolioQuery.data?.name ?? "Analysis"} />
          <PeriodToggle value={period} onChange={setPeriod} />
        </div>

        {metricsQuery.isLoading ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
            {Array.from({ length: 6 }, (_, index) => (
              <SkeletonCard key={index} />
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
            <MotionCardGrid>
              {[
                <MetricCard
                  key="sharpe"
                  label="Sharpe"
                  value={metricsQuery.data.sharpe_ratio}
                  formatter={formatNumber}
                  tone={metricsQuery.data.sharpe_ratio >= 0 ? "positive" : "negative"}
                />,
                <MetricCard
                  key="sortino"
                  label="Sortino"
                  value={metricsQuery.data.sortino_ratio}
                  formatter={formatNumber}
                  tone={metricsQuery.data.sortino_ratio >= 0 ? "positive" : "negative"}
                />,
                <MetricCard
                  key="var"
                  label="VaR"
                  value={metricsQuery.data.var}
                  formatter={formatPercent}
                  tone="negative"
                />,
                <MetricCard
                  key="cvar"
                  label="CVaR"
                  value={metricsQuery.data.cvar}
                  formatter={formatPercent}
                  tone="negative"
                />,
                <MetricCard
                  key="beta"
                  label="Beta"
                  value={metricsQuery.data.beta}
                  formatter={formatNumber}
                />,
                <MetricCard
                  key="max-drawdown"
                  label="Max drawdown"
                  value={metricsQuery.data.max_drawdown}
                  formatter={formatPercent}
                  tone="negative"
                />,
              ]}
            </MotionCardGrid>
          </div>
        ) : null}

        <section className="mt-8 rounded-lg border border-border bg-surface p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink">Efficient frontier</h2>
              <p className="mt-1 text-sm text-muted">
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
            <div className="mt-4 rounded-md border border-border p-4 text-sm text-muted">
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
            <div className="mt-6 flex h-72 items-center justify-center rounded-md border border-border text-sm text-muted">
              Frontier results will appear here.
            </div>
          )}
        </section>

        {metricsQuery.data ? (
          <section className="mt-8 rounded-lg border border-border bg-surface p-5">
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

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { axisStyle, chartColors } from "../components/chartConfig";
import { ChartTooltip } from "../components/charts";
import { MetricCard } from "../components/MetricCard";
import { MotionCardGrid } from "../components/MotionCardGrid";
import { PageHeader } from "../components/PageHeader";
import { apiClient } from "../services/apiClient";
import type {
  BacktestStatusResponse,
  BacktestSubmitResponse,
  PortfolioOut,
  RebalanceFrequency,
} from "../types/api";

const terminalStatuses = ["SUCCESS", "FAILURE"];
const rebalanceOptions: RebalanceFrequency[] = ["MONTHLY", "QUARTERLY", "ANNUALLY", "NEVER"];

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function defaultStartDate() {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 5);
  return isoDate(date);
}

function currency(value: number) {
  return new Intl.NumberFormat("en-US", {
    currency: "USD",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(value);
}

function percent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function friendlyStatus(status: string): string {
  const map: Record<string, string> = {
    READY: "Ready to run",
    PENDING: "Running…",
    STARTED: "Running…",
    SUCCESS: "Complete",
    FAILURE: "Failed",
  };
  return map[status] ?? status;
}

export function BacktestPage() {
  const { id } = useParams();
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(() => isoDate(new Date()));
  const [rebalanceFrequency, setRebalanceFrequency] = useState<RebalanceFrequency>("QUARTERLY");
  const [initialInvestment, setInitialInvestment] = useState(10_000);
  const [backtestId, setBacktestId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", id],
    enabled: id !== undefined,
    queryFn: async () => {
      const response = await apiClient.get<PortfolioOut>(`/portfolios/${id}`);
      return response.data;
    },
  });

  const backtestStatusQuery = useQuery({
    queryKey: ["backtestStatus", id, backtestId],
    enabled: id !== undefined && backtestId !== null,
    queryFn: async () => {
      const response = await apiClient.get<BacktestStatusResponse>(
        `/portfolios/${id}/backtests/${backtestId}`,
      );
      return response.data;
    },
    refetchInterval(query) {
      const status = query.state.data?.status;
      return status !== undefined && terminalStatuses.includes(status) ? false : 2000;
    },
  });

  const submitBacktest = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<BacktestSubmitResponse>(`/portfolios/${id}/backtests`, {
        end_date: endDate,
        initial_investment: initialInvestment,
        rebalance_frequency: rebalanceFrequency,
        start_date: startDate,
      });
      return response.data;
    },
    onMutate() {
      setSubmitError(null);
      setBacktestId(null);
    },
    onSuccess(response) {
      setBacktestId(response.backtest_id);
    },
    onError() {
      setSubmitError("Unable to start backtest.");
    },
  });

  const result = backtestStatusQuery.data;
  const tearsheet = result?.tearsheet ?? null;
  const chartData = useMemo(() => result?.equity_curve ?? [], [result?.equity_curve]);
  const status = result?.status ?? submitBacktest.data?.status ?? "READY";

  return (
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          title={portfolioQuery.data?.name ?? "Backtest"}
          subtitle={
            <span className="flex items-center gap-2">
              {friendlyStatus(status)}
              {(status === "PENDING" || status === "STARTED") ? (
                <span className="inline-flex gap-0.5">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
                </span>
              ) : null}
            </span>
          }
        />

        <form
          className="mt-8 grid gap-4 rounded-lg border border-border bg-surface p-5 lg:grid-cols-6"
          onSubmit={(event) => {
            event.preventDefault();
            submitBacktest.mutate();
          }}
        >
          <label className="block text-sm font-medium text-ink">
            Start date
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            End date
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Rebalance
            <select
              className="mt-1 h-10 w-full rounded-md border border-border bg-bg px-3 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              value={rebalanceFrequency}
              onChange={(event) => setRebalanceFrequency(event.target.value as RebalanceFrequency)}
            >
              {rebalanceOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-ink">
            Initial investment
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              min="1"
              type="number"
              value={initialInvestment}
              onChange={(event) => setInitialInvestment(Number(event.target.value))}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Benchmark
            <input
              className="mt-1 w-full cursor-default rounded-md border border-border/40 bg-bg/40 px-3 py-2 text-sm text-muted/70 outline-none"
              readOnly
              tabIndex={-1}
              title="Set on the portfolio — edit from Portfolio settings"
              value={portfolioQuery.data?.benchmark_ticker ?? "SPY"}
            />
          </label>
          <button
            className="self-end rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!portfolioQuery.isSuccess || submitBacktest.isPending}
            type="submit"
          >
            {submitBacktest.isPending ? "Starting" : "Run backtest"}
          </button>
        </form>

        {submitError ?? result?.error ? (
          <div className="mt-6 rounded-lg border border-negative/20 bg-negative/5 p-4 text-sm text-negative">
            <p>{submitError ?? result?.error}</p>
            <button
              className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!portfolioQuery.isSuccess || submitBacktest.isPending}
              type="button"
              onClick={() => submitBacktest.mutate()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {tearsheet ? (
          <>
            <div className="mt-8">
              <MotionCardGrid>
                {[
                  <MetricCard key="cagr" label="CAGR" value={tearsheet.cagr} formatter={percent} tone={tearsheet.cagr >= 0 ? "positive" : "negative"} />,
                  <MetricCard key="sharpe" label="Sharpe" value={tearsheet.sharpe} formatter={(value) => value.toFixed(2)} tone={tearsheet.sharpe >= 0 ? "positive" : "negative"} />,
                  <MetricCard key="sortino" label="Sortino" value={tearsheet.sortino} formatter={(value) => value.toFixed(2)} tone={tearsheet.sortino >= 0 ? "positive" : "negative"} />,
                  <MetricCard key="calmar" label="Calmar" value={tearsheet.calmar} formatter={(value) => value.toFixed(2)} tone={tearsheet.calmar === null ? "neutral" : tearsheet.calmar >= 1 ? "positive" : "negative"} />,
                  <MetricCard key="max-drawdown" label="Max drawdown" value={tearsheet.max_drawdown} formatter={percent} tone="negative" />,
                  <MetricCard key="alpha" label="Alpha" value={tearsheet.alpha} formatter={percent} tone={tearsheet.alpha >= 0 ? "positive" : "negative"} />,
                ]}
              </MotionCardGrid>
            </div>

            <section className="mt-8 rounded-lg border border-border bg-surface p-5">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                <h2 className="text-lg font-semibold text-ink">Equity curve</h2>
                <p className="text-sm text-muted">
                  Final {currency(tearsheet.final_value)} vs benchmark{" "}
                  {currency(tearsheet.benchmark_final_value)}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chartColors.portfolio }} />
                  Portfolio
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chartColors.benchmark }} />
                  {portfolioQuery.data?.benchmark_ticker ?? "Benchmark"}
                </span>
              </div>
              <div className="mt-4 h-96">
                <ResponsiveContainer height="100%" width="100%">
                  <ComposedChart data={chartData}>
                    <defs>
                      <linearGradient id="equityPortfolio" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={chartColors.portfolio} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={chartColors.portfolio} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={chartColors.grid} />
                    <XAxis dataKey="date" minTickGap={32} {...axisStyle} />
                    <YAxis tickFormatter={(value) => currency(Number(value))} width={84} {...axisStyle} />
                    <Tooltip content={<ChartTooltip formatter={(value) => currency(Number(value))} />} />
                    <Area
                      dataKey="portfolio"
                      fill="url(#equityPortfolio)"
                      isAnimationActive={false}
                      stroke="none"
                      type="monotone"
                    />
                    <Line dataKey="portfolio" dot={false} stroke={chartColors.portfolio} strokeWidth={3} type="monotone" />
                    <Line dataKey="benchmark" dot={false} stroke={chartColors.benchmark} strokeWidth={2} type="monotone" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        ) : (
          <div className="mt-8 flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
            Backtest results will appear here.
          </div>
        )}
      </section>
    </main>
  );
}

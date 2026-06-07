import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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
    <main className="min-h-screen bg-bg">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="border-b border-ink/10 pb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">
            {portfolioQuery.data?.name ?? "Backtest"}
          </h1>
          <p className="mt-1 text-sm text-ink/60">Status: {status}</p>
        </div>

        <form
          className="mt-8 grid gap-4 rounded-lg border border-ink/10 bg-white p-5 shadow-sm lg:grid-cols-6"
          onSubmit={(event) => {
            event.preventDefault();
            submitBacktest.mutate();
          }}
        >
          <label className="block text-sm font-medium text-ink">
            Start date
            <input
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            End date
            <input
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Rebalance
            <select
              className="mt-1 h-10 w-full rounded-md border border-ink/10 bg-white px-3 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
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
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              min="1"
              type="number"
              value={initialInvestment}
              onChange={(event) => setInitialInvestment(Number(event.target.value))}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Benchmark
            <input
              className="mt-1 w-full rounded-md border border-ink/10 bg-surface px-3 py-2 text-sm text-ink/70"
              readOnly
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
            <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
              {[
                ["CAGR", percent(tearsheet.cagr)],
                ["Sharpe", tearsheet.sharpe.toFixed(2)],
                ["Sortino", tearsheet.sortino.toFixed(2)],
                ["Calmar", tearsheet.calmar === null ? "N/A" : tearsheet.calmar.toFixed(2)],
                ["Max drawdown", percent(tearsheet.max_drawdown)],
                ["Alpha", percent(tearsheet.alpha)],
              ].map(([label, value]) => (
                <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm" key={label}>
                  <p className="text-sm text-ink/60">{label}</p>
                  <p className="mt-3 font-mono text-2xl font-medium text-ink">{value}</p>
                </article>
              ))}
            </div>

            <section className="mt-8 rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                <h2 className="text-lg font-semibold text-ink">Equity curve</h2>
                <p className="text-sm text-ink/60">
                  Final {currency(tearsheet.final_value)} vs benchmark{" "}
                  {currency(tearsheet.benchmark_final_value)}
                </p>
              </div>
              <div className="mt-4 h-96">
                <ResponsiveContainer height="100%" width="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="#e2e8f0" />
                    <XAxis dataKey="date" fontSize={12} minTickGap={32} />
                    <YAxis fontSize={12} tickFormatter={(value) => currency(Number(value))} width={84} />
                    <Tooltip formatter={(value) => currency(Number(value))} />
                    <Line dataKey="portfolio" dot={false} stroke="#6366f1" strokeWidth={3} type="monotone" />
                    <Line dataKey="benchmark" dot={false} stroke="#0f172a" strokeWidth={2} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        ) : (
          <div className="mt-8 flex h-72 items-center justify-center rounded-lg bg-surface text-sm text-ink/60">
            Backtest results will appear here.
          </div>
        )}
      </section>
    </main>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Area,
  Bar,
  BarChart,
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
  PortfolioOut,
  SimulationResponse,
  SimulationStatusResponse,
  SimulationSubmitResponse,
} from "../types/api";

const terminalStatuses = ["SUCCESS", "FAILURE"];

function currency(value: number) {
  return new Intl.NumberFormat("en-US", {
    currency: "USD",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(value);
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function buildFinalValueHistogram(finalValues: number[], bucketCount = 20) {
  if (finalValues.length === 0) return [];
  const sorted = [...finalValues].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  if (min === max) return [{ label: currency(min), count: finalValues.length }];
  const width = (max - min) / bucketCount;
  const buckets = Array.from({ length: bucketCount }, (_, i) => ({
    label: currency(min + width * i),
    count: 0,
  }));
  for (const value of finalValues) {
    const index = Math.min(Math.floor((value - min) / width), bucketCount - 1);
    buckets[index].count += 1;
  }
  return buckets;
}

function friendlyStatus(status: string): string {
  const map: Record<string, string> = {
    READY: "Ready to simulate",
    PENDING: "Running…",
    STARTED: "Running…",
    SUCCESS: "Complete",
    FAILURE: "Failed",
  };
  return map[status] ?? status;
}

function percentile(values: number[], percentileRank: number) {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.round((percentileRank / 100) * (sorted.length - 1))),
  );
  return sorted[index];
}

function buildPathChart(result: SimulationResponse) {
  const pathLength = result.sample_paths[0]?.length ?? 0;
  if (pathLength === 0) {
    return [];
  }
  const step = Math.max(1, Math.floor(pathLength / 120));
  const rows = [];

  for (let day = 0; day < pathLength; day += step) {
    const values = result.sample_paths.map((path) => path[day]);
    const p5 = percentile(values, 5);
    const p25 = percentile(values, 25);
    const p50 = percentile(values, 50);
    const p75 = percentile(values, 75);
    const p95 = percentile(values, 95);
    const row: Record<string, number | [number, number]> = {
      band: [p5, p95],
      day,
      initial: result.initial_investment,
      p5,
      p25,
      p50,
      p75,
      p95,
    };
    result.sample_paths.slice(0, 20).forEach((path, index) => {
      row[`path${index}`] = path[day];
    });
    rows.push(row);
  }

  const lastDay = pathLength - 1;
  if (rows.at(-1)?.day !== lastDay) {
    const values = result.sample_paths.map((path) => path[lastDay]);
    const p5 = percentile(values, 5);
    const p25 = percentile(values, 25);
    const p50 = percentile(values, 50);
    const p75 = percentile(values, 75);
    const p95 = percentile(values, 95);
    const row: Record<string, number | [number, number]> = {
      band: [p5, p95],
      day: lastDay,
      initial: result.initial_investment,
      p5,
      p25,
      p50,
      p75,
      p95,
    };
    result.sample_paths.slice(0, 20).forEach((path, index) => {
      row[`path${index}`] = path[lastDay];
    });
    rows.push(row);
  }

  return rows;
}

export function MonteCarloPage() {
  const { id } = useParams();
  const [years, setYears] = useState(10);
  const [nSimulations, setNSimulations] = useState(500);
  const [initialInvestment, setInitialInvestment] = useState(10_000);
  const [annualContribution, setAnnualContribution] = useState(0);
  const [simulationId, setSimulationId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", id],
    enabled: id !== undefined,
    queryFn: async () => {
      const response = await apiClient.get<PortfolioOut>(`/portfolios/${id}`);
      return response.data;
    },
  });

  const simulationStatusQuery = useQuery({
    queryKey: ["simulationStatus", simulationId],
    enabled: simulationId !== null,
    queryFn: async () => {
      const response = await apiClient.get<SimulationStatusResponse>(`/simulation/${simulationId}`);
      return response.data;
    },
    refetchInterval(query) {
      const status = query.state.data?.status;
      return status !== undefined && terminalStatuses.includes(status) ? false : 2000;
    },
  });

  const submitSimulation = useMutation({
    mutationFn: async () => {
      if (portfolioQuery.data === undefined || id === undefined) {
        throw new Error("Portfolio is not loaded.");
      }
      const holdings = portfolioQuery.data.holdings;
      const response = await apiClient.post<SimulationSubmitResponse>("/simulation/monte-carlo", {
        annual_contribution: annualContribution,
        initial_investment: initialInvestment,
        n_simulations: nSimulations,
        period: "1y",
        portfolio_id: id,
        tickers: holdings.map((holding) => holding.ticker),
        weights: holdings.map((holding) => Number(holding.target_weight)),
        years,
      });
      return response.data;
    },
    onMutate() {
      setSubmitError(null);
      setSimulationId(null);
    },
    onSuccess(response) {
      setSimulationId(response.simulation_id);
    },
    onError() {
      setSubmitError("Unable to start simulation.");
    },
  });

  const result = simulationStatusQuery.data?.result ?? null;
  const chartData = useMemo(() => (result ? buildPathChart(result) : []), [result]);
  const histogramData = useMemo(
    () => (result ? buildFinalValueHistogram(result.final_value_distribution) : []),
    [result],
  );
  const yearlyTicks = useMemo(() => {
    const pathLength = result?.sample_paths[0]?.length ?? 0;
    if (pathLength === 0) {
      return [];
    }
    const lastDay = pathLength - 1;
    return Array.from({ length: Math.floor(lastDay / 252) + 1 }, (_, index) => index * 252).concat(lastDay);
  }, [result]);
  const canSubmit = portfolioQuery.isSuccess && !submitSimulation.isPending;
  const status = simulationStatusQuery.data?.status ?? submitSimulation.data?.status ?? "READY";

  return (
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader
          title={portfolioQuery.data?.name ?? "Monte Carlo"}
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
          className="mt-8 grid gap-4 rounded-lg border border-border bg-surface p-5 lg:grid-cols-5"
          onSubmit={(event) => {
            event.preventDefault();
            submitSimulation.mutate();
          }}
        >
          <label className="block text-sm font-medium text-ink">
            Years
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              max="30"
              min="1"
              type="number"
              value={years}
              onChange={(event) => setYears(Number(event.target.value))}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Simulations
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              max="1000"
              min="1"
              type="number"
              value={nSimulations}
              onChange={(event) => setNSimulations(Number(event.target.value))}
            />
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
            Annual contribution
            <input
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              min="0"
              type="number"
              value={annualContribution}
              onChange={(event) => setAnnualContribution(Number(event.target.value))}
            />
          </label>
          <button
            className="self-end rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!canSubmit}
            type="submit"
          >
            {submitSimulation.isPending ? "Starting" : "Run simulation"}
          </button>
        </form>

        {submitError ?? simulationStatusQuery.data?.error ? (
          <div className="mt-6 rounded-lg border border-negative/20 bg-negative/5 p-4 text-sm text-negative">
            <p>{submitError ?? simulationStatusQuery.data?.error}</p>
            <button
              className="mt-3 rounded-md bg-negative px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!canSubmit}
              type="button"
              onClick={() => submitSimulation.mutate()}
            >
              Retry
            </button>
          </div>
        ) : null}

        {result ? (
          <>
            <div className="mt-8">
              <MotionCardGrid className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  <MetricCard
                    key="mean"
                    label="Mean final value"
                    value={result.mean_final_value}
                    formatter={currency}
                  />,
                  <MetricCard
                    key="p50"
                    label="Median final value"
                    value={result.percentile_outcomes["50"]}
                    formatter={currency}
                  />,
                  <MetricCard
                    key="profit"
                    label="Probability of profit"
                    value={result.probability_of_profit}
                    formatter={percent}
                    tone="positive"
                  />,
                  <MetricCard
                    key="doubling"
                    label="Probability of doubling"
                    value={result.probability_of_doubling}
                    formatter={percent}
                    tone="positive"
                  />,
                ]}
              </MotionCardGrid>
            </div>

            <section className="mt-8 rounded-lg border border-border bg-surface p-5">
              <h2 className="text-lg font-semibold text-ink">Simulation paths</h2>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chartColors.positive }} />
                  p95 — optimistic
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chartColors.portfolio }} />
                  p50 — median
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#ef4444" }} />
                  p5 — pessimistic
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full border border-[#6b7280]" style={{ background: "transparent" }} />
                  Initial investment
                </span>
              </div>
              <div className="mt-4 h-96">
                <ResponsiveContainer height="100%" width="100%">
                  <ComposedChart data={chartData}>
                    <defs>
                      <linearGradient id="monteCarloBand" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={chartColors.band} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={chartColors.band} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={chartColors.grid} />
                    <XAxis
                      dataKey="day"
                      domain={[0, "dataMax"]}
                      ticks={yearlyTicks}
                      tickFormatter={(value) => `${Math.round(Number(value) / 252)}y`}
                      type="number"
                      {...axisStyle}
                    />
                    <YAxis tickFormatter={(value) => currency(Number(value))} width={84} {...axisStyle} />
                    <Tooltip content={<ChartTooltip formatter={(value) => currency(Number(value))} />} />
                    <Area
                      dataKey="band"
                      fill="url(#monteCarloBand)"
                      isAnimationActive={false}
                      stroke="none"
                      type="monotone"
                    />
                    {result.sample_paths.slice(0, 20).map((_, index) => (
                      <Line
                        dataKey={`path${index}`}
                        dot={false}
                        isAnimationActive={false}
                        key={`path${index}`}
                        stroke={chartColors.benchmark}
                        strokeOpacity={0.22}
                        strokeWidth={1}
                        type="monotone"
                      />
                    ))}
                    <Line dataKey="p5" dot={false} stroke="#ef4444" strokeWidth={2} type="monotone" />
                    <Line dataKey="p25" dot={false} stroke={chartColors.portfolio} strokeOpacity={0.45} strokeWidth={2} type="monotone" />
                    <Line dataKey="p50" dot={false} stroke={chartColors.portfolio} strokeWidth={3} type="monotone" />
                    <Line dataKey="p75" dot={false} stroke={chartColors.portfolio} strokeOpacity={0.65} strokeWidth={2} type="monotone" />
                    <Line dataKey="p95" dot={false} stroke={chartColors.positive} strokeWidth={2} type="monotone" />
                    <Line dataKey="initial" dot={false} stroke={chartColors.benchmark} strokeDasharray="6 6" strokeWidth={2} type="monotone" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="mt-8 rounded-lg border border-border bg-surface p-5">
              <h2 className="text-lg font-semibold text-ink">Outcome distribution</h2>
              <p className="mt-1 text-sm text-muted">
                Final portfolio value across {result.n_simulations.toLocaleString()} simulations
              </p>
              <div className="mt-4 h-64">
                <ResponsiveContainer height="100%" width="100%">
                  <BarChart data={histogramData} barCategoryGap="4%">
                    <CartesianGrid stroke={chartColors.grid} vertical={false} />
                    <XAxis dataKey="label" interval={4} tick={{ ...axisStyle.tick, fontSize: 10 }} tickLine={false} />
                    <YAxis allowDecimals={false} width={32} {...axisStyle} />
                    <Tooltip content={<ChartTooltip formatter={(value) => `${value} simulations`} />} />
                    <Bar dataKey="count" fill={chartColors.portfolio} name="Simulations" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        ) : (
          <div className="mt-8 flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
            Simulation results will appear here.
          </div>
        )}
      </section>
    </main>
  );
}

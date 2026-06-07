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
    const row: Record<string, number> = {
      day,
      initial: result.initial_investment,
      p5: percentile(values, 5),
      p25: percentile(values, 25),
      p50: percentile(values, 50),
      p75: percentile(values, 75),
      p95: percentile(values, 95),
    };
    result.sample_paths.slice(0, 20).forEach((path, index) => {
      row[`path${index}`] = path[day];
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
  const canSubmit = portfolioQuery.isSuccess && !submitSimulation.isPending;
  const status = simulationStatusQuery.data?.status ?? submitSimulation.data?.status ?? "READY";

  return (
    <main className="min-h-screen bg-bg">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="border-b border-ink/10 pb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">QuantVault</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">
            {portfolioQuery.data?.name ?? "Monte Carlo"}
          </h1>
          <p className="mt-1 text-sm text-ink/60">Status: {status}</p>
        </div>

        <form
          className="mt-8 grid gap-4 rounded-lg border border-ink/10 bg-white p-5 shadow-sm lg:grid-cols-5"
          onSubmit={(event) => {
            event.preventDefault();
            submitSimulation.mutate();
          }}
        >
          <label className="block text-sm font-medium text-ink">
            Years
            <input
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
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
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
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
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
              min="1"
              type="number"
              value={initialInvestment}
              onChange={(event) => setInitialInvestment(Number(event.target.value))}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            Annual contribution
            <input
              className="mt-1 w-full rounded-md border border-ink/10 px-3 py-2 text-sm outline-none ring-accent/30 focus:border-accent focus:ring-4"
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
            <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <p className="text-sm text-ink/60">Mean final value</p>
                <p className="mt-3 font-mono text-2xl font-medium text-ink">
                  {currency(result.mean_final_value)}
                </p>
              </article>
              <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <p className="text-sm text-ink/60">P5 / P50 / P95</p>
                <p className="mt-3 font-mono text-xl font-medium text-ink">
                  {currency(result.percentile_outcomes["5"])} /{" "}
                  {currency(result.percentile_outcomes["50"])} /{" "}
                  {currency(result.percentile_outcomes["95"])}
                </p>
              </article>
              <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <p className="text-sm text-ink/60">Probability of profit</p>
                <p className="mt-3 font-mono text-2xl font-medium text-positive">
                  {(result.probability_of_profit * 100).toFixed(1)}%
                </p>
              </article>
              <article className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
                <p className="text-sm text-ink/60">Probability of doubling</p>
                <p className="mt-3 font-mono text-2xl font-medium text-ink">
                  {(result.probability_of_doubling * 100).toFixed(1)}%
                </p>
              </article>
            </div>

            <section className="mt-8 rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-ink">Simulation paths</h2>
              <div className="mt-4 h-96">
                <ResponsiveContainer height="100%" width="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid stroke="#e2e8f0" />
                    <XAxis dataKey="day" fontSize={12} tickFormatter={(value) => `${Math.round(Number(value) / 252)}y`} />
                    <YAxis fontSize={12} tickFormatter={(value) => currency(Number(value))} width={84} />
                    <Tooltip formatter={(value) => currency(Number(value))} />
                    {result.sample_paths.slice(0, 20).map((_, index) => (
                      <Line
                        dataKey={`path${index}`}
                        dot={false}
                        isAnimationActive={false}
                        key={`path${index}`}
                        stroke="#94a3b8"
                        strokeOpacity={0.22}
                        strokeWidth={1}
                        type="monotone"
                      />
                    ))}
                    <Line dataKey="p5" dot={false} stroke="#ef4444" strokeWidth={2} type="monotone" />
                    <Line dataKey="p25" dot={false} stroke="#f59e0b" strokeWidth={2} type="monotone" />
                    <Line dataKey="p50" dot={false} stroke="#6366f1" strokeWidth={3} type="monotone" />
                    <Line dataKey="p75" dot={false} stroke="#10b981" strokeWidth={2} type="monotone" />
                    <Line dataKey="p95" dot={false} stroke="#10b981" strokeWidth={2} type="monotone" />
                    <Line dataKey="initial" dot={false} stroke="#0f172a" strokeDasharray="6 6" strokeWidth={2} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        ) : (
          <div className="mt-8 flex h-72 items-center justify-center rounded-lg bg-surface text-sm text-ink/60">
            Simulation results will appear here.
          </div>
        )}
      </section>
    </main>
  );
}

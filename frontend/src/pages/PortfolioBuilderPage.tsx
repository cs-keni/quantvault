import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { apiClient } from "../services/apiClient";
import type { AssetClass, HoldingOut, PortfolioOut } from "../types/api";
import { validateHoldingDrafts } from "../utils/portfolioValidation";

const assetClasses: { value: AssetClass; label: string }[] = [
  { value: "EQUITY", label: "Equity" },
  { value: "FIXED_INCOME", label: "Fixed income" },
  { value: "REAL_ESTATE", label: "Real estate" },
  { value: "COMMODITY", label: "Commodity" },
  { value: "CASH", label: "Cash" },
];

interface HoldingDraft {
  clientId: string;
  ticker: string;
  asset_name: string;
  asset_class: AssetClass;
  target_weight_percent: string;
  current_shares: string;
  notes: string;
}

function createHoldingDraft(): HoldingDraft {
  return {
    clientId: crypto.randomUUID(),
    ticker: "",
    asset_name: "",
    asset_class: "EQUITY",
    target_weight_percent: "",
    current_shares: "",
    notes: "",
  };
}

function toHoldingPayload(holding: HoldingDraft) {
  const currentShares = holding.current_shares.trim();
  const notes = holding.notes.trim();

  return {
    ticker: holding.ticker.trim().toUpperCase(),
    asset_name: holding.asset_name.trim(),
    asset_class: holding.asset_class,
    target_weight: (Number(holding.target_weight_percent) / 100).toFixed(5),
    current_shares: currentShares === "" || Number(currentShares) <= 0 ? null : currentShares,
    notes: notes === "" ? null : notes,
  };
}

export function PortfolioBuilderPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [benchmarkTicker, setBenchmarkTicker] = useState("SPY");
  const [holdings, setHoldings] = useState<HoldingDraft[]>(() => [createHoldingDraft()]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);

  const validation = useMemo(() => validateHoldingDrafts(holdings), [holdings]);
  const weightBarWidth = Math.min(validation.totalPercent, 100);
  const weightTone =
    Math.abs(validation.totalPercent - 100) <= 0.1
      ? "bg-positive"
      : validation.totalPercent > 100
        ? "bg-negative"
        : "bg-muted";

  function updateHolding(clientId: string, patch: Partial<HoldingDraft>) {
    setHoldings((current) =>
      current.map((holding) =>
        holding.clientId === clientId ? { ...holding, ...patch } : holding,
      ),
    );
  }

  function addHolding() {
    setHoldings((current) => [...current, createHoldingDraft()]);
  }

  function removeHolding(clientId: string) {
    setHoldings((current) => current.filter((holding) => holding.clientId !== clientId));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setHasAttemptedSubmit(true);

    if (name.trim() === "") {
      setSubmitError("Portfolio name is required.");
      return;
    }
    if (holdings.some((holding) => holding.asset_name.trim() === "" || holding.ticker.trim() === "")) {
      setSubmitError("Each holding needs a ticker and asset name.");
      return;
    }
    if (!validation.valid) {
      setSubmitError(validation.errors[0] ?? "Fix portfolio weights before saving.");
      return;
    }

    setIsSubmitting(true);
    try {
      const portfolioResponse = await apiClient.post<PortfolioOut>("/portfolios", {
        name: name.trim(),
        description: description.trim() === "" ? null : description.trim(),
        benchmark_ticker: benchmarkTicker.trim().toUpperCase() || "SPY",
      });

      for (const holding of holdings) {
        await apiClient.post<HoldingOut>(
          `/portfolios/${portfolioResponse.data.id}/holdings`,
          toHoldingPayload(holding),
        );
      }

      await queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      navigate("/dashboard");
    } catch (error) {
      const detail =
        axios.isAxiosError(error) && typeof error.response?.data?.detail === "string"
          ? error.response.data.detail
          : "Unable to save portfolio. Try again.";
      setSubmitError(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-bg text-ink">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader title="New portfolio" />

        <form className="mt-8 space-y-8" onSubmit={handleSubmit}>
          <section className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(220px,1fr)]">
            <label className="block text-sm font-medium text-ink">
              Portfolio name
              <input
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium text-ink">
              Benchmark
              <input
                className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm uppercase outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                value={benchmarkTicker}
                onChange={(event) => setBenchmarkTicker(event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium text-ink md:col-span-2">
              Description
              <textarea
                className="mt-1 min-h-24 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </section>

          <section>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-ink">Holdings</h2>
                <p className="mt-1 font-mono text-sm text-muted">
                  {validation.totalPercent.toFixed(2)}% allocated
                </p>
              </div>
              <button
                className="rounded-md border border-border px-3 py-2 text-sm font-semibold text-ink transition hover:border-accent hover:text-accent"
                type="button"
                onClick={addHolding}
              >
                Add holding
              </button>
            </div>

            <div className="mt-4 h-2 overflow-hidden rounded-full bg-border">
              <div
                className={`h-full rounded-full transition-all duration-300 ${weightTone}`}
                style={{ width: `${weightBarWidth}%` }}
              />
            </div>

            <div className="mt-5 space-y-4">
              {holdings.map((holding) => (
                <article
                  className="rounded-lg border border-border bg-surface p-4"
                  key={holding.clientId}
                >
                  <div className="grid gap-4 lg:grid-cols-[120px_minmax(160px,1fr)_180px_140px_140px_auto]">
                    <label className="block text-sm font-medium text-ink">
                      Ticker
                      <input
                        className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm uppercase outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                        value={holding.ticker}
                        onChange={(event) =>
                          updateHolding(holding.clientId, { ticker: event.target.value })
                        }
                      />
                    </label>
                    <label className="block text-sm font-medium text-ink">
                      Asset name
                      <input
                        className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                        value={holding.asset_name}
                        onChange={(event) =>
                          updateHolding(holding.clientId, { asset_name: event.target.value })
                        }
                      />
                    </label>
                    <label className="block text-sm font-medium text-ink">
                      Asset class
                      <select
                        className="mt-1 h-10 w-full rounded-md border border-border bg-bg px-3 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                        value={holding.asset_class}
                        onChange={(event) =>
                          updateHolding(holding.clientId, {
                            asset_class: event.target.value as AssetClass,
                          })
                        }
                      >
                        {assetClasses.map((assetClass) => (
                          <option key={assetClass.value} value={assetClass.value}>
                            {assetClass.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-sm font-medium text-ink">
                      Weight %
                      <input
                        className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                        min="0"
                        max="100"
                        step="0.01"
                        type="number"
                        value={holding.target_weight_percent}
                        onChange={(event) =>
                          updateHolding(holding.clientId, {
                            target_weight_percent: event.target.value,
                          })
                        }
                      />
                    </label>
                    <label className="block text-sm font-medium text-ink">
                      Shares
                      <input
                        className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                        min="0"
                        step="0.000001"
                        type="number"
                        value={holding.current_shares}
                        onChange={(event) =>
                          updateHolding(holding.clientId, { current_shares: event.target.value })
                        }
                      />
                    </label>
                    <button
                      className="self-end rounded-md border border-border px-3 py-2 text-sm font-semibold text-muted transition hover:border-negative hover:text-negative disabled:cursor-not-allowed disabled:opacity-40"
                      type="button"
                      disabled={holdings.length === 1}
                      onClick={() => removeHolding(holding.clientId)}
                    >
                      Remove
                    </button>
                  </div>
                  <label className="mt-4 block text-sm font-medium text-ink">
                    Notes
                    <textarea
                      className="mt-1 min-h-16 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none ring-accent/30 transition focus:border-accent focus:ring-4"
                      value={holding.notes}
                      onChange={(event) =>
                        updateHolding(holding.clientId, { notes: event.target.value })
                      }
                    />
                  </label>
                </article>
              ))}
            </div>
          </section>

          {hasAttemptedSubmit && validation.errors.length > 0 ? (
            <div className="rounded-lg border border-negative/20 bg-negative/5 p-4 text-sm text-negative">
              {validation.errors[0]}
            </div>
          ) : null}
          {submitError ? (
            <div className="rounded-lg border border-negative/20 bg-negative/5 p-4 text-sm text-negative">
              {submitError}
            </div>
          ) : null}

          <div className="flex justify-end gap-3 border-t border-border pt-6">
            <button
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink transition hover:border-accent hover:text-accent"
              type="button"
              onClick={() => navigate("/dashboard")}
            >
              Cancel
            </button>
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Saving" : "Save portfolio"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

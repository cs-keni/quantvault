import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MetricCard } from "../MetricCard";
import { PageHeader } from "../PageHeader";
import { PeriodToggle, type Period } from "../PeriodToggle";
import { SkeletonCard } from "../SkeletonCard";

afterEach(() => {
  cleanup();
});

describe("shared components", () => {
  it("MetricCard renders an em dash for null values", () => {
    render(<MetricCard formatter={(value) => value.toFixed(2)} label="Beta" value={null} />);

    expect(screen.getByText("Beta")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("MetricCard renders formatted numeric values", async () => {
    render(
      <MetricCard
        formatter={(value) => `${(value * 100).toFixed(0)}%`}
        label="Return"
        value={0.12}
        tone="positive"
      />,
    );

    expect(await screen.findByText("12%")).toBeTruthy();
  });

  it("PeriodToggle emits the selected period", () => {
    const onChange = vi.fn<(period: Period) => void>();
    render(<PeriodToggle onChange={onChange} value="1y" />);

    fireEvent.click(screen.getByRole("button", { name: "6mo" }));

    expect(onChange).toHaveBeenCalledWith("6mo");
  });

  it("SkeletonCard renders loading blocks", () => {
    const { container } = render(<SkeletonCard />);

    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(2);
  });

  it("PageHeader renders title and optional subtitle", () => {
    render(<PageHeader subtitle="Status: READY" title="Monte Carlo" />);

    expect(screen.getByText("QuantVault")).toBeTruthy();
    expect(screen.getByText("Monte Carlo")).toBeTruthy();
    expect(screen.getByText("Status: READY")).toBeTruthy();
  });
});

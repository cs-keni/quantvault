import { describe, expect, it } from "vitest";

import { validateHoldingDrafts } from "../portfolioValidation";

describe("validateHoldingDrafts", () => {
  it("accepts holdings that total 100 percent", () => {
    const result = validateHoldingDrafts([
      { ticker: "VTI", target_weight_percent: "60" },
      { ticker: "BND", target_weight_percent: "40" },
    ]);

    expect(result.valid).toBe(true);
    expect(result.totalPercent).toBe(100);
  });

  it("rejects holdings over 100 percent", () => {
    const result = validateHoldingDrafts([
      { ticker: "VTI", target_weight_percent: "80" },
      { ticker: "BND", target_weight_percent: "30" },
    ]);

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Target weights must total 100%.");
    expect(result.errors).toContain("Target weights cannot exceed 100%.");
  });

  it("rejects duplicate tickers after normalization", () => {
    const result = validateHoldingDrafts([
      { ticker: "vti", target_weight_percent: "50" },
      { ticker: "VTI", target_weight_percent: "50" },
    ]);

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Ticker symbols must be unique.");
  });

  it("rejects empty holdings", () => {
    const result = validateHoldingDrafts([]);

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Add at least one holding.");
  });
});

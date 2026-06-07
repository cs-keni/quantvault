export interface HoldingDraftForValidation {
  ticker: string;
  target_weight_percent: string;
}

export interface WeightValidationResult {
  valid: boolean;
  totalPercent: number;
  errors: string[];
}

export function validateHoldingDrafts(
  holdings: HoldingDraftForValidation[],
): WeightValidationResult {
  const errors: string[] = [];
  const normalizedTickers = holdings
    .map((holding) => holding.ticker.trim().toUpperCase())
    .filter(Boolean);
  const totalPercent = holdings.reduce(
    (total, holding) => total + Number(holding.target_weight_percent || 0),
    0,
  );

  if (holdings.length === 0 || normalizedTickers.length === 0) {
    errors.push("Add at least one holding.");
  }
  if (new Set(normalizedTickers).size !== normalizedTickers.length) {
    errors.push("Ticker symbols must be unique.");
  }
  if (holdings.some((holding) => Number(holding.target_weight_percent || 0) <= 0)) {
    errors.push("Each holding needs a positive target weight.");
  }
  if (Math.abs(totalPercent - 100) > 0.1) {
    errors.push("Target weights must total 100%.");
  }
  if (totalPercent > 100.1) {
    errors.push("Target weights cannot exceed 100%.");
  }

  return {
    valid: errors.length === 0,
    totalPercent,
    errors,
  };
}

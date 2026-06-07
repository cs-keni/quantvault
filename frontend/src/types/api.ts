export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  default_portfolio_id: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PortfolioListItem {
  id: string;
  name: string;
  benchmark_ticker: string;
  holding_count: number;
}

export type AssetClass = "EQUITY" | "FIXED_INCOME" | "REAL_ESTATE" | "COMMODITY" | "CASH";

export interface HoldingOut {
  id: string;
  ticker: string;
  asset_name: string;
  asset_class: AssetClass;
  target_weight: string;
  current_shares: string | null;
  notes: string | null;
}

export interface PortfolioOut {
  id: string;
  name: string;
  description: string | null;
  benchmark_ticker: string;
  holdings: HoldingOut[];
}

export interface CorrelationMatrix {
  tickers: string[];
  matrix: number[][];
}

export interface PortfolioMetricsResponse {
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  var: number;
  cvar: number;
  confidence: number;
  max_drawdown: number;
  peak_date: string | number;
  trough_date: string | number;
  sortino_ratio: number;
  daily_returns: number[];
  beta: number | null;
  beta_benchmark: string | null;
  correlation: CorrelationMatrix;
  risk_free_rate: number;
  period: string;
  n_trading_days: number;
  dropped_tickers: string[];
}

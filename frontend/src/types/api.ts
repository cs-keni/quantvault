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

export interface FrontierPoint {
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
}

export interface FrontierResult {
  tickers: string[];
  period: string;
  risk_free_rate: number;
  frontier: FrontierPoint[];
  min_variance: FrontierPoint;
  max_sharpe: FrontierPoint;
  dropped_tickers: string[];
  n_trading_days: number;
}

export interface FrontierSubmitResponse {
  task_id: string | null;
  status: string;
  result: FrontierResult | null;
  error: string | null;
}

export interface FrontierTaskStatus {
  task_id: string;
  status: string;
  result: FrontierResult | null;
  error: string | null;
}

export interface SimulationResponse {
  percentile_outcomes: Record<string, number>;
  sample_paths: number[][];
  mean_final_value: number;
  probability_of_profit: number;
  probability_of_doubling: number;
  final_value_distribution: number[];
  initial_investment: number;
  years: number;
  n_simulations: number;
  annual_contribution: number;
}

export interface SimulationSubmitResponse {
  simulation_id: string;
  task_id: string;
  status: string;
}

export interface SimulationStatusResponse {
  simulation_id: string;
  status: string;
  result: SimulationResponse | null;
  error: string | null;
}

export type RebalanceFrequency = "MONTHLY" | "QUARTERLY" | "ANNUALLY" | "NEVER";

export interface BacktestTearsheet {
  cagr: number;
  sharpe: number;
  sortino: number;
  calmar: number | null;
  beta: number;
  alpha: number;
  win_rate: number;
  max_drawdown: number;
  rebalance_count: number;
  benchmark_cagr: number;
  final_value: number;
  benchmark_final_value: number;
  n_trading_days: number;
  risk_free_rate: number;
}

export interface EquityCurvePoint {
  date: string;
  portfolio: number;
  benchmark: number;
}

export interface BacktestSubmitResponse {
  backtest_id: string;
  task_id: string;
  status: string;
}

export interface BacktestStatusResponse {
  backtest_id: string;
  portfolio_id: string;
  strategy_name: string;
  status: string;
  start_date: string;
  end_date: string;
  rebalance_frequency: RebalanceFrequency;
  initial_investment: string;
  tearsheet: BacktestTearsheet | null;
  daily_returns: number[] | null;
  equity_curve: EquityCurvePoint[] | null;
  error: string | null;
}

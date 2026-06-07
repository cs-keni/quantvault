"""Ground-truth fixtures for financial metric unit tests.

All expected values are hand-computable from the formulas documented below.
Running this module directly prints every expected value for independent
verification:

    cd backend && python -m tests.fixtures.known_values

────────────────────────────────────────────────────────────────────────────
2-ASSET PORTFOLIO (A / B)
────────────────────────────────────────────────────────────────────────────
RETURNS_A  — 20-day daily return series (repeating 10-day pattern)
RETURNS_B  — 20-day daily return series (repeating 10-day pattern)
WEIGHTS    — [0.6, 0.4]

PORTFOLIO_RETURNS[i] = 0.6 * RETURNS_A[i] + 0.4 * RETURNS_B[i]

Mean A  = sum([0.010,-0.005,0.008,-0.003,0.012,-0.004,0.006,-0.002,0.009,-0.001])*2/20
        = 0.030 * 2 / 20 = 0.003 per day
Mean B  = sum([0.005,-0.003,0.004,-0.001,0.006,-0.002,0.003,-0.001,0.004,0.000])*2/20
        = 0.015 * 2 / 20 = 0.0015 per day
Mean P  = 0.6 * 0.003 + 0.4 * 0.0015 = 0.0018 + 0.0006 = 0.0024 per day

────────────────────────────────────────────────────────────────────────────
VAR / CVAR (100 sorted daily returns: -5.0% … +4.9%, step 0.1%)
────────────────────────────────────────────────────────────────────────────
VAR_RETURNS = [-0.050, -0.049, ..., 0.048, 0.049]  (100 values, already sorted)

95% confidence:
  var_index = max(int(0.05 * 100), 1) = 5
  VaR_95  = VAR_RETURNS[5]  = -0.050 + 5 * 0.001 = -0.045
  CVaR_95 = mean(VAR_RETURNS[0:5])
           = mean([-0.050, -0.049, -0.048, -0.047, -0.046])
           = -0.240 / 5 = -0.048

99% confidence:
  var_index = max(int(0.01 * 100), 1) = 1
  VaR_99  = VAR_RETURNS[1]  = -0.049
  CVaR_99 = mean(VAR_RETURNS[0:1]) = VAR_RETURNS[0] = -0.050

────────────────────────────────────────────────────────────────────────────
MAX DRAWDOWN
────────────────────────────────────────────────────────────────────────────
DRAWDOWN_PRICES = [100.0, 120.0, 90.0, 100.0, 110.0]
DRAWDOWN_RETURNS = pct_change = [0.20, -0.25, 0.1111..., 0.10]

Equity curve from $1 (cumprod):
  $1.00 → $1.20 → $0.90 → $1.00 → $1.10

Peak = 1.20 (index 0), Trough = 0.90 (index 1)
max_drawdown = (0.90 - 1.20) / 1.20 = -30/120 = -0.25 (-25%)

────────────────────────────────────────────────────────────────────────────
BETA = 2.0 EXACTLY
────────────────────────────────────────────────────────────────────────────
PORTFOLIO_BETA_RETURNS = 2 * BENCHMARK_RETURNS

Cov(2B, B) = 2 * Cov(B, B) = 2 * Var(B)
Beta = Cov(port, bench) / Var(bench) = 2 * Var / Var = 2.0
(ddof=1 factors cancel in numerator and denominator)
"""

import numpy as np
import numpy.typing as npt
import pandas as pd

# ────────────────────────────────────────────────────────────────
# 2-Asset portfolio
# ────────────────────────────────────────────────────────────────

RETURNS_A: npt.NDArray[np.float64] = np.array(
    [
        0.010,
        -0.005,
        0.008,
        -0.003,
        0.012,
        -0.004,
        0.006,
        -0.002,
        0.009,
        -0.001,
        0.010,
        -0.005,
        0.008,
        -0.003,
        0.012,
        -0.004,
        0.006,
        -0.002,
        0.009,
        -0.001,
    ],
    dtype=np.float64,
)

RETURNS_B: npt.NDArray[np.float64] = np.array(
    [
        0.005,
        -0.003,
        0.004,
        -0.001,
        0.006,
        -0.002,
        0.003,
        -0.001,
        0.004,
        0.000,
        0.005,
        -0.003,
        0.004,
        -0.001,
        0.006,
        -0.002,
        0.003,
        -0.001,
        0.004,
        0.000,
    ],
    dtype=np.float64,
)

WEIGHTS: npt.NDArray[np.float64] = np.array([0.6, 0.4], dtype=np.float64)
TICKERS: list[str] = ["A", "B"]
RISK_FREE_RATE: float = 0.04

PORTFOLIO_RETURNS: npt.NDArray[np.float64] = WEIGHTS[0] * RETURNS_A + WEIGHTS[1] * RETURNS_B
# = [0.008, -0.0042, 0.0064, -0.0022, 0.0096, -0.0032, 0.0048, -0.0016, 0.007, -0.0006] * 2

# ─── Expected basic metrics (computed from definitions, not from the impl) ─────

# mean_daily = 0.6*0.003 + 0.4*0.0015 = 0.0024 (exactly)
EXPECTED_MEAN_DAILY: float = float(np.mean(PORTFOLIO_RETURNS))

# Annualized return: geometric compounding over 252 trading days
EXPECTED_ANNUAL_RETURN: float = float((1 + EXPECTED_MEAN_DAILY) ** 252 - 1)

# Annualized volatility: sample std (ddof=1) scaled by sqrt(252)
EXPECTED_DAILY_VOL: float = float(np.std(PORTFOLIO_RETURNS, ddof=1))
EXPECTED_ANNUAL_VOL: float = float(EXPECTED_DAILY_VOL * np.sqrt(252))

# Sharpe ratio: (annual_return - rfr) / annual_vol
EXPECTED_SHARPE: float = (EXPECTED_ANNUAL_RETURN - RISK_FREE_RATE) / EXPECTED_ANNUAL_VOL

# Sortino: downside deviation = sqrt(mean(min(r,0)^2)) * sqrt(252)
_downside = np.minimum(PORTFOLIO_RETURNS, 0.0)
EXPECTED_DOWNSIDE_DEV_ANNUAL: float = float(np.sqrt(np.mean(_downside**2)) * np.sqrt(252))
EXPECTED_SORTINO: float = (
    (EXPECTED_ANNUAL_RETURN - RISK_FREE_RATE) / EXPECTED_DOWNSIDE_DEV_ANNUAL
    if EXPECTED_DOWNSIDE_DEV_ANNUAL > 0
    else 0.0
)

# ────────────────────────────────────────────────────────────────
# Returns DataFrame (for calculate_portfolio_metrics / correlation)
# ────────────────────────────────────────────────────────────────

RETURNS_DF: pd.DataFrame = pd.DataFrame(
    {"A": RETURNS_A, "B": RETURNS_B},
    index=pd.date_range("2023-01-02", periods=20, freq="B"),
)

# ────────────────────────────────────────────────────────────────
# VaR / CVaR: 100 returns, -5% to +4.9%, step 0.1%
# ────────────────────────────────────────────────────────────────

# Sorted ascending (worst first): -0.050, -0.049, ..., 0.049
VAR_RETURNS: npt.NDArray[np.float64] = np.array(
    [i * 0.001 - 0.050 for i in range(100)], dtype=np.float64
)

# 95% confidence
EXPECTED_VAR_95: float = -0.045  # VAR_RETURNS[5]  = -0.050 + 5*0.001
EXPECTED_CVAR_95: float = -0.048  # mean([-0.050, -0.049, -0.048, -0.047, -0.046])

# 99% confidence
EXPECTED_VAR_99: float = -0.049  # VAR_RETURNS[1]
EXPECTED_CVAR_99: float = -0.050  # VAR_RETURNS[0]

# ────────────────────────────────────────────────────────────────
# Max drawdown
# ────────────────────────────────────────────────────────────────

DRAWDOWN_PRICES: npt.NDArray[np.float64] = np.array(
    [100.0, 120.0, 90.0, 100.0, 110.0], dtype=np.float64
)

# Daily returns (pct_change from prices)
DRAWDOWN_RETURNS: pd.Series = pd.Series(
    np.diff(DRAWDOWN_PRICES) / DRAWDOWN_PRICES[:-1],
    index=pd.date_range("2023-01-02", periods=4, freq="B"),
    dtype=np.float64,
)

EXPECTED_MAX_DRAWDOWN: float = -0.25  # (90 - 120) / 120 = -0.25 exactly
EXPECTED_PEAK_INDEX: int = 0  # equity curve peaks at index 0 (after first return)
EXPECTED_TROUGH_INDEX: int = 1  # equity curve troughs at index 1 (after -25% return)

# ────────────────────────────────────────────────────────────────
# Beta = 2.0 exactly
# ────────────────────────────────────────────────────────────────

BENCHMARK_RETURNS: npt.NDArray[np.float64] = np.array(
    [0.01, 0.02, -0.01, 0.015, -0.005, 0.008, -0.003, 0.012, 0.004, -0.006],
    dtype=np.float64,
)
PORTFOLIO_BETA_RETURNS: npt.NDArray[np.float64] = np.array(
    2.0 * BENCHMARK_RETURNS, dtype=np.float64
)
EXPECTED_BETA: float = 2.0


# ────────────────────────────────────────────────────────────────
# Self-check: print all expected values when run as a script
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 2-Asset Portfolio ===")
    print(f"mean_daily          = {EXPECTED_MEAN_DAILY:.6f}")
    print(
        f"annual_return       = {EXPECTED_ANNUAL_RETURN:.6f}  ({EXPECTED_ANNUAL_RETURN * 100:.2f}%)"
    )
    print(f"daily_vol           = {EXPECTED_DAILY_VOL:.6f}")
    print(f"annual_vol          = {EXPECTED_ANNUAL_VOL:.6f}  ({EXPECTED_ANNUAL_VOL * 100:.2f}%)")
    print(f"sharpe              = {EXPECTED_SHARPE:.6f}")
    print(f"downside_dev_annual = {EXPECTED_DOWNSIDE_DEV_ANNUAL:.6f}")
    print(f"sortino             = {EXPECTED_SORTINO:.6f}")
    print()
    print("=== VaR / CVaR ===")
    print(f"VaR_95  = {EXPECTED_VAR_95:.3f}  CVaR_95 = {EXPECTED_CVAR_95:.3f}")
    print(f"VaR_99  = {EXPECTED_VAR_99:.3f}  CVaR_99 = {EXPECTED_CVAR_99:.3f}")
    print()
    print("=== Max Drawdown ===")
    print(f"max_drawdown = {EXPECTED_MAX_DRAWDOWN:.4f}  ({EXPECTED_MAX_DRAWDOWN * 100:.1f}%)")
    print()
    print("=== Beta ===")
    print(f"beta = {EXPECTED_BETA:.1f}")

"""Risk and return metrics: portfolio return, volatility, Sharpe, Sortino, VaR, CVaR,
max drawdown, beta, and correlation matrix.

All functions are pure numpy/pandas — no I/O, no DB, no yfinance.  Routes and
portfolio_service are responsible for fetching returns and passing them here.
Every function carries a docstring with the exact formula so both humans and
future agents can verify correctness independently.
"""

import logging
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

_logger = logging.getLogger(__name__)


def calculate_portfolio_metrics(
    returns_df: pd.DataFrame,
    weights: npt.NDArray[np.float64],
    rfr: float = 0.04,
) -> dict[str, float]:
    """Annualized return, volatility, and Sharpe ratio for a weighted portfolio.

    `returns_df.columns` and `weights` must be index-aligned: weights[i]
    corresponds to returns_df.columns[i].  Use `portfolio_to_weights()` (which
    preserves holding order) and `get_historical_returns(tickers)` (which
    reindexes to requested order) together to guarantee alignment.

    Formulas:
        portfolio_daily_r = returns_df @ weights
        annual_return     = (1 + mean_daily)^252 - 1   [geometric compounding]
        annual_vol        = std_daily(ddof=1) * sqrt252
        sharpe            = (annual_return - rfr) / annual_vol
    """
    port_returns: pd.Series = returns_df @ weights
    mean_daily = float(port_returns.mean())
    std_daily = float(port_returns.std(ddof=1))

    annual_return = float((1 + mean_daily) ** 252 - 1)
    annual_vol = std_daily * np.sqrt(252)
    # 1e-8 floor: float64 std of a constant series can be O(1e-19) due to
    # floating-point noise rather than exactly 0; any real vol is ≥ 0.01/sqrt252 ≈ 6e-4.
    sharpe = (annual_return - rfr) / annual_vol if annual_vol > 1e-8 else 0.0

    return {
        "annual_return": annual_return,
        "annual_volatility": float(annual_vol),
        "sharpe_ratio": sharpe,
        "mean_daily_return": mean_daily,
        "daily_volatility": std_daily,
        "n_trading_days": len(port_returns),
    }


def calculate_var_cvar(
    portfolio_returns: pd.Series | npt.NDArray[np.float64],
    confidence: float = 0.95,
) -> dict[str, float]:
    """Historical-simulation VaR and CVaR (Expected Shortfall).

    Uses the most recent 252 trading days for the "annual" window.
    This is the direct historical simulation — NOT daily_var * sqrt252,
    which is only valid for parametric (normal) VaR.

    CVaR guard: `var_index = max(int((1-confidence)*N), 1)` prevents an
    empty slice → NaN when confidence is very high or the window is small
    (locked architecture decision from PHASES.md).

    Returns are expressed as signed daily return fractions (negative = loss):
        VaR_95  = -0.032 means 5% of periods lost more than 3.2%.
        CVaR_95 = -0.048 means the mean loss in the worst 5% was 4.8%.

    Formula:
        sorted_r  = sort(annual_slice)          [ascending; worst first]
        var_index = max(int((1-conf) * N), 1)
        VaR       = sorted_r[var_index]
        CVaR      = mean(sorted_r[0 : var_index])
    """
    arr = np.asarray(portfolio_returns, dtype=np.float64)
    annual_slice = arr[-252:] if len(arr) >= 252 else arr
    sorted_returns = np.sort(annual_slice)
    n = len(sorted_returns)

    var_index = max(int((1 - confidence) * n), 1)
    var = float(sorted_returns[var_index])
    cvar = float(sorted_returns[:var_index].mean())

    return {"var": var, "cvar": cvar, "confidence": confidence, "n_periods": n}


def calculate_max_drawdown(
    portfolio_returns: pd.Series | npt.NDArray[np.float64],
) -> dict[str, Any]:
    """Peak-to-trough maximum drawdown from a daily return series.

    Reconstructs a $1 equity curve via cumulative product, then finds the
    worst (peak, subsequent trough) pair.

    Formula:
        equity   = cumprod(1 + r)
        cummax   = rolling_max(equity)
        drawdown = (equity - cummax) / cummax       [always ≤ 0]
        max_dd   = min(drawdown)

    Returns dates if `portfolio_returns` is a pd.Series with a DatetimeIndex,
    otherwise returns integer indices.
    """
    arr = np.asarray(portfolio_returns, dtype=np.float64)
    equity = np.cumprod(1.0 + arr)

    cummax = np.maximum.accumulate(equity)
    drawdown = (equity - cummax) / cummax  # ≤ 0

    trough_idx = int(np.argmin(drawdown))
    max_dd = float(drawdown[trough_idx])

    # Walk back to find the last peak at or before the trough
    peak_idx = int(np.argmax(equity[: trough_idx + 1]))

    if isinstance(portfolio_returns, pd.Series) and isinstance(
        portfolio_returns.index, pd.DatetimeIndex
    ):
        idx = portfolio_returns.index
        peak_label: Any = str(idx[peak_idx].date())
        trough_label: Any = str(idx[trough_idx].date())
    else:
        peak_label = peak_idx
        trough_label = trough_idx

    return {
        "max_drawdown": max_dd,
        "peak_date": peak_label,
        "trough_date": trough_label,
    }


def calculate_sortino(
    portfolio_returns: pd.Series | npt.NDArray[np.float64],
    annual_return: float,
    rfr: float = 0.04,
) -> float:
    """Sortino ratio: excess return over the risk-free rate per unit of downside risk.

    Uses the semi-deviation formula (Sortino & van der Meer 1991):
        downside_daily = min(r, 0)     [target = 0; zeros do not contribute]
        DD_annual      = sqrt(mean(downside_daily²)) * sqrt252

    The mean (not ddof=1 std) divides by N over ALL observations, not just the
    negative ones — downside deviation measures the risk of an entire period,
    not the variance within the subset of bad days.

    Formula:
        sortino = (annual_return - rfr) / DD_annual
    """
    arr = np.asarray(portfolio_returns, dtype=np.float64)
    downside = np.minimum(arr, 0.0)
    dd_annual = float(np.sqrt(np.mean(downside**2)) * np.sqrt(252))
    if dd_annual == 0.0:
        return 0.0
    return (annual_return - rfr) / dd_annual


def _compute_beta(
    portfolio_returns: npt.NDArray[np.float64],
    benchmark_returns: npt.NDArray[np.float64],
) -> float:
    """OLS beta via covariance: Beta = Cov(port, bench) / Var(bench).

    Uses ddof=1 (sample covariance), which is standard for financial time
    series.  Returns 0.0 if the benchmark has zero variance (constant prices).

    Formula:
        cov_matrix = np.cov([port, bench], ddof=1)   [2*2]
        beta       = cov_matrix[0,1] / cov_matrix[1,1]
    """
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError(
            f"Length mismatch: portfolio={len(portfolio_returns)}, "
            f"benchmark={len(benchmark_returns)}"
        )
    cov_matrix = np.cov(portfolio_returns, benchmark_returns, ddof=1)
    bench_var = float(cov_matrix[1, 1])
    if bench_var == 0.0:
        _logger.warning("benchmark variance is zero — returning beta=0.0")
        return 0.0
    return float(cov_matrix[0, 1] / bench_var)


def calculate_beta_from_returns(
    portfolio_returns: pd.Series | npt.NDArray[np.float64],
    benchmark_returns: pd.Series | npt.NDArray[np.float64],
) -> float:
    """Compute beta from two pre-fetched return series.

    If both arguments are pd.Series, aligns on their shared index and drops
    any NaN pairs before computing.  If either is a bare ndarray, the caller
    is responsible for alignment.
    """
    if isinstance(portfolio_returns, pd.Series) and isinstance(benchmark_returns, pd.Series):
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
        port_arr = aligned.iloc[:, 0].to_numpy(dtype=np.float64)
        bench_arr = aligned.iloc[:, 1].to_numpy(dtype=np.float64)
    else:
        port_arr = np.asarray(portfolio_returns, dtype=np.float64)
        bench_arr = np.asarray(benchmark_returns, dtype=np.float64)

    return _compute_beta(port_arr, bench_arr)


def calculate_correlation_matrix(returns_df: pd.DataFrame) -> dict[str, Any]:
    """Pairwise Pearson correlation matrix for all tickers in returns_df.

    Formula:
        corr[i,j] = Cov(ticker_i, ticker_j) / (std_i * std_j)

    Returns:
        {"tickers": ["AAPL", "MSFT", ...], "matrix": [[1.0, 0.72, ...], ...]}
    """
    corr = returns_df.corr(method="pearson")
    return {
        "tickers": list(corr.columns),
        "matrix": corr.values.tolist(),
    }

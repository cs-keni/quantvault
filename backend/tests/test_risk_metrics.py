"""Unit tests for risk_service.py — all pure math, no I/O, no DB.

Expected values come from tests/fixtures/known_values.py, which documents
every formula and its derivation.  If a test fails it means either the
formula is implemented differently than specified or the fixture is wrong —
check the fixture's inline derivation first.
"""

import numpy as np
import pandas as pd
import pytest
from app.services import risk_service

from tests.fixtures.known_values import (
    BENCHMARK_RETURNS,
    DRAWDOWN_RETURNS,
    EXPECTED_ANNUAL_RETURN,
    EXPECTED_ANNUAL_VOL,
    EXPECTED_BETA,
    EXPECTED_CVAR_95,
    EXPECTED_CVAR_99,
    EXPECTED_MAX_DRAWDOWN,
    EXPECTED_MEAN_DAILY,
    EXPECTED_SHARPE,
    EXPECTED_SORTINO,
    EXPECTED_VAR_95,
    EXPECTED_VAR_99,
    PORTFOLIO_BETA_RETURNS,
    PORTFOLIO_RETURNS,
    RETURNS_DF,
    RISK_FREE_RATE,
    VAR_RETURNS,
    WEIGHTS,
)

REL = 1e-4  # 0.01% relative tolerance across all assertions


# ─────────────────────────────────────────────────────────────────────────────
# calculate_portfolio_metrics
# ─────────────────────────────────────────────────────────────────────────────


async def test_portfolio_metrics_annual_return() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    assert result["annual_return"] == pytest.approx(EXPECTED_ANNUAL_RETURN, rel=REL)


async def test_portfolio_metrics_annual_volatility() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    assert result["annual_volatility"] == pytest.approx(EXPECTED_ANNUAL_VOL, rel=REL)


async def test_portfolio_metrics_sharpe() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    assert result["sharpe_ratio"] == pytest.approx(EXPECTED_SHARPE, rel=REL)


async def test_portfolio_metrics_mean_daily() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    assert result["mean_daily_return"] == pytest.approx(EXPECTED_MEAN_DAILY, rel=REL)


async def test_portfolio_metrics_n_trading_days() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    assert result["n_trading_days"] == 20


async def test_portfolio_metrics_includes_daily_returns() -> None:
    result = risk_service.calculate_portfolio_metrics(RETURNS_DF, WEIGHTS, RISK_FREE_RATE)
    expected = (RETURNS_DF @ WEIGHTS).to_numpy(dtype=np.float64)

    assert result["daily_returns"] == pytest.approx(expected.tolist(), rel=REL)


async def test_portfolio_metrics_zero_vol_returns_zero_sharpe() -> None:
    """A constant-return series has zero sample std → Sharpe = 0 (not ÷0 error)."""
    const_df = pd.DataFrame({"A": [0.001] * 10, "B": [0.001] * 10})
    result = risk_service.calculate_portfolio_metrics(const_df, WEIGHTS, 0.04)
    assert result["sharpe_ratio"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# calculate_var_cvar
# ─────────────────────────────────────────────────────────────────────────────


async def test_var_95() -> None:
    result = risk_service.calculate_var_cvar(VAR_RETURNS, confidence=0.95)
    assert result["var"] == pytest.approx(EXPECTED_VAR_95, rel=REL)


async def test_cvar_95() -> None:
    result = risk_service.calculate_var_cvar(VAR_RETURNS, confidence=0.95)
    assert result["cvar"] == pytest.approx(EXPECTED_CVAR_95, rel=REL)


async def test_var_99() -> None:
    result = risk_service.calculate_var_cvar(VAR_RETURNS, confidence=0.99)
    assert result["var"] == pytest.approx(EXPECTED_VAR_99, rel=REL)


async def test_cvar_99() -> None:
    result = risk_service.calculate_var_cvar(VAR_RETURNS, confidence=0.99)
    assert result["cvar"] == pytest.approx(EXPECTED_CVAR_99, rel=REL)


async def test_var_cvar_guard_prevents_empty_slice() -> None:
    """High confidence + tiny N → var_index=1 → CVaR is a single value, not NaN."""
    tiny = np.array([-0.05, -0.03, -0.01, 0.01, 0.03])
    result = risk_service.calculate_var_cvar(tiny, confidence=0.99)
    assert not np.isnan(result["cvar"])
    assert result["cvar"] == pytest.approx(tiny[0], rel=REL)


async def test_var_cvar_single_observation_uses_only_return() -> None:
    result = risk_service.calculate_var_cvar(np.array([-0.02]), confidence=0.99)

    assert result["var"] == pytest.approx(-0.02, rel=REL)
    assert result["cvar"] == pytest.approx(-0.02, rel=REL)


async def test_var_cvar_uses_252day_window() -> None:
    """Long series (>252 days): only the last 252 days are used."""
    # First 100 returns are extreme losses; last 252 are normal.
    normal = np.zeros(252)  # 0.0 returns
    extreme = np.full(100, -0.10)  # -10% returns (old history)
    long_series = np.concatenate([extreme, normal])

    result = risk_service.calculate_var_cvar(long_series, confidence=0.95)
    # With 252 zeros the VaR should be 0 (or near 0), not -10%
    assert result["var"] == pytest.approx(0.0, abs=1e-9)


async def test_var_cvar_short_window_uses_all() -> None:
    """Series shorter than 252 days: uses all available data."""
    result = risk_service.calculate_var_cvar(VAR_RETURNS, confidence=0.95)
    assert result["n_periods"] == 100


# ─────────────────────────────────────────────────────────────────────────────
# calculate_max_drawdown
# ─────────────────────────────────────────────────────────────────────────────


async def test_max_drawdown_value() -> None:
    result = risk_service.calculate_max_drawdown(DRAWDOWN_RETURNS)
    assert result["max_drawdown"] == pytest.approx(EXPECTED_MAX_DRAWDOWN, rel=REL)


async def test_max_drawdown_peak_trough_indices() -> None:
    """With DatetimeIndex series the result is date strings; check order."""
    result = risk_service.calculate_max_drawdown(DRAWDOWN_RETURNS)
    # peak comes before trough in time
    assert result["peak_date"] < result["trough_date"]


async def test_max_drawdown_no_loss_is_zero() -> None:
    """A monotonically rising series has zero max drawdown."""
    rising = pd.Series([0.01, 0.02, 0.01, 0.03])
    result = risk_service.calculate_max_drawdown(rising)
    assert result["max_drawdown"] == pytest.approx(0.0, abs=1e-9)


async def test_max_drawdown_returns_dates_for_series_with_datetime_index() -> None:
    result = risk_service.calculate_max_drawdown(DRAWDOWN_RETURNS)
    # Should be date strings (ISO format "YYYY-MM-DD")
    assert isinstance(result["peak_date"], str)
    assert isinstance(result["trough_date"], str)


async def test_max_drawdown_returns_indices_for_ndarray() -> None:
    result = risk_service.calculate_max_drawdown(DRAWDOWN_RETURNS.to_numpy())
    assert isinstance(result["peak_date"], int)
    assert isinstance(result["trough_date"], int)


# ─────────────────────────────────────────────────────────────────────────────
# calculate_sortino
# ─────────────────────────────────────────────────────────────────────────────


async def test_sortino_value() -> None:
    result = risk_service.calculate_sortino(
        PORTFOLIO_RETURNS, EXPECTED_ANNUAL_RETURN, RISK_FREE_RATE
    )
    assert result == pytest.approx(EXPECTED_SORTINO, rel=REL)


async def test_sortino_zero_downside_returns_zero() -> None:
    """All-positive returns → downside deviation = 0 → Sortino = 0 (not ÷0 error)."""
    all_positive = np.array([0.01, 0.02, 0.005, 0.03])
    result = risk_service.calculate_sortino(all_positive, annual_return=0.15, rfr=0.04)
    assert result == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# _compute_beta / calculate_beta_from_returns
# ─────────────────────────────────────────────────────────────────────────────


async def test_beta_exactly_two() -> None:
    result = risk_service.calculate_beta_from_returns(PORTFOLIO_BETA_RETURNS, BENCHMARK_RETURNS)
    assert result == pytest.approx(EXPECTED_BETA, rel=REL)


async def test_beta_with_series_aligns_on_index() -> None:
    """Series with a shared DatetimeIndex are aligned correctly."""
    idx = pd.date_range("2023-01-02", periods=10, freq="B")
    bench = pd.Series(BENCHMARK_RETURNS, index=idx)
    port = pd.Series(PORTFOLIO_BETA_RETURNS, index=idx)
    result = risk_service.calculate_beta_from_returns(port, bench)
    assert result == pytest.approx(2.0, rel=REL)


async def test_beta_zero_benchmark_variance_returns_zero() -> None:
    """Constant benchmark → zero variance → beta = 0 (no ÷0 error)."""
    bench = np.full(10, 0.005, dtype=np.float64)  # constant
    port = np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02, 0.01, -0.01])
    result = risk_service._compute_beta(port, bench)
    assert result == 0.0


async def test_beta_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="Length mismatch"):
        risk_service._compute_beta(np.ones(5), np.ones(6))


# ─────────────────────────────────────────────────────────────────────────────
# calculate_correlation_matrix
# ─────────────────────────────────────────────────────────────────────────────


async def test_correlation_matrix_diagonal_is_one() -> None:
    result = risk_service.calculate_correlation_matrix(RETURNS_DF)
    matrix = np.array(result["matrix"])
    np.testing.assert_allclose(np.diag(matrix), 1.0, atol=1e-10)


async def test_correlation_matrix_tickers_match_df_columns() -> None:
    result = risk_service.calculate_correlation_matrix(RETURNS_DF)
    assert result["tickers"] == list(RETURNS_DF.columns)


async def test_correlation_matrix_perfectly_correlated_series() -> None:
    """Two identical return series must have off-diagonal correlation = 1."""
    same_df = pd.DataFrame({"X": PORTFOLIO_RETURNS, "Y": PORTFOLIO_RETURNS})
    result = risk_service.calculate_correlation_matrix(same_df)
    assert result["matrix"][0][1] == pytest.approx(1.0, abs=1e-10)


async def test_correlation_matrix_zero_variance_fills_nan() -> None:
    """A constant-return ticker produces NaN correlation; result is 0.0 (not NaN)."""
    df = pd.DataFrame(
        {"NORMAL": PORTFOLIO_RETURNS, "FLAT": [0.0] * len(PORTFOLIO_RETURNS)}
    )
    result = risk_service.calculate_correlation_matrix(df)
    matrix = result["matrix"]
    # Diagonal must remain 1.0 even for the constant-return ticker
    assert matrix[0][0] == pytest.approx(1.0, abs=1e-10)
    assert matrix[1][1] == pytest.approx(1.0, abs=1e-10)
    # Off-diagonal for the zero-variance pair must be 0.0 (NaN replaced), not nan
    assert matrix[0][1] == pytest.approx(0.0, abs=1e-10)
    assert not any(
        v != v  # NaN check via identity (NaN != NaN)
        for row in matrix
        for v in row
    )

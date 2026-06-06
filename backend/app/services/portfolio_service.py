"""Portfolio-level business logic: weight extraction, CRUD, and risk/return metrics.

All financial math for portfolios lives here (never inline in `app/api/v1/*`) —
see `CLAUDE.md` "Financial Math Correctness".
"""

import numpy as np
import numpy.typing as npt

from app.models.holding import Holding


def portfolio_to_weights(holdings: list[Holding]) -> tuple[list[str], npt.NDArray[np.float64]]:
    """Convert a portfolio's holdings into parallel ticker/weight arrays for numpy/scipy math.

    `Holding.target_weight` is stored as `Decimal` — exact and DB-safe — but
    every downstream calculation (`calculate_portfolio_metrics`, the efficient
    frontier solver, Monte Carlo, VaR/CVaR, ...) operates on `float64`
    `np.ndarray` weights via numpy/pandas/scipy. This is the single place that
    `Decimal` -> `float` conversion happens (locked architecture decision #8),
    so rounding behavior can't drift independently across call sites.

    Returns `(tickers, weights)` as index-aligned sequences: `weights[i]` is
    the target weight for `tickers[i]`. Callers that need the weights to sum to
    1.0 should validate at the point holdings are written (`add`/`update`
    endpoints), not here — re-checking on every read would mask the same bug
    that already passed validation, while flagging legitimately transient states.
    """
    tickers = [holding.ticker for holding in holdings]
    weights = np.array([float(holding.target_weight) for holding in holdings], dtype=np.float64)
    return tickers, weights

"""Tests for MarketDataService and /api/v1/market endpoints.

Unit tests use fakeredis for cache isolation and patch yfinance at the
module level (``app.services.market_data_service.yf``). All async tests run
on the session-scoped event loop via conftest.py's modifyitems hook.

Integration/smoke tests that require live Yahoo Finance access are gated
behind the ``INTEGRATION_TESTS=1`` environment variable.
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pandas as pd
import pytest
import redis.asyncio
from app.core.redis import get_redis
from app.main import create_app
from app.services.market_data_service import MarketDataService
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    r: fakeredis.aioredis.FakeRedis = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


@pytest.fixture
def market_service(fake_redis: fakeredis.aioredis.FakeRedis) -> MarketDataService:
    return MarketDataService(fake_redis)


@pytest.fixture
async def market_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[get_redis] = lambda: fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _make_returns_df(tickers: list[str], n: int = 5) -> pd.DataFrame:
    """Build a minimal returns DataFrame for use in mocks."""

    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    data = {t: [0.01, -0.02, 0.015, -0.005, 0.008][:n] for t in tickers}
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# Unit tests: cache hit / miss
# ---------------------------------------------------------------------------


async def test_cache_hit_skips_yfinance(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Second call must return cached data without calling yfinance.download."""
    tickers = ["VTI", "BND"]
    df = _make_returns_df(tickers)
    serial = df.to_json(orient="split", date_format="iso")
    key = "qv:mds:returns:BND,VTI:1y"
    await fake_redis.setex(key, 86400, serial)

    with patch("app.services.market_data_service.yf.download") as mock_dl:
        result_df, dropped = await market_service.get_historical_returns(tickers, "1y")

    mock_dl.assert_not_called()
    assert dropped == []
    assert list(result_df.columns) == tickers


async def test_cache_miss_writes_to_cache(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Cache miss: fetch function is called, result written to Redis."""
    tickers = ["SPY"]
    df = _make_returns_df(tickers)

    with patch.object(MarketDataService, "_fetch_and_process_returns", return_value=(df, [])):
        await market_service.get_historical_returns(tickers, "1y")

    key = "qv:mds:returns:SPY:1y"
    cached = await fake_redis.get(key)
    assert cached is not None


async def test_returns_cache_ttl(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Returns cache TTL must be 86400 s (24 h)."""
    tickers = ["SPY"]
    df = _make_returns_df(tickers)

    with patch.object(MarketDataService, "_fetch_and_process_returns", return_value=(df, [])):
        await market_service.get_historical_returns(tickers, "1y")

    key = "qv:mds:returns:SPY:1y"
    ttl = await fake_redis.ttl(key)
    assert ttl == pytest.approx(86400, abs=2)


async def test_rfr_cache_ttl(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Risk-free-rate cache TTL must be 86400 s (24 h)."""
    raw_df = pd.DataFrame({"Close": [4.21]})
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        await market_service.get_risk_free_rate()

    ttl = await fake_redis.ttl("qv:mds:rfr")
    assert ttl == pytest.approx(86400, abs=2)


async def test_info_cache_ttl(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Ticker info cache TTL must be 604800 s (7 d)."""
    mock_ticker = MagicMock()
    mock_ticker.info = {"longName": "SPDR S&P 500 ETF", "sector": None}
    with patch("app.services.market_data_service.yf.Ticker", return_value=mock_ticker):
        await market_service.get_ticker_info("SPY")

    ttl = await fake_redis.ttl("qv:mds:info:SPY")
    assert ttl == pytest.approx(604800, abs=2)


async def test_quote_cache_ttl(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Quote cache TTL must be 900 s (15 min)."""
    raw_df = pd.DataFrame({"Close": [450.0, 451.5]})
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        await market_service.get_quote("SPY")

    ttl = await fake_redis.ttl("qv:mds:quote:SPY")
    assert ttl == pytest.approx(900, abs=2)


# ---------------------------------------------------------------------------
# Unit tests: Redis failure / corrupt cache fall-through
# ---------------------------------------------------------------------------


async def test_redis_failure_falls_through(
    market_service: MarketDataService,
) -> None:
    """RedisError on cache read must not propagate — fetch falls through."""
    tickers = ["SPY"]
    df = _make_returns_df(tickers)

    broken_redis = AsyncMock()
    broken_redis.get.side_effect = redis.RedisError("conn refused")
    broken_redis.setex = AsyncMock()
    market_service._redis = broken_redis

    with patch.object(
        MarketDataService, "_fetch_and_process_returns", return_value=(df, [])
    ) as mock_fn:
        result_df, _ = await market_service.get_historical_returns(tickers, "1y")

    mock_fn.assert_called_once()
    assert not result_df.empty


async def test_corrupt_cache_falls_through(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """Invalid JSON in cache must fall through to fetch, not raise."""
    await fake_redis.setex("qv:mds:returns:SPY:1y", 86400, b"not-valid-json")
    df = _make_returns_df(["SPY"])

    with patch.object(
        MarketDataService, "_fetch_and_process_returns", return_value=(df, [])
    ) as mock_fn:
        result_df, _ = await market_service.get_historical_returns(["SPY"], "1y")

    mock_fn.assert_called_once()
    assert not result_df.empty


# ---------------------------------------------------------------------------
# Unit tests: data quality
# ---------------------------------------------------------------------------


async def test_empty_dataframe_raises_valueerror(market_service: MarketDataService) -> None:
    """Empty DataFrame from yfinance must raise ValueError, not return empty data."""
    with (
        patch(
            "app.services.market_data_service.yf.download",
            return_value=pd.DataFrame(),
        ),
        pytest.raises(ValueError, match="No valid historical data"),
    ):
        await market_service.get_historical_returns(["FAKE123"], "1y")


async def test_partial_result_not_cached(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """When a ticker is dropped for data quality, the partial result must NOT be cached."""
    # Simulate fetch returning only VTI (MISSINGXYZ dropped for data quality)
    df = _make_returns_df(["VTI"])

    with patch.object(
        MarketDataService, "_fetch_and_process_returns", return_value=(df, ["MISSINGXYZ"])
    ):
        _, dropped = await market_service.get_historical_returns(["VTI", "MISSINGXYZ"], "1y")

    assert "MISSINGXYZ" in dropped
    cached = await fake_redis.get("qv:mds:returns:MISSINGXYZ,VTI:1y")
    assert cached is None


async def test_data_quality_drops_large_gap() -> None:
    """Ticker with > 5 consecutive NaN days must be dropped and listed."""
    svc = MarketDataService(AsyncMock())
    dates = pd.date_range("2024-01-01", periods=12, freq="B")
    returns = pd.DataFrame(
        {
            "VTI": [0.01, 0.02, None, None, None, None, None, None, 0.01, 0.02, 0.01, 0.02],
            "BND": [
                0.001,
                0.002,
                0.001,
                0.002,
                0.001,
                0.002,
                0.001,
                0.002,
                0.001,
                0.002,
                0.001,
                0.002,
            ],
        },
        index=dates,
    )
    result, dropped = svc._apply_data_quality(returns, ["VTI", "BND"])
    assert "VTI" in dropped
    assert "BND" not in dropped
    assert "BND" in result.columns


async def test_data_quality_ffills_small_gap() -> None:
    """Ticker with ≤ 5 consecutive NaN days must be forward-filled and kept."""
    svc = MarketDataService(AsyncMock())
    dates = pd.date_range("2024-01-01", periods=8, freq="B")
    returns = pd.DataFrame(
        {"SPY": [0.01, None, None, None, 0.02, 0.01, 0.03, 0.01]},
        index=dates,
    )
    result, dropped = svc._apply_data_quality(returns, ["SPY"])
    assert "SPY" not in dropped
    assert result["SPY"].isna().sum() == 0  # gap is filled


# ---------------------------------------------------------------------------
# Unit tests: cache key format + RFR math
# ---------------------------------------------------------------------------


async def test_cache_key_has_qv_mds_prefix_returns(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """All historical-returns cache keys must start with qv:mds:returns:."""
    df = _make_returns_df(["AAPL"])
    with patch.object(MarketDataService, "_fetch_and_process_returns", return_value=(df, [])):
        await market_service.get_historical_returns(["AAPL"], "1y")

    keys = [k.decode() for k in await fake_redis.keys("*")]
    assert all(k.startswith("qv:mds:") for k in keys)
    assert any(k.startswith("qv:mds:returns:") for k in keys)


async def test_cache_key_rfr_exact(
    market_service: MarketDataService, fake_redis: fakeredis.aioredis.FakeRedis
) -> None:
    """RFR cache key must be exactly qv:mds:rfr."""
    raw_df = pd.DataFrame({"Close": [4.21]})
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        await market_service.get_risk_free_rate()

    assert await fake_redis.exists("qv:mds:rfr")


async def test_rfr_fallback_on_network_failure(market_service: MarketDataService) -> None:
    """get_risk_free_rate must return 0.04 when yfinance raises any exception."""
    with patch(
        "app.services.market_data_service.yf.download",
        side_effect=Exception("connection refused"),
    ):
        rfr = await market_service.get_risk_free_rate()

    assert rfr == pytest.approx(0.04)


async def test_rfr_decimal_conversion(market_service: MarketDataService) -> None:
    """^TNX raw value 4.21 (percent) must map to 0.0421 (decimal), NOT 0.421.

    Decision #25: Yahoo Finance quotes ^TNX as a percentage (4.21 = 4.21%).
    Divide by 100 to get the decimal risk-free rate.  ``/ 10`` is wrong.
    """
    raw_df = pd.DataFrame({"Close": [4.21]})
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        rfr = await market_service.get_risk_free_rate()

    assert rfr == pytest.approx(0.0421, rel=1e-4)
    assert rfr != pytest.approx(0.421, rel=1e-4)  # guard: not /10


async def test_column_order_matches_requested_tickers(
    market_service: MarketDataService,
) -> None:
    """Returned DataFrame columns must be in the REQUESTED order, not sorted order.

    This is decision #24 — Phase 3 dot products with portfolio_to_weights()
    weights depend on the order matching holdings order, not ticker sort order.
    """
    # Request in reverse-alphabetical order; cache key sorts, but output must not
    requested = ["VTI", "BND", "VXUS"]
    df = _make_returns_df(requested)

    with patch.object(MarketDataService, "_fetch_and_process_returns", return_value=(df, [])):
        result_df, dropped = await market_service.get_historical_returns(requested, "1y")

    assert list(result_df.columns) == requested
    assert dropped == []


# ---------------------------------------------------------------------------
# Integration / HTTP tests
# ---------------------------------------------------------------------------


async def test_public_endpoints_no_auth_required(
    market_client: AsyncClient,
) -> None:
    """Market endpoints must be reachable without an auth token (status != 401/403)."""
    search_mock = MagicMock()
    search_mock.quotes = []
    with patch("app.services.market_data_service.yf.Search", return_value=search_mock):
        resp = await market_client.get("/api/v1/market/search?q=Apple")
    assert resp.status_code not in (401, 403)


async def test_history_422_on_empty_data(market_client: AsyncClient) -> None:
    """GET /market/{ticker}/history returns 422 when yfinance has no data."""
    with patch(
        "app.services.market_data_service.yf.download",
        return_value=pd.DataFrame(),
    ):
        resp = await market_client.get("/api/v1/market/FAKE999/history?period=1y")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unit tests: MultiIndex column format (yfinance 0.2.51 default multi_level_index=True)
# ---------------------------------------------------------------------------


async def test_rfr_multiindex_column_format(market_service: MarketDataService) -> None:
    """_fetch_rfr must handle MultiIndex columns returned by yfinance 0.2.51+ by default.

    yfinance 0.2.51 sets multi_level_index=True by default, so all yf.download()
    calls return MultiIndex columns even for a single ticker. raw["Close"] is then a
    DataFrame (not a Series), and the isinstance guard must extract the Series via .iloc[:,0].
    Without this guard, float(DataFrame.iloc[-1]) triggers FutureWarning now and will
    raise TypeError in a future pandas version.
    """
    raw_df = pd.DataFrame(
        [[4.21], [4.20]],
        columns=pd.MultiIndex.from_tuples([("Close", "^TNX")]),
    )
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        rfr = await market_service.get_risk_free_rate()

    assert rfr == pytest.approx(0.0420, rel=1e-4)


async def test_quote_multiindex_column_format(market_service: MarketDataService) -> None:
    """_fetch_quote must handle MultiIndex columns from yfinance 0.2.51+ default."""
    raw_df = pd.DataFrame(
        [[450.0], [451.5]],
        columns=pd.MultiIndex.from_tuples([("Close", "SPY")]),
    )
    with patch("app.services.market_data_service.yf.download", return_value=raw_df):
        quote = await market_service.get_quote("SPY")

    assert quote["price"] == pytest.approx(451.5, rel=1e-4)
    assert quote["change"] == pytest.approx(1.5, rel=1e-4)


# ---------------------------------------------------------------------------
# Unit tests: API endpoint edge cases
# ---------------------------------------------------------------------------


async def test_history_422_on_invalid_period(market_client: AsyncClient) -> None:
    """GET /market/{ticker}/history returns 422 for a period not in _VALID_PERIODS."""
    resp = await market_client.get("/api/v1/market/SPY/history?period=bogus")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unit tests: data quality boundary
# ---------------------------------------------------------------------------


async def test_data_quality_boundary_exactly_max_gap() -> None:
    """Ticker with exactly _MAX_GAP=5 consecutive NaN days must be kept and ffilled.

    Fence-post: 5 is the threshold (≤5 kept, >5 dropped). Exactly 5 must survive.
    """
    svc = MarketDataService(AsyncMock())
    dates = pd.date_range("2024-01-01", periods=9, freq="B")
    returns = pd.DataFrame(
        {"SPY": [0.01, None, None, None, None, None, 0.02, 0.01, 0.03]},
        index=dates,
    )
    result, dropped = svc._apply_data_quality(returns, ["SPY"])
    assert "SPY" not in dropped
    assert result["SPY"].isna().sum() == 0


async def test_data_quality_drops_exactly_max_gap_plus_one() -> None:
    """Ticker with exactly _MAX_GAP+1=6 consecutive NaN days must be dropped."""
    svc = MarketDataService(AsyncMock())
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    returns = pd.DataFrame(
        {"SPY": [0.01, None, None, None, None, None, None, 0.02, 0.01, 0.03]},
        index=dates,
    )
    _, dropped = svc._apply_data_quality(returns, ["SPY"])
    assert "SPY" in dropped


# ---------------------------------------------------------------------------
# Unit tests: validate_tickers service method
# ---------------------------------------------------------------------------


async def test_validate_tickers_all_valid(market_service: MarketDataService) -> None:
    """All tickers that return data are classified as valid."""
    non_empty = _make_returns_df(["X"])
    with patch("app.services.market_data_service.yf.download", return_value=non_empty):
        valid, invalid = await market_service.validate_tickers(["VTI", "BND"])
    assert set(valid) == {"VTI", "BND"}
    assert invalid == []


async def test_validate_tickers_all_invalid(market_service: MarketDataService) -> None:
    """All tickers that return empty DataFrames are classified as invalid."""
    with patch(
        "app.services.market_data_service.yf.download",
        return_value=pd.DataFrame(),
    ):
        valid, invalid = await market_service.validate_tickers(["FAKE1", "FAKE2"])
    assert valid == []
    assert set(invalid) == {"FAKE1", "FAKE2"}


async def test_validate_tickers_exception_treated_as_invalid(
    market_service: MarketDataService,
) -> None:
    """A yfinance exception for a ticker classifies it as invalid (not a 500)."""
    with patch(
        "app.services.market_data_service.yf.download",
        side_effect=Exception("network error"),
    ):
        valid, invalid = await market_service.validate_tickers(["SPY"])
    assert valid == []
    assert "SPY" in invalid


# ---------------------------------------------------------------------------
# Unit tests: cache write failure
# ---------------------------------------------------------------------------


async def test_redis_write_failure_does_not_propagate(
    market_service: MarketDataService,
) -> None:
    """RedisError on cache setex must not propagate — result is still returned."""
    import redis as _redis

    broken_redis = AsyncMock()
    broken_redis.get = AsyncMock(return_value=None)
    broken_redis.setex = AsyncMock(side_effect=_redis.RedisError("write failed"))
    market_service._redis = broken_redis

    df = _make_returns_df(["SPY"])
    with patch.object(MarketDataService, "_fetch_and_process_returns", return_value=(df, [])):
        result_df, dropped = await market_service.get_historical_returns(["SPY"], "1y")

    assert not result_df.empty
    assert dropped == []


# ---------------------------------------------------------------------------
# Integration smoke tests (require live Yahoo Finance — gated behind env flag)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.getenv("INTEGRATION_TESTS"),
    reason="Set INTEGRATION_TESTS=1 to run live-network tests",
)
async def test_smoke_spy_history(market_client: AsyncClient) -> None:
    """SPY history smoke test — requires Yahoo Finance network access."""
    resp = await market_client.get("/api/v1/market/SPY/history?period=1mo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "SPY"
    assert len(body["dates"]) > 0
    assert len(body["returns"]) == len(body["dates"])


@pytest.mark.skipif(
    not os.getenv("INTEGRATION_TESTS"),
    reason="Set INTEGRATION_TESTS=1 to run live-network tests",
)
async def test_smoke_tnx_rfr_is_reasonable(
    market_service: MarketDataService,
) -> None:
    """^TNX smoke test — confirms raw→decimal conversion yields a plausible rate.

    A 10-year yield of 0.01 (1%) to 0.10 (10%) is the plausible range.
    Decision #25: Yahoo returns a percentage (e.g. 4.21), divide by 100.
    """
    rfr = await market_service.get_risk_free_rate()
    assert 0.01 <= rfr <= 0.10, f"Risk-free rate {rfr} is outside plausible range 1%-10%"

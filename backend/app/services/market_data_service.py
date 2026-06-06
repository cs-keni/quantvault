"""Market data service: yfinance fetches with Redis caching.

All yfinance calls are sync and blocking; they are wrapped in
`asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)` so they never
block the event loop. Cache failures degrade speed, never correctness.
"""

import asyncio
import io
import json
import logging
from collections.abc import Callable
from typing import Annotated, Any, TypeVar

import pandas as pd
import redis.asyncio
import yfinance as yf
from fastapi import Depends

from app.core.redis import get_redis

_logger = logging.getLogger(__name__)

T = TypeVar("T")


class MarketDataService:
    """Fetch and cache market data from Yahoo Finance.

    Cache key namespace: ``qv:mds:`` — avoids Celery's ``celery-task-meta-*``
    keys sharing Redis DB 0 (architecture decision #23).
    """

    _RETURNS_TTL = 86_400  # 24 h
    _RFR_TTL = 86_400  # 24 h
    _INFO_TTL = 604_800  # 7 d
    _QUOTE_TTL = 900  # 15 min
    _MAX_GAP = 5  # max consecutive NaN days before a ticker is dropped

    def __init__(self, redis_client: redis.asyncio.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _cache_through(
        self,
        key: str,
        ttl: int,
        fetch_fn: Callable[[], T],
        serialize: Callable[[T], str],
        deserialize: Callable[[str], T],
    ) -> T:
        """Generic cache-get / miss / set helper.

        On any Redis error or deserialization failure: log a warning and fall
        through to a live fetch (cache is optional — degrades speed, not
        correctness).
        """
        try:
            cached = await self._redis.get(key)
            if cached is not None:
                raw = cached.decode()
                return deserialize(raw)
        except (redis.RedisError, json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
            _logger.warning("cache read failed key=%s: %s", key, exc)

        result: T = await asyncio.wait_for(asyncio.to_thread(fetch_fn), timeout=30.0)

        try:
            await self._redis.setex(key, ttl, serialize(result))
        except redis.RedisError as exc:
            _logger.warning("cache write failed key=%s: %s", key, exc)

        return result

    def _apply_data_quality(
        self, returns: pd.DataFrame, requested: list[str]
    ) -> tuple[pd.DataFrame, list[str]]:
        """Drop tickers with >5-day NaN gaps; forward-fill surviving tickers."""
        dropped: list[str] = []
        valid_cols: list[str] = []

        for ticker in requested:
            if ticker not in returns.columns:
                dropped.append(ticker)
                continue
            col = returns[ticker]
            is_nan = col.isna()
            max_gap = int(is_nan.groupby((~is_nan).cumsum()).sum().max()) if is_nan.any() else 0

            if max_gap > self._MAX_GAP:
                dropped.append(ticker)
            else:
                valid_cols.append(ticker)

        if not valid_cols:
            return pd.DataFrame(), dropped

        result: pd.DataFrame = returns[valid_cols].ffill().dropna(how="all")
        return result, dropped

    def _fetch_and_process_returns(
        self, tickers: list[str], period: str
    ) -> tuple[pd.DataFrame, list[str]]:
        """Sync: download OHLCV, compute daily pct returns, apply data quality."""
        download_arg: str | list[str] = tickers[0] if len(tickers) == 1 else tickers
        raw: pd.DataFrame = yf.download(
            download_arg, period=period, progress=False, auto_adjust=True
        )

        if raw.empty:
            return pd.DataFrame(columns=tickers), list(tickers)

        if isinstance(raw.columns, pd.MultiIndex):
            close: pd.DataFrame = raw["Close"]
        else:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})

        returns: pd.DataFrame = close.pct_change().iloc[1:]
        return self._apply_data_quality(returns, tickers)

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    async def get_historical_returns(
        self, tickers: list[str], period: str = "1y"
    ) -> tuple[pd.DataFrame, list[str]]:
        """Fetch daily percentage returns aligned to all requested tickers.

        Returns a DataFrame (dates x tickers) in *requested* ticker order and
        a list of any tickers that were dropped for data quality (>5-day gaps).
        Partial results are NOT written to cache — only complete fetches are
        cached (architecture decision #21).

        The cache key sorts tickers for consistency across callers; the returned
        DataFrame is reindexed to the caller's requested order so that dot
        products with `portfolio_to_weights()` weights are always aligned
        (architecture decision #24).
        """
        sorted_tickers = sorted(tickers)
        key = f"qv:mds:returns:{','.join(sorted_tickers)}:{period}"

        # --- try cache ---
        try:
            cached = await self._redis.get(key)
            if cached is not None:
                df: pd.DataFrame = pd.read_json(io.StringIO(cached.decode()), orient="split")
                return df[tickers], []
        except (redis.RedisError, json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
            _logger.warning("cache read failed key=%s: %s", key, exc)

        # --- fetch live ---
        df, dropped = await asyncio.wait_for(
            asyncio.to_thread(self._fetch_and_process_returns, sorted_tickers, period),
            timeout=30.0,
        )

        if df.empty:
            raise ValueError(f"No valid historical data for tickers: {tickers}")

        # --- cache only complete results ---
        if not dropped:
            try:
                serial = df.to_json(orient="split", date_format="iso")
                await self._redis.setex(key, self._RETURNS_TTL, serial)
            except redis.RedisError as exc:
                _logger.warning("cache write failed key=%s: %s", key, exc)

        surviving = [t for t in tickers if t not in dropped]
        return df[surviving], dropped

    async def get_risk_free_rate(self) -> float:
        """Fetch the annualized risk-free rate from ^TNX (10-year Treasury yield).

        Yahoo Finance quotes ^TNX as a percentage (e.g. 4.21 = 4.21% yield).
        Divide by 100 to get a decimal rate (0.0421). Falls back to 0.04 on
        any fetch or conversion failure. Decision #25: this is `/ 100`, NOT
        `/ 10` — the "divide by 10" note in original docs was wrong.
        """
        try:
            return await self._cache_through(
                "qv:mds:rfr",
                self._RFR_TTL,
                self._fetch_rfr,
                serialize=str,
                deserialize=float,
            )
        except Exception as exc:
            _logger.warning("get_risk_free_rate failed, using 0.04 fallback: %s", exc)
            return 0.04

    def _fetch_rfr(self) -> float:
        try:
            raw: pd.DataFrame = yf.download("^TNX", period="5d", progress=False, auto_adjust=True)
            if raw.empty:
                return 0.04
            pct_value = float(raw["Close"].iloc[-1])
            return pct_value / 100
        except Exception as exc:
            _logger.warning("^TNX fetch failed: %s; using 0.04", exc)
            return 0.04

    async def get_ticker_info(self, ticker: str) -> dict[str, Any]:
        """Fetch company metadata (name, sector, industry, market cap, currency, exchange)."""
        return await self._cache_through(
            f"qv:mds:info:{ticker.upper()}",
            self._INFO_TTL,
            lambda: self._fetch_info(ticker),
            serialize=json.dumps,
            deserialize=json.loads,
        )

    def _fetch_info(self, ticker: str) -> dict[str, Any]:
        info: dict[str, Any] = yf.Ticker(ticker).info
        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
        }

    async def get_quote(self, ticker: str) -> dict[str, Any]:
        """Fetch the most recent closing price and day-over-day change."""
        return await self._cache_through(
            f"qv:mds:quote:{ticker.upper()}",
            self._QUOTE_TTL,
            lambda: self._fetch_quote(ticker),
            serialize=json.dumps,
            deserialize=json.loads,
        )

    def _fetch_quote(self, ticker: str) -> dict[str, Any]:
        raw: pd.DataFrame = yf.download(ticker, period="2d", progress=False, auto_adjust=True)
        if raw.empty:
            raise ValueError(f"No quote data for {ticker}")
        prices = raw["Close"]
        last = float(prices.iloc[-1])
        prev = float(prices.iloc[-2]) if len(prices) >= 2 else last
        change = last - prev
        change_pct = (change / prev * 100) if prev != 0.0 else 0.0
        return {
            "ticker": ticker.upper(),
            "price": round(last, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
        }

    async def search_tickers(self, query: str) -> list[dict[str, Any]]:
        """Search for tickers matching the given query string (not cached — always fresh)."""
        return await asyncio.wait_for(
            asyncio.to_thread(self._fetch_search, query),
            timeout=30.0,
        )

    def _fetch_search(self, query: str) -> list[dict[str, Any]]:
        try:
            search = yf.Search(query, max_results=10)
            results: list[dict[str, Any]] = []
            for item in search.quotes or []:
                results.append(
                    {
                        "ticker": item.get("symbol", ""),
                        "name": item.get("longname") or item.get("shortname"),
                        "exchange": item.get("exchDisp") or item.get("exchange"),
                        "asset_type": item.get("quoteType"),
                    }
                )
            return results
        except Exception as exc:
            _logger.warning("search_tickers failed for query=%r: %s", query, exc)
            return []

    async def validate_tickers(self, tickers: list[str]) -> tuple[list[str], list[str]]:
        """Check which tickers return data from Yahoo Finance."""

        def _check(ticker: str) -> bool:
            try:
                raw: pd.DataFrame = yf.download(
                    ticker, period="5d", progress=False, auto_adjust=True
                )
                return not raw.empty
            except Exception:
                return False

        raw_results = await asyncio.gather(
            *[asyncio.wait_for(asyncio.to_thread(_check, t), timeout=15.0) for t in tickers],
            return_exceptions=True,
        )

        valid: list[str] = []
        invalid: list[str] = []
        for ticker, result in zip(tickers, raw_results, strict=False):
            if result is True:
                valid.append(ticker)
            else:
                invalid.append(ticker)

        return valid, invalid


async def get_market_data_service(
    redis_client: Annotated[redis.asyncio.Redis, Depends(get_redis)],
) -> MarketDataService:
    """FastAPI dependency yielding a MarketDataService backed by the shared Redis client."""
    return MarketDataService(redis_client)

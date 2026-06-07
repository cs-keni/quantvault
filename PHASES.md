# QuantVault — Implementation Phases

> All architecture decisions from the `/plan-eng-review` (2026-06-05) are reflected here.
> Mark tasks `[x]` in real time as we progress. Run `/review` before marking any financial math phase complete.

---

## Architecture Decisions Locked In

| # | Decision | Rationale |
|---|---|---|
| 1 | PyJWT (not python-jose) | python-jose has active CVEs |
| 2 | Celery + Redis for CPU-heavy tasks | efficient frontier, Monte Carlo, backtesting offloaded to workers |
| 3 | yfinance-only, Redis 24h TTL | no paid fallback; TTL accepted as sufficient |
| 4 | VaR annual = rolling 252-day windows | sqrt(252) scaling is wrong for historical simulation |
| 5 | Monte Carlo uses `standard_t(df=5)` | fat-tail distribution; interview differentiator |
| 6 | Backtest: init `current_allocation` from `price_data.iloc[0]` | prevents UnboundLocalError on day 1 |
| 7 | `User.default_portfolio_id FK` (not `Portfolio.is_default bool`) | avoids multi-row constraint bugs |
| 8 | `portfolio_to_weights()` centralized in portfolio_service.py | single Decimal→float conversion point |
| 9 | Sequential warm-start loop for frontier (NOT ProcessPoolExecutor) | fork-from-Celery-prefork risk; warm starts make 100×10ms=1s fast enough without PPE |
| 10 | MC capped: `n_simulations ≤ 1000`, `years ≤ 30` | Pydantic validators; prevents memory explosion |
| 11 | MC contributions: inject at year boundary, compound forward | `cumprod` add-to-all approach is financially wrong |
| 12 | CVaR: `var_index = max(int(...), 1)` | prevents empty slice → NaN at high confidence levels |
| 13 | Frontier target range: solve min-variance first as lower bound | naive `min(returns)` generates infeasible targets |
| 14 | Beta: `_compute_beta` + two public wrappers | resolves spec signature conflict between API and backtest callers |
| 15 | Redis client: module-level singleton in `app/core/redis.py` | mirrors `database.py` pattern; lazy connection, test-overridable via `app.dependency_overrides[get_redis]` |
| 16 | `MarketDataService` wired via `get_market_data_service()` FastAPI DI | testable override pattern; consistent with `get_current_user`/`get_db` idiom |
| 17 | `_cache_through(key, ttl, fetch_fn, serialize, deserialize)` private helper | DRY: 4 methods share identical cache-get/miss/set flow; error handling written once |
| 18 | yfinance calls wrapped in `asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)` | prevents event-loop blocking; 30s cap stops hung requests from exhausting uvicorn thread pool |
| 19 | Redis failures (ConnectionError, deserialization error) → log warning, fall through to live fetch | cache is an optimization; Redis being down degrades speed, not correctness |
| 20 | Empty DataFrame from yfinance → `ValueError` → 422 | catches delisted/unknown tickers at service boundary; prevents cryptic numpy errors downstream |
| 21 | Partial results (dropped tickers) NOT cached; return partial + warning in response | cache hit must return exactly what key implies; transient gaps self-heal on next fetch |
| 22 | Cache serialization: `pd.DataFrame.to_json(orient='split', date_format='iso')` | fixed schema prevents shape/precision drift between cache hits and live fetches |
| 23 | Cache key namespace: `qv:mds:` prefix on all MarketDataService keys | prevents collision with Celery's `celery-task-meta-*` keys sharing Redis DB 0 |
| 24 | `get_historical_returns()` reindexes output: `returns_df[tickers]` (requested order, not sorted) | sorted tickers needed for cache key consistency; returned DataFrame must match caller's weight order for correct dot products in Phase 3 |
| 25 | `^TNX` math: Yahoo returns yield as percentage (e.g. 4.21 = 4.21%) → `raw / 100` gives decimal 0.0421 | "divide by 10" in original docs was wrong — `4.2 / 10 = 0.42` (42%), not a risk-free rate; fallback `0.04` cross-confirms: raw ~4.0 / 100 = 0.04 |
| 26 | `fakeredis[aioredis]` for Redis test isolation | `AsyncMock` can only assert setex called; `fakeredis` enables real cache hit/miss behavioral tests (second call skips yfinance) |
| 27 | Smoke tests gated behind `INTEGRATION_TESTS=1` env flag | live-network tests in default pytest cause flaky CI; mark with `@pytest.mark.skipif(not os.getenv("INTEGRATION_TESTS"), ...)` |
| 28 | Celery task for frontier lives in `app/services/optimization_service.py` (not `celery_tasks/`) | matches pre-written `celery_app.py` include comment and `quantvault.md` architecture diagram |
| 29 | Frontier cache key: `qv:opt:frontier:{sorted_uppercase_tickers}:{period}`, 24h TTL | must uppercase-normalize before building key; rfr excluded from key (24h staleness acceptable) |
| 30 | Frontier optimizer uses arithmetic daily means; reports geometric annual returns | SLSQP target-return constraint must be linear in weights (`w.T @ mu_arith >= target`); geometric return is non-linear and would break MPT math |
| 31 | Celery task timeout: `soft_time_limit=55, time_limit=60` | yfinance fetch can take up to 30s; 25s soft limit (original plan) would kill task before data arrives |
| 32 | Celery task calls `market_data_service._fetch_and_process_returns()` directly (sync); uses `redis.Redis` (sync) | Celery has no FastAPI DI and no event loop; must avoid async |
| 33 | `find_min_variance_portfolio()` does not take `rfr` — min-variance optimization doesn't use it | rfr is only needed for max-Sharpe objective; including it was noisy |
| 34 | `AsyncResult.info` on FAILURE must be serialized to `str()` before JSON response | raw Python exception object is not JSON-safe; FastAPI serializer raises HTTP 500 |
| 35 | Frontier GET endpoint (`GET /api/v1/analysis/frontier/{task_id}`) returns `{task_id, status, result?, error?}` | non-blocking `.state` + `.info` read; never call `.get()` (would block async worker) |
| 36 | Both frontier endpoints require `CurrentUser` auth | same pattern as Phase 3 security fix; unauthenticated callers must not trigger yfinance + Celery work |
| 37 | `FrontierRequest.tickers`: uppercase normalize before dedup check; max 30 tickers; pattern same as `AdHocHolding.ticker` | "AAPL" and "aapl" must be caught as duplicates; ticker count cap prevents slow/unstable covariance for large N |
| 38 | Solver failure at a target return → skip point, return best-effort partial frontier | SLSQP `status != 0` at a specific target is normal (infeasible constraint); the whole task should not fail for partial infeasibility |
| 39 | MC API input: `tickers + weights + period + optional portfolio_id` (ad-hoc, not portfolio_id required) | Enables comparison endpoint (rebalanced scenario has no portfolio_id); mirrors Phase 4 frontier pattern |
| 40 | MC result storage: POST creates `SimulationResult(status="PENDING")`, Celery task writes results | Permanent PostgreSQL storage; GET `/simulation/{id}` reads by DB UUID; no Celery TTL expiry; audit trail |
| 41 | `SimulationResult`: new model file (not reuse `BacktestResult`) | Different schema shape; nullable `portfolio_id`, required `user_id`; separate migration |
| 42 | MC RNG: `np.random.default_rng(seed)` (new-style, isolated per-task RNG) | Thread-safe for concurrent Celery workers; global `np.random.seed()` is not safe under prefork concurrency |
| 43 | Contribution injection: `portfolio_values[year*252 - 1] += annual_contribution` for year in range(1, years+1) | Fence-post fix: yields exactly `years` contributions (not `years-1`); injects at end-of-year |
| 44 | Celery DB bridge: `asyncio.run()` with a **fresh** async engine created+disposed inside each call | Never reuse module-level async engine inside `asyncio.run()`; fresh engine avoids event-loop/pool conflict in prefork workers |
| 45 | t-distribution scaling: `daily_mu + daily_sigma * rng.standard_t(df=5)` (direct scale, no variance normalization) | Decision #5 intent: fat tails + slightly inflated baseline vol (realized vol ≈ 1.29x historical); document in docstring |
| 46 | `probability_of_profit`: `(final_values > initial_investment + annual_contribution * years).mean()` | Financially correct when contributions > 0; `final_value > initial_investment` is misleading when user has also contributed capital |
| 47 | `SimulationResult` stores `tickers` (JSONB), `weights` (JSONB), `period` (str) | Audit + reproduction: row is self-describing; inputs visible even on FAILURE state |
| 48 | GET `/simulation/{id}`: filter `WHERE id=? AND user_id=?` | Auth alone does not prevent cross-user reads; explicit user_id filter required |
| 49 | POST validates `portfolio_id` ownership if provided: must belong to `current_user` | Same security principle as Phase 3 auth fix; unauthenticated/wrong-owner access must be 403/404 |
| 50 | Celery timeout: `soft_time_limit=55, time_limit=60` (same as Phase 4) | yfinance fetch dominates; same 55s soft limit prevents zombie tasks |
| 51 | Dispatch failure (DB row committed, Celery dispatch fails): log error, return 500; add TODO for orphan cleanup | Best-effort at MVP scale; PENDING rows are visible (not silent); user can re-submit |
| 52 | `SimulationResult.status` is a native Postgres enum `simulation_status {PENDING, SUCCESS, FAILURE}` | Consistent with `RebalanceFrequency` enum pattern in `BacktestResult` |
| 53 | Input validation: ticker regex `^[A-Za-z0-9.^=\-]{1,20}$`, uppercase-normalize, dedup; weights non-negative + sum to 1.0 ± 0.001; `years >= 1`; `n_simulations >= 1`; period must be `_AnalysisPeriod` literal | Inherit all validation patterns from Phase 2 ticker whitelist and Phase 3 weight validation |
| 54 | Dropped tickers from yfinance → reject simulation with 422 (do not re-normalize weights silently) | Silent weight re-normalization changes the user's portfolio composition without their knowledge |
| 55 | `sample_paths`: select 20 paths by index spread evenly across sorted final values (quantile-sampled) for visual diversity | Deterministic selection rule: `np.linspace(0, n_simulations-1, 20, dtype=int)` on argsorted final values |
| 56 | Backtest: Celery + PENDING row pattern (same as Phase 5); `BacktestResult` gets `status`/`task_id`/`error` columns via migration | CPU-bound; long (10yr) backtests must not block the FastAPI event loop |
| 57 | Add `user_id` FK to `BacktestResult` (NOT NULL); backfill existing rows via `portfolio_id → portfolios.user_id` | Consistent auth scoping with `SimulationResult`; backfill makes migration safe for existing rows |
| 58 | Add `tickers` (JSONB) + `weights` (JSONB) to `BacktestResult`; make `tearsheet`/`daily_returns`/`equity_curve` nullable | Input audit trail for FAILURE rows; nullable blobs required for PENDING rows before Celery writes results |
| 59 | Jensen's Alpha: `alpha = CAGR_portfolio − (rfr + beta × (CAGR_benchmark − rfr))`; rfr = current `^TNX` ÷ 100; document static-rfr limitation in docstring | Static rfr acceptable at demo scale; historically misleading for multi-decade backtests — limitation must be documented |
| 60 | Data availability check: fail (`FAILURE`, no task started) if any ticker's data starts >5 trading days after `start_date` OR ends >5 trading days before `end_date` | Catches both late-start (IPO) and early-end (delisted) silently truncated series; symmetric check prevents corrupted equity curves |
| 61 | `_celery_db.py` extraction: copy the NullPool + asyncio.run() bridge into `backtest_service.py` now; extract shared helper after Phase 6 ships | Phase 5 (134 tests passing) must never be touched during Phase 6 work; copy-first isolates regression risk |
| 62 | GET `/portfolios/{id}/backtests` returns `BacktestSummary` items only — `strategy_name`, `status`, `start_date`, `end_date`, `created_at`, and top-level tearsheet scalar fields (no `equity_curve`, `daily_returns` arrays) | Prevents accidentally serving O(n) arrays in a list endpoint; summary schema defined as explicit Pydantic model, not dynamic tearsheet key reads |
| 63 | Backtest CAGR: `(final_portfolio_value / initial_investment)^(252 / n_trading_days) − 1` (true terminal CAGR) | Do NOT reuse `calculate_portfolio_metrics()` for CAGR; that returns `(1+mean_daily)^252−1`, which was already caught as wrong in Phase 5 review |
| 64 | `calmar: Optional[float]` — return `None` when `max_drawdown == 0`; document in field description | JSON does not allow `Infinity` (RFC 8259); `0.0` is actively misleading (implies zero CAGR); `None` is the honest representation of an undefined ratio |
| 65 | Benchmark source: read `portfolio.benchmark_ticker` (defaults to `"SPY"`); if benchmark_ticker collides with a portfolio holding, fetch benchmark in a separate `yf.download()` call | `Portfolio.benchmark_ticker` was added in Phase 1 for this purpose; hardcoding SPY ignores existing user data and causes duplicate-column crash when portfolio already holds SPY |
| 66 | NEVER rebalance (buy-and-hold) formula: `equity_t = initial_investment × Σ(w_i × Π(1 + r_{i,s}) for s=1..t)` | `cumprod(1 + weighted_daily_returns)` implicitly rebalances to original weights every day; true buy-and-hold tracks each asset's independent cumulative return |
| 67 | yfinance `end` parameter is exclusive: fetch through `end_date + 1 calendar day` to include the requested last trading day | yfinance drops the `end` date from the result; without `+1 day`, the equity curve is always missing the final trading day |
| 68 | Win rate = fraction of trading days where portfolio return > 0; zero-return days count as non-wins; document in `BacktestResult.tearsheet` schema | Common convention; zero-return days are rare for a multi-asset portfolio; limitation documented in field description |
| 69 | Rebalance timing: rebalance at close of the first trading day of each new calendar period — apply rebalance AFTER that day's return, BEFORE recording that day's equity curve value | Makes rebalance_count verifiable: count periods with a boundary trading day in [start+1, end] |
| 70 | Dispatch failure (POST commits PENDING, then Celery `.delay()` raises): log error, return HTTP 500; PENDING row stays visible (not silent); add TODO-6 for orphan cleanup | Same pattern as Phase 5 TODO-4; acceptable at demo scale |

---

## Phase 0 — Setup and Scaffolding
- [x] Create GitHub repo `cs-keni/quantvault`
- [x] Write `quantvault.md` (canonical spec)
- [x] Write `CLAUDE.md` (agent instructions + gbrain config)
- [x] Register gbrain (Supabase engine, session pooler mode)
- [x] Sync gbrain — `.gbrain-source` pin: `gstack-code-quantvault-ddd199b6`
- [x] Run `/plan-eng-review` — architecture locked, all 14 decisions recorded
- [x] Initialize FastAPI project structure (backend/ folder)
- [x] Initialize React + TypeScript project (frontend/ folder)
- [x] Set up PostgreSQL + Redis with Docker Compose
- [x] Configure Alembic for migrations
- [x] Set up pytest + ruff + mypy + pre-commit hooks
- [x] Set up Celery worker service in Docker Compose
- [x] Create docs/: `AI_CONTEXT.md`, `HANDOFF.md`, `ENGINEERING_LOG.md`, `CURRENT_TASK.md`
- [x] Push initial scaffold commit

**QoL:** `.env.example` with all required vars documented, `Makefile` with `make dev`, `make test`, `make lint` targets. — done

---

## Phase 1 — Domain, Database, and Auth ✅ complete (2026-06-06)
- [x] Define SQLAlchemy ORM models: `User`, `Portfolio`, `Holding`, `BacktestResult`
  - `User.default_portfolio_id` FK (not `Portfolio.is_default bool`)
  - `Portfolio.benchmark_ticker: str` default `"SPY"`
  - `Holding.target_weight: Decimal` with sum-to-1 constraint enforced at service layer
  - `BacktestResult.tearsheet: dict` JSONB column
- [x] Write Alembic initial migration
- [x] Implement `portfolio_to_weights(holdings) -> tuple[list[str], np.ndarray]` in `portfolio_service.py`
- [x] Implement JWT auth with **PyJWT** (not python-jose)
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
- [x] Write unit tests for auth flows (register, login, refresh, expired token, invalid token)
- [x] Run `/review` before marking Phase 1 complete

**QoL:** Seed script with demo user + demo portfolio (VTI 60% / BND 30% / VXUS 10%). ✅ done

---

## Phase 2 — Market Data Service
> **Architecture locked 2026-06-06 via `/plan-eng-review`.** See decisions 15–27 above.

- [x] `app/core/redis.py` — `redis_client = redis.asyncio.Redis.from_url(...)` + `get_redis()` DI (mirrors `database.py`, decision 15)
- [x] `app/services/market_data_service.py` — `MarketDataService` class:
  - `_cache_through(key, ttl, fetch_fn, serialize, deserialize)` private helper (decision 17)
  - `get_historical_returns(tickers, period)` — cache key `qv:mds:returns:{sorted_tickers}:{period}`, TTL 24h; reindex output to requested order (decisions 22–24)
  - `get_risk_free_rate()` — `^TNX` fetch ÷ 100 (Yahoo returns percentage, e.g. 4.21 → 0.0421 — decision 25), cache 24h, fallback `0.04`
  - `get_ticker_info(ticker)` — company metadata, cache key `qv:mds:info:{ticker}`, TTL 7d
  - `get_quote(ticker)` — real-time quote, cache key `qv:mds:quote:{ticker}`, TTL 15m
  - `search_tickers(query)` — yfinance search wrapper
  - All yfinance calls: `asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)` (decision 18)
  - Redis/deserialization failures → log warning, fall through to live fetch (decision 19)
  - Empty DataFrame → `ValueError` (decision 20); partial results (dropped tickers) → return data + warning, skip cache write (decision 21)
- [x] `app/schemas/market_data.py` — `HistoricalDataResponse`, `QuoteResponse`, `TickerInfoResponse`, `TickerSearchResponse`, `ValidateTickersResponse`
- [x] `app/api/v1/market_data.py` — public endpoints (no auth per spec):
  - `GET /api/v1/market/search?q=...`
  - `GET /api/v1/market/{ticker}/history`
  - `GET /api/v1/market/{ticker}/info`
- [x] Register router in `app/main.py`
- [ ] `T6 (network-blocked):` verify `^TNX` raw value when Yahoo Finance reachable from WSL2; formula confirmed as `raw / 100` via fallback cross-check (decision 25)
- [x] `tests/test_market_data.py` — full unit test suite with `fakeredis` (decision 26):
  - Cache hit (yfinance not called), cache miss, correct TTLs per tier
  - Redis failure falls through; corrupt cache falls through
  - Empty DataFrame → 422; partial result NOT cached
  - ^TNX fallback returns `0.04`; concrete numeric test: `raw / 100 ≈ 0.042` (decision 25)
  - Column order matches requested tickers (decision 24)
  - All cache keys start with `qv:mds:` (decision 23)
  - Public endpoints: 200 without auth token
- [x] Integration smoke tests (behind `INTEGRATION_TESTS=1`, decision 27): `SPY`, `^TNX`
- [x] Data quality: forward-fill gaps ≤5 trading days; drop tickers with >5-day gaps + return warning; never cache partial results
- [x] Run `/review` before marking Phase 2 complete

**QoL:** `/api/v1/market/validate-tickers` batch validation endpoint for the Portfolio Builder UI — ✅ implemented.

**NOT in scope (Phase 2):** Celery offload for fetches (asyncio.to_thread sufficient), rate limiting, authenticated history endpoints (public per spec), persistent storage of price data.

**Added during /review:** Ticker character whitelist (`_TickerStr` + `_TickerPath`, pattern `^[A-Za-z0-9.^=\-]{1,20}$`) — prevents Redis key injection (moved from "NOT in scope" per user approval). 9 additional tests added (MultiIndex format, fence-post NaN, validate_tickers, Redis write failure). Final test count: 48 passed.

---

## Phase 3 — Portfolio Service and Risk Metrics ✅ complete (2026-06-06)
> **Lock known test values in `tests/fixtures/known_values.py` before implementing any financial functions.**
> Use tiny hand-computable matrices: 2-asset portfolio with known returns, verify with pencil-and-paper.

- [x] Write `tests/fixtures/known_values.py` with deterministic inputs and expected outputs for every metric
- [x] Implement Portfolio CRUD endpoints
- [x] Implement Holding management (add, update, delete, weight validation — must sum to 1.0 ± 0.001)
- [x] Implement `calculate_portfolio_metrics()` — annualized return, volatility, Sharpe
- [x] Implement `calculate_var_cvar()`:
  - Historical simulation method (not parametric)
  - **Annual VaR = 252-day rolling window result, NOT `daily_var * sqrt(252)`**
  - **CVaR guard: `var_index = max(int((1 - confidence_level) * len(sorted_returns)), 1)`**
- [x] Implement `calculate_max_drawdown()` — peak-to-trough, returns date + series
- [x] Implement `_compute_beta()`, `calculate_beta_from_ticker()`, `calculate_beta_from_returns()`
- [x] Implement `calculate_sortino()` — downside deviation only in denominator
- [x] Implement correlation matrix calculation
- [x] Run `/review` before marking Phase 3 complete — financial math must be correct

**QoL:** `POST /api/v1/analysis/metrics` accepts an ad-hoc portfolio (no DB save required) for the live Portfolio Builder preview. ✅ implemented.

**Gate results (post-review):** 102 passed, 2 skipped, ruff clean. See ENGINEERING_LOG.md 2026-06-06 for full review findings and fixes.

---

## Phase 4 — Efficient Frontier
> **`/plan-eng-review` completed 2026-06-06** — architecture locked in decisions 28–38 above.
> Run `/review` before marking Phase 4 complete (financial math phase, non-negotiable).

- [x] Add schemas: `FrontierRequest`, `FrontierPoint`, `FrontierResult`, `FrontierTaskStatus`, `FrontierSubmitResponse` in `schemas/portfolio.py`
  - `FrontierRequest.tickers`: max 30, uppercase normalize, pattern `^[A-Za-z0-9.^=\-]{1,20}$`, dedup after normalization
- [x] Implement `optimization_service.py` (pure math + Celery task):
  - `find_min_variance_portfolio(returns_df) -> (weights, ann_return_arith, ann_vol)` — no rfr arg (decision 33)
  - `find_max_sharpe_portfolio(returns_df, rfr) -> (weights, ann_return_arith, ann_vol, sharpe)` — guard if vol < 1e-8
  - `generate_efficient_frontier(returns_df, rfr, n_points=100) -> list[FrontierPoint]`
    - **Solve min-variance first; use its arithmetic annual return as lower bound for target range** (decision 13)
    - **100 target returns via `np.linspace(min_return, max_individual_return, n_points)`**
    - **SLSQP, `bounds=[(0, 1)] * n`, weights-sum-to-1 + `port_arith_return >= target` constraints**
    - **Sequential warm starts: pass each solve's weights as `x0` to the next** (decision 9/updated)
    - **Infeasible target (SLSQP status ≠ 0) → skip point, continue** (decision 38)
    - **Output: `FrontierPoint.annual_return` = geometric `(1+mean_daily_port_r)^252 - 1`** (decision 30)
  - `@celery_app.task(bind=True, soft_time_limit=55, time_limit=60) def compute_frontier(self, tickers, period)` (decision 31)
    - Fetch returns via `_fetch_and_process_returns()` directly (sync, no DI) (decision 32)
    - Cache read/write via `redis.Redis.from_url(settings.REDIS_URL)` (sync) (decision 32)
    - Cache key: `qv:opt:frontier:{sorted(uppercase_tickers)}:{period}`, 24h TTL (decision 29)
    - Catch `SoftTimeLimitExceeded`, store as clean FAILURE
- [x] Update `celery_app.py` — uncomment `"app.services.optimization_service"` include (decision 28)
- [x] Add endpoints to `api/v1/analysis.py`:
  - `POST /api/v1/analysis/frontier` — `CurrentUser` required (decision 36); validate request; cache hit → return `FrontierSubmitResponse(status="SUCCESS", result=...)` immediately; cache miss → dispatch task, return `FrontierSubmitResponse(task_id=..., status="PENDING")`
  - `GET /api/v1/analysis/frontier/{task_id}` — `CurrentUser` required; non-blocking `AsyncResult.state/.info`; serialize `.info` to `str()` on FAILURE (decision 34/35)
- [x] Write `tests/test_efficient_frontier.py`:
  - **Math unit tests (deterministic fixtures, no live data):**
    - `weights sum to 1.0 ± 1e-6` on every frontier point
    - `all weights ≥ 0` on every point
    - `N successful points returned` (≤ 100)
    - Min-variance point has lower vol than equal-weight portfolio
    - Max-Sharpe weights are valid (sum to 1, ≥ 0, Sharpe ≥ each individual asset's Sharpe)
    - Known 2-asset cov matrix → analytically verifiable min-variance weights
  - **API integration tests:**
    - `POST /frontier` unauthenticated → 401
    - `POST /frontier` duplicate tickers (after normalization) → 422
    - `POST /frontier` < 2 tickers → 422
    - `POST /frontier` invalid period → 422
    - `POST /frontier` > 30 tickers → 422
    - `GET /frontier/{task_id}` unauthenticated → 401
    - FAILURE state returns `{status: FAILURE, error: str}` not HTTP 500
- [x] Run `/review` before marking Phase 4 complete — **done 2026-06-07 (2 informational fixes: corrupt cache fallback in Celery task, FrontierPoint field documentation)**

**QoL:** Cache frontier result in Redis by `(sorted_uppercase_tickers, period)` with 24h TTL — re-running with same inputs is instant. Cache hit on POST returns result immediately (no Celery dispatch).

---

## Phase 5 — Monte Carlo Simulation ✅ complete (2026-06-07, review passed)
> **`/plan-eng-review` completed 2026-06-07** — architecture locked in decisions 39–55 above.
> **`/review` completed 2026-06-07** — 6 fixes applied, 134 tests pass.

- [x] Add `app/models/simulation_result.py` — `SimulationResult` ORM model (decision 41):
  - `status`: native Postgres enum `simulation_status {PENDING, SUCCESS, FAILURE}` (decision 52)
  - `user_id`: UUID FK → users.id, NOT NULL (decision 48)
  - `portfolio_id`: UUID FK → portfolios.id, nullable, CASCADE (decision 41)
  - `tickers`: JSONB, `weights`: JSONB, `period`: str (decision 47)
  - `initial_investment`: Numeric(18,2), `years`: int, `n_simulations`: int, `annual_contribution`: Numeric(18,2)
  - `seed`: int nullable, `task_id`: str nullable
  - `results`: JSONB nullable (null until SUCCESS), `error`: str nullable
  - `created_at`: datetime

- [x] Add `SimulationResult` to `app/models/__init__.py` (for Alembic autodiscovery)

- [x] Write Alembic migration: creates `simulation_status` enum + `simulation_results` table

- [x] Implement `run_monte_carlo()` in `simulation_service.py`:
  - Input: `portfolio_metrics: dict` (keys: `annualized_return`, `annualized_volatility`), `initial_investment`, `years`, `n_simulations`, `annual_contribution`, `seed`
  - `rng = np.random.default_rng(seed)` — thread-safe isolated RNG (decision 42)
  - `daily_mu = mu / 252`; `daily_sigma = sigma / sqrt(252)` (arithmetic annual return)
  - `t_draws = rng.standard_t(df=5, size=(trading_days, n_simulations))`
  - `random_returns[t] = daily_mu + daily_sigma * t_draws[t]` — direct scale, no variance normalization (decision 45)
  - Contribution injection: `portfolio_values[year*252 - 1] += annual_contribution` for year in `range(1, years+1)` — exactly `years` injections (decision 43)
  - `probability_of_profit`: `(final_values > initial_investment + annual_contribution * years).mean()` (decision 46)
  - `probability_of_doubling`: `(final_values > (initial_investment + annual_contribution * years) * 2).mean()`
  - `sample_paths`: 20 paths quantile-sampled from sorted final values (decision 55)
  - Percentile bands: P5, P10, P25, P50, P75, P90, P95

- [x] Implement Celery task `run_simulation(simulation_id, params)` in `simulation_service.py` (decision 40, 44, 50):
  - `@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)` (decision 50)
  - Fetch returns via `_fetch_and_process_returns()` directly (sync, no DI) — mirrors Phase 4 pattern
  - If any tickers dropped by data-quality pipeline → mark FAILURE (decision 54)
  - `calculate_portfolio_metrics(weights, returns_df)` from `risk_service.py`
  - `asyncio.run(_write_result_to_db(...))` with fresh async engine per call (decision 44)
  - Catch `SoftTimeLimitExceeded` → write `status=FAILURE, error="timeout"` to DB
  - Catch all exceptions → write `status=FAILURE, error=str(exc)` to DB

- [x] Update `app/celery_app.py` — uncomment `"app.services.simulation_service"` include

- [x] Add `app/schemas/simulation.py`:
  - `SimulationRequest`: tickers (list, uppercase, dedup, pattern `^[A-Za-z0-9.^=\-]{1,20}$`), weights (non-negative, sum 1.0±0.001), period (`_AnalysisPeriod`), initial_investment, years (1–30), n_simulations (1–1000), annual_contribution (≥0), seed (optional), portfolio_id (optional UUID) — decision 53
  - `SimulationResponse`: percentile_outcomes, sample_paths, mean_final_value, probability_of_profit, probability_of_doubling, final_value_distribution, initial_investment, years, n_simulations, annual_contribution
  - `SimulationSubmitResponse`: simulation_id (UUID), task_id (str), status
  - `SimulationStatusResponse`: simulation_id, status, result (nullable), error (nullable)

- [x] Add `app/api/v1/simulation.py` (decision 39, 48, 49):
  - `POST /api/v1/simulation/monte-carlo` — `CurrentUser` required; validate request; validate `portfolio_id` ownership if provided (decision 49); INSERT `SimulationResult(PENDING)`; dispatch `run_simulation.delay(simulation_id, params)`; on dispatch failure → log + 500; return `SimulationSubmitResponse`
  - `GET /api/v1/simulation/{simulation_id}` — `CurrentUser` required; SELECT WHERE id=? AND user_id=? (decision 48); 404 if not found or wrong user; return `SimulationStatusResponse`

- [x] Register simulation router in `app/main.py`

- [x] Write `tests/test_simulation.py` (19 tests):
  - **Math unit tests (no live data, deterministic fixtures):**
    - Same seed → same results (two identical calls produce identical output)
    - Different seeds → different results
    - t-distribution draws differ from normal at same params (fat-tail verification)
    - 0% volatility → all paths equal `initial_investment * (1 + daily_mu)^t` within float epsilon
    - Contribution count: `years=10, annual_contribution=1000` → exactly 10 injections (verify `sum(path[-1] - no_contrib_path[-1]) ≈ 10000`)
    - `probability_of_profit` accounts for contributions (not just initial_investment)
    - `sample_paths`: exactly 20 paths returned
    - `percentile_outcomes`: keys are exactly {5, 10, 25, 50, 75, 90, 95}
  - **Pydantic validation tests:**
    - `n_simulations > 1000` → ValueError/422
    - `years > 30` → ValueError/422
    - `years < 1` → ValueError/422
    - Weights don't sum to 1.0 → 422
    - Negative weight → 422
  - **API integration tests (hermetic, mock Celery dispatch):**
    - `POST /simulation/monte-carlo` unauthenticated → 401
    - `POST /simulation/monte-carlo` valid request → 200, returns `{simulation_id, task_id, status=PENDING}`
    - `GET /simulation/{id}` unauthenticated → 401
    - `GET /simulation/{id}` wrong user → 404
    - `GET /simulation/{id}` PENDING status → null results
    - `GET /simulation/{id}` unknown ID → 404

- [x] Run `/review` before marking Phase 5 complete — **financial math must be correct**

**NOT in scope (Phase 5):** Comparison endpoint (two simulations in one response), list/delete/history endpoints, simulation caching (Redis), log-return simulation, ruin floor guard, rate limiting, Celery beat orphan cleanup (→ TODO-4).

**Fixed in /review:** With `df=5` t-distribution and high `annual_volatility`, fat-tail draws can produce `1 + r_t < 0`, flipping portfolio value sign. Fixed by flooring at zero (`np.maximum(..., 0.0)`) — equity has limited liability.

**QoL (deferred):** Comparison endpoint: run two simulations (current portfolio vs. rebalanced) and return both in one response.

---

## Phase 6 — Backtesting Engine
> **`/plan-eng-review` completed 2026-06-07** — architecture locked in decisions 56–70 above.
> **Implementation completed 2026-06-07** — T1–T7 done; pending mandatory `/review`.
> Run `/review` before marking Phase 6 complete (financial math phase, non-negotiable).

### Architecture locked (do not revisit without explicit user approval)

- API: portfolio-scoped. `POST /portfolios/{id}/backtests`. Tickers/weights derived from `portfolio.holdings` via `portfolio_to_weights()` — enforce weight sum ≤ 1.0 ± 0.001 before inserting PENDING.
- Date range: `start_date`/`end_date` ISO date fields. Minimum 30 calendar day gap enforced via Pydantic.
- Benchmark: `portfolio.benchmark_ticker` (default `"SPY"`). If benchmark collides with a holding ticker, separate `yf.download()` call (decision 65).
- yfinance fetch: `end_date + timedelta(days=1)` as the `end` param — yfinance `end` is exclusive (decision 67).
- CAGR: `(final_value / initial_investment)^(252/n_trading_days) − 1` — true terminal CAGR; do NOT use `calculate_portfolio_metrics()` (decision 63).
- NEVER rebalance: `equity_t = initial_investment × Σ(w_i × Π(1+r_{i,s}))` — true buy-and-hold; NOT daily-rebalanced cumprod (decision 66).
- Rebalance timing: after first trading day's return in each new period boundary (decision 69).
- Calmar: `Optional[float]`, `None` when `max_drawdown == 0` (decision 64).
- Celery bridge: copy NullPool + asyncio.run() pattern from simulation_service.py into backtest_service.py; do NOT touch simulation_service.py (decision 61).
- `strategy_name`: optional in request, auto-generated (`f"{rebalance_frequency} {start_date}–{end_date}"`) when null.
- Data availability: check both late-start AND early-end >5 trading days → FAILURE before task (decision 60).

### New files
- `app/services/backtest_service.py` — `run_backtest_engine()` + `run_backtest` Celery task
- `app/schemas/backtest.py` — `BacktestRequest`, `BacktestTearsheet`, `BacktestStatusResponse`, `BacktestSummary`, `BacktestSubmitResponse`
- `app/api/v1/backtest.py` — POST submit, GET status, GET list
- `alembic/versions/<ts>_add_backtest_status_columns.py` — adds `status`, `task_id`, `error`, `user_id`, `tickers`, `weights`; makes `tearsheet`/`daily_returns`/`equity_curve` nullable; backfills `user_id`

### Modified files
- `app/services/market_data_service.py` — add `_fetch_and_process_returns_by_date(tickers, start, end)` sync method
- `app/main.py` — register backtest router
- `app/celery_app.py` — add `"app.services.backtest_service"` to includes

### Implementation tasks

- [x] **T1 — Migration**: add `backtest_status` enum + columns to `backtest_results`; `user_id` NOT NULL after backfill via `portfolio_id → portfolios.user_id`; nullable result blobs
- [x] **T2 — Schema**: `BacktestRequest` (start_date, end_date, rebalance_frequency, strategy_name?), `BacktestTearsheet` (cagr, sharpe, sortino, calmar: Optional[float], beta, alpha, win_rate, max_drawdown, rebalance_count, benchmark_cagr), `BacktestStatusResponse`, `BacktestSummary` (no equity_curve/daily_returns)
- [x] **T3 — MarketDataService**: add `_fetch_and_process_returns_by_date(tickers, start, end)` — sync, wraps yfinance with `end=end_date + timedelta(days=1)`, same data-quality pipeline as existing `_fetch_and_process_returns()`
- [x] **T4 — `run_backtest_engine()`**: pure function (no I/O), takes returns DataFrames (portfolio + benchmark) + weights + dates + rebalance_frequency; returns tearsheet dict + equity_curve + daily_returns
  - Initialize per-asset dollar buckets as `weights * initial_investment` — returns-based equivalent of day-1 price allocation
  - NEVER: `equity_t = initial_investment × Σ(w_i × Π(1+r_{i,s}))` (decision 66)
  - MONTHLY/QUARTERLY/ANNUALLY: at first trading day of each new period, apply the day's return first, then reset asset buckets to `current_value × weights`
  - Benchmark: `benchmark_equity_t = initial_investment × Π(1 + r_bench_s for s=1..t)` (buy-and-hold, single asset)
  - CAGR: `(final_value / initial_investment)^(252/n_trading_days) − 1` (decision 63)
  - Sharpe, Sortino: reuse `calculate_sharpe()`, `calculate_sortino()` from risk_service.py
  - Max drawdown: reuse `calculate_max_drawdown()` from risk_service.py
  - Beta: `calculate_beta_from_returns(portfolio_daily_returns, benchmark_daily_returns)`
  - Alpha: `CAGR_portfolio − (rfr + beta × (CAGR_benchmark − rfr))`; rfr = `get_risk_free_rate()` (sync; fallback 0.04); document static-rfr limitation (decision 59)
  - Calmar: `cagr / abs(max_drawdown)` if `max_drawdown != 0` else `None` (decision 64)
  - Win rate: `(daily_returns > 0).mean()` — documented as positive-return fraction (decision 68)
  - equity_curve: `[{"date": d, "portfolio": v, "benchmark": b}, ...]` aligned by trading day
- [x] **T5 — Celery task `run_backtest`**: `@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)` — same timeout + NullPool + asyncio.run() pattern as Phase 5 (copied, not shared); write SUCCESS/FAILURE to DB; catch SoftTimeLimitExceeded + all exceptions with wrapped error DB writes
- [x] **T6 — API endpoints**:
  - `POST /api/v1/portfolios/{portfolio_id}/backtests` — `CurrentUser`; validate portfolio ownership; call `portfolio_to_weights()`; enforce weight sum; fetch `portfolio.benchmark_ticker`; data availability check (fail fast if >5 trading days off); insert PENDING; `.delay()`; return submit response
  - `GET /api/v1/portfolios/{portfolio_id}/backtests/{backtest_id}` — `CurrentUser`; filter `WHERE id=? AND user_id=?`; return full result
  - `GET /api/v1/portfolios/{portfolio_id}/backtests` — `CurrentUser`; return `BacktestSummary` list (no equity_curve, no daily_returns)
- [x] **T7 — Tests** (`tests/test_backtest.py`):
  - Math unit tests (deterministic fixtures):
    - `run_backtest_engine` with constant daily-return fixtures → verify CAGR, Sharpe, drawdown by hand
    - NEVER rebalance: `equity[-1] == initial × sum(w_i × (1+r_i)^n_days)`, `rebalance_count == 0`
    - MONTHLY rebalance: `rebalance_count == number of month boundaries in date range`
    - Win rate: 60% positive days → 0.6
    - Jensen alpha with beta=1 → `alpha ≈ cagr_portfolio − cagr_benchmark`
    - Calmar = `None` when no drawdown occurs
    - All-negative returns: `max_drawdown < 0`, all equity_curve values declining
  - API integration tests (mock Celery):
    - POST unauthenticated → 401
    - POST valid request → 202, returns backtest_id + PENDING
    - POST non-owned portfolio → 404
    - POST portfolio with no holdings → 422
    - POST portfolio with weights not summing to 1.0 → 422
    - GET /{id} unauthenticated → 401
    - GET /{id} wrong user → 404
    - GET /{id} PENDING → null tearsheet/equity_curve
    - GET /{id} unknown ID → 404
    - GET list → `BacktestSummary` items, no equity_curve
    - GET list wrong user → empty list (not another user's backtests)
  - Integration test (INTEGRATION_TESTS=1):
    - SPY-only 2018-01-01 to 2022-12-31, NEVER rebalance → CAGR cross-checked against `calculate_portfolio_metrics()` (not used as CAGR source — just a sanity upper/lower bound)
- [x] Run `/review` before marking Phase 6 complete — **non-negotiable financial math gate** (passed 2026-06-07; 3 fixes applied — see ENGINEERING_LOG.md)

**NOT in scope (Phase 6):** Transaction costs, slippage, tax-loss harvesting, portfolio comparison endpoint, backtest caching in Redis (results are persisted in PostgreSQL), fractional shares math, intraday rebalance.

**TODO-6:** Orphan cleanup for PENDING rows where `.delay()` raised (same pattern as TODO-4 from Phase 5 — acceptable at MVP scale).

**QoL:** `GET /api/v1/portfolios/{id}/backtests` history panel list — implemented as part of T6.

---

## Phase 7 — Frontend

### Architecture Decisions Locked (Phase 7 /plan-eng-review 2026-06-07)

| # | Decision | Rationale |
|---|---|---|
| D1 | Full scope — all 8 pages | Login, Register, Dashboard, Portfolio Builder, Analysis, Monte Carlo, Backtest, Compare |
| D2 | Refresh token in localStorage, access token in Zustand memory | Silent refresh on app init; access token never touches disk |
| D3 | nginx proxy `/api/` → backend:8000; Vite dev proxy `/api` → localhost:8000 | apiClient baseURL = `/api/v1` (relative); eliminates CORS for Docker deploys |
| D4 | Deduplicated refresh lock: `let refreshPromise: Promise<string> \| null = null` | All concurrent 401s queue on one promise; prevents thundering herd on token expiry |
| D5 | Vitest + @testing-library/react + @testing-library/user-event + jsdom | Unit tests: auth store, refresh lock, weight validator, usePolledTask hook |
| T1 | Dashboard shows risk metrics from GET /portfolios/:id/metrics | Redesigned from spec (no portfolio value endpoint); period toggle: 1mo/6mo/1y/2y/max |
| T2 | Add GET /auth/me backend endpoint (UserRead) | authStore.user has no data source without it; fetched on app init |
| T3 | Add `daily_returns: list[float]` to PortfolioMetricsResponse | Return distribution histogram requires it; small change in risk_service.py + schema |

**NOT in scope (Phase 7):**
- Portfolio value / "top movers" widget — backend has no holdings-price-lookup endpoint
- 1D/1W period toggles — backend period tokens are 1mo/3mo/6mo/1y/2y/5y/10y/max
- Cross-tab BroadcastChannel refresh coordination — deferred to TODO-9 (backend has no rotation yet)
- OpenAPI TypeScript type generation — deferred to TODO-10 (verify Decimal serialization first)

**What already exists (do not recreate):**
- `frontend/` scaffold: React 18.3.1, react-router-dom 7.17.0, @tanstack/react-query 5.101.0, recharts 3.8.1, zustand 5.0.14, axios 1.17.0, tailwindcss 4.3.0
- `frontend/src/index.css` — complete Tailwind v4 @theme with all design tokens
- `frontend/src/App.tsx` — QueryClientProvider + BrowserRouter + Routes stub (1 route)
- `frontend/src/services/apiClient.ts` — axios stub (needs full rewrite per D2-D4)
- `frontend/vite.config.ts` — needs dev proxy added
- `frontend/nginx.conf` — needs `/api/` proxy_pass block added
- `frontend/src/pages/DashboardPage.tsx` — placeholder only (needs full redesign)

**Missing packages (install before starting):**
- `react-hook-form` — portfolio builder + auth forms
- `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom` — D5 testing

### Tasks

**Phase 7a — Foundation**
- [x] Install missing packages: `react-hook-form vitest @testing-library/react @testing-library/user-event jsdom`
- [x] Add Vite dev proxy: `server.proxy = { '/api': 'http://localhost:8000' }` in `vite.config.ts`
- [x] Add nginx API proxy: `location /api/ { proxy_pass http://backend:8000; }` in `nginx.conf`
- [x] Rewrite `apiClient.ts`: baseURL `/api/v1`, request interceptor (attach access token), response interceptor (deduplicated refresh lock with `_retry` guard, skip /auth/* paths)
- [x] Add GET /auth/me endpoint to backend (returns UserRead; auth required)
- [x] Add `daily_returns: list[float]` to PortfolioMetricsResponse schema + risk_service.py population
- [x] Zustand authStore: `{ user, accessToken, setTokens, logout, silentRefresh }`
- [x] ProtectedRoute wrapper — redirects to /login when no accessToken
- [x] Full routing in App.tsx: all 8 pages + ProtectedRoute

**Phase 7b — Auth Pages**
- [x] LoginPage (`/login`): centered card, email + password fields, React Hook Form, POST /auth/login, store tokens, redirect /dashboard
- [x] RegisterPage (`/register`): same layout, POST /auth/register → auto POST /auth/login → redirect /dashboard
- [x] Unit test: authStore silentRefresh + deduplicated refresh lock

**Phase 7c — Dashboard**
- [x] DashboardPage (`/dashboard`): portfolio selector, risk metrics cards (Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown)
- [x] Period toggle (1mo/6mo/1y/2y/max) — passes period param to GET /portfolios/:id/metrics
- [x] Return distribution histogram (uses `daily_returns` from T3)
- [x] Staggered card entrance animation; `useRef hasAnimated` guard; stable `portfolio.id` keys
- [x] Animated number counters on metric values (count up on load)
- [x] Loading skeletons + error states with retry

**Phase 7d — Portfolio Builder**
- [x] PortfolioBuilderPage (`/portfolios/new`): ticker input, asset_class dropdown, target_weight input, current_shares + notes optional
- [x] Live weight sum indicator: green when sum = 100%, red when > 100%; animated bar
- [x] POST /portfolios (create portfolio + holdings)
- [x] Unit test: weight validator (sum=100%, duplicates, empty)

**Phase 7e — Analysis Page**
- [x] AnalysisPage (`/portfolios/:id/analysis`): Efficient Frontier scatter with TanStack Query polling
- [x] Polling: POST /analysis/frontier → if task_id null (cache hit, status SUCCESS) skip poll; else poll GET /analysis/frontier/:task_id until SUCCESS/FAILURE; stop condition: `['SUCCESS','FAILURE'].includes(status)` (covers STARTED/RETRY states)
- [x] Frontier chart: current portfolio point, min-variance point, max-Sharpe point, hover tooltip shows weights
- [x] Correlation heatmap (Recharts or CSS grid)
- [x] Risk metrics cards (reuse from Dashboard)

**Phase 7f — Monte Carlo Page**
- [x] MonteCarloPage (`/portfolios/:id/simulate`): form (years, simulations, initial_investment, annual_contribution), POST /simulation/monte-carlo, poll GET /simulation/:id
- [x] Chart: 20 sampled paths (light gray), P5/P25/P50/P75/P95 lines, initial investment reference line
- [x] Loading/empty state while task runs; error state on FAILURE

**Phase 7g — Backtest Page**
- [x] BacktestPage (`/portfolios/:id/backtest`): form (start_date, end_date, rebalance_frequency, initial_investment), POST /portfolios/:id/backtests, poll GET /portfolios/:id/backtests/:backtest_id
- [x] Equity curve chart (portfolio vs. benchmark); EquityCurvePoint: `{ date, portfolio, benchmark }`
- [x] Tearsheet cards: CAGR, Sharpe, Sortino, Calmar (may be null → "N/A"), Max Drawdown, Benchmark comparison

**Phase 7h — Compare + Polish**
- [ ] ComparePage (`/compare`): select 2+ portfolios, side-by-side metrics table
- [ ] Global: loading skeletons on all data-fetching views, error states with retry
- [ ] Run `/qa` to verify all features end-to-end before marking Phase 7 complete

**QoL:** Animated number counters on metric cards (count up on load). Staggered entrance animations on dashboard cards. Weight bar micro-animations on portfolio builder input.

---

## Phase 8 — Polish, CI, and Portfolio Integration
- [ ] Finalize Docker Compose (all 5 services: backend, frontend, db, redis, celery-worker)
- [ ] Write GitHub Actions CI:
  1. Python 3.12: pytest + ruff + mypy
  2. Node.js 20: frontend build + type check
  3. Docker image build smoke test
- [ ] Write polished README:
  - Motivation + personal narrative (Vanguard account)
  - Financial Concepts Explained (MPT, VaR, GBM — friendly but rigorous)
  - Architecture diagram
  - Algorithm notes (t-distribution rationale, rolling VaR rationale, contribution compounding fix)
  - Disclaimer: "Mean-variance optimized under assumptions. Not financial advice."
  - Setup instructions + screenshots
- [ ] Take screenshots with realistic demo data: VTI 60% / BND 30% / VXUS 10%
- [ ] Add to Kenny's ePortfolio (`src/data/projects.js`)
- [ ] Deployment: Railway or Render for hosted demo (Docker Compose target)
- [ ] Run `/review` and `/qa` on final state
- [ ] Sync gbrain with final state: `/sync-gbrain`

**QoL:** GitHub repo social preview image (Open Graph). README badge row: CI status, Python 3.12, FastAPI, React.

---

## Financial Correctness Checklist
> Run before calling any Phase complete that touches financial math.

- [ ] VaR annual is rolling 252-day window result (Phase 3)
- [ ] CVaR var_index guards against empty slice (Phase 3)
- [ ] Monte Carlo uses `standard_t(df=5)`, not `normal()` (Phase 5)
- [ ] MC contributions inject at year boundary and compound forward (Phase 5)
- [ ] Efficient frontier lower bound = min-variance return, not min individual return (Phase 4)
- [ ] All optimizer results checked for `result.success` before appending (Phase 4)
- [ ] Beta uses `_compute_beta` shared core — no duplicate math (Phase 3/6)
- [x] Backtest initializes asset buckets from `initial_investment × weights` before the first return (returns-based equivalent of price × weights; Phase 6)
- [x] Backtest CAGR uses `(end/start)^(252/n_days)−1`, NOT `(1+mean_daily)^252−1` (Phase 6, decision 63)
- [x] NEVER rebalance uses per-asset cumulative return sum, NOT daily-rebalanced cumprod (Phase 6, decision 66)
- [x] Calmar returns `None` when max_drawdown == 0 (Phase 6, decision 64)
- [x] yfinance `end` date is `end_date + timedelta(days=1)` (Phase 6, decision 67)
- [ ] `^TNX` yield divided by 100 before use as risk-free rate (Phase 2)

---

## Test Fixtures Specification (Phase 3 prerequisite)
> Lock these in `tests/fixtures/known_values.py` before writing a single financial function.

```python
# 2-asset portfolio: A returns [0.01, -0.02, 0.03] and B returns [-0.01, 0.02, 0.01]
# Hand-compute: portfolio_return, portfolio_volatility, Sharpe, VaR, CVaR, Beta
# Use: np.random.seed(42) for MC tests
# Known backtest: SPY-only 2020-01-02 to 2020-12-31 — verify CAGR within ±1% of published
```

---

## Skill Routing Checkpoints
| Phase | Skill | When |
|---|---|---|
| 0 | `/plan-eng-review` | Done (2026-06-05) |
| 2 | `/plan-eng-review` | Done (2026-06-06) — decisions 15–27 locked |
| 3 | `/review` | Before marking Phase 3 complete |
| 4 | `/plan-eng-review` | Before starting Phase 4 (optimization is math-heavy) |
| 6 | `/review` | Before marking Phase 6 complete |
| 7 | `/qa` | After frontend is feature-complete |
| 8 | `/review` + `/qa` | Final state before shipping |

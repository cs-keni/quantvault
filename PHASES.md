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
| 9 | `ProcessPoolExecutor.map()` for frontier parallelism | 100 minimize calls run in parallel |
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
- [ ] Run `/review` before marking Phase 2 complete

**QoL:** `/api/v1/market/validate-tickers` batch validation endpoint for the Portfolio Builder UI — ✅ implemented.

**NOT in scope (Phase 2):** Celery offload for fetches (asyncio.to_thread sufficient), rate limiting, input character whitelists, authenticated history endpoints (public per spec), persistent storage of price data.

---

## Phase 3 — Portfolio Service and Risk Metrics
> **Lock known test values in `tests/fixtures/known_values.py` before implementing any financial functions.**
> Use tiny hand-computable matrices: 2-asset portfolio with known returns, verify with pencil-and-paper.

- [ ] Write `tests/fixtures/known_values.py` with deterministic inputs and expected outputs for every metric
- [ ] Implement Portfolio CRUD endpoints
- [ ] Implement Holding management (add, update, delete, weight validation — must sum to 1.0 ± 0.001)
- [ ] Implement `calculate_portfolio_metrics()` — annualized return, volatility, Sharpe
- [ ] Implement `calculate_var_cvar()`:
  - Historical simulation method (not parametric)
  - **Annual VaR = 252-day rolling window result, NOT `daily_var * sqrt(252)`**
  - **CVaR guard: `var_index = max(int((1 - confidence_level) * len(sorted_returns)), 1)`**
- [ ] Implement `calculate_max_drawdown()` — peak-to-trough, returns date + series
- [ ] Implement `_compute_beta()`, `calculate_beta_from_ticker()`, `calculate_beta_from_returns()`
- [ ] Implement `calculate_sortino()` — downside deviation only in denominator
- [ ] Implement correlation matrix calculation
- [ ] Run `/review` before marking Phase 3 complete — financial math must be correct

**QoL:** `POST /api/v1/analysis/metrics` accepts an ad-hoc portfolio (no DB save required) for the live Portfolio Builder preview.

---

## Phase 4 — Efficient Frontier
> **Run `/plan-eng-review` before starting Phase 4** — optimization is the most math-heavy piece.

- [ ] Implement `generate_efficient_frontier()` in `optimization_service.py`
  - **Solve min-variance portfolio first; use `min_feasible_return` as lower bound for target range** (not `mean_returns.min()`)
  - **Parallelize 100 `scipy.optimize.minimize` calls with `ProcessPoolExecutor.map()`**
  - Long-only constraints: `bounds=[(0, 1)] * n_assets`
  - Warm start: use previous result's weights as `x0` for adjacent target returns
- [ ] Implement `find_min_variance_portfolio()` — already computed as the lower-bound solve above (reuse result)
- [ ] Implement `find_max_sharpe_portfolio()` — direct optimization on negative Sharpe
- [ ] Wire into Celery task (`celery_tasks/efficient_frontier.py`) — POST returns task ID, GET polls for result
- [ ] Verify with known asset pairs: 100% SPY on frontier, 60/40 SPY+BND lower risk than 100% SPY, max Sharpe > individual Sharpe
- [ ] Write unit tests: weights sum to 1 on every point, all weights ≥ 0, N successful points out of N targets

**QoL:** Cache frontier result in Redis by `(sorted_tickers, period)` with 24h TTL — re-running with same inputs is instant.

---

## Phase 5 — Monte Carlo Simulation
- [ ] Implement `run_monte_carlo()` in `simulation_service.py`
  - **Use `np.random.standard_t(df=5)` scaled to `daily_sigma`, not `np.random.normal()`**
  - **Pydantic validators: `n_simulations ≤ 1000`, `years ≤ 30`**
  - **Annual contributions: inject at year boundary and compound forward:**
    ```python
    portfolio_values = np.zeros((trading_days, n_simulations))
    portfolio_values[0] = initial_investment
    for t in range(1, trading_days):
        portfolio_values[t] = portfolio_values[t-1] * (1 + random_returns[t])
        if t % 252 == 0:
            portfolio_values[t] += annual_contribution
    ```
  - Seed support: `np.random.seed(seed)` param for deterministic tests
  - Percentile bands: P5, P10, P25, P50, P75, P90, P95
  - 20 representative sample paths for visualization
- [ ] Wire into Celery task — async execution, result stored in PostgreSQL
- [ ] Write unit tests: same seed → same results, 0% volatility → straight line (within float epsilon), contributions sum correctly at final year
- [ ] Store simulation results in PostgreSQL (`SimulationResult` model)

**QoL:** Comparison endpoint: run two simulations (current portfolio vs. rebalanced) and return both in one response.

---

## Phase 6 — Backtesting Engine
- [ ] Implement `run_backtest()` in `backtest_service.py`
  - **Initialize `current_allocation` before loop from `price_data.iloc[0][tickers]` at day-1 weights** (prevents UnboundLocalError)
  - Rebalance frequencies: `MONTHLY`, `QUARTERLY`, `ANNUALLY`, `NEVER`
  - No transaction costs (documented as assumption in README)
  - Benchmark: buy-and-hold SPY from day 1
- [ ] Implement full tearsheet: CAGR, Sharpe, Sortino, Calmar, `calculate_beta_from_returns()`, Alpha, win rate, max drawdown, rebalance count
- [ ] Wire into Celery task — backtests can take seconds on 10yr history
- [ ] Store `BacktestResult` (JSONB tearsheet) in PostgreSQL
- [ ] Smoke test: SPY-only portfolio 2018–2023, compare CAGR against published benchmarks
- [ ] Run `/review` before marking Phase 6 complete — correctness-sensitive

**QoL:** `GET /api/v1/portfolios/{id}/backtests` returns list with summary stats (not full tearsheet) for the history panel.

---

## Phase 7 — Frontend
- [ ] Scaffold React 18 + TypeScript + Tailwind + TanStack Query + Recharts + Zustand
- [ ] Design tokens applied globally (Inter font, `#6366f1` accent, `#f8fafc` surface, `#10b981` positive)
- [ ] Auth pages: `/login`, `/register` — clean, minimal, centered card layout
- [ ] Dashboard: `/dashboard` — portfolio value, 1D/1W/1M/1Y/ALL return toggle, top movers
- [ ] Portfolio Builder: `/portfolios/new` — ticker search, weight input, live metrics preview (calls ad-hoc metrics endpoint)
  - Micro-animation: weight bars animate to new values on input
  - Validation: weight sum indicator (green when = 100%, red when > 100%)
- [ ] Analysis page: `/portfolios/:id/analysis`
  - Efficient Frontier scatter plot — current portfolio point, min-variance star, max-Sharpe star, hover shows weights
  - Risk metrics cards (Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown)
  - Correlation heatmap
  - Return distribution histogram with overlay
- [ ] Monte Carlo page: `/portfolios/:id/simulate`
  - 20 sampled paths (light gray), P5/P25/P50/P75/P95 bands, initial investment reference line
  - Loading skeleton while Celery task runs
- [ ] Backtest page: `/portfolios/:id/backtest`
  - Date range picker, rebalance frequency selector
  - Equity curve (portfolio vs. benchmark)
  - Full tearsheet cards
- [ ] Portfolio comparison: `/compare`
- [ ] Loading skeletons on all data-fetching views
- [ ] Error states with retry buttons
- [ ] Run `/qa` to verify all features end-to-end before marking Phase 7 complete

**QoL:** Animated number counters on metric cards (count up on load). Staggered entrance animations on dashboard cards.

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
- [ ] Backtest initializes `current_allocation` before loop (Phase 6)
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

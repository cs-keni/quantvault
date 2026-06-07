# AI Context — QuantVault

Living reference for any agent (Claude Code or Codex) picking up this repo.
Read this before writing code; update it whenever the stack, data format, or
a key implementation decision changes.

## What this is

A quantitative portfolio analytics platform: real Yahoo Finance market data,
Markowitz efficient frontier optimization, Monte Carlo simulation, VaR/CVaR/
Sharpe/Sortino/Beta risk metrics, and a backtesting engine with tearsheets.
Built as a portfolio signal piece for investment-management employers — see
`quantvault.md` for the full canonical spec and `PHASES.md` for the phase plan.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic |
| Auth | PyJWT + Passlib(bcrypt) — **not** python-jose (active CVEs) |
| Async tasks | Celery + Redis (efficient frontier, Monte Carlo, backtest — CPU-bound, must not block the event loop) |
| Math | NumPy, Pandas, SciPy (`scipy.optimize.minimize`) |
| Market data | yfinance, Redis-cached (24h historical / 15m quotes / 7d metadata) |
| Frontend | React 18 + TypeScript + Vite, Tailwind CSS, Recharts, Zustand, TanStack Query |
| Infra | PostgreSQL 16, Redis 7, Docker Compose (5 services: backend, frontend, db, redis, celery-worker) |

## Repo layout

```
backend/app/
  main.py            — FastAPI app factory (create_app); routers register here per phase
  celery_app.py      — Celery app (broker=backend=Redis); task modules added per phase
  core/              — config (pydantic-settings), database (async engine/session), security (JWT/bcrypt)
  models/            — SQLAlchemy ORM models, re-exported from __init__.py for Alembic autogenerate
  schemas/           — Pydantic request/response schemas
  api/v1/            — versioned routers (auth, portfolios, analysis, simulation, backtest, market_data)
  services/          — all financial math + business logic (never inline in routes)
backend/alembic/     — async-aware migrations; env.py reads DATABASE_URL from settings
backend/tests/       — pytest + pytest-asyncio; conftest provides db_session + httpx client fixtures
frontend/src/        — pages, components/{charts,portfolio}, services (API client), store (Zustand), types
```

## Key implementation decisions (locked via /plan-eng-review, 2026-06-05)

These override the spec where they conflict — see `CLAUDE.md` and `PHASES.md`
for the full list with rationale. The ones that change *how code is written*:

- **VaR annual = rolling 252-day window**, not `daily_var * sqrt(252)` (that
  scaling is only valid for parametric/normal VaR; this project uses historical
  simulation).
- **Monte Carlo**: `np.random.standard_t(df=5)` scaled to `daily_sigma` — fat
  tails are the point; contributions inject at year boundary and compound
  forward (the spec's `cumprod` add-to-all approach was financially wrong).
- **CVaR guard**: `var_index = max(int((1 - confidence) * N), 1)` prevents an
  empty-slice → NaN on small samples or high confidence levels.
- **Efficient frontier (Phase 4 — complete)**:
  `optimization_service.py` owns all MPT math and the Celery task
  `compute_frontier`. The task calls `_fetch_and_process_returns()` directly
  (sync) + `redis.Redis` (sync — **no async DI in Celery workers**). Optimizer
  target-return constraint uses **arithmetic** daily mean returns
  (`w.T @ mu_arith >= target`, linear in weights); output
  `FrontierPoint.annual_return` is **geometric** `(1+mean_daily)^252 - 1`.
  Task timeout is `soft_time_limit=55, time_limit=60`. Cache key:
  `qv:opt:frontier:{sorted_uppercase_tickers}:{period}`, 24h TTL. API routes:
  authenticated `POST /api/v1/analysis/frontier` (cache hit returns
  `SUCCESS` with `task_id=null`; cache miss dispatches Celery) and authenticated
  `GET /api/v1/analysis/frontier/{task_id}` (non-blocking state poll; FAILURE
  must return `error=str(result.info)`). See PHASES.md decisions 28–38 for full
  rationale.
- **Monte Carlo simulation (Phase 5 — complete)**:
  `simulation_service.py` owns all MC math and the Celery task `run_simulation`.
  Results are persisted in PostgreSQL `simulation_results`, not Redis/Celery
  result TTL: POST creates `PENDING`, Celery writes `SUCCESS`/`FAILURE`, and GET
  reads by `id AND user_id`. Inputs are ad-hoc `tickers + weights + period` with
  optional `portfolio_id`; POST validates portfolio ownership when provided.
  Simulation uses `np.random.default_rng(seed)` and `standard_t(df=5)` directly
  scaled by daily sigma: `daily_mu + daily_sigma * t_draw`. Contributions inject
  at year-end after that day's return exactly `years` times. Profit/doubling
  probabilities compare against total outlay (`initial + contribution * years`).
  Dropped tickers from yfinance are task FAILURE, not silent weight
  re-normalization. Celery DB writes use `asyncio.run()` with a fresh async
  engine per write.
- **Backtesting engine (Phase 6 — implemented, pending `/review`)**:
  `backtest_service.py` owns the pure math engine and Celery task. Results are
  persisted on `backtest_results`; POST creates `PENDING`, Celery writes
  `SUCCESS`/`FAILURE`, and GET filters by `id AND user_id`. CAGR is true
  terminal CAGR `(final/initial)^(252/n_days)-1`, not the mean-daily estimate
  from `calculate_portfolio_metrics()`. `NEVER` rebalance is true buy-and-hold:
  `initial * Σ(w_i * Π(1+r_i))`; monthly/quarterly/annual rebalance applies the
  boundary-day return before resetting target weights. Benchmark data comes
  from `portfolio.benchmark_ticker` and is fetched separately from holdings.
  yfinance date-range fetches pass `end_date + 1 day` because `end` is
  exclusive. Calmar is `None` when max drawdown is zero. POST preflights data
  availability before inserting PENDING; late-start or early-end gaps over 5
  business days return 422. Celery DB writes copy the Phase 5 `NullPool` +
  `asyncio.run()` bridge; extract a shared helper only after Phase 6 review.
- **`portfolio_to_weights(holdings) -> tuple[list[str], np.ndarray]`** is the
  single Decimal→float conversion point, centralized in `portfolio_service.py`.
- **`User.default_portfolio_id` FK**, not `Portfolio.is_default bool` — avoids
  a multi-row uniqueness constraint.
- **Async tests are pinned to the session-scoped event loop** via a
  `pytest_collection_modifyitems` hook in `tests/conftest.py` (overrides
  `asyncio_mode = auto`'s per-test `loop_scope="function"` default to match
  the session-scoped `engine`/`db_session`/`client` fixtures). Don't add
  per-file `@pytest.mark.asyncio(loop_scope=...)` overrides — any test that
  issues a real query needs to be on the *same* loop the DB connection's
  internal primitives were created on, or it raises `RuntimeError: Future
  ... attached to a different loop`.
- **`MarketDataService` (Phase 2)**: `app/core/redis.py` holds a module-level
  `redis_client = redis.asyncio.Redis.from_url(REDIS_URL)` (mirrors `database.py`);
  `get_redis()` DI dependency; `get_market_data_service()` wraps a module-level
  singleton. Tests override via `app.dependency_overrides[get_redis]` with
  `fakeredis`. All yfinance calls go through
  `asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)` — never call yfinance
  directly in an async context. Cache keys prefixed `qv:mds:` to avoid Celery
  collision. Returned DataFrames are reindexed to requested ticker order
  (`returns_df[tickers]`) — NOT sorted order — so callers can safely dot-product
  with weights from `portfolio_to_weights()` (which returns tickers in holding order).
- **`^TNX` math (Phase 2)**: Verify the exact raw→decimal conversion with a
  concrete numeric test before Phase 3 uses the risk-free rate. The docs say
  "divide by 10" but the example is ambiguous. `get_risk_free_rate()` must
  return a decimal like `0.042`, not a percentage like `4.2`.
- **Cache serialization (Phase 2)**: `pd.DataFrame.to_json(orient='split', date_format='iso')`
  and `pd.read_json(orient='split')`. Fixed schema prevents shape/dtype drift
  between cache hits and fresh fetches.
- **Redis failure handling (Phase 2)**: `_cache_through()` catches both `redis.RedisError`
  and `json.JSONDecodeError`/`ValueError` (corrupt cache), logs a warning, and falls
  through to a live yfinance fetch. Cache is optional — Redis being unavailable
  degrades speed, not correctness. Partial results (tickers dropped by data-quality
  pipeline) are NOT cached; only complete fetches write to Redis.

## Data format conventions

- All financial calculations live in `app/services/*_service.py` — never
  inline in routes — and every calculation function carries a docstring
  explaining the formula and its financial interpretation (non-negotiable,
  see `CLAUDE.md`).
- Market data is **never** persisted to Postgres; it's fetched from yfinance
  on demand and cached in Redis by TTL (see table above). `BacktestResult`
  *is* persisted, with `tearsheet`/`daily_returns`/`equity_curve` as JSONB.
- `^TNX` (10-year Treasury yield, used as the risk-free rate) is quoted by
  Yahoo as a percentage value (e.g. `4.21` = 4.21%) — divide by **100** to
  get the decimal rate; fall back to `0.04` if the fetch fails. Original docs
  said "divide by 10" — that was wrong (see Decision 25 in PHASES.md).
- Test fixtures with hand-computable expected values live in
  `tests/fixtures/known_values.py` (Phase 3 prerequisite — lock these *before*
  implementing any financial function).

## Design tokens (locked)

bg `#ffffff` · surface `#f8fafc` · accent (indigo) `#6366f1` · positive
(emerald) `#10b981` · negative (red) `#ef4444` · text `#0f172a` · font Inter
(JetBrains Mono for numeric displays) · charts via Recharts on a clean SVG /
light-grid style.

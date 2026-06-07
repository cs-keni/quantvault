# Handoff — QuantVault

What the next agent (Claude Code or Codex) needs to pick up cleanly. Update
this whenever architecture, component ownership, or cross-cutting systems
change — not for routine task completion (that's `CURRENT_TASK.md` /
`ENGINEERING_LOG.md`).

## State as of 2026-06-07 (Phase 7 — Frontend, Phase 7g complete)

`/plan-eng-review` complete for Phase 7. Phase 7a foundation through Phase 7g backtest page are implemented and verified; Phase 7h Compare + Polish is next.

**Implemented in Phase 7a:**
- `frontend/package.json` / lockfile — installed `react-hook-form`, `vitest`, `@testing-library/react`, `@testing-library/user-event`, and `jsdom`.
- `frontend/vite.config.ts` — dev proxy `/api` → `http://localhost:8000`.
- `frontend/nginx.conf` — production `/api/` proxy → `backend:8000` before the SPA catch-all.
- `frontend/src/services/apiClient.ts` — full rewrite with relative `baseURL: "/api/v1"`, request token attach, deduplicated refresh lock, `_retry`, and login/refresh skip paths.
- `frontend/src/store/authStore.ts` — Zustand auth store with memory-only access token, `refresh_token` localStorage persistence, deduplicated `silentRefresh()`, and app-init hydration.
- `frontend/src/App.tsx` — `AuthBootstrap`, `ProtectedRoute`, and full route graph for all Phase 7 pages.
- `frontend/src/pages/LoginPage.tsx`, `RegisterPage.tsx`, `PlaceholderPage.tsx`, `frontend/src/types/api.ts` — temporary route surfaces/types for the foundation slice.
- `backend/app/api/v1/auth.py` — `GET /auth/me` returning `UserRead` for the authenticated user.
- `backend/app/schemas/portfolio.py`, `backend/app/services/risk_service.py`, `backend/app/api/v1/analysis.py` — `PortfolioMetricsResponse.daily_returns` populated from the weighted daily return series.
- Tests: added `/auth/me` coverage and `daily_returns` unit coverage.

**Verification after Phase 7a:**
- `cd frontend && npm run build` — clean
- `cd frontend && npm run lint` — clean
- `cd backend && .venv/bin/ruff check app tests/test_auth.py tests/test_risk_metrics.py` — clean
- `cd backend && .venv/bin/mypy app` — clean (39 source files)
- `cd backend && .venv/bin/pytest tests/test_auth.py tests/test_risk_metrics.py -q` — 50 passed, 1 warning; local Postgres/Redis had to be started with `docker compose up -d db redis`.

**Implemented in Phase 7b:**
- `frontend/src/pages/LoginPage.tsx` — React Hook Form login, `/auth/login`, token storage, `/auth/me` hydration, redirect to `/dashboard`, 401 inline error.
- `frontend/src/pages/RegisterPage.tsx` — React Hook Form registration, `/auth/register` then `/auth/login`, token/user storage, redirect to `/dashboard`, 409 inline error.
- `frontend/vite.config.ts` — Vitest jsdom test environment.
- `frontend/package.json` — `npm test` script.
- `frontend/src/store/__tests__/authStore.test.ts` — refresh dedupe, logout clearing, refresh 401 no-retry, no-token rejection.

**Verification after Phase 7b:**
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run build` — clean
- `cd frontend && npm run lint` — clean

**Implemented in Phase 7c:**
- `frontend/src/pages/DashboardPage.tsx` — authenticated dashboard using `GET /portfolios` and `GET /analysis/portfolios/:id/metrics`.
- Period controls are limited to `1mo / 6mo / 1y / 2y / max`.
- Risk cards: Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown.
- Return distribution histogram uses `daily_returns` via Recharts.
- Loading skeletons, empty state, retryable error states, sign-out, animated counters, and staggered card entrance with a `useRef` reanimation guard.
- `frontend/src/types/api.ts` — added portfolio/metrics response types.

**Verification after Phase 7c:**
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run lint` — clean
- `cd frontend && npm run build` — clean; Vite emits a non-blocking >500 kB chunk warning after Recharts enters the main bundle.

**Implemented in Phase 7d:**
- `frontend/src/pages/PortfolioBuilderPage.tsx` — portfolio create form and holdings builder.
- `/portfolios/new` route now renders the builder.
- Holding rows include ticker, asset name, asset class dropdown, target weight %, current shares, and notes.
- Weight input is a percent in the UI and is converted to backend decimal fraction strings on submit.
- Submit flow creates the portfolio first, then posts holdings, then redirects to `/dashboard`.
- `frontend/src/utils/portfolioValidation.ts` + tests cover valid 100%, >100%, duplicate tickers, and empty holdings.

**Verification after Phase 7d:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — clean; same non-blocking >500 kB chunk warning remains
- `cd frontend && npm run lint` — clean

**Implemented in Phase 7e:**
- `frontend/src/pages/AnalysisPage.tsx` — portfolio analysis route.
- Loads portfolio detail and metrics for `1mo / 6mo / 1y / 2y / max`.
- Implements frontier POST cache-hit path (`task_id=null`, `SUCCESS`) without polling.
- Polls task status until `SUCCESS` or `FAILURE`, covering STARTED/RETRY intermediate states.
- Renders Recharts frontier scatter with current, min-variance, and max-Sharpe points; tooltip includes weights.
- Renders correlation heatmap from `PortfolioMetricsResponse.correlation`.
- `frontend/src/types/api.ts` — frontier response types.

**Verification after Phase 7e:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — clean; same non-blocking >500 kB chunk warning remains
- `cd frontend && npm run lint` — clean

**Implemented in Phase 7f:**
- `frontend/src/pages/MonteCarloPage.tsx` — simulation route.
- Loads portfolio holdings, submits `POST /simulation/monte-carlo`, and polls `GET /simulation/:id` until terminal status.
- Inputs: years, n_simulations, initial_investment, annual_contribution.
- Charts 20 sampled paths plus derived percentile lines and initial investment reference.
- Renders mean final value, P5/P50/P95, probability of profit, and probability of doubling.
- `frontend/src/types/api.ts` — simulation response types.

**Verification after Phase 7f:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — clean; same non-blocking >500 kB chunk warning remains
- `cd frontend && npm run lint` — clean

**Implemented in Phase 7g:**
- `frontend/src/pages/BacktestPage.tsx` — backtest route.
- Loads portfolio metadata and submits `POST /portfolios/:id/backtests`.
- Polls `GET /portfolios/:id/backtests/:backtest_id` until terminal status.
- Inputs: start_date, end_date, rebalance_frequency, initial_investment; benchmark is displayed from portfolio metadata because backend uses `portfolio.benchmark_ticker`.
- Renders equity curve and tearsheet cards, with Calmar `null` displayed as `N/A`.
- `frontend/src/types/api.ts` — backtest response types.

**Verification after Phase 7g:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — clean; same non-blocking >500 kB chunk warning remains
- `cd frontend && npm run lint` — clean

**Next implementation slice: Phase 7h Compare + Polish**
- Build `/compare`.
- Add loading/error states where still missing.
- Run `/qa` before marking Phase 7 complete.

**Architecture decisions locked (D1–D5, T1–T3 — see PHASES.md Phase 7 for full table):**
- Refresh token in localStorage, access token in Zustand memory only (silent refresh on init)
- Deduplicated refresh lock: `let refreshPromise: Promise<string> | null = null` in apiClient.ts response interceptor — all concurrent 401s queue on one promise; `_retry` flag prevents infinite loop; skip interceptor on `/auth/login` and `/auth/refresh` paths
- nginx proxy + Vite dev proxy pattern — apiClient.baseURL = `/api/v1` (relative); no VITE_API_BASE_URL build arg needed
- Dashboard redesigned to show risk metrics from GET /portfolios/:id/metrics (no portfolio-value endpoint exists); period toggle uses 1mo/6mo/1y/2y/max (not 1D/1W/1M)
- Polling stop condition: `!['SUCCESS', 'FAILURE'].includes(status)` — covers STARTED/RETRY Celery states; POST /frontier can return task_id=null + SUCCESS on cache hit (skip polling in that case)
- /register returns UserRead (not tokens) — auto POST /auth/login after register, then redirect /dashboard
- HoldingCreate requires `asset_class` (enum: EQUITY/BOND/REAL_ESTATE/COMMODITY/CRYPTO/CASH/OTHER) — portfolio builder UI must include dropdown
- Vitest + @testing-library/react for unit tests: auth store, refresh lock, weight validator

**Asset class enum note:** planning docs originally listed asset classes as `EQUITY/BOND/REAL_ESTATE/COMMODITY/CRYPTO/CASH/OTHER`, but the backend enum currently exposes `EQUITY/FIXED_INCOME/REAL_ESTATE/COMMODITY/CASH`. Phase 7d intentionally used the current backend enum to avoid submitting invalid values; add a backend enum migration later if `BOND/CRYPTO/OTHER` are required.

**NOT in scope for Phase 7:** portfolio value widget, 1D/1W toggles, cross-tab BroadcastChannel (TODO-9), OpenAPI type gen (TODO-10)

**Implementation order:** Phase 7a (foundation + backend changes) → 7b (auth pages) → 7c (dashboard) → 7d (portfolio builder) → 7e (analysis/frontier) → 7f (Monte Carlo) → 7g (backtest) → 7h (compare + polish). Run `/qa` before marking Phase 7 complete.

---

## State as of 2026-06-07 (Phase 6 — Backtesting Engine complete ✅)

Phase 6 T1–T7 are implemented and verified, but the mandatory financial-math `/review` checkpoint has **not** been run yet. Do not mark Phase 6 complete until that review passes.

**Implemented files:**
- `app/services/backtest_service.py` — `run_backtest_engine()` pure math plus `run_backtest` Celery task.
- `app/schemas/backtest.py` — submit/status/summary schemas, including `calmar: Optional[float]`.
- `app/api/v1/backtest.py` — portfolio-scoped POST submit, GET status, and GET list endpoints.
- `alembic/versions/20260607_2330_7d8e9f012345_add_backtest_status_columns.py` — adds status/task/error/audit columns, backfills `user_id`, and makes result JSON blobs nullable.
- `tests/test_backtest.py` — deterministic math tests, API auth/ownership/state tests, and skipped live smoke.

**Modified files:**
- `app/models/backtest_result.py`, `app/models/user.py`, `app/models/__init__.py` — `BacktestStatus`, user FK/audit columns, nullable result blobs, relationship wiring.
- `app/services/market_data_service.py` — `_fetch_and_process_returns_by_date(tickers, start, end)` sync helper; uses yfinance `end=end_date + 1 day`.
- `app/main.py` — registers the backtest router under `/api/v1/portfolios`.
- `app/celery_app.py` — includes `app.services.backtest_service`.

**Verification after implementation:**
- `cd backend && .venv/bin/ruff check app tests/test_backtest.py alembic` — clean
- `cd backend && .venv/bin/mypy app` — clean (39 source files)
- `cd backend && .venv/bin/pytest tests/test_backtest.py -q` — 18 passed, 1 skipped
- `cd backend && .venv/bin/pytest -q` — 152 passed, 3 skipped
- `cd backend && .venv/bin/alembic upgrade head` — applied `9b1c2d3e4f50 -> 7d8e9f012345`
- `cd backend && .venv/bin/alembic check` — no drift

**Critical implementation notes:**
- CAGR is true terminal CAGR: `(final_value / initial_investment) ** (252 / n_trading_days) - 1`. The engine does not call `calculate_portfolio_metrics()` for CAGR.
- NEVER rebalance is true buy-and-hold: `initial * Σ(w_i * Π(1+r_i))`, not `cumprod(1 + weighted_daily_return)`.
- Rebalanced modes apply the boundary-day return first, then reset allocation to target weights for the next trading day.
- Benchmark data is fetched separately from the portfolio holdings, using `portfolio.benchmark_ticker` with no hardcoded SPY assumption.
- FastAPI POST preflights portfolio and benchmark market data before inserting PENDING; late-start or early-end gaps over 5 business days return 422 instead of creating orphan work.
- Celery DB writes use the copied `NullPool` + `asyncio.run()` bridge. `simulation_service.py` was intentionally not touched.

## State as of 2026-06-07 (Phase 5 — Monte Carlo complete ✅)

Phase 5 code is implemented, reviewed, and marked complete. `/review` found 6 issues; all were fixed.

**Implemented files:**
- `app/models/simulation_result.py` — `SimulationResult` ORM model plus native `simulation_status` enum (`PENDING`, `SUCCESS`, `FAILURE`), required `user_id`, nullable `portfolio_id`, audit inputs, task id, result blob, and error field.
- `alembic/versions/20260607_2200_9b1c2d3e4f50_add_simulation_results.py` — creates `simulation_status` and `simulation_results`.
- `app/services/simulation_service.py` — `run_monte_carlo()` and `run_simulation` Celery task.
- `app/schemas/simulation.py` — request/response/status schemas with uppercase ticker dedup, weight-sum validation, and Phase 5 caps.
- `app/api/v1/simulation.py` — authenticated `POST /api/v1/simulation/monte-carlo` and `GET /api/v1/simulation/{simulation_id}`.
- `app/main.py` and `app/celery_app.py` — router and task registration.
- `tests/test_simulation.py` — 19 tests covering math invariants, validation, and DB-backed API state behavior with Celery dispatch mocked.

**Verification after review fixes:**
- `cd backend && .venv/bin/ruff check app tests alembic` — clean
- `cd backend && .venv/bin/mypy app` — clean
- `cd backend && .venv/bin/pytest -q` — 134 passed, 2 skipped
- `cd backend && .venv/bin/alembic upgrade head` — migration applied locally
- `cd backend && .venv/bin/alembic check` — no drift

**Important implementation notes:**
- `run_monte_carlo()` uses `np.random.default_rng(seed)` and `standard_t(df=5)` directly scaled by daily sigma; this intentionally inflates realized vol relative to normal draws.
- Contributions are injected at year-end after that day’s return with `(day + 1) % 252 == 0`, exactly `years` injections.
- `probability_of_profit` and `probability_of_doubling` compare final value against total outlay (`initial + annual_contribution * years`), not just initial investment.
- `sample_paths` always returns 20 quantile-sampled paths from sorted final values, duplicating indices when `n_simulations < 20`.
- Celery task rejects dropped tickers as FAILURE instead of silently re-normalizing weights.
- Celery DB writes use `asyncio.run()` with a fresh async engine per write, matching decision 44 and avoiding event-loop/pool reuse.
- The first Alembic verification caught a duplicate enum creation bug; migration now manually creates the enum once and references it with `postgresql.ENUM(..., create_type=False)`.
- Review fixes applied arithmetic annual return in `run_simulation`, a zero floor on portfolio values, truncated error strings, wrapped error-handler DB writes, a 32-bit seed cap, and `NullPool` for the Celery DB bridge.

## State as of 2026-06-07 (Phase 4 — Efficient Frontier complete ✅)

Phase 4 implemented, reviewed, and marked complete. `/review` pass found 2 informational issues (both fixed):
1. `optimization_service.py` — Celery task cache deserialization errors now caught and logged (corrupt cache falls through to re-fetch instead of task FAILURE)
2. `portfolio.py` — `FrontierPoint.annual_return` and `.sharpe_ratio` fields now have `description=` documenting the arithmetic/geometric return convention

Gates: 113 passed, 2 skipped, ruff clean, mypy clean.

**Implemented files:**
- `app/schemas/portfolio.py` — frontier request/result/task schemas. `FrontierRequest.tickers` uppercases before duplicate detection and enforces 2–30 tickers with the Phase 2 ticker pattern.
- `app/services/optimization_service.py` — Markowitz MPT math, Redis cache helpers, and `compute_frontier` Celery task.
- `app/celery_app.py` — includes `app.services.optimization_service`.
- `app/api/v1/analysis.py` — authenticated `POST /api/v1/analysis/frontier` and `GET /api/v1/analysis/frontier/{task_id}`.
- `tests/test_efficient_frontier.py` — deterministic optimizer tests and hermetic API auth/validation/task-failure tests.

**Verification after implementation:**
- `cd backend && .venv/bin/ruff check app tests` — clean
- `cd backend && .venv/bin/mypy app` — clean (32 source files)
- `cd backend && .venv/bin/pytest -q` — 113 passed, 2 skipped (live-network market-data tests)

**Important implementation notes:**
- API POST checks Redis cache first; cache hit returns `status="SUCCESS"` with `task_id=null`, cache miss dispatches Celery and returns `PENDING`.
- Celery task uses sync Redis plus sync `MarketDataService._fetch_and_process_returns()` and falls back to `0.04` if sync `^TNX` fetch fails.
- Frontier optimizer uses arithmetic annual return for constraints and Sharpe objective; `FrontierPoint.annual_return` reports geometric annual return.
- GET failure state returns `error=str(result.info)` so raw exception objects never hit FastAPI JSON encoding.
- API tests intentionally avoid the DB fixture for frontier auth/validation because these endpoints can be tested hermetically with dependency overrides; the full suite still covers DB-backed routes.

## State as of 2026-06-06 (Phase 4 — Efficient Frontier ready to implement)

Phases 0–3 complete. `/plan-eng-review` completed for Phase 4; architecture locked in `PHASES.md` decisions 28–38. See `CURRENT_TASK.md` for the ordered implementation steps and all locked rules.

**New file: `optimization_service.py`** — will own all Markowitz MPT math:
- `find_min_variance_portfolio(returns_df)` → `(weights, ann_return_arith, ann_vol)` — no `rfr` arg
- `find_max_sharpe_portfolio(returns_df, rfr)` → weights + metrics
- `generate_efficient_frontier(returns_df, rfr, n_points=100)` → list of `FrontierPoint`
- `@celery_app.task(bind=True, soft_time_limit=55, time_limit=60) compute_frontier(tickers, period)` — sync yfinance + sync Redis, no DI

**New endpoints in `analysis.py`:**
- `POST /api/v1/analysis/frontier` — cache hit → immediate result; cache miss → task_id + PENDING
- `GET /api/v1/analysis/frontier/{task_id}` — non-blocking `.state`/`.info` poll

**Critical gotchas for Phase 4 (do not skip):**
- Celery task must NOT use async code — call `_fetch_and_process_returns()` directly (it's sync), use `redis.Redis` not `redis.asyncio.Redis`
- Arithmetic means in optimizer (`w.T @ mu_arith >= target`), geometric in output (FrontierPoint.annual_return)
- `AsyncResult.info` on FAILURE is a Python exception object — `str()` it before JSON response
- Both endpoints require `CurrentUser` auth (Phase 3 caught a missing-auth bug; frontier must not repeat it)

**Phase 3 `/review` summary (2026-06-06, commit 9f5ebbb):**
- 6 bugs fixed: unauthenticated ad-hoc metrics endpoint, `confidence=0` IndexError, correlation NaN→HTTP 500, `update_portfolio` None check, `benchmark_ticker` pattern constraint, ad-hoc weight-sum silently re-normalized
- 14 new tests added (`tests/test_analysis.py`)
- Gate: 102 passed, 2 skipped, ruff clean

## State as of 2026-06-06 (Phase 1 — Domain, Database, and Auth complete & verified)

Domain layer + JWT auth are live on top of the Phase 0 scaffold:

- **Models** (`app/models/{user,portfolio,holding,backtest_result}.py`):
  `User`/`Portfolio`/`Holding`/`BacktestResult`, plus `AssetClass` and
  `RebalanceFrequency` native Postgres enums. `User.default_portfolio_id` is
  a circular FK to `portfolios.id` — modeled with `use_alter=True` +
  `relationship(..., post_update=True)` to break the insert cycle (the
  Alembic migration adds it as a separate `op.create_foreign_key` after both
  tables exist; see the migration's comment for why autogenerate can't do
  this inline).
- **Auth** (`app/api/v1/auth.py`, `app/dependencies.py`): PyJWT-based
  register/login/refresh. `CurrentUser = Annotated[User, Depends(get_current_user)]`
  is the auth boundary every future protected route depends on — all its
  failure modes (missing/malformed/expired/wrong-type token, unknown user,
  deactivated account) collapse to the same 401 to prevent enumeration.
- **`portfolio_to_weights()`** (`app/services/portfolio_service.py`): the
  single `Decimal` → `float64` conversion point for downstream numpy/scipy
  math (locked architecture decision #8) — never convert weights anywhere
  else.
- **Seed script** (`make seed` → `app/scripts/seed.py`): idempotent (looks
  up by email, short-circuits if found) — creates `demo@quantvault.dev` /
  `quantvault-demo` with a three-fund portfolio (VTI 60% / BND 30% / VXUS 10%).

See `ENGINEERING_LOG.md` 2026-06-06 for the three bugs this phase surfaced
and fixed: a latent pytest-asyncio event-loop mismatch (now fixed globally
via a `pytest_collection_modifyitems` hook in `conftest.py` — every future
async test file benefits automatically, no per-file marker needed), a dev-DB
schema/`alembic_version` desync, and a `register` race condition caught
during manual `/review` (concurrent duplicate signups raised a raw 500
instead of 409 — now caught via `IntegrityError` and translated).

## State as of 2026-06-05 (Phase 0 — Scaffold complete & verified)

Architecture is locked (`/plan-eng-review` complete, 14 decisions recorded in
`PHASES.md`). This session scaffolds the repo to match `quantvault.md`'s
solution structure: backend (FastAPI app factory, Alembic, Celery, pytest/
ruff/mypy/pre-commit), frontend (React+TS+Tailwind via Vite), Docker Compose
(5 services), docs/, Makefile, `.env.example` — and verifies all of it live
against a running Postgres + Redis (`docker compose up -d db redis`):
`make lint`, `make test`, `make migrate`, the Celery worker, pre-commit, and
the frontend dev server all run clean. See `ENGINEERING_LOG.md` for the
verification pass and the bugs it caught.

**Not yet built:** any domain models, auth endpoints, or financial math.
`app/dependencies.py` (the `get_current_user` FastAPI dependency) and the
seed script were *deliberately deferred to Phase 1* — both need the `User`/
`Portfolio`/`Holding` ORM models, which don't exist yet. Writing them now
would mean importing nonexistent modules (dangling imports that break mypy).

## Ownership boundaries

- **`app/services/*`** owns all financial math. Routes (`app/api/v1/*`) stay
  thin — they validate via Pydantic schemas and delegate. This is enforced by
  `CLAUDE.md` ("Financial Math Correctness" — never inline in routes, every
  calculation function needs a docstring with the formula + interpretation).
- **`app/core/*`** owns cross-cutting infra: settings (`config.py`), the async
  engine/session (`database.py`), and JWT/password hashing (`security.py`).
  Nothing else should construct an engine, read an env var directly, or touch
  `jwt`/`passlib` — go through these.
- **`alembic/env.py`** auto-discovers models via `import app.models` — new
  model modules register themselves by being imported in
  `app/models/__init__.py`; `env.py` does not need to change.
- **Frontend** state: Zustand for client state, TanStack Query for server
  state/caching — don't duplicate server data into Zustand stores.

## Known quirks / gotchas

- **`CLAUDE.md` has `## Skill Routing`** (capital R) — gstack's `HAS_ROUTING`
  check greps for lowercase `r` and reports "no". Routing is effectively
  configured; this is a cosmetic mismatch, not a real gap.
- **`^TNX`** is quoted by Yahoo as a percentage (e.g. `4.21` = 4.21% yield) —
  divide by **100** to get a decimal; fall back to `0.04` on fetch failure.
  (Original docs said "divide by 10" — that was wrong; `4.2 / 10 = 0.42` is
  42%, not a reasonable risk-free rate.)
- **Test DB**: `tests/conftest.py` defaults `TEST_DATABASE_URL` to
  `quantvault_test` on the same Postgres host as dev — override in CI. The
  `db` service in `docker-compose.yml` publishes `5432:5432` *specifically*
  so `make test`/`make migrate` (which run on the host via `.venv`, not in a
  container) can reach it at `localhost:5432`.
- **`.env.example` `DB_PASSWORD=qv`**: matches the `Settings` defaults in
  `app/core/config.py` on purpose, so `cp .env.example .env` produces a
  Postgres container whose credentials match what the host-side `.venv`
  app/tests expect with zero edits. Only `SECRET_KEY` needs rotating for
  anything beyond local dev (already flagged inline with the `openssl rand`
  hint).
- **`asyncio_default_fixture_loop_scope = session`** (not `function`) in
  `pytest.ini` — required because `tests/conftest.py`'s `engine` fixture is
  session-scoped and async; pytest-asyncio raises `ScopeMismatch` if the
  default fixture loop is narrower than the fixtures that need it.
- **`conftest.py`'s `pytest_collection_modifyitems` hook** re-pins every test
  function from `asyncio_mode = auto`'s default `loop_scope="function"` to
  `loop_scope="session"`, matching the DB fixtures. Without it, any test that
  actually issues a query (not just resolves the `db` dependency) raises
  `RuntimeError: Future ... attached to a different loop` — `test_health.py`
  never tripped this because its handler never touches `db`. Don't remove
  this hook or add per-file `@pytest.mark.asyncio(...)` overrides; it's
  intentionally global.
- **`hash_password`/`verify_password`** (bcrypt via passlib, ~100–300ms by
  design) run synchronously inside `async def register`/`login` — blocks the
  event loop for that duration. Fine at demo traffic; wrap in
  `asyncio.to_thread()` before this needs to handle real concurrent load.
- **`_get_user_by_email`** intentionally does *not* filter by `is_active` —
  both call sites need the full row (`register`'s duplicate-check must also
  catch deactivated emails; `login` needs the row to verify the password
  before checking `is_active` separately, so it can return 403 instead of
  401 for deactivated accounts).
- **venv note**: this WSL box can't `apt install python3.12-venv` (needs sudo
  password), so `backend/.venv` was created with `virtualenv` instead of the
  stdlib `venv` module. Functionally identical — and once
  `requirements-dev.txt` finished installing, normal `bin/` console-script
  shims (`pip`, `pytest`, `ruff`, `mypy`, `alembic`, `celery`, ...) were all
  present as expected.

## Next up

Phase 7 — Frontend. **Architecture locked 2026-06-07 via `/plan-eng-review`.** See Phase 7 state entry above and PHASES.md Phase 7 section for full task breakdown.

---

### Older: Phase 2 — Market Data Service decisions (for reference only)

Phase 2 is complete. **Architecture was locked 2026-06-06 via `/plan-eng-review`
(decisions 15–27 in `PHASES.md`).** Key decisions to know:

- **Redis client**: module-level singleton in `app/core/redis.py`; `get_redis()` DI
  (mirrors `database.py`). Tests override via `app.dependency_overrides[get_redis]`
  with `fakeredis` — same pattern as `get_db`.
- **yfinance is blocking**: every yfinance call goes through
  `asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)`. Never call yfinance
  directly inside an `async def`.
- **`_cache_through()` private helper**: all 4 cache tiers share one method;
  catches `RedisError` and deserialization errors and falls through to live fetch
  (Redis failure degrades speed, not correctness).
- **Column order trap**: `get_historical_returns()` sorts tickers for the cache key
  but REINDEXES the returned DataFrame to requested order (`returns_df[tickers]`).
  `portfolio_to_weights()` returns tickers in holding order; Phase 3 dot products
  break silently if column order differs.
- **^TNX math**: Yahoo Finance quotes `^TNX` as a percentage (e.g. `4.21` = 4.21% yield).
  Correct formula is `raw / 100` to get a decimal (e.g. `4.21 / 100 = 0.0421`).
  The "divide by 10" note in the original docs was wrong — cross-checked against the
  `0.04` fallback (4% decimal), which only makes sense if the raw value is ~4.0 and
  we divide by 100. Verify with a live `yf.download("^TNX", period="5d")` once
  Yahoo Finance is reachable.
- **Partial results NOT cached**: if any ticker is dropped by the data-quality
  pipeline (forward-fill ≤5 trading days, then drop), return partial data + warning
  in response body but do NOT write to Redis.
- **Cache keys**: `qv:mds:` prefix on all keys to avoid Celery collision in Redis DB 0.
  Serialization: `pd.DataFrame.to_json(orient='split', date_format='iso')`.
- **Public endpoints**: search + all market data endpoints are PUBLIC (no auth
  required per spec). Do not add `CurrentUser` dependency to these routes.

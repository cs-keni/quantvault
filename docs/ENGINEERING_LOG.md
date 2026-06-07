# Engineering Log

Reverse-chronological. One entry per session/slice — what changed and why,
not a diff (git history is authoritative for that).

## 2026-06-07 — Phase 7e: Analysis Page implemented

Implemented the locked Phase 7e analysis page.

**Changed:**
- Added `AnalysisPage` and wired `/portfolios/:id/analysis`.
- Loads portfolio details and metrics for period tokens `1mo / 6mo / 1y / 2y / max`.
- Added risk cards, efficient-frontier scatter chart, and correlation heatmap.
- Implemented frontier cache-hit branch: `task_id === null && status === "SUCCESS"` renders immediately without polling.
- Implemented frontier polling with stop condition `['SUCCESS', 'FAILURE'].includes(status)` to cover STARTED/RETRY states.
- Added frontend frontier response types.

**Checks:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed after one transient Node/V8 native crash on the first lint run; immediate reruns passed.

**Build note:** Vite still warns the main JS chunk is >500 kB due to Recharts in the main route bundle.

## 2026-06-07 — Phase 7d: Portfolio Builder implemented

Implemented the locked Phase 7d portfolio builder.

**Changed:**
- Added `PortfolioBuilderPage` and wired `/portfolios/new`.
- Added portfolio metadata inputs: name, description, benchmark ticker.
- Added holding rows with ticker, asset name, asset class dropdown, target weight %, current shares, and notes.
- UI accepts target weight as percent and converts to backend decimal fraction strings before posting holdings.
- Added live weight sum indicator and animated allocation bar.
- Submit flow creates the portfolio, posts each holding, then redirects to `/dashboard`.
- Added `validateHoldingDrafts()` and tests for valid 100%, >100%, duplicate tickers, and empty holdings.

**Checks:**
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed

**Decision/gotcha:** The planned builder enum listed `BOND/CRYPTO/OTHER`, but the backend enum currently has `EQUITY/FIXED_INCOME/REAL_ESTATE/COMMODITY/CASH`. The builder uses the actual backend enum to avoid invalid API submissions; adding the planned values requires a backend enum migration.

## 2026-06-07 — Phase 7c: Dashboard implemented

Implemented the locked Phase 7c dashboard.

**Changed:**
- Replaced the scaffold dashboard with an authenticated dashboard.
- Added portfolio selector from `GET /portfolios`; default selection uses `user.default_portfolio_id` when available, otherwise the first portfolio.
- Added locked period toggle tokens only: `1mo / 6mo / 1y / 2y / max`.
- Added metrics query against `GET /analysis/portfolios/:id/metrics`.
- Added cards for Sharpe, Sortino, VaR, CVaR, Beta, and Max Drawdown.
- Added a Recharts return distribution histogram using `daily_returns`.
- Added loading skeletons, empty portfolio state, retryable error states, sign-out, animated counters, and a `useRef` guard preventing metric card reanimation on query refetch.
- Added frontend API types for portfolio list and metrics responses.

**Checks:**
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run lint` — passed
- `cd frontend && npm run build` — passed

**Build note:** Vite warns the main JS chunk is >500 kB after Recharts was added to the dashboard bundle. This is non-blocking for Phase 7; route-level lazy loading can address it during polish if needed.

## 2026-06-07 — Phase 7b: Auth pages implemented

Implemented the locked Phase 7b auth pages and frontend auth tests.

**Changed:**
- Replaced `LoginPage` placeholder with a React Hook Form email/password form.
- Login calls `POST /auth/login`, stores access/refresh tokens via `authStore`, hydrates `GET /auth/me`, and redirects to `/dashboard`.
- Replaced `RegisterPage` placeholder with a React Hook Form full-name/email/password form.
- Register calls `POST /auth/register` (returns `UserRead`), then auto-calls `POST /auth/login`, stores tokens/user, and redirects to `/dashboard`.
- Added inline auth errors for login 401 and register 409.
- Added `npm test` and Vitest jsdom config.
- Added auth store tests covering concurrent refresh dedupe, logout storage clearing, refresh-path 401 no-retry behavior, and no-token rejection without backend calls.

**Checks:**
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed

## 2026-06-07 — Phase 7a: Frontend foundation implemented

Implemented the locked Phase 7a foundation.

**Changed:**
- Installed Phase 7 frontend packages: `react-hook-form`, `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`.
- Added Vite `/api` dev proxy and nginx `/api/` production proxy.
- Rewrote `apiClient.ts` to use relative `baseURL: "/api/v1"`, attach the in-memory access token, and use a deduplicated 401 refresh lock with `_retry`.
- Added Zustand `authStore` with refresh token in `localStorage`, memory-only access token, deduplicated `silentRefresh()`, and app-init `/auth/me` hydration.
- Added protected route bootstrapping and full Phase 7 route graph with placeholders for later pages.
- Added backend `GET /api/v1/auth/me`.
- Added `daily_returns` to `PortfolioMetricsResponse`, populated from the weighted return series inside `risk_service.calculate_portfolio_metrics()`.
- Added focused tests for `/auth/me` and `daily_returns`.

**Checks:**
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed
- `cd backend && .venv/bin/ruff check app tests/test_auth.py tests/test_risk_metrics.py` — passed
- `cd backend && .venv/bin/mypy app` — passed
- `cd backend && .venv/bin/pytest tests/test_auth.py tests/test_risk_metrics.py -q` — 50 passed, 1 warning. Initial run failed because local Postgres was not started; after `docker compose up -d db redis`, rerun passed.

**Gotcha for Phase 7d:** The locked planning docs mention a builder dropdown enum including `BOND/CRYPTO/OTHER`, but the actual backend `AssetClass` enum currently has `EQUITY/FIXED_INCOME/REAL_ESTATE/COMMODITY/CASH`. Resolve intentionally before implementing the portfolio builder.

## 2026-06-07 — Phase 7: /plan-eng-review — architecture locked

No code written. Architecture review for Phase 7 Frontend complete. 10 decisions locked, 12 outside-voice issues caught and resolved, 2 deferred to TODOS.md.

**Key decisions:**
- D2: Refresh token in localStorage, access token in Zustand memory; silent refresh on init
- D3: nginx proxy + Vite dev proxy; apiClient.baseURL = `/api/v1` (relative); eliminates CORS
- D4: Deduplicated refresh lock (`refreshPromise` pattern) — prevents thundering herd on 401 at page load
- D5: Vitest + @testing-library/react for unit tests

**Outside voice (Codex) caught 3 critical API surface mismatches:**
- T1: Dashboard "portfolio value" widget has no backend endpoint → redesigned to show risk metrics from existing GET /portfolios/:id/metrics
- T2: authStore.user had no data source → decided to add GET /auth/me endpoint to backend
- T3: Return distribution histogram has no data → decided to add `daily_returns: list[float]` to PortfolioMetricsResponse

**Additional fixes from outside voice:** period toggle tokens corrected (1mo/6mo/1y/2y/max, not 1D/1W), polling stop condition broadened to cover STARTED/RETRY Celery states, POST /frontier cache-hit (task_id=null) path added, register flow corrected (register → auto-login → redirect), asset_class dropdown added to portfolio builder.

**Docs updated:** PHASES.md Phase 7 section, CURRENT_TASK.md (full implementation guide), HANDOFF.md (Phase 7 state), AI_CONTEXT.md (frontend architecture section), TODOS.md (TODO-9, TODO-10).

**Artifacts:** `~/.gstack/projects/quantvault/tasks-eng-review-20260607-114107.jsonl` (28 tasks), `~/.gstack/projects/quantvault/keni-main-eng-review-test-plan-20260607-114107.md` (test plan), `gbrain: eng-reviews/phase-7-frontend`.

---

## 2026-06-07 — Phase 6: /review pass — 3 fixes applied

Commit: 39fb38d

Ran mandatory financial-math `/review` against Phase 6. All locked math decisions verified correct (CAGR formula, buy-and-hold, Calmar=None, yfinance end-exclusivity, symmetric data availability, Jensen alpha). Three fixes applied from adversarial review findings:

1. **Status guard in `_write_result_to_db`** (`backtest_service.py:219-226`) — added `if backtest.status != BacktestStatus.PENDING: return` before writing. Prevents a duplicate Celery task execution (broker message duplication) from overwriting a correctly settled result, and also prevents `SoftTimeLimitExceeded` from downgrading a SUCCESS row to FAILURE when the signal fires after the DB commit.

2. **Single-commit task dispatch** (`backtest.py:176-212`) — pre-generates `task_id = str(uuid.uuid4())` before creating `BacktestResult`, stores it in the row, commits once, then dispatches via `apply_async(args=..., task_id=task_id)`. Eliminates the two-commit window where a failed second commit left `task_id=NULL` and a running Celery task orphaned from the client.

3. **isfinite guard** (`backtest_service.py:157-161`) — raises descriptive `ValueError` if `portfolio_equity` contains `inf`/`nan` before building daily returns. Without this, extreme theoretical returns or total-wipeout positions caused silent `FAILURE` via cryptic JSONB write rejection.

Deferred (TODOS added): `benchmark_ticker` not stored in `BacktestResult` (audit gap), migration downgrade unsafe for PENDING rows.

Gates: 7 deterministic math tests + ruff clean + mypy clean.

---

## 2026-06-07 — Phase 6: Backtesting Engine implementation

Commit: bf57e41

Implemented Phase 6 Backtesting Engine according to PHASES.md decisions 56–70. Phase 6 is **not marked complete yet** because the required financial-math `/review` checkpoint still needs to run.

**Files changed:**
- `app/models/backtest_result.py`, `app/models/user.py`, `app/models/__init__.py` — `BacktestStatus`, user/audit/task columns, nullable result blobs, relationship wiring.
- `alembic/versions/20260607_2330_7d8e9f012345_add_backtest_status_columns.py` — adds backtest status/audit columns, backfills `user_id`, and preserves existing result rows as SUCCESS.
- `app/schemas/backtest.py` — request/status/summary schemas; `BacktestSummary` intentionally excludes `equity_curve` and `daily_returns`.
- `app/services/market_data_service.py` — `_fetch_and_process_returns_by_date()` with yfinance exclusive-end handling.
- `app/services/backtest_service.py` — pure `run_backtest_engine()` plus `run_backtest` Celery task and copied NullPool DB bridge.
- `app/api/v1/backtest.py` — portfolio-scoped submit/status/list endpoints with auth, ownership checks, weight validation, and pre-dispatch data availability checks.
- `app/main.py`, `app/celery_app.py` — route/task registration.
- `tests/test_backtest.py` — 7 deterministic math tests, 11 DB-backed API tests, and 1 skipped live-network smoke.

**Implementation details:**
- CAGR uses true terminal return: `(final_value / initial_investment) ** (252 / n_trading_days) - 1`.
- `NEVER` rebalance is true buy-and-hold via per-asset cumulative returns, not daily-rebalanced weighted-return compounding.
- Rebalanced modes apply each boundary day's return before resetting asset buckets to target weights.
- Benchmark returns are fetched separately using `portfolio.benchmark_ticker`.
- Calmar is `None` when max drawdown is zero; Jensen alpha uses the current/fallback risk-free rate as a static approximation.
- POST preflights market data and rejects late-start or early-end gaps over 5 business days before inserting PENDING.

**Tests / checks:**
- `cd backend && .venv/bin/ruff check app tests/test_backtest.py alembic` — clean
- `cd backend && .venv/bin/mypy app` — clean (39 source files)
- `cd backend && .venv/bin/pytest tests/test_backtest.py -q` — 18 passed, 1 skipped
- `cd backend && .venv/bin/pytest -q` — 152 passed, 3 skipped
- `cd backend && .venv/bin/alembic upgrade head` — applied `9b1c2d3e4f50 -> 7d8e9f012345`
- `cd backend && .venv/bin/alembic check` — no new upgrade operations detected
- `gbrain sync` — blocked: gbrain database lacks `vector` extension / `sources` table; CLI suggested `gbrain apply-migrations --yes`

**Bug caught during verification:**
- Initial constant-return CAGR test used `(1 + weighted_daily_return)^n`, which is daily-rebalanced behavior. Corrected it to the locked buy-and-hold formula: `sum(w_i * (1 + r_i)^n)`.

## 2026-06-07 — Phase 6: /plan-eng-review complete, architecture locked (decisions 56–70)

Commit: eec0ec6

Full `/plan-eng-review` for Phase 6 Backtesting Engine. 7 interactive decisions (D1–D7) + 5 cross-model tension decisions (D8–D12) resolved. Codex outside voice ran and surfaced 15 additional issues; 5 became explicit locked decisions, 10 absorbed into the implementation spec. 15 architecture decisions locked in PHASES.md (decisions 56–70).

**Key decisions locked:**
- True terminal CAGR `(end/start)^(252/n_days)−1` — NOT `calculate_portfolio_metrics()` geometric return (D8)
- Copy NullPool bridge into backtest_service.py (do NOT touch simulation_service.py); extract _celery_db.py as Phase 7 cleanup (D9/D6 revised)
- Calmar = `Optional[float]`, `None` when max_drawdown == 0 (D10) — JSON cannot represent Infinity
- Benchmark = `portfolio.benchmark_ticker` (default SPY), with SPY-collision dedup (D11)
- NEVER rebalance = true buy-and-hold `Σ(w_i × cumreturn_i)`, NOT daily-rebalanced cumprod (D12)
- yfinance `end=end_date + timedelta(days=1)` (exclusive parameter, decision 67)
- Data availability: check BOTH late-start AND early-end >5 trading days (decision 60)
- Migration backfills `user_id` from portfolio → portfolios.user_id; makes result blobs nullable (decision 58)

**7 implementation tasks ready for Codex:**
- T1: Alembic migration (status/task_id/error/user_id/tickers/weights + nullable blobs + user_id backfill)
- T2: Pydantic schemas (BacktestRequest, BacktestTearsheet, BacktestStatusResponse, BacktestSummary, BacktestSubmitResponse)
- T3: `_fetch_and_process_returns_by_date()` in market_data_service.py
- T4: `run_backtest_engine()` pure function in backtest_service.py
- T5: `run_backtest` Celery task (copy NullPool bridge, same Phase 5 timeout + error pattern)
- T6: API endpoints (POST submit, GET status, GET list)
- T7: tests/test_backtest.py (7 math unit tests + 12 API integration tests + 1 integration smoke test)

## 2026-06-07 — Phase 5: /review pass — 6 fixes, Phase 5 complete

Commit: aacfe0f

Mandatory `/review` checkpoint on Phase 5 Monte Carlo (financial math phase). 9 issues found across critical pass + adversarial subagent. 6 fixes applied; 3 were low-severity informational notes requiring no code change.

**Fixes applied:**

1. **Geometric → arithmetic annual return** (`simulation_service.py`): `run_simulation` was passing `metrics["annual_return"]` (geometric, `(1+μ_d)^252 - 1`) into `run_monte_carlo`. The spec requires arithmetic (`μ_d * 252`). Using geometric overestimates daily drift by ~4% relative, compounding to ~10.28% terminal value inflation over 30 years. Fixed: `metrics["mean_daily_return"] * 252`.

2. **Zero floor on portfolio values** (`simulation_service.py`): Fat-tailed `t(df=5)` draws can produce `1 + r_t < 0` at very high volatilities, flipping the sign of `current_values` and letting them compound backward to nonsensical negatives. Fixed: `current_values = np.maximum(current_values * (1.0 + random_returns[day]), 0.0)`.

3. **Error string truncation** (`simulation_service.py`): `str(exc)` could exceed the `String(2000)` ORM column, causing `_write_result_to_db` itself to raise `DataError` and leave the row PENDING forever. Fixed: `str(exc)[:2000]`.

4. **Error-handler DB writes uncaught** (`simulation_service.py`): `_write_result_to_db_sync` calls inside both `except SoftTimeLimitExceeded` and `except Exception` handlers were uncaught; a DB failure there would propagate and leave rows PENDING. Fixed: wrapped each in its own `try/except Exception: _logger.exception(...)`.

5. **Seed range constraint** (`schemas/simulation.py`): PostgreSQL `INTEGER` is 32-bit max (2,147,483,647); seeds above that cause `DataError` on INSERT before Celery dispatch. Fixed: `seed: Annotated[int, Field(ge=0, le=2_147_483_647)] | None = None`.

6. **NullPool for Celery DB bridge** (`simulation_service.py`): Default SQLAlchemy pool creates 5 connections per single-use write. Fixed: `poolclass=NullPool` + comment documenting the prefork-only constraint of `asyncio.run()`.

**Tests added:**
- `test_simulation_post_with_other_users_portfolio_returns_404` — POST with another user's portfolio_id → 404 (covers D49)
- `test_simulation_request_rejects_duplicate_tickers` — `["AAPL", "aapl"]` → ValidationError (covers D53)

**Gates after fixes:** 134 passed, 2 skipped, ruff clean, mypy clean. **Phase 5 marked complete.**

---

## 2026-06-07 — Phase 5: Monte Carlo Simulation implementation

Commit: 9613e9b

Implemented Phase 5 Monte Carlo Simulation according to PHASES.md decisions 39–55. Phase 5 is **not marked complete yet** because the required financial-math `/review` checkpoint still needs to run.

**Files changed:**
- `app/models/simulation_result.py` — new `SimulationResult` model and `SimulationStatus` enum
- `app/models/__init__.py`, `app/models/user.py`, `app/models/portfolio.py` — model registration and relationships
- `alembic/versions/20260607_2200_9b1c2d3e4f50_add_simulation_results.py` — simulation table + native enum migration
- `app/services/simulation_service.py` — `run_monte_carlo()` + `run_simulation` Celery task + fresh-engine DB write bridge
- `app/schemas/simulation.py` — request/response/status schemas
- `app/api/v1/simulation.py` — POST submit + GET status endpoints
- `app/main.py`, `app/celery_app.py` — router/task registration
- `tests/test_simulation.py` — 19 tests for MC math, validation, and API state flow

**Implementation details:**
- RNG uses `np.random.default_rng(seed)`; no global `np.random.seed()`.
- Simulation returns use `standard_t(df=5)` directly scaled by daily sigma (`daily_mu + daily_sigma * t_draw`), preserving fat tails and intentionally higher realized vol.
- Contributions inject at year-end after that day’s return via `(day + 1) % 252 == 0`, giving exactly `years` contributions.
- `probability_of_profit` and `probability_of_doubling` compare final values against total outlay (`initial + annual_contribution * years`).
- `sample_paths` returns 20 quantile-sampled paths from sorted final values; for `n_simulations < 20`, indices intentionally repeat.
- Celery task treats any dropped ticker as FAILURE to avoid silently changing portfolio composition.
- Celery DB writes use `asyncio.run()` with a fresh async engine per write, then dispose it.

**Tests / checks:**
- `cd backend && .venv/bin/ruff check app tests alembic` — clean
- `cd backend && .venv/bin/mypy app` — clean (36 source files)
- `cd backend && .venv/bin/pytest -q` — 132 passed, 2 skipped
- `cd backend && .venv/bin/alembic upgrade head` — migration applied locally
- `cd backend && .venv/bin/alembic check` — no new upgrade operations detected

**Bug caught during verification:**
- Initial migration manually created `simulation_status` and then used the same `sa.Enum` in `create_table`, causing SQLAlchemy to emit a duplicate `CREATE TYPE`. Fixed by creating the enum once and using `postgresql.ENUM(..., create_type=False)` in the table definition.

## 2026-06-07 — Phase 5: /plan-eng-review complete, architecture locked (decisions 39-55)

Commit: 69689a3

Full `/plan-eng-review` for Phase 5 Monte Carlo Simulation. 9 interactive decisions resolved. 17 architecture decisions locked in PHASES.md (decisions 39–55). Codex outside voice ran and caught 6 additional issues absorbed into decisions. 2 new TODOs added (TODO-4: orphan cleanup, TODO-5: vectorized fast-path).

**Key decisions locked:**
- `np.random.default_rng(seed)` (thread-safe, not global `np.random.seed()`)
- Contribution fence-post fix: `portfolio_values[year*252 - 1]` for `year in range(1, years+1)` → exactly N injections
- `probability_of_profit` vs. total outlay (initial + contributions × years)
- `SimulationResult` ORM model: new file, nullable `portfolio_id`, required `user_id`, `tickers`/`weights`/`period` columns for audit trail
- Celery DB bridge: `asyncio.run()` with **fresh** async engine created inside each call (not module-level engine — avoids event-loop/pool conflict)
- `GET /simulation/{id}` filters by both `id` AND `user_id` (cross-user read guard)
- `portfolio_id` ownership validation at POST time if provided
- Same Celery timeouts as Phase 4: `soft_time_limit=55, time_limit=60`
- API input: `tickers + weights + period` (ad-hoc) with optional `portfolio_id` link

**5 implementation tasks** ready for Codex:
- T1: `run_monte_carlo()` in simulation_service.py
- T2: `SimulationResult` model + Alembic migration
- T3: Celery `run_simulation` task + asyncio.run() DB bridge
- T4: API endpoints (POST + GET) with full input validation
- T5: `tests/test_simulation.py` (18 tests)

## 2026-06-07 — Phase 4: /review pass — 2 fixes, Phase 4 complete

Commit: e83e640

Manual `/review` checklist pass on Phase 4 (direct-to-main workflow). Zero critical findings. Two informational fixes applied:

1. **Corrupt cache falls through in Celery task** (`optimization_service.py:370`): `deserialize_frontier_result` inside the Celery task was not wrapped in try/except. Corrupt cache → task FAILURE instead of re-fetch. Fixed: added try/except + warning log, same pattern as `_get_cached_frontier` in `analysis.py`.

2. **`FrontierPoint` fields undocumented re: arithmetic/geometric convention** (`portfolio.py:168`): `annual_return` is geometric but `sharpe_ratio` uses arithmetic return in the numerator. A consumer computing `(annual_return - rfr) / vol` from the API response gets a slightly different Sharpe. Fixed: added `description=` to both fields documenting the convention.

Gates: 113 passed, 2 skipped, ruff clean, mypy clean. **Phase 4 marked complete.**

## 2026-06-07 — Phase 4: Efficient Frontier implementation

Commit: 99cb890

Implemented Phase 4 efficient frontier code, following PHASES.md decisions 28–38. Phase 4 is **not marked complete yet** because the required financial-math `/review` checkpoint still needs to run.

**Files changed:**
- `app/schemas/portfolio.py` — added `FrontierRequest`, `FrontierPoint`, `FrontierResult`, `FrontierTaskStatus`, `FrontierSubmitResponse`
- `app/services/optimization_service.py` — new Markowitz optimizer service + Redis cache helpers + `compute_frontier` Celery task
- `app/celery_app.py` — registered optimization task module
- `app/api/v1/analysis.py` — added authenticated submit/poll endpoints for frontier tasks
- `tests/test_efficient_frontier.py` — added deterministic math tests and API auth/validation/task-failure tests
- `mypy.ini` — ignored missing SciPy stubs, matching existing yfinance/pandas stub policy

**Implementation details:**
- Optimizer solves min-variance first and uses its arithmetic annual return as the lower target bound.
- Frontier target constraints use arithmetic annual return (`252 * w.T @ mu_daily`); API `annual_return` reports geometric annual return.
- SLSQP runs sequentially with warm starts; individual target failures are skipped for partial frontier output.
- `find_max_sharpe_portfolio` uses arithmetic expected return in the Sharpe objective and guards near-zero volatility.
- `POST /analysis/frontier` checks Redis before dispatching Celery; cache hit returns `SUCCESS` with `task_id=null`.
- `GET /analysis/frontier/{task_id}` reads Celery state/info without `.get()` and stringifies raw failure exceptions.
- Celery task uses sync Redis and sync market-data private methods; risk-free-rate fetch falls back to `0.04`.

**Tests / checks:**
- `cd backend && .venv/bin/ruff check app tests` — clean
- `cd backend && .venv/bin/mypy app` — clean (32 source files)
- `cd backend && .venv/bin/pytest -q` — 113 passed, 2 skipped (live-network market-data tests)

**Gotcha found:**
- The restricted Codex sandbox cannot reach Docker-published localhost ports, so DB-backed pytest runs must execute with sandbox escalation. The new frontier API tests avoid the DB fixture because these endpoints can validate auth/422/task failure hermetically via FastAPI dependency overrides.

## 2026-06-06 — Phase 4: /plan-eng-review complete, architecture locked

Commit: (planning session — no code committed yet)

Full `/plan-eng-review` for Phase 4 (Efficient Frontier). 11 architecture and code quality issues found across 4 review sections + Codex outside voice. All resolved. Key decisions locked in PHASES.md decisions 28–38:

**Architecture changes from original plan:**
- `ProcessPoolExecutor` removed — replaced with sequential warm-start loop (~1s total; fork-from-prefork risk avoided)
- Celery task moves to `optimization_service.py` (not `celery_tasks/efficient_frontier.py` — spec and `celery_app.py` both point here)
- Return convention fixed: arithmetic means in optimizer, geometric in output (MPT correctness — non-linear geometric means break SLSQP target constraint)
- Task timeout corrected: `soft=55s, hard=60s` (not `25/30` — yfinance fetch can take up to 30s)
- Celery task integration: call `_fetch_and_process_returns()` directly (sync), use `redis.Redis` (sync) — no FastAPI DI in Celery worker context

**New correctness requirements:**
- Duplicate tickers → 422 at API layer (after uppercase normalization — `"AAPL"` and `"aapl"` are duplicates)
- Single-asset input → 422 (frontier requires ≥ 2 assets)
- `AsyncResult.info` on FAILURE → `str(result.info)` (raw exception is not JSON-safe → HTTP 500)
- `find_min_variance_portfolio` takes no `rfr` arg (min-variance doesn't use it)
- Infeasible target returns → skip point, return partial frontier (not task FAILURE)

**Test plan update:**
- Added `test_efficient_frontier.py` requirement with math unit tests (deterministic fixtures) + API integration tests (401, 422 variants, task states)
- `max Sharpe > individual Sharpe` is a wrong invariant — replaced with: max-Sharpe weights valid and Sharpe ≥ each individual asset's Sharpe

**New files to create:** TODOS.md (3 deferred items: cache stampede protection, Tikhonov regularization, Celery re-evaluation)

---

## 2026-06-06 — Phase 3: /review findings and fixes

Commit: 9f5ebbb

Manual checklist pass (direct-to-main workflow) against the Phase 3 diff. Six bugs fixed across three categories: correctness, security, and data safety.

**Bugs fixed:**

1. **`portfolios.py:96` — `update_portfolio` missing None check after reload (correctness)**
   - After `db.commit()`, re-fetching with `get_portfolio()` returns `Portfolio | None`. The result was passed directly to `PortfolioOut.model_validate()` without a None guard, identical to the already-fixed bug in `create_portfolio`. In an extreme concurrent-delete race the response would be a Pydantic 500 instead of the expected 404.
   - Fix: renamed variable to `reloaded`, added `assert reloaded is not None` (matching `create_portfolio` pattern).

2. **`analysis.py:147` — GET metrics endpoint accepted `confidence=0` (correctness → IndexError)**
   - `confidence: float = 0.95` had no bounds. With `confidence=0.0`, `(1-0)*N = N`, `sorted_returns[N]` raises IndexError (500). The POST endpoint's `MetricsRequest` correctly used `Field(gt=0, lt=1)`.
   - Fix: changed to `Annotated[float, Query(gt=0, lt=1)] = 0.95` — FastAPI now returns 422 for out-of-range values before handler code runs.

3. **`risk_service.py` — `calculate_correlation_matrix` propagated NaN (data safety → JSON 500)**
   - A ticker with zero variance over the requested window produces NaN from `pd.DataFrame.corr()`. `corr.values.tolist()` passes NaN through Pydantic's `list[list[float]]` field, then FastAPI's JSON encoder raises `ValueError: Out of range float values are not JSON compliant`.
   - Fix: `corr.fillna(0.0)` then `np.fill_diagonal(..., 1.0)` to restore self-correlation. Test added.

4. **`analysis.py` — `POST /analysis/metrics` had no auth (security — CRITICAL)**
   - The ad-hoc metrics endpoint accepted requests without a `CurrentUser` dependency. Any unauthenticated caller could trigger yfinance fetches for up to 50 tickers with `period=max` at no cost.
   - Fix: added `current_user: CurrentUser` parameter. Detected by security specialist subagent.

5. **`schemas/portfolio.py` — `MetricsRequest.benchmark_ticker` had no pattern constraint (security — MEDIUM)**
   - `AdHocHolding.ticker` already had `pattern=r"^[A-Za-z0-9.^=\-]{1,20}$"` to prevent Redis key injection (added in Phase 2 /review). `benchmark_ticker` had only `max_length=20` — inconsistency that left the same injection surface open.
   - Fix: applied the same pattern constraint to `benchmark_ticker`.

6. **`schemas/portfolio.py` — ad-hoc POST path silently re-normalized mismatched weights (correctness)**
   - The saved-portfolio path runs `_validate_weights()` to reject submissions where weights don't sum to 1.0. The ad-hoc POST path had no such check — `[0.3, 0.3]` would silently compute metrics for a `[0.5, 0.5]` portfolio.
   - Fix: added `@model_validator(mode="after")` to `MetricsRequest` that rejects weight sum outside `1.0 ± 0.01`.

**New tests:**
- `tests/test_analysis.py` (new file, 14 tests): auth, 404, ownership isolation, empty-portfolio 422, `confidence=0` 422, invalid period — all analysis endpoints.
- `tests/test_risk_metrics.py`: added `test_correlation_matrix_zero_variance_fills_nan` for the NaN-fill fix.

**Informational (not fixed — design/future):**
- `peak_date: str | int` in `PortfolioMetricsResponse` exposes implementation detail; the `int` path only fires on ndarray input which never comes from the saved-portfolio route. Track for Phase 4 cleanup.
- `_compute_metrics` is a coordination monolith; will need to expose sub-pipelines cleanly when Phase 4 (efficient frontier) reuses the returns/weights pipeline.
- `calculate_beta_from_ticker` lives in `portfolio_service.py` but imports from two other services; natural refactor point when Phase 4 needs beta.

**Final gate:** 102 passed, 2 skipped, ruff clean.

---

## 2026-06-06 — Phase 3: Portfolio Service and Risk Metrics

Commit: cae7d23

Implemented Phase 3 in full: ground-truth fixtures, pure-math risk service, portfolio CRUD, and
metrics endpoints. All 89 tests passing, ruff clean, mypy 0 errors (40 source files).

**New files:**
- `backend/tests/fixtures/__init__.py` + `known_values.py` — deterministic expected values with hand-derivable formulas; can be printed via `python -m tests.fixtures.known_values`
- `backend/app/services/risk_service.py` — all pure math, no I/O: `calculate_portfolio_metrics`, `calculate_var_cvar`, `calculate_max_drawdown`, `calculate_sortino`, `_compute_beta`, `calculate_beta_from_returns`, `calculate_correlation_matrix`
- `backend/app/schemas/portfolio.py` — Pydantic schemas for portfolio CRUD + metrics endpoints
- `backend/app/api/v1/portfolios.py` — full portfolio + holding CRUD (auth-required)
- `backend/app/api/v1/analysis.py` — `POST /api/v1/analysis/metrics` (ad-hoc) + `GET /api/v1/analysis/portfolios/{id}/metrics` (saved)
- `backend/tests/test_risk_metrics.py` — 27 tests covering all 7 functions + edge cases
- `backend/tests/test_portfolios.py` — 14 integration tests for portfolio/holding CRUD

**Updated files:**
- `backend/app/services/portfolio_service.py` — added full CRUD + `_validate_weights()` + `calculate_beta_from_ticker()` orchestration
- `backend/app/main.py` — registered `portfolios` and `analysis` routers

**Key implementation decisions:**
- Annual return: `(1 + mean_daily)^252 - 1` (geometric compounding, not linear)
- Annual vol: `std_daily(ddof=1) * sqrt(252)`
- Sharpe guard: `if annual_vol > 1e-8` — prevents ÷0 on float64 constant series (sample std is O(1e-19), not exactly 0)
- VaR: 252-day rolling window (NOT `daily_var * sqrt(252)`); `var_index = max(int((1-confidence)*N), 1)` prevents empty-slice NaN
- Sortino: Sortino & van der Meer 1991 formula — `sqrt(mean(min(r,0)^2)) * sqrt(252)`, divides by N (ALL observations)
- Beta: `cov(port,bench,ddof=1)[0,1] / cov[1,1]`; returns 0.0 if benchmark variance is zero
- Weight validation deferred to metrics time (not each CRUD write) to support one-at-a-time Portfolio Builder UX
- After `db.commit()` in routes, reload ORM objects via `selectinload` query to avoid MissingGreenlet on async lazy load
- Beta computation is best-effort in metrics endpoint — logs warning, returns `beta=None` rather than 500

**Ruff/mypy fixes applied during quality gate:**
- RUF002/RUF003: replaced Unicode math symbols (`−`, `×`) with ASCII in docstrings
- RUF059: renamed unused unpacked variables to `_` in market_data route + tests
- UP042: `str, enum.Enum` → `enum.StrEnum` for `AssetClass` and `RebalanceFrequency` (Python 3.11+, no migration needed)
- 14 mypy errors fixed: unused `# type: ignore` comments, missing type params in conftest/fixtures, `np.full` vs `np.ones()*scalar` type inference, type-narrowing via `isinstance` in `calculate_max_drawdown`

## 2026-06-06 — Phase 2: /review pass fixes

Commit: c2c9c51

Manual `/review` pass with specialist subagents (testing, maintainability, security) surfaced
and fixed the following. All gates still green after fixes (48 passed, 2 skipped).

**AUTO-FIXED:**
- `_fetch_rfr` and `_fetch_quote`: added `isinstance(close_col, pd.DataFrame)` guard before
  `float(.iloc[-1])`. yfinance 0.2.51 returns MultiIndex columns by default (`multi_level_index=True`),
  so `raw["Close"]` is always a DataFrame, making `.iloc[-1]` a Series. `float(Series)` produces
  a FutureWarning today and will raise TypeError in a future pandas release. Fix uses `.iloc[:, 0]`
  to reliably extract the Series from either flat or MultiIndex format.
- Extracted `_FETCH_TIMEOUT = 30.0`, `_VALIDATE_TIMEOUT = 15.0`, `_SEARCH_MAX_RESULTS = 10`
  as named class constants (30.0 was repeated 4 times inline).
- Removed double try/except in `_fetch_rfr` — inner `try/except` was redundant; the outer
  `get_risk_free_rate` catch-all is the single authoritative fallback to 0.04.
- `get_historical_returns` ValueError no longer leaks the normalized ticker list in the
  HTTP response body; logged server-side instead.
- `get_ticker_info` route no longer includes `str(exc)` in 422 detail; internal error
  logged server-side only.
- Added comment on the `is_nan.groupby((~is_nan).cumsum()).sum().max()` run-length-encoding
  one-liner in `_apply_data_quality`.
- Added `description=` to `ValidateTickersRequest.tickers` Field.

**SECURITY (user-approved):**
- Added per-item ticker character whitelist (`_TickerStr`, `_TickerPath`) — pattern
  `^[A-Za-z0-9.^=\\-]{1,20}$` prevents comma/colon injection into Redis cache keys.
  Without this, a ticker like `"AAPL,MSFT"` (single item) would produce key
  `qv:mds:returns:AAPL,MSFT:1y`, colliding with Phase 3 portfolio analytics calls
  for the two-ticker pair. Applied to both `ValidateTickersRequest` items and route
  `Path()` parameters on `/{ticker}/history` and `/{ticker}/info`.

**TESTS added (9 new, 48 total):**
- `test_rfr_multiindex_column_format` — exercises the new isinstance guard for ^TNX
- `test_quote_multiindex_column_format` — exercises the new isinstance guard for quotes
- `test_history_422_on_invalid_period` — missing negative path for period validation
- `test_data_quality_boundary_exactly_max_gap` — fence-post: exactly 5 NaNs → kept
- `test_data_quality_drops_exactly_max_gap_plus_one` — exactly 6 NaNs → dropped
- `test_validate_tickers_all_valid` / `_all_invalid` / `_exception_treated_as_invalid`
- `test_redis_write_failure_does_not_propagate` — cache setex error must not surface to caller

**DEFERRED (explicitly NOT in Phase 2 scope per PHASES.md):**
- Rate limiting on `/validate-tickers` (50 parallel yfinance downloads per request) — PHASES.md
  "NOT in scope (Phase 2)". Add with Phase 4 API hardening.
- Redis TLS/auth enforcement — deployment-level concern, not code.

## 2026-06-06 — Phase 2: full implementation (T1–T5)

Commit: b40d4d2

Implemented Phase 2 (MarketDataService) in full:

**Files created:**
- `app/core/redis.py` — module-level `redis_client` singleton + `get_redis()` DI, mirrors `database.py`
- `app/services/market_data_service.py` — `MarketDataService` class: `_cache_through()` TypeVar helper,
  `_apply_data_quality()`, `_fetch_and_process_returns()`, `get_historical_returns()`,
  `get_risk_free_rate()`, `get_ticker_info()`, `get_quote()`, `search_tickers()`,
  `validate_tickers()`, `get_market_data_service()` DI function
- `app/schemas/market_data.py` — `HistoricalDataResponse`, `TickerInfoResponse`,
  `QuoteResponse`, `TickerSearchResult`, `TickerSearchResponse`, `ValidateTickersRequest`,
  `ValidateTickersResponse`
- `app/api/v1/market_data.py` — 4 public endpoints: `GET /search`, `GET /{ticker}/history`,
  `GET /{ticker}/info`, `POST /validate-tickers`
- `tests/test_market_data.py` — 19 unit tests + 2 integration smoke tests (behind `INTEGRATION_TESTS=1`)

**Files edited:**
- `app/main.py` — registered `market_data.router` at `/api/v1/market`
- `requirements-dev.txt` — added `fakeredis==2.26.2`
- `mypy.ini` — added `[mypy-pandas.*]` and `[mypy-fakeredis.*]` ignore_missing_imports

**Verification:** `ruff check` clean, `ruff format` clean, `mypy app` 0 errors,
`pytest -q` 39 passed, 2 skipped (integration).

Non-obvious implementation decisions:
- `_fetch_and_process_returns` is sync (called via `asyncio.to_thread`) — tests mock it
  directly via `patch.object` rather than mocking `yf.download`, which would require
  building OHLCV-format mock DataFrames
- TypeVar T in `_cache_through` correctly flows through `serialize`/`deserialize`
  even when using stdlib `str`/`float`/`json.loads` as callables
- redis.asyncio.Redis doesn't support `[bytes]` type arg in redis 5.x stubs — use bare `Redis`

## 2026-06-06 — Phase 2: fix ^TNX math across all docs

Commit: 4c106e7

Corrected the `^TNX` risk-free rate formula across PHASES.md (decision 25),
HANDOFF.md (both "Known quirks" and "Next up"), and AI_CONTEXT.md. The
original "divide by 10" note was wrong: if Yahoo Finance returns `4.21`
(4.21%), then `/ 10 = 0.42` (42% risk-free rate — nonsense). The correct
formula is `raw / 100 → 0.0421`. Cross-confirmed via the `0.04` fallback:
if raw ≈ 4.0 and we need decimal ≈ 0.04, the formula must be `/ 100`.
This was verified from first principles because Yahoo Finance was unreachable
from WSL2 (rate-limiting/blocking) during the live-data verification attempt.
T6 (live verification) remains open but unblocked — the formula is settled.

## 2026-06-06 — Phase 2 planning: architecture locked via /plan-eng-review

Commit: 4c106e7 (docs only) — lock Phase 2 architecture decisions in PHASES.md, HANDOFF.md, AI_CONTEXT.md

Ran `/plan-eng-review` for Phase 2 (MarketDataService). 9 architecture/code-quality/test
issues surfaced and resolved interactively; Codex outside voice ran and surfaced 5 additional
findings, all accepted. Decisions 15–27 added to `PHASES.md` architecture table. No code
written yet — this is the planning session.

Key decisions that would be non-obvious from the spec:
- `_cache_through(key, ttl, fetch_fn, serialize, deserialize)` private helper DRYs 4 identical
  cache-get/miss/set blocks; graceful-degradation (Redis failure + corrupt cache) written once.
- `asyncio.wait_for(asyncio.to_thread(...), timeout=30.0)` for all yfinance calls — 30s cap
  prevents hung requests from exhausting uvicorn's thread pool.
- `get_historical_returns()` returns DataFrame in REQUESTED ticker order (not sorted order),
  via `returns_df[tickers]` reindex — sorted order is only for the cache key. Phase 3 dot
  products with `portfolio_to_weights()` weights depend on this being correct.
- `^TNX` "divide by 10" note in docs is ambiguous. Verify with live `yf.download("^TNX", ...)` 
  in dev shell before implementing Phase 3 Sharpe/Sortino (decision 25).
- Cache keys prefixed `qv:mds:` to avoid Celery collision in Redis DB 0.
- `fakeredis[aioredis]` for test isolation — `AsyncMock` can't test real cache hit/miss behavior.
- Partial results (dropped tickers) NOT cached; only complete fetches write to Redis.

Also updated `CLAUDE.md` to extend the Skill Routing section (was missing /context-restore,
/spec, /office-hours, /investigate, and others).

## 2026-06-06 — Phase 1: Domain, Database, and Auth

Commit: `4c5e0c4` — feat: add Phase 1 domain models, JWT auth, and seed script

Built the domain layer (`User`/`Portfolio`/`Holding`/`BacktestResult` ORM
models + initial Alembic migration), `portfolio_to_weights()`, JWT auth
(`/auth/register`, `/auth/login`, `/auth/refresh`, `get_current_user`), 19
auth unit tests, and an idempotent seed script. Three bugs surfaced and fixed
along the way:

- **pytest-asyncio event-loop mismatch** (latent since Phase 0): `pytest.ini`
  sets `asyncio_default_fixture_loop_scope = session` so the async DB
  fixtures (`engine`, `db_session`, `client`) share one session-scoped loop —
  but `asyncio_mode = auto` auto-marks *test functions* with a bare
  `@pytest.mark.asyncio`, which defaults to `loop_scope="function"`, a
  different loop. The asyncpg connection's internal locks/futures get created
  on the session loop (inside the `db_session` fixture) and then awaited from
  the test's function-scoped loop the moment a test issues a real query —
  `RuntimeError: Future ... attached to a different loop`. `test_health.py`
  never tripped this because its handler has no `db` dependency. Fixed with a
  `pytest_collection_modifyitems` hook in `conftest.py` that strips the
  auto-applied marker and replaces it with `pytest.mark.asyncio(loop_scope="session")`
  — pins every async test to the same loop as the fixtures, globally, with no
  per-file boilerplate.
- **Dev DB schema / `alembic_version` desync**: `make seed` failed with
  `UndefinedTableError: relation "users" does not exist` even though
  `alembic current` reported the migration as applied — the dev DB contained
  only the `alembic_version` table (likely residue from earlier manual `psql`
  cleanup of orphaned enum types, which also dropped the data tables without
  going through `alembic downgrade`). Fixed via `alembic stamp base` (resets
  the version table to match the empty schema) + `alembic upgrade head`
  (replays the DDL, recreating all four tables fresh).
- **`register` race condition** (caught during manual `/review`): the
  check-then-insert pattern (`_get_user_by_email` existence check, then
  `db.add`/`db.commit()`) has a TOCTOU window — two concurrent registrations
  for the same email both pass the check, then race to commit; the loser hits
  `users.email`'s unique constraint and the resulting `IntegrityError`
  surfaced as a raw 500 instead of the intended 409. Fixed by catching
  `IntegrityError`, rolling back, and translating it to the same 409
  (`app/api/v1/auth.py`). Also renamed `_get_active_user_by_email` →
  `_get_user_by_email` — the old name implied an `is_active` filter that
  doesn't exist (both call sites correctly need the unfiltered row; see
  `HANDOFF.md` "Known quirks" for why).

**Manual `/review` pass** (skill's branch-detection short-circuits on `main`,
which is this repo's established direct-to-main workflow): walked the full
diff against the CRITICAL/INFORMATIONAL checklist categories. Findings:
the `register` race condition above (fixed), plus two informational notes
now recorded in `HANDOFF.md` "Known quirks" for future awareness — bcrypt
hashing blocks the event loop synchronously inside async route handlers
(fine at demo scale; `asyncio.to_thread()` is the upgrade path), and
`/register`'s `409` already reveals email existence even though `/login`
deliberately collapses unknown-email/wrong-password into one `401` to avoid
enumeration (a common, accepted UX-vs-security tradeoff — flagging the
inconsistency for a conscious team call, not blocking).

**Verification results** (all green):
`ruff check . && ruff format .` clean · `mypy app` — 0 errors across 23
modules · `pytest -q` — 20 passed · `alembic check` — no diff detected ·
`make seed` — creates `demo@quantvault.dev` with a three-fund portfolio
(VTI 60% / BND 30% / VXUS 10%, weights sum to 1.0 exactly,
`default_portfolio_id` wired correctly), idempotent on re-run.

## 2026-06-05 — Phase 0 verification pass (live db + redis)

Commit: `a9e8ec7` — feat: scaffold Phase 0 — backend, frontend, infra, and docs

The scaffold below was written against no running services. This slice brings
up the real stack (`docker compose up -d db redis`) and runs every Phase 0
verification gate against it — `make lint`, `make test`, `make migrate`, the
Celery worker, pre-commit, and the frontend dev server — fixing what broke:

- **`docker-compose.yml`**: `db` had no `ports:` mapping, so the host-side
  `.venv` (which is what `make test`/`make migrate` actually run) couldn't
  reach Postgres at `localhost:5432` — only containers on the compose network
  could see it as `db:5432`. Added `ports: ["5432:5432"]`. This is intentional
  asymmetry from `redis` (which already published its port): the backend
  container always talks to `db`/`redis` by service name, but local
  dev/tooling on the host needs the published port too.
- **`.env.example`**: `DB_PASSWORD=change-me` didn't match the `Settings`
  defaults in `app/core/config.py` (`postgresql+asyncpg://qv:qv@...`). A fresh
  `cp .env.example .env && docker compose up -d db` produced a Postgres
  container whose password (`change-me`) didn't match what the host-side app
  expected (`qv`) — `InvalidPasswordError`. Changed `DB_PASSWORD` to `qv` so
  the example file and the code defaults agree out of the box; `SECRET_KEY`
  remains the one value that actually needs rotating (already flagged with
  the `openssl rand -hex 32` hint).
- **`pytest.ini`**: `asyncio_default_fixture_loop_scope = function` caused
  `ScopeMismatch: You tried to access the function scoped fixture event_loop
  with a session scoped request object` on the session-scoped async `engine`
  fixture in `conftest.py`. Changed to `session` — narrower-scoped async
  fixtures (`db_session`, `client`) can still ride a broader-scoped loop.
- **`app/core/security.py`**: mypy flagged `no-any-return` on
  `hash_password`/`verify_password` because `passlib`'s `CryptContext` ships
  no type stubs (its methods type as `Any`). Wrapped the returns in
  `str(...)`/`bool(...)` — both are documented to return those types; this
  just gives mypy (and readers) a concrete contract at the boundary.
- **`app/celery_app.py`**: booting the worker against live Redis surfaced a
  `CPendingDeprecationWarning` about `broker_connection_retry_on_startup` (the
  Celery 6.0 default flips). Set it to `True` explicitly — same behavior,
  silences the warning, and documents the intent before the flip lands.
- Ruff also caught two pre-existing nits (`I001` unsorted imports in
  `alembic/env.py`/`tests/conftest.py`, `UP017` `datetime.timezone.utc` →
  `datetime.UTC`) — fixed via `ruff check --fix` + `ruff format`.

**Verification results** (all green after fixes):
`ruff check . && ruff format .` clean · `mypy app` — 0 errors across 12
modules · `pytest -v` — `test_health` passes against a live `quantvault_test`
Postgres database · `alembic upgrade head` runs cleanly (no-op — no models
yet; generated and discarded a throwaway autogenerate revision to confirm the
async `env.py` pipeline works end-to-end) · `celery -A app.celery_app worker`
connects to `redis://localhost:6379/0` with no warnings · `pre-commit run`
installs all three hook environments and passes on first run · frontend dev
server renders `DashboardPage` with Inter font, indigo "QV" badge, and the
`tw-animate-css` fade-in/slide-in animation, confirmed via `/browse`.

Containers were torn down (`docker compose down`) after verification; named
volumes (`pgdata`, `redisdata`) persist for the next session.

## 2026-06-05 — Phase 0 scaffold

`/plan-eng-review` locked the architecture earlier today (commit `f5feb24`).
This session scaffolds the repo to match `quantvault.md`'s solution structure
so Phase 1 (domain models + auth) has somewhere to land.

**Backend** (`backend/`):
- Python 3.12 venv + `requirements.txt` / `requirements-dev.txt` (split so
  prod images don't carry pytest/ruff/mypy)
- FastAPI app factory in `app/main.py` (`create_app()`, CORS middleware,
  `/health`); `core/config.py` (pydantic-settings), `core/database.py`
  (async engine/session + `Base`), `core/security.py` (PyJWT + bcrypt —
  per the locked decision to avoid python-jose's CVEs)
- Package skeleton: `models/`, `schemas/`, `api/v1/`, `services/`
- Alembic wired async (`alembic/env.py` uses `async_engine_from_config` and
  reads `DATABASE_URL` from `app.core.config.settings` rather than a
  hardcoded `sqlalchemy.url`, so migrations always target the same DB the
  app connects to). `app/models/__init__.py` is the registration point —
  new models just get imported there and `env.py` sees them automatically.
- `celery_app.py` — Celery app with Redis broker/backend, ready for the
  efficient-frontier / Monte Carlo / backtest task modules in later phases
- `pytest.ini` + `tests/conftest.py` (async session fixture wrapped in a
  rolled-back transaction per test, httpx `AsyncClient` with `get_db`
  overridden) + a `/health` smoke test; `ruff.toml`, `mypy.ini` (strict),
  `.pre-commit-config.yaml`

**Deferred to Phase 1 (deliberately):** `app/dependencies.py`
(`get_current_user`) and the seed script both need `User`/`Portfolio`/
`Holding` ORM models that don't exist yet — writing them now would mean
importing nonexistent modules and failing mypy. They land with the auth
endpoints in Phase 1.

**Frontend** (`frontend/`): React 18 + TS + Tailwind via Vite, base structure
per `quantvault.md` (pages/, components/{charts,portfolio}/, services/,
store/, types/), locked design tokens applied (Inter, indigo `#6366f1` accent).

**Infra**: `docker-compose.yml` (backend, frontend, db, redis,
celery-worker — 5 services per the locked Celery+Redis decision), backend +
frontend Dockerfiles, `.env.example`, `Makefile` (`make dev/test/lint/fmt/
migrate/seed`).

**Environment note**: this WSL box can't `apt install python3.12-venv`
(needs sudo password we don't have), so `backend/.venv` was built with
`virtualenv` instead of the stdlib `venv`. Same result; `pip` only resolves
via `python -m pip` here (no `bin/pip` shim got generated).

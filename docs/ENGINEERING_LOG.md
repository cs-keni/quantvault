# Engineering Log

Reverse-chronological. One entry per session/slice — what changed and why,
not a diff (git history is authoritative for that).

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

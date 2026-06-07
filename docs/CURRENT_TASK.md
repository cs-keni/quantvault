# Current Task

**Phase 4 — Efficient Frontier** 🔄 ready to implement

`/plan-eng-review` completed 2026-06-06. Architecture locked in PHASES.md decisions 28–38. All implementation tasks defined. See PHASES.md Phase 4 section for the full spec.

**Implement in this order:**
1. `backend/app/schemas/portfolio.py` — add `FrontierRequest`, `FrontierPoint`, `FrontierResult`, `FrontierTaskStatus`, `FrontierSubmitResponse`
2. `backend/app/services/optimization_service.py` (NEW) — `find_min_variance_portfolio`, `find_max_sharpe_portfolio`, `generate_efficient_frontier`, `@celery_app.task compute_frontier`
3. `backend/app/celery_app.py` — uncomment `"app.services.optimization_service"` in the include list
4. `backend/app/api/v1/analysis.py` — add `POST /analysis/frontier` and `GET /analysis/frontier/{task_id}`
5. `backend/tests/test_efficient_frontier.py` (NEW) — math unit tests + API integration tests

**Run `/review` before marking Phase 4 complete** (financial math phase, non-negotiable).

### Key implementation rules (all locked — do not re-debate):
- Celery task: call `market_data_service._fetch_and_process_returns(sorted_tickers, period)` directly (sync); use `redis.Redis.from_url(settings.REDIS_URL)` (sync — NOT redis.asyncio). There is no FastAPI DI in Celery workers.
- Optimizer: use **arithmetic** daily mean returns for `w.T @ mu >= target` constraint; report **geometric** annual return `(1+mean_daily_port_r)^252 - 1` in `FrontierPoint.annual_return`
- Celery task decorator: `@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)` (yfinance can take up to 30s; 25s would kill the task before data arrives)
- Auth: `CurrentUser` required on **both** endpoints (unauthenticated callers must not trigger yfinance + Celery work)
- `AsyncResult.info` on FAILURE is a raw Python exception — **must** `str(result.info)` before including in response (FastAPI's JSON encoder raises HTTP 500 on raw exceptions)
- Duplicate ticker check: uppercase-normalize first, then dedup — `["AAPL", "aapl"]` must be caught
- Solver failure at an infeasible target return: skip the point, continue, return partial frontier

---

**Phase 3 — Portfolio Service and Risk Metrics** ✅ complete (review passed)

Implementation complete. 102 tests passing (2 skipped — integration-only), ruff clean.

All financial functions verified against hand-derivable ground-truth values in `tests/fixtures/known_values.py`.

`/review` pass complete — 6 bugs found and fixed (auth missing on ad-hoc endpoint, confidence IndexError, correlation NaN, update_portfolio None check, benchmark_ticker pattern, ad-hoc weight-sum validation). See ENGINEERING_LOG.md 2026-06-06.

**T6 (^TNX live verification)** — still open, network-blocked. Formula confirmed as `/ 100` via fallback cross-check. Verify when Yahoo Finance is reachable from WSL2.

---

**Phase 1 — Domain, Database, and Auth** ✅ complete, verified end-to-end

Built the domain layer and JWT auth on top of the Phase 0 scaffold:

- [x] SQLAlchemy ORM models: `User`, `Portfolio`, `Holding`, `BacktestResult`
      (incl. `AssetClass`/`RebalanceFrequency` native Postgres enums,
      `User.default_portfolio_id` circular FK via `use_alter`/`post_update`)
- [x] Alembic initial migration (`30594d39da38`) — creates all 4 tables + enums
- [x] `portfolio_to_weights()` in `portfolio_service.py` — the single
      `Decimal` → `float64` conversion point for downstream numpy/scipy math
- [x] JWT auth (PyJWT): `/auth/register`, `/auth/login`, `/auth/refresh`,
      `app/dependencies.py::get_current_user`
- [x] Unit tests for auth flows — 19 tests covering register/login/refresh/
      `get_current_user`, incl. expired/malformed/wrong-type/deactivated/
      unknown-user edge cases (full suite: 20 passed)
- [x] Seed script (`make seed`) — idempotent demo user + three-fund portfolio
      (VTI 60% / BND 30% / VXUS 10%, weights sum to 1.0 exactly)
- [x] Manual `/review` pass (see `ENGINEERING_LOG.md` for findings + fixes)

**Verified live**:
- `ruff check`/`ruff format` — clean
- `mypy app` — clean (23 source files)
- `pytest` (full suite) — 20 passed
- `alembic check` — no diff detected
- `make seed` — creates demo data end-to-end against the dev DB; idempotent on re-run

**Fixed along the way** (see `ENGINEERING_LOG.md` 2026-06-06 for full root-cause
write-ups): a latent pytest-asyncio event-loop mismatch in the Phase 0
`conftest.py` (fixtures vs. test functions on different loops), a dev-DB
schema/`alembic_version` desync, and a `register` race condition surfaced
during manual review (concurrent duplicate signups raised a raw 500 instead
of 409 — now caught and translated).

## Next

Run `/review` before marking Phase 2 complete (per PHASES.md skill-routing checkpoints).
Then Phase 3 — Risk and Return Metrics.

**Phase 2 implementation summary:**
- `app/core/redis.py` — Redis singleton + `get_redis()` DI
- `app/services/market_data_service.py` — `MarketDataService` with `_cache_through()`,
  `get_historical_returns()`, `get_risk_free_rate()` (^TNX ÷ 100), `get_ticker_info()`,
  `get_quote()`, `search_tickers()`, `validate_tickers()`
- `app/schemas/market_data.py`, `app/api/v1/market_data.py` — 4 public endpoints
- `tests/test_market_data.py` — 19 unit tests + 2 smoke tests (INTEGRATION_TESTS=1)
- All gates: ruff clean, mypy clean, 39 tests passing

**T6 (^TNX live verification)** — still open, network-blocked. Formula confirmed as `/ 100`
via fallback cross-check and `test_rfr_decimal_conversion`. Verify when Yahoo Finance
is reachable from WSL2.

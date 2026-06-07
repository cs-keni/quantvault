# Current Task

**Phase 5 — Monte Carlo Simulation** ✅ complete (2026-06-07, review passed)

`/review` pass complete. 6 fixes applied:
1. Geometric → arithmetic annual return in `run_simulation` (`mean_daily_return * 252`)
2. Zero floor on portfolio values (`np.maximum(..., 0.0)`)
3. Error string truncation (`str(exc)[:2000]`)
4. Error-handler DB writes wrapped in try/except
5. Seed range constraint (`Field(ge=0, le=2_147_483_647)`)
6. NullPool for Celery DB bridge + prefork constraint comment

2 missing tests added: portfolio ownership 404, duplicate ticker 422.

Gates: 134 passed, 2 skipped, ruff clean, mypy clean.

## Current

**Phase 6 — Backtesting Engine** ✅ complete (2026-06-07, review passed)

`/review` pass complete. 3 fixes applied:
1. Status guard in `_write_result_to_db` — prevents duplicate task execution from overwriting settled results; also prevents SoftTimeLimitExceeded from downgrading SUCCESS→FAILURE.
2. Single-commit task dispatch — pre-generates `task_id` before `BacktestResult` creation, stored in the same commit, eliminating two-commit orphan window.
3. isfinite guard on `portfolio_equity` — raises descriptive ValueError before JSONB write fails cryptically on inf/nan values.

Financial math verified correct: CAGR formula, buy-and-hold, Calmar=None, yfinance end-exclusivity, symmetric data availability, Jensen alpha.

Gates: ruff clean, mypy clean. 7 deterministic math tests pass.

---

**Phase 4 — Efficient Frontier** ✅ complete (2026-06-07, review passed)

`/review` pass complete. 2 informational fixes applied:
1. Celery task cache-hit now catches deserialization errors (corrupt cache → re-fetch, not task FAILURE)
2. `FrontierPoint.annual_return` and `.sharpe_ratio` fields documented with arithmetic/geometric convention

Gates: 113 passed, 2 skipped, ruff clean, mypy clean.

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

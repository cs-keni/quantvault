# QuantVault — Deferred TODOs

Items considered during `/plan-eng-review` sessions that were explicitly deferred. Each entry has enough context for a future session to pick it up.

---

## TODO-7: Store `benchmark_ticker` in `BacktestResult`

**What:** Add `benchmark_ticker: Mapped[str] = mapped_column(String(16), nullable=False)` to `BacktestResult`, backfill existing rows from `portfolios.benchmark_ticker` via migration, and expose it in `BacktestStatusResponse`.

**Why:** `BacktestResult` currently stores `tearsheet.benchmark_cagr` and `tearsheet.benchmark_final_value` but not which ticker produced them. If `portfolio.benchmark_ticker` is changed after a backtest runs, the stored benchmark metrics become ambiguous — no way to know what they represent.

**Scope:** New Alembic migration, ORM model column, `run_backtest` params dict inclusion, `BacktestStatusResponse` schema field. Small — ~30 lines.

**Deferred:** Phase 6 /review pass (2026-06-07). Math correctness is not affected; this is a data completeness / audit trail concern.

---

## TODO-8: Migration Downgrade Safety for PENDING Rows

**What:** In `20260607_2330_7d8e9f012345_add_backtest_status_columns.py` `downgrade()`, `op.alter_column("backtest_results", "equity_curve", nullable=False)` will raise an `IntegrityError` if any rows have NULL `equity_curve` (all PENDING rows do).

**Why:** The downgrade path is not safe on a live DB with in-flight backtests.

**Fix:** Add a `DELETE FROM backtest_results WHERE status = 'PENDING'` before the nullable→NOT NULL `alter_column` calls in `downgrade()`, or add a comment documenting the limitation.

**Deferred:** Phase 6 /review pass (2026-06-07). No production traffic on this project; downgrade is unlikely to be executed. Acceptable for MVP.

---

## TODO-1: Cache Stampede Protection for Efficient Frontier

**What:** Add a Redis SETNX distributed lock (keyed on the frontier cache key) in `POST /analysis/frontier` to prevent two simultaneous identical requests from dispatching duplicate Celery tasks.

**Why:** Two concurrent POSTs for `(["SPY","BND"], "1y")` both miss the cache and both dispatch `compute_frontier`. They race to write the same result. Result: duplicate work, two wasted Celery worker slots, possible cache key collision from concurrent writes.

**Pros:** Eliminates duplicate Celery work; Redis SETNX with 5-minute expiry is simple and battle-tested.

**Cons:** Adds a lock acquisition step on every cache-miss POST; minor complexity.

**Context:** Accepted as-is during Phase 4 `/plan-eng-review` (2026-06-06). For a single-developer MVP, stampede probability is near zero. Becomes relevant at multi-user scale or during load testing. Implementation: `nx=True, ex=300` on `redis.set(lock_key)` before dispatching; check existing task_id from a task registry if lock already held.

**Depends on:** Phase 4 (Efficient Frontier) — need the frontier endpoint working first.

---

## TODO-2: Tikhonov Regularization for Near-Singular Covariance

**What:** Add a small diagonal term to the covariance matrix before optimization: `cov_regularized = cov + epsilon * np.eye(n)` where `epsilon=1e-8`.

**Why:** Highly correlated assets (e.g., VOO and SPY, both tracking S&P 500) produce near-singular covariance matrices. SLSQP can fail to converge, return suboptimal weights, or produce numerically unstable results even when duplicate-ticker validation passes. Tikhonov regularization stabilizes the matrix at negligible cost to accuracy.

**Pros:** Prevents spurious solver failures for correlated-but-distinct assets; mathematically well-understood; standard in MPT implementations.

**Cons:** Slightly biases the optimization toward equal-weight when correlations are near 1.0; epsilon must be tuned.

**Context:** Deferred from Phase 4 `/plan-eng-review` (2026-06-06). Current mitigation: infeasible target returns are skipped (partial frontier). Full regularization is hardening for post-MVP. Lives in `optimization_service.generate_efficient_frontier()`.

**Depends on:** Phase 4 (Efficient Frontier).

---

## TODO-3: Re-evaluate Celery for Phase 4 After Phases 5–6 Land

**What:** After Monte Carlo (Phase 5) and Backtesting (Phase 6) are implemented, benchmark Phase 4 frontier computation time and consider whether to simplify it to `asyncio.to_thread()` instead of Celery.

**Why:** Efficient frontier with warm starts takes ~1s. For a ~1s operation, Celery adds operational overhead (worker process, result backend, Redis result expiry) with limited benefit. Codex raised this in the outside-voice review. Celery is the right call for Phases 5–6 (Monte Carlo: ~5–30s; Backtest: ~10–60s depending on history length).

**Pros:** Simpler stack; no Celery worker required in Phase 8 deployment if frontier is the only async task.

**Cons:** Phases 5–6 already require Celery, so the worker is there regardless. Simplifying Phase 4 creates inconsistency in the async task pattern.

**Context:** Deferred from Phase 4 `/plan-eng-review` (2026-06-06). Decision: keep Celery for Phase 4 to maintain consistency. Re-evaluate after Phase 6 once you have real benchmark data for all three task types.

**Depends on:** Phase 5 + Phase 6 implementation complete.

---

## TODO-4: Orphan PENDING Simulation Cleanup

**What:** A periodic Celery beat task (every 5 minutes) that queries `SimulationResult WHERE status='PENDING' AND created_at < now() - interval '10 minutes'` and marks them `status='FAILURE', error='Dispatch timeout — Celery broker was unreachable at submission time'`.

**Why:** When `POST /simulation/monte-carlo` commits the `SimulationResult(PENDING)` row but Celery dispatch fails (Redis broker down), the row stays PENDING forever. Users see their simulation as "running" but it never completes. At MVP scale this is near-zero probability, but orphaned rows accumulate silently over time.

**Pros:** Prevents user confusion from simulations stuck in PENDING; simple Celery beat task with a clear threshold.
**Cons:** Adds a periodic task; introduces a hardcoded orphan threshold (10 minutes) that may need tuning.

**Context:** Accepted as best-effort for Phase 5 (`/plan-eng-review` 2026-06-07, D9 decision). The failure mode is visible (user can re-submit) but sticky. Implementation: Celery beat schedule + a `cleanup_orphaned_simulations` task in `simulation_service.py`.

**Depends on:** Phase 5 (SimulationResult model) complete.

---

## TODO-5: Vectorized Fast-Path for Zero-Contribution Monte Carlo

**What:** When `annual_contribution == 0`, replace the Python for-loop over `trading_days` with a single vectorized call: `portfolio_values = initial_investment * np.cumprod(1 + returns_matrix, axis=0)`.

**Why:** The current loop does 252–7560 Python-level iterations (each triggering a NumPy vector multiply). The zero-contribution case can be expressed as a single `np.cumprod()` call, eliminating Python overhead for the common case.

**Pros:** ~10x faster for zero-contribution simulations; no change to output values.
**Cons:** Two code paths for essentially the same logic; adds an `if annual_contribution == 0` branch.

**Context:** Current loop performance is ~15–40ms for maximum parameters (1000 simulations, 30 years), which is well within the 55s Celery soft time limit. Optimization is quality improvement, not a fix. Deferred from Phase 5 `/plan-eng-review` (2026-06-07).

**Depends on:** Phase 5 complete.

---

## TODO-9: Cross-Tab Token Refresh Coordination via BroadcastChannel

**What:** When the user has two browser tabs open, both on an expired token, both simultaneously hit 401 and attempt a refresh. The in-tab deduplicated refresh lock (D4) handles concurrent requests within one tab, but two independent tabs each have their own lock and each call `/auth/refresh`. Depending on the backend's token rotation policy, the second tab's refresh may fail (rotation invalidates first refresh token). Fix: `BroadcastChannel('qv:auth')` — the tab that wins the race posts `{ type: 'token_refreshed', accessToken }` to the channel; losing tabs receive it and update their in-memory access token without re-hitting the backend.

**Why:** Refresh token rotation (future security hardening) makes dual-tab refresh non-idempotent. One tab will fail silently and log the user out unexpectedly.

**Scope:** ~40 lines in `src/store/authStore.ts`: subscribe to BroadcastChannel on mount, broadcast on successful refresh. Needs `TODOS.md` reminder to add rotation to backend when this is implemented.

**Deferred:** Phase 7 /plan-eng-review (2026-06-07). Backend currently does NOT rotate refresh tokens — risk is zero today. Implement when/if rotation is added.

---

## TODO-10: OpenAPI TypeScript Type Generation

**What:** Use `openapi-typescript` to generate TypeScript types from FastAPI's `/api/v1/openapi.json`. Run as a build step: `npx openapi-typescript /api/v1/openapi.json -o src/types/api.d.ts`. Replaces hand-written types in `src/types/`.

**Why:** FastAPI's Pydantic `Decimal` fields (`HoldingOut.target_weight`, `BacktestRequest.initial_investment`) may serialize to JSON as strings (e.g. `"0.6"` not `0.6`) depending on serialization config. Hand-written types that declare these as `number` will TypeScript-pass but runtime-fail when the actual value is `"0.6"`. OpenAPI generation catches this automatically.

**Scope:** Add `openapi-typescript` as devDependency. Add npm script `"gen:types": "openapi-typescript ..."`. Delete `src/types/` hand-written files.

**Deferred:** Phase 7 /plan-eng-review (2026-06-07). Verify Decimal serialization behavior during Phase 7 implementation — FastAPI v0.100+ with Pydantic v2 serializes `Decimal` as `float` by default when using `model_dump(mode='json')`. If fields are numbers in practice, hand-written types are fine. If strings, switch to openapi-typescript as the fix.

**Depends on:** Phase 7 scaffolded, backend running locally so openapi.json is accessible.

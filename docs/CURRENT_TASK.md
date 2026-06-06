# Current Task

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

Phase 2 — Market Data Service. **Architecture locked** — all design decisions in `PHASES.md` decisions 15–27, `HANDOFF.md`, and `AI_CONTEXT.md`. Ready to implement T1–T6. First action: verify `^TNX` raw value in dev shell before writing any risk-free-rate code.

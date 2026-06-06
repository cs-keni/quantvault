# Handoff — QuantVault

What the next agent (Claude Code or Codex) needs to pick up cleanly. Update
this whenever architecture, component ownership, or cross-cutting systems
change — not for routine task completion (that's `CURRENT_TASK.md` /
`ENGINEERING_LOG.md`).

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

Phase 2 — Market Data Service. **Architecture locked 2026-06-06 via `/plan-eng-review`
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

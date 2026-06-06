# Engineering Log

Reverse-chronological. One entry per session/slice — what changed and why,
not a diff (git history is authoritative for that).

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

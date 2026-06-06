# Handoff — QuantVault

What the next agent (Claude Code or Codex) needs to pick up cleanly. Update
this whenever architecture, component ownership, or cross-cutting systems
change — not for routine task completion (that's `CURRENT_TASK.md` /
`ENGINEERING_LOG.md`).

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
- **`^TNX`** is quoted by Yahoo as yield × 10 (e.g. `4.2` means 4.2%, not
  42%) — divide by 10, fall back to `0.04` on fetch failure.
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
- **venv note**: this WSL box can't `apt install python3.12-venv` (needs sudo
  password), so `backend/.venv` was created with `virtualenv` instead of the
  stdlib `venv` module. Functionally identical — and once
  `requirements-dev.txt` finished installing, normal `bin/` console-script
  shims (`pip`, `pytest`, `ruff`, `mypy`, `alembic`, `celery`, ...) were all
  present as expected.

## Next up

Phase 1 — Domain, Database, and Auth: SQLAlchemy models (`User`, `Portfolio`,
`Holding`, `BacktestResult`), Alembic initial migration,
`portfolio_to_weights()`, JWT auth endpoints + `app/dependencies.py`
(`get_current_user`), auth tests, and the seed script (demo user + VTI 60% /
BND 30% / VXUS 10% portfolio). Run `/review` before marking Phase 1 complete.

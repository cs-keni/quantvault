# AI Context — QuantVault

Living reference for any agent (Claude Code or Codex) picking up this repo.
Read this before writing code; update it whenever the stack, data format, or
a key implementation decision changes.

## What this is

A quantitative portfolio analytics platform: real Yahoo Finance market data,
Markowitz efficient frontier optimization, Monte Carlo simulation, VaR/CVaR/
Sharpe/Sortino/Beta risk metrics, and a backtesting engine with tearsheets.
Built as a portfolio signal piece for investment-management employers — see
`quantvault.md` for the full canonical spec and `PHASES.md` for the phase plan.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic |
| Auth | PyJWT + Passlib(bcrypt) — **not** python-jose (active CVEs) |
| Async tasks | Celery + Redis (efficient frontier, Monte Carlo, backtest — CPU-bound, must not block the event loop) |
| Math | NumPy, Pandas, SciPy (`scipy.optimize.minimize`) |
| Market data | yfinance, Redis-cached (24h historical / 15m quotes / 7d metadata) |
| Frontend | React 18 + TypeScript + Vite, Tailwind CSS, Recharts, Zustand, TanStack Query |
| Infra | PostgreSQL 16, Redis 7, Docker Compose (5 services: backend, frontend, db, redis, celery-worker) |

## Repo layout

```
backend/app/
  main.py            — FastAPI app factory (create_app); routers register here per phase
  celery_app.py      — Celery app (broker=backend=Redis); task modules added per phase
  core/              — config (pydantic-settings), database (async engine/session), security (JWT/bcrypt)
  models/            — SQLAlchemy ORM models, re-exported from __init__.py for Alembic autogenerate
  schemas/           — Pydantic request/response schemas
  api/v1/            — versioned routers (auth, portfolios, analysis, simulation, backtest, market_data)
  services/          — all financial math + business logic (never inline in routes)
backend/alembic/     — async-aware migrations; env.py reads DATABASE_URL from settings
backend/tests/       — pytest + pytest-asyncio; conftest provides db_session + httpx client fixtures
frontend/src/        — pages, components/{charts,portfolio}, services (API client), store (Zustand), types
```

## Key implementation decisions (locked via /plan-eng-review, 2026-06-05)

These override the spec where they conflict — see `CLAUDE.md` and `PHASES.md`
for the full list with rationale. The ones that change *how code is written*:

- **VaR annual = rolling 252-day window**, not `daily_var * sqrt(252)` (that
  scaling is only valid for parametric/normal VaR; this project uses historical
  simulation).
- **Monte Carlo**: `np.random.standard_t(df=5)` scaled to `daily_sigma` — fat
  tails are the point; contributions inject at year boundary and compound
  forward (the spec's `cumprod` add-to-all approach was financially wrong).
- **CVaR guard**: `var_index = max(int((1 - confidence) * N), 1)` prevents an
  empty-slice → NaN on small samples or high confidence levels.
- **Efficient frontier**: solve min-variance first, use *its* return as the
  lower target bound for the frontier sweep — `min(individual returns)`
  produces infeasible solver targets.
- **`portfolio_to_weights(holdings) -> tuple[list[str], np.ndarray]`** is the
  single Decimal→float conversion point, centralized in `portfolio_service.py`.
- **`User.default_portfolio_id` FK**, not `Portfolio.is_default bool` — avoids
  a multi-row uniqueness constraint.

## Data format conventions

- All financial calculations live in `app/services/*_service.py` — never
  inline in routes — and every calculation function carries a docstring
  explaining the formula and its financial interpretation (non-negotiable,
  see `CLAUDE.md`).
- Market data is **never** persisted to Postgres; it's fetched from yfinance
  on demand and cached in Redis by TTL (see table above). `BacktestResult`
  *is* persisted, with `tearsheet`/`daily_returns`/`equity_curve` as JSONB.
- `^TNX` (10-year Treasury yield, used as the risk-free rate) is quoted by
  Yahoo as yield × 10 — divide by 10 before use; fall back to `0.04` if the
  fetch fails.
- Test fixtures with hand-computable expected values live in
  `tests/fixtures/known_values.py` (Phase 3 prerequisite — lock these *before*
  implementing any financial function).

## Design tokens (locked)

bg `#ffffff` · surface `#f8fafc` · accent (indigo) `#6366f1` · positive
(emerald) `#10b981` · negative (red) `#ef4444` · text `#0f172a` · font Inter
(JetBrains Mono for numeric displays) · charts via Recharts on a clean SVG /
light-grid style.

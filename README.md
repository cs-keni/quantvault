# QuantVault

[![CI](https://github.com/cs-keni/quantvault/actions/workflows/ci.yml/badge.svg)](https://github.com/cs-keni/quantvault/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688)
![React](https://img.shields.io/badge/React-18-61dafb)

QuantVault is a portfolio analytics and risk modeling platform built to
demonstrate quant finance engineering depth for investment-management roles.
It combines production-style web architecture with financial math that is
specific enough to be evaluated: Markowitz efficient frontier optimization,
historical VaR/CVaR, fat-tailed Monte Carlo simulation, and backtesting against
real Yahoo Finance market data.

The project narrative is direct: an investor should be able to understand the
risk exposure, downside behavior, and allocation tradeoffs of a portfolio
instead of only seeing a static brokerage balance. QuantVault turns holdings
into measurable risk and return profiles, then exposes the assumptions in code.

## Architecture

```
                 browser
                   |
                   v
        React + TypeScript + Vite
                   |
          nginx /api/ proxy
                   |
                   v
              FastAPI API
              /api/v1/*
          /       |        \
         v        v         v
 PostgreSQL 16  Redis 7   Celery worker
 portfolios,   market     efficient frontier,
 users, task   data +     Monte Carlo,
 results       task cache backtest tasks
```

The frontend uses React, TanStack Query, Zustand, Tailwind CSS, and Recharts.
The backend uses FastAPI, SQLAlchemy 2.0 async sessions, Alembic migrations,
PyJWT authentication, Redis caching, and Celery for CPU-bound analytics tasks.
Market data is fetched from Yahoo Finance with yfinance and cached in Redis;
raw market prices are not persisted in Postgres.

## Financial Concepts

### Modern Portfolio Theory

QuantVault computes portfolio-level expected return, volatility, Sharpe ratio,
and covariance from historical daily returns. The efficient frontier uses
Markowitz optimization to find allocations with the lowest volatility for a
given target return and to identify the max-Sharpe portfolio under long-only
weight constraints.

### Historical VaR and CVaR

Value at Risk is calculated with historical simulation. QuantVault uses the
empirical distribution of weighted portfolio returns rather than assuming a
normal distribution. Annual VaR is based on a rolling 252-trading-day window,
not `daily_var * sqrt(252)`. CVaR averages the tail losses beyond VaR and
guards against empty tail slices on small samples.

### Student-t Monte Carlo

The Monte Carlo engine is not geometric Brownian motion. It draws from a
Student-t distribution with 5 degrees of freedom and scales those fat-tailed
shocks by observed daily volatility. This makes the simulation more explicit
about tail risk than a normal-return GBM shortcut. Contributions are injected
at year boundaries and compound forward.

## Features

- Portfolio builder with target weights and asset-class validation.
- Risk dashboard with Sharpe, Sortino, VaR, CVaR, beta, max drawdown, and
  return distribution.
- Efficient frontier analysis with cache-aware Celery polling.
- Monte Carlo simulation with persisted task status and percentile paths.
- Backtesting with CAGR, drawdown, alpha, benchmark comparison, and equity
  curve output.
- Portfolio comparison across side-by-side risk metrics.

## Local Development

Copy the example environment and start the stack:

```bash
cp .env.example .env
docker compose up --build
```

The frontend is available at `http://localhost:3000`; the backend health check
is `http://localhost:8000/health`.

For backend-only development:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

For frontend-only development:

```bash
cd frontend
npm ci
npm run dev
```

## Checks

Backend:

```bash
cd backend
.venv/bin/ruff check app
.venv/bin/mypy app
.venv/bin/pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npm test
npm run build
```

Docker:

```bash
docker compose build
```

## Screenshots

Screenshots are intentionally deferred until the Phase 8 UI overhaul is
complete. The demo portfolio for screenshots is VTI 60%, BND 30%, VXUS 10%.

# QuantVault — AI Agent Brief

> Read this entirely before writing a single line of code.
> This is the canonical project brief for QuantVault. All planning, architecture, and implementation decisions live here and in the docs/ folder once set up.

---

## Why This Project Exists

Kenny Nguyen (GitHub: cs-keni) is a CS grad from University of Oregon (2025). While CivicFlow targets government/public sector and LedgerBridge targets banking/enterprise, QuantVault targets a different and often higher-paying segment: **investment management firms, asset managers, and quantitative fintech**.

Target employers: Vanguard, BlackRock, Fidelity, T. Rowe Price, PIMCO, Morgan Stanley wealth tech, Charles Schwab, investment arms of banks (Wells Fargo Investment Institute, Citi Wealth), and quantitative-adjacent startups in Portland/Oregon and remote.

Why this project is different from LedgerBridge: these employers want **quantitative thinking** on top of software engineering. The ability to implement real financial math (portfolio optimization, risk analytics, backtesting) and explain it clearly is rare at the new-grad level and immediately differentiating.

**Personal connection**: Kenny has a Vanguard account with index fund holdings. The project's narrative is authentic — "I wanted to understand what my portfolio's actual risk exposure and optimal allocation looked like, so I built the tools to calculate it."

Stack synergy: Python is already in Kenny's portfolio (MemLock, Syllabify). FastAPI and React+TypeScript are familiar territory. QuantVault adds financial math depth without a full language-learning curve.

---

## Project Overview

**QuantVault** is a portfolio analytics and risk modeling platform for individual investors and wealth management professionals. Users build multi-asset portfolios from real market data, analyze risk/return profiles, visualize the efficient frontier, run Monte Carlo simulations for forward projection, and backtest portfolio strategies against historical data.

The platform uses **Yahoo Finance (yfinance)** for real historical market data at zero cost. This means the app works with real S&P 500 tickers, real historical returns, and real correlations — not fake mock data. This is a major credibility signal for the target employers.

### What QuantVault Does
1. **Portfolio Builder** — add tickers and allocations, see real-time return/risk metrics
2. **Efficient Frontier** — visualize the Markowitz efficient frontier for a given set of assets
3. **Risk Analytics** — VaR, CVaR, Sharpe, Sortino, Beta, Maximum Drawdown, per-asset attribution
4. **Monte Carlo Simulation** — forward project portfolio value over N years across M simulated paths
5. **Backtesting Engine** — simulate a strategy against historical data, generate a full performance tearsheet
6. **Portfolio Comparison** — side-by-side comparison of portfolios or against benchmark (S&P 500)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web Framework | FastAPI |
| Financial Data | yfinance (Yahoo Finance, free, no API key) |
| Numerical Computing | NumPy, Pandas |
| Portfolio Optimization | SciPy (scipy.optimize for efficient frontier) |
| Statistical Analysis | statsmodels (for regression, beta calculation) |
| Database | PostgreSQL (via SQLAlchemy + asyncpg) |
| Migrations | Alembic |
| Auth | JWT (python-jose) + Passlib (bcrypt) |
| Caching | Redis (cache market data to avoid re-fetching yfinance) |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Charts | Recharts (time series, scatter plots for frontier) |
| State Management | Zustand |
| HTTP Client | Axios + React Query (TanStack Query) |
| API Docs | FastAPI auto-generates OpenAPI/Swagger UI |
| Testing | pytest, httpx (async API tests), pytest-asyncio |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Optional | Celery + Redis for async data fetch tasks |

---

## Architecture

### Solution Structure

```
quantvault/
├── backend/
│   ├── app/
│   │   ├── main.py                      — FastAPI app factory, router registration
│   │   ├── core/
│   │   │   ├── config.py                — Settings (pydantic-settings, env vars)
│   │   │   ├── security.py              — JWT, password hashing
│   │   │   └── database.py              — SQLAlchemy async engine + session
│   │   ├── models/                      — SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── portfolio.py
│   │   │   ├── holding.py
│   │   │   └── backtest_result.py
│   │   ├── schemas/                     — Pydantic request/response schemas
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py              — /auth/register, /auth/login
│   │   │   │   ├── portfolios.py        — portfolio CRUD
│   │   │   │   ├── analysis.py          — efficient frontier, risk metrics
│   │   │   │   ├── simulation.py        — Monte Carlo
│   │   │   │   ├── backtest.py          — backtesting engine
│   │   │   │   └── market_data.py       — ticker search, price history
│   │   ├── services/
│   │   │   ├── market_data_service.py   — yfinance wrapper with Redis caching
│   │   │   ├── portfolio_service.py     — portfolio CRUD + metrics
│   │   │   ├── optimization_service.py  — efficient frontier, Markowitz MPT
│   │   │   ├── risk_service.py          — VaR, CVaR, Sharpe, Sortino, Beta, drawdown
│   │   │   ├── simulation_service.py    — Monte Carlo simulation
│   │   │   └── backtest_service.py      — backtesting engine
│   │   └── dependencies.py             — FastAPI dependency injection
│   ├── alembic/                         — database migrations
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   │   ├── charts/                  — EfficientFrontierChart, MonteCarloChart, etc.
│   │   │   └── portfolio/               — PortfolioBuilder, HoldingRow, MetricsCard
│   │   ├── services/                    — API client
│   │   ├── store/                       — Zustand state
│   │   └── types/
│   └── package.json
├── docker-compose.yml
└── .env.example
```

---

## Domain Model

### Database Entities

```python
# models/user.py
class User(Base):
    id: UUID
    email: str (unique)
    hashed_password: str
    full_name: str
    created_at: datetime
    is_active: bool

# models/portfolio.py
class Portfolio(Base):
    id: UUID
    user_id: UUID (FK → User)
    name: str
    description: str
    benchmark_ticker: str  # default "SPY" (S&P 500 ETF)
    created_at: datetime
    updated_at: datetime
    is_default: bool

# models/holding.py
class Holding(Base):
    id: UUID
    portfolio_id: UUID (FK → Portfolio)
    ticker: str           # e.g., "AAPL", "VTI", "BND"
    asset_name: str       # human-readable name
    asset_class: str      # EQUITY, FIXED_INCOME, REAL_ESTATE, COMMODITY, CASH
    target_weight: Decimal  # 0.0 - 1.0, must sum to 1.0 across portfolio
    current_shares: Decimal  # optional: actual shares held
    notes: str

# models/backtest_result.py
class BacktestResult(Base):
    id: UUID
    portfolio_id: UUID
    strategy_name: str
    start_date: date
    end_date: date
    rebalance_frequency: str  # MONTHLY, QUARTERLY, ANNUALLY, NEVER
    initial_investment: Decimal
    # Results (stored as JSON for flexibility)
    tearsheet: dict  # full performance report
    daily_returns: list[float]
    equity_curve: list[dict]  # [{date, value}]
    created_at: datetime
```

### Market Data (NOT stored in DB — fetched and cached)

Market price data is not stored in PostgreSQL. It is:
1. Fetched on-demand from Yahoo Finance via yfinance
2. Cached in Redis with a TTL based on data type:
   - Historical daily prices: TTL 24 hours (changes once per trading day)
   - Real-time quotes: TTL 15 minutes
   - Company metadata (name, sector, exchange): TTL 7 days

This caching architecture is important to document — it's a real production pattern and avoids hammering the data source.

---

## Financial Math — The Core Differentiator

This section describes the actual algorithms. The quality of these implementations is what makes QuantVault stand out to quantitative finance employers.

### 1. Portfolio Return and Risk

```python
# portfolio_service.py

def calculate_portfolio_metrics(weights: np.ndarray, returns_df: pd.DataFrame) -> dict:
    """
    weights: array of portfolio weights, must sum to 1.0
    returns_df: DataFrame of daily log returns per ticker, shape (trading_days, n_assets)
    """
    # Expected annualized return (252 trading days per year)
    mean_daily_returns = returns_df.mean()
    portfolio_return = np.dot(weights, mean_daily_returns) * 252

    # Annualized portfolio volatility (std dev of returns)
    cov_matrix = returns_df.cov() * 252
    portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
    portfolio_volatility = np.sqrt(portfolio_variance)

    # Sharpe ratio (using 10-year Treasury yield as risk-free rate, fetched from ^TNX)
    risk_free_rate = get_risk_free_rate()  # fetch from yfinance "^TNX"
    sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility

    return {
        "annualized_return": portfolio_return,
        "annualized_volatility": portfolio_volatility,
        "sharpe_ratio": sharpe_ratio,
        "covariance_matrix": cov_matrix.to_dict()
    }
```

### 2. Markowitz Efficient Frontier

```python
# optimization_service.py
from scipy.optimize import minimize

def generate_efficient_frontier(tickers: list[str], n_points: int = 100) -> dict:
    """
    Generate the efficient frontier by solving the Markowitz mean-variance optimization
    for a range of target return levels.
    Returns: list of {return, volatility, weights} for each frontier point.
    """
    returns_df = fetch_historical_returns(tickers, period="5y")  # 5 years of data
    mean_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    n_assets = len(tickers)

    # Target returns: range from min possible to max possible
    min_return = mean_returns.min()
    max_return = mean_returns.max()
    target_returns = np.linspace(min_return, max_return, n_points)

    frontier_points = []
    for target in target_returns:
        # Optimization: minimize portfolio variance subject to:
        # 1. Portfolio return == target
        # 2. Weights sum to 1
        # 3. No short selling: weights >= 0 (long-only constraint)
        result = minimize(
            fun=lambda w: np.dot(w.T, np.dot(cov_matrix, w)),  # minimize variance
            x0=np.ones(n_assets) / n_assets,  # equal weight starting point
            method='SLSQP',
            bounds=[(0, 1)] * n_assets,  # no short selling
            constraints=[
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # weights sum to 1
                {'type': 'eq', 'fun': lambda w: np.dot(w, mean_returns) - target}  # target return
            ]
        )
        if result.success:
            volatility = np.sqrt(result.fun)
            frontier_points.append({
                "return": float(target),
                "volatility": float(volatility),
                "sharpe": float((target - risk_free_rate) / volatility),
                "weights": {tickers[i]: float(result.x[i]) for i in range(n_assets)}
            })

    # Also find: minimum variance portfolio and maximum Sharpe portfolio
    # Return as special labeled points on the frontier
    return {
        "frontier": frontier_points,
        "min_variance_portfolio": find_min_variance_portfolio(tickers, mean_returns, cov_matrix),
        "max_sharpe_portfolio": find_max_sharpe_portfolio(tickers, mean_returns, cov_matrix, risk_free_rate),
        "tickers": tickers,
        "period": "5y"
    }
```

### 3. Value at Risk (VaR) and Conditional VaR (CVaR)

```python
# risk_service.py

def calculate_var_cvar(portfolio_daily_returns: pd.Series, confidence_level: float = 0.95) -> dict:
    """
    VaR (Historical Simulation Method):
    Sort historical daily returns, take the (1-confidence_level) percentile.
    "With 95% confidence, we will not lose more than X% in a single day."

    CVaR (Expected Shortfall):
    The mean return on the days that were worse than VaR.
    A better measure of tail risk than VaR alone.
    """
    sorted_returns = np.sort(portfolio_daily_returns)
    var_index = int((1 - confidence_level) * len(sorted_returns))
    var_daily = sorted_returns[var_index]  # negative number

    # CVaR: mean of all returns worse than VaR
    cvar_daily = sorted_returns[:var_index].mean()

    # Annualize (scale by sqrt of trading days — standard approximation)
    var_annual = var_daily * np.sqrt(252)
    cvar_annual = cvar_daily * np.sqrt(252)

    return {
        "var_daily": float(var_daily),          # e.g., -0.023 means 2.3% daily loss at 95% CI
        "var_annual": float(var_annual),
        "cvar_daily": float(cvar_daily),         # expected loss beyond VaR threshold
        "cvar_annual": float(cvar_annual),
        "confidence_level": confidence_level
    }

def calculate_max_drawdown(equity_curve: pd.Series) -> dict:
    """
    Maximum Drawdown: the largest peak-to-trough decline over a period.
    """
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    max_drawdown_date = drawdown.idxmin()

    return {
        "max_drawdown": float(max_drawdown),     # e.g., -0.34 means 34% max drawdown
        "max_drawdown_date": str(max_drawdown_date),
        "drawdown_series": drawdown.to_dict()    # for visualization
    }

def calculate_beta(portfolio_returns: pd.Series, benchmark_ticker: str = "SPY") -> float:
    """
    Beta: sensitivity of portfolio returns to market (benchmark) returns.
    beta = cov(portfolio, benchmark) / var(benchmark)
    beta > 1: more volatile than market
    beta < 1: less volatile
    beta = 1: moves with market
    """
    benchmark_returns = fetch_historical_returns([benchmark_ticker]).iloc[:, 0]
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    cov = aligned.cov().iloc[0, 1]
    var_benchmark = aligned.iloc[:, 1].var()
    return float(cov / var_benchmark)
```

### 4. Monte Carlo Simulation

```python
# simulation_service.py

def run_monte_carlo(
    portfolio_metrics: dict,
    initial_investment: float,
    years: int,
    n_simulations: int = 1000,
    annual_contribution: float = 0.0
) -> dict:
    """
    Simulate N paths of daily portfolio returns using a geometric Brownian motion model.
    Parameters: expected annual return, annual volatility (from portfolio_metrics).

    This gives a distribution of possible portfolio values at each future date,
    answering questions like:
    - What is the probability the portfolio doubles in 10 years?
    - What is the 10th percentile outcome at retirement?
    - What is the range of outcomes across simulations?
    """
    mu = portfolio_metrics["annualized_return"]        # expected annual return
    sigma = portfolio_metrics["annualized_volatility"]  # annual volatility
    trading_days = years * 252

    # Daily drift and volatility
    daily_mu = mu / 252
    daily_sigma = sigma / np.sqrt(252)

    # Simulate: shape (trading_days, n_simulations)
    random_returns = np.random.normal(
        loc=daily_mu,
        scale=daily_sigma,
        size=(trading_days, n_simulations)
    )

    # Build price paths using cumulative product
    price_paths = initial_investment * np.cumprod(1 + random_returns, axis=0)

    # Add annual contributions (injected at start of each year)
    if annual_contribution > 0:
        for year in range(1, years):
            price_paths[year * 252:] += annual_contribution

    final_values = price_paths[-1, :]

    # Percentile outcomes
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    percentile_values = np.percentile(final_values, percentiles)

    # Sample paths for visualization (show 20 representative paths)
    sample_paths_idx = np.random.choice(n_simulations, 20, replace=False)
    sample_paths = price_paths[:, sample_paths_idx].T.tolist()

    return {
        "initial_investment": initial_investment,
        "years": years,
        "n_simulations": n_simulations,
        "annual_contribution": annual_contribution,
        "percentile_outcomes": dict(zip(percentiles, percentile_values.tolist())),
        "mean_final_value": float(final_values.mean()),
        "probability_of_profit": float((final_values > initial_investment).mean()),
        "probability_of_doubling": float((final_values > initial_investment * 2).mean()),
        "sample_paths": sample_paths,      # 20 paths for visualization
        "final_value_distribution": np.percentile(final_values, range(1, 100)).tolist()
    }
```

### 5. Backtesting Engine

```python
# backtest_service.py

def run_backtest(
    tickers: list[str],
    weights: list[float],  # target allocations
    start_date: str,        # e.g., "2018-01-01"
    end_date: str,
    initial_investment: float,
    rebalance_frequency: str,  # "monthly", "quarterly", "annually", "never"
    benchmark_ticker: str = "SPY"
) -> dict:
    """
    Simulate holding a rebalanced portfolio over historical data.
    Compares portfolio performance against benchmark.
    """
    # Fetch historical prices for all tickers + benchmark
    price_data = fetch_historical_prices(tickers + [benchmark_ticker], start_date, end_date)

    # Build equity curve with periodic rebalancing
    portfolio_value = initial_investment
    equity_curve = []
    last_rebalance_date = None

    for date, prices in price_data.iterrows():
        # Check if rebalance is needed
        if should_rebalance(date, last_rebalance_date, rebalance_frequency):
            # Rebalance: buy/sell to restore target weights
            current_allocation = rebalance_portfolio(portfolio_value, weights, prices[tickers])
            last_rebalance_date = date

        # Update portfolio value based on price changes
        portfolio_value = calculate_portfolio_value(current_allocation, prices[tickers])
        benchmark_value = calculate_single_asset_value(initial_investment, prices[benchmark_ticker], price_data[benchmark_ticker].iloc[0])

        equity_curve.append({
            "date": str(date.date()),
            "portfolio_value": portfolio_value,
            "benchmark_value": benchmark_value
        })

    # Generate performance tearsheet
    daily_returns = pd.Series([r["portfolio_value"] for r in equity_curve]).pct_change().dropna()
    benchmark_returns = pd.Series([r["benchmark_value"] for r in equity_curve]).pct_change().dropna()

    return {
        "equity_curve": equity_curve,
        "total_return": (portfolio_value - initial_investment) / initial_investment,
        "benchmark_total_return": (equity_curve[-1]["benchmark_value"] - initial_investment) / initial_investment,
        "annualized_return": calculate_cagr(initial_investment, portfolio_value, start_date, end_date),
        "annualized_volatility": daily_returns.std() * np.sqrt(252),
        "sharpe_ratio": calculate_sharpe(daily_returns),
        "sortino_ratio": calculate_sortino(daily_returns),
        "max_drawdown": calculate_max_drawdown(pd.Series([r["portfolio_value"] for r in equity_curve]))["max_drawdown"],
        "beta": calculate_beta(daily_returns, benchmark_returns),
        "alpha": calculate_alpha(daily_returns, benchmark_returns),
        "calmar_ratio": calculate_cagr(...) / abs(max_drawdown),
        "win_rate": (daily_returns > 0).mean(),
        "rebalance_count": count_rebalances(equity_curve, rebalance_frequency)
    }
```

---

## API Endpoints

```
Auth:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh

Portfolio:
  GET    /api/v1/portfolios                     — list my portfolios
  POST   /api/v1/portfolios                     — create portfolio
  GET    /api/v1/portfolios/{id}                — portfolio detail + current metrics
  PUT    /api/v1/portfolios/{id}                — update portfolio
  DELETE /api/v1/portfolios/{id}
  POST   /api/v1/portfolios/{id}/holdings       — add holding
  PUT    /api/v1/portfolios/{id}/holdings/{hid} — update holding weight
  DELETE /api/v1/portfolios/{id}/holdings/{hid}

Analysis:
  POST /api/v1/analysis/metrics                 — compute risk/return metrics for a portfolio
  POST /api/v1/analysis/efficient-frontier      — generate efficient frontier for a ticker set
  POST /api/v1/analysis/correlation-matrix      — return correlation heatmap data
  POST /api/v1/analysis/var-cvar                — compute VaR and CVaR

Simulation:
  POST /api/v1/simulation/monte-carlo           — run Monte Carlo simulation
  GET  /api/v1/simulation/{id}                  — retrieve saved simulation result

Backtest:
  POST /api/v1/backtest/run                     — run backtest
  GET  /api/v1/backtest/{id}                    — retrieve saved backtest result
  GET  /api/v1/portfolios/{id}/backtests        — list backtests for portfolio

Market Data:
  GET  /api/v1/market/search?q=apple            — ticker search
  GET  /api/v1/market/{ticker}/history          — historical price data
  GET  /api/v1/market/{ticker}/info             — company metadata
```

---

## Frontend Pages

```
/login
/register
/dashboard                      — portfolio overview: value, performance, top movers
/portfolios                     — all portfolios list
/portfolios/new                 — portfolio builder wizard
/portfolios/:id                 — portfolio detail
/portfolios/:id/analysis        — efficient frontier, risk metrics, correlation matrix
/portfolios/:id/simulate        — Monte Carlo simulation controls + visualization
/portfolios/:id/backtest        — backtest configuration + tearsheet results
/compare                        — side-by-side portfolio comparison
```

### Key Visualizations (Recharts)
- **Efficient Frontier Chart** — scatter plot: x=volatility, y=return. Frontier curve, current portfolio point, min-variance star, max-Sharpe star. Hover shows weights.
- **Monte Carlo Chart** — 20 sampled equity curves (light gray), P5/P25/P50/P75/P95 percentile bands, initial investment reference line
- **Drawdown Chart** — area chart showing drawdown over time (negative values below 0 line)
- **Equity Curve Chart** — portfolio vs. benchmark over backtest period
- **Correlation Heatmap** — grid of ticker pairs, colored by correlation coefficient (-1 red to +1 blue)
- **Risk Attribution Pie** — per-asset contribution to total portfolio volatility
- **Return Distribution Histogram** — histogram of daily returns with normal distribution overlay

---

## Market Data Caching Architecture

```python
# market_data_service.py

class MarketDataService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get_historical_returns(self, tickers: list[str], period: str = "5y") -> pd.DataFrame:
        cache_key = f"returns:{':'.join(sorted(tickers))}:{period}"
        cached = await self.redis.get(cache_key)
        if cached:
            return pd.read_json(cached)

        # Fetch from Yahoo Finance
        raw = yf.download(tickers, period=period, interval="1d", progress=False)
        prices = raw["Adj Close"] if len(tickers) > 1 else raw["Adj Close"].to_frame(tickers[0])
        returns = prices.pct_change().dropna()

        # Cache for 24 hours (data only changes once per trading day)
        await self.redis.setex(cache_key, 86400, returns.to_json())
        return returns
```

This caching layer is documented in the README as a production architecture pattern — it's not just an optimization, it's the right design for any system consuming external market data APIs.

---

## Security

- JWT-based stateless authentication
- Passwords hashed with bcrypt (passlib)
- All endpoints require authentication except ticker search and market data preview
- Input validation via Pydantic schemas on all request models
- No real financial accounts are connected — all data is historical from Yahoo Finance
- Clear disclaimer in UI and README: "This is for educational and portfolio demonstration purposes only. Not financial advice."
- CORS configured to explicit allowed origins
- Secrets via environment variables

---

## DevOps

### Docker Compose

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://qv:${DB_PASSWORD}@db/quantvault
      - REDIS_URL=redis://redis:6379
      - SECRET_KEY=${SECRET_KEY}
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    ports: ["3000:80"]

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=quantvault
      - POSTGRES_USER=qv
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### GitHub Actions CI

```yaml
# Steps:
# 1. Install Python 3.12, run pytest
# 2. Check ruff linting, mypy type checking
# 3. Install Node.js, run frontend tests
# 4. Build Docker images
# 5. Run integration tests (httpx against running API)
```

---

## Phases

### Phase 0 — Setup
- [ ] Create GitHub repo `quantvault`
- [ ] Initialize FastAPI project structure
- [ ] Set up PostgreSQL + Redis with Docker Compose
- [ ] Configure Alembic for migrations
- [ ] Set up pytest + ruff + mypy
- [ ] Create docs/: AI_CONTEXT.md, HANDOFF.md, ENGINEERING_LOG.md, CURRENT_TASK.md
- [ ] Run `/plan-eng-review` before proceeding to Phase 1

### Phase 1 — Domain + Database + Auth
- [ ] Define SQLAlchemy models (User, Portfolio, Holding, BacktestResult)
- [ ] Write Alembic initial migration
- [ ] Implement JWT auth: register, login, refresh
- [ ] Write unit tests for auth flows

### Phase 2 — Market Data Service
- [ ] Implement MarketDataService (yfinance wrapper)
- [ ] Implement Redis caching layer with appropriate TTLs
- [ ] Implement ticker search endpoint
- [ ] Implement historical price/returns fetch endpoint
- [ ] Write tests (mock yfinance calls, verify cache behavior)
- [ ] **Important**: test with real tickers (VTI, AAPL, BND, SPY) to verify data quality

### Phase 3 — Portfolio Service + Risk Metrics
- [ ] Implement Portfolio CRUD
- [ ] Implement Holding management with weight validation (must sum to 1.0)
- [ ] Implement `calculate_portfolio_metrics` (return, volatility, Sharpe)
- [ ] Implement `calculate_var_cvar` (historical simulation method)
- [ ] Implement `calculate_max_drawdown`
- [ ] Implement `calculate_beta` and `calculate_sortino`
- [ ] Implement correlation matrix calculation
- [ ] Write unit tests for every financial calculation with known test values
- [ ] Run `/review` before calling Phase 3 done — financial math must be correct

### Phase 4 — Efficient Frontier
- [ ] Implement `generate_efficient_frontier` using SciPy minimize
- [ ] Implement `find_min_variance_portfolio`
- [ ] Implement `find_max_sharpe_portfolio`
- [ ] Test with well-known asset pairs (e.g., SPY + BND) and verify results match expected theory:
  - 100% SPY should be on the frontier
  - A 60/40 blend should be at lower risk than 100% SPY
  - Max Sharpe portfolio should have a higher Sharpe than 100% SPY
- [ ] Write unit tests verifying optimization constraints (weights sum to 1, all positive)
- [ ] Run `/plan-eng-review` before starting — efficient frontier is the most math-heavy piece

### Phase 5 — Monte Carlo Simulation
- [ ] Implement `run_monte_carlo` (geometric Brownian motion model)
- [ ] Implement with and without annual contribution
- [ ] Add percentile bands (P5, P10, P25, P50, P75, P90, P95)
- [ ] Compute probability of profit and probability of doubling
- [ ] Write unit tests verifying: same seed → same results, 0% volatility → straight line
- [ ] Store simulation results in PostgreSQL for retrieval

### Phase 6 — Backtesting Engine
- [ ] Implement `run_backtest` with rebalancing logic
- [ ] Implement all tearsheet metrics (CAGR, Sharpe, Sortino, Calmar, Beta, Alpha, win rate)
- [ ] Test with known historical data (e.g., SPY 2018-2023, results should be verifiable)
- [ ] Store backtest results in PostgreSQL
- [ ] Run `/review` — backtesting is correctness-sensitive

### Phase 7 — Frontend
- [ ] Set up React + TypeScript + Tailwind + React Query + Recharts + Zustand
- [ ] Build auth pages (login/register)
- [ ] Build Dashboard (portfolio overview, total value, performance)
- [ ] Build Portfolio Builder (add tickers, set weights, live validation)
- [ ] Build Analysis page (efficient frontier chart, risk metrics cards, correlation heatmap)
- [ ] Build Monte Carlo page (controls + chart with percentile bands)
- [ ] Build Backtest page (date range, rebalance frequency, tearsheet display)
- [ ] Build Portfolio Comparison view
- [ ] Run `/qa` to verify all features end-to-end

### Phase 8 — Polish + Portfolio Integration
- [ ] Finalize Docker Compose
- [ ] Write GitHub Actions CI
- [ ] Write polished README: Motivation, Financial Concepts Explained (friendly but rigorous), Setup, Screenshots, Architecture Diagram, Algorithm Notes, Disclaimer
- [ ] Take screenshots (use realistic demo data: VTI + BND + VXUS allocation)
- [ ] Add project to Kenny's ePortfolio (update `src/data/projects.js`)
- [ ] Run `/review` and `/qa` on final state

---

## Resume Bullets

- Built a quantitative portfolio analytics platform in Python and FastAPI that implements Markowitz mean-variance optimization to generate efficient frontiers, with SciPy-based minimization subject to long-only and budget constraints
- Implemented five financial risk metrics (VaR via historical simulation, CVaR/Expected Shortfall, Sharpe ratio, Sortino ratio, Maximum Drawdown) and a Monte Carlo simulator that projects portfolio distributions over N years using geometric Brownian motion with configurable annual contributions
- Built a backtesting engine that simulates rebalanced portfolio strategies against real Yahoo Finance historical data and generates a full performance tearsheet (CAGR, Sharpe, Sortino, Calmar ratio, alpha, beta vs. S&P 500 benchmark)
- Designed a Redis caching layer over Yahoo Finance price data with TTL policies by data type (24h for historical returns, 15m for quotes), reducing API calls by ~90% in typical interactive sessions

---

## Portfolio Case Study Content

**context**: "I have a Vanguard index fund portfolio and wanted to understand the actual math behind what 'diversification' and 'risk-adjusted returns' mean — not the marketing version. I built the tools to calculate it from real market data."

**challenge**: "Implementing production-quality financial algorithms (efficient frontier optimization via constrained minimization, historical VaR simulation, geometric Brownian motion for Monte Carlo, backtesting with rebalancing) and presenting them visually in a way that is both mathematically rigorous and accessible to non-quants."

**approach**: "Python + FastAPI backend using NumPy/Pandas/SciPy for all financial math. Real market data from Yahoo Finance with a Redis caching layer (24h TTL for historical data). Markowitz optimization via SciPy minimize with long-only constraints. Monte Carlo using geometric Brownian motion with percentile bands. Backtesting with configurable rebalancing frequency and full tearsheet generation. React + Recharts frontend with interactive efficient frontier scatter plot, Monte Carlo band chart, and correlation heatmap."

**outcome**: "A fully functional quantitative portfolio analytics platform: efficient frontier visualization with minimum variance and maximum Sharpe points, five risk metrics calculated on real historical data, Monte Carlo projections with probability analysis, and a backtesting engine that compares any allocation against the S&P 500 over any historical window."

---

## AI Agent Working Instructions

This project is built in a separate GitHub repo, not inside the ePortfolio repo.

### gstack Skills to Use
- `/plan-eng-review` — REQUIRED before Phase 4 (efficient frontier) — the optimization math needs architectural review before coding
- `/review` — REQUIRED before marking Phase 3 (risk metrics) and Phase 6 (backtesting) complete — financial math correctness is non-negotiable
- `/qa` — run after Phase 7 to verify all visualizations render correctly
- `/ship` — for commits and pushes

### gbrain
If gbrain is configured, use it to store:
- Financial algorithm implementation notes (the math behind each calculation)
- Key test values for verifying correctness (e.g., known VaR for a specific test portfolio)
- Cross-session context for numerical parameters that might need tuning

### Critical Correctness Requirements
Financial calculations must be verified against known values:
- For Sharpe ratio: test with a portfolio of 100% SPY, verify against published historical Sharpe ratios
- For efficient frontier: verify that a blend of SPY and BND is at lower risk than 100% SPY
- For VaR: verify that 95% VaR is more extreme (larger negative number) than 90% VaR
- For Monte Carlo: with 0% volatility, all simulated paths should be identical straight lines
- For backtesting: test SPY 2019-2023 against the known SPY total return

**If a financial calculation does not produce a result that matches financial theory, stop and diagnose before continuing.**

### Documentation Hygiene
Every session must maintain:
- `docs/ENGINEERING_LOG.md` — log every change with date, what changed, why
- `docs/HANDOFF.md` — update on architecture or algorithm changes
- `docs/AI_CONTEXT.md` — especially important here: document any numerical decisions (lookback periods, confidence levels, default assumptions)
- `docs/CURRENT_TASK.md` — reflect active work

### Code Quality Standards
- All financial calculations in dedicated service files — never inline in API routes
- Use `Decimal` type for all monetary/portfolio values in the database; use `float`/`ndarray` only for in-memory math computations
- Every financial calculation function has a docstring explaining the formula and the financial interpretation of the output
- ruff + mypy run clean at all times
- No financial data committed to the repo — yfinance fetches live from Yahoo Finance

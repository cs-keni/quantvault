# Current Task

**Phase 7 — Frontend** 🚧 in progress (architecture locked 2026-06-07, Phase 7g complete)

`/plan-eng-review` complete. All decisions locked. Phase 7h Compare + Polish is next.

---

## Phase 7a — Foundation ✅ complete

Completed 2026-06-07.

- Installed `react-hook-form`, `vitest`, `@testing-library/react`, `@testing-library/user-event`, and `jsdom`.
- Added Vite dev proxy and nginx `/api/` proxy.
- Rewrote `frontend/src/services/apiClient.ts` with relative `baseURL: "/api/v1"`, token attach, `_retry`, and deduplicated refresh lock.
- Added `GET /api/v1/auth/me` returning `UserRead`.
- Added `daily_returns: list[float]` to `PortfolioMetricsResponse`, populated from the weighted return series in `risk_service.calculate_portfolio_metrics()`.
- Added `frontend/src/store/authStore.ts` with memory-only access token, `refresh_token` localStorage storage, deduplicated `silentRefresh()`, and app-init hydration via `/auth/me`.
- Added protected route bootstrapping and full Phase 7 route graph in `App.tsx`; future pages beyond auth/dashboard use lightweight placeholders until their slices are implemented.

Verification:
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed
- `cd backend && .venv/bin/ruff check app tests/test_auth.py tests/test_risk_metrics.py` — passed
- `cd backend && .venv/bin/mypy app` — passed
- `cd backend && .venv/bin/pytest tests/test_auth.py tests/test_risk_metrics.py -q` — 50 passed, 1 warning (required `docker compose up -d db redis` first)

### Step 1: Install missing packages ✅
```bash
cd frontend && npm install react-hook-form vitest @testing-library/react @testing-library/user-event jsdom --save-dev
```

### Step 2: Vite dev proxy (`frontend/vite.config.ts`) ✅
Add under `server`:
```ts
proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
```

### Step 3: nginx API proxy (`frontend/nginx.conf`) ✅
Add before the SPA catch-all `location /`:
```nginx
location /api/ {
    proxy_pass http://backend:8000;
}
```

### Step 4: Rewrite `frontend/src/services/apiClient.ts` ✅
- `baseURL: '/api/v1'` (relative — no VITE_API_BASE_URL needed)
- Request interceptor: attach access token from Zustand store (`Authorization: Bearer <token>`)
- Response interceptor: deduplicated refresh lock pattern below; `_retry` guard; skip on `/auth/login` and `/auth/refresh` paths

```ts
let refreshPromise: Promise<string> | null = null;
// On 401: if (!config._retry) { config._retry = true; refreshPromise ??= authStore.silentRefresh().finally(() => { refreshPromise = null; }); const token = await refreshPromise; ... }
```

### Step 5: Add GET /auth/me backend endpoint ✅
File: `backend/app/api/v1/auth.py`
- `GET /me` → returns `UserRead` for `current_user`
- Requires `CurrentUser` dependency (same pattern as other protected routes)

### Step 6: Add daily_returns to PortfolioMetricsResponse ✅
Files:
- `backend/app/schemas/portfolio.py` — add `daily_returns: list[float]` to `PortfolioMetricsResponse`
- `backend/app/services/risk_service.py` — populate `daily_returns` from the returns series already computed for VaR (it's already computed — just include it in the response)

### Step 7: Zustand authStore (`frontend/src/store/authStore.ts`) ✅
```ts
interface AuthState {
  user: UserRead | null;
  accessToken: string | null;
  setTokens(access: string, refresh: string): void;
  logout(): void;
  silentRefresh(): Promise<string>;
}
```
- `setTokens`: store access token in memory (`accessToken`), write refresh token to `localStorage`
- `silentRefresh`: read `localStorage.getItem('refresh_token')`, POST /auth/refresh, store new tokens; returns new access token
- On app init: call `silentRefresh()` if localStorage has a refresh token, then GET /auth/me to hydrate `user`

### Step 8: ProtectedRoute + full routing (`frontend/src/App.tsx`) ✅
- `ProtectedRoute`: checks `accessToken !== null`; redirects to `/login` if missing
- Routes: `/login`, `/register` (public); `/dashboard`, `/portfolios/new`, `/portfolios/:id/analysis`, `/portfolios/:id/simulate`, `/portfolios/:id/backtest`, `/compare` (all protected)

---

## Phase 7b — Auth Pages ✅ complete

Completed 2026-06-07.

- Replaced `/login` and `/register` placeholders with React Hook Form pages.
- Login posts to `/auth/login`, stores tokens in `authStore`, hydrates `/auth/me`, and redirects to `/dashboard`.
- Register posts to `/auth/register`, then auto-posts `/auth/login`, stores tokens/user, and redirects to `/dashboard`.
- Inline errors: login 401 → "Invalid email or password"; register 409 → "Email already registered".
- Added `npm test` script and Vitest jsdom config.
- Added `frontend/src/store/__tests__/authStore.test.ts` for concurrent refresh deduplication, logout storage clearing, refresh-path 401 guard, and no-token silent refresh rejection.

Verification:
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run build` — passed
- `cd frontend && npm run lint` — passed

### LoginPage (`/login`)
- [x] Centered card layout (min-h-screen flex items-center justify-center)
- [x] React Hook Form: email + password fields with validation
- [x] POST /auth/login → `authStore.setTokens(access, refresh)` → navigate('/dashboard')
- [x] 401 → inline error "Invalid email or password"

### RegisterPage (`/register`)
- [x] Same card layout
- [x] POST /auth/register (returns UserRead) → then auto POST /auth/login → navigate('/dashboard')
- [x] 409 → "Email already registered"

### Unit test: authStore + refresh lock
`frontend/src/store/__tests__/authStore.test.ts`
- [x] silentRefresh() called by 5 concurrent components → exactly 1 POST /auth/refresh
- [x] logout() clears accessToken from memory AND localStorage
- [x] _retry guard: 401 on /auth/refresh path does NOT trigger another refresh
- [x] No refresh_token in localStorage → silentRefresh() rejects without hitting backend

---

## Phase 7c — Dashboard (`/dashboard`) ✅ complete

Completed 2026-06-07.

- Replaced the scaffold dashboard with an authenticated risk dashboard.
- Portfolio selector loads `GET /portfolios`; default selection prefers `user.default_portfolio_id`, then first portfolio.
- Period toggle uses only locked tokens: `1mo / 6mo / 1y / 2y / max`.
- Metrics query calls `GET /analysis/portfolios/:id/metrics`.
- Risk cards show Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown.
- Return distribution histogram uses `daily_returns` from `PortfolioMetricsResponse`.
- Added animated counters and staggered card entrance with a `useRef` guard so TanStack Query refetches do not reanimate cards.
- Added loading skeletons, empty portfolio state, error states with retry, and sign-out.

Verification:
- `cd frontend && npm test` — 4 passed
- `cd frontend && npm run lint` — passed
- `cd frontend && npm run build` — passed; Vite warns the dashboard bundle is >500 kB after adding Recharts.

- [x] Portfolio selector dropdown (GET /portfolios)
- [x] Period toggle: 1mo / 6mo / 1y / 2y / max (maps to backend's period enum; NOT 1D/1W/1M)
- [x] Risk metrics cards from GET /portfolios/:id/metrics: Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown
- [x] Return distribution histogram (uses `daily_returns` from PortfolioMetricsResponse — requires Step 6)
- [x] Staggered card entrance animations; `useRef hasAnimated` guard to prevent re-animation on TanStack Query cache refetch; stable `portfolio.id` keys (not array index)
- [x] Animated number counters on metric values (count up on load)
- [x] Loading skeletons + error state with retry button

---

## Phase 7d — Portfolio Builder (`/portfolios/new`) ✅ complete

Completed 2026-06-07.

- Added `PortfolioBuilderPage` and wired `/portfolios/new`.
- Form creates a portfolio with name, description, and benchmark ticker.
- Holding rows include ticker, asset name, asset class dropdown, target weight %, current shares, and notes.
- UI accepts weight as a percentage and converts to backend `target_weight` fraction (`0.60000`) on submit.
- Submit flow: `POST /portfolios`, then `POST /portfolios/:id/holdings` for each holding, then redirect to `/dashboard`.
- Live weight sum indicator shows allocated percent and animated bar, with green at 100% and red over 100%.
- Added shared `validateHoldingDrafts()` and unit tests for sum=100, sum>100, duplicates, and empty holdings.
- Asset-class dropdown uses actual backend enum values: `EQUITY / FIXED_INCOME / REAL_ESTATE / COMMODITY / CASH`.

Verification:
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed; Vite still warns main bundle >500 kB
- `cd frontend && npm run lint` — passed

- [x] Ticker input, `asset_class` dropdown
- [x] `target_weight` input as percent, converted to backend decimal fraction
- [x] Optional: `current_shares`, `notes`
- [x] Live weight sum indicator: green when sum = 100%, red when > 100%, animated bar
- [x] POST /portfolios creates portfolio + holdings
- [x] Unit test: weight validator (sum=100% valid, sum>100% invalid, duplicates invalid, empty invalid)

**Phase 7d enum resolution:** the builder uses the current backend enum in
`backend/app/models/holding.py`: `EQUITY / FIXED_INCOME / REAL_ESTATE /
COMMODITY / CASH`. The planned `BOND / CRYPTO / OTHER` values were not added
because they would require an intentional backend enum migration.

---

## Phase 7e — Analysis Page (`/portfolios/:id/analysis`) ✅ complete

Completed 2026-06-07.

- Added `AnalysisPage` and wired `/portfolios/:id/analysis`.
- Loads portfolio detail from `GET /portfolios/:id`.
- Loads metrics from `GET /analysis/portfolios/:id/metrics` with period toggle `1mo / 6mo / 1y / 2y / max`.
- Shows reusable-style risk cards for Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown.
- Implements efficient-frontier submit flow:
  - `POST /analysis/frontier`
  - if `task_id === null && status === "SUCCESS"`, renders cached result immediately with no polling
  - otherwise polls `GET /analysis/frontier/:task_id`
  - polling stop condition uses `['SUCCESS', 'FAILURE'].includes(status)`
- Added frontier scatter chart with current portfolio, min-variance, and max-Sharpe points; tooltip shows weights.
- Added correlation heatmap from metrics correlation matrix.

Verification:
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed; Vite still warns main bundle >500 kB
- `cd frontend && npm run lint` — passed

Efficient Frontier polling pattern (critical — read carefully):
```ts
// Step 1: POST /analysis/frontier
// Step 2: if (response.task_id === null && response.status === 'SUCCESS') → use result directly, no polling
// Step 3: else → poll GET /analysis/frontier/:task_id
// Polling stop: refetchInterval: (query) => ['SUCCESS', 'FAILURE'].includes(query.state.data?.status) ? false : 2000
// Covers STARTED/RETRY states — do NOT stop only on PENDING completion
```
- [x] Frontier chart: Recharts scatter; current portfolio point, min-variance point, max-Sharpe point; hover tooltip shows weights
- [x] Risk metrics cards
- [x] Correlation heatmap

---

## Phase 7f — Monte Carlo (`/portfolios/:id/simulate`) ✅ complete

Completed 2026-06-07.

- Added `MonteCarloPage` and wired `/portfolios/:id/simulate`.
- Loads portfolio holdings from `GET /portfolios/:id`.
- Form inputs: years, n_simulations, initial_investment, annual_contribution.
- Submits `POST /simulation/monte-carlo` with portfolio_id, tickers, weights, period `1y`, and form values.
- Polls `GET /simulation/:id` until `SUCCESS` or `FAILURE`.
- Shows outcome cards: mean final value, P5/P50/P95, probability of profit, probability of doubling.
- Charts 20 sampled paths plus derived P5/P25/P50/P75/P95 lines and initial investment reference line.

Verification:
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed; Vite still warns main bundle >500 kB
- `cd frontend && npm run lint` — passed

- [x] Form: years, n_simulations, initial_investment, annual_contribution (optional)
- [x] POST /simulation/monte-carlo → poll GET /simulation/:id until SUCCESS/FAILURE
- [x] Chart: 20 sampled paths (light gray, low opacity), P5/P25/P50/P75/P95 percentile lines, initial investment reference line (dashed)
- [x] Loading/empty state while task runs; FAILURE → error display

---

## Phase 7g — Backtest (`/portfolios/:id/backtest`) ✅ complete

Completed 2026-06-07.

- Added `BacktestPage` and wired `/portfolios/:id/backtest`.
- Loads portfolio detail from `GET /portfolios/:id`.
- Form inputs: start_date, end_date, rebalance_frequency, initial_investment.
- Shows benchmark ticker from portfolio metadata; backend uses `portfolio.benchmark_ticker`, so no separate benchmark field is submitted.
- Submits `POST /portfolios/:id/backtests`, then polls `GET /portfolios/:id/backtests/:backtest_id` until SUCCESS/FAILURE.
- Renders tearsheet cards: CAGR, Sharpe, Sortino, Calmar (`null` → `N/A`), Max Drawdown, Alpha.
- Renders equity curve chart: portfolio vs benchmark.

Verification:
- `cd frontend && npm test` — 8 passed
- `cd frontend && npm run build` — passed; Vite still warns main bundle >500 kB
- `cd frontend && npm run lint` — passed

- [x] Form: start_date, end_date, rebalance_frequency, initial_investment, benchmark display from portfolio metadata
- [x] POST /portfolios/:id/backtests → poll GET /portfolios/:id/backtests/:backtest_id
- [x] Equity curve chart: portfolio vs. benchmark (EquityCurvePoint: `{ date: string, portfolio: float, benchmark: float }`)
- [x] Tearsheet cards: CAGR, Sharpe, Sortino, Calmar (`null` → show "N/A", not blank), Max Drawdown, alpha

---

## Phase 7h — Compare + Polish

- ComparePage (`/compare`): multi-portfolio selector, side-by-side metrics table
- Global: loading skeletons on all data-fetching views, error states with retry
- Run `/qa` before marking Phase 7 complete

---

## Previously complete

**Phase 6 — Backtesting Engine** ✅ complete (2026-06-07, review passed)
**Phase 5 — Monte Carlo Simulation** ✅ complete (2026-06-07, review passed)
**Phase 4 — Efficient Frontier** ✅ complete (2026-06-07, review passed)
**Phase 3 — Portfolio Service and Risk Metrics** ✅ complete (review passed)
**Phase 2 — Market Data Service** ✅ complete
**Phase 1 — Domain, Database, and Auth** ✅ complete
**Phase 0 — Scaffold** ✅ complete

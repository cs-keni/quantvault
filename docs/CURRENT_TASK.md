# Current Task

**Phase 7 — Frontend** 🚧 in progress (architecture locked 2026-06-07, Phase 7a complete)

`/plan-eng-review` complete. All decisions locked. Phase 7b is next.

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

## Phase 7b — Auth Pages

### LoginPage (`/login`)
- Centered card layout (min-h-screen flex items-center justify-center)
- React Hook Form: email + password fields with validation
- POST /auth/login → `authStore.setTokens(access, refresh)` → navigate('/dashboard')
- 401 → inline error "Invalid email or password"

### RegisterPage (`/register`)
- Same card layout
- POST /auth/register (returns UserRead) → then auto POST /auth/login → navigate('/dashboard')
- 409 → "Email already registered"

### Unit test: authStore + refresh lock
`frontend/src/store/__tests__/authStore.test.ts`
- silentRefresh() called by 5 concurrent components → exactly 1 POST /auth/refresh
- logout() clears accessToken from memory AND localStorage
- _retry guard: 401 on /auth/refresh path does NOT trigger another refresh
- No refresh_token in localStorage → silentRefresh() rejects without hitting backend

---

## Phase 7c — Dashboard (`/dashboard`)

- Portfolio selector dropdown (GET /portfolios)
- Period toggle: 1mo / 6mo / 1y / 2y / max (maps to backend's period enum; NOT 1D/1W/1M)
- Risk metrics cards from GET /portfolios/:id/metrics: Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown
- Return distribution histogram (uses `daily_returns` from PortfolioMetricsResponse — requires Step 6)
- Staggered card entrance animations; `useRef hasAnimated` guard to prevent re-animation on TanStack Query cache refetch; stable `portfolio.id` keys (not array index)
- Animated number counters on metric values (count up on load)
- Loading skeletons + error state with retry button

---

## Phase 7d — Portfolio Builder (`/portfolios/new`)

- Ticker input, `asset_class` dropdown (EQUITY / BOND / REAL_ESTATE / COMMODITY / CRYPTO / CASH / OTHER — required by HoldingCreate schema)
- `target_weight` input (decimal, 0–1 or percent — clarify with backend schema)
- Optional: `current_shares`, `notes`
- Live weight sum indicator: green when sum = 100%, red when > 100%, animated bar
- POST /portfolios creates portfolio + holdings
- Unit test: weight validator (sum=100% valid, sum>100% invalid, duplicates invalid, empty invalid)

**Phase 7d gotcha discovered during 7a:** the actual backend enum in
`backend/app/models/holding.py` is currently `EQUITY / FIXED_INCOME /
REAL_ESTATE / COMMODITY / CASH`, not the planned `BOND / CRYPTO / OTHER`
set above. Resolve this before wiring the builder dropdown: either match the
current backend enum or add a backend enum migration intentionally.

---

## Phase 7e — Analysis Page (`/portfolios/:id/analysis`)

Efficient Frontier polling pattern (critical — read carefully):
```ts
// Step 1: POST /analysis/frontier
// Step 2: if (response.task_id === null && response.status === 'SUCCESS') → use result directly, no polling
// Step 3: else → poll GET /analysis/frontier/:task_id
// Polling stop: refetchInterval: (query) => ['SUCCESS', 'FAILURE'].includes(query.state.data?.status) ? false : 2000
// Covers STARTED/RETRY states — do NOT stop only on PENDING completion
```
- Frontier chart: Recharts scatter; current portfolio point (indigo dot), min-variance star, max-Sharpe star; hover tooltip shows weights
- Risk metrics cards (reuse from Dashboard)
- Correlation heatmap

---

## Phase 7f — Monte Carlo (`/portfolios/:id/simulate`)

- Form: years, n_simulations, initial_investment, annual_contribution (optional)
- POST /simulation/monte-carlo → poll GET /simulation/:id until SUCCESS/FAILURE
- Chart: 20 sampled paths (light gray, low opacity), P5/P25/P50/P75/P95 percentile bands, initial investment reference line (dashed)
- Loading skeleton while task runs; FAILURE → error with retry

---

## Phase 7g — Backtest (`/portfolios/:id/backtest`)

- Form: start_date, end_date, rebalance_frequency, initial_investment, benchmark_ticker
- POST /portfolios/:id/backtests → poll GET /portfolios/:id/backtests/:backtest_id
- Equity curve chart: portfolio vs. benchmark (EquityCurvePoint: `{ date: string, portfolio: float, benchmark: float }`)
- Tearsheet cards: CAGR, Sharpe, Sortino, Calmar (`null` → show "N/A", not blank), Max Drawdown, alpha, beta

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

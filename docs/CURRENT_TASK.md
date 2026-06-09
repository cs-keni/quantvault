# Current Task

**Phase 7 — Frontend** ✅ complete (2026-06-07)

`/qa` Standard tier passed. 2 bugs found and fixed:
- ISSUE-001 (HIGH): Backend `_compute_metrics()` returning 500 instead of 503 on Yahoo Finance rate-limit → fixed in `ccca4c7`
- ISSUE-002 (MEDIUM): `ComparePage` premature metrics queries + table render when < 2 portfolios selected → fixed in `0059387`

**Phase 8a Infra** ✅ complete (2026-06-08)

- Added backend non-root Docker runtime and migration entrypoint.
- Added GitHub Actions CI workflow with backend, frontend, and Docker Compose build jobs.
- Added README from scratch with motivation narrative, architecture diagram, financial concepts, local setup, checks, and deferred screenshots section.
- Verification passed: frontend lint/test/build, backend ruff/mypy/pytest, Docker Compose build smoke, manual review, and isolated compose QA with register/login through nginx `/api`.

**Phase 8b UI Overhaul** ✅ complete (2026-06-08)

- Added dark-mode tokens, FOUC prevention, persisted `qv-theme` Zustand store, responsive `AppShell`, shared components, lazy routes, framer-motion route/card/sidebar animations, chart theming, and README screenshots.
- Verification passed: frontend lint/test/build, manual review scans, and Playwright Standard smoke across auth pages, all 8 authenticated route surfaces, chart rendering, theme toggle, and all three sidebar breakpoints.

**Next:** Deploy — set up Supabase + Upstash + Render + Vercel. Record demo video.

**2026-06-09 Codex test audit:** Reviewed project context, fixed backend
lint/type/test drift, and reran checks. Backend market-data tests now mock the
current Tiingo/Yahoo service seams instead of stale `yf.download` calls; RFR
fallback is back to the locked `0.04`. Verification: frontend lint/test/build
passed; backend ruff/mypy passed; backend pytest passed with 155 passed, 3
skipped when run with local Docker Postgres access outside the sandbox. Deploy
remains the next product task.

**2026-06-09 Deployment/docs audit:** Found and fixed a Render single-service
deployment regression in efficient frontier dispatch. `/analysis/frontier` now
uses Celery `apply()` in eager mode, returns the completed result immediately,
and the frontier task's sync Redis client handles Upstash `rediss://` SSL like
simulation/backtest. `backend/entrypoint.sh` now respects `${PORT:-8000}` and
`render.yaml` sets `PORT=8000`. README and env docs now describe Supabase +
Upstash + Render + Vercel, Tiingo cloud market data, `USE_CELERY=false`, and
`VITE_API_BASE_URL`.

**2026-06-09 QA/regression pre-deploy audit:** Re-ran frontend lint/test/build,
backend ruff/mypy/pytest, Alembic drift check, and Docker Compose build. Current
pre-deploy deployment diff is green: backend pytest `158 passed, 3 skipped`;
frontend tests `17 passed`; Alembic `check` found no new upgrade operations;
Docker Compose built backend, celery-worker, and frontend images. First full
backend pytest pass hit a transient late-suite `UndefinedTableError: relation
"users" does not exist` in four simulation API tests; `tests/test_simulation.py`
passed in isolation and the full backend suite passed on rerun, so record this
as a local test DB/schema-state flake to watch rather than a blocking app bug.

**2026-06-09 Continuation after capacity interruption:** Re-reviewed the
deployment/backend diff, started local Docker Postgres/Redis, and reran the
settling checks: targeted frontier/risk/simulation pytest `64 passed`, full
backend pytest `158 passed, 3 skipped`, Alembic `check` clean, and full
`docker compose build` clean aside from Docker's non-blocking buildx plugin
warning. The earlier targeted pytest failure was due to stopped local Postgres,
not app behavior.

**2026-06-09 README portfolio pass:** README was updated as a showcase artifact:
clearer project pitch, demo placeholders, recommended demo flow, why the project
matters for a student/new-grad, technical highlights, example questions, and an
educational/non-advice disclaimer. No code or functionality changed.

**2026-06-09 Backend reviewer audit:** Found and fixed two small backend
correctness issues. Monte Carlo submissions now pre-generate `task_id` and use
Celery `apply/apply_async(..., task_id=...)`, matching backtest's orphan-task
race avoidance. Historical VaR/CVaR now handles a one-return sample by clamping
the VaR lookup to the only available observation. Checks: backend ruff/mypy
passed; `tests/test_simulation.py` passed; `tests/test_backtest.py` passed;
single simulation ownership regression passed. A combined simulation+risk
pytest run repeated the local DB/schema-state flake pattern after 50 passes.

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
- `baseURL: '${VITE_API_BASE_URL ?? ""}/api/v1'` (empty locally; set to Render origin on Vercel)
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

## Phase 7h — Compare + Polish ✅ implementation complete

Completed 2026-06-07.

- Added `ComparePage` and wired `/compare`.
- Loads `GET /portfolios`, defaults to the first two portfolios, and supports selecting 2+ portfolios with checkboxes.
- Loads each selected portfolio's 1-year metrics from `GET /analysis/portfolios/:id/metrics`.
- Renders a side-by-side metrics table for annual return, annual volatility, Sharpe, Sortino, VaR, CVaR, Beta, and Max Drawdown.
- Added retry buttons to the Compare metrics error state, Monte Carlo submit/task error state, and Backtest submit/task error state.
- Removed the unused `PlaceholderPage` from the foundation slice.

Verification:
- `cd frontend && npm run build` — passed; Vite still warns main bundle >500 kB
- `cd frontend && npm run lint` — passed
- `cd frontend && npm test` — 8 passed

- [x] ComparePage (`/compare`): multi-portfolio selector, side-by-side metrics table
- [x] Global: loading skeletons on all data-fetching views, error states with retry
- [ ] Run `/qa` before marking Phase 7 complete

---

## Phase 8a — Infra ✅ complete

Implemented and verified 2026-06-08.

- `backend/Dockerfile` creates non-root `appuser`, copies app files with `appuser` ownership, switches to `USER appuser`, and starts `CMD ["./entrypoint.sh"]`.
- `backend/entrypoint.sh` runs `alembic upgrade head` before `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `.github/workflows/ci.yml` adds backend, frontend, and Docker Compose build jobs. Backend CI uses Postgres 16 and Redis 7 services and idempotently creates `quantvault_test`.
- `README.md` now includes badges, motivation narrative, architecture ASCII diagram, financial concepts, setup, checks, and a deferred screenshots section for Phase 8b.

Verification:
- [x] `cd frontend && npm run lint` — passed
- [x] `cd frontend && npm test` — 8 passed
- [x] `cd frontend && npm run build` — passed; known Recharts large-bundle warning remains until Phase 8b lazy routes
- [x] `cd backend && .venv/bin/ruff check app` — passed
- [x] `cd backend && .venv/bin/mypy app` — passed
- [x] `cd backend && .venv/bin/pytest -q` — 155 passed, 3 skipped, 1 passlib deprecation warning
- [x] `docker compose build` — passed
- [x] Manual Phase 8a review — no findings
- [x] Isolated compose QA — all 5 services started; backend entrypoint ran Alembic migrations; backend health passed; frontend container reached backend; register/login through frontend nginx `/api` returned 201/200 with tokens

Environment note: direct default compose boot hit a host-port conflict on
`8000` in this WSL/Docker session even though no QuantVault container published
that port. QA used a separate compose project on alternate host ports and
in-network Docker checks to avoid disturbing the existing DB/Redis containers.

---

## Phase 8b — UI Overhaul ✅ complete

Implemented and verified 2026-06-08.

- `frontend/index.html` adds the pre-hydration `qv-theme` script to prevent dark-default FOUC.
- `frontend/src/index.css` adds Tailwind v4 dark variants and warm charcoal tokens (`bg`, `surface`, `sidebar`, `border`, `muted`, `ink`).
- `frontend/src/store/themeStore.ts` persists the default-dark theme and updates `<html data-theme>`.
- Added shared components: `AppShell`, `MetricCard`, `PeriodToggle`, `SkeletonCard`, `PageHeader`, `MotionCardGrid`, `ChartTooltip`, and chart color constants.
- `frontend/src/App.tsx` lazy-loads all page components and wraps route changes in reduced-motion-aware `AnimatePresence` fade transitions.
- `AppShell` implements the locked desktop/tablet/mobile sidebar behavior, portfolio route selector, six nav items, active state, theme toggle, and sign out.
- Dashboard, Analysis, Monte Carlo, Backtest, Compare, Portfolio Builder, Login, and Register were converted to semantic tokens; metric grids use framer-motion staggered cards.
- Dashboard, Analysis, Monte Carlo, and Backtest use the locked Recharts palette, dark tooltips, muted axes, and gradient fills where specified.
- README embeds screenshots from `docs/screenshots/` for Dashboard dark mode, Analysis efficient frontier, and Monte Carlo paths using the demo portfolio VTI 60% / BND 30% / VXUS 10%.

Verification:
- [x] `cd frontend && npm run lint` — passed
- [x] `cd frontend && npm test` — 17 passed
- [x] `cd frontend && npm run build` — passed; non-failing `rolldown:vite-resolve` plugin timing warning only
- [x] Playwright Standard smoke — passed: Login, Register, all authenticated route surfaces, chart SVG rendering, dark-mode toggle, tablet icon rail, mobile drawer
- [x] Manual Phase 8b review scans — no leftover page-level light token hardcoding; `bg-accent` only on primary buttons or active/selected interactive states

---

## Previously complete

**Phase 8a — Infra** ✅ complete (2026-06-08)
**Phase 6 — Backtesting Engine** ✅ complete (2026-06-07, review passed)
**Phase 5 — Monte Carlo Simulation** ✅ complete (2026-06-07, review passed)
**Phase 4 — Efficient Frontier** ✅ complete (2026-06-07, review passed)
**Phase 3 — Portfolio Service and Risk Metrics** ✅ complete (review passed)
**Phase 2 — Market Data Service** ✅ complete
**Phase 1 — Domain, Database, and Auth** ✅ complete
**Phase 0 — Scaffold** ✅ complete

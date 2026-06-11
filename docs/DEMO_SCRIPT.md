# QuantVault Demo Recording Script

Silent screen recording — no voiceover. Mouse movements guide the viewer.
Recording length: ~2m 45s.

## Setup before recording

- Browser fullscreen, dark mode on
- Logged in as `demo@quantvault.dev` / `quantvault-demo`
- Demo Portfolio already selected in the sidebar dropdown

---

## Scene 1 — Create a new portfolio (~45s)

1. Click **"New portfolio"** in the sidebar (or top nav)

Fill in the portfolio form:

**Header fields:**
- **Portfolio name:** type `Tech Growth`
- **Benchmark:** clear `SPY`, type `QQQ`
- **Description:** leave blank

**Holding 1** (the first row is already there):
- **Ticker:** `AAPL`
- **Asset name:** `Apple Inc`
- **Asset class dropdown:** leave as `Equity` (default)
- **Weight %:** `30`
- **Shares:** leave blank

Click **"Add holding"** — watch the new row animate in from above.

**Holding 2:**
- **Ticker:** `MSFT`
- **Asset name:** `Microsoft Corp`
- **Asset class dropdown:** leave as `Equity`
- **Weight %:** `35`

Click **"Add holding"**

**Holding 3:**
- **Ticker:** `GOOGL`
- **Asset name:** `Alphabet Inc`
- **Asset class dropdown:** leave as `Equity`
- **Weight %:** `25`

Click **"Add holding"**

**Holding 4:**
- **Ticker:** `BND`
- **Asset name:** `Vanguard Total Bond`
- **Asset class dropdown:** select `Fixed income`
- **Weight %:** `10`

Pause ~2 seconds — the weight bar should be **green** and show **"✓ Fully allocated"** at 100.00%.

Click **"Save portfolio"**

📸 **Screenshot:** Portfolio builder — all 4 holdings filled, green 100% bar + "✓ Fully allocated" badge visible

---

## Scene 2 — Dashboard (~40s)

You land on the Dashboard for Tech Growth automatically.

1. Slowly hover each of the **6 metric cards**: Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown
2. Click the **period toggle**: `1mo` → pause → `6mo` → pause → `1y`
3. Draw attention to the **Allocation sidebar** on the right:
   - Each holding has a labeled colored progress bar (indigo for equity, sky for fixed income)
   - Bars are sorted by weight descending
   - Below the bars: Annual return in green (positive) or red (negative), Volatility, Risk-free rate
4. Use the **portfolio dropdown** to switch to **Demo Portfolio** — notice the allocation bars update immediately

📸 **Screenshot:** Dashboard on Demo Portfolio — all 6 metric cards + the allocation sidebar visible

---

## Scene 3 — Analysis: Correlation heatmap + Efficient Frontier (~60s)

Make sure **Demo Portfolio** is selected.

1. Click **Analysis** in the sidebar
2. Scroll down to the **Correlation heatmap** section
3. Hover over a **non-diagonal cell** — pause on the VTI/VXUS cell (~0.82) and the VTI/BND cell (~0.29). Tooltip shows tickers + strength label ("strong positive", "weak positive")
4. Hover over a **diagonal cell** (e.g., VTI × VTI, value = 1.00) — tooltip shows "Self-correlation — always 1.0"
5. Scroll up to the **Efficient frontier** section
6. Click **"Run frontier"**
7. Wait ~10 seconds for results
8. Point out the **inline legend**: Frontier curve / Min risk / Max Sharpe / Current portfolio
9. Hover over each of the 3 special marker dots:
   - **Min risk** (green halo) — lowest volatility point
   - **Max Sharpe** (amber halo) — best risk-adjusted return
   - **Current portfolio** (indigo halo) — where your weights sit on the curve
10. Hover along the smooth frontier curve itself

📸 **Screenshot:** Analysis — correlation heatmap + efficient frontier rendered with all 3 special dots visible

---

## Scene 4 — Monte Carlo Simulation (~45s)

1. Click **Monte Carlo** in the sidebar
2. The form pre-fills with defaults — **leave all as-is:**
   - **Years:** `10`
   - **Simulations:** `500`
   - **Initial investment:** `10000`
   - **Annual contribution:** `0`
3. Click **"Run simulation"**
4. Watch the subtitle under the page title: it briefly shows **"Running…"** with **three bouncing indigo dots**
5. Wait ~10 seconds for results
6. Hover the **4 stat cards**: Mean final value, Median, Probability of profit (green), Probability of doubling (green)
7. Point out the **Simulation paths** inline legend: p95 optimistic (green) / p50 median (indigo) / p5 pessimistic (red) / Initial investment (dashed)
8. Hover along the fan of grey background paths, then trace the p50 median line (brightest indigo)
9. Scroll down to the **Outcome distribution** histogram:
   - 20-bucket bar chart of all 500 final values
   - Hover a bar — tooltip shows the currency bucket + count
   - Shows the full outcome spread at a glance (vs just the percentile lines)

📸 **Screenshot:** Monte Carlo — paths chart + 4 stat cards + outcome distribution histogram all visible

---

## Scene 5 — Backtest (~35s)

1. Click **Backtest** in the sidebar
2. The form pre-fills — **leave all as-is:**
   - **Start date:** auto-fills to 5 years ago (~2021-06-10)
   - **End date:** auto-fills to today
   - **Rebalance:** `QUARTERLY` (default)
   - **Initial investment:** `10000`
   - **Benchmark:** `SPY` (greyed out — read-only, set from portfolio settings)
3. Click **"Run backtest"**
4. Watch the bouncing dots in the subtitle while it runs
5. Wait ~15 seconds for results
6. Hover each of the **6 tearsheet cards**: CAGR, Sharpe, Sortino, Calmar (green if ≥1), Max Drawdown, Volatility
7. Point out the **equity curve legend**: Portfolio (indigo) vs SPY benchmark (grey)
8. Slowly trace both lines — show where the portfolio outperforms or diverges from the benchmark

📸 **Screenshot:** Backtest — equity curve + 6 tearsheet cards with Calmar colored

---

## Scene 6 — Compare (~25s)

1. Click **Compare** in the sidebar
2. Select **Demo Portfolio** from the first dropdown
3. Select **Tech Growth** from the second dropdown
4. Read the caption: **"1-year trailing period · green = better"**
5. Slowly hover the **side-by-side metrics table** — green-highlighted cells show the winner per row (Annual return, Sharpe, Sortino, etc.)
6. Note: ties are not highlighted — only clear single winners get the green treatment

📸 **Screenshot:** Compare — both portfolios in the metrics table, winner cells highlighted green

---

## Screenshots to take (6 total)

| # | What to capture | When |
|---|---|---|
| 1 | Portfolio builder — 4 holdings filled, green 100% bar + "✓ Fully allocated" | Before clicking Save |
| 2 | Dashboard — Demo Portfolio, all 6 metric cards + allocation sidebar | After switching to Demo Portfolio |
| 3 | Analysis — correlation heatmap + efficient frontier with all 3 special dots | After frontier renders |
| 4 | Monte Carlo — paths chart + 4 stat cards + outcome distribution histogram | After simulation completes |
| 5 | Backtest — equity curve with legend + 6 tearsheet cards | After backtest completes |
| 6 | Compare — both portfolios, winner cells in green | After selecting both portfolios |

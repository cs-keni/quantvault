# QuantVault Demo Recording Script

Silent screen recording — no voiceover. Mouse movements guide the viewer.

## Setup before recording

- Browser fullscreen, dark mode on
- Logged in as `demo@quantvault.dev` / `quantvault-demo`
- Demo Portfolio already selected in the sidebar dropdown

---

## Scene 1 — Create a new portfolio (~45s)

1. Click the **portfolio dropdown** at the top of the sidebar
2. Select **"+ Add portfolio"**

Fill in the portfolio form:

**Header fields:**
- **Portfolio name:** type `Tech Growth`
- **Benchmark:** clear `SPY`, type `QQQ`
- **Description:** leave blank

**Holding 1** (the first row is already there):
- **Ticker:** `AAPL`
- **Asset name:** `Apple Inc`
- **Asset class dropdown:** leave as `Equity` (default)
- **Weight %:** `40`
- **Shares:** leave blank
- **Notes:** leave blank

Click **"Add holding"**

**Holding 2:**
- **Ticker:** `MSFT`
- **Asset name:** `Microsoft Corp`
- **Asset class dropdown:** leave as `Equity`
- **Weight %:** `35`
- **Shares:** leave blank
- **Notes:** leave blank

Click **"Add holding"**

**Holding 3:**
- **Ticker:** `GOOGL`
- **Asset name:** `Alphabet Inc`
- **Asset class dropdown:** leave as `Equity`
- **Weight %:** `25`
- **Shares:** leave blank
- **Notes:** leave blank

Pause ~2 seconds on the weight bar — it should be **green** and say **100.00% allocated**

Click **"Save portfolio"**

📸 **Screenshot:** Portfolio builder with all 3 holdings filled and the green 100% weight bar

---

## Scene 2 — Dashboard (~30s)

You land on the Dashboard for Tech Growth automatically.

1. Slowly hover each of the **6 metric cards**: Sharpe, Sortino, VaR, CVaR, Beta, Max Drawdown
2. Click the **period toggle** slowly: `1mo` → pause → `6mo` → pause → `1y`
3. Use the **portfolio dropdown** to switch to **Demo Portfolio**
4. Hover each metric card again — the conservative allocation shows lower drawdown and lower beta

📸 **Screenshot:** Dashboard on Demo Portfolio showing all 6 metric cards

---

## Scene 3 — Analysis: Correlation heatmap + Efficient Frontier (~45s)

Make sure **Demo Portfolio** is selected.

1. Click **Analysis** in the sidebar
2. Scroll down to the **Correlation heatmap** section
3. Slowly hover over each cell — pause on the VTI/VXUS cell (~0.82, strong positive) and the VTI/BND cell (~0.29, weak positive)
4. Scroll back up to the **Efficient frontier** section
5. Click **"Run frontier"**
6. Wait ~10 seconds for results
7. Slowly hover along the **frontier curve**
8. Hover over each of the 3 special dots: current portfolio, min-variance, max-Sharpe

📸 **Screenshot:** Analysis page showing both the correlation heatmap and the efficient frontier

---

## Scene 4 — Monte Carlo Simulation (~30s)

1. Click **Monte Carlo** in the sidebar
2. The form pre-fills with defaults — **leave all as-is:**
   - **Years:** `10`
   - **Simulations:** `500`
   - **Initial investment:** `10000`
   - **Annual contribution:** `0`
3. Click **"Run simulation"**
4. Wait ~10 seconds
5. Hover the **4 stat cards**: Mean final value, Median, Probability of profit, Probability of doubling
6. Hover along the **simulation paths** — trace the P50 median line (brightest blue line in the center)

📸 **Screenshot:** Monte Carlo with the paths chart and all 4 stat cards visible

---

## Scene 5 — Backtest (~30s)

1. Click **Backtest** in the sidebar
2. The form pre-fills — **leave all as-is:**
   - **Start date:** auto-fills to 5 years ago (~2021-06-10)
   - **End date:** auto-fills to today
   - **Rebalance:** `QUARTERLY` (default)
   - **Initial investment:** `10000`
   - **Benchmark:** `SPY` (read-only, greyed out — set by portfolio settings)
3. Click **"Run backtest"**
4. Wait ~15 seconds
5. Hover each of the **6 tearsheet cards**: CAGR, Sharpe, Sortino, Calmar, Max Drawdown, Alpha
6. Slowly trace both lines on the **equity curve**: portfolio (blue) vs SPY benchmark (grey)

📸 **Screenshot:** Backtest with equity curve + 6 tearsheet cards

---

## Scene 6 — Compare (~20s)

1. Click **Compare** in the sidebar
2. Check **Demo Portfolio**
3. Check **Tech Growth**
4. Slowly hover the **side-by-side metrics table** — contrast conservative vs aggressive allocation

📸 **Screenshot:** Compare page with both portfolios in the metrics table

---

## Screenshots to take (6 total)

| # | What to capture | When |
|---|---|---|
| 1 | Portfolio builder — 3 holdings filled, green 100% bar | Before clicking Save |
| 2 | Dashboard — Demo Portfolio, all 6 metric cards | After switching to Demo Portfolio |
| 3 | Analysis — correlation heatmap + efficient frontier rendered | After frontier renders |
| 4 | Monte Carlo — paths chart + 4 stat cards | After simulation completes |
| 5 | Backtest — equity curve + 6 tearsheet cards | After backtest completes |
| 6 | Compare — both portfolios side by side | After checking both |

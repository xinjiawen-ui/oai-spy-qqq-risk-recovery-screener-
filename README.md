# SPY / QQQ Market Risk & Recovery Research Terminal

[Open the dashboard](https://xinjiawen-ui.github.io/oai-spy-qqq-risk-recovery-screener-/)

## Architecture

- `scripts/update.py`: daily market snapshot and append-only first-observed score archive.
- `scripts/backtest.py`: original 60/40 chronological train/test strategy research.
- `scripts/rebound_test.py`: Recovery-only vs high-Fragility-then-Recovery comparison.
- `scripts/regime_research.py`: historical next-open 5/10/20-session conditional returns by market regime.
- `index.html`: mobile-friendly static dashboard; includes a consolidated overview, evidence journal, research and methodology.
- `data/*.json`: generated research outputs; retain `score_history.json` across deployments.
- `.github/workflows/dashboard.yml`: scheduled refresh and GitHub Pages deployment.

## Run locally

```bash
python -m pip install -r requirements.txt
python scripts/update.py
python scripts/backtest.py
python scripts/rebound_test.py
python scripts/regime_research.py
python -m unittest discover -s tests
python -m http.server 8000
```

## Deploy from iPhone

Open the repository in GitHub, choose **Actions → Update market data and deploy → Run workflow → main → Run workflow**. In **Settings → Pages**, select **GitHub Actions** as the build source. Wait for the green deployment job before checking the dashboard. Code changes on main trigger a refresh/deployment; the manual workflow remains available.

## Model interpretation and limitations

Scores are heuristic 0–100 weighted indicators, **not** validated market probabilities. RSP/SPY is an ETF relative-performance proxy, not constituent breadth. The regime study uses 10 years of daily Yahoo Finance data, scores observed at close t, and hypothetical forward returns from open t+1 to open t+1+H. Overlapping forward-return observations are dependent; displayed positive frequencies and Wilson intervals are descriptive, not calibrated probabilities. The displayed volatility-target core allocation is a model, not a validated trading recommendation.

Legacy backtests use a single 60/40 chronological split, 5 bps per side and cash earning zero, not a full walk-forward study or risk-free adjusted Sharpe. Avoid comparing strategies without considering market exposure. Data may be delayed, missing, revised or subject to Yahoo Finance limitations. Research only; no live order execution.

## Planned incremental upgrades

1. Add daily price/volume and score history charts, with regime markers and configurable weights.
2. Implement rolling walk-forward and bootstrapped validation, T-bill cash returns, and strategy equity/drawdown curves.
3. Add independently tested dynamic sizing, RSI/EMA strategies and stop/target research.
4. Add hourly/4-hour backtests where source data supports the history.
5. Add an options-data adapter with explicit unavailable status until reliable licensed options data is configured.

Do not invent options statistics or substitute heuristic gamma exposure for measured dealer positions.

## November comprehensive checklist (experimental)

The daily market regime view now includes a separate SPY/QQQ evidence checklist: 5/20/50/100/200-session trend returns, EMA distances, drawdown and distribution volume; equal-weight participation and sector ratios; HY OAS and credit proxies; direct lagged FRED Treasury and real yields; VIX/VVIX dynamics; 10/20/30/60-day realised volatility and an illustrative 10% vol-target allocation with three five-session roll-off scenarios. Individual statuses are descriptive, not scores, and do not change legacy signals, trade sizes or backtests. New archive rows contain the checklist, version and observed coverage; old rows are preserved.

The manual checklist covers forward earnings revisions, valuations, AI demand/capex/funding, inflation and policy surprises, tariffs, direct constituent breadth, CFTC positioning, actual CTA/vol-control flows, leveraged ETF AUM/rebalance estimates, dealer gamma/skew, cash flows, seasonality and catalyst follow-through. These remain explicitly unobserved until verified independently; no synthetic institutional flow dollars or unlicensed options data are supplied. Automated coverage excludes manual rows and is not confidence or probability. Rate observations exclude same-day values and become unavailable after seven calendar days. ETF data use unfilled prices for the new diagnostics and require a matching last session. The vol roll-off scenarios are hypothetical constant daily returns, not forecasts. All thresholds are experimental; future research should compare against base rates and walk-forward calibration before integrating into trading rules.

## Consolidated decision dashboard v3

Overview shows one set of legacy scores for each ETF, the existing regime and confirmation gates, and a summary by evidence group. Evidence compares ETF-specific readings side by side and shows identical shared market-wide observations once. Direct 10Y observations take priority over the redundant Yahoo 10Y proxy when both ETFs have direct data. The checklist now also includes RSI14, VVIX, realised volatility acceleration, lagged investment-grade OAS, and explicit manual Truflation and initial-claims checks. Manual evidence can be saved per session locally in the browser with notes; it is not synced, scored or collected by the server. Research & history restores the conditional-return study, and methodology retains legacy model definitions for reproducibility. Removed overlapping qualitative panels and the old risk sizing calculator from the daily interface. No production trading rules or backtests are changed. The reload button fetches the published snapshot; it does not initiate an upstream refresh. GitHub Actions runs syntax checks, rendering smoke tests and Python unit tests before refresh/deployment. Code-only main pushes trigger the workflow; data-only bot commits do not.

## Resilient data feeds

The tracker now tries the FRED fredgraph CSV route (batch, then individual series) and independent official Treasury nominal/real curve CSV downloads. If direct spreads or yields remain missing, the Evidence tab displays alternate quotes or explicitly labelled bond ETF return proxies with their own units; raw missing fields remain in the JSON and any genuinely unresolved gaps are disclosed in a compact expandable panel. Effective coverage counts a primary field with a usable replacement once; it is not a measure of equivalent accuracy or trading confidence. Supplemental macro series use conservative observation lags (45 days for monthly, 14 days for claims, one day for daily rates) and are not point-in-time vintage data. Market-price context for AI/fundamentals, inflation and options is not a substitute for reported earnings, CPI or measured dealer positions. The leveraged ETF model shows hypothetical exposure changes per $1B starting assets, not actual dollar flows. No legacy score or backtest thresholds have been changed.

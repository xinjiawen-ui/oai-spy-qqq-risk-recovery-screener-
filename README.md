# SPY / QQQ Market Risk & Recovery Research Terminal

[Open the dashboard](https://xinjiawen-ui.github.io/oai-spy-qqq-risk-recovery-screener-/)

## Architecture

- `scripts/update.py`: daily market snapshot and append-only first-observed score archive.
- `scripts/backtest.py`: original 60/40 chronological train/test strategy research.
- `scripts/rebound_test.py`: Recovery-only vs high-Fragility-then-Recovery comparison.
- `scripts/regime_research.py`: historical next-open 5/10/20-session conditional returns by market regime.
- `index.html`: mobile-friendly static dashboard; includes regime research and user-input risk sizing.
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

Open the repository in GitHub, choose **Actions → Update market data and deploy → Run workflow → main → Run workflow**. In **Settings → Pages**, select **GitHub Actions** as the build source. Wait for the green deployment job before checking the dashboard. A fresh workflow run is required after code changes.

## Model interpretation and limitations

Scores are heuristic 0–100 weighted indicators, **not** validated market probabilities. RSP/SPY is an ETF relative-performance proxy, not constituent breadth. The regime study uses 10 years of daily Yahoo Finance data, scores observed at close t, and hypothetical forward returns from open t+1 to open t+1+H. Overlapping forward-return observations are dependent; displayed positive frequencies and Wilson intervals are descriptive, not calibrated probabilities. The risk calculator uses user-selected stop assumptions; it does not validate stops, targets or position-sizing alpha.

Legacy backtests use a single 60/40 chronological split, 5 bps per side and cash earning zero, not a full walk-forward study or risk-free adjusted Sharpe. Avoid comparing strategies without considering market exposure. Data may be delayed, missing, revised or subject to Yahoo Finance limitations. Research only; no live order execution.

## Planned incremental upgrades

1. Add daily price/volume and score history charts, with regime markers and configurable weights.
2. Implement rolling walk-forward and bootstrapped validation, T-bill cash returns, and strategy equity/drawdown curves.
3. Add independently tested dynamic sizing, RSI/EMA strategies and stop/target research.
4. Add hourly/4-hour backtests where source data supports the history.
5. Add an options-data adapter with explicit unavailable status until reliable licensed options data is configured.

Do not invent options statistics or substitute heuristic gamma exposure for measured dealer positions.


## Regime-first overhaul (October 2026)

The homepage now starts with a cross-asset regime desk: fragility/recovery, participation, tech leadership, credit, volatility and direct macro-credit readings. Existing scores, historical archives and technical drilldowns remain accessible.

`scripts/macro_credit.py` queries public FRED CSV observations for DGS2, DGS10, DGS30, BAMLH0A0HYM2, BAMLC0A0CM, and T10Y2Y; `data/macro_credit.json` is refreshed by GitHub Actions. Missing/failed/stale (>7 calendar days) inputs are explicitly unavailable and are **never assigned zero risk**. Direct readings are not live: FRED publication lags and market closes may differ. The IEF five-day move is only an ETF price-duration proxy and must not be labeled a Treasury yield. Credit ETF ratios are not credit option-adjusted spreads.

**Research caveats:** the new stress cutoffs and regime labels remain heuristic, not probability estimates or trading instructions. The historic outcome study still covers the legacy model and overlapping observations, and **does not validate the direct-yield/OAS macro panel**. Neither the dashboard's narrative classifications nor its tactical position sizes should be considered institutional-grade validated forecasts until a point-in-time, vintage-aware walk-forward study is completed with realistic cost, execution, and portfolio benchmark assumptions. The user-facing Refresh button checks GitHub Pages' latest published snapshot; it does not trigger new price collection.

Before production deployment: run the GitHub Actions workflow on the feature branch (or merge and manually trigger main), check unit tests, JS syntax and published JSON schema, then compare displayed metrics and dates to source observations.

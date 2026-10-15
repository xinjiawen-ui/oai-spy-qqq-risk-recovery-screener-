"""Historical regime-conditioned outcomes and illustrative risk sizing.
All forward returns are measured from NEXT session open to a later open.
Overlapping forward windows are descriptive, not independent trades.
"""
import datetime, json, pathlib
import numpy as np
import pandas as pd
import yfinance as yf
from backtest import ASSETS, OTHERS, build_scores

ROOT=pathlib.Path(__file__).resolve().parents[1]
HORIZONS=(5,10,20)
def classify(f,r,change):
    if not np.isfinite([f,r,change]).all(): return "Unavailable"
    if f>=60 and r>=50 and change>0: return "Early rebound"
    if f>=60: return "Market stress"
    if f<40 and r>=60 and change>=0: return "Healthy expansion"
    if f<40 and change<0: return "Potential deterioration"
    return "Mixed / transitional"

def conditional_statistics(df,horizon,regime):
    valid=df[(df["regime"]==regime)&(df["fragility_coverage"]>=90)&(df["recovery_coverage"]>=90)]
    x=valid["forward_"+str(horizon)].dropna()
    n=len(x)
    if not n: return {"samples":0,"positive_probability_pct":None}
    wins=int((x>0).sum())
    # Wilson 95% interval for the observed win fraction; overlap reduces effective sample size.
    z=1.96; p=wins/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {"samples":n,"positive_probability_pct":round(100*p,2),
            "wilson_95_pct":[round(100*(center-radius),2),round(100*(center+radius),2)],
            "mean_return_pct":round(100*x.mean(),3),"median_return_pct":round(100*x.median(),3),
            "p10_return_pct":round(100*x.quantile(.1),3),"p90_return_pct":round(100*x.quantile(.9),3),
            "prob_gain_2pct":round(100*(x>=.02).mean(),2),
            "prob_loss_2pct":round(100*(x<=-.02).mean(),2)}

def main():
    raw=yf.download(ASSETS+OTHERS,period="10y",interval="1d",auto_adjust=True,progress=False,threads=False)
    if raw.empty: raise RuntimeError("Missing historical market data")
    c=raw["Close"];v=raw["Volume"];op=raw["Open"]
    output={"schema_version":1,"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "method":"Ten-year daily adjusted prices; score at close t, hypothetical entry open t+1, exit open t+1+H; historical overlapping observations; NOT calibrated future probabilities or a tradable backtest.",
            "regime_definitions":{"Early rebound":"Fragility >=60, Recovery >=50, Recovery 5-day change >0",
                                  "Market stress":"Fragility >=60, excluding early rebound",
                                  "Healthy expansion":"Fragility <40, Recovery >=60, Recovery 5-day change >=0",
                                  "Potential deterioration":"Fragility <40, Recovery 5-day change <0",
                                  "Mixed / transitional":"Other covered observations"},
            "assets":{}}
    for ticker in ASSETS:
        scores=build_scores(c,v,ticker)
        scores["recovery_change_5d"]=scores["recovery"].diff(5)
        scores["regime"]=[classify(f,r,d) for f,r,d in zip(scores["fragility"],scores["recovery"],scores["recovery_change_5d"])]
        o=op[ticker].reindex(scores.index)
        for h in HORIZONS:
            scores["forward_"+str(h)]=o.shift(-(h+1))/o.shift(-1)-1
        covered=scores[(scores["fragility_coverage"]>=90)&(scores["recovery_coverage"]>=90)]
        if len(covered)<100: raise RuntimeError("Insufficient factor coverage for "+ticker)
        latest=covered.iloc[-1]
        latest_regime=latest["regime"]
        stats={regime:{str(h):conditional_statistics(scores,h,regime) for h in HORIZONS}
               for regime in output["regime_definitions"]}
        output["assets"][ticker]={"as_of":covered.index[-1].strftime("%Y-%m-%d"),
            "current_regime":latest_regime,"fragility":int(latest["fragility"]),
            "recovery":int(latest["recovery"]),"recovery_change_5d":float(latest["recovery_change_5d"]),
            "regimes":stats}
    path=ROOT/"data"/"regime_research.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output,indent=2,allow_nan=False))
    print("Saved",path)

if __name__=="__main__": main()

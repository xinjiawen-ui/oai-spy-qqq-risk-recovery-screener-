"""Test whether recent high fragility followed by rising recovery improves Sharpe.
Uses score construction in backtest.py; all signals known at prior close.
"""
import json, datetime, pathlib
import numpy as np
import pandas as pd
import yfinance as yf
from backtest import ASSETS, OTHERS, build_scores, stats
ROOT=pathlib.Path(__file__).resolve().parents[1]
def run(df,condition,hold,cost=0.0005):
    o=df["open"].to_numpy(float)
    valid=condition.reindex(df.index).fillna(False).to_numpy(bool)
    daily=np.zeros(len(df)-1);trades=[];i=1
    while i+hold<len(o):
        if valid[i-1] and np.isfinite(o[i:i+hold+1]).all() and np.all(o[i:i+hold+1]>0):
            path=o[i:i+hold+1]
            rets=path[1:]/path[:-1]-1
            rets[0]-=cost;rets[-1]-=cost
            daily[i:i+hold]=rets
            trades.append(float(np.prod(1+rets)-1))
            i+=hold
        else:i+=1
    return stats(daily,trades)
def make_conditions(df,kind,params):
    rec=df["recovery"];frag=df["fragility"]
    valid=(df["recovery_coverage"]>=90)&(df["fragility_coverage"]>=90)
    if kind=="recovery_only":
        threshold=params["recovery_min"]
        # Crossing avoids automatic re-entry solely because a score stays high.
        return valid&(rec>=threshold)&(rec.shift(1)<threshold)
    high=params["recent_fragility_min"]
    rec_min=params["recovery_min"]
    delta=params["recovery_rise_5d"]
    lookback=10
    # Recent fragility must PRECEDE the signal close; no contemporaneous hindsight.
    recent_high=frag.shift(1).rolling(lookback,min_periods=lookback).max()>=high
    return valid&recent_high&(rec>=rec_min)&((rec-rec.shift(5))>=delta)&((rec.shift(1)-rec.shift(6))<delta)
def benchmark(df):
    # Buy at first test open and hold through final open; mark open-to-open returns.
    o=df["open"].dropna()
    if len(o)<60:return None
    ret=o.pct_change(fill_method=None).iloc[1:].to_numpy(copy=True)
    ret[0]-=0.0005
    return stats(ret,[float(o.iloc[-1]/o.iloc[0]-1-0.0005)])
def main():
    raw=yf.download(ASSETS+OTHERS,period="10y",interval="1d",auto_adjust=True,progress=False,threads=False)
    if raw.empty:raise RuntimeError("No market data returned")
    c=raw["Close"];v=raw["Volume"];op=raw["Open"]
    out={"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "method":"60% chronological training, 40% untouched test; next-open entry; 5bps/side; nonoverlapping holds; cash zero return; daily Sharpe with zero risk-free assumption; no claim of full walk-forward validation.",
         "results":{}}
    for ticker in ASSETS:
        df=build_scores(c,v,ticker);df["open"]=op[ticker]
        df=df.dropna(subset=["open"])
        split=int(len(df)*0.6)
        train=df.iloc[:split].copy()
        # Include pre-test history for correct lookback features; no test outcome leakage.
        test=df.iloc[split:].copy()
        record={"benchmark_test":benchmark(test),"comparisons":[]}
        for hold in [5,10,20]:
            selected={}
            for kind in ["recovery_only","fragility_then_recovery"]:
                candidates=[]
                if kind=="recovery_only":
                    grid=[{"recovery_min":r} for r in [30,40,50,60,70]]
                else:
                    grid=[{"recent_fragility_min":f,"recovery_min":r,"recovery_rise_5d":d}
                          for f in [40,60,80] for r in [30,40,50,60] for d in [10,20,30]]
                for p in grid:
                    cond=make_conditions(train,kind,p)
                    st=run(train,cond,hold)
                    if st and st["sharpe"] is not None and st["trades"]>=12:
                        candidates.append((st["sharpe"],st["trades"],p,st))
                if not candidates:
                    selected[kind]={"status":"insufficient training trades"}
                    continue
                candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
                _,_,params,train_stat=candidates[0]
                # Signal history calculated on full timeline, but performance only on test.
                full_cond=make_conditions(df,kind,params)
                test_cond=full_cond.iloc[split:]
                test_stat=run(test,test_cond,hold)
                selected[kind]={"parameters":params,"train":train_stat,"test":test_stat,
                                "status":"test has fewer than 10 trades" if test_stat is None or test_stat["trades"]<10 else "evaluated"}
            record["comparisons"].append({"holding_sessions":hold,"strategies":selected})
        out["results"][ticker]=record
    path=ROOT/"data"/"rebound_comparison.json";path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out,indent=2,allow_nan=False))
    print("Saved",path)
if __name__=="__main__":main()

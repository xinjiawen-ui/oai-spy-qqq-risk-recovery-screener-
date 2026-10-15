"""Walk-forward research: daily fragility/recovery scores versus SPY/QQQ returns.
Scores are computed using information through each day's close only.
Signals execute at the NEXT day's open and exit at the open H sessions later.
Non-overlapping positions, cash when flat, no leverage. Costs: 5 bps per side.
Test thresholds on an expanding train set and evaluate on future calendar blocks.
"""
import json, pathlib, datetime
import numpy as np
import pandas as pd
import yfinance as yf
ROOT=pathlib.Path(__file__).resolve().parents[1]
ASSETS=["SPY","QQQ"]
OTHERS=["RSP","SOXX","XLK","XLP","HYG","LQD","IEF","^VIX","^VIX3M"]
def ema(x,n):return x.ewm(span=n,adjust=False,min_periods=n).mean()
def pct(x,n):return x.pct_change(n,fill_method=None)*100
def build_scores(c,v,t):
    x=c[t];cr=c["HYG"]/c["LQD"];b=c["RSP"]/c["SPY"];tech=c["XLK"]/c["XLP"];semi=c["SOXX"]/c["QQQ"]
    vx=c["^VIX"];term=vx/c["^VIX3M"]
    def flag(cond,available,weight):return (cond & available).astype(float)*weight
    def available(z):return z.notna()
    br=b/ema(b,20)-1;bt=pct(b,5);sm=semi/ema(semi,20)-1;tl=tech/ema(tech,20)-1
    cl=cr/ema(cr,20)-1;ct=pct(cr,5);vc=pct(vx,5);vr=vx/ema(vx,20)
    x20=x/ema(x,20)-1;x50=x/ema(x,50)-1;rv=v[t]/v[t].rolling(20).mean()
    ir=pct(c["IEF"],5);r5=pct(x,5);r1=pct(x,1)
    specs=[
      ("fragility",[(br,lambda z:z<0,15),(bt,lambda z:z<0,10),(x20,lambda z:z<0,10),(x50,lambda z:z<0,5),
                    (rv,lambda z:(z>1.25)&(x20<0),5),(sm,lambda z:z<0,10),(tl,lambda z:z<0,5),
                    (vc,lambda z:z>=15,5),(vr,lambda z:z>1.15,5),(term,lambda z:z>=1,5),
                    (cl,lambda z:z<0,10),(ct,lambda z:z<0,5),(ir,lambda z:z<=-1,10)]),
      ("recovery",[(bt,lambda z:z>0,15),(br,lambda z:z>0,10),(sm,lambda z:z>0,15),(tl,lambda z:z>0,5),
                   (ct,lambda z:z>0,12),(cl,lambda z:z>0,8),(r5,lambda z:z>0,10),
                   (rv,lambda z:(z>=1)&(r1>0),5),(vc,lambda z:z<0,5),(term,lambda z:z<1,5),(x20,lambda z:z>0,10)])
    ]
    out=pd.DataFrame(index=x.index)
    for name,parts in specs:
        out[name]=sum(flag(fn(z),available(z),w) for z,fn,w in parts)
        out[name+"_coverage"]=sum(available(z).astype(float)*w for z,fn,w in parts)
    return out
def simulate(df,frag,recovery,hold,cost=0.0005):
    # Entry next open; a position occupies exactly 'hold' open-to-open sessions.
    o=df["open"].to_numpy(float);f=df["fragility"].to_numpy(float);r=df["recovery"].to_numpy(float)
    cv=df["fragility_coverage"].to_numpy(float);rv=df["recovery_coverage"].to_numpy(float)
    ret=np.zeros(len(df)-1);entries=0;trade_returns=[];i=0
    while i<len(ret):
        signal_idx=i-1
        if signal_idx>=0 and cv[signal_idx]>=90 and rv[signal_idx]>=90 and f[signal_idx]>=frag and r[signal_idx]>=recovery and np.isfinite(o[i]) and o[i]>0:
            end=min(i+hold,len(o)-1)
            if end<i+hold:break
            path=o[i:end+1]
            if not np.isfinite(path).all() or np.any(path<=0):i+=1;continue
            daily=path[1:]/path[:-1]-1
            daily[0]-=cost;daily[-1]-=cost
            ret[i:end]=daily
            trade_returns.append(np.prod(1+daily)-1)
            entries+=1;i=end
        else:i+=1
    return ret,entries,trade_returns
def stats(returns,trades):
    if len(returns)<60:return None
    std=np.std(returns,ddof=1)
    sharpe=float(np.mean(returns)/std*np.sqrt(252)) if std>0 else None
    equity=np.cumprod(1+returns)
    dd=float(np.min(equity/np.maximum.accumulate(np.r_[1,equity])[1:]-1))
    return {"sharpe":sharpe,"annualized_return_pct":float((equity[-1]**(252/len(returns))-1)*100),
            "max_drawdown_pct":dd*100,"trades":len(trades),"win_rate_pct":float(np.mean(np.array(trades)>0)*100) if trades else None,
            "exposure_pct":float(np.mean(returns!=0)*100)}
def main():
    raw=yf.download(ASSETS+OTHERS,period="10y",interval="1d",auto_adjust=True,progress=False,threads=False)
    if raw.empty:raise RuntimeError("No market data")
    c=raw["Close"];v=raw["Volume"];op=raw["Open"]
    result={"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "method":"10-year rolling-history walk-forward; train first 60%, select on training, evaluate final 40%; next-open entry/exit, non-overlap, 5bps/side; no leverage; cash 0%; no benchmark risk-free subtraction.",
      "results":{}}
    for ticker in ASSETS:
        scores=build_scores(c,v,ticker)
        df=scores.copy();df["open"]=op[ticker]
        df=df.dropna(subset=["open"])
        split=int(len(df)*.6)
        # Train/test split by time. Evaluate all configurations on untouched test.
        train=df.iloc[:split];test=df.iloc[split:]
        rankings=[]
        for hold in [5,10,20]:
            candidates=[]
            for frag in range(0,81,20):
                for recovery in range(0,81,20):
                    r,n,tr=simulate(train,frag,recovery,hold)
                    s=stats(r,tr)
                    if s and n>=12 and s["sharpe"] is not None:candidates.append((s["sharpe"],frag,recovery,n))
            if not candidates:
                rankings.append({"holding_sessions":hold,"status":"insufficient training trades"});continue
            candidates.sort(reverse=True)
            _,frag,recovery,_=candidates[0]
            train_r,_,train_tr=simulate(train,frag,recovery,hold)
            test_r,n,test_tr=simulate(test,frag,recovery,hold)
            rankings.append({"holding_sessions":hold,"fragility_min":frag,"recovery_min":recovery,
              "train":stats(train_r,train_tr),"test":stats(test_r,test_tr),
              "status":"descriptive only" if n<10 else "out-of-sample estimate"})
        result["results"][ticker]=rankings
    p=ROOT/"data"/"backtest.json";p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(result,indent=2,allow_nan=False))
    print("Saved",p)
if __name__=="__main__":main()

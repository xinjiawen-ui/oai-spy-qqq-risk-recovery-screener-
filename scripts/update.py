import json, pathlib, datetime
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS=["SPY","QQQ","RSP","SOXX","XLK","XLP","HYG","LQD","^VIX","^VIX3M","IEF"]
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    raw=yf.download(TICKERS,period="1y",interval="1d",auto_adjust=True,progress=False,threads=False)
    if raw.empty: raise RuntimeError("No market data returned")
    close=raw["Close"].copy()
    volume=raw["Volume"].copy()
    close=close.ffill(limit=2)
    dates=close.index
    def s(t): return close[t] if t in close else pd.Series(dtype=float)
    def last(series):
        a=series.dropna()
        return float(a.iloc[-1]) if len(a) else None
    def ema(x,n): return x.ewm(span=n,adjust=False,min_periods=n).mean()
    def pct(x,n=1): return x.pct_change(n,fill_method=None)*100
    def ratio(a,b): return s(a)/s(b)
    credit=ratio("HYG","LQD"); breadth=ratio("RSP","SPY"); tech=ratio("XLK","XLP"); semi=ratio("SOXX","QQQ")
    vix=s("^VIX"); v3=s("^VIX3M")
    rows={}
    for ticker,target in [("SPY",0.15),("QQQ",0.20)]:
        x=s(ticker)
        if len(x.dropna())<60: continue
        d=x.diff(); gain=d.clip(lower=0); loss=(-d).clip(lower=0)
        rs=gain.rolling(2).mean()/loss.rolling(2).mean().replace(0,np.nan)
        rsi=100-100/(1+rs)
        rsi=rsi.where(loss.rolling(2).mean()!=0,100)
        vol=x.pct_change(fill_method=None).rolling(20).std()*np.sqrt(252)
        exposure=(target/vol).clip(lower=0,upper=1)
        factors={
          "Trend": bool(last(x)<last(ema(x,20)) or last(ema(x,20))<last(ema(x,50))),
          "VIX ≥25": bool(last(vix) is not None and last(vix)>=25),
          "VIX backwardation": bool(last(vix/v3) is not None and last(vix/v3)>=1),
          "Credit weakness": bool(last(credit) is not None and last(ema(credit,20)) is not None and last(credit)<last(ema(credit,20))),
          "Tech defensive rotation": bool(last(tech) is not None and last(ema(tech,20)) is not None and last(tech)<last(ema(tech,20)))
        }
        known={"Trend":True,"VIX ≥25":last(vix)!=None,"VIX backwardation":last(vix/v3)!=None,"Credit weakness":last(credit)!=None,"Tech defensive rotation":last(tech)!=None}
        original=sum(int(v) for k,v in factors.items() if known[k])
        # Heuristic dashboard score, not a backtested entry model.
        checks=[
          (20,factors["Trend"],known["Trend"]),
          (10,factors["Credit weakness"],known["Credit weakness"]),
          (10,factors["Tech defensive rotation"],known["Tech defensive rotation"]),
          (15,last(breadth/ema(breadth,20)) is not None and last(breadth/ema(breadth,20))<1,last(breadth/ema(breadth,20))!=None),
          (10,last(semi/ema(semi,20)) is not None and last(semi/ema(semi,20))<1,last(semi/ema(semi,20))!=None),
          (10,last(pct(vix,5)) is not None and last(pct(vix,5))>=15,last(pct(vix,5))!=None),
          (10,factors["VIX backwardation"],known["VIX backwardation"]),
          (10,last(vix/ema(vix,20)) is not None and last(vix/ema(vix,20))>1.15,last(vix/ema(vix,20))!=None),
          (5,last(pct(s("IEF"),5)) is not None and last(pct(s("IEF"),5))<=-1,last(pct(s("IEF"),5))!=None)
        ]
        score=sum(w for w,flag,ok in checks if ok and flag)
        coverage=sum(w for w,flag,ok in checks if ok)
        credit_ok=known["Credit weakness"] and not factors["Credit weakness"]
        oversold=last(rsi) is not None and last(rsi)<35
        # Fresh transition must be calculated using yesterday's full five-factor score.
        daily_flags=pd.DataFrame({
          "trend":(x<ema(x,20)) | (ema(x,20)<ema(x,50)),
          "vix":vix>=25,
          "term":(vix/v3)>=1,
          "credit":credit<ema(credit,20),
          "tech":tech<ema(tech,20)
        })
        daily_count=daily_flags.astype(int).sum(axis=1)
        transition=(daily_count>=4)&(daily_count.shift(1)<4)
        signal=bool(transition.iloc[-1] and oversold and credit_ok and all(known.values()))
        last_date=x.dropna().index[-1]
        rows[ticker]={
          "close":last(x),"rsi2":last(rsi),"realized_vol_20d":last(vol),
          "core_exposure_pct":round(100*last(exposure),1) if last(exposure)!=None else None,
          "original_score":original,"original_coverage":sum(known.values()),
          "original_factors":{k:{"flag":v,"available":known[k]} for k,v in factors.items()},
          "risk_score":score,"risk_coverage":coverage,"entry_signal":signal,
          "credit_filter_pass":credit_ok,"oversold":oversold,
          "date":last_date.strftime("%Y-%m-%d"),
          "history":[{"date":i.strftime("%Y-%m-%d"),"close":round(float(v),2)} for i,v in x.dropna().tail(90).items()]
        }
    def metric(name,series):return {"name":name,"value":last(series),"date":series.dropna().index[-1].strftime("%Y-%m-%d") if len(series.dropna()) else None}
    metrics=[
      metric("VIX",vix),metric("VIX 5d change %",pct(vix,5)),
      metric("RSP/SPY (breadth proxy)",breadth),metric("RSP/SPY vs 20d EMA %",(breadth/ema(breadth,20)-1)*100),
      metric("SOXX/QQQ",semi),metric("SOXX/QQQ vs 20d EMA %",(semi/ema(semi,20)-1)*100),
      metric("HYG/LQD",credit),metric("HYG/LQD vs 20d EMA %",(credit/ema(credit,20)-1)*100),
      metric("VIX/VIX3M",vix/v3)
    ]
    output={"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source":"Yahoo Finance via yfinance (unofficial; may be delayed)","assets":rows,"metrics":metrics,"limitations":["RSP/SPY is a breadth proxy, not S&P 500 constituent participation.","Expanded score weights are heuristic and have not been backtested.","Tactical signals use closing data; any execution is next session.","No options dealer gamma or IV skew is included."]}
    if not rows:raise RuntimeError("No usable SPY/QQQ rows")
    dest=ROOT/"data"/"latest.json";dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(output,indent=2,allow_nan=False))
    print("Updated",dest,output["generated_at_utc"])
if __name__=="__main__":main()

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
        # Expanded fragility model: factor coverage is explicit; weights sum to 100.
        # True constituent breadth, option gamma and IV skew are not available here.
        def observation(value, predicate):
            return (value is not None and np.isfinite(value), bool(value is not None and np.isfinite(value) and predicate(value)))
        breadth_level=last((breadth/ema(breadth,20)-1)*100)
        breadth_trend=last(pct(breadth,5))
        semi_level=last((semi/ema(semi,20)-1)*100)
        tech_level=last((tech/ema(tech,20)-1)*100)
        credit_level=last((credit/ema(credit,20)-1)*100)
        credit_change=last(pct(credit,5))
        vix_change=last(pct(vix,5))
        vix_rel=last(vix/ema(vix,20))
        term=last(vix/v3)
        x20=last(x/ema(x,20)-1)
        x50=last(x/ema(x,50)-1)
        vol5=last(volume[ticker]/volume[ticker].rolling(20).mean()) if ticker in volume else None
        rate_move=last(pct(s("IEF"),5))
        # The six categories are scored separately to expose their contributions.
        components=[
          ("Breadth proxy",25,[(15,observation(breadth_level,lambda v:v<0)),(10,observation(breadth_trend,lambda v:v<0))]),
          ("Price and volume",20,[(10,observation(x20,lambda v:v<0)),(5,observation(x50,lambda v:v<0)),(5,observation(vol5,lambda v:v>1.25 and x20 is not None and x20<0))]),
          ("Sector leadership",15,[(10,observation(semi_level,lambda v:v<0)),(5,observation(tech_level,lambda v:v<0))]),
          ("VIX dynamics",15,[(5,observation(vix_change,lambda v:v>=15)),(5,observation(vix_rel,lambda v:v>1.15)),(5,observation(term,lambda v:v>=1))]),
          ("Credit",15,[(10,observation(credit_level,lambda v:v<0)),(5,observation(credit_change,lambda v:v<0))]),
          ("Rates",10,[(10,observation(rate_move,lambda v:v<=-1))])
        ]
        breakdown=[]
        for name,weight,parts in components:
            earned=sum(w for w,(ok,flag) in parts if ok and flag)
            available=sum(w for w,(ok,flag) in parts if ok)
            breakdown.append({"name":name,"weight":weight,"score":earned,"coverage":available})
        score=sum(b["score"] for b in breakdown)
        coverage=sum(b["coverage"] for b in breakdown)
        # Recovery score measures positive changes, not simply the inverse of fragility.
        # 25 breadth + 20 leadership + 20 credit + 15 price/volume + 10 vol + 10 trend follow-through.
        recovery_parts=[
          ("Breadth improvement",25,[(15,observation(breadth_trend,lambda v:v>0)),(10,observation(breadth_level,lambda v:v>0))]),
          ("Semis / tech stabilization",20,[(15,observation(semi_level,lambda v:v>0)),(5,observation(tech_level,lambda v:v>0))]),
          ("Credit recovery",20,[(12,observation(credit_change,lambda v:v>0)),(8,observation(credit_level,lambda v:v>0))]),
          ("Price / volume reversal",15,[(10,observation(last(pct(x,5)),lambda v:v>0)),(5,observation(vol5,lambda v:v>=1 and last(pct(x,1)) is not None and last(pct(x,1))>0))]),
          ("Volatility easing",10,[(5,observation(vix_change,lambda v:v<0)),(5,observation(term,lambda v:v<1))]),
          ("Trend follow-through",10,[(10,observation(x20,lambda v:v>0))])
        ]
        recovery_breakdown=[]
        for name,weight,parts in recovery_parts:
            earned=sum(w for w,(ok,flag) in parts if ok and flag)
            available=sum(w for w,(ok,flag) in parts if ok)
            recovery_breakdown.append({"name":name,"weight":weight,"score":earned,"coverage":available})
        recovery_score=sum(b["score"] for b in recovery_breakdown)
        recovery_coverage=sum(b["coverage"] for b in recovery_breakdown)
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
          "risk_score":score,"risk_coverage":coverage,"risk_breakdown":breakdown,"recovery_score":recovery_score,"recovery_coverage":recovery_coverage,"recovery_breakdown":recovery_breakdown,"entry_signal":signal,
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
    output={"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source":"Yahoo Finance via yfinance (unofficial; may be delayed)","assets":rows,"metrics":metrics,"limitations":["RSP/SPY is a breadth proxy, not S&P 500 constituent participation.","Expanded fragility and recovery scores are heuristic and have not been backtested; neither is a standalone entry trigger.","Tactical signals use closing data; any execution is next session.","No options dealer gamma or IV skew is included."]}
    if not rows:raise RuntimeError("No usable SPY/QQQ rows")
    dest=ROOT/"data"/"latest.json";dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(output,indent=2,allow_nan=False))
    print("Updated",dest,output["generated_at_utc"])
if __name__=="__main__":main()

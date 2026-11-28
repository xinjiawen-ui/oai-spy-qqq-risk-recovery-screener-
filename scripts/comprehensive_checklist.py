"""Additive descriptive checklist. No changes to production signals or backtests."""
import io
import urllib.request
import numpy as np
import pandas as pd

VERSION = "november-checklist-v3-resilient"
MANUAL = [
 ("Fundamentals","Forward EPS revisions / earnings breadth","FactSet Earnings Insight; positive revisions vs price drawdown","https://insight.factset.com/"),
 ("Fundamentals","Forward P/E and earnings yield less 10Y","Index provider / FactSet; compare to own history, not a full equity risk premium","https://insight.factset.com/"),
 ("Fundamentals","AI monetisation, capex and funding","Verify AI lab revenue, hyperscaler capex, GPU prices, cash flow and credit; SALP forecasts are narrative, not facts","https://www.sec.gov/edgar/search/"),
 ("Fundamentals","AI borrower credit / concentration","Issuer bond spreads, liquidity, covenants, customer concentration and debt maturities","https://www.finra.org/finra-data/fixed-income"),
 ("Macro","CPI, core PCE, payrolls and surprise","Actual vs contemporaneous consensus; check inflation and growth direction jointly","https://www.bls.gov/"),
 ("Macro","Truflation / high-frequency inflation nowcast","Supplementary measure; compare methodology and direction with official CPI/PCE","https://truflation.com/"),
 ("Macro","Initial jobless claims and labour trend","Weekly releases; compare four-week average and surprises","https://www.dol.gov/agencies/eta/ui-claims"),
 ("Macro","Fed policy and rate expectations","Fed funds futures, 2Y/5Y/10Y yields, real yield and curve; separate inflation from growth shocks","https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
 ("Macro","Tariffs / regulatory and geopolitical shock","Verify announcement, effective date and earnings exposure; do not score unverified headlines","https://www.federalreserve.gov/"),
 ("Breadth","Constituent advance/decline, above 50/200DMA, new lows","Use point-in-time membership; equal-weight ETFs are proxies only","https://www.spglobal.com/spdji/"),
 ("Systematic flows","CFTC equity index futures positioning","Weekly delayed net positions by category; leveraged funds are not identical to CTAs","https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"),
 ("Systematic flows","Actual CTA / vol-control / risk-parity flows","Require timestamped provider estimates; do not infer dollars from trend or VIX","https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"),
 ("Systematic flows","Leveraged ETF AUM and rebalance estimate","Obtain dated AUM for TQQQ/QLD/SQQQ and compute L*(L-1)*AUM*index return; approximate before flows and hedges","https://www.proshares.com/"),
 ("Options / liquidity","Dealer gamma, put skew, expiry and depth","Need signed dealer positioning assumptions, option OI/IV and intraday liquidity; VIX is not gamma","https://www.cboe.com/"),
 ("Options / liquidity","Fund flows, buybacks, holiday / expiry seasonality","Confirm cash ETF flows and liquidity; calendar effects not directional certainty","https://www.cboe.com/"),
 ("Recovery validation","Catalyst and follow-through","Track source/date, earnings vs sentiment vs flows, 2-3 closes, breadth, credit and failed breakout","https://www.sec.gov/edgar/search/"),
]
def fetch_rates(as_of):
    """FRED rate observations lagged one day; failure is explicit, not filled."""
    ids=["DGS2","DGS5","DGS10","DFII10","T10Y2Y","BAMLC0A0CM"]
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?id="+",".join(ids)
    try:
        with urllib.request.urlopen(url,timeout=12) as response:
            df=pd.read_csv(io.StringIO(response.read().decode()))
        df.index=pd.to_datetime(df.iloc[:,0])
        return {k:pd.to_numeric(df[k],errors="coerce").dropna().sort_index().loc[lambda z:z.index<pd.Timestamp(as_of)] for k in ids if k in df}
    except Exception:
        return {}

def build_checklist(close, volume, assets, credit, rates=None):
    """Use unfilled prices; require exact latest ETF session for daily signals."""
    result={}
    rates = rates if rates is not None else {}
    for ticker,a in assets.items():
        date=pd.Timestamp(a["date"])
        x=close[ticker].dropna().loc[:date] if ticker in close else pd.Series(dtype=float)
        rows=[]
        def add(group,name,value,unit,rule,status,source="Yahoo Finance (proxy)",observed=None):
            valid=value is not None and np.isfinite(value)
            rows.append(dict(group=group,name=name,value=round(float(value),4) if valid else None,
                unit=unit,rule=rule,status=status if valid else "UNAVAILABLE",
                source=source,as_of=observed or (a["date"] if valid else None)))
        def series(t):
            if t not in close:return pd.Series(dtype=float)
            z=close[t].loc[:date].dropna()
            return z if len(z) and z.index[-1]==date else pd.Series(dtype=float)
        def value(z):
            return float(z.iloc[-1]) if len(z) and pd.notna(z.iloc[-1]) and np.isfinite(z.iloc[-1]) else None
        def ratio(t,u):
            return (series(t)/series(u)).dropna()
        def change(z,n):
            return value(z.pct_change(n,fill_method=None)*100)
        def signed(group,name,v,unit,rule,cut=0):
            add(group,name,v,unit,rule,"SUPPORT" if v is not None and v>cut else "STRESS" if v is not None and v<cut else "WATCH")
        if not len(x) or x.index[-1]!=date:
            result[ticker]={"rows":rows,"coverage":0};continue
        ret=x.pct_change(fill_method=None).dropna()
        for n in (5,20,50,100,200):
            v=change(x,n)
            signed("Systematic flows",f"{n}d trend return",v,"%","Positive trend supportive; negative trend may pressure trend followers")
        for n in (20,50,100,200):
            v=value((x/x.ewm(span=n,adjust=False,min_periods=n).mean()-1)*100)
            signed("Trend",f"Distance to EMA{n}",v,"%","Above EMA supportive; below EMA stress")
        delta=x.diff()
        gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
        rs=100-100/(1+gain/loss.replace(0,np.nan))
        rs=rs.where(loss!=0,100).where((gain!=0)|(loss!=0),50)
        rsi=value(rs)
        add("Trend","RSI14",rsi,"","Oversold below 30; overbought above 70; not standalone entry","WATCH")
        dd=value((x/x.rolling(63,min_periods=63).max()-1)*100)
        add("Trend","63-session drawdown",dd,"%","Stress at -10% or worse; watch at -5%","STRESS" if dd is not None and dd<=-10 else "WATCH" if dd is not None and dd<=-5 else "SUPPORT")
        neg=int((ret.tail(10)<0).sum()) if len(ret)>=10 else None
        add("Trend","Red sessions / 10",neg,"days","7+ red sessions = persistent selling","STRESS" if neg is not None and neg>=7 else "WATCH")
        if ticker in volume:
            v=volume[ticker].reindex(x.index)
            denom=v.tail(10).sum(min_count=10)
            down=v.where(ret.reindex(v.index)<0,0).tail(10).sum(min_count=10)
            share=float(100*down/denom) if pd.notna(denom) and denom>0 else None
            add("Trend","Down-day volume share / 10",share,"%","60%+ distribution warning","STRESS" if share is not None and share>=60 else "WATCH")
        # ETF-specific participation; QQQE is equal-weight Nasdaq-100, not constituent breadth.
        for t,u in [("RSP","SPY"),("QQQE","QQQ"),("SOXX",ticker),("IWM","SPY"),("XLY","XLP"),("XLK","XLU")]:
            if t=="QQQE" and ticker=="SPY":continue
            if t=="RSP" and ticker=="QQQ":continue
            signed("Breadth",f"{t}/{u} 5d relative return",change(ratio(t,u),5),"%","Positive relative strength supports participation / leadership")
        signed("Credit","HYG/LQD 5d relative return",change(ratio("HYG","LQD"),5),"%","ETF credit proxy; duration mismatch")
        signed("Credit","HYG/SHY 5d relative return",change(ratio("HYG","SHY"),5),"%","Alternative proxy; not OAS")
        oas=credit.get("change_20_observations_bps") if credit.get("status")=="available" else None
        add("Credit","HY OAS 20-observation change",oas,"bp","Widening stress; tightening support","STRESS" if oas is not None and oas>0 else "SUPPORT" if oas is not None and oas<0 else "WATCH","FRED BAMLH0A0HYM2",credit.get("observation_date"))
        oas_level=credit.get("oas_pct") if credit.get("status")=="available" else None
        add("Credit","HY OAS level",oas_level,"%","Context; widening and percentile matter more than a fixed threshold","STRESS" if oas_level is not None and oas_level>=6.5 else "WATCH","FRED BAMLH0A0HYM2",credit.get("observation_date"))
        ig=rates.get("BAMLC0A0CM",pd.Series(dtype=float)).dropna()
        ig=ig[ig.index<date] if len(ig) else ig
        ig_date=ig.index[-1].strftime("%Y-%m-%d") if len(ig) else None
        ig_fresh=bool(len(ig) and (date-ig.index[-1]).days<=7)
        ig_level=value(ig) if ig_fresh else None
        ig_change=value(ig.diff(20)*100) if ig_fresh else None
        add("Credit","IG OAS level",ig_level,"%","Direct investment-grade option-adjusted spread","WATCH","https://fred.stlouisfed.org/series/BAMLC0A0CM",ig_date)
        add("Credit","IG OAS 20-observation change",ig_change,"bp","Widening stress; tightening support","STRESS" if ig_change is not None and ig_change>0 else "SUPPORT" if ig_change is not None and ig_change<0 else "WATCH","https://fred.stlouisfed.org/series/BAMLC0A0CM",ig_date)
        for k,label in [("DGS2","2Y Treasury"),("DGS5","5Y Treasury"),("DGS10","10Y Treasury"),("DFII10","10Y real Treasury"),("T10Y2Y","10Y–2Y curve")]:
            z=rates.get(k,pd.Series(dtype=float)).dropna()
            z=z[z.index<date] if len(z) else z
            observed=z.index[-1].strftime("%Y-%m-%d") if len(z) else None
            fresh=bool(len(z) and (date-z.index[-1]).days<=7)
            v=value(z) if fresh else None
            source=z.attrs.get("source","https://fred.stlouisfed.org/series/"+k)
            add("Macro",label,v,"%","Lagged direct observation; not a forecast","WATCH",source,observed)
            bp=value(z.diff(5)*100) if fresh else None
            add("Macro",label+" 5-observation change",bp,"bp","Rise >=20bp warns for yields; curve change needs growth context","STRESS" if k!="T10Y2Y" and bp is not None and bp>=20 else "WATCH",source,observed)
        for t in ("^TNX","^IRX"):
            z=series(t); v=value(z)
            add("Macro",f"{t} yield",v,"%","10Y / 13-week yield reference, not Fed funds expectations","WATCH")
            # absolute yield change, not % change
            bp=value(z.diff(5)*100)
            add("Macro",f"{t} 5d yield change",bp,"bp","Rise >=20bp warning; falling yields require growth context","STRESS" if bp is not None and bp>=20 else "WATCH")
        vix=series("^VIX"); term=value(ratio("^VIX","^VIX3M"))
        v=value(vix)
        add("Volatility","VIX level",v,"","30+ acute stress; level is context, not a buy trigger","STRESS" if v is not None and v>=30 else "WATCH")
        vvix=value(series("^VVIX"))
        add("Volatility","VVIX level",vvix,"","Volatility of VIX; no direct dealer position inference","WATCH")
        accel=float(ret.tail(5).std()/ret.tail(20).std()) if len(ret)>=20 and ret.tail(20).std()>0 else None
        add("Volatility","Realised volatility acceleration 5d/20d",accel,"x","1.3x or higher flags accelerating risk","STRESS" if accel is not None and accel>=1.3 else "WATCH")
        for t in ("^VIX","^VVIX"):
            v=change(series(t),5)
            add("Volatility",f"{t} 5d change",v,"%","Falling fear supports stabilization; rising >=15% warns","SUPPORT" if v is not None and v<0 else "STRESS" if v is not None and v>=15 else "WATCH")
        add("Volatility","VIX/VIX3M",term,"x","Backwardation >=1 stress","STRESS" if term is not None and term>=1 else "SUPPORT")
        for n in (10,20,30,60):
            rv=float(ret.tail(n).std()*np.sqrt(252)*100) if len(ret)>=n else None
            add("Systematic flows",f"Realised volatility {n}d",rv,"% annualised","Vol-target funds react to realised rather than only implied volatility","WATCH")
        if len(ret)>=20:
            def allocation(r):
                sigma=float(r.std()*np.sqrt(252))
                return min(100,10/sigma) if sigma>0 else 100.
            base=allocation(ret.tail(20))
            add("Systematic flows","Illustrative 10% vol-target exposure",base,"%","Capped 100%; not actual fund positioning","WATCH","Model: adjusted ETF returns")
            for shock in (-.01,0,.01):
                r=pd.Series(list(ret.tail(15))+[shock]*5)
                delta=allocation(r)-base
                add("Systematic flows",f"5d vol roll-off: {shock*100:+.0f}%/day",delta,"pp","Change in illustrative allocation; not flow dollars","SUPPORT" if delta>0 else "STRESS" if delta<0 else "WATCH","Scenario: 20d realised volatility")
        # Follow-through distinct from merely oversold.
        signed("Recovery validation","3d price return",change(x,3),"%","Positive follow-through, not confirmation alone")
        prior=x.shift(1).rolling(10,min_periods=10).min()
        dist=value((x/prior-1)*100)
        add("Recovery validation","Distance from prior 10d low",dist,"%","New closing low warns; higher low requires persistence","STRESS" if dist is not None and dist<0 else "WATCH")
        result[ticker]={"rows":rows,"coverage":round(100*sum(r["value"] is not None for r in rows)/len(rows)) if rows else 0}
    return {"version":VERSION,"experimental":True,"assets":result,
            "manual":[dict(group=g,name=n,rule=r,source=s,status="MANUAL / NOT OBSERVED") for g,n,r,s in MANUAL]}

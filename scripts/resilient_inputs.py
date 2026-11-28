"""Alternate data routes and transparent proxy fallbacks for the evidence view."""
import io
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

FRED="https://fred.stlouisfed.org/graph/fredgraph.csv"
TREASURY="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv"
IDS=["DGS2","DGS5","DGS10","DFII10","T10Y2Y","BAMLC0A0CM","BAMLH0A0HYM2","T10YIE","ICSA","CPIAUCSL","PCEPILFE","UNRATE"]
def read_csv(url):
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,*/*"})
    with urllib.request.urlopen(request,timeout=10) as response:
        return pd.read_csv(io.BytesIO(response.read()))

def parse_frame(frame):
    frame=frame.copy()
    frame.index=pd.to_datetime(frame.iloc[:,0],errors="coerce")
    return frame.loc[frame.index.notna()].sort_index()

def numeric(z,source):
    z=pd.to_numeric(z,errors="coerce").dropna()
    z=z[~z.index.duplicated(keep="last")].sort_index()
    z.attrs["source"]=source
    return z

def fetch_inputs(as_of):
    date=pd.Timestamp(as_of)
    start=(date-pd.Timedelta(days=800)).strftime("%Y-%m-%d")
    def fred(ids):
        try:
            url=FRED+"?id="+",".join(ids)+"&cosd="+start
            f=parse_frame(read_csv(url))
            return {k:numeric(f[k],"https://fred.stlouisfed.org/series/"+k) for k in ids if k in f}
        except Exception:return {}
    def treasury(real):
        kind="daily_treasury_real_yield_curve" if real else "daily_treasury_yield_curve"
        data={}
        for year in {date.year,(date-pd.Timedelta(days=40)).year}:
            try:
                url=f"{TREASURY}/{year}/all?type={kind}&field_tdr_date_value={year}&page&_format=csv"
                f=parse_frame(read_csv(url))
                mapping={"10 yr":"DFII10"} if real else {"2 yr":"DGS2","5 yr":"DGS5","10 yr":"DGS10"}
                for col in f.columns:
                    k=mapping.get(str(col).strip().lower())
                    if k:
                        z=numeric(f[col],url)
                        if k in data:z=numeric(pd.concat([data[k],z]),url)
                        data[k]=z
            except Exception:continue
        return data
    def fresh(k,z):
        if z is None:return False
        lag=45 if k in ("CPIAUCSL","PCEPILFE","UNRATE") else 14 if k=="ICSA" else 1
        maxage=100 if lag==45 else 30 if lag==14 else 7
        q=z.loc[z.index<=date-pd.Timedelta(days=lag)]
        return len(q)>0 and (date-q.index[-1]).days<=maxage
    with ThreadPoolExecutor(max_workers=8) as pool:
        first=pool.submit(fred,IDS)
        nominal=pool.submit(treasury,False)
        real=pool.submit(treasury,True)
        data=first.result()
        retries={k:pool.submit(fred,[k]) for k in IDS if not fresh(k,data.get(k))}
        for k,job in retries.items():
            z=job.result().get(k)
            if fresh(k,z):data[k]=z
        for source in (nominal.result(),real.result()):
            for k,z in source.items():
                if not fresh(k,data.get(k)) and fresh(k,z):data[k]=z
    if not fresh("T10Y2Y",data.get("T10Y2Y")) and fresh("DGS10",data.get("DGS10")) and fresh("DGS2",data.get("DGS2")):
        data["T10Y2Y"]=numeric(data["DGS10"]-data["DGS2"],"Calculated: 10Y minus 2Y Treasury yields")
    return data

def augment(checklist,close,assets,inputs):
    """Replace missing rows with labelled alternative measures; never assign OAS or yield units to ETF returns."""
    for ticker,a in checklist["assets"].items():
        date=pd.Timestamp(assets[ticker]["date"])
        rows=a["rows"]
        originals=list(rows)
        def s(k):
            if k not in close:return pd.Series(dtype=float)
            z=close[k].loc[:date].dropna()
            return z if len(z) and z.index[-1]==date else pd.Series(dtype=float)
        def ret(k,n=5,base=None):
            z=s(k)
            if base:z=(z/s(base)).dropna()
            if len(z)<=n or z.iloc[-n-1]==0:return None
            v=(z.iloc[-1]/z.iloc[-n-1]-1)*100
            return float(v) if np.isfinite(v) else None
        def emit(group,name,v,unit,rule,source,kind="PROXY",as_of=None,direction=0):
            if v is None or not np.isfinite(v):return None
            status="SUPPORT" if direction*v>0 else "STRESS" if direction*v<0 else "WATCH"
            return dict(group=group,name=name,value=round(float(v),4),unit=unit,rule=rule,status=status,source=source,as_of=as_of or date.strftime("%Y-%m-%d"),data_kind=kind)
        # Each direct row remains in raw data; show one substitute for a missing family, not two duplicated rows.
        families=[
          ("HY OAS", "Credit","High-yield credit proxy: HYG/SHY 20d return","HYG","SHY",20,1,"Not an OAS level or change; duration and liquidity also affect prices"),
          ("IG OAS", "Credit","Investment-grade credit proxy: LQD/IEF 20d return","LQD","IEF",20,1,"Duration mismatch; not a measured spread"),
          ("2Y Treasury","Macro","Short-rate proxy: SHY 5d return","SHY",None,5,0,"Bond return, not a two-year yield"),
          ("5Y Treasury","Macro","Intermediate-rate proxy: IEI 5d return","IEI",None,5,0,"Bond return, not a five-year yield"),
          ("10Y Treasury","Macro","Long-rate proxy: IEF 5d return","IEF",None,5,0,"Bond return, not a ten-year yield"),
          ("10Y real Treasury","Macro","Real-rate proxy: TIP 5d return","TIP",None,5,0,"TIPS return; duration and inflation accrual affect it"),
          ("10Y–2Y curve","Macro","Curve proxy: IEF/SHY 5d relative return","IEF","SHY",5,0,"Duration-relative return, not a yield-curve spread"),
        ]
        for prefix,group,name,k,base,n,sign,rule in families:
            missing=[r for r in rows if r["name"].startswith(prefix) and r["value"] is None]
            if not missing:continue
            # Same economic observation from alternate ticker for 10Y/5Y.
            quote={"10Y Treasury":"^TNX","5Y Treasury":"^FVX"}.get(prefix)
            z=s(quote) if quote else pd.Series(dtype=float)
            if len(z):
                for item in missing:
                    v=float(z.iloc[-1]) if "change" not in item["name"] else float((z.iloc[-1]-z.iloc[-6])*100) if len(z)>=6 else None
                    row=emit(group,item["name"]+" (market quote)",v,item["unit"],"Market yield quote, not official constant maturity","Yahoo Finance "+quote,"ALTERNATE")
                    if row:row["replaces"]=[item["name"]];rows.append(row)
            remaining=[r for r in missing if not any(r["name"] in q.get("replaces",[]) for q in rows)]
            if remaining:
                v=ret(k,n,base)
                if v is None and k=="IEI":
                    k="IEF";v=ret(k,n);name="Intermediate/long-rate proxy: IEF 5d return"
                row=emit(group,name,v,"%",rule,"Yahoo Finance "+k+("/"+base if base else ""),direction=sign)
                if row:row["replaces"]=[r["name"] for r in remaining];rows.append(row)
        # Useful contextual readings, not substitutes for EPS revisions or actual fund flows.
        contexts=[
          ("Fundamentals","AI infrastructure sentiment: SOXX/QQQ","SOXX","QQQ",20,1,"Market pricing only; not AI revenue or earnings revisions"),
          ("Fundamentals","Growth vs value sentiment: VUG/VTV","VUG","VTV",20,1,"Relative market pricing, not valuation or EPS data"),
          ("Fundamentals","Cyclical earnings sentiment: XLY/XLP","XLY","XLP",20,1,"Relative market pricing, not earnings revisions"),
          ("Macro","Inflation-sensitive proxy: TIP/IEF","TIP","IEF",20,0,"TIPS vs nominal Treasury relative return; not CPI or breakeven"),
          ("Macro","Oil price pressure: USO","USO",None,20,0,"Oil ETF return, not measured inflation"),
          ("Macro","Dollar / financial conditions: UUP","UUP",None,20,0,"Dollar ETF return, not policy expectations"),
          ("Options / liquidity","Tail-risk sentiment: VIX 5d change","^VIX",None,5,-1,"Implied volatility, not dealer gamma or flows"),
          ("Options / liquidity","Short-dated fear: VIX9D/VIX","^VIX9D","^VIX",5,-1,"Relative implied volatility change; not options positioning"),
        ]
        for group,name,k,base,n,sign,rule in contexts:
            row=emit(group,name,ret(k,n,base),"%",rule,"Yahoo Finance "+k+("/"+base if base else ""),direction=sign)
            if row:rows.append(row)
        day_return=ret(ticker,1)
        if day_return is not None:
            for lev in (3,2,-3):
                v=1000*lev*(lev-1)*day_return/100
                row=emit("Systematic flows",f"{lev:+d}x ETF rebalance per $1B AUM",v,"USD M","Underlying-equivalent scenario per hypothetical $1B starting AUM; excludes subscriptions, redemptions and actual hedges","Model: L*(L-1)*AUM*index return","MODEL",direction=1)
                if row:rows.append(row)
        for k,label,lag,maxage,n,unit in [
            ("CPIAUCSL","CPI year-on-year",45,100,12,"%"),("PCEPILFE","Core PCE year-on-year",45,100,12,"%"),
            ("UNRATE","Unemployment rate",45,100,0,"%"),("ICSA","Initial claims 4-week average",14,30,0,"claims"),
            ("T10YIE","10Y breakeven inflation",1,7,0,"%")]:
            z=inputs.get(k,pd.Series(dtype=float))
            z=z.loc[z.index<=date-pd.Timedelta(days=lag)] if len(z) else z
            if not len(z) or (date-z.index[-1]).days>maxage:continue
            v=float(z.iloc[-1])
            if n:v=float((v/z.iloc[-n-1]-1)*100) if len(z)>n and z.iloc[-n-1]!=0 else None
            if k=="ICSA":v=float(z.tail(4).mean()) if len(z)>=4 else None
            row=emit("Macro",label,v,unit,"Conservatively lagged release; not a consensus surprise",z.attrs.get("source","FRED "+k),"DIRECT",z.index[-1].strftime("%Y-%m-%d"))
            if row:rows.append(row)
        for row in rows:
            if row.get("data_kind"):continue
            row["data_kind"]="DIRECT" if row["source"].startswith(("FRED","https://fred","https://home.treasury")) else "MODEL" if row["source"].startswith(("Model","Scenario")) else "DIRECT" if row["source"].startswith("Calculated:") else "MARKET"
        covered={name for row in rows for name in row.get("replaces",[])}
        a["direct_coverage"]=a["coverage"]
        a["effective_coverage"]=round(100*sum(row["value"] is not None or row["name"] in covered for row in originals)/len(originals)) if originals else 0
    return checklist

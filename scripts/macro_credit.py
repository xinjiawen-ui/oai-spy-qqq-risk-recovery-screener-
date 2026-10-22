"""Public FRED macro & credit risk inputs, with explicit freshness and missingness.

FRED graph CSV is public and does not require an API token. Never forward-fill beyond 7
calendar days or fabricate observations. Network failure is represented as unavailable.
"""
import csv, datetime as dt, io, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
SERIES={
"DGS2":("US Treasury 2Y yield","pct"),
"DGS10":("US Treasury 10Y yield","pct"),
"DGS30":("US Treasury 30Y yield","pct"),
"BAMLH0A0HYM2":("US high yield option-adjusted spread","pct"),
"BAMLC0A0CM":("US investment grade option-adjusted spread","pct"),
"T10Y2Y":("10Y minus 2Y Treasury spread","pct"),
}
def get_one(code,now):
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?id="+code
    request=urllib.request.Request(url,headers={"User-Agent":"SPYQQQ-regime-research/1.0"})
    with urllib.request.urlopen(request,timeout=14) as response:
        data=response.read(1200000).decode("utf-8-sig")
    obs=[]
    for line in csv.DictReader(io.StringIO(data)):
        try:
            date=dt.date.fromisoformat(line.get("observation_date") or line.get("DATE"))
            value=float(line[code])
            if date<=now: obs.append((date,value))
        except (KeyError,TypeError,ValueError): continue
    obs.sort()
    if not obs: raise ValueError("No valid observations")
    latest=obs[-1]
    prior=next((x for x in reversed(obs[:-1]) if x[0]<=latest[0]-dt.timedelta(days=7)),None)
    age=(now-latest[0]).days
    return {"value":latest[1] if age<=7 else None,"date":latest[0].isoformat(),
            "age_calendar_days":age,"stale":age>7,
            "change_7d":round(latest[1]-prior[1],4) if prior and age<=7 else None,
            "unit":"percentage points","source":"FRED","url":url}
def collect(now=None):
    now=now or dt.datetime.now(dt.timezone.utc).date()
    output={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "description":"Public FRED close-based data. Latest published observations can lag markets. No intraday claims.",
            "series":{}}
    for code,(name,unit) in SERIES.items():
        try: item=get_one(code,now)
        except Exception as e:
            item={"value":None,"date":None,"stale":True,"change_7d":None,
                  "source":"FRED","error":type(e).__name__}
        item["name"]=name
        output["series"][code]=item
    return output
if __name__=="__main__":
    path=ROOT/"data"/"macro_credit.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(collect(),indent=2,allow_nan=False))
    print("Saved",path)

"""Direct credit diagnostic; experimental rules never alter production scores."""
import io
import urllib.request
import pandas as pd

SOURCE = 'https://fred.stlouisfed.org/graph/?g=1&id=BAMLH0A0HYM2'
CSV = 'https://fred.stlouisfed.org/graph/graph.csv?id=BAMLH0A0HYM2'

def diagnose(series, as_of):
    as_of = pd.Timestamp(as_of).normalize()
    x = pd.to_numeric(series, errors='coerce').dropna().sort_index()
    x.index = pd.to_datetime(x.index)
    x = x[~x.index.duplicated(keep='last')]
    # Conservative publication lag: exclude same-day observations.
    x = x[x.index < as_of]
    out = {'status': 'unavailable', 'source': SOURCE, 'series': 'BAMLH0A0HYM2',
           'units': 'percentage points', 'experimental': True,
           'publication_policy': 'Exclude same-day observations; historical vintages not available.'}
    if x.empty:
        return out
    date = x.index[-1]
    out.update(observation_date=date.strftime('%Y-%m-%d'), oas_pct=float(x.iloc[-1]),
               age_calendar_days=int((as_of-date).days))
    if (as_of-date).days > 7:
        out['status'] = 'stale'
        return out
    if len(x) < 21:
        return out
    change = float((x.iloc[-1]-x.iloc[-21])*100)
    # Only completed calendar months; never treat an incomplete month as month-end.
    months = x.resample('ME').last().dropna()
    months = months[months.index < as_of.replace(day=1)]
    monthly = None
    if len(months) >= 6:
        m = float(months.iloc[-1]); peak = float(months.iloc[-6:].max())
        monthly = {'month': months.index[-1].strftime('%Y-%m'), 'oas_pct': m,
                   'six_month_peak_pct': peak, 'compression_pp': peak-m,
                   'defensive_watch': bool(m >= 6.5 and peak-m < 2)}
    out.update(status='available', change_20_observations_bps=change,
               state='Credit stress' if x.iloc[-1] >= 6.5 else 'Widening' if change > 0 else 'Stable / tightening',
               monthly_rule=monthly)
    return out

def fetch_diagnostic(as_of):
    try:
        with urllib.request.urlopen(CSV, timeout=20) as response:
            frame = pd.read_csv(io.StringIO(response.read().decode()))
        series = pd.Series(pd.to_numeric(frame.iloc[:,1], errors='coerce').to_numpy(),
                           index=pd.to_datetime(frame.iloc[:,0]))
        return diagnose(series, as_of)
    except Exception:
        return {'status':'unavailable', 'source':SOURCE, 'experimental':True,
                'reason':'Direct FRED spread feed unavailable; ETF proxies remain separate.'}

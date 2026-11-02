"""Experimental six-state market-regime classifier; descriptive, not calibrated."""
REGIMES={
 "HEALTHY_BULL":("Healthy Bull","Maintain volatility-targeted core; buy orderly pullbacks."),
 "FRAGILE_BULL":("Fragile Bull","Monitor participation and reduce concentrated beta."),
 "DELEVERAGING":("Deleveraging / Risk-Off","Prioritize capital preservation; avoid automatic dip buys."),
 "BOTTOM_FORMATION":("Capitulation / Bottom Formation","Watch exhaustion; only small tactical entries with defined risk."),
 "EARLY_RECOVERY":("Early Recovery / Unconfirmed Rally","Scale tactically; require breadth and credit follow-through."),
 "CONFIRMED_RECOVERY":("Confirmed Recovery","Consider rebuilding core exposure within risk limits."),
 "UNCERTAIN":("Uncertain / Transitioning","Wait for better data or persistent confirmation.")
}
def classify(a):
    """Use existing, separately computed signals without changing legacy scores."""
    risk=a.get("risk_score"); rec=a.get("recovery_score")
    warn=a.get("warning_score"); rebound=a.get("rebound_v2") or {}
    early=rebound.get("early_score"); confirm=rebound.get("confirmation_score")
    credit=rebound.get("credit_gate"); breadth=rebound.get("breadth_gate")
    coverage=[a.get("risk_coverage",0),a.get("recovery_coverage",0),
              a.get("warning_coverage",0),rebound.get("early_coverage",0),
              rebound.get("confirmation_coverage",0)]
    if any(v is None or v<70 for v in coverage) or any(v is None for v in (risk,rec,warn,early,confirm)):
        key="UNCERTAIN"; reason="Insufficient observed inputs for a robust regime assignment."
    elif warn>=70 and risk>=50:
        key="DELEVERAGING"; reason="Broad leading warning and fragility are both elevated."
    elif risk>=55 and warn>=50 and early>=40:
        key="BOTTOM_FORMATION"; reason="Elevated stress coincides with tentative reversal evidence."
    elif risk>=50 and warn>=50:
        key="DELEVERAGING"; reason="Fragility and deleveraging warning remain elevated."
    elif confirm>=75 and rec>=60 and credit is True and breadth is True and warn<50:
        key="CONFIRMED_RECOVERY"; reason="Recovery, breadth and credit jointly confirm; trend persistence still needs validation."
    elif early>=40 and (confirm>=40 or rec>=45) and warn<70:
        key="EARLY_RECOVERY"; reason="Rebound evidence exists without complete recovery confirmation."
    elif risk<=25 and warn<30 and rec>=65 and confirm>=65:
        key="HEALTHY_BULL"; reason="Low fragility and broad recovery support."
    elif risk<50 and warn<50 and rec>=40:
        key="FRAGILE_BULL"; reason="Constructive conditions, but confirmation remains incomplete."
    else:
        key="UNCERTAIN"; reason="Conflicting stress and recovery indicators."
    label,action=REGIMES[key]
    return {"code":key,"label":label,"action":action,"reason":reason,
            "coverage_min_pct":min(coverage),"method_version":"six-regime-v1",
            "confidence":"descriptive only; not a calibrated probability"}

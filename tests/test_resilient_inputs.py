import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from comprehensive_checklist import build_checklist
from resilient_inputs import augment

class ResilientInputsTest(unittest.TestCase):
    def setUp(self):
        idx=pd.bdate_range("2025-01-01",periods=240)
        names=["SPY","QQQ","RSP","QQQE","SOXX","IWM","XLY","XLP","XLK","XLU","HYG","LQD","SHY","IEF","IEI","TIP","^VIX","^VIX3M","^VVIX","^TNX","^FVX"]
        self.close=pd.DataFrame({k:100*np.exp(np.arange(240)*(.0002+i*.00001)) for i,k in enumerate(names)},index=idx)
        self.close["^TNX"]=4+np.arange(240)*.001
        self.close["^FVX"]=3+np.arange(240)*.001
        self.assets={k:{"date":idx[-1].strftime("%Y-%m-%d")} for k in ("SPY","QQQ")}
        self.volume=pd.DataFrame({"SPY":1000,"QQQ":1000},index=idx)
    def test_failed_fred_families_have_fallbacks(self):
        raw=build_checklist(self.close,self.volume,self.assets,{}, {})
        out=augment(raw,self.close,self.assets,{})
        rows=out["assets"]["SPY"]["rows"]
        replacements={key:row for row in rows for key in row.get("replaces",[])}
        for key in ("HY OAS level","IG OAS level","2Y Treasury","5Y Treasury","10Y Treasury","10Y real Treasury","10Y–2Y curve"):
            self.assertIn(key,replacements)
        self.assertEqual(replacements["HY OAS level"]["data_kind"],"PROXY")
        self.assertEqual(replacements["HY OAS level"]["unit"],"%")
        self.assertIn("Not an OAS",replacements["HY OAS level"]["rule"])
        self.assertEqual(replacements["10Y Treasury"]["data_kind"],"ALTERNATE")
        self.assertEqual(replacements["10Y Treasury 5-observation change"]["unit"],"bp")
        self.assertGreater(out["assets"]["SPY"]["effective_coverage"],out["assets"]["SPY"]["coverage"])
    def test_missing_data_never_fabricated(self):
        self.close=self.close[["SPY","QQQ"]]
        raw=build_checklist(self.close,self.volume,self.assets,{}, {})
        out=augment(raw,self.close,self.assets,{})
        rows=out["assets"]["SPY"]["rows"]
        self.assertFalse(any("HY OAS level" in row.get("replaces",[]) for row in rows))
        self.assertIsNone(next(row["value"] for row in rows if row["name"]=="HY OAS level"))
    def test_leveraged_model_not_flow_observation(self):
        out=augment(build_checklist(self.close,self.volume,self.assets,{}, {}),self.close,self.assets,{})
        row=next(r for r in out["assets"]["QQQ"]["rows"] if r["name"]=="-3x ETF rebalance per $1B AUM")
        self.assertEqual(row["data_kind"],"MODEL")
        self.assertGreater(row["value"],0)

if __name__=="__main__":
    unittest.main()

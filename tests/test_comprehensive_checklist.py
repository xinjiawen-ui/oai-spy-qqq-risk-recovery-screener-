import sys
import unittest
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from comprehensive_checklist import build_checklist

class ChecklistTest(unittest.TestCase):
    def setUp(self):
        self.idx=pd.bdate_range("2025-01-01",periods=230)
        self.close=pd.DataFrame({k:100*np.exp(np.cumsum(np.sin(np.arange(230)/10)*.005+.001)) for k in ["SPY","QQQ","RSP","QQQE","SOXX","HYG","LQD","SHY","^VIX","^VIX3M"]},index=self.idx)
        self.vol=pd.DataFrame({"SPY":1000.,"QQQ":1000.},index=self.idx)
        self.assets={k:{"date":self.idx[-1].strftime("%Y-%m-%d")} for k in ["SPY","QQQ"]}
    def test_separate_and_manual(self):
        out=build_checklist(self.close,self.vol,self.assets,{}, {})
        self.assertTrue(out["experimental"])
        spy={r["name"]:r for r in out["assets"]["SPY"]["rows"]}
        qqq={r["name"]:r for r in out["assets"]["QQQ"]["rows"]}
        self.assertIn("RSP/SPY 5d relative return",spy)
        self.assertIn("QQQE/QQQ 5d relative return",qqq)
        self.assertEqual(spy["HY OAS 20-observation change"]["status"],"UNAVAILABLE")
        self.assertEqual(spy["2Y Treasury"]["status"],"UNAVAILABLE")
        self.assertTrue(all(r["status"]=="MANUAL / NOT OBSERVED" for r in out["manual"]))
    def test_missing_latest_and_fred_lag(self):
        self.close.loc[self.idx[-1],"QQQE"]=np.nan
        rate=pd.Series([4.0,99.0],index=[self.idx[-2],self.idx[-1]])
        out=build_checklist(self.close,self.vol,self.assets,{}, {"DGS2":rate})
        rows={r["name"]:r for r in out["assets"]["QQQ"]["rows"]}
        self.assertIsNone(rows["QQQE/QQQ 5d relative return"]["value"])
        self.assertEqual(rows["2Y Treasury"]["value"],4.0)
        self.assertEqual(rows["2Y Treasury"]["as_of"],self.idx[-2].strftime("%Y-%m-%d"))
    def test_rolloff_bounded(self):
        out=build_checklist(self.close,self.vol,self.assets,{}, {})
        rows={r["name"]:r for r in out["assets"]["SPY"]["rows"]}
        self.assertTrue(0<=rows["Illustrative 10% vol-target exposure"]["value"]<=100)
        self.assertIn("5d vol roll-off: -1%/day",rows)
        self.assertIn("5d vol roll-off: +0%/day",rows)
        self.assertIn("5d vol roll-off: +1%/day",rows)

if __name__=="__main__":
    unittest.main()

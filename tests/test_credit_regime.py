import pathlib, sys, unittest
import pandas as pd
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from credit_regime import diagnose

class CreditTests(unittest.TestCase):
    def series(self):
        return pd.Series(7., index=pd.bdate_range('2025-01-01','2026-10-30'))
    def test_excludes_current_and_future(self):
        x=self.series(); x.loc['2026-10-30']=99
        d=diagnose(x,'2026-10-30')
        self.assertEqual(d['oas_pct'],7.)
        self.assertEqual(d['observation_date'],'2026-10-29')
        self.assertEqual(d['monthly_rule']['month'],'2026-09')
        self.assertTrue(d['monthly_rule']['defensive_watch'])
    def test_compression_releases_rule(self):
        x=self.series();x.loc['2026-05-01':'2026-05-29']=10
        self.assertFalse(diagnose(x,'2026-10-30')['monthly_rule']['defensive_watch'])
    def test_stale_is_not_healthy(self):
        d=diagnose(self.series(),'2026-11-20')
        self.assertEqual(d['status'],'stale')
        self.assertNotIn('state',d)
    def test_empty(self):
        self.assertEqual(diagnose(pd.Series(dtype=float),'2026-10-30')['status'],'unavailable')

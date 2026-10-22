import datetime as dt
import io
import unittest
from unittest.mock import patch
from scripts import macro_credit

class TestMacroCredit(unittest.TestCase):
    def test_current_data_and_change(self):
        csv=b'observation_date,DGS10\n2026-10-01,4.10\n2026-10-08,4.25\n'
        response=io.BytesIO(csv)
        with patch.object(macro_credit.urllib.request,'urlopen',return_value=response):
            result=macro_credit.get_one('DGS10',dt.date(2026,10,09))
        self.assertAlmostEqual(result['value'],4.25)
        self.assertAlmostEqual(result['change_7d'],0.15)
        self.assertFalse(result['stale'])
    def test_stale_is_unavailable(self):
        csv=b'observation_date,DGS10\n2026-09-01,4.10\n2026-09-08,4.25\n'
        with patch.object(macro_credit.urllib.request,'urlopen',return_value=io.BytesIO(csv)):
            result=macro_credit.get_one('DGS10',dt.date(2026,10,09))
        self.assertIsNone(result['value'])
        self.assertTrue(result['stale'])
    def test_missing_or_network_error_does_not_generate_fake_value(self):
        with patch.object(macro_credit,'get_one',side_effect=OSError('offline')):
            data=macro_credit.collect(dt.date(2026,10,09))
        self.assertEqual(len(data['series']),len(macro_credit.SERIES))
        self.assertTrue(all(x['value'] is None for x in data['series'].values()))
    def test_skip_dot_missing_observations(self):
        csv=b'observation_date,DGS10\n2026-10-01,4.10\n2026-10-07,.\n2026-10-08,4.15\n'
        with patch.object(macro_credit.urllib.request,'urlopen',return_value=io.BytesIO(csv)):
            result=macro_credit.get_one('DGS10',dt.date(2026,10,09))
        self.assertAlmostEqual(result['value'],4.15)

if __name__=='__main__':
    unittest.main()

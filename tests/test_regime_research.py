import pathlib,sys,unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from regime_research import classify,conditional_statistics

class RegimeTests(unittest.TestCase):
    def test_classifications(self):
        self.assertEqual(classify(70,60,10),"Early rebound")
        self.assertEqual(classify(70,20,-10),"Market stress")
        self.assertEqual(classify(20,70,5),"Healthy expansion")
        self.assertEqual(classify(20,50,-5),"Potential deterioration")
        self.assertEqual(classify(np.nan,60,5),"Unavailable")
    def test_conditional_samples(self):
        df=pd.DataFrame({"regime":["Early rebound","Early rebound","Market stress"],
            "fragility_coverage":[100,100,100],"recovery_coverage":[100,100,100],
            "forward_5":[.1,-.1,.2]})
        s=conditional_statistics(df,5,"Early rebound")
        self.assertEqual(s["samples"],2)
        self.assertEqual(s["positive_probability_pct"],50)
        self.assertEqual(s["median_return_pct"],0)
    def test_no_samples(self):
        df=pd.DataFrame({"regime":["Market stress"],"fragility_coverage":[100],
                         "recovery_coverage":[100],"forward_5":[.1]})
        self.assertEqual(conditional_statistics(df,5,"Early rebound")["samples"],0)

if __name__=="__main__":unittest.main()

import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from market_regime import classify
def sample(**changes):
    a=dict(risk_score=20,recovery_score=75,warning_score=10,
           risk_coverage=100,recovery_coverage=100,warning_coverage=100,
           rebound_v2=dict(early_score=70,confirmation_score=85,
                           early_coverage=100,confirmation_coverage=100,
                           credit_gate=True,breadth_gate=True))
    a.update(changes)
    return a
class TestRegime(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(classify(sample())["code"],"CONFIRMED_RECOVERY")
    def test_deleveraging(self):
        self.assertEqual(classify(sample(risk_score=75,warning_score=80))["code"],"DELEVERAGING")
    def test_bottom(self):
        self.assertEqual(classify(sample(risk_score=60,warning_score=60))["code"],"BOTTOM_FORMATION")
    def test_missing(self):
        self.assertEqual(classify(sample(risk_coverage=40))["code"],"UNCERTAIN")
    def test_early(self):
        x=sample(rebound_v2=dict(early_score=65,confirmation_score=50,early_coverage=100,confirmation_coverage=100,credit_gate=False,breadth_gate=False))
        self.assertEqual(classify(x)["code"],"EARLY_RECOVERY")
if __name__=="__main__":unittest.main()

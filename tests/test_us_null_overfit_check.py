from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_null_overfit_check import empirical_pvalue, simulate_random_curves


class UsNullOverfitCheckTest(unittest.TestCase):
    def test_empirical_pvalue_counts_higher_null_as_bad(self) -> None:
        pvalue = empirical_pvalue(2.0, np.array([0.5, 1.0, 2.5, 3.0]))

        self.assertAlmostEqual(pvalue, 3 / 5)

    def test_simulate_random_curves_uses_relative_excess_not_absolute_return(self) -> None:
        periods = [
            pd.Series({"asset_returns": np.array([-0.05, -0.03, -0.01]), "benchmark_ret": -0.06}),
            pd.Series({"asset_returns": np.array([0.01, 0.02, 0.03]), "benchmark_ret": 0.0}),
        ]

        sims = simulate_random_curves(periods, top_n=2, n_iter=5, seed=7)

        self.assertEqual(len(sims), 5)
        self.assertTrue((sims["excess_return"] > 0).all())
        self.assertTrue((sims["win_excess"] > 0).all())


if __name__ == "__main__":
    unittest.main()

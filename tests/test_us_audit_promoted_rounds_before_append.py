from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_audit_promoted_rounds_before_append import audit_promoted_frames


class UsAuditPromotedRoundsBeforeAppendTest(unittest.TestCase):
    def test_audit_approves_fresh_positive_low_overlap_strategy(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    "策略编号": "策略一",
                    "candidate_id": "fresh",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    "实盘超基准收益": 0.02,
                }
            ]
        )
        holdings = pd.DataFrame(
            [
                {"run_id": "r1", "策略编号": "策略一", "股票代码": symbol}
                for symbol in ["A", "B", "C", "D", "E"]
            ]
        )
        current_holdings = pd.DataFrame(
            [
                {"monitor_key": "old", "股票代码": symbol}
                for symbol in ["X", "Y", "Z", "Q", "R"]
            ]
        )

        audit = audit_promoted_frames(strategies, holdings, current_holdings, 0.25, 0.40, 8, {5, 7, 10, 20})

        self.assertEqual(audit["approved"].tolist(), [True])
        self.assertEqual(audit["reason"].tolist(), ["approved"])

    def test_audit_rejects_drag_and_reused_crowded_holdings(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    "策略编号": "策略一",
                    "candidate_id": "crowded",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    "实盘超基准收益": 0.03,
                }
            ]
        )
        holdings = pd.DataFrame(
            [
                {"run_id": "r1", "策略编号": "策略一", "股票代码": symbol}
                for symbol in ["HON", "JEF", "DUOL", "VIRT", "ON"]
            ]
        )
        current_holdings = pd.DataFrame(
            [
                {"monitor_key": f"old{i}", "股票代码": symbol}
                for i in range(10)
                for symbol in ["HON", "JEF", "DUOL", "VIRT", "ON"]
            ]
        )

        audit = audit_promoted_frames(strategies, holdings, current_holdings, 0.25, 0.40, 8, {5, 7, 10, 20})

        self.assertEqual(audit["approved"].tolist(), [False])
        reason = audit.iloc[0]["reason"]
        self.assertIn("high_current_basket_overlap", reason)
        self.assertIn("high_current_stock_reuse", reason)
        self.assertIn("high_single_stock_crowding", reason)
        self.assertIn("drag_symbol_leakage", reason)


if __name__ == "__main__":
    unittest.main()

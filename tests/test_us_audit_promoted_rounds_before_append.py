from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_audit_promoted_rounds_before_append import audit_promoted_frames


STRATEGY_ID_COL = "\u7b56\u7565\u7f16\u53f7"
SYMBOL_COL = "\u80a1\u7968\u4ee3\u7801"
LIVE_EXCESS_COL = "\u5b9e\u76d8\u8d85\u57fa\u51c6\u6536\u76ca"


class UsAuditPromotedRoundsBeforeAppendTest(unittest.TestCase):
    def test_audit_approves_fresh_positive_low_overlap_strategy(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    STRATEGY_ID_COL: "strategy_one",
                    "candidate_id": "fresh",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    LIVE_EXCESS_COL: 0.02,
                }
            ]
        )
        holdings = pd.DataFrame(
            [{"run_id": "r1", STRATEGY_ID_COL: "strategy_one", SYMBOL_COL: symbol} for symbol in ["A", "B", "C", "D", "E"]]
        )
        current_holdings = pd.DataFrame([{"monitor_key": "old", SYMBOL_COL: symbol} for symbol in ["X", "Y", "Z", "Q", "R"]])

        audit = audit_promoted_frames(strategies, holdings, current_holdings, 0.25, 0.40, 8, {5, 7, 10, 20})

        self.assertEqual(audit["approved"].tolist(), [True])
        self.assertEqual(audit["reason"].tolist(), ["approved"])

    def test_audit_rejects_drag_and_reused_crowded_holdings(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    STRATEGY_ID_COL: "strategy_one",
                    "candidate_id": "crowded",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    LIVE_EXCESS_COL: 0.03,
                }
            ]
        )
        holdings = pd.DataFrame(
            [
                {"run_id": "r1", STRATEGY_ID_COL: "strategy_one", SYMBOL_COL: symbol}
                for symbol in ["HON", "JEF", "DUOL", "VIRT", "ON"]
            ]
        )
        current_holdings = pd.DataFrame(
            [
                {"monitor_key": f"old{i}", SYMBOL_COL: symbol}
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

    def test_audit_rejects_high_pairwise_return_correlation(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    STRATEGY_ID_COL: "strategy_one",
                    "candidate_id": "correlated",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    LIVE_EXCESS_COL: 0.03,
                }
            ]
        )
        holdings = pd.DataFrame(
            [
                {"run_id": "r1", STRATEGY_ID_COL: "strategy_one", SYMBOL_COL: symbol}
                for symbol in ["AAA", "BBB", "CCC", "DDD", "EEE"]
            ]
        )
        current_holdings = pd.DataFrame(columns=["monitor_key", SYMBOL_COL])
        return_correlation = pd.DataFrame(
            [
                [1.00, 0.92, 0.10, 0.10, 0.10],
                [0.92, 1.00, 0.10, 0.10, 0.10],
                [0.10, 0.10, 1.00, 0.10, 0.10],
                [0.10, 0.10, 0.10, 1.00, 0.10],
                [0.10, 0.10, 0.10, 0.10, 1.00],
            ],
            index=["AAA", "BBB", "CCC", "DDD", "EEE"],
            columns=["AAA", "BBB", "CCC", "DDD", "EEE"],
        )

        audit = audit_promoted_frames(
            strategies,
            holdings,
            current_holdings,
            0.25,
            0.40,
            8,
            {5, 7, 10, 20},
            return_correlation=return_correlation,
            max_pairwise_correlation=0.60,
        )

        self.assertEqual(audit["approved"].tolist(), [False])
        self.assertIn("high_pairwise_return_correlation", audit.iloc[0]["reason"])
        self.assertGreater(float(audit.iloc[0]["max_pairwise_correlation"]), 0.90)

    def test_audit_rejects_too_many_recent_weak_symbols(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    STRATEGY_ID_COL: "strategy_one",
                    "candidate_id": "weak_symbols",
                    "top_n_numeric": 5,
                    "rebalance_days_numeric": 20,
                    LIVE_EXCESS_COL: 0.04,
                }
            ]
        )
        holdings = pd.DataFrame(
            [
                {"run_id": "r1", STRATEGY_ID_COL: "strategy_one", SYMBOL_COL: symbol}
                for symbol in ["ALB", "MRVL", "AAA", "BBB", "CCC"]
            ]
        )
        current_holdings = pd.DataFrame(columns=["monitor_key", SYMBOL_COL])

        audit = audit_promoted_frames(
            strategies,
            holdings,
            current_holdings,
            0.25,
            0.40,
            8,
            {5, 7, 10, 20},
            weak_symbols={"ALB", "MRVL"},
            max_weak_symbol_hits=1,
        )

        self.assertEqual(audit["approved"].tolist(), [False])
        self.assertIn("recent_weak_symbol_concentration", audit.iloc[0]["reason"])
        self.assertEqual(int(audit.iloc[0]["weak_symbol_hits"]), 2)


if __name__ == "__main__":
    unittest.main()

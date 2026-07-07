import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from quant_agent_team.backtest_runner import _condition_match, _safe_formula_eval, _simulate_strategy
from quant_agent_team.evaluation import evaluate_backtest_result


class BacktestRuleTest(unittest.TestCase):
    def test_safe_formula_eval_supports_abs_and_min(self) -> None:
        class Row(dict):
            def to_dict(self):
                return dict(self)

        row = Row(ret_20d=0.2, volume_ratio_20d=3.5, volatility_20d=0.1)
        score = _safe_formula_eval(
            "0.55 * ret_20d + 0.30 * min(volume_ratio_20d, 3.0) - 0.15 * volatility_20d",
            row,
        )
        self.assertGreater(score, 0.9)

    def test_condition_match_supports_between(self) -> None:
        row = {"ret_5d": -0.06}
        self.assertTrue(
            _condition_match(
                {"field": "ret_5d", "operator": "between", "value": [-0.12, -0.04]},
                row,
            )
        )

    def test_stock_code_round_trip_should_preserve_leading_zeroes(self) -> None:
        import pandas as pd

        frame = pd.DataFrame({"stock_code": [1, "23", "600519"]})
        frame["stock_code"] = frame["stock_code"].astype("string").str.zfill(6)
        self.assertEqual(frame["stock_code"].tolist(), ["000001", "000023", "600519"])

    def test_evaluate_backtest_result_respects_user_thresholds(self) -> None:
        payload = {
            "generated_at": "2026-03-27T00:00:00",
            "spec_id": "spec-demo",
            "strategy_id": "demo",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "trade_count": 10,
            "trade_win_rate": 0.81,
            "annualized_return": 0.25,
            "total_return": 0.25,
            "max_drawdown": 0.18,
            "sharpe": 2.1,
            "average_holding_days": 5.0,
            "equity_curve_points": 250,
            "notes": [],
            "trades": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "backtest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            from quant_agent_team.backtest_runner import BacktestResult

            result = BacktestResult(**payload)
            evaluation = evaluate_backtest_result(result)
            self.assertTrue(evaluation.passed)

    def test_condition_match_supports_next_open_gap_field(self) -> None:
        row = {"next_open_gap_pct": 0.012}
        self.assertTrue(
            _condition_match(
                {"field": "next_open_gap_pct", "operator": "between", "value": [0.0, 0.02]},
                row,
            )
        )

    def test_condition_match_supports_theme_tag_contains(self) -> None:
        row = {"theme_tags": "{电力,电网设备}"}
        self.assertTrue(
            _condition_match(
                {"field": "theme_tags", "operator": "contains", "value": "电力"},
                row,
            )
        )

    def test_min_holding_days_before_exit_delays_rule_exit(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "stock_code": "000001",
                    "trade_date": pd.Timestamp("2025-01-02"),
                    "open_price": 10.0,
                    "high_price": 10.1,
                    "low_price": 9.9,
                    "close_price": 10.0,
                    "close_price_adj": 10.0,
                    "volume": 1000.0,
                    "turnover": 10000.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": None,
                    "limit_down_price": None,
                    "ret_1d": 0.0,
                    "ranking_score": 1.0,
                    "day_seq": 0,
                    "next_trade_date": pd.Timestamp("2025-01-03"),
                    "next_open_price": 10.0,
                    "next_open_gap_pct": 0.0,
                },
                {
                    "stock_code": "000001",
                    "trade_date": pd.Timestamp("2025-01-03"),
                    "open_price": 10.0,
                    "high_price": 10.2,
                    "low_price": 9.8,
                    "close_price": 10.1,
                    "close_price_adj": 10.1,
                    "volume": 1000.0,
                    "turnover": 10100.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": None,
                    "limit_down_price": None,
                    "ret_1d": 0.03,
                    "ranking_score": 1.0,
                    "day_seq": 1,
                    "next_trade_date": pd.Timestamp("2025-01-06"),
                    "next_open_price": 10.2,
                    "next_open_gap_pct": 0.00990099009900991,
                },
                {
                    "stock_code": "000001",
                    "trade_date": pd.Timestamp("2025-01-06"),
                    "open_price": 10.2,
                    "high_price": 10.4,
                    "low_price": 10.0,
                    "close_price": 10.3,
                    "close_price_adj": 10.3,
                    "volume": 1000.0,
                    "turnover": 10300.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": None,
                    "limit_down_price": None,
                    "ret_1d": 0.03,
                    "ranking_score": 1.0,
                    "day_seq": 2,
                    "next_trade_date": pd.NaT,
                    "next_open_price": float("nan"),
                    "next_open_gap_pct": float("nan"),
                },
            ]
        )
        spec = SimpleNamespace(
            spec_id="spec-test",
            strategy_id="demo",
            ranking_formula=SimpleNamespace(formula="1", sort_direction="desc"),
            position_rules=SimpleNamespace(
                max_positions=1,
                min_holding_days_before_exit=2,
                rebalance_frequency="daily",
            ),
            filters=[],
            entry_rules=[SimpleNamespace(rule_id="buy", logic="AND", conditions=[{"field": "ret_1d", "operator": "between", "value": [-0.01, 0.01]}])],
            exit_rules=[SimpleNamespace(rule_id="sell", logic="OR", conditions=[{"field": "ret_1d", "operator": ">=", "value": 0.02}])],
        )
        result = _simulate_strategy(spec, frame, initial_capital=100000.0)
        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades[0].exit_date, "2025-01-06")

    def test_simulate_strategy_respects_limit_up_exclusion(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "stock_code": "000001",
                    "trade_date": pd.Timestamp("2025-01-02"),
                    "open_price": 10.0,
                    "high_price": 11.0,
                    "low_price": 10.0,
                    "close_price": 11.0,
                    "close_price_adj": 11.0,
                    "volume": 1000.0,
                    "turnover": 11000.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": 11.0,
                    "limit_down_price": 9.0,
                    "ret_1d": 0.03,
                    "ranking_score": 2.0,
                    "day_seq": 0,
                    "next_trade_date": pd.Timestamp("2025-01-03"),
                    "next_open_price": 11.0,
                    "next_open_gap_pct": 0.0,
                },
                {
                    "stock_code": "000001",
                    "trade_date": pd.Timestamp("2025-01-03"),
                    "open_price": 11.0,
                    "high_price": 11.2,
                    "low_price": 10.9,
                    "close_price": 11.1,
                    "close_price_adj": 11.1,
                    "volume": 1000.0,
                    "turnover": 11100.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": 12.1,
                    "limit_down_price": 9.9,
                    "ret_1d": 0.01,
                    "ranking_score": 2.0,
                    "day_seq": 1,
                    "next_trade_date": pd.NaT,
                    "next_open_price": float("nan"),
                    "next_open_gap_pct": float("nan"),
                },
                {
                    "stock_code": "000002",
                    "trade_date": pd.Timestamp("2025-01-02"),
                    "open_price": 10.0,
                    "high_price": 10.5,
                    "low_price": 9.9,
                    "close_price": 10.3,
                    "close_price_adj": 10.3,
                    "volume": 1000.0,
                    "turnover": 10300.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": 11.0,
                    "limit_down_price": 9.0,
                    "ret_1d": 0.03,
                    "ranking_score": 1.0,
                    "day_seq": 0,
                    "next_trade_date": pd.Timestamp("2025-01-03"),
                    "next_open_price": 10.2,
                    "next_open_gap_pct": -0.009708737864077669,
                },
                {
                    "stock_code": "000002",
                    "trade_date": pd.Timestamp("2025-01-03"),
                    "open_price": 10.2,
                    "high_price": 10.6,
                    "low_price": 10.1,
                    "close_price": 10.4,
                    "close_price_adj": 10.4,
                    "volume": 1000.0,
                    "turnover": 10400.0,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "is_st": False,
                    "limit_up_price": 11.3,
                    "limit_down_price": 9.3,
                    "ret_1d": 0.01,
                    "ranking_score": 1.0,
                    "day_seq": 1,
                    "next_trade_date": pd.NaT,
                    "next_open_price": float("nan"),
                    "next_open_gap_pct": float("nan"),
                },
            ]
        )
        spec = SimpleNamespace(
            spec_id="spec-test",
            strategy_id="demo",
            ranking_formula=SimpleNamespace(formula="ranking_score", sort_direction="desc"),
            position_rules=SimpleNamespace(
                max_positions=1,
                min_holding_days_before_exit=0,
                rebalance_frequency="daily",
            ),
            filters=[],
            entry_rules=[SimpleNamespace(rule_id="buy", logic="AND", conditions=[{"field": "ret_1d", "operator": ">=", "value": 0.0}])],
            exit_rules=[SimpleNamespace(rule_id="sell", logic="OR", conditions=[{"field": "ret_1d", "operator": ">=", "value": 0.0}])],
            risk_constraints=SimpleNamespace(
                exclude_limit_up=True,
                exclude_limit_down=False,
            ),
        )
        result = _simulate_strategy(spec, frame, initial_capital=100000.0)
        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades[0].stock_code, "000002")

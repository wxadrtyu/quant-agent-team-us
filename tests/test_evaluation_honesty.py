from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.backtest_runner import BacktestResult
from quant_agent_team.evaluation import AcceptanceCriteria, evaluate_strategy


def _result(annualized_return: float, max_drawdown: float, trade_count: int) -> BacktestResult:
    return BacktestResult(
        generated_at="2026-06-27T00:00:00", spec_id="s", strategy_id="d",
        start_date="2023-06-28", end_date="2025-06-27", trade_count=trade_count,
        trade_win_rate=0.0, annualized_return=annualized_return, total_return=0.0,
        max_drawdown=max_drawdown, sharpe=0.0, average_holding_days=0.0,
        equity_curve_points=500,
    )


class EvaluationHonestyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = AcceptanceCriteria(min_annualized_return=0.30, max_drawdown_limit=0.30, min_trade_count=20)

    def test_passes_when_all_gates_met(self) -> None:
        ev = evaluate_strategy(_result(0.35, 0.25, 30), self.criteria)
        self.assertTrue(ev.passed)
        self.assertEqual(ev.failed_checks, [])

    def test_fails_on_low_return(self) -> None:
        ev = evaluate_strategy(_result(0.10, 0.25, 30), self.criteria)
        self.assertFalse(ev.passed)
        self.assertIn("annualized_return", ev.failed_checks)

    def test_fails_on_excess_drawdown(self) -> None:
        ev = evaluate_strategy(_result(0.40, 0.35, 30), self.criteria)
        self.assertIn("max_drawdown", ev.failed_checks)

    def test_fails_on_too_few_trades(self) -> None:
        ev = evaluate_strategy(_result(0.40, 0.20, 5), self.criteria)
        self.assertIn("trade_count", ev.failed_checks)

    def test_criteria_is_required(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_strategy(_result(0.40, 0.20, 30))  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()

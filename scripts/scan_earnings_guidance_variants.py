from __future__ import annotations

import copy
import json
from itertools import product
from pathlib import Path

from quant_agent_team.backtest_runner import load_backtest_frame, _simulate_strategy
from quant_agent_team.db import PostgresCli
from quant_agent_team.evaluation import evaluate_backtest_result
from quant_agent_team.workflow import ProjectWorkflow


ROOT = Path("/Users/laisicong/quant-agent-team-strategy")
BASE_SPEC_PATH = ROOT / "strategies/specs/spec-cn-a-earnings-guidance-post-confirmation-v1.json"
REPORT_PATH = ROOT / "reports/backtests/earnings_guidance_variant_scan_2026-03-30.json"


def _set_condition_value(spec, field: str, operator: str, value) -> None:
    for rule in [*spec.filters, *spec.entry_rules]:
        for condition in rule.conditions:
            if condition["field"] == field and condition["operator"] == operator:
                condition["value"] = value
                return
    raise KeyError(f"Condition not found for {field=} {operator=}")


def _variant_name(params: dict[str, object]) -> str:
    return (
        f"r1d_{params['ret_1d_low']}_{params['ret_1d_high']}"
        f"__gap_{params['next_open_gap_max']}"
        f"__r20hi_{params['ret_20d_high']}"
        f"__volhi_{params['volume_ratio_high']}"
        f"__slots_{params['max_positions']}"
        f"__hold_{params['min_hold_days_before_exit']}"
    )


def main() -> None:
    workflow = ProjectWorkflow(ROOT)
    base_spec = workflow.load_strategy_spec(BASE_SPEC_PATH)
    raw_spec = json.loads(BASE_SPEC_PATH.read_text(encoding="utf-8"))

    frame = load_backtest_frame(PostgresCli(), base_spec, start_date="2025-01-01", end_date="2026-03-29")

    stage_one = []
    for ret_1d_low, ret_1d_high, next_open_gap_max, ret_20d_high, volume_ratio_high in product(
        [-0.02, -0.01, 0.00],
        [0.05, 0.04],
        [0.04, 0.02],
        [0.35, 0.20],
        [2.0, 1.6],
    ):
        if ret_1d_low >= ret_1d_high:
            continue
        params = {
            "ret_1d_low": ret_1d_low,
            "ret_1d_high": ret_1d_high,
            "next_open_gap_max": next_open_gap_max,
            "ret_20d_high": ret_20d_high,
            "volume_ratio_high": volume_ratio_high,
            "max_positions": 2,
            "min_hold_days_before_exit": 0,
        }
        stage_one.append(params)

    stage_one_results = []
    for params in stage_one:
        spec = copy.deepcopy(base_spec)
        _set_condition_value(spec, "ret_1d", "between", [params["ret_1d_low"], params["ret_1d_high"]])
        _set_condition_value(spec, "next_open_gap_pct", "<=", params["next_open_gap_max"])
        _set_condition_value(spec, "ret_20d", "between", [-0.05, params["ret_20d_high"]])
        _set_condition_value(spec, "volume_ratio_20d", "between", [0.8, params["volume_ratio_high"]])
        result = _simulate_strategy(spec, frame, initial_capital=1_000_000.0)
        evaluation = evaluate_backtest_result(result)
        stage_one_results.append(
            {
                "variant": _variant_name(params),
                "params": params,
                "trade_count": result.trade_count,
                "trade_win_rate": result.trade_win_rate,
                "annualized_return": result.annualized_return,
                "max_drawdown": result.max_drawdown,
                "sharpe": result.sharpe,
                "passed": evaluation.passed,
            }
        )

    top_stage_one = sorted(
        stage_one_results,
        key=lambda item: (
            item["passed"],
            item["sharpe"],
            item["trade_win_rate"],
            item["annualized_return"],
            item["trade_count"],
        ),
        reverse=True,
    )[:8]

    final_results = []
    for base in top_stage_one:
        for max_positions, min_hold_days_before_exit in product([1, 2], [0, 1]):
            params = dict(base["params"])
            params["max_positions"] = max_positions
            params["min_hold_days_before_exit"] = min_hold_days_before_exit
            spec = copy.deepcopy(base_spec)
            _set_condition_value(spec, "ret_1d", "between", [params["ret_1d_low"], params["ret_1d_high"]])
            _set_condition_value(spec, "next_open_gap_pct", "<=", params["next_open_gap_max"])
            _set_condition_value(spec, "ret_20d", "between", [-0.05, params["ret_20d_high"]])
            _set_condition_value(spec, "volume_ratio_20d", "between", [0.8, params["volume_ratio_high"]])
            spec.position_rules.max_positions = max_positions
            spec.position_rules.min_holding_days_before_exit = min_hold_days_before_exit
            result = _simulate_strategy(spec, frame, initial_capital=1_000_000.0)
            evaluation = evaluate_backtest_result(result)
            final_results.append(
                {
                    "variant": _variant_name(params),
                    "params": params,
                    "trade_count": result.trade_count,
                    "trade_win_rate": result.trade_win_rate,
                    "annualized_return": result.annualized_return,
                    "max_drawdown": result.max_drawdown,
                    "sharpe": result.sharpe,
                    "passed": evaluation.passed,
                }
            )

    best = sorted(
        final_results,
        key=lambda item: (
            item["passed"],
            item["sharpe"],
            item["trade_win_rate"],
            item["annualized_return"],
            item["trade_count"],
        ),
        reverse=True,
    )[0]

    payload = {
        "base_spec_id": raw_spec["spec_id"],
        "scan_range": {"start_date": "2025-01-01", "end_date": "2026-03-29"},
        "stage_one_count": len(stage_one_results),
        "stage_two_count": len(final_results),
        "best_variant": best,
        "top_stage_one": top_stage_one,
        "top_final": sorted(
            final_results,
            key=lambda item: (
                item["passed"],
                item["sharpe"],
                item["trade_win_rate"],
                item["annualized_return"],
                item["trade_count"],
            ),
            reverse=True,
        )[:10],
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(best, ensure_ascii=False))


if __name__ == "__main__":
    main()

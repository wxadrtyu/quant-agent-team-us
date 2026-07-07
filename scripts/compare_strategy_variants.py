#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.backtest_runner import load_backtest_frame, _simulate_strategy
from quant_agent_team.db import PostgresCli
from quant_agent_team.evaluation import evaluate_backtest_result
from quant_agent_team.models import (
    DerivedFeatureSpec,
    ExecutionTiming,
    PositionRules,
    RankingFormula,
    ReviewSpec,
    RiskConstraints,
    StrategySpec,
    TradingRule,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare multiple strategy specs using a single read-only historical frame."
    )
    parser.add_argument(
        "--spec-path",
        dest="spec_paths",
        action="append",
        required=True,
        help="Absolute or repo-relative path to a strategy spec JSON. Repeat for multiple specs.",
    )
    parser.add_argument("--start-date", default="", help="Inclusive backtest start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", default="", help="Inclusive backtest end date, YYYY-MM-DD.")
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument(
        "--candidate-min-attention-level",
        type=float,
        default=0.0,
        help="If set, restrict the universe to stocks that reached at least this attention level in range.",
    )
    parser.add_argument(
        "--candidate-max-attention-rank",
        type=int,
        default=0,
        help="If set, restrict the universe to stocks that reached at most this attention rank in range.",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional JSON output path. If omitted, results are printed to stdout only.",
    )
    return parser.parse_args()


def load_spec(path: Path) -> StrategySpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StrategySpec(
        spec_id=payload["spec_id"],
        strategy_id=payload["strategy_id"],
        version=payload["version"],
        status=payload["status"],
        derived_from_brief_id=payload["derived_from_brief_id"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        market_inputs=payload.get("market_inputs", []),
        fundamental_inputs=payload.get("fundamental_inputs", []),
        event_inputs=payload.get("event_inputs", []),
        label_inputs=payload.get("label_inputs", []),
        derived_features=[DerivedFeatureSpec(**item) for item in payload.get("derived_features", [])],
        filters=[TradingRule(**item) for item in payload.get("filters", [])],
        entry_rules=[TradingRule(**item) for item in payload.get("entry_rules", [])],
        exit_rules=[TradingRule(**item) for item in payload.get("exit_rules", [])],
        ranking_formula=RankingFormula(**payload["ranking_formula"]) if payload.get("ranking_formula") else None,
        position_rules=PositionRules(**payload["position_rules"]) if payload.get("position_rules") else None,
        risk_constraints=RiskConstraints(**payload["risk_constraints"])
        if payload.get("risk_constraints")
        else None,
        execution_timing=ExecutionTiming(**payload.get("execution_timing", {})),
        review_spec=ReviewSpec(**payload.get("review_spec", {})),
    )


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def build_summary(spec: StrategySpec, frame, initial_capital: float) -> dict[str, object]:
    result = _simulate_strategy(spec, frame, initial_capital=initial_capital)
    evaluation = evaluate_backtest_result(result)
    return {
        "spec_id": spec.spec_id,
        "strategy_id": spec.strategy_id,
        "version": spec.version,
        "trade_count": result.trade_count,
        "trade_win_rate": result.trade_win_rate,
        "annualized_return": result.annualized_return,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "sharpe": result.sharpe,
        "average_holding_days": result.average_holding_days,
        "passed": evaluation.passed,
        "failed_checks": evaluation.failed_checks,
        "sample_trades": [
            {
                "stock_code": trade.stock_code,
                "signal_date": trade.signal_date,
                "entry_date": trade.entry_date,
                "exit_date": trade.exit_date,
                "return_pct": trade.return_pct,
            }
            for trade in result.trades[:20]
        ],
    }


def load_candidate_stock_codes(
    db: PostgresCli,
    start_date: str,
    end_date: str,
    min_attention_level: float,
    max_attention_rank: int,
) -> list[str]:
    where_clauses = ["attention_level IS NOT NULL"]
    if start_date:
        where_clauses.append(f"trade_date >= '{start_date}'::date")
    if end_date:
        where_clauses.append(f"trade_date <= '{end_date}'::date")
    if min_attention_level > 0:
        where_clauses.append(f"attention_level >= {float(min_attention_level)}")
    if max_attention_rank > 0:
        where_clauses.append(f"attention_rank <= {int(max_attention_rank)}")

    sql = (
        "SELECT DISTINCT stock_code "
        "FROM research_market_context_daily "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY stock_code"
    )
    process = subprocess.run(
        [str(db.config.psql_bin), db.config.db_url, "-Atqc", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().zfill(6) for line in process.stdout.splitlines() if line.strip()]


def main() -> int:
    args = parse_args()
    spec_paths = [resolve_path(item) for item in args.spec_paths]
    specs = [load_spec(path) for path in spec_paths]

    # Load once using the union-ready spec with the richest field set.
    anchor_spec = max(specs, key=lambda item: len(item.market_inputs) + len(item.label_inputs))
    pg = PostgresCli()
    candidate_stock_codes: list[str] = []
    if args.candidate_min_attention_level > 0 or args.candidate_max_attention_rank > 0:
        candidate_stock_codes = load_candidate_stock_codes(
            pg,
            args.start_date,
            args.end_date,
            args.candidate_min_attention_level,
            args.candidate_max_attention_rank,
        )
    frame = load_backtest_frame(
        pg,
        anchor_spec,
        start_date=args.start_date or None,
        end_date=args.end_date or None,
        stock_codes=candidate_stock_codes or None,
    )

    payload = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "candidate_stock_count": len(candidate_stock_codes),
        "loaded_rows": len(frame),
        "specs": [build_summary(spec, frame, args.initial_capital) for spec in specs],
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output_path:
        output_path = resolve_path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

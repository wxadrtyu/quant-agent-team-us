from __future__ import annotations

import argparse
from pathlib import Path

from .workflow import ProjectWorkflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="quant-agent-team scaffold CLI")
    parser.add_argument("--root", default=".", help="Project root path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    kpi = subparsers.add_parser("new-kpi", help="Create a KPI version stub")
    kpi.add_argument("--win-rate", type=float, required=True)
    kpi.add_argument("--annual-return", type=float, required=True)
    kpi.add_argument("--max-drawdown", type=float, required=True)
    kpi.add_argument("--notes", default="")

    brief = subparsers.add_parser("new-brief", help="Create a strategy brief stub")
    brief.add_argument("--strategy-id", required=True)
    brief.add_argument("--title", required=True)
    brief.add_argument("--thesis", required=True)

    spec = subparsers.add_parser("new-spec", help="Create a strategy spec stub")
    spec.add_argument("--strategy-id", required=True)
    spec.add_argument("--spec-id", required=True)
    spec.add_argument("--title-hint", default="")
    spec.add_argument("--market-input", action="append", default=[])
    spec.add_argument("--fundamental-input", action="append", default=[])
    spec.add_argument("--event-input", action="append", default=[])
    spec.add_argument("--label-input", action="append", default=[])
    spec.add_argument("--derived-feature", action="append", default=[])

    sync = subparsers.add_parser("sync-data", help="Create a strategy data sync plan")
    sync.add_argument("--spec-path", required=True)
    sync.add_argument("--available", action="append", default=[])

    ingest = subparsers.add_parser(
        "base-incremental-ingest",
        aliases=["base-ingest-plan"],
        help="Run base incremental ingest and write ingestion summary and inventory",
    )
    ingest.add_argument("--source-dir", default="")
    ingest.add_argument("--constraints-dir", default="")
    ingest.add_argument("--sample-size", type=int, default=50)

    bootstrap = subparsers.add_parser(
        "bootstrap-ingest",
        help="Bootstrap raw market data from stock_history into PostgreSQL",
    )
    bootstrap.add_argument("--source-dir", default="")
    bootstrap.add_argument("--limit-files", type=int, default=0)

    daily = subparsers.add_parser(
        "daily-update",
        help="Run the daily incremental update and archive a timestamped summary",
    )
    daily.add_argument("--source-dir", default="")
    daily.add_argument("--constraints-dir", default="")
    daily.add_argument("--sample-size", type=int, default=50)

    refresh = subparsers.add_parser(
        "refresh-features",
        help="Refresh derived research features from normalized market data",
    )
    refresh.add_argument("--stock-code", action="append", default=[])

    quality = subparsers.add_parser(
        "data-quality-report",
        help="Build a data quality report from market, conflict, and feature tables",
    )

    repair_sync = subparsers.add_parser(
        "repair-normalized-sync",
        help="Repair normalized_market_daily rows whose source_raw_line_hash drifts from raw_market_daily",
    )
    repair_sync.add_argument("--stock-code", action="append", default=[])
    repair_sync.add_argument("--batch-size", type=int, default=250)

    market_context = subparsers.add_parser(
        "refresh-market-context",
        help="Fetch and upsert northbound and attention context data",
    )
    market_context.add_argument("--stock-code", action="append", default=[])
    market_context.add_argument("--top-n-attention", type=int, default=100)
    market_context.add_argument("--attention-start-date", default="")
    market_context.add_argument("--notice-start-date", default="")
    market_context.add_argument("--context-start-date", default="2025-01-01")
    market_context.add_argument("--theme-snapshot-date", default="")
    market_context.add_argument("--include-concepts", action="store_true")
    market_context.add_argument("--max-concepts", type=int, default=60)
    market_context.add_argument("--max-industries", type=int, default=0)

    review = subparsers.add_parser("new-review", help="Create a review stub")
    review.add_argument("--strategy-id", required=True)

    backtest = subparsers.add_parser("run-backtest", help="Run a minimal historical backtest")
    backtest.add_argument("--spec-path", required=True)
    backtest.add_argument("--start-date", default="")
    backtest.add_argument("--end-date", default="")
    backtest.add_argument("--initial-capital", type=float, default=1000000.0)

    evaluate = subparsers.add_parser("evaluate-backtest", help="Evaluate a backtest against KPI gates")
    evaluate.add_argument("--backtest-path", required=True)
    evaluate.add_argument("--min-win-rate", type=float, default=0.80)
    evaluate.add_argument("--min-annual-return", type=float, default=0.20)
    evaluate.add_argument("--max-drawdown", type=float, default=0.30)
    evaluate.add_argument("--min-sharpe", type=float, default=2.0)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workflow = ProjectWorkflow(Path(args.root).resolve())

    if args.command == "new-kpi":
        path = workflow.create_kpi_version(
            trade_win_rate=args.win_rate,
            annualized_return=args.annual_return,
            max_drawdown_limit=args.max_drawdown,
            notes=args.notes,
        )
        print(path)
        return 0

    if args.command == "new-brief":
        path = workflow.create_strategy_brief(
            strategy_id=args.strategy_id,
            title=args.title,
            thesis=args.thesis,
        )
        print(path)
        return 0

    if args.command == "new-spec":
        path = workflow.create_strategy_spec(
            strategy_id=args.strategy_id,
            spec_id=args.spec_id,
            title_hint=args.title_hint,
            market_inputs=args.market_input,
            fundamental_inputs=args.fundamental_input,
            event_inputs=args.event_input,
            label_inputs=args.label_input,
            derived_features=args.derived_feature,
        )
        print(path)
        return 0

    if args.command == "sync-data":
        spec_path = Path(args.spec_path).resolve()
        spec = workflow.load_strategy_spec(spec_path)
        path = workflow.plan_strategy_data_sync(spec, available_items=args.available)
        print(path)
        return 0

    if args.command in {"base-incremental-ingest", "base-ingest-plan"}:
        path = workflow.run_base_incremental_ingest(
            source_dir=Path(args.source_dir).resolve() if args.source_dir else None,
            sample_size=args.sample_size,
            constraints_dir=Path(args.constraints_dir).resolve() if args.constraints_dir else None,
        )
        print(path)
        return 0

    if args.command == "bootstrap-ingest":
        path = workflow.run_bootstrap_ingest(
            source_dir=Path(args.source_dir).resolve() if args.source_dir else None,
            limit_files=args.limit_files or None,
        )
        print(path)
        return 0

    if args.command == "daily-update":
        path = workflow.run_daily_update(
            source_dir=Path(args.source_dir).resolve() if args.source_dir else None,
            sample_size=args.sample_size,
            constraints_dir=Path(args.constraints_dir).resolve() if args.constraints_dir else None,
        )
        print(path)
        return 0

    if args.command == "refresh-features":
        path = workflow.run_feature_refresh(stock_codes=args.stock_code)
        print(path)
        return 0

    if args.command == "data-quality-report":
        path = workflow.run_data_quality_report()
        print(path)
        return 0

    if args.command == "repair-normalized-sync":
        path = workflow.repair_normalized_sync(
            stock_codes=args.stock_code,
            batch_size=args.batch_size,
        )
        print(path)
        return 0

    if args.command == "refresh-market-context":
        path = workflow.run_market_context_refresh(
            stock_codes=args.stock_code,
            top_n_attention=args.top_n_attention,
            attention_start_date=args.attention_start_date or None,
            notice_start_date=args.notice_start_date or None,
            context_start_date=args.context_start_date or None,
            theme_snapshot_date=args.theme_snapshot_date or None,
            include_concepts=bool(args.include_concepts),
            max_concepts=args.max_concepts,
            max_industries=args.max_industries or None,
        )
        print(path)
        return 0

    if args.command == "new-review":
        path = workflow.create_review_stub(args.strategy_id)
        print(path)
        return 0

    if args.command == "run-backtest":
        path = workflow.run_backtest(
            spec_path=Path(args.spec_path).resolve(),
            start_date=args.start_date or None,
            end_date=args.end_date or None,
            initial_capital=args.initial_capital,
        )
        print(path)
        return 0

    if args.command == "evaluate-backtest":
        path = workflow.evaluate_backtest(
            backtest_path=Path(args.backtest_path).resolve(),
            min_trade_win_rate=args.min_win_rate,
            min_annualized_return=args.min_annual_return,
            max_drawdown_limit=args.max_drawdown,
            min_sharpe=args.min_sharpe,
        )
        print(path)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import json
import math
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .cost_model import CostModel
from .db import PostgresCli
from .models import StrategySpec, TradingRule


SAFE_EVAL_GLOBALS = {
    "__builtins__": {},
    "abs": abs,
    "min": min,
    "max": max,
    "math": math,
}


@dataclass
class BacktestTrade:
    stock_code: str
    signal_date: str
    entry_date: str
    entry_price: float
    exit_signal_date: str
    exit_date: str
    exit_price: float
    holding_days: int
    return_pct: float
    exit_reason: str


@dataclass
class BacktestResult:
    generated_at: str
    spec_id: str
    strategy_id: str
    start_date: str
    end_date: str
    trade_count: int
    trade_win_rate: float
    annualized_return: float
    total_return: float
    max_drawdown: float
    sharpe: float
    average_holding_days: float
    equity_curve_points: int
    notes: List[str] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["trades"] = [asdict(trade) for trade in self.trades]
        return payload


def run_backtest(
    spec: StrategySpec,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_capital: float = 1_000_000.0,
    db: PostgresCli | None = None,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    pg = db or PostgresCli()
    pg.ensure_database()
    pg.ensure_schema()
    frame = load_backtest_frame(pg, spec, start_date=start_date, end_date=end_date)
    if frame.empty:
        raise ValueError("No market/feature rows available for the requested backtest range.")
    return _simulate_strategy(spec, frame, initial_capital=initial_capital, cost_model=cost_model)


def load_backtest_frame(
    db: PostgresCli,
    spec: StrategySpec,
    start_date: str | None = None,
    end_date: str | None = None,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame:
    required_features = sorted({feature.feature_name for feature in spec.derived_features})
    market_context_fields = sorted(
        {
            name
            for name in [*spec.market_inputs, *spec.label_inputs]
            if name
            and name
            in {
                "industry_name",
                "sector_name",
                "theme_tags",
                "northbound_hold_value",
                "northbound_estimated_increase_value",
                "northbound_holding_change_1d",
                "northbound_holding_change_5d",
                "northbound_net_flow_proxy_1d",
                "northbound_net_flow_proxy_5d",
                "attention_rank",
                "attention_level",
                "attention_change_3d",
                "attention_change_5d",
                "attention_proxy_rank",
                "attention_proxy_level",
                "attention_proxy_change_3d",
                "attention_proxy_change_5d",
                "attention_new_fans_ratio",
                "attention_loyal_fans_ratio",
                "theme_breadth_score",
                "policy_event_tag",
                "announcement_event_tag",
                "announcement_count_1d",
                "earnings_event_tag",
                "earnings_event_direction",
                "earnings_event_strength_score",
            }
        }
    )
    feature_columns = ",\n  ".join(f"feature.{name}" for name in required_features)
    context_selectors: list[str] = []
    for name in market_context_fields:
        if name in {
            "announcement_event_tag",
            "policy_event_tag",
            "announcement_count_1d",
            "earnings_event_tag",
            "earnings_event_direction",
            "earnings_event_strength_score",
        }:
            context_selectors.append(f"COALESCE(context.{name}, notice.{name}) AS {name}")
        else:
            context_selectors.append(f"context.{name}")
    context_columns = ",\n  ".join(context_selectors)
    where_clauses = ["market.stock_code ~ '^[0-9]{6}$'"]
    if start_date:
        where_clauses.append(f"market.trade_date >= '{start_date}'::date")
    if end_date:
        where_clauses.append(f"market.trade_date <= '{end_date}'::date")
    if stock_codes:
        normalized_codes = sorted({str(code).zfill(6) for code in stock_codes if str(code).strip()})
        if normalized_codes:
            quoted_codes = ", ".join(f"'{code}'" for code in normalized_codes)
            where_clauses.append(f"market.stock_code IN ({quoted_codes})")
    where_sql = " AND ".join(where_clauses)
    query = f"""
WITH notice_daily AS (
  SELECT
    stock_code,
    trade_date,
    STRING_AGG(DISTINCT announcement_event_tag, '|' ORDER BY announcement_event_tag)
      FILTER (WHERE announcement_event_tag IS NOT NULL AND announcement_event_tag <> '') AS announcement_event_tag,
    STRING_AGG(DISTINCT policy_event_tag, '|' ORDER BY policy_event_tag)
      FILTER (WHERE policy_event_tag IS NOT NULL AND policy_event_tag <> '') AS policy_event_tag,
    STRING_AGG(DISTINCT earnings_event_tag, '|' ORDER BY earnings_event_tag)
      FILTER (WHERE earnings_event_tag IS NOT NULL AND earnings_event_tag <> '') AS earnings_event_tag,
    STRING_AGG(DISTINCT earnings_event_direction, '|' ORDER BY earnings_event_direction)
      FILTER (WHERE earnings_event_direction IS NOT NULL AND earnings_event_direction <> '') AS earnings_event_direction,
    MAX(earnings_event_strength_score) AS earnings_event_strength_score,
    COUNT(*)::integer AS announcement_count_1d
  FROM raw_notice_event_daily
  GROUP BY stock_code, trade_date
)
SELECT
  market.stock_code,
  market.trade_date,
  market.open_price,
  market.high_price,
  market.low_price,
  market.close_price,
  market.close_price_adj,
  market.volume,
  market.turnover,
  market.adj_factor,
  market.is_suspended,
  market.is_st,
  market.limit_up_price,
  market.limit_down_price{"," if feature_columns or context_columns else ""}
  {context_columns}{"," if feature_columns and context_columns else ""}
  {feature_columns}
FROM normalized_market_daily AS market
LEFT JOIN research_market_context_daily AS context
  ON context.stock_code = market.stock_code
 AND context.trade_date = market.trade_date
LEFT JOIN notice_daily AS notice
  ON notice.stock_code = market.stock_code
 AND notice.trade_date = market.trade_date
LEFT JOIN research_feature_daily AS feature
  ON feature.stock_code = market.stock_code
 AND feature.trade_date = market.trade_date
WHERE {where_sql}
ORDER BY market.trade_date, market.stock_code
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as handle:
        csv_path = Path(handle.name)
    try:
        copy_sql = f"\\copy ({query}) TO '{csv_path}' WITH CSV HEADER"
        subprocess.run(
            [str(db.config.psql_bin), db.config.db_url, "-v", "ON_ERROR_STOP=1", "-c", copy_sql],
            check=True,
            capture_output=True,
            text=True,
        )
        frame = pd.read_csv(
            csv_path,
            dtype={
                "stock_code": "string",
                "is_suspended": "string",
                "is_st": "string",
            },
            low_memory=False,
        )
    finally:
        csv_path.unlink(missing_ok=True)

    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["stock_code"] = frame["stock_code"].astype("string").str.zfill(6)
    string_context_fields = {
        "industry_name",
        "sector_name",
        "theme_tags",
        "announcement_event_tag",
        "policy_event_tag",
        "earnings_event_tag",
        "earnings_event_direction",
    }
    numeric_cols = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "close_price_adj",
        "volume",
        "turnover",
        "adj_factor",
        *required_features,
        *[
            name
            for name in market_context_fields
            if name not in string_context_fields
        ],
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    for col in ["is_suspended", "is_st"]:
        if col in frame.columns:
            frame[col] = frame[col].map(lambda value: str(value).lower() == "true" if pd.notna(value) else False)
    frame = frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    frame["next_trade_date"] = frame.groupby("stock_code")["trade_date"].shift(-1)
    frame["next_open_price"] = frame.groupby("stock_code")["open_price"].shift(-1)
    frame["next_open_gap_pct"] = (
        frame["next_open_price"] / frame["close_price_adj"] - 1.0
    )
    frame["day_seq"] = frame.groupby("stock_code").cumcount()
    return frame


def _simulate_strategy(
    spec: StrategySpec,
    frame: pd.DataFrame,
    initial_capital: float,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    costs = cost_model if cost_model is not None else CostModel()
    frame = frame.copy()
    frame["ranking_score"] = frame.apply(
        lambda row: _safe_formula_eval(spec.ranking_formula.formula if spec.ranking_formula else "0", row),
        axis=1,
    )
    max_positions = spec.position_rules.max_positions if spec.position_rules else 5
    min_holding_days_before_exit = (
        spec.position_rules.min_holding_days_before_exit if spec.position_rules else 0
    )
    rebalance_frequency = spec.position_rules.rebalance_frequency if spec.position_rules else "daily"

    cash = initial_capital
    open_positions: Dict[str, Dict[str, Any]] = {}
    pending_entries: Dict[pd.Timestamp, List[Dict[str, Any]]] = {}
    pending_exits: Dict[pd.Timestamp, List[Dict[str, Any]]] = {}
    equity_points: List[Dict[str, Any]] = []
    trades: List[BacktestTrade] = []

    for trade_date, day_frame in frame.groupby("trade_date", sort=True):
        day_frame = day_frame.sort_values("stock_code").reset_index(drop=True)

        for order in pending_exits.pop(trade_date, []):
            stock_code = order["stock_code"]
            position = open_positions.pop(stock_code, None)
            if position is None:
                continue
            row = _row_for_stock(day_frame, stock_code)
            raw_exit_price = _numeric(row.get("open_price")) if row is not None else position["last_close"]
            exit_price = costs.exit_fill_price(raw_exit_price)
            proceeds = position["shares"] * exit_price
            cash += proceeds
            cash -= costs.commission(proceeds)
            holding_days = int(order["signal_day_seq"] - position["entry_day_seq"])
            return_pct = (exit_price / position["entry_price"]) - 1 if position["entry_price"] else 0.0
            trades.append(
                BacktestTrade(
                    stock_code=stock_code,
                    signal_date=position["signal_date"].strftime("%Y-%m-%d"),
                    entry_date=position["entry_date"].strftime("%Y-%m-%d"),
                    entry_price=position["entry_price"],
                    exit_signal_date=order["exit_signal_date"].strftime("%Y-%m-%d"),
                    exit_date=trade_date.strftime("%Y-%m-%d"),
                    exit_price=exit_price,
                    holding_days=holding_days,
                    return_pct=return_pct,
                    exit_reason=order["exit_reason"],
                )
            )

        for order in pending_entries.pop(trade_date, []):
            if len(open_positions) >= max_positions:
                continue
            row = _row_for_stock(day_frame, order["stock_code"])
            if row is None:
                continue
            raw_entry_price = _numeric(row.get("open_price"))
            if not raw_entry_price or not np.isfinite(raw_entry_price):
                continue
            entry_price = costs.entry_fill_price(raw_entry_price)
            slot_capital = cash / max(1, max_positions - len(open_positions))
            if slot_capital <= 0:
                continue
            shares = slot_capital / entry_price
            cash -= slot_capital
            cash -= costs.commission(slot_capital)
            open_positions[order["stock_code"]] = {
                "stock_code": order["stock_code"],
                "signal_date": order["signal_date"],
                "entry_date": trade_date,
                "entry_price": entry_price,
                "shares": shares,
                "entry_day_seq": int(row["day_seq"]),
                "last_close": _numeric(row.get("close_price_adj")) or entry_price,
            }

        current_equity = cash
        for stock_code, position in list(open_positions.items()):
            row = _row_for_stock(day_frame, stock_code)
            if row is None:
                current_equity += position["shares"] * position["last_close"]
                continue
            close_price = _numeric(row.get("close_price_adj")) or position["last_close"]
            position["last_close"] = close_price
            current_equity += position["shares"] * close_price

        equity_points.append({"trade_date": trade_date, "equity": current_equity})

        rebalance_allowed = _is_rebalance_day(trade_date, rebalance_frequency)

        for stock_code, position in list(open_positions.items()):
            row = _row_for_stock(day_frame, stock_code)
            if row is None:
                continue
            holding_days_so_far = int(row["day_seq"]) - int(position["entry_day_seq"])
            if holding_days_so_far < min_holding_days_before_exit:
                continue
            if _rules_match(spec.exit_rules, row):
                next_trade_date = row.get("next_trade_date")
                if pd.isna(next_trade_date):
                    continue
                pending_exits.setdefault(next_trade_date, []).append(
                    {
                        "stock_code": stock_code,
                        "exit_signal_date": trade_date,
                        "signal_day_seq": int(row["day_seq"]),
                        "exit_reason": spec.exit_rules[0].rule_id if spec.exit_rules else "rule_exit",
                    }
                )

        if not rebalance_allowed:
            continue

        available_slots = max_positions - len(open_positions)
        if available_slots <= 0:
            continue

        candidates = []
        for _, row in day_frame.iterrows():
            stock_code = str(row["stock_code"])
            if stock_code in open_positions:
                continue
            if _boolish(row.get("is_suspended")) or _boolish(row.get("is_st")):
                continue
            if _violates_risk_entry_constraints(spec, row):
                continue
            if not _rules_match(spec.filters, row):
                continue
            if not _rules_match(spec.entry_rules, row):
                continue
            if pd.isna(row.get("next_trade_date")) or pd.isna(row.get("next_open_price")):
                continue
            candidates.append(row)

        candidates = sorted(
            candidates,
            key=lambda row: float(row.get("ranking_score", 0.0)),
            reverse=(spec.ranking_formula.sort_direction if spec.ranking_formula else "desc") == "desc",
        )

        for row in candidates[:available_slots]:
            next_trade_date = row["next_trade_date"]
            pending_entries.setdefault(next_trade_date, []).append(
                {
                    "stock_code": str(row["stock_code"]),
                    "signal_date": trade_date,
                }
            )

    last_date = frame["trade_date"].max()
    for stock_code, position in list(open_positions.items()):
        trades.append(
            BacktestTrade(
                stock_code=stock_code,
                signal_date=position["signal_date"].strftime("%Y-%m-%d"),
                entry_date=position["entry_date"].strftime("%Y-%m-%d"),
                entry_price=position["entry_price"],
                exit_signal_date=last_date.strftime("%Y-%m-%d"),
                exit_date=last_date.strftime("%Y-%m-%d"),
                exit_price=position["last_close"],
                holding_days=max(0, int((last_date - position["entry_date"]).days)),
                return_pct=(position["last_close"] / position["entry_price"]) - 1 if position["entry_price"] else 0.0,
                exit_reason="forced_end_of_test",
            )
        )

    equity = pd.DataFrame(equity_points)
    equity = equity.sort_values("trade_date").reset_index(drop=True)
    equity["daily_return"] = equity["equity"].pct_change().fillna(0.0)
    equity["cummax"] = equity["equity"].cummax()
    equity["drawdown"] = equity["equity"] / equity["cummax"] - 1.0

    total_return = (equity.iloc[-1]["equity"] / initial_capital) - 1.0
    num_days = max(len(equity), 1)
    annualized_return = (equity.iloc[-1]["equity"] / initial_capital) ** (252 / num_days) - 1.0
    daily_std = float(equity["daily_return"].std(ddof=0))
    sharpe = 0.0 if daily_std == 0 else float(equity["daily_return"].mean() / daily_std * math.sqrt(252))
    trade_returns = [trade.return_pct for trade in trades]
    trade_win_rate = 0.0 if not trade_returns else float(sum(r > 0 for r in trade_returns) / len(trade_returns))
    avg_holding = 0.0 if not trades else float(sum(trade.holding_days for trade in trades) / len(trades))

    return BacktestResult(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        spec_id=spec.spec_id,
        strategy_id=spec.strategy_id,
        start_date=equity.iloc[0]["trade_date"].strftime("%Y-%m-%d"),
        end_date=equity.iloc[-1]["trade_date"].strftime("%Y-%m-%d"),
        trade_count=len(trades),
        trade_win_rate=trade_win_rate,
        annualized_return=float(annualized_return),
        total_return=float(total_return),
        max_drawdown=float(abs(equity["drawdown"].min())),
        sharpe=sharpe,
        average_holding_days=avg_holding,
        equity_curve_points=len(equity),
        notes=[
            "Signals are generated after close and executed at next open.",
            "Portfolio uses fixed-slot capital allocation with daily mark-to-market.",
        ],
        trades=trades[:500],
    )


def _safe_formula_eval(formula: str, row: pd.Series) -> float:
    locals_dict = {key: _numeric(value) for key, value in row.to_dict().items()}
    try:
        value = eval(formula, SAFE_EVAL_GLOBALS, locals_dict)
    except Exception:
        return 0.0
    return float(value) if value is not None and np.isfinite(value) else 0.0


def _rules_match(rules: List[TradingRule], row: pd.Series) -> bool:
    if not rules:
        return True
    return all(_rule_match(rule, row) for rule in rules)


def _rule_match(rule: TradingRule, row: pd.Series) -> bool:
    outcomes = [_condition_match(condition, row) for condition in rule.conditions]
    return all(outcomes) if rule.logic == "AND" else any(outcomes)


def _condition_match(condition: Dict[str, Any], row: pd.Series) -> bool:
    left = row.get(condition["field"])
    operator = condition["operator"]
    right = condition.get("value")
    value_from = condition.get("value_from")
    if value_from:
        right = row.get(value_from)

    left_num = _numeric(left)
    right_num = _numeric(right)

    if operator == ">":
        return left_num > right_num
    if operator == ">=":
        return left_num >= right_num
    if operator == "<":
        return left_num < right_num
    if operator == "<=":
        return left_num <= right_num
    if operator == "=":
        return left == right
    if operator == "!=":
        return left != right
    if operator == "between":
        if not isinstance(right, list) or len(right) != 2:
            return False
        low, high = _numeric(right[0]), _numeric(right[1])
        return low <= left_num <= high
    if operator == "is_true":
        return _boolish(left)
    if operator == "is_false":
        return not _boolish(left)
    if operator == "in":
        return left in (right or [])
    if operator == "not_in":
        return left not in (right or [])
    if operator == "contains":
        return str(right) in str(left)
    if operator == "not_contains":
        return str(right) not in str(left)
    return False


def _row_for_stock(day_frame: pd.DataFrame, stock_code: str) -> pd.Series | None:
    matched = day_frame.loc[day_frame["stock_code"] == stock_code]
    if matched.empty:
        return None
    return matched.iloc[0]


def _violates_risk_entry_constraints(spec: StrategySpec, row: pd.Series) -> bool:
    constraints = getattr(spec, "risk_constraints", None)
    if constraints is None:
        return False

    close_price = _numeric(row.get("close_price"))
    limit_up_price = _numeric(row.get("limit_up_price"))
    limit_down_price = _numeric(row.get("limit_down_price"))

    if constraints.exclude_limit_up and limit_up_price and close_price >= limit_up_price:
        return True
    if constraints.exclude_limit_down and limit_down_price and close_price <= limit_down_price:
        return True
    return False


def _numeric(value: Any) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    return str(value).lower() in {"true", "1", "t", "yes"}


def _is_rebalance_day(trade_date: pd.Timestamp, rebalance_frequency: str) -> bool:
    if rebalance_frequency == "daily":
        return True
    if rebalance_frequency == "weekly":
        return trade_date.weekday() == 0
    return True

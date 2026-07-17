from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd
import us_strategy_factory_loop as factory


CN_NUMBERS = "一二三四五六七八九十"


def cn_strategy_number(index: int) -> str:
    if 1 <= index <= 10:
        return f"策略{CN_NUMBERS[index - 1]}"
    if index == 20:
        return "策略二十"
    if index == 30:
        return "策略三十"
    tens, ones = divmod(index, 10)
    if tens == 1:
        return f"策略十{CN_NUMBERS[ones - 1]}"
    return f"策略{CN_NUMBERS[tens - 1]}十{CN_NUMBERS[ones - 1]}"


def strategy_type(candidate_id: str) -> str:
    if candidate_id.startswith("pulltrend"):
        return "回调趋势型"
    if candidate_id.startswith("qmv"):
        return "质量动量低波型"
    if candidate_id.startswith("microrev"):
        return "微观反转型"
    return "均衡回调型"


def factor_description(candidate_id: str) -> str:
    parts = []
    mapping = {
        "cmf_10": "十日资金流强度",
        "cmf_20": "二十日资金流强度",
        "obv_change_20": "二十日能量潮变化",
        "mfi_7": "七日资金流指标",
        "mfi_14": "十四日资金流指标",
        "vol_20d": "二十日波动率",
        "vol_60d": "六十日波动率",
        "atr_20d": "二十日真实波幅",
        "parkinson_vol_20d": "二十日高低价波动率",
        "dollar_volume_20d": "二十日成交额",
        "turnover_stability_20d": "二十日成交稳定性",
        "volume_ma_ratio_5_20": "五日与二十日成交量比",
        "ret_skew_20d": "二十日收益偏度",
        "kurtosis_20d": "二十日收益峰度",
        "px_to_ma20": "相对二十日均线位置",
        "px_to_ma60": "相对六十日均线位置",
        "ma20_above_ma60": "二十日均线相对六十日均线",
        "overnight_gap_1d": "隔夜跳空",
        "intraday_ret_1d": "日内收益",
    }
    for key, label in mapping.items():
        if key in candidate_id:
            parts.append(label)
    return "、".join(dict.fromkeys(parts)) or "多因子组合"


def _merge_random_checks(rolling: pd.DataFrame, random_checks: pd.DataFrame) -> pd.DataFrame:
    checks = random_checks.copy()
    if checks.empty:
        checks = pd.DataFrame(columns=["candidate_id", "top_n", "rebalance_days", "pvalue_ir", "pvalue_excess", "deflated_ir_z"])
    for column in ["candidate_id", "top_n", "rebalance_days", "pvalue_ir", "pvalue_excess", "deflated_ir_z"]:
        if column not in checks.columns:
            checks[column] = pd.NA
    if checks["pvalue_excess"].isna().all() and not checks["pvalue_ir"].isna().all():
        checks["pvalue_excess"] = checks["pvalue_ir"]
    keys = ["candidate_id"]
    check_columns = ["candidate_id", "pvalue_ir", "pvalue_excess", "deflated_ir_z"]
    if (
        {"top_n", "rebalance_days"}.issubset(rolling.columns)
        and {"top_n", "rebalance_days"}.issubset(checks.columns)
        and checks[["top_n", "rebalance_days"]].notna().all().all()
    ):
        rolling = rolling.copy()
        checks = checks.copy()
        rolling["top_n"] = rolling["top_n"].astype(int)
        rolling["rebalance_days"] = rolling["rebalance_days"].astype(int)
        checks["top_n"] = checks["top_n"].astype(int)
        checks["rebalance_days"] = checks["rebalance_days"].astype(int)
        keys = ["candidate_id", "top_n", "rebalance_days"]
        check_columns = ["candidate_id", "top_n", "rebalance_days", "pvalue_ir", "pvalue_excess", "deflated_ir_z"]
    return rolling.merge(checks[check_columns], on=keys, how="left")


def _worth_mask(frame: pd.DataFrame, min_ir: float, min_deflated_z: float, max_random_pvalue: float) -> pd.Series:
    pvalue_excess = pd.to_numeric(frame.get("pvalue_excess"), errors="coerce")
    deflated = pd.to_numeric(frame.get("deflated_ir_z"), errors="coerce")
    return (
        pd.to_numeric(frame["ir"], errors="coerce").ge(min_ir)
        & pd.to_numeric(frame["excess_return"], errors="coerce").gt(0)
        & pvalue_excess.le(max_random_pvalue)
        & deflated.ge(min_deflated_z)
    )


def select_live_pool(
    rolling: pd.DataFrame,
    random_checks: pd.DataFrame,
    top_n: int | None = 30,
    min_ir: float = 1.30,
    min_deflated_z: float = 1.64,
    max_random_pvalue: float = 0.05,
    allowed_holdings: tuple[int, ...] = (5, 7, 10, 20),
) -> pd.DataFrame:
    frame = _merge_random_checks(rolling.copy(), random_checks.copy())
    frame = frame.sort_values(["ir", "excess_return", "mdd"], ascending=[False, False, True]).reset_index(drop=True)
    frame = frame[frame["top_n"].astype(int).isin(allowed_holdings)].copy()
    frame = frame[_worth_mask(frame, min_ir=min_ir, min_deflated_z=min_deflated_z, max_random_pvalue=max_random_pvalue)].copy()
    if top_n is not None and top_n > 0:
        frame = frame.head(top_n).copy()
    frame = frame.reset_index(drop=True)

    rows = []
    for idx, row in frame.iterrows():
        has_check = pd.notna(row.get("pvalue_ir"))
        pvalue_excess = row.get("pvalue_excess")
        rows.append(
            {
                "策略编号": cn_strategy_number(idx + 1),
                "candidate_id": row["candidate_id"],
                "top_n_numeric": int(row["top_n"]),
                "rebalance_days_numeric": int(row["rebalance_days"]),
                "策略类型": strategy_type(str(row["candidate_id"])),
                "主要区分因子": factor_description(str(row["candidate_id"])),
                "持仓数量": int(row["top_n"]),
                "调仓周期": f"{int(row['rebalance_days'])}日",
                "样本外滚动验证超基准收益": float(row["excess_return"]),
                "信息比率": float(row["ir"]),
                "年度平均信息比率": float(row.get("avg_ir", 0.0)),
                "最大回撤": float(row["mdd"]),
                "超基准胜率": float(row.get("win_excess", 0.0)),
                "信息比率随机检验显著性概率": None if not has_check else float(row["pvalue_ir"]),
                "超基准收益随机检验显著性概率": None if (not has_check or pd.isna(pvalue_excess)) else float(pvalue_excess),
                "去偏标准分": None if not has_check else float(row["deflated_ir_z"]),
                "随机检验状态": "已完成随机检验" if has_check else "待补随机检验",
                "数据池状态": "动态流动性降偏，尚非历史时点成分",
                "入库状态": "已写入实盘池数据库",
                "监控状态": "待人工审核，未进入正式监控",
                "结论": "纳入纸面实盘池；继续跟踪并补齐历史时点成分验证",
            }
        )
    return pd.DataFrame(rows)


def build_candidate_review_table(
    candidates: pd.DataFrame,
    strategies: pd.DataFrame,
    rolling: pd.DataFrame,
    random_checks: pd.DataFrame,
) -> pd.DataFrame:
    frame = candidates.copy()
    rolling_keys = rolling[["candidate_id", "top_n", "rebalance_days", "ir", "excess_return", "mdd"]].copy()
    random_keys = random_checks[["candidate_id", "top_n", "rebalance_days", "pvalue_excess", "deflated_ir_z"]].copy() if not random_checks.empty else pd.DataFrame()
    if not random_keys.empty:
        rolling_keys = rolling_keys.merge(random_keys, on=["candidate_id", "top_n", "rebalance_days"], how="left")
    frame = frame.merge(rolling_keys, on=["candidate_id", "top_n", "rebalance_days"], how="left", suffixes=("", "_rolling"))
    if {"candidate_id", "top_n_numeric", "rebalance_days_numeric"}.issubset(strategies.columns):
        live_keys = set(zip(strategies["candidate_id"], strategies["top_n_numeric"], strategies["rebalance_days_numeric"]))
    else:
        live_keys = set()
    statuses = []
    reasons = []
    for _, row in frame.iterrows():
        key = (row["candidate_id"], int(row["top_n"]), int(row["rebalance_days"]))
        if key in live_keys:
            statuses.append("已纳入纸面实盘池")
            reasons.append("滚动样本外和随机检验达标")
        elif pd.isna(row.get("ir")):
            statuses.append("待滚动验证")
            reasons.append("已有工厂候选，但尚未完成同级别滚动样本外和随机检验")
        else:
            statuses.append("待优化后复核")
            reasons.append("有滚动验证结果，但未达到本次纸面实盘池阈值")
    return pd.DataFrame(
        {
            "candidate_id": frame["candidate_id"],
            "持仓数量": frame["top_n"].astype(int),
            "调仓周期": frame["rebalance_days"].astype(int).astype(str) + "日",
            "工厂最终评分": pd.to_numeric(frame.get("final_score"), errors="coerce"),
            "滚动信息比率": pd.to_numeric(frame.get("ir"), errors="coerce"),
            "滚动超基准收益": pd.to_numeric(frame.get("excess_return"), errors="coerce"),
            "随机检验超基准显著性概率": pd.to_numeric(frame.get("pvalue_excess"), errors="coerce"),
            "去偏标准分": pd.to_numeric(frame.get("deflated_ir_z"), errors="coerce"),
            "处理状态": statuses,
            "处理原因": reasons,
        }
    )


def _date_frame(panel: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    return panel[panel["trade_date"].eq(pd.Timestamp(date))].copy()


def build_live_period(panel: pd.DataFrame, signal_date: str, valuation_date: str | None = None) -> tuple[pd.DataFrame, str, str, str]:
    dates = pd.Series(sorted(pd.Timestamp(d) for d in panel["trade_date"].unique()))
    signal = pd.Timestamp(signal_date)
    if signal not in set(dates):
        available = dates[dates <= signal]
        if available.empty:
            raise ValueError(f"没有可用于信号日 {signal_date} 的行情")
        signal = pd.Timestamp(available.iloc[-1])
    future = dates[dates > signal]
    if future.empty:
        raise ValueError(f"信号日 {signal.date()} 之后没有可入场交易日")
    entry = pd.Timestamp(future.iloc[0])
    if valuation_date:
        valuation = pd.Timestamp(valuation_date)
        if valuation not in set(dates):
            available = dates[dates <= valuation]
            if available.empty:
                raise ValueError(f"没有可用于估值日 {valuation_date} 的行情")
            valuation = pd.Timestamp(available.iloc[-1])
    else:
        valuation = pd.Timestamp(dates.iloc[-1])
    if valuation < entry:
        raise ValueError("估值日早于入场日")

    score_cols = [f"score_{factor.name}" for factor in factory.FACTOR_LIBRARY]
    signal_frame = _date_frame(panel, signal)
    entry_frame = _date_frame(panel, entry)
    valuation_frame = _date_frame(panel, valuation)
    live_frame = signal_frame[["symbol", *score_cols]].merge(entry_frame[["symbol", "open"]].rename(columns={"open": "entry"}), on="symbol")
    live_frame = live_frame.merge(valuation_frame[["symbol", "close"]].rename(columns={"close": "exit"}), on="symbol")
    live_frame = live_frame[(live_frame["entry"] > 0) & (live_frame["exit"] > 0)].copy()
    live_frame["asset_ret"] = live_frame["exit"] / live_frame["entry"] - 1.0 - 0.002
    return live_frame, signal.date().isoformat(), entry.date().isoformat(), valuation.date().isoformat()


def build_signal_holdings_and_live_metrics(
    strategies: pd.DataFrame,
    candidates: pd.DataFrame,
    live_frame: pd.DataFrame,
    signal_date: str,
    entry_date: str,
    valuation_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    holding_rows = []
    metric_rows = []
    benchmark_ret = float(live_frame["asset_ret"].mean())
    for _, strategy in strategies.iterrows():
        candidate_id = strategy["candidate_id"]
        matched = candidates[candidates["candidate_id"].eq(candidate_id)].copy()
        if "top_n" in matched.columns:
            matched = matched[matched["top_n"].astype(int).eq(int(strategy.get("top_n_numeric", strategy["持仓数量"])))]
        if "rebalance_days" in matched.columns:
            matched = matched[matched["rebalance_days"].astype(int).eq(int(strategy.get("rebalance_days_numeric", 20)))]
        if matched.empty:
            continue
        weights = json.loads(str(matched.iloc[0]["weights"]))
        scores = factory.score_panel(live_frame, weights)
        top_n = int(strategy["持仓数量"])
        picks = scores.nlargest(top_n)
        if picks.empty:
            continue
        trade = live_frame.loc[picks.index].copy()
        strategy_ret = float(trade["asset_ret"].mean())
        weight = 1.0 / len(trade)
        for rank, row in enumerate(trade.itertuples(index=False), start=1):
            holding_rows.append(
                {
                    "策略编号": strategy["策略编号"],
                    "股票代码": row.symbol,
                    "排名": rank,
                    "目标权重": weight,
                    "信号日期": signal_date,
                    "计划入场": f"{entry_date}开盘，基于{signal_date}收盘信号",
                    "估值日期": valuation_date,
                    "策略类型": strategy["策略类型"],
                }
            )
        metric_rows.append(
            {
                "策略编号": strategy["策略编号"],
                "实盘起点": signal_date,
                "入场日期": entry_date,
                "估值日期": valuation_date,
                "实盘收益": strategy_ret,
                "实盘基准收益": benchmark_ret,
                "实盘超基准收益": (1.0 + strategy_ret) / (1.0 + benchmark_ret) - 1.0,
                "实盘持仓数量": int(len(trade)),
            }
        )
    return pd.DataFrame(holding_rows), pd.DataFrame(metric_rows)


def enrich_strategies_with_live_metrics(strategies: pd.DataFrame, live_metrics: pd.DataFrame) -> pd.DataFrame:
    if live_metrics.empty:
        out = strategies.copy()
    else:
        out = strategies.merge(live_metrics, on="策略编号", how="left")
    out["入库状态"] = "已写入实盘池数据库"
    return out


def filter_live_outperformers(strategies: pd.DataFrame, holdings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if strategies.empty or "实盘超基准收益" not in strategies.columns:
        return strategies.copy(), holdings.copy()
    kept_strategies = strategies[pd.to_numeric(strategies["实盘超基准收益"], errors="coerce").gt(0)].copy()
    if holdings.empty or "策略编号" not in holdings.columns:
        return kept_strategies.reset_index(drop=True), holdings.copy()
    kept_ids = set(kept_strategies["策略编号"].astype(str))
    kept_holdings = holdings[holdings["策略编号"].astype(str).isin(kept_ids)].copy()
    return kept_strategies.reset_index(drop=True), kept_holdings.reset_index(drop=True)


def build_live_holdings(strategies: pd.DataFrame, latest_signals: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for _, strategy in strategies.iterrows():
        candidate_id = strategy["candidate_id"]
        signals = latest_signals[latest_signals["candidate_id"].eq(candidate_id)].copy()
        if signals.empty:
            continue
        signals["策略编号"] = strategy["策略编号"]
        signals["策略类型"] = strategy["策略类型"]
        signals = signals.rename(
            columns={
                "symbol": "股票代码",
                "rank": "排名",
                "weight": "目标权重",
                "signal_date": "信号日期",
                "intended_entry": "计划入场",
            }
        )
        frames.append(signals[["策略编号", "股票代码", "排名", "目标权重", "信号日期", "计划入场", "策略类型"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_latest_holdings_from_candidates(
    strategies: pd.DataFrame,
    candidates: pd.DataFrame,
    latest_panel: pd.DataFrame,
) -> pd.DataFrame:
    live_frame = latest_panel.copy()
    if "asset_ret" not in live_frame.columns:
        live_frame["asset_ret"] = 0.0
    latest_date = pd.Timestamp(live_frame["trade_date"].max()).date().isoformat() if "trade_date" in live_frame.columns else ""
    holdings, _ = build_signal_holdings_and_live_metrics(
        strategies=strategies,
        candidates=candidates,
        live_frame=live_frame,
        signal_date=latest_date,
        entry_date="下一交易日",
        valuation_date=latest_date,
    )
    return holdings.drop(columns=["估值日期"], errors="ignore")


def _write_table(con: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    con.register("_frame", frame)
    try:
        con.execute(f"create table if not exists {table} as select * from _frame where 1=0")
        if frame.empty:
            return
        existing_columns = [row[1] for row in con.execute(f"pragma table_info('{table}')").fetchall()]
        if existing_columns != list(frame.columns):
            con.execute(f"drop table {table}")
            con.execute(f"create table {table} as select * from _frame where 1=0")
        con.execute(f"insert into {table} select * from _frame")
    finally:
        con.unregister("_frame")


def write_live_pool(
    db_path: Path,
    run_id: str,
    strategies: pd.DataFrame,
    holdings: pd.DataFrame,
    review_candidates: pd.DataFrame | None = None,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    strategies = strategies.copy()
    holdings = holdings.copy()
    if "run_id" not in strategies.columns:
        strategies.insert(0, "run_id", run_id)
    if "run_id" not in holdings.columns:
        holdings.insert(0, "run_id", run_id)
    review = review_candidates.copy() if review_candidates is not None else None
    if review is not None and "run_id" not in review.columns:
        review.insert(0, "run_id", run_id)
    con = duckdb.connect(str(db_path))
    try:
        for table in ["us_live_pool_strategies", "us_live_pool_holdings", "us_live_pool_candidate_review"]:
            exists = con.execute("select count(*) from information_schema.tables where table_name = ?", [table]).fetchone()[0]
            if exists:
                con.execute(f"delete from {table} where run_id = ?", [run_id])
        _write_table(con, "us_live_pool_strategies", strategies)
        _write_table(con, "us_live_pool_holdings", holdings)
        if review is not None:
            _write_table(con, "us_live_pool_candidate_review", review)
    finally:
        con.close()


def _fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "未完成"
    return f"{float(value) * 100:.2f}%"


def _fmt_num(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "未完成"
    return f"{float(value):.3f}"


def write_report(strategies: pd.DataFrame, holdings: pd.DataFrame, review_candidates: pd.DataFrame, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    display = strategies.copy()
    report_cols = [
        "策略编号",
        "策略类型",
        "主要区分因子",
        "持仓数量",
        "调仓周期",
        "实盘起点",
        "入场日期",
        "估值日期",
        "实盘收益",
        "实盘基准收益",
        "实盘超基准收益",
        "样本外滚动验证超基准收益",
        "信息比率",
        "年度平均信息比率",
        "最大回撤",
        "超基准胜率",
        "随机检验状态",
        "去偏标准分",
        "数据池状态",
        "入库状态",
        "监控状态",
        "结论",
    ]
    for col in report_cols:
        if col not in display.columns:
            display[col] = pd.Series(dtype="object")
    percent_cols = [
        "样本外滚动验证超基准收益",
        "最大回撤",
        "超基准胜率",
        "实盘收益",
        "实盘基准收益",
        "实盘超基准收益",
    ]
    for col in percent_cols:
        if col in display.columns:
            display[col] = display[col].map(_fmt_pct)
    for col in ["信息比率", "年度平均信息比率", "去偏标准分"]:
        if col in display.columns:
            display[col] = display[col].map(_fmt_num)
    for col in ["信息比率随机检验显著性概率", "超基准收益随机检验显著性概率"]:
        if col in display.columns:
            display[col] = display[col].map(lambda value: "未完成" if pd.isna(value) else f"{float(value):.4f}")
    status_counts = review_candidates["处理状态"].value_counts().to_dict() if not review_candidates.empty else {}
    text = [
        "# 2026-07-13 美股实盘池策略报告",
        "",
        f"本批入池策略数：{len(strategies)}。",
        f"持仓明细行数：{len(holdings)}。",
        "实盘口径：以 2026-06-30 收盘信号为起点，下一交易日开盘入场，估值到当前最新可用交易日。",
        "基准口径：同一动态流动性股票池等权收益，扣除与策略相同的单期交易摩擦。",
        "排序口径：先看样本外滚动验证信息比率，再看样本外滚动验证超基准收益，最后看最大回撤。",
        "数据池状态：动态流动性降偏，尚非历史时点成分。",
        "监控状态：待人工审核，未进入正式监控。",
        "",
        "## 策略表",
        "",
        display[report_cols].to_markdown(index=False),
        "",
        "## 候选处理汇总",
        "",
        f"已纳入纸面实盘池：{status_counts.get('已纳入纸面实盘池', 0)}。",
        f"待滚动验证：{status_counts.get('待滚动验证', 0)}。",
        f"待优化后复核：{status_counts.get('待优化后复核', 0)}。",
        "",
        "没有通过同级别滚动样本外和随机检验的候选，不进入本次纸面实盘池，但已写入候选复核表，后续用于继续优化和验证。",
    ]
    report_path.write_text("\n".join(text), encoding="utf-8")


def _validate_outputs(db_path: Path, run_id: str, report_path: Path, strategies: pd.DataFrame, holdings: pd.DataFrame) -> None:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        strategy_count = con.execute("select count(*) from us_live_pool_strategies where run_id = ?", [run_id]).fetchone()[0]
        holding_count = con.execute("select count(*) from us_live_pool_holdings where run_id = ?", [run_id]).fetchone()[0]
    finally:
        con.close()
    if strategy_count != len(strategies):
        raise RuntimeError(f"策略入库数量不一致：数据库 {strategy_count}，报告 {len(strategies)}")
    if holding_count != len(holdings) or (len(strategies) > 0 and holding_count == 0):
        raise RuntimeError(f"持仓入库数量异常：数据库 {holding_count}，报告 {len(holdings)}")
    text = report_path.read_text(encoding="utf-8")
    for bad in ["NaN", "Infinity", "__PLACEHOLDER__", "TBD"]:
        if bad in text:
            raise RuntimeError(f"报告存在无效占位或不可展示值：{bad}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--run-id", default="2026-07-13-live-all-worthy-dynamic-liquidity")
    parser.add_argument("--rolling-summary", default=r"E:\quant-agent-team-us\research\2026-07-13-rolling-dynamic-liquidity-top30\rolling_summary.csv")
    parser.add_argument("--random-checks", default=r"E:\quant-agent-team-us\research\2026-07-13-null-dynamic-liquidity-top30\null_overfit_summary.csv")
    parser.add_argument("--candidates", default=r"E:\quant-agent-team-us\research\2026-07-12-factory-dynamic-liquidity\factory_qualified_candidates.csv")
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-12")
    parser.add_argument("--report-dir", default=r"G:\quant-agent-team-us\reports\us\live")
    parser.add_argument("--signal-date", default="2026-06-30")
    parser.add_argument("--valuation-date", default="")
    parser.add_argument("--top-n", type=int, default=0, help="0 表示纳入全部达标策略")
    parser.add_argument("--min-ir", type=float, default=1.30)
    parser.add_argument("--min-deflated-z", type=float, default=1.64)
    parser.add_argument("--max-random-pvalue", type=float, default=0.05)
    parser.add_argument("--allowed-holdings", default="5,7,10,20")
    args = parser.parse_args()

    rolling = pd.read_csv(args.rolling_summary)
    random_checks = pd.read_csv(args.random_checks) if Path(args.random_checks).exists() else pd.DataFrame()
    candidates = pd.read_csv(args.candidates)
    strategies = select_live_pool(
        rolling,
        random_checks,
        top_n=None if args.top_n == 0 else args.top_n,
        min_ir=args.min_ir,
        min_deflated_z=args.min_deflated_z,
        max_random_pvalue=args.max_random_pvalue,
        allowed_holdings=tuple(int(item.strip()) for item in args.allowed_holdings.split(",") if item.strip()),
    )
    panel, _, _, _ = factory.load_panel(Path(args.raw_dir), universe_mode="dynamic_liquidity")
    live_frame, signal_date, entry_date, valuation_date = build_live_period(
        panel,
        signal_date=args.signal_date,
        valuation_date=args.valuation_date or None,
    )
    holdings, live_metrics = build_signal_holdings_and_live_metrics(
        strategies=strategies,
        candidates=candidates,
        live_frame=live_frame,
        signal_date=signal_date,
        entry_date=entry_date,
        valuation_date=valuation_date,
    )
    strategies = enrich_strategies_with_live_metrics(strategies, live_metrics)
    strategies, holdings = filter_live_outperformers(strategies, holdings)
    review_candidates = build_candidate_review_table(candidates, strategies, rolling, random_checks)
    write_live_pool(Path(args.db), args.run_id, strategies, holdings, review_candidates)

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    strategies_path = report_dir / "2026-07-13-美股实盘池策略表.csv"
    holdings_path = report_dir / "2026-07-13-美股实盘池持仓表.csv"
    review_path = report_dir / "2026-07-13-美股候选策略复核表.csv"
    report_path = report_dir / "2026-07-13-美股实盘池策略报告.md"
    strategies.to_csv(strategies_path, index=False, encoding="utf-8-sig")
    holdings.to_csv(holdings_path, index=False, encoding="utf-8-sig")
    review_candidates.to_csv(review_path, index=False, encoding="utf-8-sig")
    write_report(strategies, holdings, review_candidates, report_path)
    _validate_outputs(Path(args.db), args.run_id, report_path, strategies, holdings)
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "strategies": len(strategies),
                "holdings": len(holdings),
                "review_candidates": len(review_candidates),
                "signal_date": signal_date,
                "entry_date": entry_date,
                "valuation_date": valuation_date,
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

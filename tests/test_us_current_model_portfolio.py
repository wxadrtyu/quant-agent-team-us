from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_build_current_model_portfolio import build_model_portfolio


class UsCurrentModelPortfolioTest(unittest.TestCase):
    def test_drag_symbols_are_capped_and_sector_weight_is_limited(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "monitor_key": "S1",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.08,
                    "信息比率": 2.0,
                    "去偏标准分": 2.0,
                    "top_n_numeric": 5,
                },
                {
                    "monitor_key": "S2",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.07,
                    "信息比率": 1.8,
                    "去偏标准分": 2.0,
                    "top_n_numeric": 7,
                },
                {
                    "monitor_key": "S3",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.06,
                    "信息比率": 1.5,
                    "去偏标准分": 1.5,
                    "top_n_numeric": 7,
                },
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "S1", "股票代码": "ON", "目标权重": 0.7},
                {"monitor_key": "S1", "股票代码": "MSFT", "目标权重": 0.3},
                {"monitor_key": "S2", "股票代码": "ON", "目标权重": 0.5},
                {"monitor_key": "S2", "股票代码": "AAPL", "目标权重": 0.5},
                {"monitor_key": "S3", "股票代码": "JNJ", "目标权重": 0.5},
                {"monitor_key": "S3", "股票代码": "PG", "目标权重": 0.5},
            ]
        )
        metadata = pd.DataFrame(
            [
                {"symbol": "ON", "sector": "Technology", "name": "ON Semiconductor"},
                {"symbol": "MSFT", "sector": "Technology", "name": "Microsoft"},
                {"symbol": "AAPL", "sector": "Technology", "name": "Apple"},
                {"symbol": "JNJ", "sector": "Health Care", "name": "Johnson & Johnson"},
                {"symbol": "PG", "sector": "Consumer Staples", "name": "Procter & Gamble"},
            ]
        )

        portfolio = build_model_portfolio(
            strategies,
            holdings,
            target_symbols=4,
            max_symbol_weight=0.5,
            metadata=metadata,
            drag_symbols={"ON"},
            max_drag_weight=0.02,
            max_sector_weight=0.5,
        )

        weights = dict(zip(portfolio["股票代码"], portfolio["目标权重"]))
        if "ON" in weights:
            self.assertLessEqual(weights["ON"], 0.0200001)
        sector_weights = portfolio.groupby("行业分组")["目标权重"].sum()
        self.assertLessEqual(float(sector_weights.max()), 0.5000001)
        self.assertAlmostEqual(float(portfolio["目标权重"].sum()), 1.0)

    def test_drag_symbols_can_be_excluded_when_enough_clean_symbols_exist(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "monitor_key": f"S{i}",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.08 - i * 0.001,
                    "信息比率": 2.0,
                    "去偏标准分": 2.0,
                    "top_n_numeric": 7,
                }
                for i in range(4)
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "S0", "股票代码": "ON", "目标权重": 0.5},
                {"monitor_key": "S0", "股票代码": "MSFT", "目标权重": 0.5},
                {"monitor_key": "S1", "股票代码": "AAPL", "目标权重": 0.5},
                {"monitor_key": "S1", "股票代码": "JNJ", "目标权重": 0.5},
                {"monitor_key": "S2", "股票代码": "PG", "目标权重": 0.5},
                {"monitor_key": "S2", "股票代码": "COST", "目标权重": 0.5},
                {"monitor_key": "S3", "股票代码": "HD", "目标权重": 0.5},
                {"monitor_key": "S3", "股票代码": "UNH", "目标权重": 0.5},
            ]
        )
        metadata = pd.DataFrame(
            [
                {"symbol": symbol, "sector": sector, "name": symbol}
                for symbol, sector in [
                    ("ON", "Technology"),
                    ("MSFT", "Technology"),
                    ("AAPL", "Technology"),
                    ("JNJ", "Health Care"),
                    ("PG", "Consumer Staples"),
                    ("COST", "Consumer Staples"),
                    ("HD", "Consumer Discretionary"),
                    ("UNH", "Health Care"),
                ]
            ]
        )

        portfolio = build_model_portfolio(
            strategies,
            holdings,
            target_symbols=6,
            max_symbol_weight=0.4,
            metadata=metadata,
            drag_symbols={"ON"},
            exclude_drag_symbols=True,
            max_sector_weight=0.5,
        )

        self.assertNotIn("ON", set(portfolio["股票代码"]))


if __name__ == "__main__":
    unittest.main()

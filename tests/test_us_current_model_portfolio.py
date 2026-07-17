from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_build_current_model_portfolio import build_model_portfolio, strategy_cluster_key


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

    def test_cluster_concentration_penalty_prefers_diverse_strategy_support(self) -> None:
        self.assertEqual(strategy_cluster_key("qmv_ret_120d_px_to_ma20_mfi_14_top5"), "qmv:ret_120d|px_to_ma20|mfi_14")

        strategies = pd.DataFrame(
            [
                {
                    "monitor_key": "S1",
                    "candidate_id": "qmv_ret_120d_px_to_ma20_mfi_14_a",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.090,
                    "信息比率": 1.0,
                    "去偏标准分": 1.8,
                    "top_n_numeric": 5,
                },
                {
                    "monitor_key": "S2",
                    "candidate_id": "qmv_ret_120d_px_to_ma20_mfi_14_b",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.090,
                    "信息比率": 1.0,
                    "去偏标准分": 1.8,
                    "top_n_numeric": 5,
                },
                {
                    "monitor_key": "S3",
                    "candidate_id": "liquidity_close_pos_20d_turnover_stability_20d_a",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.047,
                    "信息比率": 1.0,
                    "去偏标准分": 1.8,
                    "top_n_numeric": 5,
                },
                {
                    "monitor_key": "S4",
                    "candidate_id": "defensivequality_low_vol_20d_ret_120d_a",
                    "入库至今持续跑赢": True,
                    "实盘超基准收益": 0.047,
                    "信息比率": 1.0,
                    "去偏标准分": 1.8,
                    "top_n_numeric": 5,
                },
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "S1", "股票代码": "AAA", "目标权重": 1.0},
                {"monitor_key": "S2", "股票代码": "AAA", "目标权重": 1.0},
                {"monitor_key": "S3", "股票代码": "BBB", "目标权重": 1.0},
                {"monitor_key": "S4", "股票代码": "BBB", "目标权重": 1.0},
            ]
        )
        metadata = pd.DataFrame(
            [
                {"symbol": "AAA", "sector": "Technology", "name": "AAA"},
                {"symbol": "BBB", "sector": "Health Care", "name": "BBB"},
            ]
        )

        portfolio = build_model_portfolio(
            strategies,
            holdings,
            target_symbols=2,
            max_symbol_weight=0.8,
            metadata=metadata,
            drag_symbols=set(),
            max_sector_weight=None,
            max_cluster_share=0.60,
        )

        by_symbol = portfolio.set_index("股票代码")
        self.assertEqual(int(by_symbol.loc["AAA", "cluster_count"]), 1)
        self.assertEqual(int(by_symbol.loc["BBB", "cluster_count"]), 2)
        self.assertAlmostEqual(float(by_symbol.loc["AAA", "max_cluster_share"]), 1.0)
        self.assertLess(float(by_symbol.loc["BBB", "adjusted_score"]), float(by_symbol.loc["BBB", "raw_score"]))
        self.assertGreater(float(by_symbol.loc["BBB", "adjusted_score"]), float(by_symbol.loc["AAA", "adjusted_score"]))

    def test_max_allowed_cluster_share_filters_over_concentrated_symbols(self) -> None:
        persistent_col = "\u5165\u5e93\u81f3\u4eca\u6301\u7eed\u8dd1\u8d62"
        excess_col = "\u5b9e\u76d8\u8d85\u57fa\u51c6\u6536\u76ca"
        ir_col = "\u4fe1\u606f\u6bd4\u7387"
        z_col = "\u53bb\u504f\u6807\u51c6\u5206"
        symbol_col = "\u80a1\u7968\u4ee3\u7801"
        weight_col = "\u76ee\u6807\u6743\u91cd"
        strategies = pd.DataFrame(
            [
                {
                    "monitor_key": key,
                    "candidate_id": candidate_id,
                    persistent_col: True,
                    excess_col: excess,
                    ir_col: 1.0,
                    z_col: 1.8,
                    "top_n_numeric": 5,
                }
                for key, candidate_id, excess in [
                    ("A1", "qmv_ret_120d_px_to_ma20_mfi_14_a", 0.20),
                    ("B1", "balanced_ret_120d_ret_5d_px_to_ma20_a", 0.10),
                    ("B2", "defensivequality_low_vol_20d_ret_120d_a", 0.10),
                    ("C1", "liquidity_close_pos_20d_turnover_stability_20d_a", 0.09),
                    ("C2", "smoothquality_ret_60d_mfi_14_vol_20d_a", 0.09),
                ]
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "A1", symbol_col: "AAA", weight_col: 1.0},
                {"monitor_key": "B1", symbol_col: "BBB", weight_col: 1.0},
                {"monitor_key": "B2", symbol_col: "BBB", weight_col: 1.0},
                {"monitor_key": "C1", symbol_col: "CCC", weight_col: 1.0},
                {"monitor_key": "C2", symbol_col: "CCC", weight_col: 1.0},
            ]
        )
        metadata = pd.DataFrame(
            [
                {"symbol": "AAA", "sector": "Technology", "name": "AAA"},
                {"symbol": "BBB", "sector": "Health Care", "name": "BBB"},
                {"symbol": "CCC", "sector": "Financials", "name": "CCC"},
            ]
        )

        portfolio = build_model_portfolio(
            strategies,
            holdings,
            target_symbols=2,
            max_symbol_weight=0.8,
            metadata=metadata,
            drag_symbols=set(),
            max_sector_weight=None,
            max_allowed_cluster_share=0.75,
        )

        self.assertNotIn("AAA", set(portfolio[symbol_col]))
        self.assertLessEqual(float(portfolio["max_cluster_share"].max()), 0.75)

if __name__ == "__main__":
    unittest.main()

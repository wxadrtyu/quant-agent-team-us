from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_overlap_aware_monitoring_review import select_overlap_aware


class UsOverlapAwareMonitoringReviewTest(unittest.TestCase):
    def test_select_overlap_aware_skips_highly_overlapping_strategy(self) -> None:
        strategies = pd.DataFrame(
            [
                {
                    "monitor_key": "a",
                    "信息比率": 2.5,
                    "年度平均信息比率": 1.0,
                    "实盘超基准收益": 0.05,
                    "样本外滚动验证超基准收益": 0.2,
                    "去偏标准分": 2.0,
                    "最大回撤": 0.1,
                    "持仓数量": 3,
                },
                {
                    "monitor_key": "b",
                    "信息比率": 2.4,
                    "年度平均信息比率": 1.0,
                    "实盘超基准收益": 0.04,
                    "样本外滚动验证超基准收益": 0.2,
                    "去偏标准分": 2.0,
                    "最大回撤": 0.1,
                    "持仓数量": 3,
                },
                {
                    "monitor_key": "c",
                    "信息比率": 2.0,
                    "年度平均信息比率": 1.0,
                    "实盘超基准收益": 0.03,
                    "样本外滚动验证超基准收益": 0.2,
                    "去偏标准分": 2.0,
                    "最大回撤": 0.1,
                    "持仓数量": 3,
                },
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "a", "股票代码": "AAA"},
                {"monitor_key": "a", "股票代码": "BBB"},
                {"monitor_key": "a", "股票代码": "CCC"},
                {"monitor_key": "b", "股票代码": "AAA"},
                {"monitor_key": "b", "股票代码": "BBB"},
                {"monitor_key": "b", "股票代码": "CCC"},
                {"monitor_key": "c", "股票代码": "XXX"},
                {"monitor_key": "c", "股票代码": "YYY"},
                {"monitor_key": "c", "股票代码": "ZZZ"},
            ]
        )

        selected, selected_holdings, review = select_overlap_aware(
            strategies,
            holdings,
            target_count=3,
            max_jaccard=0.55,
        )

        self.assertEqual(selected["monitor_key"].tolist(), ["a", "c"])
        self.assertEqual(set(selected_holdings["monitor_key"]), {"a", "c"})
        status = dict(zip(review["monitor_key"], review["组合层审核状态"]))
        reason = dict(zip(review["monitor_key"], review["审核原因"]))
        self.assertEqual(status["b"], "延后观察")
        self.assertEqual(reason["b"], "与已选策略持仓重叠过高")

    def test_select_overlap_aware_keeps_live_outperformers_only(self) -> None:
        strategies = pd.DataFrame(
            [
                {"monitor_key": "keep", "信息比率": 2.0, "实盘超基准收益": 0.01, "最大回撤": 0.1},
                {"monitor_key": "drop", "信息比率": 3.0, "实盘超基准收益": 0.0, "最大回撤": 0.1},
            ]
        )
        holdings = pd.DataFrame(
            [
                {"monitor_key": "keep", "股票代码": "AAA"},
                {"monitor_key": "drop", "股票代码": "BBB"},
            ]
        )

        selected, selected_holdings, review = select_overlap_aware(strategies, holdings)

        self.assertEqual(selected["monitor_key"].tolist(), ["keep"])
        self.assertEqual(selected_holdings["monitor_key"].tolist(), ["keep"])
        self.assertEqual(review["monitor_key"].tolist(), ["keep"])


if __name__ == "__main__":
    unittest.main()

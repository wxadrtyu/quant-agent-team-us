import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.market_context import (
    _classify_notice_earnings_details,
    _classify_notice_policy_tag,
    _classify_notice_earnings_tag,
    _extract_earnings_change_range,
    _extract_notice_info_code,
    _normalize_stock_code,
    _normalize_notice_event_tag,
    _normalize_stock_name,
    _normalize_trade_date,
    _resolve_code_from_name_cell,
)
from quant_agent_team.workflow import ProjectWorkflow


class MarketContextHelperTest(unittest.TestCase):
    def test_normalize_stock_code_handles_prefixed_symbols(self) -> None:
        self.assertEqual(_normalize_stock_code("SH600050"), "600050")
        self.assertEqual(_normalize_stock_code("SZ000001"), "000001")

    def test_normalize_trade_date_from_text(self) -> None:
        self.assertEqual(_normalize_trade_date("2025-03-27 12:00:00"), "2025-03-27")

    def test_normalize_stock_name_removes_spaces(self) -> None:
        self.assertEqual(_normalize_stock_name("万  科Ａ"), "万科Ａ")

    def test_resolve_code_from_name_cell_uses_name_map(self) -> None:
        mapping = {"平安银行": "000001", "万科Ａ": "000002"}
        self.assertEqual(_resolve_code_from_name_cell("万  科Ａ", mapping), "000002")

    def test_normalize_notice_event_tag_preserves_scope_and_type(self) -> None:
        self.assertEqual(
            _normalize_notice_event_tag("重大事项", "签订协议"),
            "重大事项::签订协议",
        )

    def test_classify_notice_policy_tag_detects_risk(self) -> None:
        self.assertEqual(
            _classify_notice_policy_tag(
                "股票交易异常波动及风险提示公告",
                "股票交易异常波动",
                "风险提示",
            ),
            "risk_warning",
        )

    def test_classify_notice_policy_tag_detects_contract(self) -> None:
        self.assertEqual(
            _classify_notice_policy_tag(
                "关于签署重大合同的公告",
                "签订协议",
                "重大事项",
            ),
            "business_contract",
        )

    def test_classify_notice_earnings_tag_detects_positive_guidance(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "2025年半年度业绩预告：净利润同比增长并实现扭亏为盈",
                "业绩预告",
                "重大事项",
            ),
            ("earnings_guidance", "positive", 2.0),
        )

    def test_classify_notice_earnings_tag_detects_negative_guidance(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "2025年半年度业绩预告：预计首亏",
                "业绩预告",
                "重大事项",
            ),
            ("earnings_guidance", "negative", -2.0),
        )

    def test_classify_notice_earnings_tag_excludes_operating_quick_report_noise(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "2026年2月份产销数据快报",
                "月度经营情况",
                "风险提示",
            ),
            (None, None, None),
        )

    def test_classify_notice_earnings_tag_excludes_compensation_noise(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "关于签署业绩承诺补偿协议的公告",
                "签订协议",
                "重大事项",
            ),
            (None, None, None),
        )

    def test_classify_notice_earnings_tag_detects_positive_guidance_variants(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "2025年度业绩预告：预计减亏并实现同比扭亏",
                "业绩预告",
                "重大事项",
            ),
            ("earnings_guidance", "positive", 2.0),
        )

    def test_classify_notice_earnings_tag_marks_correction_as_mixed(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "2025年度业绩预告更正公告",
                "业绩预告",
                "风险提示",
            ),
            (None, None, None),
        )

    def test_extract_notice_info_code_from_url(self) -> None:
        self.assertEqual(
            _extract_notice_info_code("https://data.eastmoney.com/notices/detail/301508/AN202601151817051955.html"),
            "AN202601151817051955",
        )

    def test_extract_earnings_change_range_reads_percent_interval(self) -> None:
        self.assertEqual(
            _extract_earnings_change_range("预计2025年归母净利润同比增长 45.2% 至 62.8%"),
            (45.2, 62.8),
        )

    def test_classify_notice_earnings_details_uses_content_range(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_details(
                title="2025年度业绩预告",
                notice_type="业绩预告",
                report_scope="重大事项",
                notice_content="预计2025年度归属于上市公司股东的净利润同比增长45.2%至62.8%。",
                notice_attach_type="0",
            ),
            ("earnings_guidance", "positive", 2.0, 45.2, 62.8),
        )

    def test_classify_notice_earnings_details_uses_negative_content_range(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_details(
                title="2025年度业绩预告",
                notice_type="业绩预告",
                report_scope="重大事项",
                notice_content="预计2025年度归属于上市公司股东的净利润同比下降-55%至-42%。",
                notice_attach_type="0",
            ),
            ("earnings_guidance", "negative", -2.0, -55.0, -42.0),
        )

    def test_classify_notice_earnings_tag_returns_none_for_non_earnings_notice(self) -> None:
        self.assertEqual(
            _classify_notice_earnings_tag(
                "关于签署重大合同的公告",
                "签订协议",
                "重大事项",
            ),
            (None, None, None),
        )

    def test_workflow_market_context_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow = ProjectWorkflow(Path(tmpdir))
            path = workflow.root / "reports" / "market_context" / "latest.json"
            self.assertEqual(path, Path(tmpdir) / "reports" / "market_context" / "latest.json")

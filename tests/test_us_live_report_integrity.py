from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import us_generate_live_html_report as report
import us_validate_live_current as validator


class UsLiveReportIntegrityTest(unittest.TestCase):
    def test_report_integrity_rejects_missing_prices_and_contribution_mismatch(self) -> None:
        payload = {
            "results": [
                {
                    "monitor_key": "s1",
                    "sid": "strategy_one",
                    "live_return": 0.05,
                    "stocks": [
                        {
                            "code": "AAA",
                            "buy_price": None,
                            "mtm_price": 10.0,
                            "contribution": 0.0,
                        }
                    ],
                }
            ]
        }

        with self.assertRaisesRegex(RuntimeError, "missing price|contribution mismatch"):
            report.validate_payload_integrity(payload)

    def test_report_integrity_rejects_duplicate_strategy_display_ids(self) -> None:
        payload = {
            "results": [
                {"monitor_key": "a", "sid": "策略一", "live_return": 0.01, "stocks": []},
                {"monitor_key": "b", "sid": "策略一", "live_return": 0.02, "stocks": []},
            ]
        }

        with self.assertRaisesRegex(RuntimeError, "duplicate strategy display"):
            report.validate_payload_integrity(payload)

    def test_auto_raw_dir_uses_valuation_date_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = root / "2026-07-24-intraday-chart"
            stale = root / "2026-07-17-intraday-chart"
            expected.mkdir()
            stale.mkdir()

            self.assertEqual(report.resolve_raw_dir(None, "2026-07-24", root), expected)
            self.assertEqual(report.resolve_raw_dir(stale, "2026-07-24", root), stale)

    def test_validator_summary_flags_missing_prices_and_mismatched_contributions(self) -> None:
        data = {
            "results": [
                {
                    "monitor_key": "s1",
                    "live_return": 0.05,
                    "stocks": [
                        {
                            "code": "AAA",
                            "buy_price": None,
                            "mtm_price": 10.0,
                            "contribution": 0.0,
                        }
                    ],
                }
            ]
        }

        summary = validator.report_payload_quality(data)

        self.assertEqual(summary["json_missing_price_count"], 1)
        self.assertEqual(summary["json_contribution_mismatch_count"], 1)


if __name__ == "__main__":
    unittest.main()

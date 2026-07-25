from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import us_explore_strategy_rounds as rounds
import us_live_strength_strategy_exploration as live_strength
import us_audit_promoted_rounds_before_append as audit_before_append


class UsExploreStrategyRoundsConfigTest(unittest.TestCase):
    def test_promote_round_uses_same_latest_raw_dir_as_live_strength_generation(self) -> None:
        self.assertEqual(rounds.RAW_DIR, live_strength.RAW_DIR)
        self.assertIn("2026-07-24", str(rounds.RAW_DIR))

    def test_promote_round_valuation_date_is_explicit_latest_trade_date(self) -> None:
        self.assertEqual(rounds.LIVE_SIGNAL_DATE, "2026-06-30")
        self.assertEqual(rounds.LIVE_VALUATION_DATE, "2026-07-24")

    def test_promote_round_artifacts_use_latest_trade_date_prefix(self) -> None:
        self.assertEqual(rounds.ARTIFACT_DATE, "2026-07-24")
        self.assertEqual(rounds.MONITOR_RUN_DATE, "2026-07-24")

    def test_audit_defaults_use_latest_raw_dir(self) -> None:
        self.assertIn("2026-07-24", str(audit_before_append.RAW_DIR))


if __name__ == "__main__":
    unittest.main()

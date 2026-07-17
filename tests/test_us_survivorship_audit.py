from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from us_survivorship_audit import audit_membership


class UsSurvivorshipAuditTest(unittest.TestCase):
    def test_current_snapshot_only_blocks_active_monitoring(self) -> None:
        membership = pd.DataFrame(
            [
                {"symbol": "AAPL", "universe_name": "SP500", "membership_type": "current_snapshot", "effective_date": "2026-07-12", "end_date": ""},
                {"symbol": "MSFT", "universe_name": "SP500", "membership_type": "current_snapshot", "effective_date": "2026-07-12", "end_date": ""},
            ]
        )

        result = audit_membership(membership)

        self.assertFalse(result["pit_ready"])
        self.assertEqual(result["status"], "blocked_current_snapshot_only")


if __name__ == "__main__":
    unittest.main()

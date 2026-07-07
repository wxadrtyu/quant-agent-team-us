from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import RAW_MARKET_DDL


class DbSchemaTest(unittest.TestCase):
    def test_market_column_added_to_raw_and_normalized(self) -> None:
        self.assertIn("ALTER TABLE raw_market_daily", RAW_MARKET_DDL)
        self.assertIn("ALTER TABLE normalized_market_daily", RAW_MARKET_DDL)
        self.assertEqual(
            RAW_MARKET_DDL.count("ADD COLUMN IF NOT EXISTS market TEXT NOT NULL DEFAULT 'cn'"),
            2,
        )


if __name__ == "__main__":
    unittest.main()

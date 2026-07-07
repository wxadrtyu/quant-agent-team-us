from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.db import DatabaseConfig


class DbConfigTest(unittest.TestCase):
    def test_db_name_parses_socket_url(self) -> None:
        cfg = DatabaseConfig(db_url="postgresql:///quant_agent_team?host=/tmp")
        self.assertEqual(cfg.db_name, "quant_agent_team")

    def test_db_name_parses_host_url(self) -> None:
        cfg = DatabaseConfig(db_url="postgresql://localhost:5432/quant_agent_team")
        self.assertEqual(cfg.db_name, "quant_agent_team")

    def test_from_env_reads_psql_bin(self) -> None:
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"QUANT_PSQL_BIN": "/custom/psql"}):
            cfg = DatabaseConfig.from_env()
        self.assertEqual(cfg.psql_bin, Path("/custom/psql"))


if __name__ == "__main__":
    unittest.main()

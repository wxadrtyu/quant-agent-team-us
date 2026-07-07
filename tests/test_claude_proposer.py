from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.claude_proposer import ClaudeHypothesisProposer
from quant_agent_team.refinement import InvalidHypothesisError, ProposalContext


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


def _context() -> ProposalContext:
    return ProposalContext(
        market="cn", return_target=0.30, available_factors=["momentum_20d", "volatility_20d"], history=[]
    )


class ClaudeProposerTest(unittest.TestCase):
    def test_parses_valid_json_into_hypothesis(self) -> None:
        payload = (
            '{"factors": [{"name": "momentum_20d", "source_field": "momentum_20d", '
            '"direction": "long_high"}], "sector_neutral": false}'
        )
        client = _FakeClient(payload)
        proposer = ClaudeHypothesisProposer(client=client)
        hyp = proposer.propose(_context())
        self.assertEqual(hyp.market, "cn")
        self.assertEqual(len(hyp.factors), 1)
        self.assertEqual(hyp.factors[0].name, "momentum_20d")
        self.assertEqual(client.messages.last_kwargs["model"], "claude-opus-4-8")

    def test_invalid_json_raises_invalid_hypothesis(self) -> None:
        proposer = ClaudeHypothesisProposer(client=_FakeClient("not json"))
        with self.assertRaises(InvalidHypothesisError):
            proposer.propose(_context())

    def test_schema_violation_raises_invalid_hypothesis(self) -> None:
        payload = '{"factors": [{"name": "x", "source_field": "x", "direction": "sideways"}], "sector_neutral": false}'
        proposer = ClaudeHypothesisProposer(client=_FakeClient(payload))
        with self.assertRaises(InvalidHypothesisError):
            proposer.propose(_context())


if __name__ == "__main__":
    unittest.main()

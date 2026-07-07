"""Tests for A17 factor library + offline factor suggester."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_agent_team.factor_library import (  # noqa: E402
    DEFAULT_FACTOR_LIBRARY,
    FactorSpec,
    available_factors,
    build_hypothesis,
)
from quant_agent_team.offline_factor_suggester import OfflineFactorSuggester  # noqa: E402


def test_build_hypothesis_from_library():
    hyp = build_hypothesis(["ret_20d", "vol_20d"], market="cn")
    assert len(hyp.factors) == 2
    names = {f.name for f in hyp.factors}
    assert names == {"ret_20d", "vol_20d"}
    # directions come from the library
    d = {f.name: f.direction for f in hyp.factors}
    assert d["ret_20d"] == "long_high" and d["vol_20d"] == "long_low"


def test_unknown_factor_rejected():
    with pytest.raises(KeyError):
        build_hypothesis(["does_not_exist"])


def test_unreviewed_factor_cannot_enter_loop():
    lib = list(DEFAULT_FACTOR_LIBRARY) + [
        FactorSpec("experimental", "experimental", "long_high", "misc", "unproven", reviewed=False)
    ]
    with pytest.raises(ValueError):
        build_hypothesis(["experimental"], library=lib)


def test_available_factors_excludes_fundamentals_when_absent():
    no_fund = available_factors(include_fundamentals=False)
    assert "ep" not in no_fund and "roe" not in no_fund
    assert "ret_20d" in no_fund
    with_fund = available_factors(include_fundamentals=True)
    assert "ep" in with_fund and "roe" in with_fund


class _FakeBlock:
    type = "text"
    def __init__(self, text): self.text = text


class _FakeResp:
    def __init__(self, text): self.content = [_FakeBlock(text)]


class _FakeMessages:
    def create(self, **kwargs):
        payload = {"ideas": [
            {"name": "amihud_illiq", "category": "liquidity", "computable_from": "ret + amount",
             "direction": "long_high", "rationale": "Amihud illiquidity premium"},
        ]}
        return _FakeResp(json.dumps(payload))


class _FakeClient:
    messages = _FakeMessages()


def test_offline_suggester_returns_unreviewed_ideas():
    sug = OfflineFactorSuggester(client=_FakeClient())
    ideas = sug.propose_factor_ideas(DEFAULT_FACTOR_LIBRARY, market="cn", notes="momentum decaying")
    assert len(ideas) == 1
    assert ideas[0].name == "amihud_illiq"
    # offline ideas must NEVER be auto-trusted into the loop
    assert ideas[0].reviewed is False

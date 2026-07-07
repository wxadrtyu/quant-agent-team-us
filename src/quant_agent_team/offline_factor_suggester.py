"""A17 — Offline LLM factor-idea suggester (OUTSIDE the tight loop).

Locked decision (2026-06-28): the LLM does NOT propose factors inside the optimization
loop (that adds multiple-testing/overfitting risk and burns tokens). Instead it runs
OFFLINE, occasionally, to suggest NEW factor IDEAS. Every suggestion is a PROPOSAL that
a human reviews before it is added to factor_library (reviewed=True). The quant loop
only ever consumes reviewed library factors.

This also doubles as the place to ask the LLM to interpret attribution offline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List

from .factor_library import FactorSpec

FACTOR_IDEA_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "computable_from": {"type": "string", "description": "what raw data it needs"},
                    "direction": {"type": "string", "enum": ["long_high", "long_low"]},
                    "rationale": {"type": "string"},
                },
                "required": ["name", "category", "computable_from", "direction", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ideas"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a quant researcher proposing NEW candidate stock-selection factors for "
    "human review (they are NOT auto-deployed). Avoid duplicating the existing factors. "
    "Prefer factors computable from daily OHLCV + turnover + basic fundamentals. Respond "
    "only with JSON matching the schema."
)


@dataclass
class FactorIdea:
    name: str
    category: str
    computable_from: str
    direction: str
    rationale: str
    reviewed: bool = False  # ALWAYS false until a human approves it into the library


@dataclass
class OfflineFactorSuggester:
    client: Any = None
    model: str = "claude-opus-4-8"
    max_tokens: int = 1500

    def _resolve_client(self) -> Any:
        if self.client is not None:
            return self.client
        import anthropic

        self.client = anthropic.Anthropic()
        return self.client

    def _build_prompt(self, existing: List[FactorSpec], market: str, notes: str) -> str:
        lines = [
            f"Market: {market}",
            "Existing factors (do not duplicate): "
            + ", ".join(f"{f.name}[{f.category}]" for f in existing),
        ]
        if notes:
            lines.append(f"Researcher notes / what's underperforming: {notes}")
        lines.append("Propose 3-6 NEW factor ideas in distinct categories.")
        return "\n".join(lines)

    def propose_factor_ideas(
        self, existing: List[FactorSpec], market: str = "cn", notes: str = ""
    ) -> List[FactorIdea]:
        client = self._resolve_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": self._build_prompt(existing, market, notes)}],
            output_config={"format": {"type": "json_schema", "schema": FACTOR_IDEA_SCHEMA}},
        )
        text = next(block.text for block in response.content if block.type == "text")
        data = json.loads(text)
        return [
            FactorIdea(
                name=i["name"], category=i["category"], computable_from=i["computable_from"],
                direction=i["direction"], rationale=i["rationale"], reviewed=False,
            )
            for i in data["ideas"]
        ]

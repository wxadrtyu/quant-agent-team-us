from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List

from .hypothesis import FactorDef, FactorHypothesis
from .refinement import InvalidHypothesisError, ProposalContext

HYPOTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_field": {"type": "string"},
                    "direction": {"type": "string", "enum": ["long_high", "long_low"]},
                },
                "required": ["name", "source_field", "direction"],
                "additionalProperties": False,
            },
        },
        "sector_neutral": {"type": "boolean"},
    },
    "required": ["factors", "sector_neutral"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a quantitative researcher proposing a linear multi-factor stock-selection "
    "hypothesis. Choose 1-8 factors from the available list. Respond only with JSON "
    "matching the provided schema."
)


def _build_prompt(context: ProposalContext) -> str:
    lines = [
        f"Market: {context.market}",
        f"Target annualized return (net of costs, out-of-sample): >= {context.return_target:.0%}",
        f"Available factor fields: {', '.join(context.available_factors)}",
    ]
    if context.history:
        lines.append("Past attempts (most recent last):")
        for record in context.history[-5:]:
            lines.append(f"- passed={record.passed} score={record.best_score} note={record.note}")
        lines.append("Propose a different hypothesis that addresses the failures above.")
    return "\n".join(lines)


@dataclass
class ClaudeHypothesisProposer:
    client: Any = None
    model: str = "claude-opus-4-8"
    max_tokens: int = 2000

    def _resolve_client(self) -> Any:
        if self.client is not None:
            return self.client
        import anthropic

        self.client = anthropic.Anthropic()
        return self.client

    def propose(self, context: ProposalContext) -> FactorHypothesis:
        client = self._resolve_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(context)}],
            output_config={"format": {"type": "json_schema", "schema": HYPOTHESIS_SCHEMA}},
        )
        try:
            text = next(block.text for block in response.content if block.type == "text")
            data = json.loads(text)
            factors: List[FactorDef] = [
                FactorDef(name=f["name"], source_field=f["source_field"], direction=f["direction"])
                for f in data["factors"]
            ]
            return FactorHypothesis(
                market=context.market,
                factors=factors,
                sector_neutral=bool(data["sector_neutral"]),
            )
        except (StopIteration, ValueError, KeyError, TypeError) as exc:
            raise InvalidHypothesisError(str(exc)) from exc

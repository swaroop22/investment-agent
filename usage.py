"""Token usage + cost tracking across every Claude call in a committee run."""
from __future__ import annotations

from dataclasses import dataclass, field

from config import price_for


@dataclass
class CallUsage:
    agent: str
    round: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        p = price_for(self.model)
        return (
            self.input_tokens / 1_000_000 * p["input"]
            + self.output_tokens / 1_000_000 * p["output"]
            + self.cache_creation_input_tokens / 1_000_000 * p["cache_write"]
            + self.cache_read_input_tokens / 1_000_000 * p["cache_read"]
        )


@dataclass
class UsageTracker:
    calls: list = field(default_factory=list)

    def record(self, agent: str, round_name: str, model: str, usage) -> CallUsage:
        input_tokens = getattr(usage, "input_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage, "prompt_token_count", 0)

        output_tokens = getattr(usage, "output_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage, "candidates_token_count", 0)

        cache_read = getattr(usage, "cache_read_input_tokens", None)
        if cache_read is None:
            cache_read = getattr(usage, "cached_content_token_count", 0)

        cache_write = getattr(usage, "cache_creation_input_tokens", 0)

        call = CallUsage(
            agent=agent,
            round=round_name,
            model=model,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            cache_creation_input_tokens=cache_write or 0,
            cache_read_input_tokens=cache_read or 0,
        )
        self.calls.append(call)
        return call

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def by_agent(self) -> dict:
        out: dict[str, dict] = {}
        for c in self.calls:
            bucket = out.setdefault(c.agent, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            bucket["calls"] += 1
            bucket["input_tokens"] += c.input_tokens
            bucket["output_tokens"] += c.output_tokens
            bucket["cost_usd"] += c.cost_usd
        for bucket in out.values():
            bucket["cost_usd"] = round(bucket["cost_usd"], 6)
        return out

    def summary(self) -> dict:
        return {
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "by_agent": self.by_agent(),
        }

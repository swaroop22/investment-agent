"""Base classes and data structures for LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TokenUsage:
    """Normalized token usage matching UsageTracker expectation."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class AgentResult:
    agent: str
    round: str
    parsed: dict
    transcript: list = field(default_factory=list)


class BaseProvider(ABC):
    """Abstract base class for all LLM providers (Anthropic, Gemini, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'anthropic' or 'gemini'."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier for this provider."""
        pass

    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str]:
        """Check whether the necessary API keys or tokens are set.
        Returns (is_valid, warning_message).
        """
        pass

    @abstractmethod
    async def run_agent(
        self,
        *,
        agent_name: str,
        round_name: str,
        system: str,
        user_content: str,
        output_schema: dict,
        tools: list[dict] | None,
        dispatch: dict[str, Callable],
        tracker: Any,
        model: str,
        max_tokens: int,
    ) -> AgentResult:
        """Execute agent's tool loop and return parsed structured output."""
        pass

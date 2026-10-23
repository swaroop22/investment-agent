"""Single-agent call: provider delegation + structured JSON final answer."""
from __future__ import annotations

from typing import Any

from config import MODEL, MAX_TOKENS
from providers.anthropic_provider import AnthropicProvider
from providers.base import AgentResult, BaseProvider
from tool_defs import DISPATCH
from usage import UsageTracker


async def run_agent(
    provider_or_client: BaseProvider | Any,
    *,
    agent_name: str,
    round_name: str,
    system: str,
    user_content: str,
    output_schema: dict,
    tools: list[dict] | None,
    tracker: UsageTracker,
    model: str = MODEL,
    max_tokens: int = MAX_TOKENS,
) -> AgentResult:
    """Execute a single agent's reasoning & tool loop using the configured provider."""
    if isinstance(provider_or_client, BaseProvider):
        provider = provider_or_client
    else:
        # Backward compatibility for direct Anthropic client instances (e.g. mock client)
        provider = AnthropicProvider(client=provider_or_client)

    return await provider.run_agent(
        agent_name=agent_name,
        round_name=round_name,
        system=system,
        user_content=user_content,
        output_schema=output_schema,
        tools=tools,
        dispatch=DISPATCH,
        tracker=tracker,
        model=model,
        max_tokens=max_tokens,
    )


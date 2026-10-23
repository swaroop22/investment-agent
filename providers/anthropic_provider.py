"""Anthropic LLM provider implementation."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from providers.base import AgentResult, BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, client=None, api_key: str | None = None):
        self._client = client
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return "claude-opus-5"

    def validate_credentials(self) -> tuple[bool, str]:
        if self._client is not None:
            return True, ""
        has_key = bool(self._api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        if not has_key:
            return False, (
                "ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN not set; "
                "relying on default SDK credential resolution."
            )
        return True, ""

    def get_client(self):
        if self._client is not None:
            return self._client
        import anthropic
        if self._api_key:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        else:
            self._client = anthropic.AsyncAnthropic()
        return self._client

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
        client = self.get_client()
        messages = [{"role": "user", "content": user_content}]
        tools = tools or []

        output_config = {"format": {"type": "json_schema", "schema": output_schema}}

        while True:
            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_config=output_config,
            )
            if tools:
                kwargs["tools"] = tools

            response = await client.messages.create(**kwargs)
            tracker.record(agent_name, round_name, model, response.usage)

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    try:
                        result = dispatch[block.name](block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error running {block.name}: {e}",
                            "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            messages.append({"role": "assistant", "content": response.content})
            text = next(b.text for b in response.content if getattr(b, "type", None) == "text")
            parsed = json.loads(text)
            return AgentResult(agent=agent_name, round=round_name, parsed=parsed, transcript=messages)

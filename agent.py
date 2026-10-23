"""Single-agent call: manual tool-use loop + structured JSON final answer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from config import MODEL, MAX_TOKENS
from tool_defs import DISPATCH
from usage import UsageTracker


@dataclass
class AgentResult:
    agent: str
    round: str
    parsed: dict
    transcript: list = field(default_factory=list)  # full message list for this call


async def run_agent(
    client: anthropic.AsyncAnthropic,
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
    messages = [{"role": "user", "content": user_content}]
    tools = tools or []

    output_config = {"format": {"type": "json_schema", "schema": output_schema}}

    # Tool-use loop: keep calling until Claude stops requesting tools.
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
                if block.type != "tool_use":
                    continue
                try:
                    result = DISPATCH[block.name](block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                except Exception as e:  # noqa: BLE001 - surface to the model as a tool error
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error running {block.name}: {e}",
                        "is_error": True,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        # Done — output_config guarantees the text block is valid JSON per schema.
        messages.append({"role": "assistant", "content": response.content})
        text = next(b.text for b in response.content if b.type == "text")
        parsed = json.loads(text)
        return AgentResult(agent=agent_name, round=round_name, parsed=parsed, transcript=messages)

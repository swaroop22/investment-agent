"""A fake AsyncAnthropic client for exercising the committee flow with zero network/API calls.

It mimics the subset of the real SDK surface agent.py touches:
client.messages.create(**kwargs) -> an object with .stop_reason, .content, .usage.

For any request with `tools`, it emits one tool_use block per tool (first call only),
then on the follow-up (tool_results present in the last user message) returns a text
block containing JSON satisfying the request's output_schema's `required` fields with
placeholder values. For tool-less requests it returns the JSON answer immediately.
"""
from __future__ import annotations

import json
import random
import types


class FakeUsage:
    def __init__(self, input_tokens=120, output_tokens=80):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text

    def model_dump(self):
        return {"type": "text", "text": self.text}


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id_, name, input_):
        self.id = id_
        self.name = name
        self.input = input_

    def model_dump(self):
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


class FakeMessage:
    def __init__(self, content, stop_reason, usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or FakeUsage()


_ENUM_DEFAULTS = {
    "strong_sell": 0, "sell": 1, "hold": 2, "buy": 3, "strong_buy": 4,
}


def _placeholder_for_schema(schema: dict, path_hint: str = "", active_symbol: str = "AAPL"):
    """Produce a minimal value satisfying a JSON-schema fragment."""
    t = schema.get("type")
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if t == "object":
        props = schema.get("properties", {})
        required = schema.get("required", list(props.keys()))
        return {k: _placeholder_for_schema(props[k], k, active_symbol) for k in required}
    if t == "array":
        item_schema = schema.get("items", {"type": "string"})
        return [_placeholder_for_schema(item_schema, path_hint, active_symbol), _placeholder_for_schema(item_schema, path_hint, active_symbol)]
    if t == "string":
        if path_hint == "symbol":
            return active_symbol
        return f"[mock {path_hint or 'text'}]"
    if t == "number":
        return round(random.uniform(0.4, 0.9), 2)
    if t == "integer":
        return random.randint(0, 3)
    if t == "boolean":
        return random.choice([True, False])
    return None


class FakeMessagesResource:
    def __init__(self):
        self.call_count = 0

    async def create(self, *, model, max_tokens, messages, system=None, tools=None, output_config=None, **_):
        self.call_count += 1
        tools = tools or []

        # Detect symbol from user message if possible
        active_symbol = "AAPL"
        first_content = messages[0].get("content", "") if messages else ""
        if isinstance(first_content, str):
            import re
            m = re.search(r"\b([A-Z]{1,5})\b", first_content)
            if m:
                active_symbol = m.group(1)

        last_msg = messages[-1]
        had_tool_results = (
            isinstance(last_msg["content"], list)
            and len(last_msg["content"]) > 0
            and isinstance(last_msg["content"][0], dict)
            and last_msg["content"][0].get("type") == "tool_result"
        )

        if tools and not had_tool_results:
            # First turn with tools available: call every declared tool once (parallel tool use).
            blocks = []
            for i, tool in enumerate(tools):
                blocks.append(FakeToolUseBlock(f"toolu_{self.call_count}_{i}", tool["name"], {"symbol": active_symbol}))
            return FakeMessage(content=blocks, stop_reason="tool_use")

        # Either no tools, or tools already satisfied — return the structured JSON answer.
        schema = (output_config or {}).get("format", {}).get("schema", {"type": "object", "properties": {}})
        payload = _placeholder_for_schema(schema, active_symbol=active_symbol)
        text = json.dumps(payload)
        return FakeMessage(content=[FakeTextBlock(text)], stop_reason="end_turn")



class FakeAsyncAnthropic:
    def __init__(self, *_, **__):
        self.messages = FakeMessagesResource()

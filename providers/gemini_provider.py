"""Google Gemini LLM provider implementation using official google-genai SDK."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from providers.base import AgentResult, BaseProvider, TokenUsage


class GeminiProvider(BaseProvider):
    def __init__(self, client=None, api_key: str | None = None):
        self._client = client
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash"

    def validate_credentials(self) -> tuple[bool, str]:
        if self._client is not None:
            return True, ""
        has_key = bool(self._api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        if not has_key:
            return False, (
                "GEMINI_API_KEY / GOOGLE_API_KEY not set; "
                "please export GEMINI_API_KEY=... or GOOGLE_API_KEY=... to run with Gemini."
            )
        return True, ""

    def get_client(self):
        if self._client is not None:
            return self._client
        from google import genai
        api_key = self._api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = genai.Client()
        return self._client

    def _convert_tools(self, tools: list[dict] | None):
        if not tools:
            return None
        from google.genai import types
        fn_decls = []
        for t in tools:
            params = dict(t.get("input_schema", {}))
            params.pop("additionalProperties", None)
            fn_decls.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=params,
                )
            )
        return [types.Tool(function_declarations=fn_decls)]

    def _clean_json_text(self, text: str) -> str:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean.rsplit("```", 1)[0]
            clean = clean.strip()
        return clean

    def _serialize_contents(self, contents: list) -> list[dict]:
        serialized = []
        for c in contents:
            role = getattr(c, "role", "unknown")
            parts_serialized = []
            for p in getattr(c, "parts", []):
                if getattr(p, "text", None):
                    parts_serialized.append({"type": "text", "text": p.text})
                elif getattr(p, "function_call", None):
                    fc = p.function_call
                    parts_serialized.append({
                        "type": "tool_use",
                        "name": getattr(fc, "name", ""),
                        "input": dict(getattr(fc, "args", {}) or {}),
                    })
                elif getattr(p, "function_response", None):
                    fr = p.function_response
                    parts_serialized.append({
                        "type": "tool_result",
                        "name": getattr(fr, "name", ""),
                        "content": getattr(fr, "response", {}),
                    })
            serialized.append({"role": role, "content": parts_serialized})
        return serialized

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
        from google.genai import types

        client = self.get_client()

        system_instruction = (
            system
            + "\n\nCRITICAL REQUIREMENT: Your final response MUST be a valid JSON object matching this schema:\n"
            + json.dumps(output_schema)
        )

        gemini_tools = self._convert_tools(tools)
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_content)],
            )
        ]

        # Use JSON mode directly when no tools are declared
        config_kwargs = {
            "system_instruction": system_instruction,
            "max_output_tokens": max_tokens,
            "temperature": 0.2,
        }
        if gemini_tools:
            config_kwargs["tools"] = gemini_tools
        else:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = output_schema

        config = types.GenerateContentConfig(**config_kwargs)

        while True:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            if response.usage_metadata:
                tracker.record(agent_name, round_name, model, response.usage_metadata)

            if response.function_calls:
                candidate = response.candidates[0]
                contents.append(candidate.content)

                tool_response_parts = []
                for fc in response.function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args or {})
                    try:
                        res = dispatch[fn_name](fn_args)
                    except Exception as e:
                        res = {"error": f"Error running {fn_name}: {e}"}
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": res},
                        )
                    )

                contents.append(
                    types.Content(
                        role="user",
                        parts=tool_response_parts,
                    )
                )
                continue

            # Done — candidate generated final text
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            raw_text = response.text or ""
            clean_text = self._clean_json_text(raw_text)
            parsed = json.loads(clean_text)

            return AgentResult(
                agent=agent_name,
                round=round_name,
                parsed=parsed,
                transcript=self._serialize_contents(contents),
            )

"""Unit tests for the multi-provider abstraction (Anthropic & Gemini)."""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from config import DEFAULT_MODELS, default_model_for, price_for
from providers import AnthropicProvider, GeminiProvider, get_provider
from usage import UsageTracker


class TestProviderRegistry(unittest.TestCase):
    def test_get_provider_anthropic(self):
        p = get_provider("anthropic")
        self.assertIsInstance(p, AnthropicProvider)
        self.assertEqual(p.name, "anthropic")
        self.assertEqual(p.default_model, "claude-opus-5")

    def test_get_provider_gemini(self):
        p = get_provider("gemini")
        self.assertIsInstance(p, GeminiProvider)
        self.assertEqual(p.name, "gemini")
        self.assertEqual(p.default_model, "gemini-2.5-flash")

    def test_get_provider_invalid(self):
        with self.assertRaises(ValueError):
            get_provider("unsupported_provider")

    def test_model_defaults_and_pricing(self):
        self.assertEqual(default_model_for("anthropic"), "claude-opus-5")
        self.assertEqual(default_model_for("gemini"), "gemini-2.5-flash")

        p_claude = price_for("claude-opus-5")
        self.assertEqual(p_claude["input"], 5.00)

        p_gemini = price_for("gemini-2.5-flash")
        self.assertEqual(p_gemini["input"], 0.15)
        self.assertEqual(p_gemini["output"], 0.60)


class TestGeminiProvider(unittest.TestCase):
    def test_credentials_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            p = GeminiProvider()
            valid, msg = p.validate_credentials()
            self.assertFalse(valid)
            self.assertIn("GEMINI_API_KEY", msg)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}, clear=True):
            p = GeminiProvider()
            valid, msg = p.validate_credentials()
            self.assertTrue(valid)

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=True):
            p = GeminiProvider()
            valid, msg = p.validate_credentials()
            self.assertTrue(valid)

    def test_convert_tools(self):
        provider = GeminiProvider()
        tools = [
            {
                "name": "get_financials",
                "description": "Financial metrics",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                    "additionalProperties": False,
                },
            }
        ]
        gemini_tools = provider._convert_tools(tools)
        self.assertIsNotNone(gemini_tools)
        self.assertEqual(len(gemini_tools), 1)
        fn_decl = gemini_tools[0].function_declarations[0]
        self.assertEqual(fn_decl.name, "get_financials")
        self.assertEqual(fn_decl.description, "Financial metrics")

    def test_gemini_run_agent_mocked(self):
        from google.genai import types

        # Create mock client
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()

        # Step 1: Function call response
        fc_part = types.Part(function_call=types.FunctionCall(name="test_tool", args={"x": 10}))
        msg_call = types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=[fc_part]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=100, candidates_token_count=20),
        )

        # Step 2: Final text JSON response
        text_part = types.Part(text='{"recommendation": "buy", "score": 9.5}')
        msg_final = types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=[text_part]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=150, candidates_token_count=40),
        )

        mock_client.aio.models.generate_content = AsyncMock(side_effect=[msg_call, msg_final])

        provider = GeminiProvider(client=mock_client)
        tracker = UsageTracker()

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
            }
        ]
        dispatch = {"test_tool": lambda args: {"result_x": args["x"] * 2}}

        schema = {
            "type": "object",
            "properties": {"recommendation": {"type": "string"}, "score": {"type": "number"}},
            "required": ["recommendation", "score"],
        }

        result = asyncio.run(
            provider.run_agent(
                agent_name="tester",
                round_name="round1",
                system="You are a test agent.",
                user_content="Perform analysis.",
                output_schema=schema,
                tools=tools,
                dispatch=dispatch,
                tracker=tracker,
                model="gemini-2.5-flash",
                max_tokens=2000,
            )
        )

        self.assertEqual(result.agent, "tester")
        self.assertEqual(result.parsed["recommendation"], "buy")
        self.assertEqual(result.parsed["score"], 9.5)
        self.assertEqual(tracker.total_input_tokens, 250)
        self.assertEqual(tracker.total_output_tokens, 60)


if __name__ == "__main__":
    unittest.main()

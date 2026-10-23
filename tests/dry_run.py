#!/usr/bin/env python3
"""Exercise the full committee flow with a fake Claude client (no API key, no network calls
to Anthropic). Real yfinance tool calls still run against AAPL. Run from repo root:

    ./venv/bin/python -m tests.dry_run
"""
import argparse
import asyncio
import sys
import warnings

import anthropic

from tests.mock_client import FakeAsyncAnthropic

warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*inplace keyword.*")

# Patch before importing committee so `anthropic.AsyncAnthropic()` inside it resolves to the fake.
anthropic.AsyncAnthropic = FakeAsyncAnthropic

import committee  # noqa: E402


def main():
    args = argparse.Namespace(
        symbol="AAPL",
        portfolio_context="Test portfolio context: 10% position limit, no existing holding.",
        model="claude-opus-5",
        max_tokens=8000,
        out_dir="transcripts",
    )
    asyncio.run(committee.main_async(args))


if __name__ == "__main__":
    sys.exit(main())

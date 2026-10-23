#!/usr/bin/env python3
"""Multi-agent investment committee CLI.

Usage:
    python committee.py MSFT
    python committee.py AAPL --portfolio-context "5% tech-heavy portfolio, $2000 current position"
    python committee.py NVDA --max-tokens 6000 --out-dir transcripts
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import warnings
from datetime import datetime, timezone

import prompts
from agent import run_agent
from config import MODEL, MAX_TOKENS, DEFAULT_PROVIDER, default_model_for
from providers import get_provider
from schemas import (
    DEVILS_ADVOCATE_SCHEMA,
    FINAL_MEMO_SCHEMA,
    FUNDAMENTAL_REPORT_SCHEMA,
    REBUTTAL_SCHEMA,
    RISK_REPORT_SCHEMA,
    SENTIMENT_REPORT_SCHEMA,
    TECHNICAL_REPORT_SCHEMA,
)
from tool_defs import FUNDAMENTAL_TOOLS, SENTIMENT_TOOLS, TECHNICAL_TOOLS
from usage import UsageTracker

warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*inplace keyword.*")

RATING_TO_VOTE = {
    "strong_buy": "buy",
    "buy": "buy",
    "hold": "hold",
    "sell": "sell",
    "strong_sell": "sell",
}

ROLE_TITLES = {
    "fundamental_analyst": "Fundamental Analyst",
    "technical_analyst": "Technical Analyst",
    "sentiment_analyst": "Sentiment Analyst",
}


async def run_round1(client, symbol, tracker, model, max_tokens):
    """Analysts 1-3 run in parallel."""
    tasks = [
        run_agent(
            client,
            agent_name="fundamental_analyst",
            round_name="round1",
            system=prompts.FUNDAMENTAL_ANALYST_SYSTEM,
            user_content=f"Analyze {symbol} and produce your fundamental report.",
            output_schema=FUNDAMENTAL_REPORT_SCHEMA,
            tools=FUNDAMENTAL_TOOLS,
            tracker=tracker,
            model=model,
            max_tokens=max_tokens,
        ),
        run_agent(
            client,
            agent_name="technical_analyst",
            round_name="round1",
            system=prompts.TECHNICAL_ANALYST_SYSTEM,
            user_content=f"Analyze {symbol} and produce your technical report.",
            output_schema=TECHNICAL_REPORT_SCHEMA,
            tools=TECHNICAL_TOOLS,
            tracker=tracker,
            model=model,
            max_tokens=max_tokens,
        ),
        run_agent(
            client,
            agent_name="sentiment_analyst",
            round_name="round1",
            system=prompts.SENTIMENT_ANALYST_SYSTEM,
            user_content=f"Analyze {symbol} and produce your sentiment report.",
            output_schema=SENTIMENT_REPORT_SCHEMA,
            tools=SENTIMENT_TOOLS,
            tracker=tracker,
            model=model,
            max_tokens=max_tokens,
        ),
    ]
    fundamental, technical, sentiment = await asyncio.gather(*tasks)
    return fundamental, technical, sentiment


async def run_round2(client, symbol, round1_reports, portfolio_context, tracker, model, max_tokens):
    """Risk Manager and Devil's Advocate respond to round 1, in parallel."""
    reports_json = json.dumps([r.parsed for r in round1_reports], indent=2)

    risk_task = run_agent(
        client,
        agent_name="risk_manager",
        round_name="round2",
        system=prompts.RISK_MANAGER_SYSTEM,
        user_content=(
            f"Symbol: {symbol}\n\n"
            f"Portfolio context: {portfolio_context}\n\n"
            f"Analyst reports from Round 1:\n{reports_json}\n\n"
            "Produce your risk assessment."
        ),
        output_schema=RISK_REPORT_SCHEMA,
        tools=None,
        tracker=tracker,
        model=model,
        max_tokens=max_tokens,
    )
    devil_task = run_agent(
        client,
        agent_name="devils_advocate",
        round_name="round2",
        system=prompts.DEVILS_ADVOCATE_SYSTEM,
        user_content=(
            f"Symbol: {symbol}\n\n"
            f"Analyst reports from Round 1:\n{reports_json}\n\n"
            "Identify the emerging consensus and argue against it."
        ),
        output_schema=DEVILS_ADVOCATE_SCHEMA,
        tools=None,
        tracker=tracker,
        model=model,
        max_tokens=max_tokens,
    )
    risk, devil = await asyncio.gather(risk_task, devil_task)
    return risk, devil


async def run_round3(client, symbol, round1_reports, risk, devil, tracker, model, max_tokens):
    """Each Round 1 analyst gets one rebuttal, in parallel."""
    risk_json = json.dumps(risk.parsed, indent=2)
    devil_json = json.dumps(devil.parsed, indent=2)

    tasks = []
    for report in round1_reports:
        role_title = ROLE_TITLES[report.agent]
        system = prompts.REBUTTAL_SYSTEM_TEMPLATE.format(role_title=role_title, symbol=symbol)
        user_content = (
            f"Your original Round 1 report:\n{json.dumps(report.parsed, indent=2)}\n\n"
            f"Risk Manager's response:\n{risk_json}\n\n"
            f"Devil's Advocate's response:\n{devil_json}\n\n"
            "Give your rebuttal."
        )
        tasks.append(run_agent(
            client,
            agent_name=report.agent,
            round_name="round3",
            system=system,
            user_content=user_content,
            output_schema=REBUTTAL_SCHEMA,
            tools=None,
            tracker=tracker,
            model=model,
            max_tokens=max_tokens,
        ))
    return await asyncio.gather(*tasks)


async def run_chair(client, symbol, round1, round2, round3, tracker, model, max_tokens):
    transcript_summary = {
        "round1_analyst_reports": [r.parsed for r in round1],
        "round2_risk_and_devil": [r.parsed for r in round2],
        "round3_rebuttals": [r.parsed for r in round3],
    }
    return await run_agent(
        client,
        agent_name="chair",
        round_name="final",
        system=prompts.CHAIR_SYSTEM.format(symbol=symbol),
        user_content=(
            f"Full committee debate transcript for {symbol}:\n"
            f"{json.dumps(transcript_summary, indent=2)}\n\n"
            "Write the final decision memo."
        ),
        output_schema=FINAL_MEMO_SCHEMA,
        tools=None,
        tracker=tracker,
        model=model,
        max_tokens=max_tokens,
    )


def tally_votes(round3, risk, devil) -> dict:
    tally = {"buy": 0, "hold": 0, "sell": 0}
    for r in round3:
        vote = RATING_TO_VOTE.get(r.parsed["rating"], "hold")
        tally[vote] += 1
    tally[risk.parsed["vote"]] += 1
    tally[devil.parsed["vote"]] += 1
    return tally


def _serialize_message(m: dict) -> dict:
    content = m["content"]
    if isinstance(content, list):
        content = [
            block.model_dump() if hasattr(block, "model_dump") else block
            for block in content
        ]
    return {"role": m["role"], "content": content}


def build_transcript(symbol, round1, round2, round3, chair_result, tracker, started_at) -> dict:
    def report_block(r):
        return {
            "agent": r.agent,
            "round": r.round,
            "output": r.parsed,
            "messages": [_serialize_message(m) for m in r.transcript],
        }

    return {
        "symbol": symbol,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "rounds": {
            "round1_analysts": [report_block(r) for r in round1],
            "round2_risk_devil": [report_block(r) for r in round2],
            "round3_rebuttals": [report_block(r) for r in round3],
            "final_chair_memo": report_block(chair_result),
        },
        "vote_tally": tally_votes(round3, *round2),
        "usage": tracker.summary(),
    }


def print_memo(memo: dict, tally: dict, usage_summary: dict):
    print("\n" + "=" * 72)
    print(f"  INVESTMENT COMMITTEE DECISION MEMO — {memo['symbol']}")
    print("=" * 72)
    print(f"\nDECISION: {memo['decision'].upper()}   (confidence: {memo['overall_confidence']:.0%})")
    print(f"VOTE TALLY: buy={tally['buy']}  hold={tally['hold']}  sell={tally['sell']}")
    print(f"\nExecutive Summary:\n  {memo['executive_summary']}")
    print(f"\nFundamental View:\n  {memo['fundamental_view']}")
    print(f"\nTechnical View:\n  {memo['technical_view']}")
    print(f"\nSentiment View:\n  {memo['sentiment_view']}")
    print(f"\nRisk Assessment:\n  {memo['risk_assessment']}")
    print(f"\nDevil's Advocate Challenge:\n  {memo['devils_advocate_challenge']}")
    print(f"\nRecommended Position Sizing:\n  {memo['recommended_position_sizing']}")
    print("\nKey Catalysts to Watch:")
    for c in memo["key_catalysts_to_watch"]:
        print(f"  - {c}")
    print("\nInvalidation Conditions:")
    for c in memo["invalidation_conditions"]:
        print(f"  - {c}")
    print("\n" + "-" * 72)
    print(f"Token usage: {usage_summary['total_input_tokens']:,} in / "
          f"{usage_summary['total_output_tokens']:,} out across {usage_summary['total_calls']} calls")
    print(f"Estimated cost: ${usage_summary['total_cost_usd']:.4f}")
    print("-" * 72 + "\n")


async def main_async(args):
    symbol = args.symbol.upper()
    provider_name = getattr(args, "provider", None) or DEFAULT_PROVIDER
    provider = get_provider(provider_name)
    model = getattr(args, "model", None) or default_model_for(provider_name)

    valid, warning = provider.validate_credentials()
    if not valid and warning:
        if provider.name == "gemini":
            print(f"\n[Error] {warning}\n", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Warning: {warning}", file=sys.stderr)

    tracker = UsageTracker()
    started_at = datetime.now(timezone.utc).isoformat()

    print(f"Using provider: {provider.name} | Model: {model}")
    print(f"[1/4] Round 1 — Fundamental, Technical, Sentiment analysts (parallel)...")
    round1 = await run_round1(provider, symbol, tracker, model, args.max_tokens)

    print(f"[2/4] Round 2 — Risk Manager and Devil's Advocate (parallel)...")
    round2 = await run_round2(provider, symbol, round1, args.portfolio_context, tracker, model, args.max_tokens)

    print(f"[3/4] Round 3 — Analyst rebuttals (parallel)...")
    round3 = await run_round3(provider, symbol, round1, *round2, tracker, model, args.max_tokens)

    print(f"[4/4] Final — Chair writes decision memo...")
    chair_result = await run_chair(provider, symbol, round1, round2, round3, tracker, model, args.max_tokens)

    tally = tally_votes(round3, *round2)
    print_memo(chair_result.parsed, tally, tracker.summary())

    os.makedirs(args.out_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(args.out_dir, f"{symbol}_{ts}.json")
    transcript = build_transcript(symbol, round1, round2, round3, chair_result, tracker, started_at)
    with open(out_path, "w") as f:
        json.dump(transcript, f, indent=2, default=str)
    print(f"Full transcript saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Multi-agent investment committee")
    parser.add_argument("symbol", help="Ticker symbol, e.g. MSFT")
    parser.add_argument("--portfolio-context", default="No specific portfolio context provided; assume a diversified retail portfolio with no existing position in this name.",
                         help="Free-text portfolio context for the Risk Manager")
    parser.add_argument("--provider", choices=["anthropic", "gemini"], default=DEFAULT_PROVIDER,
                         help=f"LLM provider to use: 'anthropic' or 'gemini' (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--model", default=None,
                         help="Model ID (defaults to provider default: e.g. claude-opus-5 for anthropic, gemini-2.5-flash for gemini)")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--out-dir", default="transcripts")
    args = parser.parse_args()

    if args.model is None:
        args.model = default_model_for(args.provider)

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

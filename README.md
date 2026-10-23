# Investment Committee

A multi-agent investment committee built on the Anthropic Python SDK. Six Claude
agents — each a separate system prompt and, for the analysts, their own tools —
debate a stock ticker over three rounds and a Chair writes the final decision memo.

## Setup

```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...   # or ANTHROPIC_AUTH_TOKEN / an `ant auth login` profile
```

Requires Python 3.12+ (pandas-ta's current release needs it).

## Usage

```bash
./venv/bin/python committee.py MSFT
./venv/bin/python committee.py AAPL --portfolio-context "5% tech-heavy portfolio, $2000 current position"
./venv/bin/python committee.py NVDA --model claude-opus-5 --max-tokens 6000
```

Prints a decision memo (decision, vote tally, confidence, rationale) to stdout and
writes the full debate transcript — every message, tool call, and parsed JSON
output, plus token usage and cost — to `transcripts/<SYMBOL>_<timestamp>.json`.

## Flow

1. **Round 1** (parallel): Fundamental Analyst (`get_financials`), Technical Analyst
   (`get_price_history`, `get_technical_indicators` — RSI/MACD/SMAs via pandas-ta),
   and Sentiment Analyst (`get_news`, `get_social_sentiment`) each produce a
   structured report.
2. **Round 2** (parallel): Risk Manager (sees Round 1 reports + portfolio context)
   and Devil's Advocate (argues against the emerging consensus) respond.
3. **Round 3** (parallel): each Round 1 analyst files one rebuttal, having seen
   Round 2.
4. **Final**: the Chair synthesizes everything into a decision memo with a
   buy/hold/sell vote tally and overall confidence.

Every agent call enforces a JSON schema via `output_config.format`, so each
hand-off between agents is structured data, not freeform text.

## Files

- `committee.py` — CLI entrypoint and round orchestration (asyncio)
- `agent.py` — single-agent tool-use loop + structured output parsing
- `prompts.py` — system prompt per committee seat
- `schemas.py` — JSON schemas enforced on each agent's output
- `tool_defs.py` — tool definitions + dispatch table
- `tools/market_data.py` — yfinance-backed data functions (financials, price
  history, technical indicators, news, and a labeled keyword-heuristic
  sentiment score — not a real sentiment model)
- `usage.py` — token usage + cost tracking (`config.PRICING`)
- `config.py` — model id and pricing table
- `tests/` — a fake Claude client for exercising the full flow without API
  credentials (`./venv/bin/python -m tests.dry_run`)

## Notes

- Sentiment is a simple keyword heuristic over Yahoo Finance headlines, labeled
  as such in both the tool output and the Sentiment Analyst's prompt — it is a
  placeholder for a real sentiment/news API, not a production-grade signal.
- Cost tracking pricing lives in `config.PRICING`; update it if you change
  `--model` to something other than `claude-opus-5`.

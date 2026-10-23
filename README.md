# Investment Committee

A multi-agent investment committee with multi-provider LLM support (**Anthropic Claude** and **Google Gemini**). Six AI agents — each with a dedicated system prompt and, for the analysts, their own market data tools — debate a stock ticker over three rounds and a Chair writes the final decision memo.

## Setup

```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt

# For Anthropic (Claude):
export ANTHROPIC_API_KEY=sk-ant-...   # or ANTHROPIC_AUTH_TOKEN

# For Google Gemini:
export GEMINI_API_KEY=AIzaSy...       # or GOOGLE_API_KEY

# Optional: set default provider globally (default is anthropic)
export PROVIDER=gemini                # or anthropic
```

Requires Python 3.12+ (pandas-ta's current release needs it).

## Web UI Dashboard

Launch the interactive financial terminal dashboard:
```bash
./venv/bin/python server.py --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to:
- Browse all previous investment committee deliberations and transcripts.
- View the executive consensus, vote tally, confidence meter, and position sizing.
- Inspect round-by-round specialist reports (Fundamental, Technical, Sentiment, Risk Manager, Devil's Advocate, and Analyst Rebuttals).
- Launch new committee deliberations directly from the UI with live progress streaming.

## CLI Usage

Run with Google Gemini:
```bash
./venv/bin/python committee.py NVDA --provider gemini
./venv/bin/python committee.py AAPL --provider gemini --model gemini-2.5-pro
```

Run with Anthropic Claude:
```bash
./venv/bin/python committee.py MSFT --provider anthropic
./venv/bin/python committee.py AAPL --provider anthropic --portfolio-context "5% tech-heavy portfolio, $2000 current position"
./venv/bin/python committee.py NVDA --provider anthropic --model claude-opus-5 --max-tokens 6000
```

Prints a decision memo (decision, vote tally, confidence, rationale) to stdout and
writes the full debate transcript — every message, tool call, and parsed JSON
output, plus token usage and cost — to `transcripts/<SYMBOL>_<timestamp>.json`.

## Supported Providers & Models

| Provider | Default Model | Configurable Models | Key Environment Variable |
|---|---|---|---|
| `gemini` | `gemini-2.5-flash` | `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) |
| `anthropic` | `claude-opus-5` | `claude-opus-5`, `claude-3-7-sonnet-latest`, `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) |

Set default provider in `config.py` (`DEFAULT_PROVIDER`) or via `PROVIDER` environment variable, or pass `--provider` directly to the CLI.

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

Every agent call enforces a JSON schema, so each hand-off between agents is structured data, not freeform text.

## Files

- `committee.py` — CLI entrypoint and round orchestration (asyncio)
- `agent.py` — single-agent runner delegating to the configured provider
- `providers/` — multi-provider abstraction:
  - `providers/base.py` — `BaseProvider` abstract class, `AgentResult`, `TokenUsage`
  - `providers/gemini_provider.py` — Google Gemini integration (`google-genai` SDK)
  - `providers/anthropic_provider.py` — Anthropic Claude integration (`anthropic` SDK)
- `prompts.py` — system prompt per committee seat
- `schemas.py` — JSON schemas enforced on each agent's output
- `tool_defs.py` — tool definitions + dispatch table
- `tools/market_data.py` — yfinance-backed data functions (financials, price
  history, technical indicators, news, and a labeled keyword-heuristic
  sentiment score — not a real sentiment model)
- `usage.py` — token usage + cost tracking across Anthropic and Gemini models
- `config.py` — provider configuration, model mappings, and pricing table
- `tests/` — tests including dry-runs and provider unit tests (`./venv/bin/python -m unittest tests/test_providers.py` and `./venv/bin/python -m tests.dry_run`)


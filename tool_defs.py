"""Raw JSON-schema tool definitions + dispatch, split by analyst role."""
from tools import market_data as md

FINANCIALS_TOOL = {
    "name": "get_financials",
    "description": "Key financial statement figures and valuation/profitability/growth/balance-sheet ratios for a stock ticker.",
    "input_schema": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "Ticker symbol, e.g. MSFT"}},
        "required": ["symbol"],
        "additionalProperties": False,
    },
}

PRICE_HISTORY_TOOL = {
    "name": "get_price_history",
    "description": "Raw daily OHLCV price history for a ticker over a given period.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "period": {"type": "string", "description": "e.g. '1mo', '3mo', '6mo', '1y', '2y'", "default": "1y"},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
}

TECHNICAL_INDICATORS_TOOL = {
    "name": "get_technical_indicators",
    "description": "RSI(14), MACD(12,26,9), and SMA/EMA(20,50,200) computed from recent daily price history.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "period": {"type": "string", "description": "lookback window for indicator calculation, e.g. '1y'", "default": "1y"},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
}

NEWS_TOOL = {
    "name": "get_news",
    "description": "Recent news headlines for a ticker.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
}

SOCIAL_SENTIMENT_TOOL = {
    "name": "get_social_sentiment",
    "description": "Keyword-heuristic sentiment score derived from recent headlines (not a ground-truth sentiment model — treat as a rough signal).",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["symbol"],
        "additionalProperties": False,
    },
}

DISPATCH = {
    "get_financials": lambda i: md.get_financials(i["symbol"]),
    "get_price_history": lambda i: md.get_price_history(i["symbol"], i.get("period", "1y")),
    "get_technical_indicators": lambda i: md.get_technical_indicators(i["symbol"], i.get("period", "1y")),
    "get_news": lambda i: md.get_news(i["symbol"], i.get("limit", 10)),
    "get_social_sentiment": lambda i: md.get_social_sentiment(i["symbol"], i.get("limit", 10)),
}

FUNDAMENTAL_TOOLS = [FINANCIALS_TOOL]
TECHNICAL_TOOLS = [PRICE_HISTORY_TOOL, TECHNICAL_INDICATORS_TOOL]
SENTIMENT_TOOLS = [NEWS_TOOL, SOCIAL_SENTIMENT_TOOL]

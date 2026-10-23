"""Data-fetching functions backing the committee's Claude tool calls.

All functions take a ticker symbol and return plain JSON-serializable dicts
so they can be dropped directly into a tool_result content block.
"""
from __future__ import annotations

import warnings
from functools import lru_cache

import pandas as pd
import yfinance as yf

# yfinance still calls pandas with inplace=True in a few spots; pandas 3.x
# warns but behaves correctly, so silence the noise rather than pin pandas back.
warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*inplace keyword.*")


@lru_cache(maxsize=16)
def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def _round_floats(obj):
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v) for v in obj]
    return obj


def get_financials(symbol: str) -> dict:
    """Key financial statement line items and valuation/profitability ratios."""
    t = _ticker(symbol)
    info = t.info or {}

    def g(key):
        v = info.get(key)
        return v if v is not None else None

    result = {
        "symbol": symbol,
        "name": g("shortName"),
        "sector": g("sector"),
        "industry": g("industry"),
        "market_cap": g("marketCap"),
        "valuation": {
            "trailing_pe": g("trailingPE"),
            "forward_pe": g("forwardPE"),
            "price_to_book": g("priceToBook"),
            "price_to_sales_ttm": g("priceToSalesTrailing12Months"),
            "peg_ratio": g("pegRatio") or g("trailingPegRatio"),
            "ev_to_ebitda": g("enterpriseToEbitda"),
            "ev_to_revenue": g("enterpriseToRevenue"),
        },
        "profitability": {
            "gross_margins": g("grossMargins"),
            "operating_margins": g("operatingMargins"),
            "profit_margins": g("profitMargins"),
            "return_on_equity": g("returnOnEquity"),
            "return_on_assets": g("returnOnAssets"),
        },
        "growth": {
            "revenue_growth_yoy": g("revenueGrowth"),
            "earnings_growth_yoy": g("earningsGrowth"),
            "earnings_quarterly_growth": g("earningsQuarterlyGrowth"),
        },
        "balance_sheet": {
            "total_cash": g("totalCash"),
            "total_debt": g("totalDebt"),
            "debt_to_equity": g("debtToEquity"),
            "current_ratio": g("currentRatio"),
            "quick_ratio": g("quickRatio"),
        },
        "cash_flow": {
            "free_cashflow": g("freeCashflow"),
            "operating_cashflow": g("operatingCashflow"),
        },
        "dividend": {
            "dividend_yield": g("dividendYield"),
            "payout_ratio": g("payoutRatio"),
        },
        "per_share": {
            "trailing_eps": g("trailingEps"),
            "forward_eps": g("forwardEps"),
            "book_value": g("bookValue"),
        },
    }
    return _round_floats(result)


def get_price_history(symbol: str, period: str = "1y", interval: str = "1d") -> dict:
    """Raw OHLCV price history."""
    t = _ticker(symbol)
    hist: pd.DataFrame = t.history(period=period, interval=interval)
    if hist.empty:
        return {"symbol": symbol, "period": period, "interval": interval, "rows": []}

    hist = hist.reset_index()
    date_col = "Date" if "Date" in hist.columns else "Datetime"
    rows = []
    for _, row in hist.iterrows():
        rows.append({
            "date": str(row[date_col].date()) if hasattr(row[date_col], "date") else str(row[date_col]),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        })
    return {"symbol": symbol, "period": period, "interval": interval, "rows": rows}


def get_technical_indicators(symbol: str, period: str = "1y") -> dict:
    """RSI(14), MACD(12,26,9), and SMA/EMA(20,50,200) computed with pandas-ta."""
    import pandas_ta as ta  # imported lazily: heavy optional dependency

    t = _ticker(symbol)
    hist: pd.DataFrame = t.history(period=period, interval="1d")
    if hist.empty or len(hist) < 30:
        return {"symbol": symbol, "error": "insufficient price history for indicators"}

    hist = hist.rename(columns=str.lower)

    rsi = hist.ta.rsi(length=14)
    macd = hist.ta.macd(fast=12, slow=26, signal=9)
    sma20 = hist.ta.sma(length=20)
    sma50 = hist.ta.sma(length=50)
    sma200 = hist.ta.sma(length=200) if len(hist) >= 200 else None
    ema12 = hist.ta.ema(length=12)
    ema26 = hist.ta.ema(length=26)

    last_close = float(hist["close"].iloc[-1])

    def last(series):
        if series is None or series.empty or pd.isna(series.iloc[-1]):
            return None
        return round(float(series.iloc[-1]), 4)

    macd_cols = macd.columns if macd is not None else []
    macd_line = last(macd[macd_cols[0]]) if len(macd_cols) > 0 else None
    macd_hist = last(macd[macd_cols[1]]) if len(macd_cols) > 1 else None
    macd_signal = last(macd[macd_cols[2]]) if len(macd_cols) > 2 else None

    return {
        "symbol": symbol,
        "as_of": str(hist.index[-1].date()),
        "last_close": round(last_close, 4),
        "rsi_14": last(rsi),
        "macd": {
            "macd_line": macd_line,
            "signal_line": macd_signal,
            "histogram": macd_hist,
        },
        "moving_averages": {
            "sma_20": last(sma20),
            "sma_50": last(sma50),
            "sma_200": last(sma200) if sma200 is not None else None,
            "ema_12": last(ema12),
            "ema_26": last(ema26),
            "price_vs_sma20_pct": round((last_close / last(sma20) - 1) * 100, 2) if last(sma20) else None,
            "price_vs_sma50_pct": round((last_close / last(sma50) - 1) * 100, 2) if last(sma50) else None,
        },
    }


def get_news(symbol: str, limit: int = 10) -> dict:
    """Recent news headlines for the symbol, as returned by Yahoo Finance."""
    t = _ticker(symbol)
    try:
        items = t.news or []
    except Exception as e:
        return {"symbol": symbol, "articles": [], "error": str(e)}

    articles = []
    for item in items[:limit]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        publisher = (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher")
        pub_date = content.get("pubDate") or item.get("providerPublishTime")
        link = ((content.get("canonicalUrl") or {}).get("url")
                if isinstance(content.get("canonicalUrl"), dict) else item.get("link"))
        if title:
            articles.append({
                "title": title,
                "publisher": publisher,
                "published": str(pub_date),
                "link": link,
            })
    return {"symbol": symbol, "articles": articles}


_POSITIVE_WORDS = {
    "beat", "beats", "surge", "soar", "rally", "upgrade", "upgraded", "record",
    "growth", "strong", "outperform", "bullish", "gain", "gains", "win", "wins",
    "profit", "boost", "positive", "buy", "raise", "raised", "expand", "breakthrough",
}
_NEGATIVE_WORDS = {
    "miss", "misses", "plunge", "slump", "downgrade", "downgraded", "lawsuit",
    "probe", "investigation", "weak", "underperform", "bearish", "loss", "losses",
    "cut", "cuts", "decline", "falls", "fall", "negative", "sell", "layoff", "layoffs",
    "recall", "fraud", "fine", "scandal", "warning",
}


def get_social_sentiment(symbol: str, limit: int = 10) -> dict:
    """Lightweight keyword-based sentiment heuristic over recent headlines.

    This is a crude stand-in for a real social/news sentiment API and is
    labeled as such in its output so the Sentiment Analyst can weigh it
    accordingly rather than treating it as ground truth.
    """
    news = get_news(symbol, limit=limit)
    articles = news.get("articles", [])

    scored = []
    pos_total = neg_total = 0
    for a in articles:
        title_words = {w.strip(".,!?:;'\"()").lower() for w in a["title"].split()}
        pos = len(title_words & _POSITIVE_WORDS)
        neg = len(title_words & _NEGATIVE_WORDS)
        pos_total += pos
        neg_total += neg
        score = pos - neg
        scored.append({"title": a["title"], "score": score})

    net = pos_total - neg_total
    if net > 1:
        label = "positive"
    elif net < -1:
        label = "negative"
    else:
        label = "neutral"

    return {
        "symbol": symbol,
        "method": "keyword_heuristic_over_headlines (not a real sentiment model)",
        "articles_analyzed": len(articles),
        "positive_hits": pos_total,
        "negative_hits": neg_total,
        "net_score": net,
        "label": label,
        "headline_scores": scored,
    }

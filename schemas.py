"""JSON schemas enforced via output_config.format on every agent call.

Keeping these as plain dicts (not a tool) means each agent's final answer is
guaranteed-valid JSON text in the response, independent of any tool calls it
made along the way to gather data.
"""

RATING_ENUM = ["strong_sell", "sell", "hold", "buy", "strong_buy"]
VOTE_ENUM = ["buy", "hold", "sell"]

FUNDAMENTAL_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string", "const": "fundamental_analyst"},
        "symbol": {"type": "string"},
        "rating": {"type": "string", "enum": RATING_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "key_metrics": {
            "type": "object",
            "properties": {
                "valuation_assessment": {"type": "string"},
                "profitability_assessment": {"type": "string"},
                "growth_assessment": {"type": "string"},
                "balance_sheet_assessment": {"type": "string"},
            },
            "required": ["valuation_assessment", "profitability_assessment",
                         "growth_assessment", "balance_sheet_assessment"],
            "additionalProperties": False,
        },
        "bull_points": {"type": "array", "items": {"type": "string"}},
        "bear_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agent", "symbol", "rating", "confidence", "summary",
                 "key_metrics", "bull_points", "bear_points"],
    "additionalProperties": False,
}

TECHNICAL_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string", "const": "technical_analyst"},
        "symbol": {"type": "string"},
        "rating": {"type": "string", "enum": RATING_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "signals": {
            "type": "object",
            "properties": {
                "trend": {"type": "string", "enum": ["uptrend", "downtrend", "sideways"]},
                "rsi_signal": {"type": "string", "enum": ["overbought", "oversold", "neutral"]},
                "macd_signal": {"type": "string", "enum": ["bullish_crossover", "bearish_crossover", "no_crossover"]},
                "moving_average_signal": {"type": "string", "enum": ["golden_cross", "death_cross", "above_averages", "below_averages", "mixed"]},
            },
            "required": ["trend", "rsi_signal", "macd_signal", "moving_average_signal"],
            "additionalProperties": False,
        },
        "bull_points": {"type": "array", "items": {"type": "string"}},
        "bear_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agent", "symbol", "rating", "confidence", "summary",
                 "signals", "bull_points", "bear_points"],
    "additionalProperties": False,
}

SENTIMENT_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string", "const": "sentiment_analyst"},
        "symbol": {"type": "string"},
        "rating": {"type": "string", "enum": RATING_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "sentiment_label": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
        "data_quality_caveat": {"type": "string"},
        "bull_points": {"type": "array", "items": {"type": "string"}},
        "bear_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agent", "symbol", "rating", "confidence", "summary",
                 "sentiment_label", "data_quality_caveat", "bull_points", "bear_points"],
    "additionalProperties": False,
}

RISK_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string", "const": "risk_manager"},
        "symbol": {"type": "string"},
        "vote": {"type": "string", "enum": VOTE_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "position_sizing_guidance": {"type": "string"},
        "key_risks": {"type": "array", "items": {"type": "string"}},
        "risk_mitigations": {"type": "array", "items": {"type": "string"}},
        "concentration_concern": {"type": "boolean"},
    },
    "required": ["agent", "symbol", "vote", "confidence", "summary",
                 "position_sizing_guidance", "key_risks", "risk_mitigations",
                 "concentration_concern"],
    "additionalProperties": False,
}

DEVILS_ADVOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string", "const": "devils_advocate"},
        "symbol": {"type": "string"},
        "vote": {"type": "string", "enum": VOTE_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "consensus_being_challenged": {"type": "string"},
        "counterarguments": {"type": "array", "items": {"type": "string"}},
        "overlooked_risks": {"type": "array", "items": {"type": "string"}},
        "what_would_change_my_mind": {"type": "string"},
    },
    "required": ["agent", "symbol", "vote", "confidence", "summary",
                 "consensus_being_challenged", "counterarguments",
                 "overlooked_risks", "what_would_change_my_mind"],
    "additionalProperties": False,
}

REBUTTAL_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string"},
        "symbol": {"type": "string"},
        "rating": {"type": "string", "enum": RATING_ENUM},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "stance_changed": {"type": "boolean"},
        "rebuttal": {"type": "string"},
        "concessions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agent", "symbol", "rating", "confidence", "stance_changed",
                 "rebuttal", "concessions"],
    "additionalProperties": False,
}

FINAL_MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "decision": {"type": "string", "enum": VOTE_ENUM},
        "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "vote_tally": {
            "type": "object",
            "properties": {
                "buy": {"type": "integer", "minimum": 0},
                "hold": {"type": "integer", "minimum": 0},
                "sell": {"type": "integer", "minimum": 0},
            },
            "required": ["buy", "hold", "sell"],
            "additionalProperties": False,
        },
        "executive_summary": {"type": "string"},
        "fundamental_view": {"type": "string"},
        "technical_view": {"type": "string"},
        "sentiment_view": {"type": "string"},
        "risk_assessment": {"type": "string"},
        "devils_advocate_challenge": {"type": "string"},
        "recommended_position_sizing": {"type": "string"},
        "key_catalysts_to_watch": {"type": "array", "items": {"type": "string"}},
        "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["symbol", "decision", "overall_confidence", "vote_tally",
                 "executive_summary", "fundamental_view", "technical_view",
                 "sentiment_view", "risk_assessment", "devils_advocate_challenge",
                 "recommended_position_sizing", "key_catalysts_to_watch",
                 "invalidation_conditions"],
    "additionalProperties": False,
}

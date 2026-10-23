"""Shared configuration: model id and pricing used for cost tracking."""

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

# USD per 1M tokens. Keep in sync with the model actually used above.
PRICING = {
    "claude-opus-5": {
        "input": 5.00,
        "output": 25.00,
        "cache_write": 6.25,   # ~1.25x input
        "cache_read": 0.50,    # ~0.1x input
    },
}


def price_for(model: str) -> dict:
    if model not in PRICING:
        raise KeyError(f"No pricing entry for model '{model}' — add one to config.PRICING")
    return PRICING[model]

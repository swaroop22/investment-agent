"""Shared configuration: provider, model id, and pricing used for cost tracking."""
import os

DEFAULT_PROVIDER = os.environ.get("PROVIDER", "anthropic").lower()

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "gemini": "gemini-2.5-flash",
}

MODEL = DEFAULT_MODELS.get(DEFAULT_PROVIDER, "claude-opus-5")
MAX_TOKENS = 8000

# USD per 1M tokens. Keep in sync with the model actually used.
PRICING = {
    # Anthropic models
    "claude-opus-5": {
        "input": 5.00,
        "output": 25.00,
        "cache_write": 6.25,   # ~1.25x input
        "cache_read": 0.50,    # ~0.1x input
    },
    "claude-3-7-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-3-5-haiku-latest": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
    # Gemini models
    "gemini-2.5-flash": {
        "input": 0.15,
        "output": 0.60,
        "cache_write": 0.0,
        "cache_read": 0.0375,
    },
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 5.00,
        "cache_write": 0.0,
        "cache_read": 0.3125,
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
        "cache_write": 0.0,
        "cache_read": 0.025,
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00,
        "cache_write": 0.0,
        "cache_read": 0.3125,
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
        "cache_write": 0.0,
        "cache_read": 0.01875,
    },
}


def default_model_for(provider: str) -> str:
    """Return the default model name for the given provider."""
    return DEFAULT_MODELS.get(provider.lower(), "claude-opus-5")


def price_for(model: str) -> dict:
    if model in PRICING:
        return PRICING[model]
    # Fallback default pricing if model is not in table
    return {
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.00,
        "cache_read": 0.20,
    }


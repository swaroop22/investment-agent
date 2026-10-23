"""Provider registry and exports."""
from __future__ import annotations

from config import DEFAULT_PROVIDER
from providers.anthropic_provider import AnthropicProvider
from providers.base import AgentResult, BaseProvider, TokenUsage
from providers.gemini_provider import GeminiProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str | None = None, **kwargs) -> BaseProvider:
    """Instantiate a provider by name (e.g. 'anthropic' or 'gemini')."""
    provider_name = (name or DEFAULT_PROVIDER).lower()
    if provider_name not in PROVIDERS:
        supported = ", ".join(repr(k) for k in PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Supported providers: {supported}")
    return PROVIDERS[provider_name](**kwargs)


__all__ = [
    "AgentResult",
    "AnthropicProvider",
    "BaseProvider",
    "GeminiProvider",
    "PROVIDERS",
    "TokenUsage",
    "get_provider",
]

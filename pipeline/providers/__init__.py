"""Provider registry. Pick providers by name in config/providers.yaml."""
from __future__ import annotations

from .base import Provider, ProviderError, VoiceResult
from .edge_tts_voice import EdgeTTSProvider
from .mock import MockProvider
from .openart import OpenArtProvider
from .viewmax import ViewmaxProvider

REGISTRY: dict[str, type[Provider]] = {
    "mock": MockProvider,
    "openart": OpenArtProvider,
    "viewmax": ViewmaxProvider,
    "edge_tts": EdgeTTSProvider,
}


def provider_class(name: str) -> type[Provider]:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ProviderError(f"unknown provider '{name}'; choose from {sorted(REGISTRY)}") from None


def get_provider(name: str, settings=None) -> Provider:
    """Instantiate a provider. Only called after the approval gate passes."""
    return provider_class(name)(settings)


__all__ = ["Provider", "ProviderError", "VoiceResult", "REGISTRY", "get_provider", "provider_class"]

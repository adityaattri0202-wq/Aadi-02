"""Provider adapter interface. Stages only talk to providers through this."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ProviderError(RuntimeError):
    """Provider misconfigured (e.g. missing key) or the API call failed."""


@dataclass
class VoiceResult:
    path: Path
    duration_sec: float
    # word timings: [{"word": str, "start": float, "end": float}, ...] (may be empty)
    words: list = field(default_factory=list)


def require_env(name: str) -> str:
    """Read an API key from the environment only. Never from code or repo files."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderError(
            f"{name} is not set. Copy .env.example to .env, fill it in, and load it "
            f"with: set -a; source .env; set +a"
        )
    return value


class Provider(ABC):
    """Abstract adapter. Each method writes exactly one file at ``out_path``."""

    name: str = "base"
    image_extension = ".png"
    video_extension = ".mp4"
    voice_extension = ".mp3"

    def __init__(self, settings=None):
        self.settings = settings

    @abstractmethod
    def generate_image(self, prompt: str, out_path: Path, *, negative_prompt: str = "",
                       width: int = 1920, height: int = 1080) -> Path:
        """Text-to-image. Returns the written path."""

    @abstractmethod
    def generate_video(self, image_path: Path, prompt: str, out_path: Path, *,
                       motion: str, duration_sec: float) -> Path:
        """Image-to-video for hero shots. Returns the written path."""

    @abstractmethod
    def generate_voice(self, text: str, out_path: Path, *, voice: str) -> VoiceResult:
        """Text-to-speech. Returns the audio path, duration and word timings."""

    def unsupported(self, what: str):
        raise ProviderError(f"provider '{self.name}' does not support {what}; "
                            f"pick another in config/providers.yaml")

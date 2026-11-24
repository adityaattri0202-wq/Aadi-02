"""Viewmax adapter. STUB, NOT VERIFIED.

TODO(viewmax): fill in from Viewmax's official API documentation:
  - BASE_URL and auth header format
  - image generation, image-to-video, and voiceover endpoints + payloads
  - voice ids for the US and UK voices (put them in config/audience.yaml)
  - whether TTS returns word timings; if not, return words=[] and the audio
    duration (e.g. via ffprobe)
  - job polling and result download
Every method raises NotImplementedError before any network call.
"""
from __future__ import annotations

from pathlib import Path

from .base import Provider, require_env

BASE_URL = "TODO_VIEWMAX_API_BASE_URL"


class ViewmaxProvider(Provider):
    name = "viewmax"
    image_extension = ".png"
    video_extension = ".mp4"
    voice_extension = ".mp3"
    env_key = "VIEWMAX_API_KEY"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.api_key = require_env(self.env_key)

    def _todo(self, what: str):
        raise NotImplementedError(
            f"Viewmax {what} is not implemented. Fill in pipeline/providers/viewmax.py "
            f"from Viewmax's API docs (endpoint, payload, polling, download)."
        )

    def generate_image(self, prompt, out_path: Path, *, negative_prompt="", width=1920, height=1080):
        self._todo("image generation")  # TODO(viewmax)

    def generate_video(self, image_path: Path, prompt, out_path: Path, *, motion, duration_sec):
        self._todo("image-to-video")  # TODO(viewmax)

    def generate_voice(self, text, out_path: Path, *, voice):
        if voice.startswith("TODO"):
            raise NotImplementedError("Set the Viewmax voice ids in config/audience.yaml")
        self._todo("voiceover")  # TODO(viewmax): return VoiceResult(path, duration, words)

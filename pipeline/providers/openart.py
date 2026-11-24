"""OpenArt adapter. STUB, NOT VERIFIED.

TODO(openart): fill in from OpenArt's official API documentation:
  - BASE_URL and auth header format
  - text-to-image endpoint, model id, request fields (prompt, negative
    prompt, width/height or aspect ratio), response shape
  - image-to-video endpoint, how the source image is uploaded/referenced,
    motion/duration fields
  - job polling (status URL, terminal states, rate limits) and result download
Until then every method raises NotImplementedError *before* any network call,
so nothing is ever sent to an unverified endpoint.
"""
from __future__ import annotations

from pathlib import Path

from .base import Provider, require_env

BASE_URL = "TODO_OPENART_API_BASE_URL"


class OpenArtProvider(Provider):
    name = "openart"
    image_extension = ".png"
    video_extension = ".mp4"
    env_key = "OPENART_API_KEY"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.api_key = require_env(self.env_key)

    def _todo(self, what: str):
        raise NotImplementedError(
            f"OpenArt {what} is not implemented. Fill in pipeline/providers/openart.py "
            f"from OpenArt's API docs (endpoint, payload, polling, download)."
        )

    def generate_image(self, prompt, out_path: Path, *, negative_prompt="", width=1920, height=1080):
        # TODO(openart): POST {BASE_URL}/<image endpoint> with
        #   headers={"Authorization": f"Bearer {self.api_key}"}  (verify format)
        #   json={"prompt": prompt, "negative_prompt": negative_prompt, ...}
        # then poll the job and download the image to out_path.
        self._todo("text-to-image")

    def generate_video(self, image_path: Path, prompt, out_path: Path, *, motion, duration_sec):
        # TODO(openart): upload image_path, start image-to-video with prompt and
        # duration_sec, poll, download the MP4 to out_path.
        self._todo("image-to-video")

    def generate_voice(self, text, out_path: Path, *, voice):
        self.unsupported("text-to-speech")

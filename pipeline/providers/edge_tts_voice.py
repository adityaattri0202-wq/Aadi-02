"""Free voice provider using the ``edge-tts`` package (voice only).

Requires ``pip install edge-tts`` and network access to Microsoft's speech
service. Check its terms before commercial use. Returns real word timings.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from .base import Provider, ProviderError, VoiceResult

_TICKS = 10_000_000  # edge-tts offsets are in 100 ns units


class EdgeTTSProvider(Provider):
    name = "edge_tts"
    voice_extension = ".mp3"

    def generate_image(self, *a, **k):
        self.unsupported("images")

    def generate_video(self, *a, **k):
        self.unsupported("video")

    def generate_voice(self, text, out_path: Path, *, voice):
        try:
            import edge_tts
        except ImportError as exc:
            raise ProviderError("pip install edge-tts to use provider edge_tts") from exc
        rate = "-4%"
        if self.settings is not None:
            rate = str(self.settings.audience.get("voices", {}).get("edge_tts_rate", rate))
        words: list[dict] = []
        tmp = out_path.with_suffix(out_path.suffix + ".part")

        async def run():
            comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            with open(tmp, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / _TICKS
                        words.append({"word": chunk["text"], "start": round(start, 3),
                                      "end": round(start + chunk["duration"] / _TICKS, 3)})

        asyncio.run(run())
        tmp.replace(out_path)
        return VoiceResult(out_path, _duration(out_path, words), words)


def _duration(path: Path, words: list) -> float:
    if shutil.which("ffprobe"):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
        try:
            return round(float(out.stdout.strip()), 3)
        except ValueError:
            pass
    return round(words[-1]["end"] + 0.2, 3) if words else 0.0

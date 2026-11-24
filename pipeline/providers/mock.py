"""Offline mock provider for tests and wiring checks. Spends nothing.

Writes a small solid-colour PNG, a placeholder (not playable) .mp4, and a
silent WAV whose length matches the text at ~140 words per minute.
"""
from __future__ import annotations

import struct
import wave
import zlib
from pathlib import Path

from .base import Provider, VoiceResult


def _write_png(path: Path, w: int, h: int, rgb=(214, 196, 160)) -> None:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw))
                     + chunk(b"IEND", b""))


class MockProvider(Provider):
    name = "mock"
    image_extension = ".png"
    video_extension = ".mp4"
    voice_extension = ".wav"

    calls: list = []  # class-level record of every call, for tests

    def generate_image(self, prompt, out_path, *, negative_prompt="", width=1920, height=1080):
        MockProvider.calls.append(("image", out_path.name))
        _write_png(out_path, 160, 90)
        return out_path

    def generate_video(self, image_path, prompt, out_path, *, motion, duration_sec):
        MockProvider.calls.append(("video", out_path.name))
        out_path.write_text(f"MOCK VIDEO\nimage={image_path.name}\nmotion={motion}\n"
                            f"duration={duration_sec}\n", encoding="utf-8")
        return out_path

    def generate_voice(self, text, out_path, *, voice):
        MockProvider.calls.append(("voice", out_path.name))
        words = text.split()
        duration = round(max(1.0, len(words) / (140 / 60)), 3)
        rate = 8000
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(duration * rate))
        step = duration / max(len(words), 1)
        timings = [{"word": wd, "start": round(i * step, 3), "end": round((i + 1) * step, 3)}
                   for i, wd in enumerate(words)]
        return VoiceResult(out_path, duration, timings)

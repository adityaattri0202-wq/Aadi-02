"""File layout of a topic folder. All stages find their inputs/outputs here."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def slugify(name: str) -> str:
    """'Livyatan melvillei' -> 'livyatan_melvillei'."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug:
        raise ValueError(f"cannot make a topic slug from {name!r}")
    return slug


@dataclass(frozen=True)
class TopicPaths:
    """Paths for ``<root>/topics/<slug>/``."""

    root: Path
    slug: str

    @property
    def dir(self) -> Path:
        return self.root / "topics" / self.slug

    # inputs
    @property
    def topic_yaml(self) -> Path:
        return self.dir / "topic.yaml"

    @property
    def script_md(self) -> Path:
        return self.dir / "script.md"

    # stage outputs
    @property
    def script_check_json(self) -> Path:
        return self.dir / "script_check.json"

    @property
    def sources_md(self) -> Path:
        return self.dir / "sources.md"

    @property
    def shots_json(self) -> Path:
        return self.dir / "shots.json"

    @property
    def images_dir(self) -> Path:
        return self.dir / "images"

    @property
    def clips_dir(self) -> Path:
        return self.dir / "clips"

    @property
    def voiceover_dir(self) -> Path:
        return self.dir / "voiceover"

    @property
    def segments_json(self) -> Path:
        return self.voiceover_dir / "segments.json"

    @property
    def manifest_json(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def timeline_csv(self) -> Path:
        return self.dir / "timeline.csv"

    @property
    def timeline_edl(self) -> Path:
        return self.dir / "timeline.edl"

    @property
    def subtitles_srt(self) -> Path:
        return self.dir / "subtitles.srt"

    @property
    def report_md(self) -> Path:
        return self.dir / "review_report.md"

    @property
    def logs_dir(self) -> Path:
        return self.dir / "logs"

    def rel(self, path: Path) -> str:
        """Path relative to the topic folder, with forward slashes."""
        return path.relative_to(self.dir).as_posix()

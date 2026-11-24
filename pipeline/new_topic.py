"""Scaffold ``topics/<slug>/`` with a topic.yaml and script.md template."""
from __future__ import annotations

from pathlib import Path

from .paths import TopicPaths

TOPIC_TEMPLATE = """name: {name}
target_minutes: 8
required_sections: [Hook, Outro]
facts:
  - claim: "TODO: a key fact"
    source: ""
    verified: false
"""

SCRIPT_TEMPLATE = """# {name}

## Hook
[SHOT: describe what we see | motion=slow_push_in]
Opening line that makes the viewer stay. [VERIFY: any fact here]

## Outro
[SHOT: describe the closing image]
Closing line and call to subscribe.
"""


def create(root: Path, slug: str, name: str) -> list[Path]:
    p = TopicPaths(root, slug)
    p.dir.mkdir(parents=True, exist_ok=True)
    made = []
    for path, text in ((p.topic_yaml, TOPIC_TEMPLATE), (p.script_md, SCRIPT_TEMPLATE)):
        if not path.exists():
            path.write_text(text.format(name=name), encoding="utf-8")
            made.append(path)
    for d in (p.images_dir, p.clips_dir, p.voiceover_dir, p.logs_dir):
        d.mkdir(exist_ok=True)
    return made

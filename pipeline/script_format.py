"""Parser for ``script.md``.

Format::

    # Video title

    ## Hook                      <- each "##" heading is a scene
    [SHOT: what we see | motion=slow_push_in | overlay=36 cm (14 in) | dur=4]
    Narration for this shot. Facts awaiting a check carry [VERIFY: note].

    More narration for the same shot (until the next [SHOT] or heading).

``[SHOT: ...]`` lines are optional: a scene with none gets one shot per
paragraph. Lines starting with ``>`` are director notes and are not spoken.
HTML comments are ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import MOTIONS

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SHOT_RE = re.compile(r"^\s*\[SHOT:\s*(.*?)\]\s*$", re.IGNORECASE)
VERIFY_RE = re.compile(r"\[VERIFY(?::\s*([^\]]*))?\]", re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SCENE_PREFIX_RE = re.compile(r"^scene\s+\d+\s*[:.\-–—]\s*", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’.,\-][A-Za-z0-9À-ɏ]+)*")


@dataclass
class RawShot:
    line: int
    visual: str = ""
    motion: str = "none"
    overlay: str = ""
    duration: float | None = None
    explicit: bool = False
    paragraphs: list = field(default_factory=list)

    @property
    def raw_narration(self) -> str:
        return " ".join(" ".join(p) for p in self.paragraphs if p).strip()

    @property
    def narration(self) -> str:
        return clean_narration(self.raw_narration)


@dataclass
class Section:
    title: str
    line: int
    shots: list = field(default_factory=list)

    @property
    def name(self) -> str:
        """Heading without a 'Scene 3:' prefix."""
        return SCENE_PREFIX_RE.sub("", self.title).strip()


@dataclass
class ParsedScript:
    title: str
    sections: list
    errors: list


def clean_narration(text: str) -> str:
    """Spoken text: drop [VERIFY] tags and markdown emphasis, tidy spaces."""
    text = VERIFY_RE.sub("", text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text)
    return text.strip()


def count_words(text: str) -> int:
    """Spoken words, ignoring [VERIFY] tags and markdown."""
    return len(WORD_RE.findall(clean_narration(text)))


def _strip_comments(md: str) -> str:
    # keep line numbers stable
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), md)


def _parse_shot(content: str, line: int, errors: list) -> RawShot:
    parts = [p.strip() for p in content.split("|")]
    shot = RawShot(line=line, visual=parts[0], explicit=True)
    if not shot.visual:
        errors.append(f"line {line}: [SHOT] needs a visual description")
    for part in parts[1:]:
        key, _, value = part.partition("=")
        key, value = key.strip().lower(), value.strip()
        if key == "motion":
            if value not in MOTIONS:
                errors.append(f"line {line}: motion '{value}' must be one of {MOTIONS}")
            else:
                shot.motion = value
        elif key == "overlay":
            shot.overlay = value
        elif key in ("dur", "duration"):
            try:
                shot.duration = float(value.rstrip("s"))
            except ValueError:
                errors.append(f"line {line}: bad duration '{value}'")
        else:
            errors.append(f"line {line}: unknown [SHOT] option '{key}'")
    return shot


def parse_script(md: str) -> ParsedScript:
    title, sections, errors = "", [], []
    current: Section | None = None
    shot: RawShot | None = None

    for lineno, raw in enumerate(_strip_comments(md).splitlines(), 1):
        line = raw.strip()
        heading = HEADING_RE.match(line)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            if level == 1 and not title:
                title = text
            else:
                current = Section(title=text, line=lineno)
                sections.append(current)
                shot = None
            continue
        if not line or line.startswith(">") or set(line) <= {"-", "*", "_"}:
            if not line and shot is not None:
                if shot.explicit:
                    if shot.paragraphs and shot.paragraphs[-1]:
                        shot.paragraphs.append([])  # paragraph break inside explicit shot
                else:
                    shot = None  # implicit shot ends at a blank line
            continue
        m = SHOT_RE.match(line)
        if m:
            if current is None:
                errors.append(f"line {lineno}: [SHOT] before the first '##' scene heading")
                continue
            shot = _parse_shot(m.group(1), lineno, errors)
            current.shots.append(shot)
            continue
        if current is None:
            continue  # intro text before the first scene is not narration
        if shot is None:
            shot = RawShot(line=lineno, explicit=False, paragraphs=[[]])
            current.shots.append(shot)
        if not shot.paragraphs:
            shot.paragraphs.append([])
        shot.paragraphs[-1].append(line)

    return ParsedScript(title=title, sections=sections, errors=errors)

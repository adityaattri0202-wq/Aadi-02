"""Stage 1: validate script.md.

Checks required sections, counts spoken words, estimates runtime at 130-150
words per minute, lists [VERIFY] tags, and flags metric measurements with no
imperial equivalent. With ``--publish`` any [VERIFY] tag or unverified fact in
topic.yaml fails the stage. Writes ``script_check.json`` and ``sources.md``.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from .config import load_topic
from .context import Context, StageFailed
from .script_format import VERIFY_RE, count_words, parse_script
from .sources import write_sources

WPM_LOW, WPM_HIGH = 130, 150
DEFAULT_REQUIRED = ["Hook", "Outro"]

_METRIC_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:-\s*)?(?:m|metres?|meters?|cm|centimetres?|centimeters?|mm|"
    r"km|kilometres?|kilometers?|kg|kilograms?|tonnes?)\b", re.IGNORECASE)
_IMPERIAL_RE = re.compile(r"\b(?:ft|feet|foot|in|inch(?:es)?|yd|yards?|miles?|lbs?|pounds?|tons?)\b",
                          re.IGNORECASE)


@dataclass
class CheckResult:
    word_count: int = 0
    runtime_minutes_fast: float = 0.0   # at 150 wpm
    runtime_minutes_slow: float = 0.0   # at 130 wpm
    target_minutes: float | None = None
    sections: list = field(default_factory=list)
    shot_count: int = 0
    verify_tags: list = field(default_factory=list)
    unverified_facts: list = field(default_factory=list)
    missing_sections: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def estimate_runtime(words: int, wpm_low: int = WPM_LOW, wpm_high: int = WPM_HIGH) -> tuple[float, float]:
    """(fastest, slowest) runtime in minutes."""
    return round(words / wpm_high, 2), round(words / wpm_low, 2)


def find_verify_tags(md: str) -> list[dict]:
    tags = []
    for lineno, line in enumerate(md.splitlines(), 1):
        for m in VERIFY_RE.finditer(line):
            tags.append({"line": lineno, "note": (m.group(1) or "").strip()})
    return tags


def find_missing_imperial(md: str) -> list[str]:
    out = []
    for lineno, line in enumerate(md.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in _METRIC_RE.finditer(line):
            window = line[m.end(): m.end() + 40]
            if not _IMPERIAL_RE.search(window):
                out.append(f"line {lineno}: '{m.group(0)}' has no imperial equivalent nearby")
    return out


def check_script(md: str, *, required_sections=None, publish: bool = False,
                 facts=(), target_minutes: float | None = None,
                 warn_units: bool = True) -> CheckResult:
    """Pure check used by the stage and unit tests."""
    res = CheckResult(target_minutes=target_minutes)
    parsed = parse_script(md)
    res.errors.extend(parsed.errors)
    if not parsed.title:
        res.warnings.append("no '# Title' line at the top of script.md")
    if not parsed.sections:
        res.errors.append("script.md has no '## ' scene sections")

    names = []
    for sec in parsed.sections:
        words = sum(count_words(s.raw_narration) for s in sec.shots)
        names.append(sec.name)
        res.sections.append({"title": sec.title, "line": sec.line, "words": words, "shots": len(sec.shots)})
        res.shot_count += len(sec.shots)
        if words == 0:
            res.errors.append(f"section '{sec.title}' (line {sec.line}) has no narration")
        for s in sec.shots:
            if not s.raw_narration and s.duration is None:
                res.errors.append(f"line {s.line}: shot has no narration and no dur=")

    lowered = {n.lower() for n in names}
    res.missing_sections = [r for r in (required_sections or DEFAULT_REQUIRED) if r.lower() not in lowered]
    for r in res.missing_sections:
        res.errors.append(f"missing required section '## {r}'")

    res.word_count = sum(s["words"] for s in res.sections)
    res.runtime_minutes_fast, res.runtime_minutes_slow = estimate_runtime(res.word_count)
    if target_minutes:
        if res.runtime_minutes_slow < target_minutes * 0.8 or res.runtime_minutes_fast > target_minutes * 1.2:
            res.warnings.append(
                f"runtime {res.runtime_minutes_fast}-{res.runtime_minutes_slow} min is more than 20% "
                f"off the {target_minutes} min target ({round(target_minutes * 140)} words is about right)")

    res.verify_tags = find_verify_tags(md)
    res.unverified_facts = [f["claim"] for f in facts if not f.get("verified")]
    missing_src = [f["claim"] for f in facts if not str(f.get("source") or "").strip()]
    if publish:
        if res.verify_tags:
            lines = ", ".join(str(t["line"]) for t in res.verify_tags[:20])
            res.errors.append(f"{len(res.verify_tags)} unresolved [VERIFY] tag(s) (lines {lines}); "
                              "resolve them before publishing")
        if res.unverified_facts:
            res.errors.append(f"{len(res.unverified_facts)} fact(s) in topic.yaml have verified: false")
        if missing_src:
            res.errors.append(f"{len(missing_src)} fact(s) in topic.yaml have no source")
    else:
        if res.verify_tags:
            res.warnings.append(f"{len(res.verify_tags)} [VERIFY] tag(s) unresolved (allowed in draft mode)")
        if res.unverified_facts:
            res.warnings.append(f"{len(res.unverified_facts)} unverified fact(s) in topic.yaml")
    if warn_units:
        res.warnings.extend(find_missing_imperial(md))
    return res


def run(ctx: Context) -> dict:
    p = ctx.paths
    if not p.script_md.exists():
        raise StageFailed(f"missing {p.script_md}")
    topic = load_topic(p.topic_yaml)
    md = p.script_md.read_text(encoding="utf-8")
    res = check_script(
        md,
        required_sections=topic.get("required_sections"),
        publish=ctx.publish,
        facts=topic["facts"],
        target_minutes=float(topic["target_minutes"]),
        warn_units=bool(ctx.settings.audience.get("units", {}).get("warn_missing_imperial", True)),
    )
    log = ctx.log
    log.info(f"words={res.word_count} sections={len(res.sections)} shots={res.shot_count} "
             f"runtime={res.runtime_minutes_fast}-{res.runtime_minutes_slow} min "
             f"(target {res.target_minutes}) verify_tags={len(res.verify_tags)}")
    log.count("words", res.word_count)
    log.count("verify_tags", len(res.verify_tags))
    for w in res.warnings:
        log.warning(w)
    for e in res.errors:
        log.error(e)

    # Free local outputs: written in dry-run too (no API involved).
    out = asdict(res) | {"passed": res.passed, "publish": ctx.publish}
    p.script_check_json.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    write_sources(topic, p.sources_md)
    if not res.passed:
        log.status = "failed"
        raise StageFailed(f"script_check failed with {len(res.errors)} error(s); see above")
    log.info("script_check passed" + (" (publish mode)" if ctx.publish else " (draft mode)"))
    return out

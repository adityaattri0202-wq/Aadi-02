"""Stage 2: parse script.md into shots.json.

Every ``image_prompt`` starts with the style spec's ``prompt_prefix``. The
prefix is applied here and re-checked by ``validate_shots`` whenever a later
stage loads shots.json, so a hand-edited prompt without it is rejected.
"""
from __future__ import annotations

import json
import re

from .config import MOTIONS, StyleSpec
from .context import Context, StageFailed
from .script_format import VERIFY_RE, count_words, parse_script


def apply_style(style: StyleSpec, description: str) -> str:
    """Return ``prefix + description + suffix``. Never drops the prefix."""
    prefix = style.prompt_prefix
    desc = " ".join(str(description).split())
    if desc.startswith(prefix):
        desc = desc[len(prefix):]
    desc = desc.strip(" ,.;")
    sep = " " if prefix[-1] in ".,;:" else ". "
    prompt = prefix + (sep + desc + "." if desc else "")
    if style.prompt_suffix:
        prompt += " " + style.prompt_suffix
    assert prompt.startswith(prefix)
    return prompt


def estimate_duration(narration: str, style: StyleSpec, override: float | None = None) -> float:
    if override:
        return round(float(override), 2)
    seconds = count_words(narration) / style.words_per_minute * 60 + style.pad_sec
    return round(max(style.min_shot_sec, seconds), 2)


def _first_sentence(text: str, limit: int = 160) -> str:
    s = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return s[:limit].rstrip()


def build_shots(md: str, style: StyleSpec) -> list[dict]:
    parsed = parse_script(md)
    if parsed.errors:
        raise StageFailed("script.md has errors:\n  " + "\n  ".join(parsed.errors))
    shots = []
    for s_idx, sec in enumerate(parsed.sections, 1):
        for n, raw in enumerate(sec.shots, 1):
            narration = raw.narration
            visual = raw.visual or f"{sec.name}: {_first_sentence(narration)}"
            shots.append({
                "id": f"s{s_idx:02d}_{n:02d}",
                "scene": s_idx,
                "scene_title": sec.name,
                "duration_sec": estimate_duration(narration, style, raw.duration),
                "visual_description": visual,
                "image_prompt": apply_style(style, visual),
                "negative_prompt": style.negative_prompt,
                "motion": raw.motion,
                "hero": raw.motion != "none",
                "overlay_text": raw.overlay,
                "narration": narration,
                "needs_verify": bool(VERIFY_RE.search(raw.raw_narration)),
                "script_line": raw.line,
            })
    if not shots:
        raise StageFailed("script.md produced no shots")
    return shots


def validate_shots(shots: list[dict], style: StyleSpec) -> list[str]:
    errors, seen = [], set()
    for shot in shots:
        sid = shot.get("id", "?")
        if sid in seen:
            errors.append(f"duplicate shot id {sid}")
        seen.add(sid)
        if not str(shot.get("image_prompt", "")).startswith(style.prompt_prefix):
            errors.append(f"{sid}: image_prompt does not start with the style prefix")
        if shot.get("motion") not in MOTIONS:
            errors.append(f"{sid}: invalid motion {shot.get('motion')!r}")
        if not shot.get("duration_sec") or float(shot["duration_sec"]) <= 0:
            errors.append(f"{sid}: duration_sec must be > 0")
    return errors


def load_shots(ctx: Context) -> list[dict]:
    """Load and validate shots.json (used by all later stages)."""
    p = ctx.paths.shots_json
    if not p.exists():
        raise StageFailed(f"{p} not found; run shot_plan first")
    shots = json.loads(p.read_text(encoding="utf-8"))
    errors = validate_shots(shots, ctx.settings.style)
    if errors:
        raise StageFailed("shots.json is invalid:\n  " + "\n  ".join(errors))
    return shots


def run(ctx: Context) -> dict:
    p, log = ctx.paths, ctx.log
    if not p.script_md.exists():
        raise StageFailed(f"missing {p.script_md}")
    if p.shots_json.exists() and not ctx.force:
        newest_input = max(p.script_md.stat().st_mtime, ctx.settings.style_path.stat().st_mtime)
        if p.shots_json.stat().st_mtime >= newest_input:
            shots = load_shots(ctx)
            log.info(f"shots.json is up to date ({len(shots)} shots); skipping. Use --force to rebuild.")
            log.count("shots", len(shots))
            return {"shots": len(shots), "skipped": True}

    shots = build_shots(p.script_md.read_text(encoding="utf-8"), ctx.settings.style)
    errors = validate_shots(shots, ctx.settings.style)
    if errors:
        raise StageFailed("\n".join(errors))
    hero = sum(1 for s in shots if s["hero"])
    total = sum(s["duration_sec"] for s in shots)
    # Free local output: written in dry-run too (no API involved).
    p.shots_json.write_text(json.dumps(shots, indent=2, ensure_ascii=False), encoding="utf-8")
    log.count("shots", len(shots))
    log.count("hero_shots", hero)
    log.info(f"Wrote {len(shots)} shots ({hero} hero) to shots.json; "
             f"estimated length {total / 60:.1f} min")
    return {"shots": len(shots), "hero": hero, "estimated_sec": round(total, 1), "skipped": False}

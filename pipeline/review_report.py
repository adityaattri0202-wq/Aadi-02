"""Stage 7: review_report.md with counts, fact-check status and cost estimates.

Read-only with respect to providers: it never generates anything. Run it
before approving paid stages to see what they would cost.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from . import approval, image_generate, motion_generate, voiceover
from .assets import find_asset
from .config import load_topic
from .context import Context
from .manifest import build_manifest, validate_manifest
from .shot_plan import load_shots


def _money(v, cur):
    return "UNKNOWN" if v is None else f"{v:.2f} {cur}"


def run(ctx: Context) -> dict:
    shots = load_shots(ctx)
    s, p, log = ctx.settings, ctx.paths, ctx.log
    topic = load_topic(p.topic_yaml)
    check = json.loads(p.script_check_json.read_text()) if p.script_check_json.exists() else None
    heroes = motion_generate.hero_shots(shots)
    segs = voiceover.segments(shots)
    imgs_ready = sum(1 for x in shots if find_asset(p.images_dir, x["id"]))
    clips_ready = sum(1 for x in heroes if find_asset(p.clips_dir, x["id"]))
    vo_ready = sum(1 for x in segs if find_asset(p.voiceover_dir, x["id"]))

    prov = {k: s.provider_for(k, ctx.provider_override) for k in ("image", "video", "voice")}
    rows = [
        ("image_generate", approval.estimate(s.costs, prov["image"], "image", len(shots)),
         approval.estimate(s.costs, prov["image"], "image", len(image_generate.pending(ctx, shots)))),
        ("motion_generate", approval.estimate(s.costs, prov["video"], "video", len(heroes) * s.style.clip_seconds),
         approval.estimate(s.costs, prov["video"], "video",
                           len(motion_generate.pending(ctx, shots)) * s.style.clip_seconds)),
        ("voiceover", approval.estimate(s.costs, prov["voice"], "voice", sum(len(x["text"]) for x in segs)),
         approval.estimate(s.costs, prov["voice"], "voice",
                           sum(len(x["text"]) for x in voiceover.pending(ctx, shots)))),
    ]
    cur = s.costs.get("currency", "USD")
    per_provider: dict = defaultdict(lambda: [0.0, 0.0, False])
    for _, full, rem in rows:
        acc = per_provider[full.provider]
        if full.total is None:
            acc[2] = True
        else:
            acc[0] += full.total
            acc[1] += rem.total or 0
    manifest = build_manifest(ctx, shots)
    m_errors = validate_manifest(manifest, shots)
    unverified = [f for f in topic["facts"] if not f.get("verified")]

    L = [f"# Review report: {topic['name']}", "",
         f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
         + (" (dry run)" if ctx.dry_run else ""), "",
         "## Summary", "", "| Item | Count |", "|---|---|",
         f"| Shots | {len(shots)} |",
         f"| Images ready | {imgs_ready} / {len(shots)} |",
         f"| Hero shots (motion clips) | {len(heroes)} |",
         f"| Motion clips ready | {clips_ready} / {len(heroes)} |",
         f"| Voiceover segments ready | {vo_ready} / {len(segs)} |",
         f"| Estimated length (from current timings) | {manifest['total_duration_sec'] / 60:.1f} min "
         f"(target {topic['target_minutes']} min) |"]
    if check:
        L.append(f"| Script words | {check['word_count']} "
                 f"({check['runtime_minutes_fast']}-{check['runtime_minutes_slow']} min at 150-130 wpm) |")
    L += ["", "## Estimated cost per stage", "",
          f"Prices from config/costs.yaml (verified: {str(s.costs.get('verified', False)).lower()}).", "",
          "| Stage | Provider | Units (all) | Est. total | Units still to generate | Est. remaining |",
          "|---|---|---|---|---|---|"]
    for stage, full, rem in rows:
        L.append(f"| {stage} | {full.provider} | {full.units:g} {full.unit_label} | {_money(full.total, cur)} | "
                 f"{rem.units:g} {rem.unit_label} | {_money(rem.total, cur)} |")
    L += ["", "## Estimated cost per provider", "", "| Provider | Est. total | Est. remaining |", "|---|---|---|"]
    for name, (tot, rem, unknown) in per_provider.items():
        suffix = " + UNKNOWN items" if unknown else ""
        L.append(f"| {name} | {tot:.2f} {cur}{suffix} | {rem:.2f} {cur}{suffix} |")
    L += ["", "## Fact check", "",
          f"- [VERIFY] tags in script: {len(check['verify_tags']) if check else 'run script_check'}",
          f"- Unverified facts in topic.yaml: {len(unverified)} of {len(topic['facts'])}",
          f"- Shots whose narration has [VERIFY]: {sum(1 for x in shots if x.get('needs_verify'))}",
          "- Publishing requires `script_check --publish` to pass.", ""]
    for f in unverified:
        L.append(f"  - {f['claim']} (source: {f.get('source') or 'TODO'})")
    L += ["", "## Manifest", "",
          f"- Valid: {'yes' if not m_errors else 'NO'}; ready for edit: "
          f"{'yes' if manifest['ready_for_edit'] else 'no (assets still planned)'}"]
    L += [f"  - {e}" for e in m_errors]
    L += ["", "## Next steps (paid stages need approval)", "", "```",
          f"python -m pipeline image_generate --topic {p.slug} --dry-run    # review plan",
          f"python -m pipeline image_generate --topic {p.slug} --approve",
          f"python -m pipeline motion_generate --topic {p.slug} --approve",
          f"python -m pipeline voiceover --topic {p.slug} --approve [--accent uk]",
          f"python -m pipeline manifest --topic {p.slug}", "```", ""]
    p.report_md.write_text("\n".join(L), encoding="utf-8")
    log.count("shots", len(shots))
    log.count("images_ready", imgs_ready)
    log.count("hero_shots", len(heroes))
    for stage, full, rem in rows:
        log.info(f"{stage}: {full.describe()}")
    log.info(f"Wrote {p.rel(p.report_md)}")
    return {"shots": len(shots), "hero": len(heroes), "images_ready": imgs_ready, "clips_ready": clips_ready}

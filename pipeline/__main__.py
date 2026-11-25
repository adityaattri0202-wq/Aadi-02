"""CLI: ``python -m pipeline <stage> --topic <slug> [--dry-run] [--approve]``.

Exit codes: 0 ok, 1 config/provider error, 2 approval required, 3 stage failed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (STAGES, image_generate, manifest, motion_generate, new_topic, render,
               review_report, script_check, shot_plan, voiceover)
from .config import ConfigError, load_settings
from .context import ApprovalRequired, Context, StageFailed
from .paths import TopicPaths, slugify
from .providers import ProviderError
from .runlog import RunLog

RUNNERS = {
    "script_check": script_check.run,
    "shot_plan": shot_plan.run,
    "image_generate": image_generate.run,
    "motion_generate": motion_generate.run,
    "voiceover": voiceover.run,
    "manifest": manifest.run,
    "review_report": review_report.run,
    "render": render.run,
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=[*STAGES, "new_topic"])
    ap.add_argument("--topic", required=True, help="topic slug (folder name under topics/) or name")
    ap.add_argument("--name", help="display name for new_topic")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; never call a provider API")
    ap.add_argument("--approve", action="store_true", help="allow paid stages to spend credits")
    ap.add_argument("--publish", action="store_true", help="script_check: fail on any [VERIFY] / unverified fact")
    ap.add_argument("--force", action="store_true", help="rebuild outputs even if up to date")
    ap.add_argument("--provider", help="override every provider for this run (e.g. mock)")
    ap.add_argument("--accent", choices=["us", "uk"], help="voiceover accent (default from audience.yaml)")
    ap.add_argument("--shots", help="render: comma-separated shot ids for a quick preview")
    ap.add_argument("--style", help="style spec file (default config/style_spec.yaml)")
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    slug = slugify(args.topic)

    if args.stage == "new_topic":
        made = new_topic.create(root, slug, args.name or args.topic)
        for path in made:
            print(f"created {path.relative_to(root)}")
        print(f"Topic ready: topics/{slug}/ (edit topic.yaml and script.md)")
        return 0

    paths = TopicPaths(root, slug)
    if not paths.dir.exists():
        print(f"error: topics/{slug}/ not found. Create it with: "
              f"python -m pipeline new_topic --topic {slug}", file=sys.stderr)
        return 1
    try:
        settings = load_settings(root, Path(args.style) if args.style else None)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    with RunLog(paths, args.stage, dry_run=args.dry_run) as log:
        ctx = Context(settings=settings, paths=paths, log=log, dry_run=args.dry_run, approve=args.approve,
                      publish=args.publish, force=args.force, provider_override=args.provider,
                      accent=args.accent,
                      only_shots=[s.strip() for s in args.shots.split(',')] if args.shots else None)
        if args.dry_run and args.approve:
            log.warning("--dry-run wins over --approve: nothing will be generated")
        try:
            RUNNERS[args.stage](ctx)
            return 0
        except ApprovalRequired as exc:
            log.status = "awaiting_approval"
            log.warning(str(exc))
            return 2
        except StageFailed as exc:
            log.status = "failed"
            log.error(str(exc))
            return 3
        except (ConfigError, ProviderError, NotImplementedError) as exc:
            log.status = "error"
            log.error(str(exc))
            return 1


if __name__ == "__main__":
    sys.exit(main())

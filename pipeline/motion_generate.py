"""Stage 4: image-to-video clips for hero shots (motion != none) into clips/.

Paid and approval-gated. Needs the shot's image from image_generate. A clip is
regenerated only if its image, motion or prompt changed.
"""
from __future__ import annotations

from . import approval
from .assets import clear_asset, find_asset, fingerprint, is_current, read_sidecar, write_sidecar
from .context import Context, StageFailed
from .providers import get_provider
from .shot_plan import load_shots


def video_prompt(shot: dict, style) -> str:
    motion = style.motion_prompts.get(shot["motion"], shot["motion"].replace("_", " "))
    return (f"{motion}. {shot['visual_description'].rstrip('.')}. "
            f"Keep the exact hand-drawn style of the source image; no text appears.")


def clip_fingerprint(ctx: Context, shot: dict) -> str:
    img = read_sidecar(ctx.paths.images_dir, shot["id"]) or {}
    return fingerprint({"image": img.get("fingerprint"), "motion": shot["motion"],
                        "prompt": video_prompt(shot, ctx.settings.style),
                        "seconds": ctx.settings.style.clip_seconds})


def hero_shots(shots: list[dict]) -> list[dict]:
    return [s for s in shots if s.get("motion", "none") != "none"]


def pending(ctx: Context, shots: list[dict]) -> list[dict]:
    folder = ctx.paths.clips_dir
    return [s for s in hero_shots(shots)
            if ctx.force or not is_current(folder, s["id"], clip_fingerprint(ctx, s))]


def run(ctx: Context) -> dict:
    shots = load_shots(ctx)
    log, style = ctx.log, ctx.settings.style
    heroes = hero_shots(shots)
    todo = pending(ctx, shots)
    missing_img = [s["id"] for s in todo if not find_asset(ctx.paths.images_dir, s["id"])]
    log.info(f"{len(heroes)} hero shots of {len(shots)}; {len(heroes) - len(todo)} clips already done")
    if missing_img:
        log.warning(f"{len(missing_img)} hero shot(s) have no image yet: {', '.join(missing_img[:10])}"
                    + ("" if ctx.dry_run else " (run image_generate first)"))
    provider_name = ctx.settings.provider_for("video", ctx.provider_override)
    est = approval.estimate(ctx.settings.costs, provider_name, "video", len(todo) * style.clip_seconds)
    if not approval.gate(log, "motion_generate", [s["id"] for s in todo], est, ctx.approve, ctx.dry_run):
        return {"generated": 0, "pending": len(todo), "dry_run": ctx.dry_run}
    if missing_img:
        log.status = "failed"
        raise StageFailed("run image_generate first; no credits were spent")

    provider = get_provider(provider_name, ctx.settings)
    folder = ctx.paths.clips_dir
    folder.mkdir(parents=True, exist_ok=True)
    done = 0
    for shot in todo:
        sid = shot["id"]
        try:
            clear_asset(folder, sid)
            out = folder / f"{sid}{provider.video_extension}"
            provider.generate_video(find_asset(ctx.paths.images_dir, sid), video_prompt(shot, style), out,
                                    motion=shot["motion"], duration_sec=style.clip_seconds)
            write_sidecar(folder, sid, {"fingerprint": clip_fingerprint(ctx, shot), "provider": provider_name,
                                        "file": out.name, "motion": shot["motion"],
                                        "duration_sec": style.clip_seconds})
            done += 1
            log.count("generated")
            log.info(f"{sid}: clip saved to {ctx.paths.rel(out)}")
        except NotImplementedError as exc:
            raise StageFailed(str(exc)) from exc
        except Exception as exc:
            log.error(f"{sid}: {type(exc).__name__}: {exc}")
    if log.errors:
        log.status = "failed"
        raise StageFailed(f"{len(log.errors)} clip(s) failed; re-run to retry only those")
    return {"generated": done, "pending": 0, "dry_run": False}

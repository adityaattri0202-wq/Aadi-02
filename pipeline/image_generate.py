"""Stage 3: generate one image per shot into images/ (paid, approval-gated).

Skips shots whose image exists with a matching prompt fingerprint.
"""
from __future__ import annotations

from . import approval
from .assets import clear_asset, fingerprint, is_current, write_sidecar
from .context import Context, StageFailed
from .providers import get_provider
from .shot_plan import load_shots


def shot_fingerprint(shot: dict, style) -> str:
    return fingerprint({"prompt": shot["image_prompt"], "negative": shot.get("negative_prompt", ""),
                        "w": style.width, "h": style.height})


def pending(ctx: Context, shots: list[dict]) -> list[dict]:
    style, folder = ctx.settings.style, ctx.paths.images_dir
    return [s for s in shots if ctx.force or not is_current(folder, s["id"], shot_fingerprint(s, style))]


def run(ctx: Context) -> dict:
    shots = load_shots(ctx)
    style, log = ctx.settings.style, ctx.log
    provider_name = ctx.settings.provider_for("image", ctx.provider_override)
    todo = pending(ctx, shots)
    log.info(f"{len(shots)} shots, {len(shots) - len(todo)} already have images")
    est = approval.estimate(ctx.settings.costs, provider_name, "image", len(todo))
    if not approval.gate(log, "image_generate", [s["id"] for s in todo], est, ctx.approve, ctx.dry_run):
        return {"generated": 0, "pending": len(todo), "dry_run": ctx.dry_run}

    provider = get_provider(provider_name, ctx.settings)
    folder = ctx.paths.images_dir
    folder.mkdir(parents=True, exist_ok=True)
    done = 0
    for shot in todo:
        sid = shot["id"]
        try:
            clear_asset(folder, sid)
            out = folder / f"{sid}{provider.image_extension}"
            provider.generate_image(shot["image_prompt"], out, negative_prompt=shot.get("negative_prompt", ""),
                                    width=style.width, height=style.height)
            write_sidecar(folder, sid, {"fingerprint": shot_fingerprint(shot, style), "provider": provider_name,
                                        "file": out.name, "prompt": shot["image_prompt"]})
            done += 1
            log.count("generated")
            log.info(f"{sid}: image saved to {ctx.paths.rel(out)}")
        except NotImplementedError as exc:
            raise StageFailed(str(exc)) from exc  # stub provider: stop, don't loop over every shot
        except Exception as exc:  # keep going; failed shots stay pending for the next run
            log.error(f"{sid}: {type(exc).__name__}: {exc}")
    if log.errors:
        log.status = "failed"
        raise StageFailed(f"{len(log.errors)} image(s) failed; re-run to retry only those")
    return {"generated": done, "pending": 0, "dry_run": False}

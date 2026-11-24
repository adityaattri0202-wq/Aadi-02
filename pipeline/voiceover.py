"""Stage 5: text-to-speech, one segment per shot with narration (paid, gated).

Writes ``voiceover/<shot_id>.<ext>`` plus ``<shot_id>.json`` (duration and
word timings) and an index ``voiceover/segments.json``. The accent (us/uk)
picks the voice from config/audience.yaml.
"""
from __future__ import annotations

import json

from . import approval
from .assets import clear_asset, find_asset, fingerprint, is_current, read_sidecar, write_sidecar
from .config import ConfigError
from .context import Context, StageFailed
from .providers import get_provider
from .shot_plan import load_shots


def segments(shots: list[dict]) -> list[dict]:
    return [{"id": s["id"], "text": s["narration"]} for s in shots if s.get("narration")]


def seg_fingerprint(seg: dict, provider: str, voice: str) -> str:
    return fingerprint({"text": seg["text"], "provider": provider, "voice": voice})


def resolve_voice(ctx: Context, provider: str) -> str:
    return ctx.settings.voice_for(provider, ctx.accent)


def pending(ctx: Context, shots: list[dict]) -> list[dict]:
    provider = ctx.settings.provider_for("voice", ctx.provider_override)
    try:
        voice = resolve_voice(ctx, provider)
    except ConfigError:
        voice = "?"
    folder = ctx.paths.voiceover_dir
    return [s for s in segments(shots)
            if ctx.force or not is_current(folder, s["id"], seg_fingerprint(s, provider, voice))]


def write_index(ctx: Context, shots: list[dict]) -> int:
    folder, index = ctx.paths.voiceover_dir, []
    for seg in segments(shots):
        side, audio = read_sidecar(folder, seg["id"]), find_asset(folder, seg["id"])
        if side and audio:
            index.append({"id": seg["id"], "file": audio.name, "duration_sec": side.get("duration_sec"),
                          "voice": side.get("voice"), "provider": side.get("provider"),
                          "words": len(side.get("words", []))})
    if index:
        ctx.paths.segments_json.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return len(index)


def run(ctx: Context) -> dict:
    shots = load_shots(ctx)
    log = ctx.log
    provider_name = ctx.settings.provider_for("voice", ctx.provider_override)
    voice = resolve_voice(ctx, provider_name)
    segs = segments(shots)
    todo = pending(ctx, shots)
    chars = sum(len(s["text"]) for s in todo)
    log.info(f"{len(segs)} narration segments; {len(segs) - len(todo)} already voiced; "
             f"voice={voice} ({ctx.accent or 'default'} accent) via {provider_name}")
    if voice.startswith("TODO"):
        log.warning(f"voice id for {provider_name} is a placeholder; set it in config/audience.yaml")
    est = approval.estimate(ctx.settings.costs, provider_name, "voice", chars)
    if not approval.gate(log, "voiceover", [s["id"] for s in todo], est, ctx.approve, ctx.dry_run):
        return {"generated": 0, "pending": len(todo), "chars": chars, "dry_run": ctx.dry_run}
    if voice.startswith("TODO"):
        log.status = "failed"
        raise StageFailed(f"set a real {provider_name} voice id in config/audience.yaml; no credits spent")

    provider = get_provider(provider_name, ctx.settings)
    folder = ctx.paths.voiceover_dir
    folder.mkdir(parents=True, exist_ok=True)
    done = 0
    for seg in todo:
        sid = seg["id"]
        try:
            clear_asset(folder, sid)
            out = folder / f"{sid}{provider.voice_extension}"
            res = provider.generate_voice(seg["text"], out, voice=voice)
            write_sidecar(folder, sid, {"fingerprint": seg_fingerprint(seg, provider_name, voice),
                                        "provider": provider_name, "voice": voice, "file": out.name,
                                        "duration_sec": res.duration_sec, "words": res.words,
                                        "text": seg["text"]})
            done += 1
            log.count("generated")
            log.info(f"{sid}: {res.duration_sec:.1f}s audio saved to {ctx.paths.rel(out)}")
        except NotImplementedError as exc:
            raise StageFailed(str(exc)) from exc
        except Exception as exc:
            log.error(f"{sid}: {type(exc).__name__}: {exc}")
    indexed = write_index(ctx, shots)
    log.info(f"segments.json lists {indexed} voiced segment(s)")
    if log.errors:
        log.status = "failed"
        raise StageFailed(f"{len(log.errors)} segment(s) failed; re-run to retry only those")
    return {"generated": done, "pending": 0, "chars": chars, "dry_run": False}

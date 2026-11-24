"""Stage 6: manifest.json + timeline.csv + timeline.edl + subtitles.srt.

Links every shot to its image, clip (hero shots) and voiceover segment, with
start/end times. Shot length = voiceover duration + pad once audio exists,
otherwise the shot_plan estimate. Assets not generated yet are linked by
their planned path with status "planned" (that is what a dry run produces).

Import into an editor: DaVinci Resolve reads timeline.edl (File > Import >
Timeline) or timeline.csv; CapCut takes the media folders + subtitles.srt.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from .assets import find_asset, read_sidecar
from .context import Context, StageFailed
from .providers import provider_class
from .shot_plan import load_shots

MANIFEST_VERSION = 1


def _link(ctx: Context, folder, sid: str, planned_ext: str) -> dict:
    found = find_asset(folder, sid)
    if found:
        return {"path": ctx.paths.rel(found), "status": "ready"}
    return {"path": ctx.paths.rel(folder / f"{sid}{planned_ext}"), "status": "planned"}


def build_manifest(ctx: Context, shots: list[dict]) -> dict:
    s, p = ctx.settings, ctx.paths
    names = {k: s.provider_for(k, ctx.provider_override) for k in ("image", "video", "voice")}
    exts = {"image": provider_class(names["image"]).image_extension,
            "video": provider_class(names["video"]).video_extension,
            "voice": provider_class(names["voice"]).voice_extension}
    t, entries = 0.0, []
    for shot in shots:
        sid = shot["id"]
        image = _link(ctx, p.images_dir, sid, exts["image"])
        clip = _link(ctx, p.clips_dir, sid, exts["video"]) if shot.get("hero") else None
        audio, duration = None, float(shot["duration_sec"])
        if shot.get("narration"):
            audio = _link(ctx, p.voiceover_dir, sid, exts["voice"])
            side = read_sidecar(p.voiceover_dir, sid)
            if audio["status"] == "ready" and side and side.get("duration_sec"):
                audio["duration_sec"] = float(side["duration_sec"])
                audio["words"] = side.get("words", [])
                duration = max(s.style.min_shot_sec, audio["duration_sec"] + s.style.pad_sec)
            else:
                audio["duration_sec"] = None
        start, end = round(t, 3), round(t + duration, 3)
        t = end
        entries.append({
            "shot_id": sid, "scene": shot["scene"], "scene_title": shot["scene_title"],
            "start_sec": start, "end_sec": end, "duration_sec": round(end - start, 3),
            "image": image, "clip": clip, "audio": audio, "motion": shot["motion"],
            "overlay_text": shot.get("overlay_text", ""), "narration": shot.get("narration", ""),
        })
    statuses = [e["image"]["status"] for e in entries] + \
               [e[k]["status"] for e in entries for k in ("clip", "audio") if e[k]]
    return {
        "version": MANIFEST_VERSION,
        "topic": p.slug,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": ctx.dry_run,
        "fps": s.style.fps,
        "resolution": [s.style.width, s.style.height],
        "providers": names,
        "total_duration_sec": round(t, 3),
        "ready_for_edit": all(x == "ready" for x in statuses),
        "counts": {"shots": len(entries),
                   "images_ready": sum(e["image"]["status"] == "ready" for e in entries),
                   "clips_planned": sum(1 for e in entries if e["clip"]),
                   "clips_ready": sum(1 for e in entries if e["clip"] and e["clip"]["status"] == "ready"),
                   "audio_segments": sum(1 for e in entries if e["audio"]),
                   "audio_ready": sum(1 for e in entries if e["audio"] and e["audio"]["status"] == "ready")},
        "shots": entries,
    }


def validate_manifest(manifest: dict, shots: list[dict]) -> list[str]:
    """Every shot present in order, linked to its assets, contiguous timing."""
    errors = []
    entries = manifest.get("shots", [])
    ids = [e.get("shot_id") for e in entries]
    expected = [s["id"] for s in shots]
    if ids != expected:
        errors.append(f"manifest shots {ids[:5]}... do not match shots.json {expected[:5]}...")
    by_id = {s["id"]: s for s in shots}
    prev_end = 0.0
    for e in entries:
        sid, shot = e.get("shot_id"), by_id.get(e.get("shot_id"), {})
        if not (e.get("image") or {}).get("path"):
            errors.append(f"{sid}: no image linked")
        if shot.get("hero") and not (e.get("clip") or {}).get("path"):
            errors.append(f"{sid}: hero shot has no clip linked")
        if shot.get("narration") and not (e.get("audio") or {}).get("path"):
            errors.append(f"{sid}: narration has no audio linked")
        if abs(e.get("start_sec", -1) - prev_end) > 0.002:
            errors.append(f"{sid}: start {e.get('start_sec')} != previous end {prev_end}")
        if not e.get("end_sec", 0) > e.get("start_sec", 0):
            errors.append(f"{sid}: end must be after start")
        prev_end = e.get("end_sec", prev_end)
    if entries and abs(manifest.get("total_duration_sec", 0) - prev_end) > 0.002:
        errors.append("total_duration_sec does not match the last shot's end")
    return errors


def timecode(seconds: float, fps: int) -> str:
    frames = int(round(seconds * fps))
    f = frames % fps
    s = frames // fps
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{f:02d}"


def write_csv(manifest: dict, path) -> None:
    fps = manifest["fps"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["shot_id", "scene", "start_sec", "end_sec", "duration_sec", "start_tc", "end_tc",
                    "image", "clip", "audio", "motion", "overlay_text", "narration"])
        for e in manifest["shots"]:
            w.writerow([e["shot_id"], e["scene"], e["start_sec"], e["end_sec"], e["duration_sec"],
                        timecode(e["start_sec"], fps), timecode(e["end_sec"], fps), e["image"]["path"],
                        (e["clip"] or {}).get("path", ""), (e["audio"] or {}).get("path", ""),
                        e["motion"], e["overlay_text"], e["narration"]])


def render_edl(manifest: dict, title: str) -> str:
    """CMX3600 EDL: one video event (clip or still) and one audio event per shot."""
    fps = manifest["fps"]
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    n = 0
    for e in manifest["shots"]:
        dur = e["duration_sec"]
        rec_in, rec_out = timecode(e["start_sec"], fps), timecode(e["end_sec"], fps)
        src_out = timecode(dur, fps)
        media = (e["clip"] or e["image"])["path"]
        n += 1
        lines += [f"{n:03d}  AX       V     C        00:00:00:00 {src_out} {rec_in} {rec_out}",
                  f"* FROM CLIP NAME: {media.split('/')[-1]}", f"* COMMENT: {e['shot_id']} {media}", ""]
        if e["audio"]:
            a_dur = e["audio"].get("duration_sec") or dur
            a_end = timecode(e["start_sec"] + min(a_dur, dur), fps)
            n += 1
            lines += [f"{n:03d}  AX       A     C        00:00:00:00 {timecode(min(a_dur, dur), fps)} "
                      f"{rec_in} {a_end}",
                      f"* FROM CLIP NAME: {e['audio']['path'].split('/')[-1]}", ""]
    return "\n".join(lines)


def _srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def render_srt(manifest: dict, max_words: int = 9) -> str:
    cues = []
    for e in manifest["shots"]:
        if not e["audio"] or not e["narration"]:
            continue
        timed = e["audio"].get("words") or []
        if not timed:  # spread words evenly over the shot
            words = e["narration"].split()
            span = (e["audio"].get("duration_sec") or e["duration_sec"] - 0.3) / max(len(words), 1)
            timed = [{"word": w, "start": i * span, "end": (i + 1) * span} for i, w in enumerate(words)]
        for i in range(0, len(timed), max_words):
            chunk = timed[i:i + max_words]
            cues.append((e["start_sec"] + chunk[0]["start"], e["start_sec"] + chunk[-1]["end"],
                         " ".join(w["word"] for w in chunk)))
    out = []
    for i, (a, b, text) in enumerate(cues, 1):
        out += [str(i), f"{_srt_time(a)} --> {_srt_time(b)}", text, ""]
    return "\n".join(out)


def run(ctx: Context) -> dict:
    shots = load_shots(ctx)
    log, p = ctx.log, ctx.paths
    m = build_manifest(ctx, shots)
    errors = validate_manifest(m, shots)
    for e in errors:
        log.error(e)
    if errors:
        log.status = "failed"
        raise StageFailed("manifest is invalid; nothing written")
    # Free local outputs: written in dry-run too (links planned paths).
    p.manifest_json.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(m, p.timeline_csv)
    p.timeline_edl.write_text(render_edl(m, p.slug), encoding="utf-8")
    p.subtitles_srt.write_text(render_srt(m), encoding="utf-8")
    c = m["counts"]
    for k, v in c.items():
        log.count(k, v)
    log.info(f"{c['shots']} shots linked; images ready {c['images_ready']}/{c['shots']}, "
             f"clips ready {c['clips_ready']}/{c['clips_planned']}, audio ready "
             f"{c['audio_ready']}/{c['audio_segments']}; total {m['total_duration_sec'] / 60:.1f} min")
    log.info("ready_for_edit=" + str(m["ready_for_edit"]).lower()
             + ("" if m["ready_for_edit"] else " (some assets are still planned)"))
    log.info("Wrote manifest.json, timeline.csv, timeline.edl, subtitles.srt")
    return m

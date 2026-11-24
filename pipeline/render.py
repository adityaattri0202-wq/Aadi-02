"""Stage 8 (free, local): render manifest.json into a finished MP4 with ffmpeg.

Per shot:
- hero shot with a ready clip: the clip plays, then holds on its last frame,
  with a gentle push-in over the whole shot so nothing sits frozen;
- any other shot: Ken Burns move on the still (push-in, pull-out or pan,
  chosen from the shot's motion and position);
- overlay_text appears as a lower-third caption that fades in and out;
- the shot's voiceover segment, padded with silence to the shot length.

Shots are cut together with a short fade from/to black at the start and end.
Clips are re-rendered only when inputs change (cached in render/). Output:
``<slug>_final.mp4``. Needs ffmpeg/ffprobe; never calls a paid API.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .assets import fingerprint
from .context import Context, StageFailed

W, H, FPS = 1920, 1080, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def _ff(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise StageFailed("ffmpeg failed:\n" + r.stderr[-1500:])


def _is_video(path: Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=codec_type", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return r.returncode == 0 and "video" in r.stdout


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def _overlay(text: str, dur: float) -> str:
    if not text:
        return ""
    t_in, t_out = 0.6, max(dur - 0.6, 1.2)
    alpha = (f"if(lt(t,{t_in}),0,if(lt(t,{t_in}+0.5),(t-{t_in})/0.5,"
             f"if(lt(t,{t_out}-0.5),1,if(lt(t,{t_out}),({t_out}-t)/0.5,0))))")
    if text.isupper() and len(text) <= 20:  # title card: large, centred near the top
        return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=110:fontcolor=0x3A2A18:"
                f"x=(w-text_w)/2:y=h*0.085-text_h/2+8:alpha='{alpha}'")
    return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=54:fontcolor=0xF3EAD6:"
            f"box=1:boxcolor=0x1E1A14@0.62:boxborderw=22:x=110:y=h-210:alpha='{alpha}'")


def _ken_burns(index: int, motion: str, frames: int) -> str:
    n = max(frames, 1)
    if motion == "slow_pan" or (motion == "none" and index % 3 == 2):
        z, x, y = "1.12", f"(iw-iw/zoom)*on/{n}", "(ih-ih/zoom)/2"
    elif motion == "none" and index % 3 == 1:   # gentle pull-out
        z, x, y = f"1.12-0.10*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    else:                                         # push-in
        z, x, y = f"1.0+0.12*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}"


def render_shot(entry: dict, index: int, topic_dir: Path, out: Path) -> None:
    dur = float(entry["duration_sec"])
    frames = int(round(dur * FPS))
    image = topic_dir / entry["image"]["path"]
    clip = topic_dir / entry["clip"]["path"] if entry.get("clip") and entry["clip"]["status"] == "ready" else None
    audio = topic_dir / entry["audio"]["path"] if entry.get("audio") and entry["audio"]["status"] == "ready" else None
    if clip and not _is_video(clip):
        clip = None  # e.g. mock placeholder
    over = _overlay(entry.get("overlay_text", ""), dur)

    if clip:
        vin = ["-i", str(clip)]
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
              f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
              f"scale={int(W*1.1)}:{int(H*1.1)},"
              f"zoompan=z='1.0+0.08*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}"
              f"{over},format=yuv420p[v]")
    else:
        vin = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(image)]
        vf = (f"[0:v]scale={int(W*1.25)}:{int(H*1.25)}:force_original_aspect_ratio=increase,"
              f"crop={int(W*1.25)}:{int(H*1.25)},{_ken_burns(index, entry.get('motion', 'none'), frames)},"
              f"trim=duration={dur:.3f}{over},format=yuv420p[v]")
    if audio:
        ain = ["-i", str(audio)]
        af = f";[1:a]aresample=48000,apad,atrim=duration={dur:.3f}[a]"
    else:
        ain = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        af = ";[1:a]anull[a]"
    _ff([*vin, *ain, "-filter_complex", vf + af, "-map", "[v]", "-map", "[a]",
         "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000", str(out)])


def run(ctx: Context) -> dict:
    p, log = ctx.paths, ctx.log
    if not shutil.which("ffmpeg"):
        raise StageFailed("ffmpeg is not installed")
    if not p.manifest_json.exists():
        raise StageFailed("manifest.json not found; run manifest first")
    m = json.loads(p.manifest_json.read_text(encoding="utf-8"))
    entries = m["shots"]
    missing = [e["shot_id"] for e in entries if e["image"]["status"] != "ready"]
    log.info(f"{len(entries)} shots, {m['total_duration_sec'] / 60:.1f} min; "
             f"images missing: {len(missing)}; clips ready: {m['counts']['clips_ready']}")
    if ctx.dry_run:
        log.info("[dry-run] would render each shot and join them into "
                 f"{p.slug}_final.mp4 (local ffmpeg, no API calls)")
        return {"rendered": 0, "dry_run": True}
    if missing:
        raise StageFailed(f"images missing for {', '.join(missing[:10])}; run image_generate first")

    work = p.dir / "render"
    work.mkdir(exist_ok=True)
    parts = []
    for i, e in enumerate(entries):
        fp = fingerprint({k: e.get(k) for k in ("duration_sec", "image", "clip", "audio", "overlay_text", "motion")}
                         | {"v": 2})
        out = work / f"{e['shot_id']}_{fp}.mp4"
        if not out.exists() or ctx.force:
            render_shot(e, i, p.dir, out)
            log.count("rendered")
            log.info(f"{e['shot_id']}: rendered {e['duration_sec']:.1f}s"
                     + (" (clip)" if e.get("clip") and e["clip"]["status"] == "ready" else " (still)"))
        parts.append(out)

    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{x.resolve()}'\n" for x in parts), encoding="utf-8")
    final = p.dir / f"{p.slug}_final.mp4"
    total = m["total_duration_sec"]
    _ff(["-f", "concat", "-safe", "0", "-i", str(concat),
         "-vf", f"fade=t=in:st=0:d=0.8,fade=t=out:st={max(total - 1.2, 0):.2f}:d=1.2",
         "-af", f"afade=t=in:st=0:d=0.3,afade=t=out:st={max(total - 1.2, 0):.2f}:d=1.2",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(final)])
    log.info(f"Wrote {p.rel(final)} ({total / 60:.1f} min)")
    return {"rendered": len(parts), "video": str(final)}

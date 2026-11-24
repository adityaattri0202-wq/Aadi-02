"""Stage 8 (free, local): render manifest.json into a finished, edited MP4.

Editing style ("documentary pro" defaults, all local ffmpeg, no paid APIs):

- Pacing: every shot is cut into ~4 s sub-shots with different framings of
  the same plate (wide push-in, tight detail crops, pans, pull-outs), so the
  picture changes every few seconds like a hand-edited video. Hero shots open
  on their AI motion clip, then cut to detail framings.
- Overlays: lower-third captions and a centred title card fade in and out.
- Sound: narration on top; a dark synth drone and a low ocean rumble
  underneath, ducked under the voice (sidechain); a whoosh at each chapter.
- Finish: subtle grade, vignette and film grain; fade in/out; loudness
  normalised to -14 LUFS (YouTube); ``chapters.txt`` for the description.

Shot renders are cached in ``render/`` by a fingerprint of their inputs.
Output: ``<slug>_final.mp4``.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from .assets import fingerprint
from .context import Context, StageFailed

W, H, FPS = 1920, 1080, 30
SRC_W, SRC_H = 3200, 1800          # stills are upscaled first so tight crops stay sharp
SUB_SHOT_SEC = 4.2                 # target length of one cut
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
RENDER_VERSION = 4

# Framings for sub-shots: (zoom_from, zoom_to, cx_from, cx_to, cy_from, cy_to)
# cx/cy are the frame centre as a fraction of the plate. Every framing both
# zooms and travels, so no cut is ever static.
FRAMINGS = [
    (1.02, 1.20, 0.48, 0.52, 0.50, 0.49),   # wide push-in
    (1.55, 1.75, 0.36, 0.44, 0.52, 0.47),   # tight detail, drifting right
    (1.40, 1.52, 0.66, 0.50, 0.47, 0.45),   # pan right->left with push
    (1.38, 1.10, 0.52, 0.48, 0.53, 0.50),   # pull-out reveal
    (1.70, 1.92, 0.57, 0.62, 0.42, 0.38),   # tight detail, upper right
    (1.25, 1.38, 0.36, 0.64, 0.56, 0.52),   # pan left->right with push
]


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
    t_in, t_out = 0.5, max(dur - 0.5, 1.2)
    alpha = (f"if(lt(t,{t_in}),0,if(lt(t,{t_in}+0.4),(t-{t_in})/0.4,"
             f"if(lt(t,{t_out}-0.4),1,if(lt(t,{t_out}),({t_out}-t)/0.4,0))))")
    if text.isupper() and len(text) <= 20:  # title card: large, centred in the top banner
        return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=110:fontcolor=0x3A2A18:"
                f"x=(w-text_w)/2:y=h*0.085-text_h/2+8:alpha='{alpha}'")
    return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=54:fontcolor=0xF3EAD6:"
            f"box=1:boxcolor=0x1E1A14@0.62:boxborderw=22:x=110:y=h-210:alpha='{alpha}'")


def _zoompan(framing, frames: int) -> str:
    z0, z1, x0, x1, y0, y1 = framing
    n = max(frames - 1, 1)
    z = f"{z0}+({z1}-{z0})*on/{n}"
    x = f"max(0,min(iw-iw/zoom,({x0}+({x1}-{x0})*on/{n})*iw-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,({y0}+({y1}-{y0})*on/{n})*ih-ih/zoom/2))"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}"


def _split(dur: float, first: float = 0.0) -> list[float]:
    """Sub-shot lengths: an optional fixed first part, the rest in ~4 s cuts."""
    rest = dur - first
    n = max(1, round(rest / SUB_SHOT_SEC)) if rest > 0.5 else 0
    parts = ([first] if first else []) + [rest / n] * n
    if not parts:
        parts = [dur]
    return parts


def render_shot(entry: dict, index: int, topic_dir: Path, out: Path) -> None:
    dur = float(entry["duration_sec"])
    image = topic_dir / entry["image"]["path"]
    clip = topic_dir / entry["clip"]["path"] if entry.get("clip") and entry["clip"]["status"] == "ready" else None
    audio = topic_dir / entry["audio"]["path"] if entry.get("audio") and entry["audio"]["status"] == "ready" else None
    if clip and not _is_video(clip):
        clip = None
    if entry.get("overlay_text", "").isupper():
        clip_len, parts = 0.0, [dur]                   # title card: one calm move
    else:
        clip_len = min(5.0, dur) if clip else 0.0
        parts = _split(dur, clip_len)

    inputs = ["-i", str(image)]
    chains, labels = [], []
    still_parts = parts[1:] if clip_len else parts
    k = len(still_parts)
    chains.append(f"[0:v]scale={SRC_W}:{SRC_H}:force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={SRC_W}:{SRC_H},split={k}" + "".join(f"[s{i}]" for i in range(k)))
    if clip_len:
        inputs += ["-i", str(clip)]
        chains.append(f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                      f"tpad=stop_mode=clone:stop_duration=1,trim=duration={clip_len:.3f},"
                      f"setpts=PTS-STARTPTS,setsar=1[c]")
        labels.append("[c]")
    offset = 0 if clip_len else index % len(FRAMINGS)
    for i, seg in enumerate(still_parts):
        frames = max(int(round(seg * FPS)), 1)
        framing = FRAMINGS[(offset + i + (1 if clip_len else 0)) % len(FRAMINGS)]
        chains.append(f"[s{i}]{_zoompan(framing, frames)},trim=end_frame={frames},setpts=PTS-STARTPTS,setsar=1[p{i}]")
        labels.append(f"[p{i}]")
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,trim=duration={dur:.3f}"
                  f"{_overlay(entry.get('overlay_text', ''), dur)},format=yuv420p[v]")

    a_idx = len(inputs) // 2
    if audio:
        inputs += ["-i", str(audio)]
        chains.append(f"[{a_idx}:a]aresample=48000,apad,atrim=duration={dur:.3f}[a]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        chains.append(f"[{a_idx}:a]anull[a]")
    _ff([*inputs, "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "[a]",
         "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000", str(out)])


def make_sound_bed(work: Path, total: float, music: list[Path] | None = None) -> tuple[Path, Path]:
    """Music bed (tracks from music/, crossfaded, over a low ocean rumble) or,
    without tracks, a synthesised royalty-free drone; plus a whoosh SFX."""
    music = music or []
    tag = fingerprint({"m": [m.name for m in music], "t": int(total)})
    bed = work / f"bed_{tag}.wav"
    if music and not bed.exists():
        t = f"{total + 1:.2f}"
        ins, chain = [], ""
        for m in music:
            ins += ["-i", str(m)]
        if len(music) == 1:
            chain = "[0:a]aloop=loop=-1:size=2e9[m];"
        else:
            chain = "[0:a][1:a]acrossfade=d=5:c1=tri:c2=tri[x1];"
            for i in range(2, len(music)):
                chain += f"[x{i - 1}][{i}:a]acrossfade=d=5:c1=tri:c2=tri[x{i}];"
            chain += f"[x{len(music) - 1}]anull[m];"
        n = len(music)
        _ff([*ins, "-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.6:d={t}",
             "-filter_complex",
             chain + f"[m]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.55,apad,atrim=duration={t}[mm];"
             f"[{n}:a]lowpass=f=220,tremolo=f=0.1:d=0.5,volume=0.22,"
             "aformat=sample_rates=48000:channel_layouts=stereo[r];"
             "[mm][r]amix=inputs=2:normalize=0,afade=t=in:d=2", str(bed)])
    if not bed.exists():
        t = f"{total + 1:.2f}"
        _ff(["-f", "lavfi", "-i", f"sine=f=55:d={t}", "-f", "lavfi", "-i", f"sine=f=82.4:d={t}",
             "-f", "lavfi", "-i", f"sine=f=110:d={t}", "-f", "lavfi", "-i", f"sine=f=164.8:d={t}",
             "-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.6:d={t}",
             "-filter_complex",
             "[0]volume=0.50,tremolo=f=0.1:d=0.5[a];[1]volume=0.30,tremolo=f=0.11:d=0.6[b];"
             "[2]volume=0.22,tremolo=f=0.1:d=0.7[c];[3]volume=0.10,tremolo=f=0.13:d=0.8[d];"
             "[4]lowpass=f=260,volume=0.9,tremolo=f=0.1:d=0.5[n];"
             "[a][b][c][d][n]amix=inputs=5:normalize=0,lowpass=f=900,"
             "aecho=0.8:0.7:120|260:0.35|0.22,volume=0.35,"
             "afade=t=in:d=3,aformat=sample_rates=48000:channel_layouts=stereo",
             str(bed)])
    whoosh = work / "whoosh.wav"
    if not whoosh.exists():
        _ff(["-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.9:d=1.4",
             "-af", "highpass=f=250,lowpass=f=3200,afade=t=in:d=0.9:curve=exp,afade=t=out:st=0.9:d=0.5,"
                    "aecho=0.6:0.5:60:0.3,volume=0.55,aformat=sample_rates=48000:channel_layouts=stereo",
             str(whoosh)])
    return bed, whoosh


def make_particles(work: Path) -> Path:
    """Seamlessly tileable 'marine snow' plate (1920x2160, two stacked copies)."""
    out = work / "particles.png"
    if not out.exists():
        _ff(["-f", "lavfi", "-i", f"color=black:s={W}x{H}:d=1",
             "-vf", "noise=alls=100:allf=0,format=gray,lut=y='if(gt(val,251),255,0)',"
                    "gblur=sigma=1.6,lut=y='min(255,val*3)',split[a][b];[a][b]vstack",
             "-frames:v", "1", str(out)])
    return out


def write_chapters(entries: list[dict], path: Path) -> None:
    lines, seen = [], set()
    for e in entries:
        if e["scene"] in seen:
            continue
        seen.add(e["scene"])
        s = int(e["start_sec"])
        lines.append(f"{s // 60}:{s % 60:02d} {e['scene_title']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(ctx: Context) -> dict:
    p, log = ctx.paths, ctx.log
    if not shutil.which("ffmpeg"):
        raise StageFailed("ffmpeg is not installed")
    if not p.manifest_json.exists():
        raise StageFailed("manifest.json not found; run manifest first")
    m = json.loads(p.manifest_json.read_text(encoding="utf-8"))
    entries = m["shots"]
    total = float(m["total_duration_sec"])
    missing = [e["shot_id"] for e in entries if e["image"]["status"] != "ready"]
    cuts = sum(len(_split(float(e["duration_sec"]), 5.0 if e.get("clip") else 0.0)) for e in entries)
    log.info(f"{len(entries)} shots -> ~{cuts} cuts, {total / 60:.1f} min; images missing: {len(missing)}; "
             f"clips ready: {m['counts']['clips_ready']}")
    if ctx.dry_run:
        log.info(f"[dry-run] would render and mix {p.slug}_final.mp4 locally (no API calls)")
        return {"rendered": 0, "dry_run": True}
    if missing:
        raise StageFailed(f"images missing for {', '.join(missing[:10])}; run image_generate first")

    work = p.dir / "render"
    work.mkdir(exist_ok=True)
    parts = []
    for i, e in enumerate(entries):
        fp = fingerprint({k: e.get(k) for k in ("duration_sec", "image", "clip", "audio", "overlay_text", "motion")}
                         | {"v": RENDER_VERSION, "i": i})
        out = work / f"{e['shot_id']}_{fp}.mp4"
        if not out.exists() or ctx.force:
            render_shot(e, i, p.dir, out)
            log.count("rendered")
            log.info(f"{e['shot_id']}: rendered {e['duration_sec']:.1f}s")
        parts.append(out)

    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{x.resolve()}'\n" for x in parts), encoding="utf-8")
    music = sorted((p.dir / "music").glob("*.mp3")) if (p.dir / "music").exists() else []
    bed, whoosh = make_sound_bed(work, total, music)
    log.info(f"Sound bed: {len(music)} music track(s)" if music else "Sound bed: synthesised drone")
    chapter_starts = []
    seen = set()
    for e in entries:
        if e["scene"] not in seen:
            seen.add(e["scene"])
            if e["start_sec"] > 0:
                chapter_starts.append(e["start_sec"])
    k = len(chapter_starts)
    wh = "".join(f"[w{i}]" for i in range(k))
    delays = ";".join(f"[w{i}]adelay={int(max(t - 0.8, 0) * 1000)}|{int(max(t - 0.8, 0) * 1000)}[d{i}]"
                      for i, t in enumerate(chapter_starts))
    sfx = "".join(f"[d{i}]" for i in range(k))
    fade_out = max(total - 1.5, 0)
    # Two particle layers drifting at different speeds = constant depth motion.
    graph = (
        f"[3:v]format=gray,split[pa][pb];"
        f"[pa]crop={W}:{H}:0:'{H}-mod(t*22\\,{H})'[m1];"
        f"[pb]scale={int(W * 1.6)}:{int(H * 3.2)},gblur=sigma=3,"
        f"crop={W}:{H}:'mod(t*6\\,300)':'{int(H * 1.6)}-mod(t*40\\,{int(H * 1.6)})'[m2];"
        f"color=c=0xF5EBD8:s={W}x{H}:r={FPS}:d={total:.3f},format=rgba,split[c1][c2];"
        "[c1][m1]alphamerge,colorchannelmixer=aa=0.38[o1];"
        "[c2][m2]alphamerge,colorchannelmixer=aa=0.28[o2];"
        "[0:v]eq=contrast=1.06:saturation=0.92:gamma=0.98:brightness='0.012*sin(2*PI*t/4)':eval=frame[base];"
        "[base][o1]overlay=shortest=1[b1];"
        "[b1][o2]overlay=shortest=1,"
        "vignette=angle=PI/5,noise=alls=7:allf=t+u,"
        f"fade=t=in:st=0:d=1.0,fade=t=out:st={fade_out:.2f}:d=1.5,format=yuv420p[v];"
        "[0:a]asplit=2[voice][key];"
        f"[1:a]atrim=duration={total:.3f}[bed];"
        "[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[ducked];"
        + (f"[2:a]asplit={k}{wh};{delays};" if k else "")
        + f"[voice][ducked]{sfx}amix=inputs={2 + k}:normalize=0:duration=first,"
        f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out:.2f}:d=1.5,"
        "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
    )
    final = p.dir / f"{p.slug}_final.mp4"
    particles = make_particles(work)
    _ff(["-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(bed), "-i", str(whoosh),
         "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", str(particles),
         "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "256k",
         "-movflags", "+faststart", str(final)])
    write_chapters(entries, p.dir / "chapters.txt")
    log.info(f"Wrote {p.rel(final)} ({total / 60:.1f} min, ~{cuts} cuts) and chapters.txt")
    return {"rendered": len(parts), "video": str(final), "cuts": cuts}

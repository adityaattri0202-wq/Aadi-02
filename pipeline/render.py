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
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .assets import fingerprint
from .context import Context, StageFailed

W, H, FPS = 1920, 1080, 30
SRC_W, SRC_H = 3200, 1800          # stills are upscaled first so tight crops stay sharp
SUB_SHOT_SEC = 4.2                 # target length of one cut
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_CINE = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
# Overlay look, set per style (``overlay: cinematic`` in the style yaml):
# "plate" = dark serif title in the top banner (Naturalist Plate art);
# "cinematic" = white sans with an amber rule and shadow, for dark photoreal shots.
OVERLAY_STYLE = {"name": "plate"}
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
        raise StageFailed(f"ffmpeg failed (exit {r.returncode}):\n" + r.stderr[-1500:])


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
    if OVERLAY_STYLE["name"] == "cinematic":
        return _overlay_cinematic(text, dur)
    if text.isupper() and len(text) <= 20:  # title card: large, centred in the top banner
        return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=110:fontcolor=0x3A2A18:"
                f"x=(w-text_w)/2:y=h*0.085-text_h/2+8:alpha='{alpha}'")
    return (f",drawtext=fontfile={FONT}:text='{_escape(text)}':fontsize=54:fontcolor=0xF3EAD6:"
            f"box=1:boxcolor=0x1E1A14@0.62:boxborderw=22:x=110:y=h-210:alpha='{alpha}'")


def _fade(t_in: float, t_out: float) -> str:
    return (f"if(lt(t,{t_in}),0,if(lt(t,{t_in}+0.4),(t-{t_in})/0.4,"
            f"if(lt(t,{t_out}-0.4),1,if(lt(t,{t_out}),({t_out}-t)/0.4,0))))")


def _overlay_cinematic(text: str, dur: float) -> str:
    """Numbered titles ("3. TITANOBOA") as a big centred card for a few seconds;
    other caps text (dates, sizes) as a lower-third stat with an amber rule;
    mixed case as a boxed label."""
    t = _escape(text)
    shadow = "shadowcolor=black@0.75:shadowx=0:shadowy=4"
    if text[:1].isdigit() and ". " in text[:4]:
        num, name = text.split(". ", 1)
        t_in, t_out = 0.3, min(max(dur - 0.3, 1.5), 4.0)
        a = _fade(t_in, t_out)
        return (f",drawbox=x=0:y=ih*0.38:w=iw:h=ih*0.26:color=black@0.4:t=fill:enable='between(t,{t_in},{t_out})',"
                f"drawtext=fontfile={FONT_CINE}:text='{_escape(num)}':fontsize=70:fontcolor=0xF2A93B:"
                f"x=(w-text_w)/2:y=h*0.405:alpha='{a}':{shadow},"
                f"drawtext=fontfile={FONT_CINE}:text='{_escape(name)}':fontsize=130:fontcolor=white:"
                f"x=(w-text_w)/2:y=h*0.405+88:alpha='{a}':{shadow}")
    t_in, t_out = 0.5, max(dur - 0.5, 1.2)
    a = _fade(t_in, t_out)
    if text.upper() == text:
        return (f",drawtext=fontfile={FONT_CINE}:text='{t}':fontsize=78:fontcolor=white:"
                f"x=110:y=h-250:alpha='{a}':{shadow},"
                f"drawbox=x=112:y=ih-156:w=160:h=7:color=0xF2A93B:t=fill:enable='between(t,{t_in},{t_out})'")
    return (f",drawtext=fontfile={FONT_CINE}:text='{t}':fontsize=52:fontcolor=white:"
            f"box=1:boxcolor=black@0.5:boxborderw=20:x=110:y=h-210:alpha='{a}'")


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
    parts = ([first] if first else []) + ([rest / n] * n if n else [])
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
    if entry.get("overlay_text", "").isupper() and not (clip and OVERLAY_STYLE["name"] == "cinematic"):
        clip_len, parts = 0.0, [dur]                   # title card: one calm move
    else:
        clip_len = min(5.0, dur) if clip else 0.0
        parts = _split(dur, clip_len)

    inputs = ["-i", str(image)]
    chains, labels = [], []
    still_parts = parts[1:] if clip_len else parts
    k = len(still_parts)
    if k:  # a short shot can be covered by its clip alone
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


MOGRAPH_VERSION = 3
# Music sits well under the narration (about -10 dB before ducking).
MUSIC_LEVEL = 0.32


def load_mograph_specs(topic_dir: Path) -> dict:
    """shot_id -> motion-graphics spec from topics/<slug>/mograph.yaml (optional)."""
    path = topic_dir / "mograph.yaml"
    if not path.exists():
        return {}
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("shots", {}) or {}


def render_mograph_shot(entry: dict, spec: dict, topic_dir: Path, work: Path, out: Path) -> None:
    from . import mograph
    dur = float(entry["duration_sec"])
    silent = work / f"{out.stem}_v.mp4"
    mograph.render(spec, dur, silent, work / "mograph", topic_dir)
    audio = topic_dir / entry["audio"]["path"] if entry.get("audio") and entry["audio"]["status"] == "ready" else None
    a_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    _ff(["-i", str(silent), *a_in, "-filter_complex",
         f"[1:a]aresample=48000,apad,atrim=duration={dur:.3f}[a]", "-map", "0:v", "-map", "[a]",
         "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000", str(out)])
    silent.unlink(missing_ok=True)


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
    try:
        import yaml
        OVERLAY_STYLE["name"] = (yaml.safe_load(ctx.settings.style_path.read_text()) or {}).get("overlay", "plate")
    except (OSError, AttributeError):
        OVERLAY_STYLE["name"] = "plate"
    total = float(m["total_duration_sec"])
    mg_ids = set(load_mograph_specs(p.dir))
    missing = [e["shot_id"] for e in entries if e["image"]["status"] != "ready" and e["shot_id"] not in mg_ids]
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
    mg_specs = load_mograph_specs(p.dir)
    if mg_specs:
        log.info(f"Motion-graphics shots: {', '.join(sorted(mg_specs))}")
    only = set(getattr(ctx, "only_shots", None) or [])
    parts, jobs = [], []
    for i, e in enumerate(entries):
        if only and e["shot_id"] not in only:
            continue
        spec = mg_specs.get(e["shot_id"])
        fp = fingerprint({k: e.get(k) for k in ("duration_sec", "image", "clip", "audio", "overlay_text", "motion")}
                         | {"v": RENDER_VERSION, "i": i, "ov": OVERLAY_STYLE["name"], "mg": spec, "mgv": MOGRAPH_VERSION if spec else 0})
        out = work / f"{e['shot_id']}_{fp}.mp4"
        if not out.exists() or ctx.force:
            jobs.append((i, e, spec, out))
        parts.append(out)

    def _render(job):
        i, e, spec, out = job
        if spec:
            render_mograph_shot(e, spec, p.dir, work, out)
        else:
            render_shot(e, i, p.dir, out)
        return e, spec

    # Shots are independent; ffmpeg filters like zoompan are mostly single-threaded,
    # so a few in parallel use the machine far better.
    if any(spec for _, _, spec, _ in jobs):  # shared plates: build once before going parallel
        from . import mograph
        (work / "mograph").mkdir(parents=True, exist_ok=True)
        mograph.rays_plate(work / "mograph" / "rays.png")
        mograph.particles_plate(work / "mograph" / "particles_mg.png")
    workers = max(1, min(len(jobs), (os.cpu_count() or 2) - 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for e, spec in pool.map(_render, jobs):
            log.count("rendered")
            log.info(f"{e['shot_id']}: rendered {e['duration_sec']:.1f}s" + (" (motion graphics)" if spec else ""))
    if only:  # preview of selected shots: shift timings so chapters/SFX line up
        keep = [e for e in entries if e["shot_id"] in only]
        t0 = 0.0
        for e in keep:
            d = float(e["duration_sec"])
            e.update(start_sec=t0, end_sec=t0 + d)
            t0 += d
        entries, total = keep, t0

    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{x.resolve()}'\n" for x in parts), encoding="utf-8")
    music = sorted((p.dir / "music").glob("*.mp3")) if (p.dir / "music").exists() else []
    if music:  # repeat the playlist until it covers the whole video
        lengths = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", str(m)], capture_output=True, text=True).stdout or 0)
                   for m in music]
        playlist, covered, k = [], 0.0, 0
        while covered < total + 5 and k < 50:
            playlist.append(music[k % len(music)])
            covered += max(lengths[k % len(music)] - 5, 1)
            k += 1
        music = playlist
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
    # Audio and video are mixed in separate passes: one huge combined graph runs
    # out of memory on long videos.
    final = p.dir / (f"{p.slug}_preview.mp4" if only else f"{p.slug}_final.mp4")
    a_graph = (
        "[0:a]asplit=2[voice][key];"
        f"[1:a]atrim=duration={total:.3f},volume={MUSIC_LEVEL}[bed];"
        "[bed][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=800[ducked];"
        + (f"[2:a]asplit={k}{wh};{delays};" if k else "")
        + f"[voice][ducked]{sfx}amix=inputs={2 + k}:normalize=0:duration=first,"
        f"afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out:.2f}:d=1.5,"
        "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
    )
    cine = OVERLAY_STYLE["name"] == "cinematic"
    if cine:  # trailer-style hit: the whoosh rises into a deep sub boom on the cut
        boom = work / "whoosh_boom.wav"
        if not boom.exists():
            _ff(["-i", str(whoosh), "-f", "lavfi", "-i",
                 "aevalsrc='0.9*sin(2*PI*(58-30*t)*t)*exp(-2.6*t)':s=48000:d=2.2",
                 "-filter_complex",
                 "[1:a]lowpass=f=160,adelay=800|800,aformat=sample_rates=48000:channel_layouts=stereo,"
                 "volume=1.6[b];[0:a][b]amix=inputs=2:normalize=0:duration=longest",
                 str(boom)])
        whoosh = boom
    mix = work / "mix.m4a"
    _ff(["-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(bed), "-i", str(whoosh),
         "-filter_complex", a_graph, "-map", "[a]", "-vn", "-c:a", "aac", "-b:a", "256k", str(mix)])

    grade = ("eq=contrast=1.04:saturation=1.0:gamma=1.08:brightness='0.03+0.01*sin(2*PI*t/4)':eval=frame")
    all_mograph = bool(mg_specs) and all(e["shot_id"] in mg_specs for e in entries)
    # mograph shots carry their own light vignette; don't stack a second one (crushed the edges)
    vig = "" if all_mograph else "vignette=angle=PI/9,"
    finish = (f"{vig}noise=alls=4:allf=t+u,"
              f"fade=t=in:st=0:d=1.0,fade=t=out:st={fade_out:.2f}:d=1.5,format=yuv420p[v]")
    if cine:
        hits = chapter_starts + [e["start_sec"] for e in entries
                                 if (e.get("clip") or {}).get("status") == "ready" and e["start_sec"] > 0]
        hits = sorted(set(round(t, 2) for t in hits))
        flash = "+".join(f"0.55*exp(-pow((t-{t})*9\\,2))" for t in chapter_starts) or "0"
        env = "+".join(f"between(t\\,{t}\\,{t + 1.4})*(1-(t-{t})/1.4)" for t in hits) or "0"
        bar = int(H * 0.122)  # ~2.35:1 frame inside 16:9
        grade = ("colorbalance=rs=-0.05:gs=-0.01:bs=0.07:rh=0.07:gh=0.02:bh=-0.05,"
                 f"eq=contrast=1.10:saturation=1.08:gamma=1.04:brightness='0.02+{flash}':eval=frame,"
                 f"crop=w=iw-40:h=ih-40:x='20+14*sin(t*41)*({env})':y='20+11*cos(t*37)*({env})',"
                 f"scale={W}:{H}")
        finish = (f"vignette=angle=PI/7,noise=alls=7:allf=t+u,"
                  f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
                  f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill,"
                  f"fade=t=in:st=0:d=1.0,fade=t=out:st={fade_out:.2f}:d=1.5,format=yuv420p[v]")
    v_inputs = ["-f", "concat", "-safe", "0", "-i", str(concat)]
    if all_mograph:  # mograph shots already carry their own particle layers
        v_graph = f"[0:v]{grade},{finish}"
    else:  # two particle layers drifting at different speeds = constant depth motion
        particles = make_particles(work)
        v_inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", str(particles)]
        v_graph = (
            f"[1:v]format=gray,split[pa][pb];"
            f"[pa]crop={W}:{H}:0:'{H}-mod(t*22\\,{H})'[m1];"
            f"[pb]scale={int(W * 1.6)}:{int(H * 3.2)},gblur=sigma=3,"
            f"crop={W}:{H}:'mod(t*6\\,300)':'{int(H * 1.6)}-mod(t*40\\,{int(H * 1.6)})'[m2];"
            f"color=c=0xF5EBD8:s={W}x{H}:r={FPS}:d={total:.3f},format=rgba,split[c1][c2];"
            "[c1][m1]alphamerge,colorchannelmixer=aa=0.38[o1];"
            "[c2][m2]alphamerge,colorchannelmixer=aa=0.28[o2];"
            f"[0:v]{grade}[base];[base][o1]overlay=shortest=1[b1];[b1][o2]overlay=shortest=1,{finish}"
        )
    video = work / "video_only.mp4"
    _ff([*v_inputs, "-filter_complex", v_graph, "-map", "[v]", "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "8M", "-bufsize", "16M", str(video)])
    _ff(["-i", str(video), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest",
         "-movflags", "+faststart", str(final)])
    if not only:
        write_chapters(entries, p.dir / "chapters.txt")
    log.info(f"Wrote {p.rel(final)} ({total / 60:.1f} min, ~{cuts} cuts) and chapters.txt")
    return {"rendered": len(parts), "video": str(final), "cuts": cuts}

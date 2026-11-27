"""Cut a ~50 s vertical Short from the leopard seal final video."""
import re, subprocess, sys
from pathlib import Path

T = Path("/home/user/Aadi-02/topics/leopard_seal")
OUT = T / "leopard_seal_short.mp4"
SEGS = [(0.0, 30.194), (252.46, 264.379), (562.378, 571.476)]  # hook, ice-edge, payoff


def ts(s):
    h, r = divmod(s, 3600); m, r = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(r):02d},{int(round((r % 1) * 1000)):03d}"


def parse(t):
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


blocks = re.split(r"\n\s*\n", (T / "subtitles.srt").read_text().strip())
cues = []
for b in blocks:
    lines = b.splitlines()
    a, z = [parse(x.strip()) for x in lines[1].split("-->")]
    cues.append((a, z, " ".join(lines[2:])))

out, off, n = [], 0.0, 1
for s, e in SEGS:
    for a, z, txt in cues:
        if z <= s + 0.05 or a >= e - 0.05:
            continue
        out.append(f"{n}\n{ts(max(a, s) - s + off)} --> {ts(min(z, e) - s + off)}\n{txt}\n")
        n += 1
    off += e - s
srt = T / "render" / "short.srt"
srt.write_text("\n".join(out))
total = off

parts, cat, ins = [], "", []
for i, (s, e) in enumerate(SEGS):
    d = e - s
    seg = T / "render" / f"short_seg{i}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{s}", "-i",
                    str(T / "leopard_seal_final.mp4"), "-t", f"{d:.3f}", "-c:v", "libx264", "-crf", "16",
                    "-preset", "fast", "-c:a", "pcm_s16le", str(seg).replace(".mp4", ".mov")], check=True)
    ins += ["-i", str(seg).replace(".mp4", ".mov")]
    parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}];"
                 f"[{i}:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.12,afade=t=out:st={d - 0.15:.3f}:d=0.15[a{i}];")
    cat += f"[v{i}][a{i}]"
style = ("FontName=Inter Display,Bold=1,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
         "BorderStyle=1,Outline=2.2,Shadow=0,Alignment=2,MarginV=62,MarginL=18,MarginR=18")
g = ("".join(parts) + f"{cat}concat=n={len(SEGS)}:v=1:a=1[cv][ca];"
     "[cv]split[bgs][fgs];"
     "[bgs]scale=-2:1920,crop=1080:1920,boxblur=30:3,eq=brightness=-0.12[bg];"
     "[fgs]scale=1080:-2[fg];"
     "[bg][fg]overlay=0:(H-h)/2-60,"
     "drawbox=x=90:y=300:w=900:h=150:color=black@0.45:t=fill,"
     "drawtext=fontfile=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf:text='WHY ARE PENGUINS':"
     "fontsize=58:fontcolor=white:x=(w-text_w)/2:y=318,"
     "drawtext=fontfile=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf:text='AFRAID TO JUMP?':"
     "fontsize=64:fontcolor=0xF2A93B:x=(w-text_w)/2:y=382,"
     f"subtitles={srt}:force_style='{style}',"
     f"fade=t=out:st={total - 0.6:.2f}:d=0.6,format=yuv420p[v];"
     f"[ca]afade=t=out:st={total - 0.8:.2f}:d=0.8,loudnorm=I=-14:TP=-1.5[a]")
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins,
       "-filter_complex", g, "-map", "[v]", "-map", "[a]", "-r", "30",
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
       "-movflags", "+faststart", str(OUT)]
subprocess.run(cmd, check=True)
print(f"wrote {OUT} {total:.1f}s")

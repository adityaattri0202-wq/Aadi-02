# Usage: python -m pipeline.split_voice topics/<slug> <speed> <parts.json> [part,numbers]
"""Split ElevenLabs part files on the <break> pauses into per-shot mp3s,
speeding the voice up (pitch kept) and writing pipeline sidecars."""
import json, re, subprocess, sys
from pathlib import Path

T = Path(sys.argv[1])            # topic dir
SPEED = float(sys.argv[2])       # e.g. 1.1
parts = json.loads(Path(sys.argv[3]).read_text())
which = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else range(1, len(parts) + 1)
shots = {s["id"]: s for s in json.loads((T / "shots.json").read_text())}
vo = T / "voiceover"


def silences(f, min_d):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(f), "-af",
                        f"silencedetect=noise=-38dB:d={min_d}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    return list(zip(st, en))


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(f)]).strip())


for pi in which:
    ids = parts[pi - 1]
    f = vo / "parts" / f"p{pi}.mp3"
    total = dur(f)
    need = len(ids) - 1
    for d in (1.2, 1.1, 1.0, 0.9, 1.3):
        sil = [s for s in silences(f, d) if s[0] > 0.5 and s[1] < total - 0.3]
        if len(sil) >= need:
            break
    # keep the `need` longest pauses (the inserted breaks), in time order
    sil = sorted(sorted(sil, key=lambda s: s[1] - s[0], reverse=True)[:need])
    if len(sil) != need:
        sys.exit(f"part {pi}: found {len(sil)} pauses, need {need}")
    cuts = [0.0] + [(a + b) / 2 for a, b in sil] + [total]
    for k, sid in enumerate(ids):
        a, b = cuts[k], cuts[k + 1]
        out = vo / f"{sid}.mp3"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                        "-i", str(f), "-af",
                        f"silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        f"silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        f"atempo={SPEED},apad=pad_dur=0.12",
                        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", str(out)], check=True)
        d = dur(out)
        (vo / f"{sid}.json").write_text(json.dumps({
            "fingerprint": "external-elevenlabs", "provider": "elevenlabs",
            "voice": "Atlas (3YzGaTGef0x5PLEK9yGq)", "file": out.name, "duration_sec": round(d, 3),
            "words": [], "text": shots[sid]["narration"], "speed": SPEED}, indent=1))
        print(sid, round(d, 2), shots[sid]["narration"][:50])

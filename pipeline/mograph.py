"""Motion-graphics shots: layered 2D animation rendered locally with ffmpeg.

Instead of moving a camera over one flat picture, a mograph shot composites
separate layers that each move on their own, like an animated documentary:

- background plate (deep-water gradient with glow, or an image)
- animated light rays and two drifting particle layers
- "subjects": cut-out characters (transparent PNG) that swim in, bob and tilt
- kinetic labels that pop in with an accent underline
- number counters ("LENGTH 0 -> 17 M"), scale bars
- a camera HUD (REC dot, timecode, corner brackets, depth counter)
- a slow camera push over the whole composite, vignette, optional tint

Shots opt in through ``topics/<slug>/mograph.yaml`` (shot_id -> spec); see
README "Motion graphics". Built-in flat-vector assets (``asset: livyatan``,
``bus``, ...) are drawn procedurally, so a shot can render with zero credits;
any PNG with transparency (e.g. an AI cut-out) can be used via ``path``.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .context import StageFailed

OUT_W, OUT_H, FPS = 1920, 1080, 30
CW, CH = 2304, 1296                        # composite canvas (1.2x) for the camera move
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
ACCENT = "0xF2A93B"                        # amber accent (house colour)
TEXT = "0xF4F1EA"


def _hex(c: str) -> tuple[int, int, int]:
    c = c.replace("#", "").replace("0x", "")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------
# Procedural flat-vector assets (drawn at 2x, downsampled for clean edges)
# --------------------------------------------------------------------------
def _canvas(w, h, k=2):
    img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), k


def _poly(d, pts, k, fill):
    d.polygon([(x * k, y * k) for x, y in pts], fill=fill)


def draw_livyatan(path: Path, silhouette: bool = False) -> Path:
    """Side view of Livyatan facing right, flat-vector style (1600x560)."""
    img, d, k = _canvas(1600, 560)
    body = (22, 44, 52, 255) if silhouette else (47, 62, 70, 255)
    belly = (22, 44, 52, 255) if silhouette else (107, 123, 131, 255)
    _poly(d, [(240, 300), (110, 205), (55, 196), (150, 292), (55, 392), (118, 386), (240, 312)], k, body)  # flukes
    _poly(d, [(230, 285), (400, 245), (600, 200), (680, 188), (720, 165), (760, 180), (1000, 150),
              (1200, 140), (1380, 140), (1480, 150), (1530, 180), (1552, 230), (1556, 292), (1550, 332),
              (1522, 352), (1500, 382), (1440, 396), (1200, 402), (1000, 410), (800, 400), (600, 370),
              (400, 336), (230, 316)], k, body)
    if not silhouette:
        _poly(d, [(1440, 396), (1200, 402), (1000, 410), (800, 400), (600, 370), (400, 336), (460, 326),
                  (800, 356), (1200, 364), (1440, 372), (1500, 382)], k, belly)
        d.line([(1532 * k, 352 * k), (1170 * k, 372 * k)], fill=(14, 20, 24, 255), width=6 * k)
        for i in range(11):  # teeth on both jaws
            x = 1505 - i * 30
            y = 353 + (1532 - x) * 0.055
            _poly(d, [(x - 9, y - 2), (x + 9, y - 2), (x, y + 20)], k, (236, 226, 200, 255))
            _poly(d, [(x - 24, y + 4), (x - 8, y + 4), (x - 16, y - 16)], k, (236, 226, 200, 255))
        d.ellipse([(1240 * k, 252 * k), (1264 * k, 276 * k)], fill=(10, 14, 16, 255))
        d.ellipse([(1252 * k, 256 * k), (1259 * k, 263 * k)], fill=(230, 230, 230, 255))
        _poly(d, [(1080, 368), (1000, 452), (955, 462), (990, 384)], k, (38, 50, 57, 255))  # fin
        for x0 in (600, 820, 1040):  # subtle skin creases
            d.arc([(x0 * k, 230 * k), ((x0 + 160) * k, 330 * k)], 200, 250, fill=(58, 75, 84, 255), width=3 * k)
    img.resize((1600, 560), Image.LANCZOS).save(path)
    return path


def draw_bus(path: Path) -> Path:
    """Flat yellow school bus, side view (1200x440)."""
    img, d, k = _canvas(1200, 440)
    d.rounded_rectangle([(40 * k, 60 * k), (1000 * k, 330 * k)], radius=30 * k, fill=(232, 176, 52, 255))
    d.rounded_rectangle([(980 * k, 160 * k), (1160 * k, 330 * k)], radius=24 * k, fill=(232, 176, 52, 255))
    for i in range(9):
        x = 80 + i * 98
        d.rounded_rectangle([(x * k, 95 * k), ((x + 78) * k, 180 * k)], radius=8 * k, fill=(34, 49, 58, 255))
    d.rectangle([(40 * k, 215 * k), (1160 * k, 228 * k)], fill=(40, 40, 40, 255))
    d.rectangle([(40 * k, 262 * k), (1160 * k, 272 * k)], fill=(40, 40, 40, 255))
    d.rectangle([(1150 * k, 300 * k), (1180 * k, 330 * k)], fill=(70, 70, 70, 255))
    for cx in (230, 900):
        d.ellipse([((cx - 62) * k, 272 * k), ((cx + 62) * k, 396 * k)], fill=(20, 20, 20, 255))
        d.ellipse([((cx - 26) * k, 308 * k), ((cx + 26) * k, 360 * k)], fill=(150, 150, 150, 255))
    img.resize((1200, 440), Image.LANCZOS).save(path)
    return path


BUILTIN_ASSETS = {
    "livyatan": lambda p: draw_livyatan(p),
    "livyatan_silhouette": lambda p: draw_livyatan(p, silhouette=True),
    "bus": draw_bus,
}


def asset_path(name: str, work: Path) -> Path:
    if name not in BUILTIN_ASSETS:
        raise StageFailed(f"mograph: unknown built-in asset '{name}' (have {sorted(BUILTIN_ASSETS)})")
    p = work / f"asset_{name}.png"
    if not p.exists():
        BUILTIN_ASSETS[name](p)
    return p


# --------------------------------------------------------------------------
# Plates
# --------------------------------------------------------------------------
def gradient_plate(path: Path, top: str, bottom: str, glow: float = 0.35) -> Path:
    if path.exists():
        return path
    t, b = np.array(_hex(top), float), np.array(_hex(bottom), float)
    y = np.linspace(0, 1, CH)[:, None, None]
    img = t * (1 - y) + b * y
    yy, xx = np.mgrid[0:CH, 0:CW]
    r = np.sqrt(((xx - CW / 2) / (CW * 0.55)) ** 2 + ((yy + CH * 0.15) / (CH * 0.9)) ** 2)
    img = img + glow * 90 * np.clip(1 - r, 0, 1)[..., None] ** 2
    Image.fromarray(np.clip(img, 0, 255).astype("uint8")).save(path)
    return path


def rays_plate(path: Path) -> Path:
    if path.exists():
        return path
    img = Image.new("L", (CW, CH), 0)
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(7)
    for _ in range(9):
        cx = CW / 2 + rng.uniform(-CW * 0.3, CW * 0.3)
        spread = rng.uniform(40, 130)
        lean = rng.uniform(-260, 260)
        d.polygon([(cx - spread * 0.3, -10), (cx + spread * 0.3, -10),
                   (cx + lean + spread, CH * 0.95), (cx + lean - spread, CH * 0.95)],
                  fill=int(rng.uniform(28, 60)))
    img = img.filter(ImageFilter.GaussianBlur(28))
    fade = np.linspace(1, 0, CH)[:, None] ** 1.4
    a = (np.asarray(img, float) * fade).astype("uint8")
    rgba = np.zeros((CH, CW, 4), "uint8")
    rgba[..., :3] = (210, 235, 230)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)
    return path


def particles_plate(path: Path) -> Path:
    """Tileable two-copy marine-snow plate (CW x 2*CH, grey)."""
    if path.exists():
        return path
    rng = np.random.default_rng(3)
    tile = np.zeros((CH, CW), float)
    n = 900
    ys, xs = rng.integers(0, CH, n), rng.integers(0, CW, n)
    tile[ys, xs] = rng.uniform(120, 255, n)
    img = Image.fromarray(tile.astype("uint8")).filter(ImageFilter.GaussianBlur(1.4))
    arr = np.clip(np.asarray(img, float) * 4, 0, 255).astype("uint8")
    Image.fromarray(np.vstack([arr, arr])).save(path)
    return path


# --------------------------------------------------------------------------
# Expression helpers
# --------------------------------------------------------------------------
def _ease(start: float, dur: float) -> str:
    """Smoothstep 0->1 between start and start+dur, as an ffmpeg expression of t."""
    p = f"clip((t-{start:.3f})/{max(dur, 0.01):.3f},0,1)"
    return f"({p}*{p}*(3-2*{p}))"


def _text_width(text: str, size: int, font: str = FONT_BOLD) -> int:
    return int(ImageFont.truetype(font, size).getlength(text))


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


# --------------------------------------------------------------------------
# Compositor
# --------------------------------------------------------------------------
def render(spec: dict, dur: float, out: Path, work: Path, topic_dir: Path) -> Path:
    """Render one silent mograph shot of length ``dur`` to ``out`` (1920x1080)."""
    work.mkdir(parents=True, exist_ok=True)
    bg = spec.get("background", {})
    inputs, chains = [], []

    def add_image(path: Path) -> int:
        inputs.extend(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(path)])
        return len(inputs) // 8 - 1

    if bg.get("path"):
        i_bg = add_image(topic_dir / bg["path"])
        chains.append(f"[{i_bg}:v]scale={CW}:{CH}:force_original_aspect_ratio=increase,crop={CW}:{CH},"
                      f"format=rgba[base]")
    else:
        top, bottom = bg.get("top", "#174A58"), bg.get("bottom", "#030A0D")
        plate = gradient_plate(work / f"grad_{top[1:]}_{bottom[1:]}.png", top, bottom, bg.get("glow", 0.5))
        i_bg = add_image(plate)
        chains.append(f"[{i_bg}:v]format=rgba[base]")
    cur = "base"

    if bg.get("path2"):  # crossfade to a second plate (e.g. ancient -> modern)
        i_b2 = add_image(topic_dir / bg["path2"])
        fade_at = float(bg.get("fade_at", dur * 0.4))
        chains.append(f"[{i_b2}:v]scale={CW}:{CH}:force_original_aspect_ratio=increase,crop={CW}:{CH},"
                      f"format=rgba,fade=t=in:st={fade_at:.2f}:d={float(bg.get('fade_dur', 3.0)):.2f}:alpha=1[bg2]")
        chains.append(f"[{cur}][bg2]overlay=0:0[l_bg2]")
        cur = "l_bg2"

    if spec.get("rays", True):
        i_r = add_image(rays_plate(work / "rays.png"))
        chains.append(f"[{i_r}:v]format=rgba,rotate=a='0.025*sin(2*PI*t/11)':c=none[rays]")
        chains.append(f"[{cur}][rays]overlay=0:0[l_r]")
        cur = "l_r"

    for n, layer in enumerate(spec.get("subjects", [])):
        src = asset_path(layer["asset"], work) if layer.get("asset") else topic_dir / layer["path"]
        i_s = add_image(src)
        w = int(layer.get("width", 0.5) * CW)
        start = float(layer.get("start", 0))
        mdur = float(layer.get("move", dur - start))
        e = _ease(start, mdur)
        (fx, fy), (tx, ty) = layer.get("from", [0.5, 0.5]), layer.get("to", [0.5, 0.5])
        bob, bobp = float(layer.get("bob", 0.008)), float(layer.get("bob_period", 3.2))
        (fx, fy), (tx, ty) = layer.get("from", [0.5, 0.5]), layer.get("to", [0.5, 0.5])
        tilt = float(layer.get("tilt", 0.012))
        opacity = float(layer.get("opacity", 1.0))
        # Built-in assets face right; auto-flip so a subject faces where it travels.
        flip_auto = tx < fx if layer.get("flip") is None else bool(layer.get("flip"))
        flip = ",hflip" if flip_auto else ""
        g0, g1 = layer.get("grow", [1.0, 1.0])
        scale = (f"scale=w='trunc({w}*({g0}+({g1}-{g0})*{e})/2)*2':h=-1:eval=frame" if (g0, g1) != (1.0, 1.0)
                 else f"scale={w}:-1")
        end = layer.get("end")
        chains.append(
            f"[{i_s}:v]format=rgba,{scale}{flip},"
            + (f"rotate=a='{tilt}*sin(2*PI*t/{bobp * 1.3:.2f})':c=none:ow='rotw(0.06)':oh='roth(0.06)',"
               if (g0, g1) == (1.0, 1.0) else "")  # rotate's frame is fixed at init: no tilt while growing
            + f"colorchannelmixer=aa={opacity},fade=t=in:st={start:.2f}:d=0.6:alpha=1[s{n}]")
        x = f"({fx}+({tx}-{fx})*{e})*W-w/2"
        y = f"({fy}+({ty}-{fy})*{e})*H-h/2+{bob}*H*sin(2*PI*t/{bobp})"
        chains.append(f"[{cur}][s{n}]overlay=x='{x}':y='{y}':eval=frame:"
                      f"enable='{f'between(t,{start:.2f},{float(end):.2f})' if end is not None else f'gte(t,{start:.2f})'}'[l_s{n}]")
        cur = f"l_s{n}"

    if spec.get("particles", True):
        i_p = add_image(particles_plate(work / "particles_mg.png"))
        chains.append(f"[{i_p}:v]format=gray,split[pa][pb];"
                      f"[pa]crop={CW}:{CH}:0:'{CH}-mod(t*24\\,{CH})'[m1];"
                      f"[pb]scale={CW}:{CH * 2},gblur=sigma=2.5,"
                      f"crop={CW}:{CH}:0:'{CH}-mod(t*45\\,{CH})',hflip[m2];"
                      f"color=c=0xDDEFEA:s={CW}x{CH}:r={FPS}:d={dur:.3f},format=rgba,split[c1][c2];"
                      f"[c1][m1]alphamerge,colorchannelmixer=aa=0.45[o1];"
                      f"[c2][m2]alphamerge,colorchannelmixer=aa=0.30[o2];"
                      f"[{cur}][o1]overlay=shortest=1[l_p1];[l_p1][o2]overlay=shortest=1[l_p]")
        cur = "l_p"

    draws = []
    sx, sy = CW / OUT_W, CH / OUT_H   # spec sizes are in 1080p units
    for lab in spec.get("labels", []):
        size = int(lab.get("size", 56) * sy)
        txt = lab["text"].upper()
        start = float(lab.get("start", 0.4))
        end = float(lab.get("end", dur))
        e = _ease(start, 0.45)
        cx, cy = lab.get("x", 0.5), lab.get("y", 0.8)
        color = ACCENT if lab.get("accent") else TEXT
        tw = _text_width(txt, size)
        x0 = int(cx * CW - tw / 2)
        alpha = f"{e}*(1-{_ease(end - 0.4, 0.4)})"
        pad = int(16 * sy)
        draws.append(f"drawtext=fontfile={FONT_BOLD}:text='{_esc(txt)}':fontsize={size}:fontcolor={color}:"
                     f"box=1:boxcolor=0x0B0F12@0.55:boxborderw={pad}:"
                     f"shadowcolor=black@0.6:shadowx=3:shadowy=3:x={x0}:"
                     f"y='{cy}*h-text_h/2+{int(28 * sy)}*(1-{e})':alpha='{alpha}'")
        if lab.get("underline", True):
            uy = int(cy * CH + size * 0.62 + pad)
            draws.append(f"drawbox=x={x0}:y={uy}:w={tw}:h={max(4, int(5 * sy))}:color={ACCENT}@0.95:t=fill:"
                         f"enable='between(t,{start + 0.3:.2f},{end:.2f})'")

    for c in spec.get("counters", []):
        size = int(c.get("size", 64) * sy)
        start, cdur = float(c.get("start", 0.5)), float(c.get("duration", 2.0))
        v0, v1 = float(c.get("from", 0)), float(c["to"])
        val = f"({v0}+({v1}-{v0})*{_ease(start, cdur)})"
        label, suffix = _esc(c.get("label", "").upper()), _esc(c.get("suffix", ""))
        num = f"%{{eif\\:floor({val})\\:d}}"
        if c.get("decimals"):
            num += f".%{{eif\\:mod(floor({val}*10)\\,10)\\:d}}"
        cx, cy = c.get("x", 0.5), c.get("y", 0.2)
        if label:
            draws.append(f"drawtext=fontfile={FONT_BOLD}:text='{label}':fontsize={int(size * 0.45)}:"
                         f"fontcolor={ACCENT}:box=1:boxcolor=0x0B0F12@0.55:boxborderw={int(10 * sy)}:"
                         f"x='{cx}*w-text_w/2':y='{cy}*h-{int(size * 0.95)}':"
                         f"alpha='{_ease(start - 0.3, 0.3)}'")
        draws.append(f"drawtext=fontfile={FONT_BOLD}:text='{num}{suffix}':fontsize={size}:fontcolor={TEXT}:"
                     f"box=1:boxcolor=0x0B0F12@0.55:boxborderw={int(14 * sy)}:"
                     f"shadowcolor=black@0.6:shadowx=3:shadowy=3:x='{cx}*w-text_w/2':y='{cy}*h-text_h/2':"
                     f"alpha='{_ease(start - 0.3, 0.3)}'")

    for s in spec.get("scalebars", []):
        y = int(s.get("y", 0.85) * CH)
        x0, x1 = int(s.get("x0", 0.1) * CW), int(s.get("x1", 0.9) * CW)
        start = float(s.get("start", 0.5))
        draws.append(f"drawbox=x={x0}:y={y}:w={x1 - x0}:h=4:color={TEXT}@0.85:t=fill:enable='gte(t,{start})'")
        for x in (x0, x1 - 4):
            draws.append(f"drawbox=x={x}:y={y - 14}:w=4:h=32:color={TEXT}@0.85:t=fill:enable='gte(t,{start})'")

    for mk in spec.get("markers", []):
        start = float(mk.get("start", 0.5))
        cx, cy = int(mk["x"] * CW), int(mk["y"] * CH)
        r = int(mk.get("size", 26) * sy)
        dot = int(r * 0.55)
        draws.append(f"drawbox=x={cx - dot // 2}:y={cy - dot // 2}:w={dot}:h={dot}:color={ACCENT}@1:t=fill:"
                     f"enable='gte(t,{start})'")
        for k, (rr, a) in enumerate(((r, 0.9), (int(r * 1.8), 0.5))):
            draws.append(f"drawbox=x={cx - rr}:y={cy - rr}:w={2 * rr}:h={2 * rr}:color={ACCENT}@{a}:t=3:"
                         f"enable='gte(t,{start})*lt(mod(t-{start}+{k * 0.4},1.2),0.7)'")
        if mk.get("label"):
            size = int(mk.get("label_size", 40) * sy)
            dx = int(mk.get("label_dx", 0.0) * CW) or int(r * 2.4)
            draws.append(f"drawtext=fontfile={FONT_BOLD}:text='{_esc(mk['label'].upper())}':fontsize={size}:"
                         f"fontcolor={TEXT}:box=1:boxcolor=0x0B0F12@0.6:boxborderw={int(10 * sy)}:"
                         f"shadowcolor=black@0.7:shadowx=3:shadowy=3:x={cx + dx}:y={cy - size // 2}:"
                         f"alpha='{_ease(start + 0.2, 0.4)}'")

    for path in spec.get("paths", []):
        pts = [(float(x) * CW, float(y) * CH) for x, y in path["points"]]
        start, pdur = float(path.get("start", 0.5)), float(path.get("duration", 3.0))
        seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        total_len = sum(seg) or 1
        n = int(path.get("dots", 34))
        for i in range(n + 1):
            dist, j = total_len * i / n, 0
            while j < len(seg) - 1 and dist > seg[j]:
                dist -= seg[j]
                j += 1
            f = dist / seg[j] if seg[j] else 0
            x = pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f
            y = pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f
            s = int(10 * sy)
            draws.append(f"drawbox=x={int(x - s / 2)}:y={int(y - s / 2)}:w={s}:h={s}:color={ACCENT}@0.95:t=fill:"
                         f"enable='gte(t,{start + pdur * i / n:.2f})'")

    if spec.get("divider"):
        draws.append(f"drawbox=x={CW // 2 - 3}:y=0:w=6:h={CH}:color={TEXT}@0.85:t=fill")

    hud = spec.get("hud")
    if hud:
        m, L, th = int(60 * sx), int(70 * sx), max(3, int(3 * sx))
        col = f"{TEXT}@0.8"
        for (x, y, dx, dy) in ((m, m, 1, 1), (CW - m, m, -1, 1), (m, CH - m, 1, -1), (CW - m, CH - m, -1, -1)):
            draws.append(f"drawbox=x={min(x, x + dx * L)}:y={y if dy > 0 else y - th}:w={L}:h={th}:color={col}:t=fill")
            draws.append(f"drawbox=x={x if dx > 0 else x - th}:y={min(y, y + dy * L)}:w={th}:h={L}:color={col}:t=fill")
        fs = int(44 * sy)
        draws.append(f"drawtext=fontfile={FONT_BOLD}:text='●':fontsize={fs}:fontcolor=0xE5483B:"
                     f"x={m + 30}:y={m + 30}:enable='lt(mod(t,1),0.6)'")
        draws.append(f"drawtext=fontfile={FONT_BOLD}:text='REC':fontsize={fs}:fontcolor={TEXT}:x={m + 30 + fs + 12}:y={m + 30}")
        clock = hud.get("clock", "21:47:")
        draws.append(f"drawtext=fontfile={FONT_MONO}:text='{_esc(clock)}%{{eif\\:mod(trunc(t)+12\\,60)\\:d\\:2}}':"
                     f"fontsize={fs}:fontcolor={TEXT}:x=w-text_w-{m + 30}:y={m + 30}")
        if "depth_to" in hud:
            d0, d1 = float(hud.get("depth_from", 0)), float(hud["depth_to"])
            val = f"({d0}+({d1}-{d0})*{_ease(0, dur)})"
            draws.append(f"drawtext=fontfile={FONT_MONO}:text='DEPTH %{{eif\\:floor({val})\\:d}} M':"
                         f"fontsize={int(fs * 0.85)}:fontcolor={TEXT}@0.85:x={m + 30}:y=h-{m + 30}-text_h")
        if hud.get("crosshair", True):
            draws.append(f"drawbox=x=w/2-{L // 3}:y=h/2-1:w={2 * (L // 3)}:h={th - 1}:color={col}:t=fill")
            draws.append(f"drawbox=x=w/2-1:y=h/2-{L // 3}:w={th - 1}:h={2 * (L // 3)}:color={col}:t=fill")

    tint = spec.get("tint")
    grade = {"danger": ",colorbalance=rs=0.35:gs=-0.12:bs=-0.15:rm=0.2,eq=saturation=1.15",
             "cold": ",colorbalance=bs=0.12:bm=0.08"}.get(tint, "")
    z0, z1 = spec.get("zoom", [1.0, 1.08])
    frames = max(int(round(dur * FPS)), 1)
    cam = (f"zoompan=z='{z0}+({z1}-{z0})*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
           f"d=1:s={OUT_W}x{OUT_H}:fps={FPS}")
    tail = (",".join(draws) + "," if draws else "") + f"format=yuv420p{grade},{cam},vignette=angle=PI/9," \
        f"trim=duration={dur:.3f},setsar=1[v]"
    chains.append(f"[{cur}]{tail}")

    script = work / f"{out.stem}.fg"
    script.write_text(";\n".join(chains), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                        "-filter_complex_script", str(script), "-map", "[v]", "-t", f"{dur:.3f}",
                        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise StageFailed("mograph ffmpeg failed:\n" + r.stderr[-2000:])
    return out

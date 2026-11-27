"""Generate mograph.yaml for the leopard seal video (55 shots).

Run from the repo root:  python topics/leopard_seal/build_mograph.py
Building blocks keep the shot list short and consistent; edit here, not in
the generated YAML.
"""
from pathlib import Path

import yaml

C = "images/cutouts/"
BG = "images/bg/"


def bg(name, **kw):
    return {"background": {"path": BG + name + ".png", **kw}}


def sub(name, width, frm, to=None, start=0.0, move=None, **kw):
    d = {"path": C + name + ".png", "width": width, "from": list(frm), "to": list(to or frm), "start": start}
    d["move"] = move if move is not None else (5.0 if to else 1.0)
    if to is None:
        d.setdefault("bob", kw.pop("bob", 0.003))
    d.update(kw)
    return d


def lab(text, start, y=0.14, x=0.5, size=48, accent=False, end=None, underline=True):
    d = {"text": text, "x": x, "y": y, "start": start, "size": size}
    if accent:
        d["accent"] = True
    if end is not None:
        d["end"] = end
    if not underline:
        d["underline"] = False
    return d


def shot(background, subjects=(), labels=(), zoom=(1.0, 1.08), rays=False, particles=True, **extra):
    d = dict(background)
    d.update({"rays": rays, "particles": particles, "zoom": list(zoom)})
    if subjects:
        d["subjects"] = list(subjects)
    if labels:
        d["labels"] = list(labels)
    d.update(extra)
    return d


def crowd(xs=(0.16, 0.22, 0.27, 0.32, 0.38, 0.43), y=0.47, width=0.045):
    out = []
    for i, x in enumerate(xs):
        out.append(sub("penguin", width * (0.92 + 0.08 * (i % 3)), (x, y + 0.004 * (i % 2)), start=0.1 * i,
                       bob=0.003, bob_period=1.6 + 0.3 * i, tilt=0.02, flip=(i % 3 == 1)))
    return out


def krill_swarm(n=10, start=0.3):
    out = []
    for i in range(n):
        x = 0.12 + (i * 0.083) % 0.78
        y = 0.25 + ((i * 37) % 50) / 100
        out.append(sub("krill", 0.06 + 0.02 * (i % 3), (x, y), (x + 0.05, y - 0.03), start=start + 0.15 * i,
                       move=8.0, bob=0.01, bob_period=1.2 + 0.2 * (i % 4), tilt=0.05))
    return out


S = {
    # ---- Cold open
    "s01_01": shot(bg("ice_edge"), crowd()),
    "s01_02": shot(bg("under_ice"), [sub("seal_silhouette", 0.42, (1.3, 0.80), (0.62, 0.78), start=3.0, move=6.0,
                                         opacity=0.6, bob=0.004)], zoom=(1.0, 1.10), rays=True),
    "s01_03": shot(bg("under_ice"), [sub("seal", 0.52, (-0.45, 0.56), (0.55, 0.52), start=0.2, move=5.0, bob=0.006)],
                   [lab("The top hunter of the Antarctic coast", 5.5)], rays=True),
    "s01_04": shot(bg("pack_ice"), [sub("seal_rest", 0.26, (0.74, 0.74))],
                   [lab("Leopard seal", 0.4, y=0.30, x=0.34, size=120, accent=True, underline=False),
                    lab("The hunter at the edge of the ice", 1.2, y=0.43, x=0.34, size=48)], zoom=(1.06, 1.0)),
    # ---- What is a leopard seal
    "s02_01": shot(bg("pack_ice"), [sub("seal_rest", 0.32, (0.52, 0.70))],
                   [lab("Hydrurga leptonyx", 1.2, accent=True, size=56), lab("A true seal: no ear flaps", 8.0, y=0.25)]),
    "s02_02": shot(bg("map"), labels=[lab("The pack ice around Antarctica", 1.0, y=0.92)],
                   markers=[{"x": 0.6, "y": 0.5, "label": "Antarctica", "start": 0.5}], particles=False,
                   zoom=(1.0, 1.15)),
    "s02_03": shot(bg("under_ice"), [sub("seal", 1.5, (0.75, 0.52), (0.32, 0.50), start=0.0, move=10.0, bob=0.003)],
                   [lab("Silver-gray coat", 1.5), lab("Dark, leopard-like spots", 5.0, y=0.25, accent=True)]),
    # ---- A giant with a twist
    "s03_01": shot(bg("deep"), [sub("seal", 0.62, (0.55, 0.60)), sub("diver", 0.30, (0.30, 0.28), bob=0.006, tilt=0.01)],
                   counters=[{"label": "Length", "from": 0, "to": 3.5, "decimals": True, "suffix": " m",
                              "x": 0.78, "y": 0.22, "start": 0.8, "duration": 3.0}],
                   labels=[lab("About 11 ft, up to ~half a ton", 5.0, y=0.90)]),
    "s03_02": shot(bg("pack_ice"), [sub("seal_rest", 0.40, (0.32, 0.72)), sub("seal_rest", 0.29, (0.74, 0.74), flip=True)],
                   [lab("Female", 1.0, y=0.92, x=0.32, size=42, accent=True), lab("Male", 1.6, y=0.92, x=0.74, size=42),
                    lab("The biggest are the females", 5.0, accent=True)]),
    "s03_03": shot(bg("deep"), [sub("seal", 1.7, (0.12, 0.55), (0.18, 0.54), move=10.0)],
                   [lab("Huge head, long snout", 1.5), lab("Almost reptile-like", 6.5, y=0.25, accent=True)],
                   zoom=(1.0, 1.12)),
    # ---- Built for speed
    "s04_01": shot(bg("under_ice"), [sub("seal", 0.55, (-0.5, 0.52), (1.5, 0.46), start=0.3, move=7.0, bob=0.012,
                                         bob_period=0.8)], [lab("Powered by long front flippers", 2.0)], rays=True),
    "s04_02": shot(bg("deep"), [sub("seal", 0.48, (-0.45, 0.38), (1.45, 0.34), start=0.0, move=5.0, end=5.5, bob=0.01),
                                sub("seal", 0.48, (1.45, 0.66), (-0.45, 0.62), start=6.0, move=5.5, bob=0.01)],
                   [lab("Fast. Flexible. Agile.", 2.5, accent=True)]),
    "s04_03": shot(bg("deep"), [sub("seal", 0.45, (0.25, 0.22), (0.62, 0.86), start=0.2, move=5.5, bob=0.004)],
                   [lab("Many minutes on a single breath", 1.5)]),
    # ---- Two mouths in one
    "s05_01": shot(bg("deep"), [sub("seal_jaws", 0.55, (0.62, 0.62), start=0.0, move=10.0, grow=[0.95, 1.05])],
                   [lab("Front: long canine teeth", 3.0, x=0.30, y=0.20, accent=True)]),
    "s05_02": shot({"background": {"top": "#1C2A33", "bottom": "#05090C", "glow": 0.6}},
                   [sub("seal_jaws", 0.70, (0.55, 0.60), start=0.0, move=12.0, grow=[1.0, 1.12])],
                   [lab("Back: three-pointed cheek teeth", 1.0, y=0.12), lab("They lock together like a strainer", 6.0,
                                                                              y=0.90, accent=True)],
                   zoom=(1.0, 1.10)),
    "s05_03": shot(bg("deep"), krill_swarm(), [lab("Krill: tiny shrimp-like animals", 2.0)]),
    "s05_04": shot(bg("deep"), [sub("whale_silhouette", 0.9, (1.5, 0.55), (-0.5, 0.52), start=0.0, move=9.0,
                                    opacity=0.45, bob=0.002)] + krill_swarm(7, 0.5),
                   [lab("One mouth, two ways to eat", 4.0, accent=True)]),
    # ---- The menu
    "s06_01": shot(bg("deep"), [sub("krill", 0.22, (0.28, 0.50), bob=0.01, tilt=0.04)],
                   [lab("Krill", 1.0, x=0.70, y=0.30, size=60, accent=True), lab("Fish", 4.5, x=0.70, y=0.47, size=60),
                    lab("Squid", 7.5, x=0.70, y=0.64, size=60)]),
    "s06_02": shot(bg("under_ice"), [sub("penguin_swim", 0.20, (-0.2, 0.30), (1.25, 0.26), start=0.2, move=5.0,
                                         bob=0.01, bob_period=0.6),
                                     sub("seal", 0.50, (-0.55, 0.74), (0.55, 0.70), start=0.8, move=5.5, bob=0.008)],
                   [lab("It only has to win once", 3.5, accent=True)], rays=True),
    "s06_03": shot(bg("deep"), [sub("crabeater", 0.50, (1.4, 0.52), (0.52, 0.50), start=0.2, move=5.0)],
                   [lab("Crabeater seals carry long scars", 2.5), lab("from leopard seal attacks", 6.0, y=0.25,
                                                                      accent=True)]),
    "s06_04": shot(bg("ice_edge"), [sub("seal_jaws", 0.40, (0.74, 0.70), start=0.2, move=1.0, bob=0.012,
                                        bob_period=0.45, tilt=0.06)],
                   [lab("Big prey is shaken into pieces", 2.0)], tint="danger"),
    # ---- Ambush at the ice edge
    "s07_01": shot(bg("ice_edge"), crowd() + [sub("seal_silhouette", 0.30, (0.74, 0.82), opacity=0.7, bob=0.004)],
                   [lab("Waiting at the ice edge", 1.5)]),
    "s07_02": shot(bg("ice_edge"), crowd(), [lab("To a penguin, the water looks empty", 2.5)], zoom=(1.06, 1.0)),
    "s07_03": shot(bg("under_ice"),
                   [sub("penguin_swim", 0.13, (0.20 + 0.12 * i, -0.10), (0.30 + 0.12 * i, 0.32 + 0.05 * (i % 2)),
                        start=0.4 + 0.25 * i, move=2.5, bob=0.008, bob_period=0.5) for i in range(5)]
                   + [sub("seal", 0.45, (1.4, 0.78), (0.80, 0.74), start=1.5, move=6.0)],
                   [lab("Safety in numbers", 4.5, accent=True)], rays=True),
    "s07_04": shot(bg("ice_edge"), [sub("penguin", 0.045, (0.47 - 0.05 * i, 0.64), (0.40 - 0.05 * i, 0.47),
                                        start=0.6 + 0.5 * i, move=0.8, bob=0.003) for i in range(4)],
                   [lab("Out of the water, fast", 3.5)]),
    # ---- Songs under the ice
    "s08_01": shot(bg("deep"), [sub("seal_silhouette", 0.40, (0.55, 0.62), opacity=0.5)],
                   [lab("Leopard seals sing", 0.4, y=0.30, size=84, accent=True, underline=False)]),
    "s08_02": shot(bg("deep"), [sub("seal", 0.50, (0.52, 0.55), bob=0.008, bob_period=4.0, tilt=0.03)],
                   [lab("Long, low, eerie calls", 2.0), lab("in the breeding season", 6.5, y=0.25, accent=True)]),
    "s08_03": shot(bg("pack_ice"), labels=[lab("Underwater microphones", 1.5), lab("Listening is how we find them",
                                                                                     6.0, y=0.25, accent=True)],
                   markers=[{"x": 0.42, "y": 0.72, "label": "Hydrophone", "start": 1.0}]),
    # ---- Life on the ice
    "s09_01": shot(bg("pack_ice"), [sub("seal_rest", 0.26, (0.62, 0.70))], [lab("Mostly loners", 1.5)]),
    "s09_02": shot(bg("pack_ice"), [sub("seal_rest", 0.32, (0.42, 0.70)), sub("pup", 0.15, (0.66, 0.75), start=0.6)],
                   [lab("Pups are born on the pack ice", 1.0), lab("Nursed for a few weeks", 4.5, y=0.25)]),
    "s09_03": shot(bg("deep"), [sub("orca", 0.55, (1.4, 0.50), (0.52, 0.46), start=0.2, move=4.5)],
                   [lab("Main natural enemy: killer whales", 2.0, accent=True)], tint="danger"),
    "s09_04": shot(bg("pack_ice"), [sub("seal_rest", 0.30, (0.50, 0.72), bob=0.002)], [lab("Can live 20+ years", 1.0)]),
    # ---- Meeting humans
    "s10_01": shot(bg("ship"), labels=[lab("1916: Shackleton's expedition", 1.0, accent=True),
                                       lab("Ship crushed, crew camped on the ice", 6.0, y=0.25)], particles=False),
    "s10_02": shot(bg("ship"), [sub("human", 0.035, (0.80, 0.78), (0.30, 0.78), start=0.2, move=6.0, bob=0.006,
                                    bob_period=0.4, flip=False),
                                sub("seal_jaws", 0.22, (0.62, 1.10), (0.62, 0.86), start=3.0, move=0.8, bob=0.006)],
                   [lab("Thomas Orde-Lees, chased across the ice", 1.0, size=44)], particles=False),
    "s10_03": shot(bg("under_ice"), [sub("diver", 0.28, (0.36, 0.48), bob=0.006, tilt=0.01),
                                     sub("seal", 0.40, (1.4, 0.78), (0.72, 0.74), start=1.0, move=7.0)],
                   [lab("Most encounters: curiosity", 3.5, accent=True)], rays=True),
    "s10_04": shot(bg("under_ice"), [sub("diver", 0.26, (0.26, 0.46), bob=0.006, tilt=0.01),
                                     sub("seal", 0.42, (0.78, 0.64), flip=True),
                                     sub("penguin_swim", 0.12, (0.66, 0.58), (0.44, 0.50), start=2.0, move=5.0,
                                         flip=True, opacity=0.95)],
                   [lab("She kept bringing him penguins", 3.0)], rays=True),
    "s10_05": shot(bg("station"), labels=[lab("Remembering Kirsty Brown", 4.0, y=0.86)], particles=False,
                   zoom=(1.0, 1.06)),
    "s10_06": shot(bg("station"), labels=[lab("The only known human death", 1.0),
                                          lab("Stricter safety rules followed", 6.0, y=0.25)], particles=False,
                   zoom=(1.06, 1.12)),
    # ---- Wanderers
    "s11_01": shot(bg("map"), particles=False, zoom=(1.0, 1.06),
                   markers=[{"x": 0.08, "y": 0.38, "label": "South America", "start": 2.2, "label_dx": 0.02},
                            {"x": 0.32, "y": 0.06, "label": "Africa", "start": 3.2},
                            {"x": 0.86, "y": 0.07, "label": "Australia & NZ", "start": 4.2, "label_dx": -0.24}],
                   paths=[{"points": [[0.6, 0.42], [0.36, 0.40], [0.08, 0.38]], "start": 0.4, "duration": 2.0},
                          {"points": [[0.6, 0.42], [0.45, 0.20], [0.32, 0.06]], "start": 1.2, "duration": 2.0},
                          {"points": [[0.6, 0.42], [0.76, 0.22], [0.86, 0.07]], "start": 2.0, "duration": 2.0}]),
    "s11_02": shot(bg("harbor"), [sub("seal_rest", 0.30, (0.46, 0.82))],
                   [lab("New Zealand: some now treated as residents", 3.0, size=44)], particles=False),
    "s11_03": shot(bg("harbor"), [sub("seal_rest", 0.26, (0.62, 0.84))],
                   [lab("Give it plenty of space", 1.0, accent=True), lab("Keep dogs well away", 4.0, y=0.25)],
                   particles=False, zoom=(1.06, 1.0)),
    # ---- How scientists study them
    "s12_01": shot(bg("pack_ice"), labels=[lab("Searching from boats, ships and aircraft", 2.0, size=44)],
                   zoom=(1.0, 1.12)),
    "s12_02": shot(bg("pack_ice"), [sub("seal_rest", 0.40, (0.50, 0.70))],
                   [lab("Falls off when the seal molts", 6.0, y=0.25)],
                   markers=[{"x": 0.30, "y": 0.62, "label": "Satellite tag", "start": 1.5, "label_dx": -0.20}]),
    "s12_03": shot(bg("under_ice"), [sub("seal", 0.55, (0.50, 0.52), bob=0.006)],
                   [lab("A seal's-eye view", 4.5, y=0.86, accent=True)],
                   markers=[{"x": 0.44, "y": 0.44, "label": "Tiny camera", "start": 1.0}], rays=True),
    "s12_04": shot({"background": {"top": "#2E2822", "bottom": "#0A0908", "glow": 0.7}},
                   [sub("krill", 0.18, (0.30, 0.55), bob=0.006), sub("penguin", 0.06, (0.68, 0.56), start=0.5)],
                   [lab("Bones, beaks, even DNA", 2.0, accent=True), lab("found in their droppings", 6.0, y=0.86)]),
    # ---- Myths and facts
    "s13_01": shot(bg("deep"), [sub("seal_silhouette", 0.42, (0.55, 0.66), opacity=0.55)],
                   [lab("Myths & facts", 0.3, y=0.32, size=96, accent=True, underline=False)]),
    "s13_02": shot(bg("under_ice"), [sub("seal", 0.44, (0.40, 0.62), bob=0.006),
                                     sub("penguin_swim", 0.14, (0.78, 0.34), bob=0.008)],
                   [lab("Myth: they mostly eat penguins", 0.8, size=44),
                    lab("Fact: the diet changes with season and place", 5.5, y=0.25, size=44, accent=True)], rays=True),
    "s13_03": shot(bg("under_ice"), [sub("diver", 0.26, (0.32, 0.50), bob=0.006),
                                     sub("seal", 0.40, (1.3, 0.76), (0.72, 0.72), start=0.5, move=6.0)],
                   [lab("Myth: every approach is an attack", 0.8, size=44),
                    lab("Fact: most are curious", 5.5, y=0.25, size=44, accent=True)], rays=True),
    "s13_04": shot(bg("pack_ice"), [sub("seal_rest", 0.30, (0.28, 0.73)), sub("polar_bear", 0.24, (0.74, 0.70),
                                                                               opacity=0.6, flip=True)],
                   [lab("Antarctic", 2.0, x=0.28, y=0.92, size=42), lab("Arctic", 3.5, x=0.74, y=0.92, size=42),
                    lab("They never meet", 7.0, accent=True)]),
    # ---- A changing ice
    "s14_01": shot(bg("pack_ice"), labels=[lab("They need the sea ice", 2.0, accent=True)], zoom=(1.0, 1.15)),
    "s14_02": shot(bg("map"), labels=[lab("Some record-low sea ice in recent years", 2.0, y=0.92, size=44)],
                   particles=False, tint="cold", zoom=(1.0, 1.10)),
    "s14_03": shot(bg("pack_ice"), [sub("seal_rest", 0.14, (0.30, 0.72)), sub("seal_rest", 0.12, (0.58, 0.80),
                                                                               start=0.6, flip=True),
                                    sub("seal_rest", 0.10, (0.80, 0.68), start=1.2)],
                   [lab("Nobody knows exactly how many", 2.0), lab("They're hard to count", 6.5, y=0.25,
                                                                     accent=True)]),
    # ---- Outro
    "s15_01": shot(bg("ice_edge"), crowd(xs=(0.16, 0.22, 0.27, 0.32, 0.38))
                   + [sub("penguin", 0.045, (0.44, 0.47), (0.53, 0.66), start=3.0, move=1.2)],
                   [lab("Not shy. Smart.", 5.0, accent=True, size=60)]),
    "s15_02": shot(bg("deep"), [sub("seal", 0.50, (0.40, 0.52), (1.45, 0.62), start=0.5, move=6.5)],
                   [lab("A brilliant, flexible hunter", 2.0)]),
    "s15_03": shot(bg("ice_edge"), crowd(), [lab("Which animal next?", 0.4, y=0.26, size=90, accent=True,
                                                 underline=False),
                                             lab("Tell us in the comments", 1.4, y=0.38, size=48)], zoom=(1.04, 1.0)),
}

out = Path(__file__).with_name("mograph.yaml")
header = ("# Generated by build_mograph.py; edit that file, not this one.\n"
          "# Leopard seal: every shot is layered motion graphics.\n")
out.write_text(header + yaml.safe_dump({"shots": S}, sort_keys=False, width=120), encoding="utf-8")
print(f"wrote {len(S)} shots to {out}")

"""
build_sequences.py — pack each animated sequence into one file the page loads: viz_d3/sequences/<key>.json.

Run (from anywhere):   python viz_d3/build_sequences.py
Rerun after the frames or eyes.json change in SVG/sheet_tools (trace_frames.py / eyes_json.py).

A sequence's frames are traced one SVG per frame (eyeless, in kit units) plus eyes.json, the eye track.
The page needs them all before it can play, so this joins them into one file, with coordinates rounded to
one decimal (a tenth of a kit unit; invisible at any size the cats are drawn), styles and ids dropped, and
only the eye-track fields the page reads. Each cream shape is marked as muzzle (r-muzzle) or chest (r-chest),
so a cat's white muzzle and white bib can show while it plays. Frames with the drawing's own shut eyes
(frame_NNNNN_drawnshut.svg, from trace_frames.py --keep-shut) go in too, under "drawnShut".
Which of those the page shows, and other hand fixes, are set in SEQUENCES in js/config.js.
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "sequences")

# key (as in SEQUENCES in js/config.js): (folder of traced frames, frames per second)
SOURCES = {
    "grooming": ("SVG/sheet_tools/out/grooming_wan/svg", 12),
    "headTurn": ("SVG/sheet_tools/out/head_turn_wan/svg", 12),
}
NUM = re.compile(r"-?\d+\.\d+")


PAIR = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


def tag_cream(g, to_kit, eyes):
    """Mark each cream shape as the muzzle (r-muzzle), the chest (r-chest) or inside the ears (r-head-cream), so a
    cat's white muzzle and white bib can each be drawn white. Ear cream is above the eyes; the muzzle is the
    cream shape under the eyes, between them, at most about 1.6 eye spacings tall; everything else is chest."""
    if not eyes:
        return g
    s, tx, ty = to_kit
    L, R = eyes["left"], eyes["right"]
    sp = max(1.0, ((R["cx"] - L["cx"]) ** 2 + (R["cy"] - L["cy"]) ** 2) ** 0.5)
    ey, x0, x1 = (L["cy"] + R["cy"]) / 2, min(L["cx"], R["cx"]) - 0.3 * sp, max(L["cx"], R["cx"]) + 0.3 * sp

    def one(m):
        pts = [(float(a) * s + tx, float(b) * s + ty) for a, b in PAIR.findall(m.group(1))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        cx, cy, h = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(ys) - min(ys)
        if cy < ey:
            kind = "r-head-cream"                      # inside the ears, above the eyes: never turns white
        elif x0 <= cx <= x1 and cy < ey + 1.8 * sp and h < 1.6 * sp:
            kind = "r-muzzle"
        else:
            kind = "r-chest"
        return f'<path class="{kind}" d="{m.group(1)}"'

    def group(m):
        return re.sub(r'<path d="([^"]*)"', one, m.group(0))
    return re.sub(r'<g class="r-cream">.*?</g>', group, g, flags=re.S)


def frame_markup(path, to_kit=None, eyes=None):
    """The frame's drawing as one <g> (its to-kit matrix kept), compact."""
    text = open(path, encoding="utf-8").read()
    g = re.search(r"<g\b[^>]*>.*</g>", text, re.S).group(0)
    g = re.sub(r"<defs>.*?</defs>", "", g, flags=re.S)
    g = re.sub(r"<!--.*?-->", "", g, flags=re.S)
    g = re.sub(r'\s(id)="[^"]*"', "", g)
    g = re.sub(r'(<path d=")([^"]*)"', lambda m: m.group(1) + NUM.sub(lambda n: f"{float(n.group()):.1f}".rstrip("0").rstrip("."), m.group(2)) + '"', g)
    g = re.sub(r">\s+<", "><", g).strip()
    return tag_cream(g, to_kit, eyes)


def eye(e):
    s = e["smooth"]
    return {"cx": s["cx"], "cy": s["cy"], "w": s["w"], "h": s["h"], "angle": s["angle"],
            "visible": e["visible"], "lid": e["lid"], "gaze_x": e["gaze_x"], "gaze_y": e["gaze_y"]}


def main():
    os.makedirs(OUT, exist_ok=True)
    for key, (folder, fps) in SOURCES.items():
        d = os.path.join(ROOT, folder)
        files = sorted(glob.glob(os.path.join(d, "frame_[0-9][0-9][0-9][0-9][0-9].svg")))
        track = json.load(open(os.path.join(d, "eyes.json"), encoding="utf-8"))
        to_kit = track["to_kit"]
        smooth = {f["frame"]: {k: f[k]["smooth"] for k in ("left", "right")} for f in track["frames"]}
        shut = {}
        for f in sorted(glob.glob(os.path.join(d, "frame_*_drawnshut.svg"))):
            n = int(re.search(r"frame_(\d+)_", f).group(1))
            shut[n] = frame_markup(f, to_kit, smooth.get(n))
        frames = [{"frame": f["frame"], "keyframe": f["keyframe"], "left": eye(f["left"]), "right": eye(f["right"])}
                  for f in track["frames"]]
        if len(frames) != len(files):
            raise SystemExit(f"{key}: {len(files)} frame files but {len(frames)} frames in eyes.json")
        out = {"key": key, "fps": fps, "source": folder, "units": track["units"],
               "frames": [frame_markup(f, to_kit, smooth.get(i + 1)) for i, f in enumerate(files)],
               "drawnShut": shut, "track": frames}
        path = os.path.join(OUT, key + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, separators=(",", ":"))
        print(f"{key}: {len(files)} frames ({len(shut)} drawn-shut) -> {os.path.relpath(path, ROOT)}, "
              f"{os.path.getsize(path) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

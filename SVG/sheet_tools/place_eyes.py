"""Put the kit's eye sets on traced frames, where each frame's drawing had its eyes (cues.json from sheet_frames.py).

Usage:  python3 place_eyes.py FRAMES_DIR KIT.svg --set round [--front 3] [--out FRAMES_DIR]

Each kit eye set is split into its left and right eye. For every frame and eye:
  - position: the centre of the drawn eye;
  - size: one scale for the whole sheet, set so the kit's eyes are as far apart as the drawn eyes on the
    front-facing frame (--front);
  - shape: the eye is narrowed or squashed by how much the drawn eye is narrower or shorter than the same eye
    on the front frame (so the far eye narrows as the head turns, and an eye closing flattens), which keeps the
    eye set's own style;
  - tilt: the eyes turn with the line between them, against the front frame (a tilted head tilts its eyes).
Frames with eyes shut get no eyes (their drawn closed eyes are kept in the trace). A frame whose cue has a "lid"
(trace_frames.py: the frames easing into and out of a drawn blink) gets it as data-lid on the eyes group, for the viz
to close the kit eyes' lids that far (blink.js closeEyes).
Writes frame_NN_<set>.svg next to the frames.
"""
import argparse, json, os, re, sys
import numpy as np
from svgelements import SVG, Path, Shape, Group

OLD_ANCHOR_X = 93.7      # the kit's eye sets are drawn as a pair either side of this x (old kit units)


def eye_set(kit_text, name):
    """The named eye set, split into left and right eyes: lists of (class, path d) in old kit units."""
    i = kit_text.index('<g class="eye-sets"')
    j = kit_text.index(">", i) + 1
    m = re.search(rf'<g class="eyes" data-set="{name}"', kit_text[j:])
    start = j + m.start()
    depth, k = 0, start
    while True:                                       # find the end of this set's group
        a, b = kit_text.find("<g", k), kit_text.find("</g>", k)
        if a != -1 and a < b:
            depth += 1; k = a + 2
        else:
            depth -= 1; k = b + 4
            if depth == 0:
                break
    block = kit_text[start:k]
    doc = SVG.parse(__import__("io").StringIO(f'<svg xmlns="http://www.w3.org/2000/svg">{block}</svg>'), reify=True)
    sides = {"left": [], "right": []}
    for el in doc.elements():
        if not isinstance(el, Shape):
            continue
        cls = el.values.get("class", "")
        rule = el.values.get("fill-rule", "nonzero")
        p = Path(el)
        p.reify()
        # keep each eye's pieces of this shape together in one path, so holes (an outline's inside) stay holes
        parts = {"left": [], "right": []}
        for sp in p.as_subpaths():
            sp = Path(sp)
            bb = sp.bbox()
            if bb:
                parts["left" if (bb[0] + bb[2]) / 2 < OLD_ANCHOR_X else "right"].append((sp, bb))
        for side, items in parts.items():
            if items:
                bb = (min(b[0] for _, b in items), min(b[1] for _, b in items),
                      max(b[2] for _, b in items), max(b[3] for _, b in items))
                d = " ".join(sp.d() for sp, _ in items)
                sides[side].append(("k-eye-white" if "eye-white" in cls else "k-eye-line", d, bb, rule))
    return sides


def box(items):
    b = np.array([it[2] for it in items])
    return b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("kit")
    ap.add_argument("--set", default="round")
    ap.add_argument("--front", type=int, default=3)
    a = ap.parse_args()
    cues = json.load(open(os.path.join(a.frames, "cues.json")))
    sides = eye_set(open(a.kit, encoding="utf-8").read(), a.set)
    old = {s: box(v) for s, v in sides.items()}
    old_c = {s: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for s, b in old.items()}
    front = next(f for f in cues["frames"] if f["frame"] == a.front)
    if len(front["eyes"]) < 2:
        sys.exit(f"front frame {a.front} has {len(front['eyes'])} eyes detected - pick a frontal frame with both eyes detected")
    fl, fr = front["eyes"]
    scale = (fr["x"] - fl["x"]) / (old_c["right"][0] - old_c["left"][0])
    front_tilt = np.degrees(np.arctan2(fr["y"] - fl["y"], fr["x"] - fl["x"]))
    if abs(front_tilt) > 15:
        print(f"WARNING: front frame {a.front} eyes tilted {front_tilt:.0f} deg - pick a frontal frame with both eyes detected", file=sys.stderr)
    for f in cues["frames"]:
        svg = open(os.path.join(a.frames, f["file"])).read()
        eyes_svg = ""
        if not f["eyes_closed"]:
            el, er = f["eyes"]
            tilt = np.degrees(np.arctan2(er["y"] - el["y"], er["x"] - el["x"])) - front_tilt
            for side, e, fe in (("left", el, fl), ("right", er, fr)):
                sx = scale * e["w"] / fe["w"]
                sy = scale * e["h"] / fe["h"]
                ox, oy = old_c[side]
                tf = f"translate({e['x']},{e['y']}) rotate({tilt:.1f}) scale({sx:.3f},{sy:.3f}) translate({-ox:.2f},{-oy:.2f})"
                paths = "".join(f'<path class="{c}" fill-rule="{r}" d="{d}"/>' for c, d, _, r in sides[side])
                eyes_svg += f'  <g class="kit-eye kit-eye-{side}" transform="{tf}">{paths}</g>\n'
        css = ("<style>.k-eye-white{fill:var(--cat-eye-white,#fff)}"
               ".k-eye-line{fill:var(--cat-outline,#462E29)}</style>")
        lid = f' data-lid="{f["lid"]}"' if f.get("lid") else ""     # trace_frames.py: lids part-closed near a drawn blink
        group = f'  <g id="eyes" data-set="{a.set}"{lid}>{css}\n{eyes_svg}  </g>\n'
        # frames wrapped into kit units by eyes_json.py: the eyes go inside the wrapper, in frame pixels like the cues
        out = svg.replace("<!--kit-eyes-->", group) if "<!--kit-eyes-->" in svg else svg.replace("</svg>", group + "</svg>")
        name = f["file"].replace(".svg", f"_{a.set}.svg")
        open(os.path.join(a.frames, name), "w").write(out)
    print(f"placed '{a.set}' eyes on {len(cues['frames'])} frames (scale {scale:.2f} px per kit unit)")


if __name__ == "__main__":
    main()

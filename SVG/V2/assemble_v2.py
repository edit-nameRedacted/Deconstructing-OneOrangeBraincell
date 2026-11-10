"""Assemble the hand-drawn V2 cat parts (SVG/V2/SVG/*.svg) into one layered, recolourable SVG.

Usage (from SVG/V2/):  python3 assemble_v2.py SVG cat_v2.svg

Each part was exported from Illustrator cropped to its own contents, so the files share a scale (1 unit = 1 unit)
but not an origin. PLACE below says where each part's origin goes on the outline, and how that was found:
  - ear shading: shifted until its edge best followed the inside of the outline's ears (chamfer fit, 0.25-unit steps)
  - ear lines:   shifted until they best filled the white gaps left in the ear shading (same fit)
  - face stripes: from the ear lines, by a stray speck of the trace that both files contain at the same spot
  - body stripes: shifted to stay inside the body, with their outer ends on the outline
  - chest fluff, nose and mouth: placed by eye on the face's centre line (nothing in the files ties them down)
mouth 2 is mouth 1 with a wider mouth; its nose is the same drawing 2.9 units further right in its file.

The coat is not one of the parts: it is the outline's inside, found by closing the small gaps in the line work,
filling from outside, and tracing the result.

Layers, bottom to top: coat, body stripes, face stripes, ear shading, chest fluff, outline (with whiskers),
ear lines, mouth. <svg> attributes switch parts on and off:
  data-stripes  on | off      data-ears  on | off      data-fluff  on | off      data-mouth  1 | 2
Colours are CSS variables, defaulting to the colours the parts were drawn in.
"""
import os, re, sys
import numpy as np
import cv2
from svgelements import Path
from playwright.sync_api import sync_playwright

PLACE = {                                   # file: (x, y) of its origin on the outline
    "outline 1.svg": (0, 0),
    "stripe pattern 1.svg": (7.25, 149.5),
    "face stripe pattern 1.svg": (14.18, 28.16),
    "ear 1 shading.svg": (23.75, -0.25),
    "fluff 1.svg": (21.6, 141),            # lowered to match the reference render (2026-11-04)
    "ears 1.svg": (29.75, 3.25),
    "mouth 1.svg": (51.5, 98),
    "mouth 2.svg": (51.5 - 2.9, 98),
}
LAYERS = [  # (layer class, file)
    ("v2-stripes", "stripe pattern 1.svg"),
    ("v2-face-stripes", "face stripe pattern 1.svg"),
    ("v2-ear-shading", "ear 1 shading.svg"),
    ("v2-fluff", "fluff 1.svg"),
    ("v2-outline", "outline 1.svg"),
    ("v2-ear-lines", "ears 1.svg"),
    ("v2-mouth v2-mouth-1", "mouth 1.svg"),
    ("v2-mouth v2-mouth-2", "mouth 2.svg"),
]
# the colours the parts were drawn in -> a role each, so they can be recoloured together
ROLES = {"#462e29": "line", "#3c2415": "line-dark", "#603913": "line-mid", "#d78e34": "coat", "#9d5224": "stripe",
         "#f5dab5": "cream", "#c1886a": "ear", "#f5f4f3": "white"}
SPECK = 1.0          # elements smaller than this (in both directions) are stray bits of the trace, and dropped
R, X0, Y0, W, H = 4, -20, -20, 220, 400   # raster used to find the coat


def elements(path):
    s = open(path, encoding="utf-8").read()
    cols = {k: v.lower() for k, v in re.findall(r"\.(cls-\d+)\s*\{\s*fill:\s*(#[0-9a-fA-F]+)", s)}
    out = []
    for e in re.findall(r"<(?:path|polygon|rect)[^>]*/>", s):
        role = ROLES[cols[re.search(r'class="(cls-\d+)"', e).group(1)]]
        if e.startswith("<path"):
            bb = Path(re.search(r' d="([^"]+)"', e).group(1)).bbox()
            if bb and bb[2] - bb[0] < SPECK and bb[3] - bb[1] < SPECK:
                continue
        else:
            continue                                   # the rects and polygons in these files are all specks
        out.append(re.sub(r'class="cls-\d+"', f'class="r-{role}"', e))
    return out


def coat_path(outline_elems):
    g = "".join(e.replace('class="r-line"', 'fill="#000"') for e in outline_elems if 'r-line"' in e)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{X0} {Y0} {W} {H}" width="{W * R}" height="{H * R}" '
           f'style="display:block">{g}</svg>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W * R, "height": H * R})
        pg.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
        b.close()
    lines = (img < 128).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))      # closes gaps up to ~5 units
    fence = cv2.dilate(lines, k) * 255
    mask = np.zeros((fence.shape[0] + 2, fence.shape[1] + 2), np.uint8)
    cv2.floodFill(fence, mask, (0, 0), 128)                         # everything reachable from outside
    inside = cv2.erode((fence != 128).astype(np.uint8), k)
    inside = cv2.dilate(inside, np.ones((5, 5), np.uint8))          # reach the middle of the outline stroke
    cs, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 1.2, True)[:, 0, :] / R + [X0, Y0]
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in c) + " Z"


def main():
    src, out = sys.argv[1:3]
    parts = {f: elements(os.path.join(src, f)) for f in PLACE}
    coat = coat_path(parts["outline 1.svg"])
    body = [f'  <path class="r-coat v2-coat" d="{coat}"/>']
    for cls, f in LAYERS:
        x, y = PLACE[f]
        body.append(f'  <g class="{cls}" transform="translate({x},{y})">\n    ' + "\n    ".join(parts[f]) + "\n  </g>")
    var = lambda role, hexv: f".r-{role} {{ fill: var(--v2-{role}, {hexv}); }}"
    css = "\n".join("    " + var(role, hexv) for hexv, role in ROLES.items())
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -4 186 368" id="cat-v2" data-stripes="on" data-ears="on" data-fluff="on" data-mouth="1">
  <defs>
    <style>
{css}
    #cat-v2[data-stripes="off"] .v2-stripes, #cat-v2[data-stripes="off"] .v2-face-stripes {{ display: none; }}
    #cat-v2[data-ears="off"] .v2-ear-shading, #cat-v2[data-ears="off"] .v2-ear-lines {{ display: none; }}
    #cat-v2[data-fluff="off"] .v2-fluff {{ display: none; }}
    .v2-mouth {{ display: none; }}
    #cat-v2[data-mouth="1"] .v2-mouth-1, #cat-v2[data-mouth="2"] .v2-mouth-2 {{ display: inline; }}
    </style>
  </defs>
{chr(10).join(body)}
</svg>
'''
    open(out, "w", encoding="utf-8").write(svg)
    print(f"wrote {out} ({len(svg) // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()

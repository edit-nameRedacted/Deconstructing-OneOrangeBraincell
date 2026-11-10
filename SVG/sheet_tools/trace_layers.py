"""Trace a flat-colour cat drawing (JPG/PNG) into a layered SVG: one group per colour role.

Usage:  python3 trace_layers.py INPUT [INPUT ...] --out OUTDIR [--line-min 2.5 --line-max 6 --speck 40]

What it does, per image:
  1. Sorts every pixel into a role by its nearest reference colour (ROLES below): line, coat, stripe, cream,
     ear, nose, white. The background is the near-white area connected to the image's edge.
  2. Cleans up: anti-aliased halos around the lines and specks smaller than --speck pixels are handed to
     whichever colour surrounds them. Each colour also continues under the lines, so the fills have no gaps.
  3. Optionally (--open-bottom) drops the outline along the bottom edge, for heads that sit on a body.
  4. Evens out the line work (optional): lines are thinned to their centre and redrawn with each point's
     width clamped between --line-min and --line-max pixels, so thin wisps thicken and blobs slim, but the
     brush taper in between is kept.
  4. Traces each role separately (vtracer) and writes one SVG with a <g> per role, classes r-<role>, on the
     image's full canvas, so files cut from the same canvas stay lined up with each other.
Colours are CSS variables (--r-<role>) with the reference colours as defaults.
"""
import argparse, os, re, sys, tempfile
import numpy as np
import cv2
import vtracer
from skimage.morphology import skeletonize

ROLES = {   # role: reference colour (AC's V2 kit colours)
    "line": "#462E29", "coat": "#D78E34", "stripe": "#9D5224", "cream": "#F5DAB5",
    "ear": "#C1886A", "nose": "#CF9389", "white": "#F5F4F3",
}
ORDER = ["coat", "stripe", "ear", "cream", "white", "nose", "line"]   # bottom to top
BG = -1


def lab(hexes):
    rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in hexes], np.uint8)[None]
    return cv2.cvtColor(rgb[:, :, ::-1], cv2.COLOR_BGR2LAB)[0].astype(np.float32)


def classify(img):
    """Label map: index into ROLES order, or BG."""
    names = list(ROLES)
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    ref = lab(ROLES.values())
    d = ((L[:, :, None, :] - ref[None, None]) ** 2).sum(-1)
    labels = d.argmin(-1).astype(np.int16)
    # background: near-white pixels connected to the image edge
    white_like = (labels == names.index("white")).astype(np.uint8)
    n, comp = cv2.connectedComponents(white_like)
    edge = set(np.unique(np.concatenate([comp[0], comp[-1], comp[:, 0], comp[:, -1]]))) - {0}
    labels[np.isin(comp, list(edge))] = BG
    return labels


def clean(labels, speck, halo=2):
    """Hand halos and specks to their surroundings; extend fills under the lines."""
    names = list(ROLES)
    li = names.index("line")
    line = labels == li
    unknown = cv2.dilate(line.astype(np.uint8), np.ones((2 * halo + 1,) * 2, np.uint8)).astype(bool) & ~line
    for r in range(len(names)):                      # specks of any colour (lines included)
        n, comp, stats, _ = cv2.connectedComponentsWithStats((labels == r).astype(np.uint8), 8)
        small = np.where(stats[1:, cv2.CC_STAT_AREA] < speck)[0] + 1
        unknown |= np.isin(comp, small)
    line &= ~unknown
    known = ~unknown & ~line & (labels != BG)
    # fills: every pixel inside the cat takes the nearest known fill colour (so fills run under the lines)
    _, idx = cv2.distanceTransformWithLabels((~known).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(known)
    lut = np.zeros(idx.max() + 1, np.int16)
    lut[idx[ys, xs]] = labels[ys, xs]
    fills = lut[idx]
    inside = labels != BG
    inside = cv2.morphologyEx(inside.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    fills[~inside] = BG
    return fills, line


def even_lines(line, wmin, wmax):
    """Redraw the lines along their centre, each point's width clamped to [wmin, wmax] px."""
    if wmax <= 0:
        return line
    dist = cv2.distanceTransform(line.astype(np.uint8), cv2.DIST_L2, 5)
    sk = skeletonize(line)
    r = np.clip(dist * 2, wmin, wmax) / 2              # half-widths along the centre line
    out = np.zeros(line.shape, np.uint8)
    for rad in np.unique(np.round(r[sk] * 2) / 2):      # one pass per half-pixel radius
        seeds = (sk & (np.abs(r - rad) <= 0.25)).astype(np.uint8)
        k = int(np.ceil(rad)) * 2 + 1
        disk = np.zeros((k, k), np.uint8)
        cv2.circle(disk, (k // 2, k // 2), max(1, int(round(rad))), 1, -1)
        out |= cv2.dilate(seeds, disk)
    return out.astype(bool)


def open_bottom(line, sil, band, reach=14):
    """Drop the outline along the drawing's bottom edge (a head that will sit on a body has no line under its
    neck). A line pixel goes if the drawing ends just below it but continues just above it, within the lowest
    share `band` of the drawing's height (so whiskers and the chin are left alone)."""
    ys = np.nonzero(sil)[0]
    limit = ys.max() - band * (ys.max() - ys.min())
    below = np.zeros_like(sil); below[:-reach] = sil[reach:]
    above = np.zeros_like(sil); above[reach:] = sil[:-reach]
    rows = np.arange(sil.shape[0])[:, None] > limit
    return line & ~(~below & above & rows)


def trace(mask, tmp):
    """Binary mask -> list of path d strings (absolute, in pixels)."""
    if mask.sum() == 0:
        return []
    src, dst = os.path.join(tmp, "m.png"), os.path.join(tmp, "m.svg")
    cv2.imwrite(src, np.where(mask, 0, 255).astype(np.uint8))
    vtracer.convert_image_to_svg_py(src, dst, colormode="binary", mode="spline", filter_speckle=4,
                                    corner_threshold=60, length_threshold=4.0, splice_threshold=45,
                                    path_precision=2)
    svg = open(dst).read()
    out = []
    for el in re.findall(r"<path[^>]*/>", svg):
        d = re.search(r'd="([^"]+)"', el).group(1)
        t = re.search(r'translate\(([-\d.]+),([-\d.]+)\)', el)
        tx, ty = (float(t.group(1)), float(t.group(2))) if t else (0.0, 0.0)
        if tx or ty:
            d = re.sub(r"(-?[\d.]+)[ ,](-?[\d.]+)", lambda q: f"{float(q.group(1)) + tx:.2f},{float(q.group(2)) + ty:.2f}", d)
        out.append(d)
    return out


def process(path, outdir, args):
    img = cv2.imread(path)
    labels = classify(img)
    fills, line = clean(labels, args.speck)
    line = even_lines(line, args.line_min, args.line_max)
    if getattr(args, "open_bottom", 0):
        line = open_bottom(line, fills != BG, args.open_bottom)
    names = list(ROLES)
    h, w = img.shape[:2]
    groups = []
    with tempfile.TemporaryDirectory() as tmp:
        for role in ORDER:
            if role == "line":
                mask = line
            elif role == "coat":
                mask = fills != BG                     # the coat is the whole silhouette: no gaps under anything
            else:
                mask = fills == names.index(role)
            ds = trace(mask, tmp)
            if ds:
                groups.append(f'  <g id="{role}" class="r-{role}">\n' + "\n".join(f'    <path d="{d}"/>' for d in ds) + "\n  </g>")
            print(f"  {role}: {len(ds)} shapes", file=sys.stderr)
    css = "\n".join(f"    .r-{r} {{ fill: var(--r-{r}, {c}); fill-rule: evenodd; }}" for r, c in ROLES.items())
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">\n  <defs><style>\n{css}\n  </style></defs>\n'
           + "\n".join(groups) + "\n</svg>\n")
    out = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + ".svg")
    open(out, "w").write(svg)
    print(f"wrote {out} ({len(svg) // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--line-min", type=float, default=0, help="thinnest line, px (0 with --line-max 0 = leave lines as drawn)")
    ap.add_argument("--line-max", type=float, default=0, help="thickest line, px")
    ap.add_argument("--speck", type=int, default=40, help="smallest kept shape, px area")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for p in a.inputs:
        print(p, file=sys.stderr)
        process(p, a.out, a)

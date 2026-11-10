"""Build the cat kit (SVG/cat_kit.svg) from AC's V2 parts: four bodies, white zones, eye sets, coats, ears.

Usage (from SVG/V2/):  python3 build_kit_v2.py SVG ../cat_kit.svg ../cat_kit.svg
  arg 1: the folder of V2 parts       arg 2: the kit to take the eye sets from       arg 3: where to write

V2 is one front-facing drawing (assemble_v2.py places its parts). The four bodies the viz uses are made from it:
  typical  the drawing itself
  slender  narrower and a little taller below the neck, head 4% smaller
  chunky   wider and a little shorter below the neck, head 4% larger
  kitten   much smaller body, with a head that is large for it
Each body is a warp of the drawing: the head is scaled evenly (so the face is never squashed) about the neck,
the body is scaled across about its middle and up from the floor, and the two blend over the neck. Every part
(outline, stripes, fluff, ears, mouth, white zones) goes through the same warp, so they stay in register.

The page reads the kit exactly as before (see viz_d3/js/kit.js): one <g class="body" data-body=...> per body,
white zones .w-zone.w-<name>, eye sets .eyes[data-set], the outline in .outline, colours as --cat-* variables,
and the <svg> attributes that pick what shows:
  data-body     typical | kitten | slender | chunky
  data-white    white zones by name, e.g. "chin locket paws"
  data-eyes     one eye set: original | almond | squint | big-shiny | slit | half-lidded | round
  data-stripes  on | off
  data-coat     classic | high-contrast | soft                  (classic = the colours AC drew V2 in)
  data-ears     tufted | plain                                  (tufted = AC's ear shading and lines)
  data-cream    on | off       the cream chest bib and muzzle
  data-fluff    on | off       the fluff lines on the chest
  data-mouth    1 | 2          AC's two mouths
  data-fur      off | on       fur-textured edges on the white zones
The eye sets are lifted unchanged from the previous kit and placed on the V2 face where AC's reference render
puts the eyes. Kit units are V2 units x KIT_SCALE (the old kit's size, so the tail and the row keep their scale).
"""
import os, re, sys
import numpy as np
import cv2
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from svgelements import Path, Move, Line, CubicBezier, QuadraticBezier, Close, Arc
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_v2 import PLACE, elements, coat_path    # noqa: E402

KIT_SCALE = 1.35          # V2 units -> kit units
NECK_Y, FLOOR_Y = 130, 358
HEAD_X, BODY_X = 60.5, 86  # the head scales about the nose line, the body about its middle
BODIES = {                 # head scale, body scale across, body scale up
    "typical": (1.00, 1.00, 1.00),
    "kitten": (0.80, 0.64, 0.60),
    "slender": (0.96, 0.84, 1.03),
    "chunky": (1.04, 1.27, 0.96),
}
BODY_CENTRE = (115, 380)   # tail.js needs one point inside every body (kit units); checked on each build
LABELS = {"typical": "Typical", "kitten": "Kitten", "slender": "Slender", "chunky": "Chunky"}

# Eyes: where AC's reference render puts them on V2 (the midpoint between the eyes), and how the old eye sets
# (drawn around OLD_EYE_ANCHOR, about 65 old units apart) scale to the reference's 47 V2 units apart, then
# 12% larger, which matches the size of the reference's eyes.
EYE_ANCHOR_V2 = (60.6, 83.1)
OLD_EYE_ANCHOR = (93.7, 97.7)
EYE_SCALE_V2 = 47 / 65 * 1.12

# Colours AC drew V2 in (classic), and the coat variants, from the palette sampled from the reference sheet.
CLASSIC = {"coat": "#D78E34", "stripes": "#9D5224", "outline": "#462E29", "white": "#F5F4F3", "cream": "#F5DAB5",
           "ear": "#C1886A", "nose": "#CF9389", "eye-white": "#FFFFFF", "glow": "#FCD9AF"}
COATS = {
    "high-contrast": {"coat": "#C37825", "stripes": "#6B3B13", "ear": "#9A662D"},
    "soft": {"coat": "#BB9063", "stripes": "#BE7643", "white": "#FCD9AF", "cream": "#F1E7DB"},
}

rng = np.random.default_rng(7)


# ------------------------------------------------------------------------------------------- the warp
def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def make_warp(hs, sx, sy):
    """V2 point(s) -> kit point(s) for one body."""
    def body(x, y):
        return BODY_X + (x - BODY_X) * sx, FLOOR_Y + (y - FLOOR_Y) * sy
    nbx, nby = body(HEAD_X, NECK_Y)                    # where the neck lands on the body

    def warp(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        bx, by = body(x, y)
        hx, hy = nbx + (x - HEAD_X) * hs, nby + (y - NECK_Y) * hs
        w = 1 - smooth((y - (NECK_Y - 15)) / 35)      # 1 on the head, 0 below the neck
        return KIT_SCALE * (w * hx + (1 - w) * bx), KIT_SCALE * (w * hy + (1 - w) * by)
    return warp


def warp_d(d, warp, tx=0.0, ty=0.0):
    """Path data (in a part's own units, placed at tx, ty) -> warped, absolute path data."""
    p = Path(d)
    p.approximate_arcs_with_cubics()
    out = []

    def f(*pts):
        xs, ys = warp([q.x + tx for q in pts], [q.y + ty for q in pts])
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in zip(np.atleast_1d(xs), np.atleast_1d(ys)))
    for seg in p:
        if isinstance(seg, Move):
            out.append("M" + f(seg.end))
        elif isinstance(seg, Close):
            out.append("Z")
        elif isinstance(seg, Line):
            out.append("L" + f(seg.end))
        elif isinstance(seg, CubicBezier):
            out.append("C" + f(seg.control1, seg.control2, seg.end))
        elif isinstance(seg, QuadraticBezier):
            out.append("Q" + f(seg.control, seg.end))
    return " ".join(out)


def d_of(el):
    return re.search(r' d="([^"]+)"', el).group(1)


# ------------------------------------------------------------------------------------------- shape helpers
def catmull(pts, closed=True):
    pts = np.asarray(pts, float)
    n = len(pts)
    get = (lambda i: pts[i % n]) if closed else (lambda i: pts[min(max(i, 0), n - 1)])
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1, c2 = p1 + (p2 - p0) / 6, p2 - (p3 - p1) / 6
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d) + (" Z" if closed else "")


def ellipse(cx, cy, rx, ry, n=24):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return catmull(np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], 1))


def foot(x0, x1, top, bottom=372):
    """A white foot or leg: a gently scalloped top (toes) down past the floor."""
    w = x1 - x0
    return (f"M{x0:.1f},{top + 5:.1f} C{x0 + .13 * w:.1f},{top - 3:.1f} {x0 + .31 * w:.1f},{top + 2:.1f} {x0 + .46 * w:.1f},{top - 3:.1f} "
            f"C{x0 + .6 * w:.1f},{top + 2:.1f} {x0 + .8 * w:.1f},{top - 5:.1f} {x1:.1f},{top + 3:.1f} L{x1 + 2:.1f},{bottom} L{x0 - 2:.1f},{bottom} Z")


def rings_of(d, step=1.0):
    rings = []
    for sp in Path(d).as_subpaths():
        sp = Path(sp)
        L = sp.length(error=1e-3)
        if L < 1:
            continue
        n = max(8, int(L / step))
        rings.append(np.array([[sp.point(i / n).x, sp.point(i / n).y] for i in range(n)]))
    return rings


def furry(d, amp=2.2, spacing=3.2, inside=None):
    """A zone's outline with small fur tufts leaning downwards. Stretches outside `inside` (the body, which
    clips them anyway) keep a point every 12 units and no tufts."""
    near = (lambda x, y: True) if inside is None else (lambda x, y: inside.contains(Point(x, y)))
    out = []
    for ring in rings_of(d):
        area = 0.5 * np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - np.roll(ring[:, 0], -1) * ring[:, 1])
        sgn = 1 if area > 0 else -1
        closed = np.vstack([ring, ring[:1]])
        seg = np.diff(closed, axis=0)
        s = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
        total = s[-1]
        if total < 12:
            continue
        n = max(6, int(total / spacing))
        pts, skipped = [], 0
        at = lambda u: (np.interp(u, s, closed[:, 0]), np.interp(u, s, closed[:, 1]))
        for i in range(n):
            x0, y0 = at(i / n * total)
            if not near(x0, y0):
                skipped += spacing
                if skipped >= 12 or i == 0:
                    pts.append((x0, y0)); skipped = 0
                continue
            skipped = 0
            for frac, tip in ((0.0, False), (0.55, True)):
                u = (i + frac) / n * total
                x, y = at(u)
                j = min(np.searchsorted(s, u), len(seg) - 1)
                tx, ty = seg[j] / (np.hypot(*seg[j]) or 1)
                nx, ny = sgn * ty, -sgn * tx
                a = amp * (rng.uniform(0.45, 1.25) if tip else -0.35)
                x, y = x + nx * a, y + ny * a + (0.9 * a if tip else 0)
                pts.append((x, y))
        out.append(catmull(np.array(pts)))
    return " ".join(out)


# ------------------------------------------------------------------------------------------- raster helpers
R, X0, Y0, W, H = 3, -40, -30, 360, 560


def raster(page, ds, fill_rule="nonzero"):
    g = "".join(f'<path d="{d}" fill="#000" fill-rule="{fill_rule}"/>' for d in ds)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{X0} {Y0} {W} {H}" width="{W * R}" height="{H * R}" '
           f'style="display:block">{g}</svg>')
    page.set_viewport_size({"width": W * R, "height": H * R})
    page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
    img = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
    return img < 128


def mask_poly(mask):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    polys = [Polygon(c[:, 0, :] / R + [X0, Y0]).buffer(0) for c in cs if len(c) > 10]
    return unary_union(polys)


def poly_d(poly, tol=0.5):
    geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
    return " ".join("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in np.array(g.simplify(tol).exterior.coords)[:-1]) + " Z"
                    for g in geoms if g.area > 2)


# ------------------------------------------------------------------------------------------- V2-only shapes
def nose_fill(page, mouth_d):
    """The inside of the nose loop drawn in mouth 1 (the largest hole in it)."""
    m = raster(page, [mouth_d])
    cs, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    holes = [c for c, h in zip(cs, hier[0]) if h[3] >= 0]
    c = max(holes, key=cv2.contourArea)
    poly = Polygon(c[:, 0, :] / R + [X0, Y0]).buffer(0.8)     # tuck under the line
    return poly_d(poly, 0.3)


def bib_fill(page, fluff_ds):
    """The cream chest bib: the area the fluff lines enclose (their hull), with a ragged top running between
    the two top spikes and dipping in the middle, as in AC's reference render."""
    m = raster(page, fluff_ds)
    ys, xs = np.nonzero(m)
    pts = np.stack([X0 + xs / R, Y0 + ys / R], 1)
    hull = Polygon(cv2.convexHull(pts.astype(np.float32))[:, 0, :])
    x0, y0, x1, y1 = hull.bounds
    cx = (x0 + x1) / 2
    top = [(x0 - 5, y0 - 5), (x0 + 2, y0 + 2)]
    for k in range(1, 8):                                       # the top edge: little tufts, lowest mid-way
        x = x0 + (x1 - x0) * k / 8
        sag = 9 * (1 - abs(x - cx) / ((x1 - x0) / 2))
        top.append((x, y0 + 2 + sag + (3 if k % 2 else -1)))
    top += [(x1 - 2, y0 + 2), (x1 + 5, y0 - 5), (x1 + 5, y0 - 30), (x0 - 5, y0 - 30)]
    cap = Polygon(top).buffer(0)
    return poly_d(hull.difference(cap).buffer(1.2).buffer(-1.2), 0.4)


# White zones on V2 (front view). Order = how white spreads as a cat gets whiter (as in the old kit).
def v2_zones(bib_d):
    bib = rings_of(bib_d)[0]
    bib_big = Polygon(bib).buffer(4)
    return [
        ("chin", "Chin", ellipse(58.5, 131, 8, 4.5)),
        ("locket", "Chest locket", catmull([(58, 146), (66, 148), (66, 160), (62, 174), (59, 186), (55, 174), (51, 160), (51, 148)])),
        ("muzzle", "Muzzle", ellipse(59, 117, 17, 15)),
        ("bib", "Chest bib", poly_d(bib_big, 0.4)),
        ("blaze", "Nose blaze", "M60.5,40 C62,55 63,70 65,85 C66,92 66,97 64,100 L57,100 C55,97 55,92 56,85 C58,70 59,55 60.5,40 Z"),
        ("belly", "Belly", catmull([(44, 205), (62, 200), (80, 205), (87, 262), (86, 352), (60, 352), (56, 262)])),
        ("paws", "Paws", " ".join([foot(16, 58, 334), foot(75, 118, 334), foot(-4, 22, 326), foot(108, 152, 324)])),
        ("stockings", "Stockings", " ".join([foot(18, 60, 286), foot(80, 120, 286), foot(-4, 22, 300), foot(108, 152, 300)])),
        ("face", "Lower face", catmull([(4, 102), (22, 93), (42, 97), (60, 90), (78, 97), (100, 93), (138, 101), (132, 126),
                                        (104, 140), (60, 145), (24, 139), (6, 126)])),
        ("body", "Body (mostly white)", "M-20,152 C20,146 40,150 60,148 C80,150 110,146 200,152 L200,380 L-20,380 Z"),
    ]


# ------------------------------------------------------------------------------------------- the old eye sets
def old_eye_sets(old_kit):
    """The inner content of the old kit's typical body's eye-sets group (all seven sets)."""
    i = old_kit.index('<g class="eye-sets"')
    j = old_kit.index(">", i) + 1
    depth, k = 1, j
    while depth:
        a, b = old_kit.find("<g", k), old_kit.find("</g>", k)
        if a != -1 and a < b:
            depth += 1; k = a + 2
        else:
            depth -= 1; k = b + 4
    return old_kit[j:k - 4]


# ------------------------------------------------------------------------------------------- CSS
def css(names, zones):
    v = lambda k: f"var(--cat-{k}, {CLASSIC[k]})"
    L = ["    .body { display: none; }"]
    L += [f'    #cat[data-body="{n}"] .body[data-body="{n}"] {{ display: inline; }}' for n in names]
    L += [f"    .k-coat {{ fill: {v('coat')}; }}",
          f"    .k-stripes {{ fill: {v('stripes')}; }}",
          '    #cat[data-stripes="off"] .k-stripes { display: none; }',
          f"    .k-cream {{ fill: {v('cream')}; }}",
          '    #cat[data-cream="off"] .k-cream { display: none; }',
          f"    .w-zone {{ fill: {v('white')}; display: none; }}"]
    L += [f'    #cat[data-white~="{k}"] .w-{k} {{ display: inline; }}' for k, _, _ in zones]
    L += ['    .fur-zones { display: none; }',
          '    #cat[data-fur="on"] .smooth-zones { display: none; }',
          '    #cat[data-fur="on"] .fur-zones { display: inline; }',
          f"    .k-ear {{ fill: {v('ear')}; }}",
          f"    .k-ear-cream {{ fill: {v('cream')}; }}",
          '    #cat[data-ears="plain"] .k-ears, #cat[data-ears="plain"] .k-ear-line { display: none; }',
          f"    .k-nose {{ fill: {v('nose')}; }}",
          f"    .k-glow-stop {{ stop-color: {v('glow')}; }}",
          '    .k-glow { display: none; }',
          '    #cat[data-coat="soft"] .k-glow { display: inline; }',
          f"    .k-outline {{ fill: var(--cat-outline, {CLASSIC['outline']}); }}",
          '    #cat[data-fluff="off"] .k-fluff { display: none; }',
          '    .k-mouth { display: none; }',
          '    #cat[data-mouth="1"] .k-mouth-1, #cat[data-mouth="2"] .k-mouth-2 { display: inline; }',
          f"    .k-eye-white {{ fill: {v('eye-white')}; }}",
          f"    .eyes {{ display: none; fill: var(--cat-outline, {CLASSIC['outline']}); }}"]
    L += [f'    #cat[data-eyes="{k}"] .eyes[data-set="{k}"] {{ display: inline; }}'
          for k in ["original", "almond", "squint", "big-shiny", "slit", "half-lidded", "round"]]
    for name, c in COATS.items():
        L.append(f'    #cat[data-coat="{name}"] {{ ' + " ".join(f"--cat-{k}: {val};" for k, val in c.items()) + " }")
    return "\n".join(L)


# ------------------------------------------------------------------------------------------- build
def main():
    src, old_kit_path, out = sys.argv[1:4]
    parts = {f: elements(os.path.join(src, f)) for f in PLACE}
    by_role = lambda f, *roles: [d_of(e) for e in parts[f] if any(f'r-{r}"' in e for r in roles)]
    placed = lambda f, ds: [warp_d(d, lambda x, y: (np.asarray(x), np.asarray(y)), *PLACE[f]) for d in ds]  # V2 world

    coat_v2 = coat_path(parts["outline 1.svg"])
    stripes_v2 = placed("stripe pattern 1.svg", by_role("stripe pattern 1.svg", "stripe")) + \
        placed("face stripe pattern 1.svg", by_role("face stripe pattern 1.svg", "stripe"))
    ear_v2 = placed("ear 1 shading.svg", by_role("ear 1 shading.svg", "ear"))
    ear_cream_v2 = placed("ear 1 shading.svg", by_role("ear 1 shading.svg", "cream"))
    outline_v2 = placed("outline 1.svg", by_role("outline 1.svg", "line"))
    ear_lines_v2 = placed("ears 1.svg", by_role("ears 1.svg", "line"))
    fluff_v2 = placed("fluff 1.svg", by_role("fluff 1.svg", "line", "line-dark", "line-mid"))
    mouth_v2 = {k: placed(f"mouth {k}.svg", by_role(f"mouth {k}.svg", "line")) for k in (1, 2)}

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        nose_v2 = nose_fill(pg, " ".join(mouth_v2[1]))
        bib_v2 = bib_fill(pg, fluff_v2)
        zones_v2 = v2_zones(bib_v2)
        muzzle_v2 = ellipse(58.7, 117.4, 15.4, 15.4)
        glows_v2 = [ellipse(60, 200, 40, 60), ellipse(60, 114, 28, 18)]

        old = open(old_kit_path, encoding="utf-8").read()
        eyes_inner = old_eye_sets(old)

        names = list(BODIES)
        clips, groups, attach, boxes = [], [], {}, []
        for n in names:
            hs, sx, sy = BODIES[n]
            w = make_warp(hs, sx, sy)
            W_ = lambda d: warp_d(d, w)
            sil = W_(coat_v2)
            sil_poly = mask_poly(raster(pg, [sil])).buffer(4)
            x0, y0, x1, y1 = sil_poly.bounds
            boxes.append((x0, y0, x1, y1))
            clips.append(f'<clipPath id="sil-{n}"><path d="{sil}"/></clipPath>')
            clip = f'clip-path="url(#sil-{n})"'
            zone_ds = [(k, lab, W_(d)) for k, lab, d in zones_v2]
            smooth_z = "\n".join(f'      <path class="w-zone w-{k}" data-label="{lab}" fill-rule="evenodd" d="{d}"/>' for k, lab, d in zone_ds)
            fur_z = "\n".join(f'      <path class="w-zone w-{k}" data-label="{lab}" fill-rule="evenodd" d="{furry(d, inside=sil_poly)}"/>'
                              for k, lab, d in zone_ds)
            ex, ey = w([EYE_ANCHOR_V2[0]], [EYE_ANCHOR_V2[1]])
            es = EYE_SCALE_V2 * hs * KIT_SCALE
            eye_tf = f"translate({ex[0]:.2f},{ey[0]:.2f}) scale({es:.4f}) translate({-OLD_EYE_ANCHOR[0]},{-OLD_EYE_ANCHOR[1]})"

            # the tail: it comes out from behind the bum on the cat's left (the viewer's right), on the
            # haunch's outer edge, between these two heights of the drawing
            rows = []
            for yv in (312, 338):
                _, yk = w([BODY_X], [yv])
                cut = sil_poly.buffer(-4).intersection(Polygon([(-500, yk[0] - .3), (900, yk[0] - .3), (900, yk[0] + .3), (-500, yk[0] + .3)]))
                rows.append((round(cut.bounds[2], 1), round(float(yk[0]), 1)))
            attach[n] = {"up": list(rows[0]), "low": list(rows[1]),
                         "BODY_CENTRE inside": sil_poly.buffer(-4).contains(Point(*BODY_CENTRE))}

            groups.append(f'''  <g class="body" data-body="{n}" data-label="{LABELS[n]}">
    <path class="k-coat" d="{sil}"/>
    <g class="k-glow" {clip}>{"".join(f'<path fill="url(#k-glow)" d="{W_(g)}"/>' for g in glows_v2)}</g>
    <path class="k-stripes" {clip} d="{" ".join(W_(d) for d in stripes_v2)}"/>
    <path class="k-cream" {clip} d="{furry(W_(bib_v2), 2.4, 3.0)} {W_(muzzle_v2)}"/>
    <g class="white-zones smooth-zones" {clip}>
{smooth_z}
    </g>
    <g class="white-zones fur-zones" {clip}>
{fur_z}
    </g>
    <g class="k-ears"><path class="k-ear" d="{" ".join(W_(d) for d in ear_v2)}"/><path class="k-ear-cream" d="{" ".join(W_(d) for d in ear_cream_v2)}"/></g>
    <path class="k-nose" d="{W_(nose_v2)}"/>
    <g class="outline">
      <path class="k-outline" d="{" ".join(W_(d) for d in outline_v2)}"/>
      <path class="k-outline k-ear-line" d="{" ".join(W_(d) for d in ear_lines_v2)}"/>
      <path class="k-outline k-fluff" d="{" ".join(W_(d) for d in fluff_v2)}"/>
      <path class="k-outline k-mouth k-mouth-1" d="{" ".join(W_(d) for d in mouth_v2[1])}"/>
      <path class="k-outline k-mouth k-mouth-2" d="{" ".join(W_(d) for d in mouth_v2[2])}"/>
    </g>
    <g class="eye-sets" transform="{eye_tf}">{eyes_inner}</g>
  </g>''')
        b.close()

    x0 = min(bx[0] for bx in boxes) - 4; y0 = min(bx[1] for bx in boxes) - 4
    x1 = max(bx[2] for bx in boxes) + 4; y1 = max(bx[3] for bx in boxes) + 4
    vb = f"{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}"
    clip_block = "\n".join("    " + c for c in clips)
    glow_def = ('    <radialGradient id="k-glow" cx="50%" cy="50%" r="50%">'
                '<stop class="k-glow-stop" offset="0" stop-opacity=".95"/><stop class="k-glow-stop" offset=".55" stop-opacity=".6"/>'
                '<stop class="k-glow-stop" offset="1" stop-opacity="0"/></radialGradient>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" id="cat" data-body="typical" data-white="" data-eyes="original" data-stripes="on" data-coat="classic" data-ears="tufted" data-cream="on" data-fluff="on" data-mouth="1" data-fur="off">
  <!-- Cat kit V2: built by SVG/V2/build_kit_v2.py from AC's V2 parts in SVG/V2/SVG. -->
  <defs>
{clip_block}
{glow_def}
    <style>
{css(names, zones_v2)}
    </style>
  </defs>
{chr(10).join(groups)}
</svg>
'''
    open(out, "w", encoding="utf-8").write(svg)
    print(f"wrote {out} ({len(svg) // 1024} KB), viewBox {vb}", file=sys.stderr)
    print("tail ATTACH (kit units):", file=sys.stderr)
    for n, a in attach.items():
        print(f"  {n}: {a}", file=sys.stderr)


if __name__ == "__main__":
    main()

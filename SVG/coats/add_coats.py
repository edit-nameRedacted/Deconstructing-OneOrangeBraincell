"""Superseded (2026-11-04): this added coats to the first (3/4-view) kit. The V2 kit is built, coats and all,
by SVG/V2/build_kit_v2.py; running this on it would not work.

Add the coat variants, fur-edged white zones and ear interiors to the cat kit, and set its palette.

Usage (from SVG/):  python3 coats/add_coats.py cat_kit.svg cat_kit.svg

Reads the kit, removes anything an earlier run added (all of it is marked "cv-"), and writes it back with:

  data-coat   classic | mackerel | high-contrast | soft            (default classic)
  data-ears   plain | pink | tufted                                (default plain)
  data-fur    off | on    fur-textured edges on the white zones    (default off)

The eyes are untouched: they stay their own layer, switched by data-eyes as before. Tails are not touched either.

Colours come from one 10-swatch palette (PALETTE below), dark to light. Each coat sets the kit's colour
variables from it; classic uses the page's --cat-* tokens when they are set, and the palette otherwise.
Pink (nose, inner ear) is the one colour outside the palette.

How the new shapes are made:
  - Stripes (mackerel; high-contrast thickens them with an outline) and the soft-gradient glows are drawn once on the typical body, in
    kit units, as tapered brush strokes. They are carried onto the kitten, slender and chunky bodies with the same
    landmark warp warp_bodies.py used for the original stripes and white zones, so they keep their place on the body.
  - Fur edges: every white zone's outline is resampled and given small tufts (a saw-tooth leaning downwards, the
    way fur lies). Same zones, same order, so white_stages.json barely moves.
  - Ear interiors are cut from each body's own silhouette (the part above the crown, each side of the nose, shrunk
    inwards), so they fit every drawing without warping.
Every new layer is clipped to its body's silhouette, like the white zones.
"""
import os, re, sys
import numpy as np
import cv2
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union
from svgelements import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bodies"))
sys.path.insert(0, os.path.join(HERE, ".."))
from warp_bodies import Frame, make_warp   # noqa: E402
from fit_bodies import render, R, X0, Y0              # noqa: E402
from playwright.sync_api import sync_playwright        # noqa: E402

# ---------------------------------------------------------------- palette (sampled from the reference sheet)
PALETTE = ["#442511", "#6B3B13", "#9A662D", "#C37825", "#DB8C3F",
           "#F1B96F", "#BB9063", "#BE7643", "#FCD9AF", "#F1E7DB"]
P = PALETTE
PINK, PINK_DARK = "#E7A49E", "#C98078"

# coat -> colour variables. stripes: which stripe drawing shows (classic = the kit's original stripes).
COATS = {
    "classic":       {"stripes": "classic",  "vars": {}},   # page tokens / palette defaults below
    "mackerel":      {"stripes": "mackerel", "vars": {"coat": P[4], "stripes": P[2], "white": P[9]}},
    "high-contrast": {"stripes": "mackerel", "vars": {"coat": P[3], "stripes": P[1], "white": P[9], "ear-back": P[0]}},
    "soft":          {"stripes": "mackerel", "vars": {"coat": P[6], "stripes": P[7], "white": P[8], "glow": P[8]}},
}
DEFAULTS = {"coat": P[4], "stripes": P[2], "white": P[9], "nose": PINK, "ear": PINK, "ear-line": PINK_DARK,
            "tuft": P[9], "glow": P[8], "ear-back": P[1]}

rng = np.random.default_rng(7)


# ---------------------------------------------------------------- path helpers
def catmull(pts, closed=False):
    """Points -> smooth cubic path through them (Catmull-Rom)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    get = (lambda i: pts[i % n]) if closed else (lambda i: pts[min(max(i, 0), n - 1)])
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1, c2 = p1 + (p2 - p0) / 6, p2 - (p3 - p1) / 6
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d) + (" Z" if closed else "")


def dense(pts, step=1.0):
    """Sample a smooth curve through the control points at about `step` units."""
    pts = np.asarray(pts, float)
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        n = max(2, int(np.hypot(*(p2 - p1)) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return np.array(out)


def stroke(pts, w, ends="both"):
    """A tapered brush stroke along the control points, as a ring of outline points (see ring_d).
    ends: 'both' tapers at both ends; 'tip' starts full width (hidden past the body edge) and tapers to a point."""
    c = dense(pts, 1.0)
    seg = np.diff(c, axis=0)
    s = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
    t = s / s[-1]
    prof = np.sin(np.pi * t) ** 0.6 if ends == "both" else np.cos(np.pi / 2 * t) ** 0.7
    tang = np.gradient(c, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
    half = (w / 2 * prof)[:, None]
    ring = np.concatenate([c + nrm * half, (c - nrm * half)[::-1]])
    return ring[:: max(1, len(ring) // 18)]                 # ~18 points is plenty for a stroke


def ring_d(rings, warp=None):
    """Rings of points -> one path. With `warp`, the points are moved onto another body first."""
    out = []
    for r in rings:
        if warp is not None:
            xs, ys = warp(r[:, 0], r[:, 1])
            r = np.stack([xs, ys], 1)
        out.append(catmull(r, closed=True))
    return " ".join(out)


def path_polys(d, step=1.5):
    """Path data -> list of point rings (each subpath sampled every ~step units)."""
    rings = []
    for sp in Path(d).as_subpaths():
        sp = Path(sp)
        L = sp.length(error=1e-3)
        if L < 1:
            continue
        n = max(8, int(L / step))
        pts = np.array([[sp.point(i / n).x, sp.point(i / n).y] for i in range(n)])
        rings.append(pts)
    return rings


def furry(d, amp=2.2, spacing=3.2, inside=None):
    """Give a zone's outline small fur tufts: soft teeth leaning downwards (fur lies down the body).
    `inside`: the body's silhouette (shapely). Stretches of outline outside it are clipped away in the kit
    anyway, so they keep just a point every 12 units and no tufts, which keeps the file small."""
    from shapely.geometry import Point
    near = (lambda x, y: True) if inside is None else (lambda x, y: inside.contains(Point(x, y)))
    out = []
    for ring in path_polys(d, 1.0):
        area = 0.5 * np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - np.roll(ring[:, 0], -1) * ring[:, 1])
        sgn = 1 if area > 0 else -1                        # which side is outside
        seg = np.diff(np.vstack([ring, ring[:1]]), axis=0)
        s = np.concatenate([[0], np.cumsum(np.hypot(seg[:, 0], seg[:, 1]))])
        total = s[-1]
        if total < 12:
            continue
        n = max(6, int(total / spacing))
        pts = []
        skipped = 0
        for i in range(n):
            u0 = i / n * total
            x0, y0 = np.interp(u0, s, np.append(ring[:, 0], ring[0, 0])), np.interp(u0, s, np.append(ring[:, 1], ring[0, 1]))
            if not near(x0, y0):
                skipped += spacing
                if skipped >= 12 or i == 0:
                    pts.append((x0, y0)); skipped = 0
                continue
            skipped = 0
            for frac, tip in ((0.0, False), (0.55, True)):
                u = (i + frac) / n * total
                x, y = np.interp(u, s, np.append(ring[:, 0], ring[0, 0])), np.interp(u, s, np.append(ring[:, 1], ring[0, 1]))
                j = min(np.searchsorted(s, u), len(seg) - 1)
                tx, ty = seg[j] / (np.hypot(*seg[j]) or 1)
                nx, ny = sgn * ty, -sgn * tx                 # outward normal
                if tip:
                    a = amp * rng.uniform(0.45, 1.25)
                    x, y = x + nx * a, y + ny * a + 0.9 * a  # lean the tip downwards
                else:
                    a = amp * 0.35
                    x, y = x - nx * a, y - ny * a
                pts.append((x, y))
        out.append(catmull(np.array(pts), closed=True))
    return " ".join(out)


# ---------------------------------------------------------------- the typical cat's new drawings (kit units)
def mackerel_strokes(A, width=1.3):
    """Mackerel tabby stripes on the typical body. A = its Frame (for the body's edge at each height)."""
    L = lambda y: float(A.ext(y)[0])
    Rt = lambda y: float(A.ext(y)[1])
    w = lambda v: v * width
    out = []
    # forehead: an M of thin lines between the ears
    for x0, x1, y1, ww in [(93, 93, 76, 4.2), (83, 79, 72, 3.8), (103, 107, 72, 3.8), (73, 66, 62, 3.2), (113, 120, 62, 3.2)]:
        out.append(stroke([(x0, 36), ((x0 + x1) / 2 + rng.uniform(-1, 1), (36 + y1) / 2), (x1, y1)], w(ww)))
    # cheeks: two lines sweeping out from each eye
    for pts, ww in [([(48, 109), (38, 111), (24, 108)], 3.4), ([(52, 121), (40, 127), (26, 128)], 3.0),
                    ([(143, 110), (158, 108), (178, 104)], 3.4), ([(140, 122), (154, 126), (176, 125)], 3.0)]:
        out.append(stroke(pts, w(ww)))
    # temples: short marks behind the eyes
    out.append(stroke([(30, 72), (40, 76), (50, 77)], w(3)))
    out.append(stroke([(176, 74), (164, 78), (154, 79)], w(3)))
    # necklace: two broken bands across the chest
    for y in (182, 202):
        out.append(stroke([(62, y), (78, y + 7), (92, y + 9)], w(4)))
        out.append(stroke([(100, y + 9), (116, y + 7), (134, y)], w(4)))
    # left flank: bars from the edge inwards, sloping down
    for y in (210, 236, 262, 288, 318, 384, 410, 436):
        x = L(y)
        out.append(stroke([(x - 6, y), (x + 10, y + 3), (x + 24, y + 9)], w(6.5), "tip"))
    # right side: shoulder, then the haunch, curving with the body
    for y, ln in [(188, 22), (212, 28), (238, 32), (264, 36), (292, 44), (320, 54), (348, 60), (376, 62), (404, 60), (432, 52)]:
        x = Rt(y)
        out.append(stroke([(x + 6, y - 2), (x - ln * 0.45, y + 4), (x - ln, y + 14)], w(7), "tip"))
    # front legs: short bars across each leg
    for y in (340, 366, 392, 418):
        out.append(stroke([(48, y), (60, y + 2), (72, y + 3)], w(5.2)))           # left leg, outer side
        out.append(stroke([(198, y + 6), (186, y + 7), (174, y + 9)], w(5.2)))    # right leg, outer side
        out.append(stroke([(149, y + 4), (157, y + 6), (164, y + 7)], w(4.2)))    # right leg, inner side
    return out


def glows():
    """Soft-gradient tabby: pale patches (filled with a radial gradient) on the chest, belly and muzzle."""
    def ellipse(cx, cy, rx, ry):
        a = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        return np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], 1)
    return [ellipse(100, 285, 62, 150), ellipse(94, 132, 40, 26), ellipse(78, 450, 50, 40)]


# ---------------------------------------------------------------- ears, from each body's own silhouette
def to_poly(mask, region):
    """Mask pixels -> shapely polygon(s) in kit units, cut to `region` (a shapely box)."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    polys = [Polygon((c[:, 0, :] / R) + [X0, Y0]).buffer(0) for c in cs if len(c) > 10]
    return unary_union(polys).intersection(region)


def ears(mask, fr):
    """Inner-ear shapes and fur tufts for one body. fr = its Frame.
    Each inner ear is a teardrop inside the ear: its point a little below the ear's tip, its base just below
    the crown, set in from both sides of the ear, with a rounded bottom."""
    inner, tufts = [], []
    for side in (-1, 1):
        x_lo, x_hi = (-200, fr.nose_x) if side < 0 else (fr.nose_x, 600)
        ear = to_poly(mask, box(x_lo, -100, x_hi, fr.crown + 2)).buffer(-4).buffer(4)
        if isinstance(ear, MultiPolygon):
            ear = max(ear.geoms, key=lambda g: g.area)
        if ear.is_empty:
            continue
        ring = np.array(ear.exterior.coords)
        tip = ring[np.argmin(ring[:, 1])]
        h = fr.crown - tip[1]
        # the ear's width a little above the crown
        yb = fr.crown - 0.12 * h
        cut = ear.intersection(box(-200, yb - 0.5, 600, yb + 0.5))
        if cut.is_empty:
            continue
        bl, br = cut.bounds[0], cut.bounds[2]
        w = br - bl
        T = tip + [(bl + br) / 2 - tip[0], 0] * np.array([0.25, 0]) + [0, 0.2 * h]
        L0, R0 = np.array([bl + 0.2 * w, yb]), np.array([br - 0.2 * w, yb])
        Lm, Rm = (T + L0) / 2 + [-0.06 * w, 0], (T + R0) / 2 + [0.06 * w, 0]
        B = np.array([(bl + br) / 2, fr.crown + 0.1 * h])
        pts = np.array([T, Rm, R0, (R0 + B) / 2 + [0.04 * w, 0.02 * h], B, (L0 + B) / 2 + [-0.04 * w, 0.02 * h], L0, Lm])
        inner.append(catmull(pts, closed=True))
        # tufts: three wisps rising from the base of the inner ear, fanning towards the tip
        for k, f in enumerate((-0.22, 0.0, 0.22)):
            b = B + [f * w * 0.9 + side * 0.06 * w, -0.06 * h]
            e = b + (T - b) * (0.6 - 0.12 * abs(k - 1)) + [side * 0.08 * w, 0]
            m = (b + e) / 2 + [-side * 0.07 * w, 0]
            tufts.append(catmull(stroke([b, m, e], 0.045 * h + 1.0), closed=True))
    return inner, tufts


def ear_backs(mask, fr):
    """The outer ears (everything above the crown), for the high-contrast coat's dark ears. An opening
    (shrink, then grow back) drops the thin strip of head between the ears."""
    out = []
    geo = to_poly(mask, box(-200, -100, 600, fr.crown + 2)).buffer(-5).buffer(5)
    for g in (geo.geoms if isinstance(geo, MultiPolygon) else [geo]):
        if g.area > 40:
            out.append(catmull(np.array(g.simplify(0.6).exterior.coords)[:-1], closed=True))
    return " ".join(out)


# ---------------------------------------------------------------- reading and writing the kit
def body_block(kit, name):
    m = re.search(rf'<g class="body" data-body="{name}"[^>]*>.*?\n  </g>', kit, re.S)
    return m


def strip_previous(kit):
    kit = re.sub(r"\s*<!-- cv:begin -->.*?<!-- cv:end -->", "", kit, flags=re.S)
    kit = re.sub(r'\s*<(path|g)[^>]*class="[^"]*\bcv-[^"]*"[^>]*?(/>|>.*?</g>)', "", kit, flags=re.S)
    kit = re.sub(r'\s*<g class="white-zones cv-fur-zones".*?</g>', "", kit, flags=re.S)
    kit = kit.replace('class="k-stripes s-classic"', 'class="k-stripes"')
    kit = kit.replace('class="white-zones smooth-zones"', 'class="white-zones"')
    kit = re.sub(r' data-coat="[^"]*" data-ears="[^"]*" data-fur="[^"]*"', "", kit)
    kit = re.sub(r'\s*<(linearGradient|radialGradient) id="cv-[^"]*".*?</\1>', "", kit, flags=re.S)
    return kit


def css():
    var = lambda k: f"var(--cat-{k}, {DEFAULTS[k]})"
    lines = ["<!-- cv:begin -->",
             "    /* ---- Coat variants, ears and fur edges (coats/add_coats.py) ---- */",
             f"    /* palette, dark to light: {' '.join(PALETTE)} */",
             f"    .k-coat {{ fill: {var('coat')}; }}",
             f"    .k-stripes, .cv-stripes {{ fill: {var('stripes')}; }}",
             f"    .w-zone {{ fill: {var('white')}; }}",
             f"    .k-nose {{ fill: {var('nose')}; }}",
             "    .cv-stripes, .cv-glow, .cv-ear-back, .cv-ear, .cv-tuft { display: none; }",
             f"    .cv-ear-back {{ fill: {var('ear-back')}; }}",
             f"    .cv-ear {{ fill: {var('ear')}; stroke: {var('ear-line')}; stroke-width: 1.2; }}",
             f"    .cv-tuft {{ fill: {var('tuft')}; }}",
             "    #cat[data-stripes=\"off\"] .cv-stripes { display: none !important; }"]
    for name, c in COATS.items():
        if c["vars"]:
            decl = " ".join(f"--cat-{k}: {v};" for k, v in c["vars"].items())
            lines.append(f'    #cat[data-coat="{name}"] {{ {decl} }}')
        if c["stripes"] != "classic":
            lines.append(f'    #cat[data-coat="{name}"] .s-classic {{ display: none; }}')
            lines.append(f'    #cat[data-coat="{name}"] .cv-stripes.s-{c["stripes"]} {{ display: inline; }}')
    lines += [  # high-contrast: the mackerel stripes, thickened by an outline in their own colour
              f'    #cat[data-coat="high-contrast"] .cv-stripes {{ stroke: {var("stripes")}; stroke-width: 4; stroke-linejoin: round; }}',
              '    #cat[data-coat="soft"] .cv-glow { display: inline; }',
              '    #cat[data-coat="high-contrast"] .cv-ear-back { display: inline; }',
              '    #cat[data-ears="pink"] .cv-ear, #cat[data-ears="tufted"] .cv-ear { display: inline; }',
              '    #cat[data-ears="tufted"] .cv-tuft { display: inline; }',
              # fur edges: swap the smooth zone group for the furry one
              '    .cv-fur-zones { display: none; }',
              '    #cat[data-fur="on"] .white-zones.smooth-zones { display: none; }',
              '    #cat[data-fur="on"] .white-zones.cv-fur-zones { display: inline; }',
              "<!-- cv:end -->"]
    return "\n".join(lines)


def main():
    src, out = sys.argv[1:3]
    kit = strip_previous(open(src, encoding="utf-8").read())
    names = re.findall(r'<g class="body" data-body="([\w-]+)"', kit)

    sils, noses = {}, {}
    for n in names:
        blk = body_block(kit, n).group(0)
        sils[n] = re.search(r'<path class="k-coat" d="([^"]+)"', blk).group(1)
        nd = re.search(r'<path class="k-nose" d="([^"]+)"', blk).group(1)
        bb = Path(nd).bbox()
        dy = -4 if n == "typical" else 0                    # the typical outline group is shifted up 4 units
        noses[n] = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2 + dy)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        masks = {n: render([sils[n]], pg).astype(bool) for n in names}
        b.close()
    frames = {n: Frame(masks[n], noses[n]) for n in names}
    A = frames["typical"]

    # typical-body drawings
    mack = mackerel_strokes(A)
    glow = glows()

    defs = (f'    <radialGradient id="cv-glow" cx="50%" cy="50%" r="50%">'
            f'<stop offset="0" stop-color="var(--cat-glow, {DEFAULTS["glow"]})" stop-opacity=".95"/>'
            f'<stop offset=".55" stop-color="var(--cat-glow, {DEFAULTS["glow"]})" stop-opacity=".6"/>'
            f'<stop offset="1" stop-color="var(--cat-glow, {DEFAULTS["glow"]})" stop-opacity="0"/></radialGradient>')
    kit = kit.replace("    <style>", defs + "\n    <style>", 1)

    for n in names:
        warp = None if n == "typical" else make_warp(A, frames[n])
        clip = f'clip-path="url(#sil-{n})"'
        under = [f'<g class="cv-glow" {clip}>' + "".join(f'<path fill="url(#cv-glow)" d="{ring_d([g], warp)}"/>' for g in glow) + "</g>",
                 f'<path class="cv-stripes s-mackerel" {clip} d="{ring_d(mack, warp)}"/>']
        inner, tufts = ears(masks[n], frames[n])
        ear_back_d = ear_backs(masks[n], frames[n])
        sil = to_poly(masks[n], box(-200, -100, 600, 600)).buffer(4)
        over = [f'<path class="cv-ear-back" {clip} d="{furry(ear_back_d, 1.6, 3.0, sil)}"/>',
                f'<path class="cv-ear" {clip} d="{" ".join(inner)}"/>',
                f'<path class="cv-tuft" {clip} d="{" ".join(tufts)}"/>']

        m = body_block(kit, n)
        blk = m.group(0)
        blk = blk.replace('<path class="k-stripes"', '<path class="k-stripes s-classic"', 1)
        # glow + new stripes go just before the classic stripes ... (glow under all stripes)
        i = blk.index('<path class="k-stripes s-classic"')
        blk = blk[:i] + "\n    ".join(under) + "\n    " + blk[i:]
        # fur-edged copy of the white zones, right after the smooth ones
        zm = re.search(r'(    <g class="white-zones"[^>]*>)(.*?)(\n    </g>)', blk, re.S)
        smooth_open = zm.group(1).replace('class="white-zones"', 'class="white-zones smooth-zones"')
        fur_paths = re.sub(r'(<path class="w-zone w-[\w-]+"[^>]*?) d="([^"]+)"',
                           lambda mm: f'{mm.group(1)} d="{furry(mm.group(2), inside=sil)}"', zm.group(2))
        fur_group = zm.group(1).replace('class="white-zones"', 'class="white-zones cv-fur-zones"') + fur_paths + zm.group(3)
        blk = blk.replace(zm.group(0), smooth_open + zm.group(2) + zm.group(3) + "\n" + fur_group + "\n    " + "\n    ".join(over), 1)
        kit = kit.replace(m.group(0), blk, 1)

    kit = kit.replace("    </style>", css() + "\n    </style>", 1)
    kit = re.sub(r'(<svg [^>]*data-stripes="[^"]*")', r'\1 data-coat="classic" data-ears="plain" data-fur="off"', kit, count=1)
    open(out, "w", encoding="utf-8").write(kit)
    print(f"wrote {out} ({len(kit) // 1024} KB): coats {list(COATS)}, bodies {names}", file=sys.stderr)


if __name__ == "__main__":
    main()

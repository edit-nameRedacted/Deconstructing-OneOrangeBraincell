"""Carry the original cat's stripes, white zones and eyes onto the other body types.

Usage: python3 warp_bodies.py bodies_raw.json bodies_fit.json ../smooth_parts.json bodies_kit.json

Each body is matched to the original by landmarks found the same way on every silhouette: ear tip, crown (the dip
between the ears), nose, neck (narrowest point below the head), haunch (widest point) and floor. Heights are mapped
piecewise between those landmarks; across each row, the cat's left edge, the nose line and its right edge are
matched. Stripes and white zones are moved point by point with that mapping, so they keep their place on the body.
The eyes move to the mapped spot and scale with the width of the face.
"""
import json, os, re, sys
import cv2
import numpy as np
from svgelements import Path, Move, Line, CubicBezier, QuadraticBezier, Close
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fit_bodies import place, render, R, X0, Y0
from compose_kit import ZONES, EYE_ANCHOR

# kittens' eyes are large for their faces; others scale with face width alone
EYE_BOOST = {"kitten": 1.15}

# Paws and stockings follow each sketch's own leg lines rather than the warp, since every drawing puts its feet
# somewhere slightly different. Read off each drawing in kit units: feet = (left x, right x) at the floor for front
# left, front right and hind foot; legs = the same three at stocking height, following the slant of the leg lines.
# k = how tall the white reaches, relative to the original cat (the kitten is shorter).
FEET = {
    "kitten": {"feet": [(50, 123), (124, 156), (157, 218)], "legs": [(52, 135), (136, 171), (172, 222)], "k": 0.7},
    "slender": {"feet": [(44, 109), (110, 140), (141, 180)], "legs": [(46, 113), (114, 154), (148, 187)], "k": 1.0},
    "chunky": {"feet": [(54, 108), (110, 172), (173, 230)], "legs": [(44, 90), (92, 194), (188, 232)], "k": 1.0},
}


def foot(bottom_x, top_y, top_x=None, bottom=492):
    """One white foot or leg: a gently scalloped top edge (toes), down to below the floor."""
    x0, x1 = top_x or bottom_x
    w = x1 - x0
    return (f"M{x0:.1f},{top_y + 6:.1f} C{x0 + .13 * w:.1f},{top_y - 4:.1f} {x0 + .31 * w:.1f},{top_y + 2:.1f} {x0 + .46 * w:.1f},{top_y - 4:.1f} "
            f"C{x0 + .6 * w:.1f},{top_y + 2:.1f} {x0 + .8 * w:.1f},{top_y - 6:.1f} {x1:.1f},{top_y + 4:.1f} "
            f"L{bottom_x[1] + 2:.1f},{bottom} L{bottom_x[0] - 2:.1f},{bottom} Z")


def feet_zones(name, floor):
    spec = FEET[name]
    k = spec["k"]
    paws = " ".join(foot(f, floor - 30 * k) for f in spec["feet"])
    tops = [floor - 100 * k, floor - 100 * k, floor - 72 * k]
    stockings = " ".join(foot(f, t, l) for f, l, t in zip(spec["feet"], spec["legs"], tops))
    return {"paws": paws, "stockings": stockings}


def affine_path(d, s, tx, ty):
    """Sketch-pixel path (absolute x,y pairs, as potrace writes them) -> kit units."""
    return re.sub(r"(-?[\d.]+),(-?[\d.]+)",
                  lambda m: f"{s * float(m.group(1)) + tx:.2f},{s * float(m.group(2)) + ty:.2f}", d)


class Frame:
    """Landmarks and row extents of one silhouette, in kit units."""

    def __init__(self, mask, nose):
        self.nose_x, self.nose_y = nose
        rows = np.nonzero(mask.any(1))[0]
        self.y = Y0 + np.arange(mask.shape[0]) / R
        L = np.full(mask.shape[0], np.nan); Rt = np.full(mask.shape[0], np.nan)
        for r in rows:
            xs = np.nonzero(mask[r])[0]
            L[r], Rt[r] = X0 + xs.min() / R, X0 + xs.max() / R
        self.top, self.floor = self.y[rows.min()], self.y[rows.max()]
        # crown: lowest point of the head's top edge between the ears
        cols = np.nonzero(mask.any(0))[0]
        tops = np.array([np.argmax(mask[:, c]) for c in cols])
        cx = X0 + cols / R
        left_ear = cx < self.nose_x; right_ear = ~left_ear
        lx = cx[left_ear][np.argmin(tops[left_ear])]; rx = cx[right_ear][np.argmin(tops[right_ear])]
        between = (cx > lx) & (cx < rx)
        self.crown = Y0 + tops[between].max() / R
        # above the crown the rows cut through the ears; hold the extents at the crown's
        cr = int((self.crown - Y0) * R)
        L[:cr], Rt[:cr] = L[cr], Rt[cr]
        # the last rows only catch the bottoms of the paws; hold the extents from just above them
        fl = int((self.floor - 14 - Y0) * R)
        L[fl:], Rt[fl:] = L[fl], Rt[fl]
        valid = ~np.isnan(L)
        idx = np.arange(len(L))
        L = np.interp(idx, idx[valid], L[valid]); Rt = np.interp(idx, idx[valid], Rt[valid])
        self.L = cv2.GaussianBlur(L.reshape(-1, 1), (1, 0), sigmaX=0, sigmaY=4 * R).ravel()
        self.R = cv2.GaussianBlur(Rt.reshape(-1, 1), (1, 0), sigmaX=0, sigmaY=4 * R).ravel()
        width = self.R - self.L
        band = (self.y > self.nose_y + 15) & (self.y < self.nose_y + 0.35 * (self.floor - self.nose_y))
        self.neck = self.y[band][np.argmin(width[band])]
        low = self.y > self.neck + 0.3 * (self.floor - self.neck)
        self.haunch = self.y[low][np.argmax(width[low])]
        self.anchors = np.array([self.top, self.crown, self.nose_y, self.neck, self.haunch, self.floor])

    def ext(self, y):
        return np.interp(y, self.y, self.L), np.interp(y, self.y, self.R)

    def width(self, y):
        l, r = self.ext(y)
        return r - l


def piecewise(v, src, dst):
    """Piecewise-linear map through matched anchors, extended past the ends with the end slopes."""
    v = np.asarray(v, float)
    out = np.interp(v, src, dst)
    lo, hi = v < src[0], v > src[-1]
    out[lo] = dst[0] + (v[lo] - src[0]) * (dst[1] - dst[0]) / (src[1] - src[0])
    out[hi] = dst[-1] + (v[hi] - src[-1]) * (dst[-1] - dst[-2]) / (src[-1] - src[-2])
    return out


def make_warp(a, b):
    def warp(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        y2 = piecewise(y, a.anchors, b.anchors)
        la, ra = a.ext(y); lb, rb = b.ext(y2)
        x2 = np.where(x < a.nose_x,
                      b.nose_x + (x - a.nose_x) * (b.nose_x - lb) / (a.nose_x - la),
                      b.nose_x + (x - a.nose_x) * (rb - b.nose_x) / (ra - a.nose_x))
        return x2, y2
    return warp


STEP = 5.0  # kit units: segments are cut into pieces about this long before moving, so straight edges bend with the body


def _split_cubic(p0, p1, p2, p3, n):
    """Cut a cubic into n pieces (de Casteljau at even steps of t)."""
    out = []
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        def at(t):
            a = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
            da = 3 * ((1 - t) ** 2 * (p1 - p0) + 2 * (1 - t) * t * (p2 - p1) + t ** 2 * (p3 - p2))
            return a, da
        a, da = at(t0); b, db = at(t1)
        h = (t1 - t0) / 3
        out.append((a + da * h, b - db * h, b))
    return out


def warp_path(d, warp):
    p = Path(d)
    p.approximate_arcs_with_cubics()
    out = []
    def f(pts):
        xs, ys = warp([q[0] for q in pts], [q[1] for q in pts])
        return [f"{x:.2f},{y:.2f}" for x, y in zip(xs, ys)]
    V = lambda q: np.array([q.x, q.y], float)
    for seg in p:
        if isinstance(seg, Move):
            out.append("M" + f([V(seg.end)])[0])
        elif isinstance(seg, Close):
            if seg.start is not None and seg.end is not None:
                a, b = V(seg.start), V(seg.end)
                n = max(1, int(np.ceil(np.hypot(*(b - a)) / STEP)))
                if n > 1:
                    out.append("L" + " L".join(f([a + (b - a) * (i / n) for i in range(1, n)])))
            out.append("Z")
        elif isinstance(seg, Line):
            a, b = V(seg.start), V(seg.end)
            n = max(1, int(np.ceil(np.hypot(*(b - a)) / STEP)))
            out.append("L" + " L".join(f([a + (b - a) * (i / n) for i in range(1, n + 1)])))
        elif isinstance(seg, (CubicBezier, QuadraticBezier)):
            if isinstance(seg, QuadraticBezier):
                q0, q1, q2 = V(seg.start), V(seg.control), V(seg.end)
                c = (q0, q0 + 2 / 3 * (q1 - q0), q2 + 2 / 3 * (q1 - q2), q2)
            else:
                c = (V(seg.start), V(seg.control1), V(seg.control2), V(seg.end))
            length = sum(np.hypot(*(c[i + 1] - c[i])) for i in range(3))
            n = max(1, int(np.ceil(length / STEP)))
            for c1, c2, e in _split_cubic(*c, n):
                out.append("C" + " ".join(f([c1, c2, e])))
    return " ".join(out)


def main():
    raw_path, fit_path, parts_path, out = sys.argv[1:5]
    B = json.load(open(raw_path)); F = json.load(open(fit_path)); P = json.load(open(parts_path))
    with sync_playwright() as p:
        b = p.chromium.launch()
        kit_mask = render([P["silhouette"]], b.new_page()).astype(bool)
        b.close()
    ft = F["bodies"]["typical"]
    nose_t = (ft["s"] * B["typical"]["nose_centre"][0] + ft["tx"], ft["s"] * B["typical"]["nose_centre"][1] + ft["ty"])
    A = Frame(kit_mask, nose_t)
    res = {"typical": {"anchors": A.anchors.round(1).tolist()}}
    for name in ["kitten", "slender", "chunky"]:
        f = F["bodies"][name]; r = B[name]
        mask = place(np.load(os.path.join(os.path.dirname(raw_path) or ".", f"sil_{name}.npy")), r["crop"], f["s"], f["tx"], f["ty"])
        nose = (f["s"] * r["nose_centre"][0] + f["tx"], f["s"] * r["nose_centre"][1] + f["ty"])
        Bf = Frame(mask, nose)
        warp = make_warp(A, Bf)
        ax, ay = warp([EYE_ANCHOR[0]], [EYE_ANCHOR[1]])
        eye_scale = Bf.width(ay[0]) / A.width(EYE_ANCHOR[1]) * EYE_BOOST.get(name, 1.0)
        res[name] = {
            "anchors": Bf.anchors.round(1).tolist(),
            "silhouette": affine_path(r["silhouette"], f["s"], f["tx"], f["ty"]),
            "outline": affine_path(r["outline"], f["s"], f["tx"], f["ty"]),
            "nose": affine_path(r["nose"], f["s"], f["tx"], f["ty"]),
            "stripes": warp_path(P["stripes"], warp),
            "zones": {**{k: warp_path(d, warp) for k, _, d in ZONES}, **feet_zones(name, Bf.floor)},
            "eyes": {"from": list(EYE_ANCHOR), "to": [round(float(ax[0]), 2), round(float(ay[0]), 2)],
                     "scale": round(float(eye_scale), 3)},
        }
        print(name, "anchors", res[name]["anchors"], "eyes", res[name]["eyes"], file=sys.stderr)
    print("typical anchors", res["typical"]["anchors"], file=sys.stderr)
    json.dump(res, open(out, "w"))


if __name__ == "__main__":
    main()

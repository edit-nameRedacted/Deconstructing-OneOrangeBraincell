"""Turn the two single-stroke tail drawings into a centreline and a width profile.

Usage: python3 tail_geometry.py ../source_drawings/tail_long.svg ../source_drawings/tail_short.svg tail_geometry.json

Each drawing is one open stroke: up one edge from the base, round the tip, down the other edge. The stroke is
closed across the base and filled; the centreline is the fill's medial axis from the middle of the base to the
far end of the tip, and the width at each point is twice the distance to the nearest edge. Units are the
drawing's own; the base is the line between the stroke's two ends.
"""
import json, re, sys
from collections import deque
import cv2
import numpy as np
from skimage.morphology import skeletonize
from svgelements import Path

N = 120   # centreline points
S = 8     # raster px per unit


def load(path):
    d_attr = re.search(r'<path[^>]* d="([^"]+)"', open(path).read()).group(1)
    p = Path(d_attr)
    pts = np.array([[q.x, q.y] for q in (p.point(i / 4000) for i in range(4001))])
    lo = pts.min(0) - 4
    poly = ((pts - lo) * S).round().astype(np.int32)
    H, W = poly[:, 1].max() + 8 * S, poly[:, 0].max() + 8 * S
    fill = np.zeros((H, W), np.uint8)
    cv2.fillPoly(fill, [poly], 1)
    dt = cv2.distanceTransform(fill, cv2.DIST_L2, 5)
    sk = skeletonize(fill > 0)
    ys, xs = np.nonzero(sk)
    base_mid = (pts[0] + pts[-1]) / 2
    bm = (base_mid - lo) * S
    start = int(np.argmin(np.hypot(xs - bm[0], ys - bm[1])))
    # walk the skeleton from the base; the far end is the tip
    idx = {(y, x): i for i, (y, x) in enumerate(zip(ys, xs))}
    dist = np.full(len(xs), -1); prev = np.full(len(xs), -1)
    dist[start] = 0; q = deque([start])
    while q:
        i = q.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                j = idx.get((ys[i] + dy, xs[i] + dx))
                if j is not None and dist[j] < 0:
                    dist[j] = dist[i] + 1; prev[j] = i; q.append(j)
    end = int(np.argmax(dist))
    chain = [end]
    while prev[chain[-1]] >= 0:
        chain.append(prev[chain[-1]])
    chain = chain[::-1]
    c = np.c_[xs[chain], ys[chain]].astype(float)
    w = 2 * dt[ys[chain], xs[chain]]
    # carry the centreline on to the tip's edge along its last direction
    dirv = c[-1] - c[-min(len(c), 6 * S)]
    dirv /= np.linalg.norm(dirv)
    extra = [c[-1] + dirv * t for t in np.arange(1, w[-1] / 2 + 1)]
    c = np.vstack([c, extra]); w = np.r_[w, np.linspace(w[-1], 0, len(extra))]
    c = cv2.GaussianBlur(c.reshape(-1, 1, 2), (1, 0), sigmaX=0, sigmaY=3 * S).reshape(-1, 2)
    w = cv2.GaussianBlur(w.reshape(-1, 1), (1, 0), sigmaX=0, sigmaY=2 * S).ravel()
    # back to drawing units, evenly spaced
    c = c / S + lo; w = w / S
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    t = np.linspace(0, d[-1], N)
    centre = np.c_[np.interp(t, d, c[:, 0]), np.interp(t, d, c[:, 1])]
    width = np.interp(t, d, w)
    width[0] = np.hypot(*(pts[0] - pts[-1]))  # the base is as wide as the gap between the stroke's ends
    width[-1] = 0
    stroke = pts[::5]  # 801 points along the drawn stroke
    stations = ladder(stroke, centre)
    return {"centre": centre.round(2).tolist(), "width": width.round(2).tolist(), "d": d_attr,
            "base": [pts[0].round(2).tolist(), pts[-1].round(2).tolist()], "length": round(float(d[-1]), 1),
            "stroke": stroke.round(2).tolist(), "stations": stations}


def ray_hits(c, n, P):
    """Distances t > 0 along c + t*n where the ray crosses the polyline P, with the crossing's index on P."""
    p, q = P[:-1], P[1:]
    e = q - p
    den = n[0] * e[:, 1] - n[1] * e[:, 0]
    ok = np.abs(den) > 1e-9
    w = p - c
    t = np.where(ok, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / np.where(ok, den, 1), np.inf)
    u = np.where(ok, (w[:, 0] * n[1] - w[:, 1] * n[0]) / np.where(ok, den, 1), -1)
    good = ok & (t > 0.01) & (u >= 0) & (u <= 1)
    if not good.any():
        return None
    k = int(np.argmin(np.where(good, t, np.inf)))
    return k + float(u[k])


def ladder(stroke, centre, n_st=61):
    """Stations across the tail: at evenly spaced centreline points, where the cross-line meets each edge.

    Each station is [a, b]: positions on the stroke (fractional point index) on the first edge (from the stroke's
    start) and on the second edge (from its end). Station 0 is the base (the stroke's two ends); the last is the tip."""
    tip = None
    T = np.gradient(centre, axis=0); T /= np.linalg.norm(T, axis=1)[:, None]
    Nrm = np.c_[-T[:, 1], T[:, 0]]
    picks = np.linspace(0, len(centre) - 1, n_st).round().astype(int)
    out = [[0.0, float(len(stroke) - 1)]]
    for i in picks[1:-1]:
        h1, h2 = ray_hits(centre[i], Nrm[i], stroke), ray_hits(centre[i], -Nrm[i], stroke)
        if h1 is None or h2 is None:
            out.append(None); continue
        a, b = sorted([h1, h2])
        out.append([a, b])
    # the tip: where the stroke doubles back, nearest the centreline's end
    k = int(np.argmin(np.hypot(*(stroke - centre[-1]).T)))
    out.append([float(k), float(k)])
    # fill misses, then keep each edge moving steadily toward the tip
    for j, v in enumerate(out):
        if v is None:
            lo = next(x for x in out[j - 1::-1] if x is not None); hi = next(x for x in out[j + 1:] if x is not None)
            out[j] = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
    a = np.maximum.accumulate([v[0] for v in out]); b = np.minimum.accumulate([v[1] for v in out])
    a = np.minimum(a, k); b = np.maximum(b, k)
    return [[round(float(x), 2), round(float(y), 2)] for x, y in zip(a, b)]


long_, short_, out = sys.argv[1:4]
G = {"long": load(long_), "short": load(short_)}
for k, g in G.items():
    w = np.array(g["width"])
    print(k, "base", g["centre"][0], "tip", g["centre"][-1], "length", g["length"], "width base/max",
          w[0].round(1), w.max().round(1), file=sys.stderr)
json.dump(G, open(out, "w"))

"""Trace the body-type sketch: outline strokes, filled silhouette and nose fill for each cat.

Usage: python3 trace_bodies.py bodies_sketch.jpg bodies_raw.json

Output per body, in sketch pixels: outline path (the ink strokes), silhouette path (inside of the outline,
gaps bridged), nose path (the inside of the nose), and landmarks used to place the body (nose centre, floor).
The silhouette mask is also saved as sil_<name>.npy (with its crop offset) for finding landmarks.
"""
import json, sys
import cv2
import numpy as np
import potrace
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize

# ink bounding box of each cat in the sketch (x, y, w, h) and of its nose; a margin is added when cropping
BODIES = {
    "typical": ((335, 443, 519, 867), (475, 643, 69, 83)),
    "kitten": ((921, 758, 361, 538), (994, 871, 79, 75)),
    "slender": ((392, 1391, 461, 865), (476, 1557, 69, 78)),
    "chunky": ((1084, 1364, 570, 867), (1228, 1565, 67, 84)),
}
MARGIN = 30
MAX_GAP = 75  # px: open spots in an outline up to this wide are bridged when finding its inside
UP = 3  # strokes are traced from a 3x enlargement so the curves come out smooth


def to_path(mask, ox, oy, k=1.0, turd=30, alphamax=1.0, tol=0.5):
    plist = potrace.Bitmap(~mask.astype(bool)).trace(turdsize=turd, alphamax=alphamax, opticurve=True, opttolerance=tol)
    f = lambda p: f"{ox + p.x / k:.2f},{oy + p.y / k:.2f}"
    out = []
    for c in plist:
        out.append("M" + f(c.start_point))
        for s in c.segments:
            out.append(("L" + f(s.c) + " L" + f(s.end_point)) if s.is_corner
                       else ("C" + f(s.c1) + " " + f(s.c2) + " " + f(s.end_point)))
        out.append("Z")
    return " ".join(out)


def bridge_gaps(ink, maxgap):
    """Draw a line from each stroke end to the nearest other stroke (or stroke end) within maxgap px.

    Unlike thickening every stroke, this closes the open spots without pulling the fill away from them."""
    skel = skeletonize(ink > 0).astype(np.uint8)
    nb = cv2.filter2D(skel, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - skel
    ends = np.argwhere((skel == 1) & (nb == 1))
    _, lab = cv2.connectedComponents(ink, connectivity=8)
    pix = np.argwhere(ink > 0)
    tree = cKDTree(pix)
    end_set = {tuple(e) for e in ends}
    out = ink.copy()
    for e in ends:
        best = None
        for j in tree.query_ball_point(e, maxgap):
            q = pix[j]
            other = lab[q[0], q[1]] != lab[e[0], e[1]]
            far_end = tuple(q) in end_set and np.hypot(*(q - e)) > 12
            if other or far_end:
                dd = np.hypot(*(q - e))
                if best is None or dd < best[0]:
                    best = (dd, q)
        if best is not None:
            cv2.line(out, (int(e[1]), int(e[0])), (int(best[1][1]), int(best[1][0])), 1, 5)
    return out


def fill_inside(ink, maxgap, G=7):
    """Everything enclosed by the strokes once gaps up to maxgap px are bridged."""
    ink = bridge_gaps(ink, maxgap)
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (G, G))
    thick = cv2.dilate(ink, disc)
    pad = cv2.copyMakeBorder((1 - thick).astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
    cv2.floodFill(pad, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 2)
    inside = (pad[1:-1, 1:-1] != 2).astype(np.uint8)
    # undo the thickening (the fill then stops at the middle of the strokes), add back the strokes themselves
    return cv2.bitwise_or(cv2.erode(inside, disc), ink & inside)


def main():
    src, out = sys.argv[1], sys.argv[2]
    grey = cv2.imread(src, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    dark = 1 - grey
    res = {}
    for name, ((x, y, w, h), (nx, ny, nw, nh)) in BODIES.items():
        x, y, w, h = x - MARGIN, y - MARGIN, w + 2 * MARGIN, h + 2 * MARGIN
        d = dark[y:y + h, x:x + w]
        ink = (cv2.GaussianBlur(d, (0, 0), 1.0) > 0.45).astype(np.uint8)
        # drop stray marks: pieces of ink lying outside the convex outline of the main strokes
        n0, lab0, st0, cen0 = cv2.connectedComponentsWithStats(ink, 8)
        mains = [i for i in range(1, n0) if st0[i, 4] > 0.05 * ink.sum()]
        main_hull = cv2.convexHull(cv2.findNonZero(np.isin(lab0, mains).astype(np.uint8)))
        for i in range(1, n0):
            if cv2.pointPolygonTest(main_hull, (float(cen0[i][0]), float(cen0[i][1])), True) < -3:
                ink[lab0 == i] = 0
                d = d * (lab0 != i)
        inside = fill_inside(ink, MAX_GAP)
        n, lab, st, _ = cv2.connectedComponentsWithStats(inside, 8)
        sil = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
        sil = (cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 2.5) > 0.5).astype(np.uint8)
        # strokes: keep only ink that belongs to the cat (drops stray marks), trace from a smoothed enlargement
        near = cv2.dilate(sil, np.ones((9, 9), np.uint8))
        n2, lab2, _, _ = cv2.connectedComponentsWithStats(ink, 8)
        keep_ids = [i for i in range(1, n2) if (near[lab2 == i] > 0).mean() > 0.6]
        keep = np.isin(lab2, keep_ids)
        big = cv2.resize(d * keep, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
        strokes = cv2.GaussianBlur(big, (0, 0), 0.9 * UP) > 0.42
        # nose fill: hull of the nose's upper loop (the part above where the mouth lines start)
        lx, ly = nx - x, ny - y
        nose_ink = ink[ly:ly + int(nh * 0.52), lx:lx + nw]
        pts = cv2.findNonZero(nose_ink)
        nose = np.zeros_like(ink)
        if pts is not None:
            hull = cv2.convexHull(pts + np.array([[lx, ly]]))
            cv2.fillConvexPoly(nose, hull, 1)
        ys, xs = np.nonzero(sil)
        res[name] = {
            "crop": [x, y, w, h],
            "outline": to_path(strokes, x, y, k=UP, turd=40 * UP * UP, tol=0.4),
            "silhouette": to_path(sil, x, y, turd=400, alphamax=1.2, tol=0.8),
            "nose": to_path(nose, x, y, turd=10),
            "nose_centre": [nx + nw / 2, ny + nh * 0.25],
            "floor": float(y + ys.max()),
            "top": float(y + ys.min()),
        }
        np.save(f"sil_{name}.npy", sil)
        print(name, "silhouette px", int(sil.sum()), file=sys.stderr)
    json.dump(res, open(out, "w"))


if __name__ == "__main__":
    main()

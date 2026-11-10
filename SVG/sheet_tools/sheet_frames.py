"""Cut a sheet of cat drawings into frames, line them up, read where the eyes and nose are, and trace each frame.

Usage:  python3 sheet_frames.py SHEET.jpg --out OUTDIR [--min-height 0.5] [--keep-eyes]

For each sheet:
  1. Finds the drawings: everything that isn't paper (near-white or grey, so grid lines and cell borders drop
     out), joined up, keeping only pieces at least --min-height of the tallest one, with real line work in them
     (so labels, numbers and faded sketches are skipped). Frames are numbered in reading order.
  2. Lines them up on one canvas: every frame is placed so the middle of its base (the bottom of the neck, or
     the feet) lands on the same point. Drawn on one sheet at one scale, that keeps them registered.
  3. Reads the cues each frame already has: each eye (the white, the pupil inside it, the eye's size and
     tilt) and the nose. Eyes that are shut (no white) are reported as closed. These go in cues.json, in the
     shared canvas's pixels, so the kit's own eyes and features can be placed where the drawing had them.
  4. Traces each frame into layers with trace_layers.py, after painting the drawn eyes over with the
     surrounding fur (unless --keep-eyes), so the kit's eyes can go on top cleanly.
Writes OUTDIR/frame_NN.png (aligned crop), frame_NN.svg (layers) and cues.json.
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trace_layers as tl   # noqa: E402


def ink_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    return (s > 45) | (v < 140)          # orange/brown fills or dark lines; paper, grid and borders are neither


def find_frames(img, min_height):
    ink = ink_mask(img).astype(np.uint8)
    k = max(5, round(0.0125 * max(img.shape[:2])))    # join a drawing's loose bits (25 px on a 2000 px sheet), scaled
    joined = cv2.dilate(ink, np.ones((k, k), np.uint8))  # so neighbouring drawings on a smaller sheet stay apart
    n, comp, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    dark = hsv[:, :, 2] < 90
    boxes = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        piece = (comp == i) & ink.astype(bool)
        if dark[comp == i].sum() < 400:   # no real line work: a faded sketch
            continue
        # a label printed just under the feet gets joined to the drawing: drop ink lying wholly below the drawing's
        # lowest point (nothing of a sitting or standing cat is below its own feet)
        pn, pc, ps, _ = cv2.connectedComponentsWithStats(piece.astype(np.uint8), 8)
        if pn > 2:
            big = 1 + np.argmax(ps[1:, 4])
            floor = ps[big][1] + ps[big][3]
            below = [j for j in range(1, pn) if ps[j][1] >= floor - 2]
            if below:
                comp[np.isin(pc, below)] = 0
                ys, xs = np.nonzero(comp == i)
                x, y, w, h = xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        boxes.append((x, y, w, h, i))
    tallest = max(b[3] for b in boxes)
    boxes = [b for b in boxes if b[3] >= min_height * tallest]
    rows = sorted(boxes, key=lambda b: b[1])
    # reading order: group into rows by vertical overlap, then left to right
    ordered, row = [], []
    for b in rows:
        if row and b[1] > max(r[1] + r[3] * 0.5 for r in row):
            ordered += sorted(row, key=lambda r: r[0]); row = []
        row.append(b)
    ordered += sorted(row, key=lambda r: r[0])
    return ordered, comp, ink.astype(bool)


def base_anchor(mask):
    """Middle of the drawing's base: centre of the lowest 8% of its rows, and its lowest row."""
    ys, xs = np.nonzero(mask)
    y1 = ys.max()
    low = ys > y1 - 0.08 * (y1 - ys.min())
    return float(xs[low].mean()), float(y1)


def silhouette(img):
    """The drawing and everything enclosed by it (gaps up to ~15 px closed), as a bool mask."""
    H, W = img.shape[:2]
    filled = cv2.morphologyEx(ink_mask(img).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cv2.floodFill(filled, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 2)
    return filled != 2


def eyes_and_nose(img, inside, keep_single=False):
    """Eye whites (with pupils) and the nose, inside the drawing. A lone eye counts as none unless keep_single."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = [hsv[:, :, i].astype(int) for i in range(3)]
    white = (s < 30) & (v > 215) & inside
    white = cv2.morphologyEx(white.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, comp, stats, cent = cv2.connectedComponentsWithStats(white, 8)
    H = inside.shape[0]
    # whiskers crossing the outline close off pockets of paper that look like an eye white with a dark "pupil";
    # those touch the silhouette's edge, a real eye white sits well inside the head
    edge_dist = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
    W = inside.shape[1]
    pieces = [i for i in range(1, n)
              if stats[i][4] >= 25 and stats[i][2] <= 0.25 * W and stats[i][3] <= 0.25 * H
              and edge_dist[comp == i].min() >= 5]
    # a pupil can split one eye white into pieces, and a half-lidded eye leaves only a sliver of white: join pieces
    # that sit side by side (gap under ~3.5% of the canvas width, about a pupil; eyes sit much further apart) into one eye
    groups = []
    for i in sorted(pieces, key=lambda i: stats[i][0]):
        x, y, w, hh = stats[i][:4]
        for g in groups:
            gx1 = max(stats[j][0] + stats[j][2] for j in g)
            gy0, gy1 = min(stats[j][1] for j in g), max(stats[j][1] + stats[j][3] for j in g)
            if x - gx1 <= 0.035 * W and y < gy1 and y + hh > gy0:
                g.append(i); break
        else:
            groups.append([i])
    cands = []
    for g in groups:
        a = int(sum(stats[i][4] for i in g))
        # an eye white has a dark pupil inside its hull
        hull = cv2.convexHull(np.argwhere(np.isin(comp, g))[:, ::-1].astype(np.int32))
        region = np.zeros_like(white)
        cv2.fillConvexPoly(region, hull, 1)
        region = cv2.dilate(region, np.ones((5, 5), np.uint8)).astype(bool)
        pupil = region & (v < 90)
        if pupil.sum() < 30:
            continue
        both = region | pupil
        ys_, xs_ = np.nonzero(both)
        ex, ey = (xs_.min() + xs_.max()) / 2, (ys_.min() + ys_.max()) / 2   # centre and size of the eye's box
        ew, eh = xs_.max() - xs_.min() + 1, ys_.max() - ys_.min() + 1
        py, px = np.argwhere(pupil).mean(0)
        cands.append({"x": round(float(ex), 1), "y": round(float(ey), 1), "w": int(ew), "h": int(eh),
                      "pupil": [round(float(px), 1), round(float(py), 1)], "area": int(a), "_region": both})
    cands = sorted(cands, key=lambda c: -c["area"])[:2]
    if len(cands) < 2 and not (keep_single and cands):
        cands = []                                  # eyes shut (or one stray highlight): no eyes
    cands.sort(key=lambda c: c["x"])
    # the nose: a pink blob below the eyes, nearest the middle of the face
    pink = (h < 12) & (s > 50) & (s < 140) & (v > 150) & inside
    n, comp, stats, cent = cv2.connectedComponentsWithStats(pink.astype(np.uint8), 8)
    nose = None
    if cands:
        mx = np.mean([c["x"] for c in cands]); my = max(c["y"] for c in cands)
        best = None
        for i in range(1, n):
            if stats[i][4] < 60 or cent[i][1] < my:
                continue
            d = np.hypot(cent[i][0] - mx, cent[i][1] - my)
            if best is None or d < best[0]:
                best = (d, i)
        if best:
            i = best[1]
            nose = {"x": round(float(cent[i][0]), 1), "y": round(float(cent[i][1]), 1), "w": int(stats[i][2])}
    return cands, nose


def process_frame(canvas, name, out_dir, a, fill_eyes=None):
    """Read the eyes and nose off one registered frame, paint the eyes out, trace it. Writes name.png and name.svg.
    fill_eyes: eyes to use instead of the ones read here (in a sequence: none or only slivers were found, so they are
    taken from the frames either side); the drawn eyes are painted out over an oval the size of each eye's box."""
    H, W = canvas.shape[:2]
    eyes, nose = eyes_and_nose(canvas, silhouette(canvas))
    filled = bool(fill_eyes)
    if filled:
        eyes = []
        for e in fill_eyes:
            oval = np.zeros((H, W), np.uint8)
            cv2.ellipse(oval, (round(e["x"]), round(e["y"])), (int(e["w"]) // 2, int(e["h"]) // 2), 0, 0, 360, 1, -1)
            eyes.append({**e, "_region": oval.astype(bool)})
    cv2.imwrite(os.path.join(out_dir, name + ".png"), canvas)
    work = canvas.copy()
    if len(eyes) == 2 and not a.keep_eyes:     # one "eye" alone is a stray highlight: leave the drawing as it is
        # paint the drawn eyes (and their outlines) over with the nearest fur, so the kit's eyes replace them
        hole = np.zeros((H, W), np.uint8)
        for e in eyes:
            hole |= e["_region"].astype(np.uint8)
        hole = cv2.dilate(hole, np.ones((13, 13), np.uint8))
        work = cv2.inpaint(work, hole, 6, cv2.INPAINT_TELEA)
        # inpainting blurs; snap the patch to the fur colour around it
        ring = cv2.dilate(hole, np.ones((9, 9), np.uint8)).astype(bool) & ~hole.astype(bool)
        work[hole.astype(bool)] = np.median(work[ring], 0).astype(np.uint8)
    wpath = os.path.join(out_dir, name + "_noeyes.png")
    cv2.imwrite(wpath, work)
    tl.process(wpath, out_dir, a)
    os.replace(os.path.join(out_dir, name + "_noeyes.svg"), os.path.join(out_dir, name + ".svg"))
    os.remove(wpath)
    r = {"eyes": [{kk: vv for kk, vv in e.items() if not kk.startswith("_") and kk != "area"} for e in eyes],
         "eyes_closed": len(eyes) < 2, "nose": nose}
    if filled:
        r["eyes_filled"] = True
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-height", type=float, default=0.5)
    ap.add_argument("--keep-eyes", action="store_true")
    ap.add_argument("--line-min", type=float, default=0)
    ap.add_argument("--line-max", type=float, default=0)
    ap.add_argument("--speck", type=int, default=40)
    ap.add_argument("--open-bottom", type=float, default=0,
                    help="drop the outline along the bottom edge, within this share of the height (heads: 0.22)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    img = cv2.imread(a.sheet)
    frames, comp, ink = find_frames(img, a.min_height)
    # shared canvas: big enough for every frame, each placed by its base anchor
    pad = 20
    infos = []
    for (x, y, w, h, i) in frames:
        mask = (comp == i) & ink
        ax, ay = base_anchor(mask)
        infos.append((x, y, w, h, i, ax, ay))
    left = max(ax - x for x, y, w, h, i, ax, ay in infos) + pad
    right = max(x + w - ax for x, y, w, h, i, ax, ay in infos) + pad
    up = max(ay - y for x, y, w, h, i, ax, ay in infos) + pad
    down = max(y + h - ay for x, y, w, h, i, ax, ay in infos) + pad
    W, H = int(left + right), int(up + down)
    anchor = [round(left, 1), round(up, 1)]

    cues = {"sheet": os.path.basename(a.sheet), "canvas": [W, H], "base_anchor": anchor, "frames": []}
    for k, (x, y, w, h, i, ax, ay) in enumerate(infos, 1):
        ox, oy = int(round(ax - left)), int(round(ay - up))
        canvas = np.full((H, W, 3), 255, np.uint8)
        region = cv2.dilate(((comp == i) & ink).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        sx0, sy0 = max(ox, 0), max(oy, 0)
        sx1, sy1 = min(ox + W, img.shape[1]), min(oy + H, img.shape[0])
        crop = img[sy0:sy1, sx0:sx1].copy()
        keep = region[sy0:sy1, sx0:sx1]
        crop[~keep] = 255                                      # only this drawing, on plain white
        canvas[sy0 - oy:sy1 - oy, sx0 - ox:sx1 - ox] = crop
        name = f"frame_{k:02d}"
        r = process_frame(canvas, name, a.out, a)
        cues["frames"].append({"frame": k, "file": name + ".svg", **r, "sheet_box": [int(x), int(y), int(w), int(h)]})
        print(f"{name}: eyes {len(r['eyes'])}{' (closed?)' if r['eyes_closed'] else ''}, nose {'yes' if r['nose'] else 'no'}", file=sys.stderr)
    json.dump(cues, open(os.path.join(a.out, "cues.json"), "w"), indent=1)
    print(f"{len(infos)} frames on a {W}x{H} canvas -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

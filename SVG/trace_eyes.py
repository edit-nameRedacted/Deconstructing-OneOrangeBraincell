"""Trace the six eye pairs from a screenshot into one SVG with a named group per pair.

Usage: python3 trace_eyes.py eyes_screenshot.png cat_eyes.svg

Each pair becomes <g id="eyes-<name>"> holding <path id="eyes-<name>-left"> and "-right", in the screenshot's
pixel coordinates. The image is enlarged 8x and smoothed before tracing (potrace), then scaled back, so the
low-resolution screenshot still gives smooth curves.
"""
import sys
import cv2
import numpy as np
import potrace

SCALE = 8
PAIRS = ["almond", "squint", "big-shiny", "slit", "half-lidded", "round"]
# pairs whose outlines have small gaps: bridge gaps this wide (screenshot px) before filling the eye white
GAP_CLOSE = {"almond": 9, "slit": 9}
# round eyes whose white should fill their whole outer shape (convex hull)
HULL = {"big-shiny", "slit"}


def ink_mask(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4:  # dark ink on a transparent or white background
        alpha = im[:, :, 3].astype(np.float32) / 255
        grey = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        darkness = (1 - grey) * alpha
    else:
        darkness = 1 - cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    return darkness


def find_eyes(dark):
    ink = (dark > 0.5).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(ink, np.ones((7, 7), np.uint8)), 8)
    boxes = [tuple(int(v) for v in stats[i][:4]) for i in range(1, n) if stats[i][4] > 30]
    boxes.sort(key=lambda b: (b[1] // 40, b[0]))  # rows, then left to right
    return boxes


def trace_box(dark, box, pad=4, filled=False, close_px=0, hull=False):
    """Trace one eye. filled=True traces its silhouette with the holes filled in: the white of the eye."""
    x, y, w, h = box
    x0, y0 = max(0, x - pad), max(0, y - pad)
    crop = dark[y0:y + h + pad, x0:x + w + pad]
    big = cv2.resize(crop, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), SCALE * 0.6)
    ink = big > 0.5
    if filled:
        m = ink.astype(np.uint8)
        if close_px:  # bridge gaps in the outline so it has an inside; closing never grows past the convex hull
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px * SCALE | 1, close_px * SCALE | 1))
            m = cv2.morphologyEx(cv2.copyMakeBorder(m, close_px * SCALE, close_px * SCALE, close_px * SCALE, close_px * SCALE,
                                                    cv2.BORDER_CONSTANT, 0), cv2.MORPH_CLOSE, k)
            m = m[close_px * SCALE:-close_px * SCALE, close_px * SCALE:-close_px * SCALE]
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if hull and cs:
            cs = [cv2.convexHull(np.vstack([c for c in cs if cv2.contourArea(c) > 20 * SCALE * SCALE] or cs))]
        solid = np.zeros(ink.shape, np.uint8)
        cv2.drawContours(solid, cs, -1, 1, thickness=cv2.FILLED)
        ink = solid.astype(bool)
    bmp = potrace.Bitmap(~ink)  # potracer treats False as ink
    plist = bmp.trace(turdsize=SCALE * SCALE * 2, alphamax=1.0, opticurve=True, opttolerance=0.4)
    f = lambda p: f"{x0 + p.x / SCALE:.2f},{y0 + p.y / SCALE:.2f}"
    parts = []
    for curve in plist:
        parts.append("M" + f(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                parts.append("L" + f(seg.c) + " L" + f(seg.end_point))
            else:
                parts.append("C" + f(seg.c1) + " " + f(seg.c2) + " " + f(seg.end_point))
        parts.append("Z")
    return " ".join(parts)


def main():
    src, out = sys.argv[1], sys.argv[2]
    dark = ink_mask(src)
    boxes = find_eyes(dark)
    if len(boxes) != 2 * len(PAIRS):
        sys.exit(f"expected {2 * len(PAIRS)} eyes, found {len(boxes)}")
    # pair up: two eyes per pair, in reading order (row by row, left to right)
    groups, xs, ys = [], [], []
    for i, name in enumerate(PAIRS):
        l, r = sorted(boxes[2 * i:2 * i + 2])
        for b in (l, r):
            xs += [b[0], b[0] + b[2]]
            ys += [b[1], b[1] + b[3]]
        groups.append(
            f'  <g id="eyes-{name}" fill-rule="evenodd">\n'
            f'    <path class="eye-white" fill="#fff" d="{trace_box(dark, l, filled=True, close_px=GAP_CLOSE.get(name, 0), hull=name in HULL)}"/>\n'
            f'    <path class="eye-white" fill="#fff" d="{trace_box(dark, r, filled=True, close_px=GAP_CLOSE.get(name, 0), hull=name in HULL)}"/>\n'
            f'    <path id="eyes-{name}-left" d="{trace_box(dark, l)}"/>\n'
            f'    <path id="eyes-{name}-right" d="{trace_box(dark, r)}"/>\n  </g>')
    h, w = dark.shape
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" id="cat-eyes" fill="#000">\n'
           + "\n".join(groups) + "\n</svg>\n")
    open(out, "w", encoding="utf-8").write(svg)
    print(f"wrote {out}: {len(PAIRS)} pairs", file=sys.stderr)


if __name__ == "__main__":
    main()

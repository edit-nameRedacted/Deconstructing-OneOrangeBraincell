"""Place the traced sketch bodies in the kit's own units.

Usage: python3 fit_bodies.py bodies_raw.json ../smooth_parts.json bodies_fit.json

The sketch's top-left cat is the original. Its silhouette is fitted to the kit silhouette (scale and shift that
overlap them best); the same scale is used for every body, so the kitten stays smaller. Each body then stands on
the kit's floor, centred on the kit's nose.
Writes, per body, the transform from sketch pixels to kit units: x' = s*x + tx, y' = s*y + ty.
"""
import json, sys
import cv2
import numpy as np
from scipy.optimize import minimize
from playwright.sync_api import sync_playwright

R = 4                      # raster px per kit unit
X0, Y0, W, H = -80, -30, 460, 540   # kit-unit canvas used for comparing shapes


def render(paths, page):
    """Rasterise kit-unit paths (list of d strings) to a 0/1 mask on the canvas."""
    g = "".join(f'<path d="{d}" fill="#000"/>' for d in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{X0} {Y0} {W} {H}" width="{W * R}" height="{H * R}" '
           f'style="display:block">{g}</svg>')
    page.set_viewport_size({"width": W * R, "height": H * R})
    page.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
    img = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
    return (img < 128).astype(np.uint8)


def place(mask, crop, s, tx, ty):
    """Sketch-pixel mask (with its crop offset) -> canvas raster under x' = s*x + tx."""
    cx, cy = crop[0], crop[1]
    M = np.float32([[s * R, 0, (s * cx + tx - X0) * R], [0, s * R, (s * cy + ty - Y0) * R]])
    return cv2.warpAffine(mask.astype(np.float32), M, (W * R, H * R)) > 0.5


def main():
    raw_path, parts_path, out = sys.argv[1:4]
    B = json.load(open(raw_path))
    P = json.load(open(parts_path))
    with sync_playwright() as p:
        b = p.chromium.launch()
        kit = render([P["silhouette"]], b.new_page()).astype(bool)
        b.close()
    ys, xs = np.nonzero(kit)
    k_top, k_floor = Y0 + ys.min() / R, Y0 + ys.max() / R
    k_left, k_right = X0 + xs.min() / R, X0 + xs.max() / R
    t = B["typical"]
    sil = np.load("sil_typical.npy")
    sy, sx = np.nonzero(sil)
    s_top, s_floor = t["crop"][1] + sy.min(), t["crop"][1] + sy.max()
    s_left, s_right = t["crop"][0] + sx.min(), t["crop"][0] + sx.max()
    s0 = (k_floor - k_top) / (s_floor - s_top)
    x0 = [s0, (k_left + k_right) / 2 - s0 * (s_left + s_right) / 2, k_floor - s0 * s_floor]

    def loss(v):
        m = place(sil, t["crop"], *v)
        return -(m & kit).sum() / max(1, (m | kit).sum())

    fit = minimize(loss, x0, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-5, "maxiter": 400,
                                                             "initial_simplex": [x0, [x0[0] * 1.02, x0[1], x0[2]],
                                                                                 [x0[0], x0[1] + 3, x0[2]], [x0[0], x0[1], x0[2] + 3]]})
    s, tx, ty = fit.x
    print(f"typical fit: scale {s:.4f} units/px, overlap {-fit.fun:.3f}", file=sys.stderr)
    nose_kit_x = s * t["nose_centre"][0] + tx
    floor_kit = s * t["floor"] + ty
    res = {"scale": s, "kit_floor": floor_kit, "kit_nose_x": nose_kit_x, "bodies": {}}
    for name, r in B.items():
        if name == "typical":
            res["bodies"][name] = {"s": s, "tx": tx, "ty": ty}
        else:  # same scale; stand on the same floor, nose on the same vertical
            res["bodies"][name] = {"s": s, "tx": nose_kit_x - s * r["nose_centre"][0], "ty": floor_kit - s * r["floor"]}
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()

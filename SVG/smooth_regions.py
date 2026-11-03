"""Smooth the traced cat: re-trace the coat silhouette and the stripes as clean curves.

Usage: python3 smooth_regions.py cat_regions.svg smooth_parts.json

Renders chosen regions of cat_regions.svg as a mask at 6x, blurs it, and re-traces it with potrace.
Writes path data (in the cat's own viewBox units) for:
  silhouette  every coloured region together: the whole cat, used for the coat fill and as a clip
  stripes     body and forehead stripes
"""
import base64, json, sys
import cv2
import numpy as np
import potrace
from playwright.sync_api import sync_playwright

SCALE = 6
REGIONS = ["body", "stripes", "head-stripes", "legs", "leg-streaks", "paws", "face", "cheeks",
           "muzzle", "muzzle-shade", "belly", "belly-edge"]


def render_mask(svg, on, vbw, vbh, page):
    style = ";".join(f"--cat-{k}:{'#000' if k in on else '#fff'}" for k in REGIONS)
    w, h = int(vbw * SCALE), int(vbh * SCALE)
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(f'<html><body style="margin:0;background:#fff"><div style="{style}">'
                     + svg.replace("<svg ", f'<svg width="{w}" height="{h}" style="display:block" ', 1)
                     + "</div></body></html>")
    png = page.screenshot(full_page=False)
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    return (255 - img).astype(np.float32) / 255  # 1 = region


def trace(mask, blur_units, close_units=0, min_area_units=6):
    m = mask
    if close_units:
        k = max(1, int(close_units * SCALE)) | 1
        m = cv2.morphologyEx((m > 0.5).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), blur_units * SCALE)
    bmp = potrace.Bitmap(~(m > 0.5))  # potracer treats False as ink
    plist = bmp.trace(turdsize=int(min_area_units * SCALE * SCALE), alphamax=1.15, opticurve=True, opttolerance=0.6)
    f = lambda p: f"{p.x / SCALE:.2f},{p.y / SCALE:.2f}"
    out = []
    for c in plist:
        out.append("M" + f(c.start_point))
        for s in c.segments:
            out.append(("L" + f(s.c) + " L" + f(s.end_point)) if s.is_corner
                       else ("C" + f(s.c1) + " " + f(s.c2) + " " + f(s.end_point)))
        out.append("Z")
    return " ".join(out)


def main():
    src, out = sys.argv[1], sys.argv[2]
    svg = open(src, encoding="utf-8").read()
    import re
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        sil = render_mask(svg, set(REGIONS), vb[2], vb[3], page)
        stripes = render_mask(svg, {"stripes", "head-stripes"}, vb[2], vb[3], page)
        b.close()
    parts = {
        "viewBox": vb,
        # close small gaps between traced shapes, then soften the edge
        "silhouette": trace(sil, blur_units=1.6, close_units=3, min_area_units=40),
        "stripes": trace(stripes, blur_units=1.1, min_area_units=4),
    }
    json.dump(parts, open(out, "w"))
    print({k: len(v) for k, v in parts.items() if k != "viewBox"}, file=sys.stderr)


if __name__ == "__main__":
    main()

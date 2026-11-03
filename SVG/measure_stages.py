"""Measure how much of each body is white as the zones are added in spreading order.

Usage: python3 measure_stages.py cat_kit.svg white_stages.json

Writes {"order": [...], "white_pct_cumulative": {body: [0, after zone 1, after zone 2, ...]}}.
Outline and eyes are left out; the share is white area / (coloured + white) area of the cat.
"""
import json, re, sys
import cv2
import numpy as np
from playwright.sync_api import sync_playwright

kit_path, out = sys.argv[1:3]
kit = open(kit_path, encoding="utf-8").read()
order = re.findall(r'class="w-zone w-([\w-]+)"', kit)
order = list(dict.fromkeys(order))
bodies = list(dict.fromkeys(re.findall(r'class="body" data-body="([\w-]+)"', kit)))
hide = "<style>.outline,.eye-sets{display:none!important}</style>"
res = {"order": order, "white_pct_cumulative": {}}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 640, "height": 1000})
    for body in bodies:
        vals = []
        for i in range(len(order) + 1):
            s = kit.replace('data-body="typical" data-white=""', f'data-body="{body}" data-white="{" ".join(order[:i])}"', 1)
            s = s.replace("<svg ", '<svg width="640" height="1000" style="--cat-coat:#000;--cat-stripes:#000;--cat-white:#f00" ', 1)
            pg.set_content(f'<html><body style="margin:0;background:#fff">{hide}{s}</body></html>')
            img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_COLOR).astype(int)
            bl, g, r = img[..., 0], img[..., 1], img[..., 2]
            red = ((r > 180) & (g < 90)).sum()
            dark = ((r < 90) & (g < 90)).sum()
            vals.append(round(100 * red / max(1, red + dark), 1))
        res["white_pct_cumulative"][body] = vals
        print(body, vals, file=sys.stderr)
    b.close()
json.dump(res, open(out, "w"))

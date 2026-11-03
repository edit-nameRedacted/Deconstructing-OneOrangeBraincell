"""Write cat_tail.js: the tail module with the tail geometry filled in.

Usage: python3 build_tail_js.py tail_geometry.json cat_tail_template.js cat_tail.js
"""
import json, sys

geom, tpl, out = sys.argv[1:4]
G = json.load(open(geom))
slim = {k: {"stroke": [[round(x, 1), round(y, 1)] for x, y in g["stroke"]], "stations": g["stations"]} for k, g in G.items()}
js = open(tpl).read().replace("__TAIL_GEOMETRY__", json.dumps(slim, separators=(",", ":")))
open(out, "w").write(js)
print(f"wrote {out} ({len(js) // 1024} KB)", file=sys.stderr)

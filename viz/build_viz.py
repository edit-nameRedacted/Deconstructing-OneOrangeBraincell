"""Build oobc_cat_viz.html: the typical-cat visualization as one local page.
Usage (from the Orange_Braincells folder): python viz/build_viz.py"""
import json, os, re
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, ".."))
kit = open(os.path.join(root, "SVG", "cat_kit.svg"), encoding="utf-8").read()
kit = re.sub(r"<metadata>.*?</metadata>", "", kit, flags=re.S)
m = re.search(r"<style[^>]*>(.*?)</style>", kit, re.S)
kitcss = m.group(1).replace("#cat[", ".cat-kit[")
kit = kit.replace(m.group(0), "").replace('id="cat"', 'class="cat-kit"', 1)
S = json.load(open(os.path.join(root, "SVG", "white_stages.json")))["white_pct_cumulative"]
G = json.load(open(os.path.join(root, "SVG", "tails", "tail_geometry.json")))
slim = {k: {"stroke": [[round(x, 1), round(y, 1)] for x, y in g["stroke"]], "stations": g["stations"]} for k, g in G.items()}
tail = open(os.path.join(here, "cat_tail_viz_template.js"), encoding="utf-8").read().replace("__TAIL_GEOMETRY__", json.dumps(slim, separators=(",", ":")))
data = json.load(open(os.path.join(root, "oobc_archive", "viz", "oobc_viz_data.json"), encoding="utf-8"))
data.pop("groups", None)  # the page computes groups itself; the file keeps them for checking
page = open(os.path.join(here, "viz_template.html"), encoding="utf-8").read()
for k, v in {"__KITCSS__": kitcss, "__KIT__": kit.strip(), "__STAGES__": json.dumps(S), "__TAILJS__": tail,
             "__DATA__": json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}.items():
    page = page.replace(k, v)
out = os.path.join(here, "oobc_cat_viz.html"); open(out, "w", encoding="utf-8").write(page)
print(f"wrote {out} ({len(page) // 1024} KB)")

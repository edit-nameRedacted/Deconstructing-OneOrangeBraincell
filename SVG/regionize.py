"""Turn the Image Trace export into a cat with named colour regions.

Usage: python3 regionize.py "Asset 3.svg" paths.json cat_regions.svg

Every traced shape keeps its original drawing order. Each gets class="r-<region>", and each region's fill
is a CSS variable (--cat-<region>), so a page or a script can recolour the cat by setting those variables.
The traced belly shape also covers the muzzle; it is drawn twice, clipped at the neck, so the two can differ.
"""
import json, re, sys

src, info_path, out = sys.argv[1:4]
svg = open(src, encoding="utf-8").read()
info = {r["i"]: r for r in json.load(open(info_path))}
NECK_Y = 172   # viewBox units: belly below, muzzle above
ANKLE_Y = 440  # legs above, paws below

def rgb(s):
    return tuple(int(v) for v in re.findall(r"\d+", s)[:3])

def region(r):
    R, G, B = rgb(r["fill"])
    top = r["y"] + r["h"] / 2
    if R < 205 and G < 70:                       # dark magenta: stripes and legs
        if top < 90: return "head-stripes"
        if r["h"] > 150 or (r["y"] > 400 and r["w"] < 40 and 180 < r["x"] < 225): return "legs"
        return "stripes"
    if (R, G, B) == (231, 76, 140): return "face"  # ears and outer face mask
    if R >= 245 and 125 <= G <= 140: return "body"
    if 215 <= R <= 241 and 88 <= G <= 130 and B >= 185: return "leg-streaks"
    if 228 <= R <= 238 and 138 <= G <= 165 and 168 <= B <= 196: return "belly-edge"
    if 218 <= R <= 230 and 100 <= G <= 120 and B <= 95: return "cheeks"
    if (R, G, B) == (254, 203, 184): return "belly"  # split below
    if R >= 233 and 145 <= G <= 185 and 120 <= B <= 165: return "muzzle-shade"
    return "unassigned"

DEFAULTS = {  # an ordinary orange tabby with a cream chest
    "body": "#E8913A", "stripes": "#B4561E", "head-stripes": "var(--cat-stripes)", "legs": "var(--cat-body)",
    "leg-streaks": "var(--cat-stripes)", "paws": "var(--cat-legs)", "face": "#E08434", "cheeks": "#D26F28", "muzzle": "#F7E6D2",
    "muzzle-shade": "#EBCDB0", "belly": "#FBF3EA", "belly-edge": "#EBD9C6",
}

paths = list(re.finditer(r"<path\b[^>]*?/>", svg, re.S))
counts, out_paths = {}, []
for i, m in enumerate(paths):
    tag = m.group(0)
    reg = region(info[i])
    counts[reg] = counts.get(reg, 0) + 1
    tag = re.sub(r'class="[^"]*"', "", tag)
    if reg == "belly":
        out_paths.append(tag.replace("<path", '<path class="r-muzzle" clip-path="url(#above-neck)"', 1))
        out_paths.append(tag.replace("<path", '<path class="r-belly" clip-path="url(#below-neck)"', 1))
    elif reg in ("legs", "leg-streaks"):
        out_paths.append(tag.replace("<path", f'<path class="r-{reg}" clip-path="url(#above-ankle)" data-trace="{i}"', 1))
        out_paths.append(tag.replace("<path", f'<path class="r-paws" clip-path="url(#below-ankle)" data-trace="{i}"', 1))
    else:
        out_paths.append(tag.replace("<path", f'<path class="r-{reg}" data-trace="{i}"', 1))

vb = re.search(r'viewBox="([^"]+)"', svg).group(1)
W, H = [float(v) for v in vb.split()[2:4]]
def fallback(v):
    # "var(--cat-body)" -> "var(--cat-body, #E8913A)", so a borrowed colour still has a value when unset
    m = re.fullmatch(r"var\(--cat-([a-z-]+)\)", v)
    return f"var(--cat-{m.group(1)}, {fallback(DEFAULTS[m.group(1)])})" if m else v
style = "\n".join(f"    .r-{k} {{ fill: var(--cat-{k}, {fallback(v)}); }}" for k, v in DEFAULTS.items())
result = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" id="cat">
  <defs>
    <clipPath id="above-neck"><rect x="0" y="0" width="{W}" height="{NECK_Y}"/></clipPath>
    <clipPath id="above-ankle"><rect x="0" y="0" width="{W}" height="{ANKLE_Y}"/></clipPath>
    <clipPath id="below-ankle"><rect x="0" y="{ANKLE_Y}" width="{W}" height="{H - ANKLE_Y}"/></clipPath>
    <clipPath id="below-neck"><rect x="0" y="{NECK_Y}" width="{W}" height="{H - NECK_Y}"/></clipPath>
    <style>
{style}
    .r-unassigned {{ fill: #888; }}
    </style>
  </defs>
  <g id="cat-regions">
    {chr(10).join("    " + p for p in out_paths)}
  </g>
</svg>
'''
open(out, "w", encoding="utf-8").write(result)
print(counts, file=sys.stderr)

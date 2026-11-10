"""Assemble the cat kit: smoothed coat and stripes, smooth white-marking zones, outline, nose, and eye sets,
for each body type.

Usage: python3 compose_kit.py smooth_parts.json source_drawings/cat_v1_outline.svg source_drawings/cat_v1_eyes.svg cat_eyes.svg cat_kit.svg [bodies_kit.json]

Layers in each body, bottom to top: coat, stripes, white zones (clipped to that body), outline and nose, eyes.
Colours are CSS variables: --cat-coat, --cat-stripes, --cat-white, --cat-nose, --cat-outline, --cat-eye-white.
The <svg> attributes pick what shows:
  data-body     typical | kitten | slender | chunky  (bodies come from bodies_kit.json; typical is your original)
  data-white    white zones by name, e.g. data-white="chin muzzle blaze"
  data-eyes     one eye set, e.g. data-eyes="round"
  data-stripes  on | off
"""
import json, re, sys

# White zones in the original cat's units, placed from landmarks (nose ~94,122; eyes ~60,102 and ~125,103;
# chest from y 165; front paws x 40-100 and 145-197; hind foot x 185-225). Order = how white spreads.
ZONES = [
    ("chin", "Chin", "M95,145 m-15,8 a15,9 0 1,0 30,0 a15,9 0 1,0 -30,0 Z"),
    ("locket", "Chest locket", "M82,160 C88,165 102,165 108,160 C110,183 103,204 95,219 C87,204 80,183 82,160 Z"),
    ("muzzle", "Muzzle", "M72,133 C70,147 82,159 95,161 C108,159 120,147 118,133 C112,128 104,130 100,127 L90,127 C86,130 78,128 72,133 Z"),
    ("bib", "Chest bib", "M66,150 C76,162 114,162 124,150 C134,180 138,222 128,256 C120,276 108,292 95,300 "
                         "C82,292 70,276 62,256 C52,222 56,180 66,150 Z"),
    ("blaze", "Nose blaze", "M83,128 C86,117 89,106 91,96 C92,86 93,77 94,66 C95,77 96,86 97,96 C99,106 102,117 105,128 Z"),
    ("belly", "Belly", "M64,250 C80,262 112,262 128,250 C138,300 140,360 146,420 C148,450 150,470 151,492 L99,492 "
                       "C98,470 96,445 92,420 C86,370 74,300 64,250 Z"),
    ("paws", "Paws", "M37,456 C46,446 58,452 68,446 C78,452 92,444 104,454 L106,492 L35,492 Z "
                     "M141,456 C150,447 162,452 172,446 C182,452 192,445 199,455 L201,492 L139,492 Z "
                     "M184,440 C194,431 202,437 210,431 C218,436 224,434 228,441 L229,476 L184,476 Z"),
    ("stockings", "Stockings", "M38,384 C50,370 62,380 72,368 C82,378 94,368 102,380 L106,492 L35,492 Z "
                               "M143,382 C153,370 165,379 174,368 C184,378 193,369 198,381 L201,492 L139,492 Z "
                               "M182,414 C194,402 206,410 214,401 C222,408 226,404 229,414 L229,476 L182,476 Z"),
    ("face", "Lower face", "M30,140 C44,128 62,126 78,130 C84,118 89,104 94,92 C99,104 104,118 110,130 "
                          "C126,126 146,128 160,140 C164,160 150,176 124,180 C106,184 84,184 66,180 C40,176 26,160 30,140 Z"),
    ("body", "Body (mostly white)", "M0,205 C30,190 60,180 95,182 C130,180 165,190 200,200 C230,210 260,215 290,220 "
                                    "L290,492 L0,492 Z M222,330 C250,320 272,350 268,385 C264,418 236,430 214,412 "
                                    "C194,396 196,342 222,330 Z"),
]

BODY_LABELS = {"typical": "Typical", "kitten": "Kitten", "slender": "Slender", "chunky": "Chunky"}
EYE_SCALE = 0.855              # traced screenshot pixels -> cat units (matches your original eye width)
EYE_ANCHOR = (93.7, 97.7)      # centre of your original eye pair on the face
TRACED = {  # pair centre in screenshot pixels
    "almond": (108, 128), "squint": (115.5, 202.5), "big-shiny": (311, 222.5),
    "slit": (468.5, 227.5), "half-lidded": (118.5, 271), "round": (121.5, 335.5),
}


def inner(s):
    s = re.sub(r"<\?xml[^>]*>", "", s)
    s = re.sub(r"<defs>.*?</defs>", "", s, flags=re.S)
    return re.sub(r"^\s*<svg[^>]*>|</svg>\s*$", "", s.strip(), flags=re.S)


def zone_paths(ds):
    return "\n".join(f'      <path class="w-zone w-{k}" data-label="{label}" fill-rule="evenodd" d="{ds[k]}"/>'
                     for k, label, _ in ZONES)


def main():
    parts_path, outline_path, eyes_orig_path, eyes_traced_path, out = sys.argv[1:6]
    bodies = json.load(open(sys.argv[6])) if len(sys.argv) > 6 else {}
    P = json.load(open(parts_path))

    outline = inner(open(outline_path, encoding="utf-8").read())
    # the outline's white fills: the big one inside the nose becomes the nose colour, the speck in the foot becomes coat
    outline = re.sub(r'<path class="cls-1"', '<path class="k-nose"', outline)
    outline = re.sub(r'<polygon class="cls-1"', '<polygon class="k-coat"', outline)
    outline = re.sub(r"<path(?![^>]*class=)", '<path class="k-outline"', outline)

    eyes_orig = inner(open(eyes_orig_path, encoding="utf-8").read()).replace('class="cls-1"', 'class="k-eye-white"')
    traced = open(eyes_traced_path, encoding="utf-8").read()
    eye_groups = [f'<g class="eyes" data-set="original" transform="translate(42.4,86)">{eyes_orig}</g>']
    for name, (cx, cy) in TRACED.items():
        g = re.search(rf'<g id="eyes-{name}".*?</g>', traced, re.S).group(0)
        g = g.replace(f'<g id="eyes-{name}"', '<g', 1).replace('class="eye-white" fill="#fff"', 'class="k-eye-white"')
        tx, ty = EYE_ANCHOR[0] - EYE_SCALE * cx, EYE_ANCHOR[1] - EYE_SCALE * cy
        eye_groups.append(f'<g class="eyes" data-set="{name}" transform="translate({tx:.2f},{ty:.2f}) scale({EYE_SCALE})">{g}</g>')
    eyes_block = "\n".join("      " + g for g in eye_groups)

    # the original body
    clips = [f'<clipPath id="sil-typical"><path d="{P["silhouette"]}"/></clipPath>']
    groups = [f'''  <g class="body" data-body="typical" data-label="{BODY_LABELS["typical"]}">
    <path class="k-coat" d="{P["silhouette"]}"/>
    <path class="k-stripes" d="{P["stripes"]}"/>
    <g class="white-zones" clip-path="url(#sil-typical)">
{zone_paths({k: d for k, _, d in ZONES})}
    </g>
    <g class="outline" transform="translate(0,-4)">{outline}</g>
    <g class="eye-sets">
{eyes_block}
    </g>
  </g>''']
    xs, ys = [0, 290], [-6, 486]
    for name, b in bodies.items():
        if name == "typical":
            continue
        pts = [(float(a), float(c)) for a, c in re.findall(r"(-?[\d.]+),(-?[\d.]+)", b["outline"])]
        xs += [min(p[0] for p in pts), max(p[0] for p in pts)]
        ys += [min(p[1] for p in pts), max(p[1] for p in pts)]
        e = b["eyes"]
        eye_tf = (f'translate({e["to"][0]},{e["to"][1]}) scale({e["scale"]}) '
                  f'translate({-e["from"][0]},{-e["from"][1]})')
        clips.append(f'<clipPath id="sil-{name}"><path d="{b["silhouette"]}"/></clipPath>')
        groups.append(f'''  <g class="body" data-body="{name}" data-label="{BODY_LABELS.get(name, name)}">
    <path class="k-coat" d="{b["silhouette"]}"/>
    <path class="k-stripes" d="{b["stripes"]}" clip-path="url(#sil-{name})"/>
    <g class="white-zones" clip-path="url(#sil-{name})">
{zone_paths(b["zones"])}
    </g>
    <g class="outline"><path class="k-nose" d="{b["nose"]}"/><path class="k-outline" d="{b["outline"]}"/></g>
    <g class="eye-sets" transform="{eye_tf}">
{eyes_block}
    </g>
  </g>''')
    pad = 4
    x0, y0 = int(min(xs)) - pad, int(min(ys)) - pad
    vb = f"{x0} {y0} {int(max(xs)) + pad - x0} {int(max(ys)) + pad - y0}"

    names = ["typical", *[n for n in bodies if n != "typical"]]
    body_css = "\n".join(f'    #cat[data-body="{k}"] .body[data-body="{k}"] {{ display: inline; }}' for k in names)
    zone_css = "\n".join(f'    #cat[data-white~="{k}"] .w-{k} {{ display: inline; }}' for k, _, _ in ZONES)
    eye_css = "\n".join(f'    #cat[data-eyes="{k}"] .eyes[data-set="{k}"] {{ display: inline; }}' for k in ["original", *TRACED])
    clip_block = "\n".join("    " + c for c in clips)
    body_block = "\n".join(groups)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" id="cat" data-body="typical" data-white="" data-eyes="original" data-stripes="on">
  <defs>
{clip_block}
    <style>
    .body {{ display: none; }}
{body_css}
    .k-coat {{ fill: var(--cat-coat, #E8913A); }}
    .k-stripes {{ fill: var(--cat-stripes, #B4561E); }}
    #cat[data-stripes="off"] .k-stripes {{ display: none; }}
    .w-zone {{ fill: var(--cat-white, #FBF8F3); display: none; }}
{zone_css}
    .k-outline {{ fill: var(--cat-outline, #1B1714); }}
    .k-nose {{ fill: var(--cat-nose, #E7A49E); }}
    .k-eye-white {{ fill: var(--cat-eye-white, #FFFFFF); }}
    .eyes {{ display: none; fill: var(--cat-outline, #1B1714); }}
{eye_css}
    </style>
  </defs>
{body_block}
</svg>
'''
    open(out, "w", encoding="utf-8").write(svg)
    print(f"wrote {out}: {len(names)} bodies, {len(ZONES)} white zones, {len(eye_groups)} eye sets, viewBox {vb}",
          file=sys.stderr)


if __name__ == "__main__":
    main()

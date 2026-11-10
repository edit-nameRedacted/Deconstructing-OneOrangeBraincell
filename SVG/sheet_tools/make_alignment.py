"""Make the files for lining the head-turn heads up on the V2 body by hand (in Illustrator).

Usage:  python3 make_alignment.py HEADS_DIR V2_PARTS_DIR OUTDIR [--cut 128]
  HEADS_DIR     sheet_frames.py output for the head-turn sheet (run with --open-bottom), with cues.json
  V2_PARTS_DIR  SVG/V2/SVG (the hand-drawn V2 parts); assemble_v2.py and build_kit_v2.py must sit in its parent folder

Writes, all in V2 units (the units of the V2 outline):
  body_headless.svg     the V2 body with its head taken off: coat, body stripes, cream bib, fluff and outline,
                        inside a clipping mask whose top edge is the cut (--cut, just under the chin). Move the
                        mask's top edge in Illustrator to change the cut.
  head_N.svg            each head on its own, eyeless and open at the bottom, with a "cues" layer marking where
                        its eyes and nose were (rings and a dot), so the kit's eyes can be placed after aligning.
  align_head_turn.svg   all of it in one file: the headless body, the old V2 head faded (for reference), and the
                        five heads in one "Heads" group, already lined up with each other and roughly placed so
                        the front head's eyes sit where the V2 head's eyes were. Move or scale the Heads group to
                        align all five at once; only Head 3 (front) shows to start with.
Colours are written as plain fills so Illustrator keeps them.
"""
import argparse, json, os, re, sys

ROLE_FILL = {"coat": "#D78E34", "stripe": "#9D5224", "ear": "#C1886A", "cream": "#F5DAB5",
             "white": "#F5F4F3", "nose": "#CF9389", "line": "#462E29"}
EYE_ANCHOR_V2, EYE_SPACING_V2 = (60.6, 83.1), 47.0     # where the V2 kit puts the eyes (build_kit_v2.py)


def head_layers(svg_text):
    """The role groups of a traced frame, with plain fills instead of classes."""
    groups = re.findall(r'<g id="(\w+)" class="r-\w+">(.*?)</g>', svg_text, re.S)
    return "".join(f'<g id="{r}" fill="{ROLE_FILL[r]}" fill-rule="evenodd">{body}</g>' for r, body in groups)


def cue_layer(f, r):
    marks = "".join(f'<ellipse cx="{e["x"]}" cy="{e["y"]}" rx="{e["w"] / 2}" ry="{e["h"] / 2}"/>' for e in f["eyes"])
    marks += "".join(f'<circle cx="{e["x"]}" cy="{e["y"]}" r="{r}"/>' for e in f["eyes"])
    if f["nose"]:
        marks += f'<circle cx="{f["nose"]["x"]}" cy="{f["nose"]["y"]}" r="{r}"/>'
    return f'<g id="cues" fill="none" stroke="#1E90FF" stroke-width="{r / 2}">{marks}</g>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("heads")
    ap.add_argument("parts")
    ap.add_argument("out")
    ap.add_argument("--cut", type=float, default=128)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.abspath(a.parts)))
    from assemble_v2 import PLACE, elements, coat_path
    from build_kit_v2 import bib_fill, ellipse
    from playwright.sync_api import sync_playwright

    # ---- the V2 body, in V2 units ----
    parts = {f: elements(os.path.join(a.parts, f)) for f in PLACE}

    def placed(f, *roles):
        x, y = PLACE[f]
        els = [e for e in parts[f] if any(f'r-{r}"' in e for r in roles)]
        return f'<g transform="translate({x},{y})">' + "".join(re.sub(r'class="r-[\w-]+"', "", e) for e in els) + "</g>"

    coat = coat_path(parts["outline 1.svg"])
    fluff_ds = []
    fx, fy = PLACE["fluff 1.svg"]
    for e in parts["fluff 1.svg"]:
        d = re.search(r' d="([^"]+)"', e).group(1)
        fluff_ds.append(f'<path d="{d}" transform="translate({fx},{fy})"/>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        from build_kit_v2 import warp_d
        ident = lambda xx, yy: (xx, yy)
        world = [warp_d(re.search(r' d="([^"]+)"', e).group(1), ident, fx, fy) for e in parts["fluff 1.svg"]]
        bib = bib_fill(pg, world)
        b.close()
    L = ROLE_FILL["line"]
    body_layers = (f'<path id="coat" fill="{ROLE_FILL["coat"]}" d="{coat}"/>'
                   f'<g id="stripes" fill="{ROLE_FILL["stripe"]}">{placed("stripe pattern 1.svg", "stripe")}</g>'
                   f'<path id="bib" fill="{ROLE_FILL["cream"]}" d="{bib}"/>'
                   f'<g id="fluff" fill="{L}">{placed("fluff 1.svg", "line", "line-dark", "line-mid")}</g>'
                   f'<g id="outline" fill="{L}">{placed("outline 1.svg", "line")}</g>')
    W, H = 186, 368
    clip = f'<clipPath id="neck-cut"><rect x="-20" y="{a.cut}" width="230" height="{H}"/></clipPath>'
    body = f'<g id="Body_headless" clip-path="url(#neck-cut)">{body_layers}</g>'
    ref_clip = f'<clipPath id="head-only"><rect x="-20" y="-20" width="230" height="{a.cut + 20}"/></clipPath>'
    reference = (f'<g id="Reference_V2_head" opacity="0.3" clip-path="url(#head-only)">'
                 f'<path fill="{ROLE_FILL["coat"]}" d="{coat}"/>'
                 f'<g fill="{ROLE_FILL["stripe"]}">{placed("face stripe pattern 1.svg", "stripe")}</g>'
                 f'<g fill="{ROLE_FILL["ear"]}">{placed("ear 1 shading.svg", "ear")}</g>'
                 f'<g fill="{L}">{placed("outline 1.svg", "line")}{placed("ears 1.svg", "line")}{placed("mouth 1.svg", "line")}</g>'
                 f'<path fill="none" stroke="#1E90FF" stroke-width="0.8" d="{ellipse(EYE_ANCHOR_V2[0] - EYE_SPACING_V2 / 2, EYE_ANCHOR_V2[1], 9, 9)} {ellipse(EYE_ANCHOR_V2[0] + EYE_SPACING_V2 / 2, EYE_ANCHOR_V2[1], 9, 9)}"/>'
                 f'</g>')
    head = lambda vb, inner: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n<defs>{clip}{ref_clip}</defs>\n{inner}\n</svg>\n'
    open(os.path.join(a.out, "body_headless.svg"), "w").write(head(f"-6 -4 {W} {H}", body))

    # ---- the heads ----
    cues = json.load(open(os.path.join(a.heads, "cues.json")))
    front = next(f for f in cues["frames"] if f["frame"] == 3)
    (l, r) = front["eyes"]
    s = EYE_SPACING_V2 / (r["x"] - l["x"])
    tx = EYE_ANCHOR_V2[0] - s * (l["x"] + r["x"]) / 2
    ty = EYE_ANCHOR_V2[1] - s * (l["y"] + r["y"]) / 2
    cw, ch = cues["canvas"]
    heads = []
    for f in cues["frames"]:
        text = open(os.path.join(a.heads, f["file"])).read()
        layers = head_layers(text) + cue_layer(f, 6)
        k = f["frame"]
        open(os.path.join(a.out, f"head_{k}.svg"), "w").write(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cw} {ch}">\n<g id="Head_{k}">{layers}</g>\n</svg>\n')
        hide = "" if k == 3 else ' style="display:none"'
        heads.append(f'<g id="Head_{k}"{hide}>{layers}</g>')
    group = f'<g id="Heads" transform="matrix({s:.5f} 0 0 {s:.5f} {tx:.3f} {ty:.3f})">' + "".join(heads) + "</g>"
    open(os.path.join(a.out, "align_head_turn.svg"), "w").write(
        head(f"-6 -4 {W} {H}", body + "\n" + reference + "\n" + group))
    print(f"heads placed at scale {s:.4f} (head pixels -> V2 units); cut at y={a.cut}", file=sys.stderr)


if __name__ == "__main__":
    main()

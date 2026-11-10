"""Build the head-turn poses from hand alignments: each head travels with its own chest fluff.

Usage:  python3 build_head_poses.py ALIGN_SVG OUTDIR --pose 3=attached.svg:Head_3 --pose 4=folder.svg:Head_41
                                                     --pose 1=left1.svg:Head_1 [--bib 3="fwd 1.svg"]
  ALIGN_SVG   the align_head_turn.svg make_alignment.py wrote (the starting positions)
  --pose N=FILE:GROUP   a file in which head N was placed by hand (on the body), and that head's group id there
  --bib N=FILE          a file with pose N's bib and fluff placed by hand, when that isn't the head's file

For each hand-placed pose, the script measures, against the starting positions:
  - the head's move and scale (fitted to its ear and nose shapes, so trimmed lines don't throw it off), and
    keeps the drawn head shapes (with any trims);
  - the bib's and the fluff lines' move and stretch (from their boxes).
Poses not yet placed get a placement from their neighbours: between two placed poses, halfway; past the last
placed pose, the same as it. Those are marked "derived" in poses.json.

Writes, in V2 units (the units of the V2 outline), to OUTDIR:
  body_headless.svg   the body without its head, and now also without the bib and fluff (they belong to the head)
  pose_N_head.svg     the moving part for pose N: the head with its bib and fluff, and a "cues" layer (eyes, nose)
  pose_N.svg          the same on the body
  poses.json          per pose: where the head, bib and fluff go, the eye and nose positions, and the source
"""
import argparse, json, re, sys
import numpy as np
from svgelements import SVG, Group, Shape, Path

POSES = [1, 2, 3, 4, 5]
CREAM_SEAM = 0.9      # how far the head's cream is grown to hide the hairline at the bottom of its ruff (V2 units)


# ---------------------------------------------------------------------------- reading Illustrator's SVG
def css_classes(text):
    """Illustrator's <style>: class -> {property: value}."""
    out = {}
    style = "".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", style):
        props = dict((k.strip(), v.strip()) for k, v in (p.split(":", 1) for p in body.split(";") if ":" in p))
        for c in re.findall(r"\.([\w-]+)", sel):
            out.setdefault(c, {}).update(props)
    return out


def group_text(text, gid):
    """The full text of <g id="gid" ...> ... </g>, nested groups included."""
    m = re.search(rf'<g[^>]*\bid="{re.escape(gid)}"[^>]*>', text)
    if not m:
        return None
    depth, k = 0, m.start()
    while True:
        a, b = text.find("<g", k), text.find("</g>", k)
        if a != -1 and a < b:
            depth += 1; k = a + 2
        else:
            depth -= 1; k = b + 4
            if depth == 0:
                return text[m.start():k]


def inline_styles(fragment, classes):
    """Replace class="..." with the properties it stands for (so the fragment works in any file)."""
    def rep(m):
        props = {}
        for c in m.group(1).split():
            props.update(classes.get(c, {}))
        props.pop("display", None)                    # keep hidden layers visible here
        props.pop("clip-path", None)
        return " ".join(f'{k}="{v}"' for k, v in props.items())
    return re.sub(r'class="([^"]*)"', rep, fragment)


def boxes(path, ids):
    """Bounding boxes of named groups/paths (and of each head's ear and nose shapes), transforms applied."""
    out = {}
    def walk(g, head, role):
        for el in g:
            if isinstance(el, Group):
                nm = el.values.get("id") or ""
                h = nm if nm.startswith("Head_") else head
                r = re.sub(r"[-\d]+$", "", nm) if (h and nm and not nm.startswith("Head_")) else role
                if nm in ids and not h:                   # (heads have a "coat" group of their own)
                    h, r = None, nm
                walk(el, h, r)
            elif isinstance(el, Shape):
                key = (head, role) if head else ((el.values.get("id") if el.values.get("id") in ids else role), None)
                bb = Path(el).bbox()
                if bb and key[0]:
                    b = out.setdefault(key, [1e9, 1e9, -1e9, -1e9])
                    b[:] = [min(b[0], bb[0]), min(b[1], bb[1]), max(b[2], bb[2]), max(b[3], bb[3])]
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"display:\s*none;?", "", text).replace(' style="display:none"', "")
    walk(SVG.parse(__import__("io").StringIO(text), reify=True), None, None)
    return out


def layer_names(fragment):
    """Name a head's layers head_coat, head_line, head_cues ... (Illustrator's numbered copies such as "ear3"
    or "coat-2" lose their numbers); other ids are dropped so nothing clashes with the body's."""
    def rep(m):
        name = re.sub(r"[-\d]+$", "", m.group(1))
        keep = ("coat", "stripe", "ear", "cream", "nose", "line", "cues", "white")
        return f'id="head_{name}"' if name in keep else ""
    return re.sub(r'\bid="([^"]*)"', rep, fragment)


def fit_similarity(src_boxes, dst_boxes):
    """dst = s * src + t, least squares over box corners."""
    po = np.array([c for b in src_boxes for c in ((b[0], b[1]), (b[2], b[3]))])
    pa = np.array([c for b in dst_boxes for c in ((b[0], b[1]), (b[2], b[3]))])
    co, ca = po.mean(0), pa.mean(0)
    s = ((po - co) * (pa - ca)).sum() / ((po - co) ** 2).sum()
    t = ca - s * co
    rms = float(np.sqrt((((s * po + t) - pa) ** 2).sum(1).mean()))
    return float(s), t.tolist(), rms


def box_stretch(o, a):
    sx, sy = (a[2] - a[0]) / (o[2] - o[0]), (a[3] - a[1]) / (o[3] - o[1])
    return [sx, sy, a[0] - sx * o[0], a[1] - sy * o[1]]


# ---------------------------------------------------------------------------- build
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("align")
    ap.add_argument("out")
    ap.add_argument("--pose", action="append", required=True)
    ap.add_argument("--cues", help="cues.json of the traced heads (eye and nose positions)")
    ap.add_argument("--bib", action="append", default=[],
                    help="N=FILE: take pose N's bib and fluff placement from FILE instead of the head's file")
    a = ap.parse_args()
    import os
    os.makedirs(a.out, exist_ok=True)

    base_text = open(a.align, encoding="utf-8").read()
    base = boxes(a.align, {"bib", "fluff", "coat"})
    heads_m = re.search(r'<g id="Heads" transform="matrix\(([^)]+)\)"', base_text)
    M0 = [float(v) for v in heads_m.group(1).split()]          # head pixels -> V2 units, as first placed

    bib_files = {int(k): v for k, v in (b.split("=", 1) for b in a.bib)}
    placed = {}
    for spec in a.pose:
        n, rest = spec.split("=", 1)
        f, gid = rest.rsplit(":", 1)
        text = open(f, encoding="utf-8").read()
        B = boxes(f, {"bib", "fluff", "coat"})
        off = np.array(B[("coat", None)][:2]) - np.array(base[("coat", None)][:2])   # the body may sit elsewhere
        sub = lambda b: [b[0] - off[0], b[1] - off[1], b[2] - off[0], b[3] - off[1]]
        n = int(n)
        src = [base[(f"Head_{n}", r)] for r in ("ear", "nose")]
        dst = [sub(B[(gid, r)]) for r in ("ear", "nose")]
        s, t, rms = fit_similarity(src, dst)
        frag = inline_styles(group_text(text, gid), css_classes(text))
        frag = layer_names(frag)
        bib_src = f"{os.path.basename(f)}"
        if n in bib_files:                                  # the bib and fluff were placed in another file
            bf = bib_files[n]
            Bb = boxes(bf, {"bib", "fluff", "coat"})
            offb = np.array(Bb[("coat", None)][:2]) - np.array(base[("coat", None)][:2])
            subb = lambda b: [b[0] - offb[0], b[1] - offb[1], b[2] - offb[0], b[3] - offb[1]]
            bib_box, fluff_box, bib_src = subb(Bb[("bib", None)]), subb(Bb[("fluff", None)]), os.path.basename(bf)
        else:
            bib_box, fluff_box = sub(B[("bib", None)]), sub(B[("fluff", None)])
        placed[n] = {"source": f"head {os.path.basename(f)}:{gid}, bib and fluff {bib_src}",
                     "head_scale": s, "head_t": t, "fit_rms": rms,
                     "bib": box_stretch(base[("bib", None)], bib_box),
                     "fluff": box_stretch(base[("fluff", None)], fluff_box),
                     "shapes": f'<g transform="translate({-off[0]:.2f},{-off[1]:.2f})">{frag}</g>'}
        print(f"pose {n}: head scale {s:.3f}, move ({t[0]:.1f}, {t[1]:.1f}), fit {rms:.2f}", file=sys.stderr)

    # poses not yet placed: halfway between placed neighbours, or the same as the nearest one past the end
    poses = {}
    for n in POSES:
        if n in placed:
            poses[n] = dict(placed[n], derived=False)
            continue
        lo = max([k for k in placed if k < n], default=None)
        hi = min([k for k in placed if k > n], default=None)
        if lo is not None and hi is not None:
            w = (n - lo) / (hi - lo)
            mix = lambda x, y: (np.array(x) * (1 - w) + np.array(y) * w).tolist()
            P = {k: mix(placed[lo][k], placed[hi][k]) for k in ("head_scale", "head_t", "bib", "fluff")}
            how = f"between poses {lo} and {hi}"
        else:
            near = lo if lo is not None else hi
            P = {k: placed[near][k] for k in ("head_scale", "head_t", "bib", "fluff")}
            how = f"same as pose {near}"
        s, t = P["head_scale"], P["head_t"]
        orig = group_text(base_text, f"Head_{n}").replace(' style="display:none"', "")
        orig = layer_names(orig)
        shapes = (f'<g transform="matrix({s:.5f} 0 0 {s:.5f} {t[0]:.3f} {t[1]:.3f}) '
                  f'matrix({" ".join(f"{v:.5f}" for v in M0)})">{orig}</g>')
        poses[n] = dict(P, source=how, derived=True, shapes=shapes)
        print(f"pose {n}: derived ({how})", file=sys.stderr)

    # the body, without bib and fluff
    body = group_text(base_text, "Body_headless")
    bib = re.search(r'<path id="bib"[^>]*/>', body).group(0)
    fluff = group_text(body, "fluff")
    body_only = body.replace(bib, "").replace(fluff, "")
    defs = re.search(r"<defs>.*?</defs>", base_text, re.S).group(0)
    bib_inner = re.sub(r'\bid="[^"]*"', "", bib)
    fluff_inner = re.sub(r'\bid="[^"]*"', "", fluff)

    cues = json.load(open(a.cues)) if a.cues else None
    vb = re.search(r'viewBox="([^"]+)"', base_text).group(1)
    wrap = lambda inner: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n{defs}\n{inner}\n</svg>\n'
    open(os.path.join(a.out, "body_headless.svg"), "w").write(wrap(body_only))
    record = {}
    for n in POSES:
        P = poses[n]
        bx, fx = P["bib"], P["fluff"]
        # the head's coat runs under its cream ruff to the same edge, which leaves a hairline of orange around the
        # ruff's bottom where it sits on the bib: grow the cream by CREAM_SEAM (V2 units) to cover it
        unit = 1.0 if not P["derived"] else P["head_scale"] * M0[0]       # V2 units per unit of the head's shapes
        shapes = P["shapes"].replace(
            '<g id="head_cream"',
            f'<g id="head_cream" stroke="#F5DAB5" stroke-width="{CREAM_SEAM / unit:.2f}" stroke-linejoin="round"', 1)
        piece = (f'<g id="Pose_{n}">'
                 f'<g id="bib" transform="matrix({bx[0]:.4f} 0 0 {bx[1]:.4f} {bx[2]:.3f} {bx[3]:.3f})">{bib_inner}</g>'
                 f'<g id="fluff" transform="matrix({fx[0]:.4f} 0 0 {fx[1]:.4f} {fx[2]:.3f} {fx[3]:.3f})">{fluff_inner}</g>'
                 f'<g id="head">{shapes}</g></g>')
        open(os.path.join(a.out, f"pose_{n}_head.svg"), "w").write(wrap(piece))
        open(os.path.join(a.out, f"pose_{n}.svg"), "w").write(wrap(body_only + "\n" + piece))
        rec = {k: (np.round(np.array(P[k]), 4).tolist() if k != "source" and k != "derived" else P[k])
               for k in ("source", "derived", "head_scale", "head_t", "bib", "fluff")}
        if cues:
            f = next(c for c in cues["frames"] if c["frame"] == n)
            s, t = P["head_scale"], P["head_t"]
            to_v2 = lambda x, y: [round(s * (M0[0] * x + M0[4]) + t[0], 2), round(s * (M0[3] * y + M0[5]) + t[1], 2)]
            rec["eyes"] = [{"centre": to_v2(e["x"], e["y"]), "w": round(e["w"] * M0[0] * s, 2),
                            "h": round(e["h"] * M0[3] * s, 2)} for e in f["eyes"]]
            rec["nose"] = to_v2(f["nose"]["x"], f["nose"]["y"]) if f["nose"] else None
        record[n] = rec
    json.dump({"units": "V2 outline units", "bib/fluff": "matrix(sx 0 0 sy tx ty) applied to the body's bib/fluff",
               "head": "x' = head_scale * x + head_t, from the align file's first placement", "poses": record},
              open(os.path.join(a.out, "poses.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

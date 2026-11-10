"""Apply corrections to the head-turn poses, from the one-file sheet (Illustrator) or from the pose editor page.

Usage:  python3 apply_pose_edits.py POSES_DIR OUTDIR --sheet all_poses.svg
        python3 apply_pose_edits.py POSES_DIR OUTDIR --edits edits.json
  POSES_DIR  the current poses (build_head_poses.py output, or an earlier run of this script)
  --sheet    the sheet from make_pose_sheet.py, as saved by Illustrator. Everything in it is kept as you left it,
             redrawn shapes included; each pose is lined up by its body (so moving a whole pose column is fine).
  --edits    the pose editor's saved edits: {"poses": {"N": {"head": [a,b,c,d,e,f], "bib": [...], "fluff": [...]}}},
             SVG matrices in V2 units, applied on top of POSES_DIR's poses.

Writes OUTDIR/body_headless.svg, pose_N_head.svg, pose_N.svg and poses.json in the same form as
build_head_poses.py, with the eye and nose positions in poses.json moved along with each head (the head's move is
fitted to its ear and nose shapes; the fit is printed).
"""
import argparse, json, os, re, shutil, sys
import numpy as np
from pose_io import ancestor_transforms, measure, group_text, inline_styles, css_classes, fit_similarity, box_stretch, strip_outer_id


def compose_stretch(d, o):
    """[sx, sy, tx, ty] for d after o."""
    return [d[0] * o[0], d[1] * o[1], d[0] * o[2] + d[2], d[1] * o[3] + d[3]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poses")
    ap.add_argument("out")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sheet")
    g.add_argument("--edits")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    record = json.load(open(os.path.join(a.poses, "poses.json")))
    body_path = os.path.join(a.poses, "body_headless.svg")
    body_text = open(body_path, encoding="utf-8").read()
    body_only = group_text(body_text, "Body_headless")
    defs = re.search(r"<defs>.*?</defs>", body_text, re.S).group(0)
    vb = re.search(r'viewBox="([^"]+)"', body_text).group(1)
    wrap = lambda inner: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n{defs}\n{inner}\n</svg>\n'

    old = {}
    for n in range(1, 6):
        t = open(os.path.join(a.poses, f"pose_{n}_head.svg"), encoding="utf-8").read()
        old[n] = {"text": t, "box": measure(os.path.join(a.poses, f"pose_{n}.svg"), n)[n]}

    if a.sheet:
        stext = open(a.sheet, encoding="utf-8").read()
        classes = css_classes(stext)
        S = measure(a.sheet)
        src = os.path.basename(a.sheet)
    else:
        E = json.load(open(a.edits))["poses"]
        src = os.path.basename(a.edits)

    if os.path.abspath(a.out) != os.path.abspath(a.poses):
        shutil.copy(body_path, os.path.join(a.out, "body_headless.svg"))
    for n in range(1, 6):
        P, rec = old[n], record["poses"][str(n)]
        if a.sheet:
            if n not in S:
                print(f"pose {n}: not in the sheet, left as it was", file=sys.stderr)
                pieces = {p: group_text(P["text"], p) for p in ("bib", "fluff", "head")}
                head_d, bib_d, fluff_d = (1.0, [0.0, 0.0]), [1, 1, 0, 0], [1, 1, 0, 0]
            else:
                N = S[n]
                off = np.array(N["body_coat"][:2]) - np.array(P["box"]["body_coat"][:2])
                sub = lambda b: [b[0] - off[0], b[1] - off[1], b[2] - off[0], b[3] - off[1]]
                pieces = {}
                for p in ("bib", "fluff", "head"):
                    frag = strip_outer_id(inline_styles(group_text(stext, N["ids"][p]), classes))
                    up = ancestor_transforms(stext, N["ids"][p])      # e.g. the column's translate, if not baked in
                    pieces[p] = (f'<g id="{p}"><g transform="translate({-off[0]:.3f},{-off[1]:.3f}) {up}">'
                                 f'{frag}</g></g>')
                s, t, rms = fit_similarity([P["box"]["head_ear"], P["box"]["head_nose"]],
                                           [sub(N["head_ear"]), sub(N["head_nose"])])
                head_d = (s, t)
                bib_d = box_stretch(P["box"]["bib"], sub(N["bib"]))
                fluff_d = box_stretch(P["box"]["fluff"], sub(N["fluff"]))
                print(f"pose {n}: head scale x{s:.3f}, move ({t[0]:+.1f}, {t[1]:+.1f}), fit {rms:.2f}; "
                      f"bib x{bib_d[0]:.3f} y{bib_d[1]:.3f}; fluff x{fluff_d[0]:.3f}", file=sys.stderr)
        else:
            e = E.get(str(n), {})
            ident = [1, 0, 0, 1, 0, 0]
            pieces = {}
            for p in ("bib", "fluff", "head"):
                m = e.get(p, ident)
                inner = strip_outer_id(group_text(P["text"], p))
                pieces[p] = (f'<g id="{p}"><g transform="matrix({" ".join(f"{v:.5f}" for v in m)})">'
                             f'{inner}</g></g>')
            hm, bm, fm = (e.get(p, ident) for p in ("head", "bib", "fluff"))
            head_d = (hm[0], [hm[4], hm[5]])
            bib_d, fluff_d = [bm[0], bm[3], bm[4], bm[5]], [fm[0], fm[3], fm[4], fm[5]]
            if e:
                print(f"pose {n}: head x{hm[0]:.3f} ({hm[4]:+.1f}, {hm[5]:+.1f}); bib x{bm[0]:.3f} y{bm[3]:.3f}; "
                      f"fluff x{fm[0]:.3f}", file=sys.stderr)

        # layer order, bottom to top: the sheet's own order, the editor's saved order, or as it was
        if a.sheet and n in S:
            order = sorted(pieces, key=lambda p: stext.find(f'id="{S[n]["ids"][p]}"'))
        elif not a.sheet and "order" in E.get(str(n), {}):
            order = E[str(n)]["order"]
        else:
            order = sorted(pieces, key=lambda p: P["text"].find(f'<g id="{p}"'))
        piece = f'<g id="Pose_{n}">' + "".join(pieces[p] for p in order) + "</g>"
        rec["order"] = order
        open(os.path.join(a.out, f"pose_{n}_head.svg"), "w", encoding="utf-8").write(wrap(piece))
        open(os.path.join(a.out, f"pose_{n}.svg"), "w", encoding="utf-8").write(wrap(body_only + "\n" + piece))

        s, t = head_d
        moved = not (abs(s - 1) < 1e-6 and abs(t[0]) < 1e-6 and abs(t[1]) < 1e-6
                     and bib_d == [1, 1, 0, 0] and fluff_d == [1, 1, 0, 0])
        rec["head_scale"] = round(s * rec["head_scale"], 4)
        rec["head_t"] = [round(s * rec["head_t"][0] + t[0], 4), round(s * rec["head_t"][1] + t[1], 4)]
        rec["bib"] = [round(v, 4) for v in compose_stretch(bib_d, rec["bib"])]
        rec["fluff"] = [round(v, 4) for v in compose_stretch(fluff_d, rec["fluff"])]
        if rec.get("eyes"):
            for ey in rec["eyes"]:
                ey["centre"] = [round(s * ey["centre"][0] + t[0], 2), round(s * ey["centre"][1] + t[1], 2)]
                ey["w"], ey["h"] = round(ey["w"] * s, 2), round(ey["h"] * s, 2)
        if rec.get("nose"):
            rec["nose"] = [round(s * rec["nose"][0] + t[0], 2), round(s * rec["nose"][1] + t[1], 2)]
        if moved:
            rec["derived"] = False
            rec["source"] = f'{rec["source"]}; corrected in {src}'
    json.dump(record, open(os.path.join(a.out, "poses.json"), "w"), indent=1)
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

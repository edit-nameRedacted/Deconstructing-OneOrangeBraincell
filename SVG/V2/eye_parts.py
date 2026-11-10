"""Measure each kit eye set's parts, so a pupil can look around while the drawing stays as drawn.

Usage:  python3 eye_parts.py ../cat_kit.svg ../eye_parts.json [--preview eye_parts_preview.png]
(run from SVG/V2; rerun whenever the kit's eye sets change)

In the kit, each eye is one or two filled shapes: the lid line and the pupil are often one shape (a pupil
touching the lid), so the pupil can't simply be picked out and moved. Instead, for each eye this finds two
regions, in the eye set's own units (the units inside its <g class="eyes">, before that group's transform):
  opening  the inside of the eye: the drawn eye with its lid line peeled off. The viz fills it white.
  pupil    the dark inside the opening (iris, pupil and the highlights in them), away from the lid line.
The viz then draws, per eye: the opening in white, the drawing clipped to `pupil` (moved by the gaze and
clipped to the opening), and the drawing with `pupil` masked out (the lid line, staying put). Eye sets whose
dark fills the whole opening (big-shiny) get a pupil the size of the opening, so they don't look around.

Also written per eye: the box of the opening (centre, width, height) and of the pupil, which the viz uses to
scale the eye to the tracked size and to work out how far the pupil can travel.
"""
import argparse, io, json, re
import numpy as np
import cv2
from lxml import etree
from playwright.sync_api import sync_playwright

NS = {"s": "http://www.w3.org/2000/svg"}
S = 16                      # pixels per eye-set unit when measuring


def shapes(g):
    """(svg markup, is_white) for every shape in an eye set, with any inner transforms kept."""
    out = []
    for e in g.iter():
        if not isinstance(e.tag, str) or etree.QName(e).localname not in ("path", "polygon", "ellipse", "circle"):
            continue
        tr = []                                          # transforms between the shape and the eye set's group
        for a in e.iterancestors():
            if a is g:
                break
            if a.get("transform"):
                tr.append(a.get("transform"))
        attrs = {k: v for k, v in e.attrib.items() if k in ("d", "points", "cx", "cy", "r", "rx", "ry", "transform")}
        el = f'<{etree.QName(e).localname} ' + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + "/>"
        for t in tr:
            el = f'<g transform="{t}">{el}</g>'
        out.append((el, e.get("class") == "k-eye-white"))
    return out


def render(pg, markup, box, fill):
    x, y, w, h = box
    W, H = int(np.ceil(w * S)), int(np.ceil(h * S))
    pg.set_viewport_size({"width": W, "height": H})
    pg.set_content(f'<style>body{{margin:0;background:#fff}}</style><svg xmlns="http://www.w3.org/2000/svg" '
                   f'width="{W}" height="{H}" viewBox="{x} {y} {W / S} {H / S}"><g fill="{fill}" fill-rule="evenodd">{markup}</g></svg>')
    img = cv2.imdecode(np.frombuffer(pg.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
    return img < 128


def fill_holes(m):
    m = m.astype(np.uint8)
    ff = np.pad(m, 1).copy()
    cv2.floodFill(ff, None, (0, 0), 2)
    return (ff[1:-1, 1:-1] != 2)


def to_path(mask, box, eps=0.6):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    x, y = box[0], box[1]
    d = []
    for c in cs:
        if cv2.contourArea(c) < (0.4 * S) ** 2:
            continue
        c = cv2.approxPolyDP(c, eps, True)[:, 0, :]
        d.append("M" + " L".join(f"{x + px / S:.2f},{y + py / S:.2f}" for px, py in c) + "Z")
    return "".join(d)


def bbox(mask, box):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min() / S + box[0], (xs.max() + 1) / S + box[0], ys.min() / S + box[1], (ys.max() + 1) / S + box[1]
    return {"cx": round((x0 + x1) / 2, 2), "cy": round((y0 + y1) / 2, 2), "w": round(x1 - x0, 2), "h": round(y1 - y0, 2)}


def split_eyes(sil):
    """Label the drawing's pieces and split them into left and right eye at the widest gap."""
    n, comp, stats, _ = cv2.connectedComponentsWithStats(sil.astype(np.uint8), 8)
    pieces = sorted([i for i in range(1, n) if stats[i][4] > 20], key=lambda i: stats[i][0])
    best, cut = -1, 1
    for k in range(1, len(pieces)):
        gap = stats[pieces[k]][0] - max(stats[i][0] + stats[i][2] for i in pieces[:k])
        if gap > best:
            best, cut = gap, k
    return [np.isin(comp, pieces[:cut]), np.isin(comp, pieces[cut:])]


def lid_thickness(dark, sil):
    """Typical thickness of the lid line: down the middle half of the eye, the first dark run from the top."""
    xs = np.nonzero(sil.any(0))[0]
    runs = []
    for x in range(xs.min() + len(xs) // 4, xs.max() - len(xs) // 4):
        col = dark[:, x]
        ys = np.nonzero(sil[:, x])[0]
        if len(ys) == 0:
            continue
        y = ys.min(); n = 0
        while y < len(col) and col[y]:
            n += 1; y += 1
        if n:
            runs.append(n)
    return float(np.median(runs)) if runs else 2.0 * S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kit")
    ap.add_argument("out")
    ap.add_argument("--preview")
    a = ap.parse_args()
    t = etree.parse(a.kit)
    sets = {}
    for g in t.xpath('//s:g[@class="eyes"]', namespaces=NS):
        sets.setdefault(g.get("data-set"), g)            # the same drawing in every body
    result, previews = {}, []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        for name, g in sets.items():
            sh = shapes(g)
            allm = "".join(m for m, _ in sh)
            pg.set_content(f'<svg xmlns="http://www.w3.org/2000/svg"><g id="g">{allm}</g></svg>')
            bb = pg.evaluate("(() => { const b = document.getElementById('g').getBBox(); return [b.x, b.y, b.width, b.height]; })()")
            box = [bb[0] - 2, bb[1] - 2, bb[2] + 4, bb[3] + 4]
            dark = render(pg, "".join(m for m, w in sh if not w), box, "#000")
            white = render(pg, "".join(m for m, w in sh if w), box, "#000")
            sil = fill_holes(dark | white)
            out = {}
            for side, eye in zip(("left", "right"), split_eyes(sil)):
                d_eye, s_eye = dark & eye, sil & eye
                T = lid_thickness(d_eye, s_eye)
                inside = cv2.distanceTransform(s_eye.astype(np.uint8), cv2.DIST_L2, 5)   # distance to the eye's edge
                opening = s_eye & (inside > 0.6 * T)
                pupil = d_eye & (inside > 1.2 * T)
                pupil = cv2.morphologyEx(pupil.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
                pupil = fill_holes(pupil) & opening
                n, comp, st, _ = cv2.connectedComponentsWithStats(pupil.astype(np.uint8), 8)
                if n > 2:                                    # keep the pupil itself, not slivers of a thick lid line
                    pupil = comp == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
                share = pupil.sum() / max(1, opening.sum())
                out[side] = {
                    "opening": to_path(opening, box), "pupil": to_path(pupil, box) if pupil.any() else "",
                    "opening_box": bbox(opening, box), "pupil_box": bbox(pupil, box),
                    "eye_box": bbox(s_eye, box), "lid_line": round(T / S, 2), "pupil_share": round(float(share), 2),
                }
                if previews is not None:
                    vis = np.full(sil.shape + (3,), 255, np.uint8)
                    vis[s_eye] = (210, 210, 210); vis[opening] = (255, 230, 200); vis[d_eye] = (60, 60, 60); vis[pupil] = (40, 40, 220)
                    previews.append((name, side, vis[np.ix_(eye.any(1), eye.any(0))]))
            result[name] = out
            print(f"{name}: " + ", ".join(f"{s} lid {o['lid_line']}, pupil {o['pupil_share']:.0%} of opening" for s, o in out.items()))
        b.close()
    json.dump({"units": "eye-set units (inside each <g class='eyes'>, before its transform)", "sets": result},
              open(a.out, "w"), indent=1)
    if a.preview:
        h = max(v.shape[0] for *_, v in previews)
        tiles = [cv2.copyMakeBorder(v, 0, h - v.shape[0], 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for *_, v in previews]
        rows = [np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]
        W = max(r.shape[1] for r in rows)
        rows = [cv2.copyMakeBorder(r, 6, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]
        img = np.vstack(rows)
        cv2.imwrite(a.preview, cv2.resize(img, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA))


if __name__ == "__main__":
    main()

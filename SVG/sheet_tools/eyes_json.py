"""Eye positions as data for the viz's live kit eyes, from a traced Wan sequence (after trace_frames.py).

Usage:  python eyes_json.py out/NAME [--kit ../cat_kit.svg]

Reads out/NAME/svg/eyes_px.json (written by trace_frames.py), out/NAME/run.json and out/NAME/frames/, and:
  - fits "to_kit" [scale, tx, ty] (frame pixels -> kit units: x_kit = scale * x + tx) on the first frame: its width
    below the neck to the kit's typical body, its middle to BODY_X and its floor line to FLOOR_Y (both V2 units in
    V2/build_kit_v2.py, times KIT_SCALE 1.35 = the units of cat_kit.svg), and adds it to run.json;
  - writes svg/eyes.json: per frame, per eye ("left" = the viewer's left, followed from frame to frame, not re-sorted
    by x), in kit units: cx, cy, w, h (the eye's size, open), opening_h (the white as read), angle (eye line, degrees),
    visible, lid (0 open .. 1 shut), gaze_x, gaze_y (pupil offset from the centre, share of half the width/height,
    -1..1), source (detected | filled | interpolated); a smoothed track ("smooth": cx, cy, w, h, angle; 3-frame median
    then a light [1 2 1] pass, keyframes pinned to their detected values) for the viz to use; and "flags";
  - wraps every svg/frame_NNNNN.svg (and _drawnshut.svg) in <g id="to-kit" transform=...> with a kit-unit viewBox,
    so the frames overlay the kit body exactly;
  - draws svg/check_eyes.png: every frame with its eye boxes, gaze arrows and lid value, flagged frames in red.
"""
import argparse, glob, json, math, os, re, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_frames as sf   # noqa: E402

KIT_SCALE, FLOOR_Y, BODY_X, NECK_Y = 1.35, 358, 86, 130      # V2/build_kit_v2.py (V2 units)


# ------------------------------------------------------------------------------------------- pure parts
def track_sides(frames):
    """frames: per frame two eyes {x, y} in any order. Returns ([[left, right] per frame], swaps, unsure).
    Frame 1's eyes are sorted by x; after that each eye follows whichever eye is nearer its last position, so an eye
    keeps its side name through the sequence. swaps: 1-based frames where the left eye is right of the right eye.
    unsure: frames where the other pairing was nearly as close (within 1.5x)."""
    d = lambda p, q: math.hypot(p["x"] - q["x"], p["y"] - q["y"])
    sides, swaps, unsure = [sorted(frames[0], key=lambda e: e["x"])], [], []
    for i, (a, b) in enumerate(frames[1:], 2):
        L, R = sides[-1]
        keep, swap = d(L, a) + d(R, b), d(L, b) + d(R, a)
        pair = [a, b] if keep <= swap else [b, a]
        if max(keep, swap) < 1.5 * max(min(keep, swap), 1.0):
            unsure.append(i)
        if pair[0]["x"] > pair[1]["x"]:
            swaps.append(i)
        sides.append(pair)
    return sides, swaps, unsure


def smooth_track(raw, pinned=None):
    """3-frame median, then [1 2 1]/4, then the pinned frames ({1-based frame: value}) set back."""
    v = np.asarray(raw, float)
    p = np.pad(v, 1, mode="edge")
    med = np.median(np.stack([p[:-2], p[1:-1], p[2:]]), axis=0)
    q = np.pad(med, 1, mode="edge")
    out = (q[:-2] + 2 * q[1:-1] + q[2:]) / 4
    for f, val in (pinned or {}).items():
        out[f - 1] = val
    return [round(float(x), 2) for x in out]


def flag_frames(spacing, angle, swaps=(), single_frontal=()):
    """Frames that differ from the frames either side (their mean; one neighbour at the ends): eye spacing by more
    than 20%, eye-line angle by more than 10 degrees; plus eye swaps and a lone eye on a frontal head."""
    flags = []
    n = len(spacing)
    for i in range(n):
        nb = [j for j in (i - 1, i + 1) if 0 <= j < n]
        s = np.mean([spacing[j] for j in nb])
        if s and abs(spacing[i] / s - 1) > 0.2:
            flags.append({"frame": i + 1, "why": "spacing", "value": round(spacing[i], 1), "neighbours": round(float(s), 1)})
        a = np.mean([angle[j] for j in nb])
        if abs(angle[i] - a) > 10:
            flags.append({"frame": i + 1, "why": "angle", "value": round(angle[i], 1), "neighbours": round(float(a), 1)})
    flags += [{"frame": f, "why": "swap"} for f in swaps]
    flags += [{"frame": f, "why": "one eye, head frontal"} for f in single_frontal]
    return sorted(flags, key=lambda x: x["frame"])


# ------------------------------------------------------------------------------------------- kit fit
def body_measure(mask, neck_y):
    """Widest row below the neck, the middle of the body there, and the floor line."""
    rows = np.nonzero(mask.any(1))[0]
    floor = rows[-1]
    best = (0, 0.0)
    for y in rows[rows > neck_y]:
        xs = np.nonzero(mask[y])[0]
        if xs[-1] - xs[0] > best[0]:
            best = (xs[-1] - xs[0] + 1, (xs[0] + xs[-1]) / 2)
    return best[0], best[1], float(floor)


def kit_body(kit_path):
    """The typical body's coat silhouette from cat_kit.svg, measured in kit units."""
    from playwright.sync_api import sync_playwright
    s = open(kit_path, encoding="utf-8").read()
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
    d = re.search(r'<path class="k-coat" d="([^"]+)"', s[s.index('data-body="typical"'):]).group(1)
    R = 4
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(map(str, vb))}" width="{vb[2] * R}" '
           f'height="{vb[3] * R}"><path d="{d}" fill="#000"/></svg>')
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
        png = pg.locator("svg").screenshot(); b.close()
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    w, cx, floor = body_measure(img < 128, (NECK_Y * KIT_SCALE - vb[1]) * R)
    return w / R, cx / R + vb[0], floor / R + vb[1]


def fit_to_kit(frame_png, kit_path):
    m = sf.silhouette(cv2.imread(frame_png))
    rows = np.nonzero(m.any(1))[0]
    neck = rows[0] + 0.4 * (rows[-1] - rows[0])      # below the head: the frame cat's neck is about 40% down
    fw, fcx, ffloor = body_measure(m, neck)
    kw, kcx, kfloor = kit_body(kit_path)
    s = kw / fw
    return [round(float(s), 5), round(float(BODY_X * KIT_SCALE - s * fcx), 3), round(float(FLOOR_Y * KIT_SCALE - s * ffloor), 3)], \
        {"frame_body_width_px": int(fw), "kit_body_width": round(kw, 2), "kit_measured_centre_x": round(kcx, 2),
         "kit_measured_floor_y": round(kfloor, 2)}


def wrap_svg(path, to_kit, canvas):
    s0 = open(path, encoding="utf-8").read()
    if 'id="to-kit"' in s0:
        return
    sc, tx, ty = to_kit
    W, H = canvas
    head = re.match(r"<svg[^>]*>", s0).group(0)
    new_head = re.sub(r'viewBox="[^"]+"', f'viewBox="{tx:.2f} {ty:.2f} {W * sc:.2f} {H * sc:.2f}"', head)
    body = s0[len(head):s0.rindex("</svg>")]
    out = f'{new_head}\n<g id="to-kit" transform="matrix({sc} 0 0 {sc} {tx} {ty})">{body}<!--kit-eyes--></g>\n</svg>\n'
    open(path, "w", encoding="utf-8").write(out)


# ------------------------------------------------------------------------------------------- build
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq", help="out/NAME (with frames/, svg/, run.json)")
    ap.add_argument("--keep-wan-blinks", action="store_true",
                    help="keep lids for 1-2 frame blinks Wan made up (default: lid 0 there; drawn blinks always count)")
    ap.add_argument("--kit", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cat_kit.svg"))
    a = ap.parse_args()
    svg_dir = os.path.join(a.seq, "svg")
    px = json.load(open(os.path.join(svg_dir, "eyes_px.json")))
    cues = json.load(open(os.path.join(svg_dir, "cues.json")))
    run = json.load(open(os.path.join(a.seq, "run.json")))
    frames = px["frames"]
    n = len(frames)
    kf = sorted(set(run.get("keyframe_frames", [])))
    to_kit, fit_info = fit_to_kit(os.path.join(a.seq, "frames", "frame_00001.png"), a.kit)
    sc, tx, ty = to_kit
    K = lambda x, y: (sc * x + tx, sc * y + ty)

    sides, swaps, unsure = track_sides([f["eyes"] for f in frames])
    # the eye's open height, per side: the median of nearby frames where it was read open
    open_h = {s: {} for s in (0, 1)}
    for s in (0, 1):
        hs = [(i, sides[i][s]["h"]) for i in range(n) if frames[i]["state"] == "open"]
        for i in range(n):
            near = [h for j, h in hs if abs(j - i) <= 6 and j != i] or [h for _, h in hs]
            open_h[s][i] = float(np.median(near))
    ramp = [c.get("lid", 0) for c in cues["frames"]]
    single_frontal = []
    recs = []
    for i, f in enumerate(frames):
        L, R = sides[i]
        ang = math.degrees(math.atan2(R["y"] - L["y"], R["x"] - L["x"]))
        meas = f["measured"]
        nose = f.get("nose")
        mid = (L["x"] + R["x"]) / 2
        frontal = nose is not None and abs(nose["x"] - mid) < 0.25 * abs(R["x"] - L["x"])
        if len(meas) == 1 and frontal:
            single_frontal.append(i + 1)
        rec = {"frame": i + 1, "keyframe": (i + 1) in kf, "state": f["state"]}
        for s, (name, e) in enumerate((("left", L), ("right", R))):
            href = open_h[s][i]
            if f["state"] == "closed":
                lid, opening = 1.0, 0.0
            elif f["state"] == "filled" and not a.keep_wan_blinks:
                # eyes that went shut or to a sliver for a frame or two: a blink Wan made up, not one drawn in the
                # keyframes (the viz blinks on its own), so the lid stays open
                lid, opening = 0.0, 0.0
            else:
                # what was read for this eye on this frame (a sliver when half-lidded), if anything
                m = min(meas, key=lambda q: abs(q["x"] - e["x"])) if meas else None
                m = m if m and abs(m["x"] - e["x"]) < 0.6 * e["w"] else None
                opening = float(m["h"]) if m else 0.0
                lid = max(0.0, min(1.0, 1 - opening / href)) if href else 0.0
                lid = 0.0 if lid < 0.15 else lid
            lid = max(lid, float(ramp[i]))
            visible = True
            if len(meas) == 1 and not frontal:           # a turned head showing one eye: the far one is hidden
                visible = abs(meas[0]["x"] - e["x"]) < 0.5 * e["w"]
            cx, cy = K(e["x"], e["y"])
            h_open = max(float(e["h"]), href) if f["state"] != "open" or lid > 0 else float(e["h"])
            px_, py_ = e["pupil"]
            rec[name] = {"cx": round(cx, 2), "cy": round(cy, 2), "w": round(sc * e["w"], 2), "h": round(sc * h_open, 2),
                         "opening_h": round(sc * opening if f["state"] != "open" else sc * e["h"], 2),
                         "angle": round(ang, 2), "visible": visible, "lid": round(lid, 2),
                         "gaze_x": round(max(-1, min(1, (px_ - e["x"]) / (e["w"] / 2))), 3),
                         "gaze_y": round(max(-1, min(1, (py_ - e["y"]) / (max(e["h"], 1) / 2))), 3),
                         "source": e.get("source", "detected")}
        recs.append(rec)

    # smoothed tracks, keyframes pinned to their detected values
    for name in ("left", "right"):
        for k in ("cx", "cy", "w", "h", "angle"):
            raw = [r[name][k] for r in recs]
            pin = {r["frame"]: r[name][k] for r in recs if r["keyframe"] and r[name]["source"] == "detected"}
            for r, v in zip(recs, smooth_track(raw, pin)):
                r[name].setdefault("smooth", {})[k] = v
    spacing = [math.hypot(r["right"]["cx"] - r["left"]["cx"], r["right"]["cy"] - r["left"]["cy"]) for r in recs]
    flags = flag_frames(spacing, [r["left"]["angle"] for r in recs], swaps, single_frontal)
    out = {"sequence": os.path.basename(os.path.normpath(a.seq)), "units": "kit (cat_kit.svg; V2 units x 1.35)",
           "to_kit": to_kit, "fit": fit_info,
           "notes": "left = the viewer's left, followed frame to frame. w, h: the eye's size when open; opening_h: "
                    "the white as read; lid: 0 open .. 1 shut. Use 'smooth' for cx, cy, w, h, angle.",
           "unsure_which_eye": unsure, "flags": flags, "frames": recs}
    json.dump(out, open(os.path.join(svg_dir, "eyes.json"), "w"), indent=1)
    run["to_kit"] = to_kit
    json.dump(run, open(os.path.join(a.seq, "run.json"), "w"), indent=2)
    for p in glob.glob(os.path.join(svg_dir, "frame_[0-9][0-9][0-9][0-9][0-9].svg")) + \
            glob.glob(os.path.join(svg_dir, "frame_*_drawnshut.svg")):
        wrap_svg(p, to_kit, px["canvas"])
    check_image(a.seq, frames, sides, recs, {x["frame"] for x in flags}, os.path.join(svg_dir, "check_eyes.png"))
    print(f"to_kit {to_kit}; flags {[(x['frame'], x['why']) for x in flags]}; unsure {unsure} -> {svg_dir}/eyes.json")


def check_image(seq, frames, sides, recs, flagged, out, cols=8, cell=300):
    tiles = []
    for i, f in enumerate(frames):
        img = cv2.imread(os.path.join(seq, "frames", f"frame_{i + 1:05d}.png"))
        for s, name in ((0, "left"), (1, "right")):
            e, r = sides[i][s], recs[i][name]
            col = {"detected": (0, 160, 0), "filled": (200, 60, 0), "interpolated": (230, 230, 0)}[r["source"]]  # green, blue, cyan
            p0 = (int(e["x"] - e["w"] / 2), int(e["y"] - e["h"] / 2))
            p1 = (int(e["x"] + e["w"] / 2), int(e["y"] + e["h"] / 2))
            cv2.rectangle(img, p0, p1, col, 2)
            c = (int(e["x"]), int(e["y"]))
            g = (int(e["x"] + r["gaze_x"] * e["w"] / 2), int(e["y"] + r["gaze_y"] * e["h"] / 2))
            cv2.arrowedLine(img, c, g, (255, 0, 255), 2, tipLength=0.4)
            cv2.putText(img, f"{name[0].upper()} {r['lid']:.1f}", (p0[0], p0[1] - 4), 0, 0.45, col, 1, cv2.LINE_AA)
        s = cell / img.shape[1]
        img = cv2.resize(img, (cell, int(img.shape[0] * s)))
        lab = f"{i + 1}{' K' if recs[i]['keyframe'] else ''}"
        cv2.putText(img, lab, (6, 22), 0, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
        if (i + 1) in flagged:
            cv2.rectangle(img, (0, 0), (img.shape[1] - 1, img.shape[0] - 1), (0, 0, 255), 6)
        tiles.append(img)
    h = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    grid = np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])
    cv2.imwrite(out, grid)


if __name__ == "__main__":
    main()

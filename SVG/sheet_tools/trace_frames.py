"""Trace a folder of already-registered frames (frame_00001.png, ...) into SVGs and one cues.json.

Usage:  python trace_frames.py FRAMES_DIR --out DIR [--record RUN_JSON] [--line-min --line-max --speck --open-bottom --keep-eyes]

Same per-frame work as sheet_frames.py (eyes/nose read, eyes painted out, layers traced), but no cutting or aligning.
"""
import argparse, glob, json, os, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_frames as sf   # noqa: E402


def eye_state(n_eyes):
    return {2: "open", 0: "closed"}.get(n_eyes, "partial")


def usable(found):
    """Frames with two eyes that aren't slivers (under half the size of the eyes within 3 frames either side)."""
    size = lambda e: min(x["w"] * x["h"] for x in e)      # the smaller eye: one sliver is enough to be wrong
    have = [i for i, e in enumerate(found) if len(e) == 2]
    near = lambda i: sorted(size(found[j]) for j in have if j != i and abs(j - i) <= 3)
    return [i for i in have if not near(i) or size(found[i]) >= 0.5 * near(i)[len(near(i)) // 2]]


def fill_gaps(found, max_gap=2):
    """found: per frame, the two eyes read off it (or fewer). Runs of at most max_gap frames without two eyes, with
    two eyes on the frames either side, get eyes interpolated between those frames. Returns {index: [left, right]}.
    Longer runs are eyes really shut (a blink drawn into the keyframes) and are left alone. Eyes under half the size
    of those within 3 frames either side were read off a sliver of white (half-lidded) and count as missing too."""
    have = usable(found)
    fills = {}
    for i0, i1 in zip(have, have[1:]):
        if 1 < i1 - i0 <= max_gap + 1:
            for i in range(i0 + 1, i1):
                t = (i - i0) / (i1 - i0)
                fills[i] = [{"x": round(a["x"] + t * (b["x"] - a["x"]), 1), "y": round(a["y"] + t * (b["y"] - a["y"]), 1),
                             "w": round(a["w"] + t * (b["w"] - a["w"])), "h": round(a["h"] + t * (b["h"] - a["h"])),
                             "pupil": [round(pa + t * (pb - pa), 1) for pa, pb in zip(a["pupil"], b["pupil"])]}
                            for a, b in zip(found[i0], found[i1])]
    return fills


def _lerp_eyes(a, b, t):
    return [{"x": round(p["x"] + t * (q["x"] - p["x"]), 1), "y": round(p["y"] + t * (q["y"] - p["y"]), 1),
             "w": round(p["w"] + t * (q["w"] - p["w"])), "h": round(p["h"] + t * (q["h"] - p["h"])),
             "pupil": [round(pa + t * (pb - pa), 1) for pa, pb in zip(p["pupil"], q["pupil"])]} for p, q in zip(a, b)]


def place_shut(found, known):
    """Eyes for every frame that has none in `known` (frame -> [left, right]: read off the frame or filled):
    interpolated between the known frames either side, or held from the nearest one at the start or end."""
    ks = sorted(known)
    out = {}
    for i in range(len(found)):
        if i in known or not ks:
            continue
        before = [k for k in ks if k < i]
        after = [k for k in ks if k > i]
        if before and after:
            i0, i1 = before[-1], after[0]
            out[i] = _lerp_eyes(known[i0], known[i1], (i - i0) / (i1 - i0))
        else:
            out[i] = [dict(e) for e in known[before[-1] if before else after[0]]]
    return out


def lid_line(img, inside, e):
    """A drawn shut eye near where eye e should be: a dark curve about as wide as the eye. Its centre and width,
    or None."""
    v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 2]
    H, W = v.shape
    x0, x1 = max(0, int(e["x"] - 0.9 * e["w"])), min(W, int(e["x"] + 0.9 * e["w"]))
    y0, y1 = max(0, int(e["y"] - 0.8 * e["h"])), min(H, int(e["y"] + 0.8 * e["h"]))
    dark = ((v[y0:y1, x0:x1] < 100) & inside[y0:y1, x0:x1]).astype(np.uint8)
    n, comp, st, cen = cv2.connectedComponentsWithStats(dark, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 15 or not 0.35 * e["w"] <= w <= 1.6 * e["w"] or h > 0.7 * e["w"]:
            continue
        if x == 0 or x + w >= x1 - x0 or y == 0 or y + h >= y1 - y0:
            continue                       # runs out of the window: a whisker or an outline, not a lid
        cx, cy = x0 + x + w / 2, y0 + y + h / 2
        d = np.hypot(cx - e["x"], cy - e["y"])
        if d <= 0.8 * e["w"] and (best is None or d < best[0]):
            best = (d, cx, cy, w)
    return None if best is None else {"x": round(best[1], 1), "y": round(best[2], 1), "w": int(best[3])}


def lid_ramp(states, ramp=2):
    """Per frame, how far the kit eyes' lids should be closed (0 open, 1 shut): 1 where the eyes are drawn shut, and
    easing over `ramp` frames before and after each shut run, so the kit eyes blink into the drawn ones naturally."""
    lids = [1 if s == "closed" else 0 for s in states]
    for i, s in enumerate(states):
        if s != "closed":
            continue
        for k in range(1, ramp + 1):
            for j in (i - k, i + k):
                if 0 <= j < len(states) and states[j] != "closed":
                    lids[j] = max(lids[j], round(1 - k / (ramp + 1), 2))
    return lids


def isolated_flips(states):
    """1-based frames whose state differs from both neighbours, which agree with each other."""
    return [i + 1 for i in range(1, len(states) - 1)
            if states[i - 1] == states[i + 1] != states[i]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("--out", required=True)
    ap.add_argument("--record", help="run.json to add the eye states to")
    ap.add_argument("--keep-eyes", action="store_true")
    ap.add_argument("--keep-shut", action="store_true",
                    help="also write frame_NNNNN_drawnshut.svg (eyes drawn shut kept) for frames with eyes shut")
    ap.add_argument("--blink-ramp", type=int, default=2,
                    help="frames over which the kit eyes' lids close before (and open after) eyes drawn shut")
    ap.add_argument("--rest-lid", type=float, default=0,
                    help="lids rest this far closed on every frame (0 open .. 1 shut), e.g. 0.45 for a content, sleepy "
                         "cat (kneading); blinks still close fully")
    ap.add_argument("--line-min", type=float, default=0)
    ap.add_argument("--line-max", type=float, default=0)
    ap.add_argument("--speck", type=int, default=40)
    ap.add_argument("--open-bottom", type=float, default=0)
    a = ap.parse_args()
    if a.record and not os.path.isfile(a.record):
        sys.exit(f"--record file not found: {a.record}")
    os.makedirs(a.out, exist_ok=True)

    files = sorted(glob.glob(os.path.join(a.frames, "frame_*.png")))
    if not files:
        sys.exit(f"no frame_*.png in {a.frames}")
    cues = {"source": a.frames, "canvas": None, "frames": []}
    canvases = []
    for f in files:
        canvas = cv2.imread(f)
        if cues["canvas"] is None:
            cues["canvas"] = [canvas.shape[1], canvas.shape[0]]
        elif [canvas.shape[1], canvas.shape[0]] != cues["canvas"]:
            sys.exit(f"{f}: size differs from the first frame {cues['canvas']}")
        canvases.append(canvas)
    insides = [sf.silhouette(c) for c in canvases]
    dets = [sf.eyes_and_nose(c, m, keep_single=True) for c, m in zip(canvases, insides)]
    found = [d[0] if len(d[0]) == 2 else [] for d in dets]
    # eyes missed for a frame or two (squinting, a stray blink) are taken from the frames either side
    fills = fill_gaps(found)
    known = {i: found[i] for i in usable(found)}
    known.update(fills)
    # eyes drawn shut for longer: placed between the frames either side, then moved onto the drawn lid line where
    # one is clearly there, and painted out like the rest (the viz draws them, closed by the lid value)
    shut = place_shut(found, known)
    px, states = [], []
    for i, (f, canvas) in enumerate(zip(files, canvases)):
        name = os.path.splitext(os.path.basename(f))[0]
        clean = lambda es: [{k: v for k, v in e.items() if not k.startswith("_") and k != "area"} for e in es]
        if i in shut:
            eyes = []
            for e in shut[i]:
                ln = lid_line(canvas, insides[i], e)
                ok = ln and abs(ln["x"] - e["x"]) < 0.5 * e["w"] and abs(ln["y"] - e["y"]) < 0.5 * e["h"]
                eyes.append({**e, "x": ln["x"], "y": ln["y"], "w": ln["w"], "source": "detected", "lid_line": True}
                            if ok else {**e, "source": "interpolated", "lid_line": False})
            if all(e["lid_line"] for e in eyes):          # two lid lines must sit as far apart as the eyes would
                prior = abs(shut[i][1]["x"] - shut[i][0]["x"])
                if not 0.75 <= abs(eyes[1]["x"] - eyes[0]["x"]) / prior <= 1.25:
                    eyes = [{**e, "source": "interpolated", "lid_line": False} for e in shut[i]]
            # paint: a lid line found is painted where it is; an interpolated eye may sit half an eye off the drawn
            # lid, so its oval is painted larger
            grow = lambda e, p: (1.0, 1.0) if e["lid_line"] else (1.5, 1.3)
            state, fill = "closed", [{**e, "w": round(max(e["w"], p["w"]) * grow(e, p)[0]), "h": round(e["h"] * grow(e, p)[1])}
                                     for e, p in zip(eyes, shut[i])]
        elif i in fills:
            eyes, state, fill = [{**e, "source": "filled"} for e in fills[i]], "filled", fills[i]
        else:
            eyes, state, fill = [{**e, "source": "detected"} for e in clean(found[i])], "open", None
        r = sf.process_frame(canvas, name, a.out, a, fill_eyes=fill)
        if state == "closed":
            r["eyes_closed"] = True                       # the eyes are painted out, but drawn shut: no kit eyes here
            if a.keep_shut:                               # optional: the drawn-shut version as well
                sf.process_frame(canvas, name + "_drawnshut", a.out, a)
                os.remove(os.path.join(a.out, name + "_drawnshut.png"))
        cues["frames"].append({"frame": i + 1, "file": name + ".svg", **r})
        states.append(state)
        px.append({"frame": i + 1, "state": state, "eyes": eyes, "measured": clean(dets[i][0]), "nose": dets[i][1]})
        print(f"{name}: {state}, eyes {len(eyes)}, nose {'yes' if r['nose'] else 'no'}", file=sys.stderr)
    json.dump({"canvas": cues["canvas"], "frames": px}, open(os.path.join(a.out, "eyes_px.json"), "w"), indent=1)
    for f, lid in zip(cues["frames"], lid_ramp(states, a.blink_ramp)):
        f["lid"] = max(lid, a.rest_lid)
    json.dump(cues, open(os.path.join(a.out, "cues.json"), "w"), indent=1)
    flips = isolated_flips(["open" if s == "filled" else s for s in states])
    print(f"{len(files)} frames; eye states " + ", ".join(f"{s} {states.count(s)}" for s in ("open", "filled", "partial", "closed"))
          + f"; isolated flips {flips} -> {a.out}", file=sys.stderr)
    if a.record:
        run = json.load(open(a.record))
        run["eyes"] = {"states": states, "isolated_flips": flips}
        json.dump(run, open(a.record, "w"), indent=1)


if __name__ == "__main__":
    main()

"""Put keyframes from several sheet_frames.py folders on one canvas, lined up by the middle of their base (the feet).

Usage:  python join_keys.py OUT SRC:N[,N...] [SRC:N...] [--match SRC:N=SRC:M]

  SRC:N,...        keyframes N of the folder SRC (sheet_frames.py output), in the order given; they become
                   OUT/frame_01.png, frame_02.png, ... (cues.json says where each came from)
  --match A:N=B:M  scale every keyframe from folder A so A's keyframe N is as tall as B's keyframe M
                   (two sheets of the same cat drawn at slightly different sizes)

For a sequence that needs a pose from another sheet, e.g. the head turn's frontal pose as the base pose of the
kneading sheet:  python join_keys.py out/knead_keys out/head_turn_keys:3 out/knead_sheet_keys:1,2,3,4,5,6
                 --match out/head_turn_keys:3=out/knead_sheet_keys:3
"""
import argparse, json, os, sys
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet_frames as sf   # noqa: E402


def _mask(img):
    return sf.silhouette(cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR))


def height(img):
    ys = np.nonzero(_mask(img).any(1))[0]
    return ys[-1] - ys[0]


def join(images, scales, pad=20):
    """Scale each image, then place all on one white canvas so their base middles coincide."""
    scaled = [im.convert("RGB").resize((round(im.width * s), round(im.height * s)), Image.LANCZOS) if s != 1
              else im.convert("RGB") for im, s in zip(images, scales)]
    anchors = []
    for im in scaled:
        m = _mask(im)
        ys, xs = np.nonzero(m)
        anchors.append((sf.base_anchor(m), (xs.min(), ys.min(), xs.max(), ys.max())))
    left = max(ax - b[0] for (ax, ay), b in anchors) + pad
    right = max(b[2] - ax for (ax, ay), b in anchors) + pad
    up = max(ay - b[1] for (ax, ay), b in anchors) + pad
    down = max(b[3] - ay for (ax, ay), b in anchors) + pad
    W, H = int(round(left + right)), int(round(up + down))
    out = []
    for im, ((ax, ay), b) in zip(scaled, anchors):
        m = _mask(im)
        cut = np.asarray(im).copy()
        cut[~cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)] = 255   # just the drawing
        canvas = Image.new("RGB", (W, H), "white")
        canvas.paste(Image.fromarray(cut), (int(round(left - ax)), int(round(up - ay))))
        out.append(canvas)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("sources", nargs="+", help="SRC:N[,N...]")
    ap.add_argument("--match", action="append", default=[], help="A:N=B:M")
    ap.add_argument("--append", action="append", default=[],
                    help="a PNG already on the joined canvas (e.g. a Wan frame from out/NAME/raw), added as is")
    a = ap.parse_args()
    load = lambda src, n: Image.open(os.path.join(src, f"frame_{n:02d}.png"))
    items = []
    for s in a.sources:
        src, ns = s.rsplit(":", 1)
        items += [(src, int(n)) for n in ns.split(",")]
    scale = {}
    for m in a.match:
        (sa, na), (sb, nb) = [(p.rsplit(":", 1)[0], int(p.rsplit(":", 1)[1])) for p in m.split("=")]
        scale[sa] = height(load(sb, nb)) / height(load(sa, na))
    imgs = join([load(s, n) for s, n in items], [scale.get(s, 1.0) for s, _ in items])
    for p in a.append:            # already lined up (made on this canvas): re-anchoring would move a lifted paw's frame
        im = Image.open(p).convert("RGB")
        if im.size != imgs[0].size:
            sys.exit(f"--append {p}: {im.size} is not the joined canvas {imgs[0].size}")
        imgs.append(im)
        items.append((p, 0))
    os.makedirs(a.out, exist_ok=True)
    cues = {"joined": True, "canvas": list(imgs[0].size), "frames": []}
    for k, (im, (src, n)) in enumerate(zip(imgs, items), 1):
        name = f"frame_{k:02d}"
        im.save(os.path.join(a.out, name + ".png"))
        bgr = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
        eyes, nose = sf.eyes_and_nose(bgr, sf.silhouette(bgr))
        cues["frames"].append({"frame": k, "file": name + ".svg", "from": f"{src}:{n}",
                               "scale": round(scale.get(src, 1.0), 4),
                               "eyes": [{kk: vv for kk, vv in e.items() if not kk.startswith("_") and kk != "area"} for e in eyes],
                               "eyes_closed": len(eyes) < 2, "nose": nose})
        print(f"{name}: from {src}:{n} (scale {scale.get(src, 1.0):.3f}), eyes {len(eyes)}")
    json.dump(cues, open(os.path.join(a.out, "cues.json"), "w"), indent=1)
    print(f"{len(imgs)} keyframes on a {imgs[0].size[0]}x{imgs[0].size[1]} canvas -> {a.out}")


if __name__ == "__main__":
    main()

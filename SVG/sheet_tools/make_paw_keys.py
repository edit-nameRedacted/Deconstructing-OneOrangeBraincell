"""Build alternating-paw keyframes from the 8.webp paw sheet (cut by sheet_frames into out/paw_sheet_keys).

The sheet only presses the cat's right paw (viewer-left). The other side is made by copying that arm
across without flipping (cats show no thumb, so a copied paw reads as the other paw):
  1 both paws down  = sheet frame 7 with its tucked paw painted out
  2 left tuck       = sheet frame 4      3 left press = sheet frame 5
  4 right tuck      = sheet frame 7      5 right press = frame 1 + sheet frame 5's arm moved +DX
Polygons are hand-placed in canvas px for this sheet (259x401 canvas).
usage: make_paw_keys.py [SRC=out/paw_sheet_keys] [OUT=out/paw_keys]
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TUCK = [(112, 256), (153, 256), (151, 280), (147, 300), (149, 330), (143, 348), (112, 348), (103, 330), (103, 300), (108, 275)]
ARM = [(80, 270), (117, 270), (111, 290), (104, 304), (118, 316), (127, 328), (130, 345), (126, 357), (100, 359), (82, 357), (76, 345), (78, 325), (80, 300)]
DX = 30           # left arm -> right arm (mirror of the arm about the body centre lands here too)
STRIPES_FROM = 127  # right of this x, the painted patch takes sheet frame 5's pixels (its right side is planted)


def mask(size, poly, blur):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur))


def paint_out_tuck(f7, f5):
    a = np.asarray(f7.convert("RGB"))
    fur = tuple(int(v) for v in np.median(a[300:340, 85:95].reshape(-1, 3), axis=0))
    fill = Image.new("RGBA", f7.size, fur + (255,))
    right = Image.new("L", f7.size, 0)
    ImageDraw.Draw(right).rectangle([STRIPES_FROM, 0, f7.width, f7.height], fill=255)
    fill.paste(f5, (0, 0), right.filter(ImageFilter.GaussianBlur(2)))
    fill.putalpha(mask(f7.size, TUCK, 1.5))
    out = f7.copy()
    out.alpha_composite(fill)
    return out


def copy_arm(src, base, poly, dx):
    arm = src.copy()
    arm.putalpha(mask(src.size, poly, 1.2))
    out = base.copy()
    out.alpha_composite(arm.transform(src.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0)))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "out/paw_sheet_keys"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "out/paw_keys"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(src, "cues.json"), encoding="utf-8") as f:
        cues = json.load(f)
    by = {e["frame"]: e for e in cues["frames"]}
    im = {k: Image.open(os.path.join(src, f"frame_{k:02d}.png")).convert("RGBA") for k in (1, 2, 4)}
    down = paint_out_tuck(im[4], im[2])
    made = {1: (down, 4), 2: (im[1], 1), 3: (im[2], 2), 4: (im[4], 4), 5: (copy_arm(im[2], down, ARM, DX), 4)}
    frames = []
    for k, (img, eyes_from) in made.items():
        name = f"frame_{k:02d}"
        img.save(os.path.join(out_dir, name + ".png"))
        e = dict(by[eyes_from], frame=k, file=name + ".svg")   # face untouched -> eyes of the frame it was built on
        frames.append(e)
    with open(os.path.join(out_dir, "cues.json"), "w", encoding="utf-8") as f:
        json.dump(dict(cues, frames=frames, built_by="make_paw_keys.py"), f, indent=1)
    print(f"{len(frames)} keyframes -> {out_dir}")


if __name__ == "__main__":
    main()

"""Preview a traced frame sequence: animated GIF + contact sheet.

Usage:  python preview_seq.py DIR [--set round] [--fps 12] [--width 300] [--cols 12]
DIR holds frame_NNNNN[_<set>].svg and cues.json; DIR/../run.json "keyframe_frames" marks K cells.
--set "" uses the plain frame_NNNNN.svg. Writes DIR/preview_<set>.gif and DIR/contact_<set>.png
(<set> = "traced" when empty).
"""
import argparse, io, json, os
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--set", default="round")
    ap.add_argument("--fps", type=float, default=12)
    ap.add_argument("--width", type=int, default=300)
    ap.add_argument("--cols", type=int, default=12)
    a = ap.parse_args()
    cues = json.load(open(os.path.join(a.dir, "cues.json"), encoding="utf-8"))
    cw, ch = cues["canvas"]
    W, H = a.width, round(a.width * ch / cw)
    try:
        keys = set(json.load(open(os.path.join(a.dir, "..", "run.json"), encoding="utf-8"))["keyframe_frames"])
    except (OSError, KeyError, ValueError):
        keys = set()
    tag = a.set or "traced"
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for f in cues["frames"]:
            name = f["file"] if not a.set else f["file"].replace(".svg", f"_{a.set}.svg")
            svg = open(os.path.join(a.dir, name), encoding="utf-8").read()
            pg.set_content(f'<style>body{{margin:0;background:#fff}} svg{{display:block}}</style>{svg}')
            pg.evaluate(f"""() => {{ const s = document.querySelector('svg');
                if (!s.getAttribute('viewBox')) s.setAttribute('viewBox', '0 0 {cw} {ch}');
                s.setAttribute('width', {W}); s.setAttribute('height', {H}); }}""")
            frames.append((f["frame"], Image.open(io.BytesIO(pg.locator("svg").screenshot())).convert("RGB")))
        b.close()
    gif = [im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for _, im in frames]
    gif[0].save(os.path.join(a.dir, f"preview_{tag}.gif"), save_all=True, append_images=gif[1:],
                duration=round(1000 / a.fps), loop=0)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    lab = 24
    rows = -(-len(frames) // a.cols)
    sheet = Image.new("RGB", (min(a.cols, len(frames)) * W, rows * (H + lab)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(frames):
        x, y = i % a.cols * W, i // a.cols * (H + lab)
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + W - 1, y + H - 1], outline=(200, 200, 200))
        d.text((x + 4, y + H + 3), f"{n} K" if n in keys else str(n), fill=(200, 0, 0) if n in keys else "black", font=font)
    sheet.save(os.path.join(a.dir, f"contact_{tag}.png"))
    print(f"wrote preview_{tag}.gif ({len(frames)} frames) and contact_{tag}.png in {a.dir}")


if __name__ == "__main__":
    main()

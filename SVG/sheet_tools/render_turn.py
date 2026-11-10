"""Render the head-turn poses: a strip of all five and an animated GIF of the turn (cue marks hidden).

Usage:  python3 render_turn.py POSES_DIR [--crop 0,0,186,250] [--scale 3]
Writes POSES_DIR/turn_strip.png and POSES_DIR/head_turn_preview.gif.
"""
import argparse, io, os, re
from PIL import Image
from playwright.sync_api import sync_playwright

ORDER = [3, 2, 1, 2, 3, 4, 5, 4]       # front, turn one way, back, turn the other way


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poses")
    ap.add_argument("--crop", default="-6,-4,186,250", help="x,y,w,h of the view, V2 units")
    ap.add_argument("--scale", type=float, default=3)
    a = ap.parse_args()
    x, y, w, h = (float(v) for v in a.crop.split(","))
    frames = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": int(w * a.scale), "height": int(h * a.scale)})
        for n in range(1, 6):
            svg = open(os.path.join(a.poses, f"pose_{n}.svg"), encoding="utf-8").read()
            svg = re.sub(r'viewBox="[^"]+"', f'viewBox="{x} {y} {w} {h}" width="{w * a.scale}" height="{h * a.scale}"', svg, count=1)
            pg.set_content(f'<style>body{{margin:0;background:#fff}} [id^="head_cues"]{{display:none}}</style>{svg}')
            frames[n] = Image.open(io.BytesIO(pg.locator("svg").screenshot())).convert("RGB")
        b.close()
    W, H = frames[1].size
    strip = Image.new("RGB", (W * 5, H), "white")
    for n in range(1, 6):
        strip.paste(frames[n], ((n - 1) * W, 0))
    strip.save(os.path.join(a.poses, "turn_strip.png"))
    seq = [frames[n] for n in ORDER]
    seq[0].save(os.path.join(a.poses, "head_turn_preview.gif"), save_all=True, append_images=seq[1:],
                duration=[500 if n == 3 else 160 for n in ORDER], loop=0)
    print("wrote turn_strip.png and head_turn_preview.gif")


if __name__ == "__main__":
    main()

"""Preview a traced frame sequence: animated GIF + contact sheet.

Usage:  python preview_seq.py DIR [--set round] [--fps 12] [--width 300] [--cols 12]
DIR holds frame_NNNNN[_<set>].svg and cues.json; DIR/../run.json "keyframe_frames" marks K cells.
--set "" uses the plain frame_NNNNN.svg. Writes DIR/preview_<set>.gif and DIR/contact_<set>.png
(<set> = "traced" when empty).
"""
import argparse, io, json, os
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

# Draws the lids the viz will draw for a frame's data-lid (blink.js closeEyes): same geometry as blink.js lidsFor and
# setLid, with config.js BLINK's pad/curve/shut/line. Keep in step with those if they change.
LIDS_JS = """() => {
  const g = document.querySelector('#eyes[data-lid]'); if (!g) return;
  const amount = +g.dataset.lid, NS = 'http://www.w3.org/2000/svg', B = {pad: .18, curve: .28, shut: .25, line: .13, lineMin: 1.2};
  const coat = document.querySelector('.r-coat path');
  const fur = coat ? getComputedStyle(coat).fill : '#D78E34';
  const mk = (n, at, par) => { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); par.append(e); return e; };
  const inv = g.getCTM().inverse(); let n = 0;
  for (const eye of g.querySelectorAll('.kit-eye')) {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const el of eye.querySelectorAll('.k-eye-white')) {
      const b = el.getBBox(), m = inv.multiply(el.getCTM());
      for (const [x, y] of [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]) {
        const p = new DOMPoint(x, y).matrixTransform(m);
        x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); } }
    if (x1 < x0) continue;
    const w = x1 - x0, h = y1 - y0, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, pad = B.pad * h;
    const rx = w / 2 + pad, ry = h / 2 + pad, sag = B.curve * h, lw = Math.max(B.lineMin, B.line * h);
    const L = cx - rx - lw, R = cx + rx + lw, id = 'lidclip' + (++n);
    mk('ellipse', {cx, cy, rx, ry}, mk('clipPath', {id}, mk('defs', {}, g)));
    const clip = mk('g', {'clip-path': `url(#${id})`}, g);
    const edge = `M${L},0 Q${cx},${2 * sag} ${R},0`, shutAt = cy + B.shut * ry - sag;
    const upOpen = cy - ry - sag - lw, lowOpen = cy + ry + lw;
    mk('path', {d: `${edge} L${R},${3 * h} L${L},${3 * h} Z`, fill: fur,
                transform: `translate(0 ${lowOpen + amount * (shutAt - lowOpen)})`}, clip);
    const up = mk('g', {transform: `translate(0 ${upOpen + amount * (shutAt - upOpen)})`}, clip);
    mk('path', {d: `M${L},${-3 * h} L${R},${-3 * h} L${R},0 Q${cx},${2 * sag} ${L},0 Z`, fill: fur}, up);
    mk('path', {d: edge, fill: 'none', stroke: 'var(--cat-outline, #462E29)', 'stroke-width': lw, 'stroke-linecap': 'round'}, up);
  }
}"""


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
            pg.evaluate(LIDS_JS)
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

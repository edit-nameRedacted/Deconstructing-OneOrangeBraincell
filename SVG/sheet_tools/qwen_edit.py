"""Edit one keyframe with Qwen-Image-Edit-2511 (comfyui-wan, models on L:\\Models) over several seeds.

Each result is scaled back to the input's size. With --box, only that region (canvas px, feathered) is
taken from the edit and pasted onto the input, so the rest stays AC's drawing.
Writes OUT/seed_<n>.png (+ seed_<n>_raw.png, full res) and OUT/contact.png.
usage: qwen_edit.py IMAGE OUT --prompt "..." [--seeds 42,7,2024] [--box x0,y0,x1,y1] [--steps 4]
"""
import argparse, io, json, os
from PIL import Image, ImageDraw, ImageFilter
from flf_runner import ComfyClient, patch_graph

GRAPH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_edit_2511_api.json")
STYLE = (" Keep the same flat-colour 2D cartoon style, clean dark brown outlines, plain white background, "
         "same framing and size. Change nothing else.")


def paste_box(base, edit, box, feather=4):
    m = Image.new("L", base.size, 0)
    ImageDraw.Draw(m).rectangle(box, fill=255)
    out = base.copy()
    out.paste(edit, (0, 0), m.filter(ImageFilter.GaussianBlur(feather)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("image"); ap.add_argument("out")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seeds", default="42")
    ap.add_argument("--box")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--url", default="http://127.0.0.1:8189")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    src = Image.open(a.image).convert("RGBA")
    base = Image.new("RGBA", src.size, "white"); base.alpha_composite(src); base = base.convert("RGB")
    flat = os.path.join(a.out, "input.png"); base.save(flat)
    box = tuple(int(v) for v in a.box.split(",")) if a.box else None
    c = ComfyClient(a.url)
    name = c.upload(flat, "qwen_edit_input.png")
    graph = json.load(open(GRAPH, encoding="utf-8"))
    tiles = []
    for seed in (int(s) for s in a.seeds.split(",")):
        g = patch_graph(graph, {"image": {"image": name}, "positive": {"prompt": a.prompt + STYLE},
                                "sampler": {"seed": seed, "steps": a.steps}})
        raw = Image.open(io.BytesIO(c.images(c.wait(c.queue(g)))[0])).convert("RGB")
        raw.save(os.path.join(a.out, f"seed_{seed}_raw.png"))
        res = raw.resize(base.size, Image.LANCZOS)
        if box:
            res = paste_box(base, res, box)
        res.save(os.path.join(a.out, f"seed_{seed}.png"))
        tiles.append((seed, res))
        print(f"seed {seed}: {raw.size} -> {a.out}/seed_{seed}.png", flush=True)
    W, H = base.size
    sheet = Image.new("RGB", (W * (len(tiles) + 1), H + 16), "white")
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate([("input", base)] + tiles):
        sheet.paste(im, (i * W, 16)); d.text((i * W + 4, 2), str(label), fill="black")
    sheet.save(os.path.join(a.out, "contact.png"))


if __name__ == "__main__":
    main()

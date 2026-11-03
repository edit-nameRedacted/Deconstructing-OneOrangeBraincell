"""'AI opinion' of each cat from SigLIP 2 image-text similarity (no instruction tuning).
For each post: average the image embeddings of its stills/frames, then score each caption pair as
mean logit(pole A captions) - mean logit(pole B captions). Positive = leans to pole A.
Run with any env that has torch (CUDA) + transformers >= 4.49:
  python oobc_archive/ai_opinion/siglip_scores.py
"""
import csv, glob, os, sys
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

MODEL = "google/siglip2-so400m-patch14-384"
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", ".."))
SHEET = os.path.join(root, "Orange Braincell Data - InProgress.csv")
MEDIA = os.path.join(root, "oobc_media")
OUT = os.path.join(here, "siglip_scores.csv")

T = ["a photo of a {} cat.", "a {} cat.", "a picture of a {} cat.", "a close-up photo of a {} cat."]
def adj(words): return [t.format(w) for w in words for t in T]
PAIRS = {  # name: (pole A captions, pole B captions)
    "dumb":  (adj(["dumb", "stupid", "clueless"]),      adj(["smart", "clever", "intelligent"])),
    "cute":  (adj(["cute", "adorable"]),                 adj(["ugly", "unattractive"])),
    "fat":   (adj(["fat", "chubby", "chonky"]),          adj(["skinny", "thin", "slender"])),
    "derp":  (adj(["derpy", "goofy", "silly"]),          adj(["dignified", "serious", "majestic"])),
    "blank": (["a cat with nothing going on in its head.", "a cat staring blankly into space.",
               "a cat with no thoughts behind its eyes."],
              ["a cat thinking hard.", "a cat concentrating on a problem.", "a cat figuring something out."]),
    "loaf":  (["a photo of a loaf of bread.", "a loaf of bread."], ["a photo of a cat.", "a cat."]),
}

dev = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if dev == "cuda" else torch.float32
print("device", dev, "| loading", MODEL, flush=True)
model = AutoModel.from_pretrained(MODEL, torch_dtype=dtype).to(dev).eval()
proc = AutoProcessor.from_pretrained(MODEL)
scale, bias = model.logit_scale.exp().float(), model.logit_bias.float()

@torch.no_grad()
def text_emb(caps):
    t = proc(text=[c.lower() for c in caps], padding="max_length", max_length=64, truncation=True, return_tensors="pt").to(dev)
    e = model.get_text_features(**t).float()
    return e / e.norm(dim=-1, keepdim=True)
TXT = {k: (text_emb(a), text_emb(b)) for k, (a, b) in PAIRS.items()}

@torch.no_grad()
def post_emb(pid):
    files = sorted(glob.glob(os.path.join(MEDIA, pid, "*.jpg")))
    if not files: return None, 0
    ims = [Image.open(f).convert("RGB") for f in files]
    x = proc(images=ims, return_tensors="pt").to(dev)
    e = model.get_image_features(pixel_values=x["pixel_values"].to(dtype),
                                 **{k: v for k, v in x.items() if k != "pixel_values"}).float()
    e = e / e.norm(dim=-1, keepdim=True)
    m = e.mean(0); return m / m.norm(), len(files)

ids = [r["post_id"] for r in csv.DictReader(open(SHEET, encoding="utf-8-sig"))]
rows = []
for i, pid in enumerate(ids, 1):
    e, n = post_emb(pid)
    r = {"post_id": pid, "n_frames": n}
    if e is not None:
        for k, (a, b) in TXT.items():
            la = (scale * (a @ e) + bias).mean().item(); lb = (scale * (b @ e) + bias).mean().item()
            r[f"siglip_{k}"] = round(la - lb, 3)
    rows.append(r)
    if i % 25 == 0: print(f"{i}/{len(ids)}", flush=True)
cols = ["post_id", "n_frames"] + [f"siglip_{k}" for k in PAIRS]
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
print("wrote", OUT, len(rows), "posts")

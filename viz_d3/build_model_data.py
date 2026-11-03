"""
build_model_data.py — gather the two models' readings of each post into one file for the page.

Run (from anywhere):   python viz_d3/build_model_data.py
Writes:                viz_d3/model_data.json
Re-run it if the model outputs in oobc_archive/ai_opinion change.

Two models, both trained on large amounts of internet text and images, both run without any
instructions about this project:

  qwen   qwen3.5:9b, a language model that can read images. Shown each post's photos with its reply
         already started ("This cat is so" / "What a"), it gave probabilities for the next word.
         Those words were sorted into five families (cute, funny, calm, body, mind; see
         oobc_archive/ai_opinion/tokenprobs/summarize_tokenprobs.py). Per post this file keeps each
         family's probability, averaged over the two openings, and the top three words for each.
         Source: oobc_archive/ai_opinion/tokenprobs/tokenprobs_by_post.csv

  siglip google/siglip2-so400m-patch14-384, an image-text matching model. For each post it scored
         how much better the cat's images match one caption than its opposite (e.g. "a derpy cat"
         vs "a dignified cat"). Positive leans to the first caption. Six pairs: dumb, cute, fat,
         derp, blank, loaf (see oobc_archive/ai_opinion/siglip_scores.py).
         Source: oobc_archive/ai_opinion/ai_opinion.csv
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # Orange_Braincells
AI = os.path.join(ROOT, "oobc_archive", "ai_opinion")
DATA = os.path.join(ROOT, "oobc_archive", "viz", "oobc_viz_data.json")
OUT = os.path.join(HERE, "model_data.json")

FAMILIES = ["cute", "funny", "calm", "body", "mind"]
OPENINGS = {"so": "This cat is so", "whata": "What a"}
SIGLIP = ["dumb", "cute", "fat", "derp", "blank", "loaf"]


def number(text):
    return float(text) if text not in ("", None) else None


if __name__ == "__main__":
    with open(DATA, encoding="utf-8") as f:
        post_ids = [p["id"] for p in json.load(f)["posts"]]

    qwen_rows = {r["post_id"]: r for r in csv.DictReader(open(os.path.join(AI, "tokenprobs", "tokenprobs_by_post.csv"), encoding="utf-8-sig"))}
    siglip_rows = {r["post_id"]: r for r in csv.DictReader(open(os.path.join(AI, "ai_opinion.csv"), encoding="utf-8-sig"))}

    qwen, siglip = {}, {}
    for pid in post_ids:
        r = qwen_rows.get(pid)
        if r:
            entry = {}
            for fam in FAMILIES:
                values = [number(r.get(f"tp_{o}_p_{fam}")) for o in OPENINGS]
                values = [v for v in values if v is not None]
                entry[fam] = round(sum(values) / len(values), 4) if values else None
            entry["words"] = {OPENINGS[o]: (r.get(f"tp_{o}_top3") or "").split() for o in OPENINGS}
            qwen[pid] = entry
        r = siglip_rows.get(pid)
        if r and number(r.get("siglip_derp")) is not None:
            siglip[pid] = {k: number(r.get(f"siglip_{k}")) for k in SIGLIP}

    out = {
        "qwen": {"model": "qwen3.5:9b", "families": FAMILIES, "openings": list(OPENINGS.values()), "posts": qwen},
        "siglip": {"model": "google/siglip2-so400m-patch14-384", "scores": SIGLIP, "posts": siglip},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT}: qwen {len(qwen)} of {len(post_ids)} posts, siglip {len(siglip)} of {len(post_ids)} posts")

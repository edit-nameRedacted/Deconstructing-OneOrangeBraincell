"""Stage 1 summary of next-token probabilities. No hand codes are read here.
Word families were defined after looking at the vocabulary across all posts (exploratory).
Only the first token of each word is seen, so fragments ('cut', 'ador') are folded into the obvious family."""
import csv, json, math, os, collections
here = os.path.dirname(os.path.abspath(__file__))
R = [json.loads(l) for l in open(os.path.join(here, "tokenprobs_raw.jsonl"), encoding="utf-8")]
FAM = {
 "cute":  "cute cut adorable ador sweet lovely precious darling charming cudd cuddly beautiful handsome gorgeous heart wholesome pretty",
 "funny": "funny hilarious hilar silly goofy clumsy weird dramatic humorous chaotic strange ridiculous whims derpy fun",
 "calm":  "relaxed relaxing rel comfortable com comfy cozy chill lazy sleepy peaceful calm laid content",
 "body":  "fluffy fl furry big chubby fat round chunky tall little",
 "mind":  "expressive curious focused determined clever surprised shocked scared sad excited obsessed dedicated brave energetic playful confused hungry",
}
W2F = {w: f for f, ws in FAM.items() for w in ws.split()}
OPS = ["This cat is so", "What a"]
post = collections.defaultdict(dict)
for r in R:
    probs = [(t["token"].strip().lower(), math.exp(t["logprob"])) for t in r["top"]]
    words = [(w, p) for w, p in probs if w.isalpha()]
    wm = sum(p for _, p in words)
    fam = collections.Counter()
    for w, p in words: fam[W2F.get(w, "unassigned")] += p / wm
    ent = -sum((p / wm) * math.log(p / wm) for _, p in words)
    post[r["post_id"]][r["opening"]] = {"top3": " ".join(w for w, _ in words[:3]), "top1_p": round(words[0][1], 3),
        "word_mass": round(wm, 3), "entropy": round(ent, 3), **{f"p_{f}": round(fam[f], 3) for f in list(FAM) + ["unassigned"]},
        "funny_vs_cute": round(fam["funny"] / (fam["funny"] + fam["cute"]), 3) if fam["funny"] + fam["cute"] else ""}
keys = ["top3", "top1_p", "word_mass", "entropy"] + [f"p_{f}" for f in list(FAM) + ["unassigned"]] + ["funny_vs_cute"]
tag = {"This cat is so": "so", "What a": "whata"}
with open(os.path.join(here, "tokenprobs_by_post.csv"), "w", newline="", encoding="utf-8-sig") as f:
    cols = ["post_id"] + [f"tp_{tag[o]}_{k}" for o in OPS for k in keys]
    w = csv.DictWriter(f, cols); w.writeheader()
    for pid, d in post.items():
        w.writerow({"post_id": pid, **{f"tp_{tag[o]}_{k}": d.get(o, {}).get(k, "") for o in OPS for k in keys}})

def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]: j += 1
        for k in range(i, j + 1): r[s[k]] = (i + j) / 2
        i = j + 1
    return r
def spear(a, b):
    ra, rb = rank(a), rank(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    c = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); return c / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
both = [d for d in post.values() if all(o in d for o in OPS)]
out = [f"{len(post)} posts, {len(R)} calls"]
for o in OPS:
    rs = [d[o] for d in post.values() if o in d]
    out.append(f"\n== '{o} ___'  top-1 word: {collections.Counter(x['top3'].split()[0] for x in rs).most_common(8)}")
    for k in ["p_cute", "p_funny", "p_calm", "p_body", "p_mind", "p_unassigned", "entropy", "funny_vs_cute"]:
        v = sorted(float(x[k]) for x in rs if x[k] != "")
        out.append(f"   {k:14s} min {v[0]:.2f}  p10 {v[len(v)//10]:.2f}  median {v[len(v)//2]:.2f}  p90 {v[9*len(v)//10]:.2f}  max {v[-1]:.2f}")
out.append(f"\n== Stability across the two openings (Spearman, n={len(both)})")
for k in ["p_cute", "p_funny", "p_calm", "p_body", "p_mind", "entropy", "funny_vs_cute"]:
    a = [float(d[OPS[0]][k]) for d in both if d[OPS[0]][k] != "" and d[OPS[1]][k] != ""]
    b = [float(d[OPS[1]][k]) for d in both if d[OPS[0]][k] != "" and d[OPS[1]][k] != ""]
    out.append(f"   {k:14s} rho = {spear(a, b):+.2f}")
for o in OPS:
    rs = sorted(((pid, d[o]) for pid, d in post.items() if o in d), key=lambda x: -float(x[1]["funny_vs_cute"] or 0))
    out.append(f"\n'{o}' most funny-leaning: " + "; ".join(f"{p} [{x['top3']}] {x['funny_vs_cute']}" for p, x in rs[:5]))
    out.append(f"'{o}' most cute-leaning:  " + "; ".join(f"{p} [{x['top3']}] {x['funny_vs_cute']}" for p, x in rs[-3:]))
out.append("\nBread (wqtzrl): " + json.dumps({o: post["wqtzrl"][o] for o in OPS}))
open(os.path.join(here, "tokenprobs_summary.txt"), "w", encoding="utf-8").write("\n".join(out)); print("\n".join(out))

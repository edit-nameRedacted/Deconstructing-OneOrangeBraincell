"""Stage 2: the five tests in oobc_archive/ai_opinion/stage2_predictions.md, run once, as written.
Confirmatory set = coded posts NOT among the 35 listed in the predictions file (memorial posts are already
excluded from the sheet). One-sided Spearman, bootstrap 95% CI (2,000 resamples, seed 1), Holm within each family."""
import csv, os, re, numpy as np
from scipy.stats import spearmanr
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
A = lambda *p: os.path.join(root, *p)
rd = lambda p: {r["post_id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}
codes = rd(A("oobc_archive", "final_codes", "final_codes_2026-10-27.csv"))
pred = open(A("oobc_archive", "ai_opinion", "stage2_predictions.md"), encoding="utf-8").read()
used = set(re.search(r"excluded from the test\)\n(.+)", pred).group(1).replace(" ", "").split(","))
mem = set(rd(A("oobc_archive", "memorial_posts.csv")))
tp = rd(A("oobc_archive", "ai_opinion", "tokenprobs", "tokenprobs_by_post.csv"))
sg = rd(A("oobc_archive", "ai_opinion", "siglip_scores.csv"))
rs = rd(A("oobc_archive", "ai_opinion", "reasoning_measures.csv"))
cm = rd(A("oobc_archive", "comment_analysis", "comment_lexicon_by_post.csv"))
f = lambda v: float(v) if v not in ("", None, "NA") else np.nan
test_ids = [p for p in codes if p not in used and p not in mem]
MEAS = {
 1: ("qwen funny-vs-cute (mean of 2 openings)", lambda p: (f(tp[p]["tp_so_funny_vs_cute"]) + f(tp[p]["tp_whata_funny_vs_cute"])) / 2, "Dumb", +1),
 2: ("SigLIP derp", lambda p: f(sg[p]["siglip_derp"]), "Dumb", +1),
 3: ("trait-model reasoning length", lambda p: f(rs[p]["reasoning_chars"]), "Cuteness", -1),
 4: ("comments funny-vs-cute share", lambda p: f(cm[p]["cm_funny_vs_cute"]), "Dumb", +1),
 5: ("comments dumb words per 1k", lambda p: f(cm[p]["cm_dumb_per1k"]), "Dumb", +1),
}
rng = np.random.default_rng(1)
def run(k, ids):
    name, get, code, sign = MEAS[k]
    x = np.array([get(p) for p in ids]); y = np.array([f(codes[p][code]) for p in ids])
    m = ~np.isnan(x) & ~np.isnan(y); x, y = x[m], y[m]
    r, p2 = spearmanr(x, y)
    p1 = p2 / 2 if np.sign(r) == sign else 1 - p2 / 2
    bs = [spearmanr(x[i], y[i])[0] for i in (rng.integers(0, len(x), len(x)) for _ in range(2000))]
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return dict(k=k, name=name, code=code, dir="+" if sign > 0 else "-", n=len(x), rho=r, p1=p1, lo=lo, hi=hi)
def holm(res, alpha=0.05):
    order = sorted(res, key=lambda d: d["p1"]); m = len(order); stop = False
    for i, d in enumerate(order):
        d["p_holm"] = min(1.0, max(dd.get("p_holm", 0) for dd in order[:i]) if i else 0)
        d["p_holm"] = max(d["p_holm"], min(1.0, (m - i) * d["p1"]))
        d["supported"] = (not stop) and d["p_holm"] < alpha
        if not d["supported"]: stop = True
    return res
fam1 = holm([run(k, test_ids) for k in (1, 2, 3)]); fam2 = holm([run(k, test_ids) for k in (4, 5)])
out = ["# Stage 2 results", "", "Run once on 2026-10-27, as written in `oobc_archive/ai_opinion/stage2_predictions.md`.",
       f"Confirmatory set: {len(test_ids)} posts coded after the predictions were saved (the 35 earlier posts and 5 memorial posts excluded).",
       "Codes read from the Google Sheet (Sheet5) and checked cell by cell with checksums. Measure files matched their saved hashes.", "",
       "| # | Measure | Hand code | Predicted | n | Spearman rho | 95% CI | one-sided p | Holm p | Supported |", "|---|---|---|---|---|---|---|---|---|---|"]
for d in sorted(fam1 + fam2, key=lambda d: d["k"]):
    out.append(f"| {d['k']} | {d['name']} | {d['code']} | {d['dir']} | {d['n']} | {d['rho']:+.2f} | [{d['lo']:+.2f}, {d['hi']:+.2f}] | {d['p1']:.4f} | {d['p_holm']:.4f} | {'yes' if d['supported'] else 'no'} |")
out.append("\nHolm families: predictions 1-3, and predictions 4-5.")
# exploratory, clearly labelled
out += ["", "## Exploratory (not predicted; all 182 coded posts, no correction)", ""]
allids = [p for p in codes if p not in mem]
def ex(name, get, code):
    x = np.array([get(p) for p in allids]); y = np.array([f(codes[p][code]) for p in allids]); m = ~np.isnan(x) & ~np.isnan(y)
    r, p = spearmanr(x[m], y[m]); return f"- {name} vs {code}: rho {r:+.2f} (n={m.sum()}, two-sided p={p:.3f})"
for k in MEAS:
    for code in ("Dumb", "Cuteness"): out.append(ex(MEAS[k][0], MEAS[k][1], code))
out.append(ex("hand Cuteness", lambda p: f(codes[p]["Cuteness"]), "Dumb"))
# braincell groups
out += ["", "Means by braincell code (all 182):", ""]
grp = {}
for p in allids: grp.setdefault(codes[p]["Braincell Posession"], []).append(p)
out.append("| Braincell | n | Dumb | Cuteness | qwen funny-vs-cute | SigLIP derp | comments funny-vs-cute |"); out.append("|---|---|---|---|---|---|---|")
for g in ["What braincell?", "Seeking it", "Had it", "Has it", "Not applicable"]:
    ps = grp.get(g, []); mn = lambda fn: np.nanmean([fn(p) for p in ps])
    out.append(f"| {g} | {len(ps)} | {mn(lambda p: f(codes[p]['Dumb'])):.2f} | {mn(lambda p: f(codes[p]['Cuteness'])):.2f} | {mn(MEAS[1][1]):.2f} | {mn(MEAS[2][1]):+.2f} | {mn(MEAS[4][1]):.2f} |")
txt = "\n".join(out); open(A("oobc_archive", "final_codes", "stage2_results.md"), "w", encoding="utf-8").write(txt); print(txt)

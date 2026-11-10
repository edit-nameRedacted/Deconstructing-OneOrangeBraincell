"""Join SigLIP scores + reasoning measures, check them against model traits and the human hand codes.
Writes ai_opinion.csv (one row per post) and compare_report.txt."""
import csv, os, numpy as np
from scipy.stats import spearmanr
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", ".."))
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
sheet = rd(os.path.join(root, "Orange Braincell Data - InProgress.csv"))
sig = {r["post_id"]: r for r in rd(os.path.join(here, "siglip_scores.csv"))}
rea = {r["post_id"]: r for r in rd(os.path.join(here, "reasoning_measures.csv"))}
cat1 = {}
for r in rd(os.path.join(root, "oobc_heyday_2022-04_08_top40_cats.csv")): cat1.setdefault(r["post_id"], r)
BC = {"very_thin": 1, "thin": 2, "ideal": 3, "overweight": 4, "obese": 5}
AX = [k for k in next(iter(sig.values())) if k.startswith("siglip_")]
RM = ["model_seconds", "reasoning_chars", "second_guesses", "second_guesses_per_1k_chars", "model_confidence"]
num = lambda v: float(v) if str(v).strip() not in ("", "NA") else np.nan

rows = []
for s in sheet:
    p = s["post_id"]; c = cat1.get(p, {})
    rows.append({"post_id": p, **{k: sig.get(p, {}).get(k, "") for k in AX},
                 **{k: rea.get(p, {}).get(k, "") for k in ["reasoning_overflowed", "model_saw_cat"] + RM},
                 "_bc": BC.get(c.get("body_condition", ""), np.nan), "_kg": num(c.get("est_weight_kg", "")),
                 "_cute": num(s["Cuteness"]), "_dumb": num(s["Dumb"]), "_braincell": s["Braincell Posession"]})
with open(os.path.join(here, "ai_opinion.csv"), "w", newline="", encoding="utf-8-sig") as f:
    cols = [k for k in rows[0] if not k.startswith("_")]
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows({k: r[k] for k in cols} for r in rows)

out = []; P = lambda *a: out.append(" ".join(str(x) for x in a))
rng = np.random.default_rng(1)
def rho(xk, yk, boot=True):
    x = np.array([num(r[xk]) for r in rows]); y = np.array([num(r[yk]) for r in rows])
    m = ~np.isnan(x) & ~np.isnan(y); x, y = x[m], y[m]
    if len(x) < 8: return f"n={len(x)} too few"
    r, p = spearmanr(x, y)
    s = f"rho={r:+.2f} p={p:.3f} n={len(x)}"
    if boot:
        bs = [spearmanr(x[i], y[i])[0] for i in (rng.integers(0, len(x), len(x)) for _ in range(2000))]
        lo, hi = np.nanpercentile(bs, [2.5, 97.5]); s += f"  95% CI [{lo:+.2f}, {hi:+.2f}]"
    return s

P("== 1. Does SigLIP see what it should? (all posts with cat traits)")
P("siglip_fat vs model body condition :", rho("siglip_fat", "_bc"))
P("siglip_fat vs model est. weight    :", rho("siglip_fat", "_kg"))
P("\n== 2. Are the SigLIP axes separate, or one 'vibe'? (Spearman between axes)")
P(" " * 14 + "".join(f"{a[7:]:>8}" for a in AX))
for a in AX:
    P(f"{a[7:]:>14}" + "".join(f"{spearmanr([num(r[a]) for r in rows], [num(r[b]) for r in rows], nan_policy='omit')[0]:+8.2f}" for b in AX))
P("\n== 3. Against the human hand codes (35 coded posts)")
P("hand Cuteness vs hand Dumb:", rho("_cute", "_dumb"))
for a in AX + RM:
    P(f"{a:30s} vs Cuteness: {rho(a, '_cute')}")
    P(f"{'':30s} vs Dumb    : {rho(a, '_dumb')}")
P("\n== 4. Means by braincell code (hand)")
groups = sorted({r["_braincell"] for r in rows if r["_braincell"]})
for a in ["siglip_dumb", "siglip_blank", "siglip_derp", "siglip_cute", "second_guesses"]:
    P(f"{a:16s}", "  ".join(f"{g}: {np.nanmean([num(r[a]) for r in rows if r['_braincell']==g]):+.2f} (n={sum(1 for r in rows if r['_braincell']==g and not np.isnan(num(r[a])))})" for g in groups))
P("\n== 5. Extremes")
for a in AX:
    v = sorted([r for r in rows if r[a] != ""], key=lambda r: -float(r[a]))
    P(f"{a:14s} top: {[(r['post_id'], r[a]) for r in v[:3]]}  bottom: {[(r['post_id'], r[a]) for r in v[-2:]]}")
b = next(r for r in rows if r["post_id"] == "wqtzrl")
P("Bread:", {a: b[a] for a in AX}, "| loaf rank:", 1 + sum(float(r["siglip_loaf"]) > float(b["siglip_loaf"]) for r in rows if r["siglip_loaf"] != ""), "of", sum(1 for r in rows if r["siglip_loaf"] != ""))
open(os.path.join(here, "compare_report.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))

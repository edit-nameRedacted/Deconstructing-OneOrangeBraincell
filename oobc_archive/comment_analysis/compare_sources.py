"""Comments vs the computer measures (no hand codes). Reliability = split-half (odd vs even comments
by time), Spearman, stepped up with Spearman-Brown."""
import csv, json, math, os, statistics as st
here = os.path.dirname(os.path.abspath(__file__)); ai = os.path.join(here, "..", "ai_opinion")
rd = lambda p: {r["post_id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}
MEM = set(rd(os.path.join(here, "..", "memorial_posts.csv")))
cm = {p: r for p, r in rd(os.path.join(here, "comment_lexicon_by_post.csv")).items() if p not in MEM}  # memorial posts excluded
sg = rd(os.path.join(ai, "siglip_scores.csv")); tp = rd(os.path.join(ai, "tokenprobs", "tokenprobs_by_post.csv"))
rs = rd(os.path.join(ai, "reasoning_measures.csv"))
H = {r["post_id"]: r for r in csv.DictReader(open(os.path.join(here, "..", "..", "oobc_heyday_2022-04_08_top40.csv"), encoding="utf-8-sig"))}
halves = {d["post_id"]: d for d in json.load(open(os.path.join(here, "_split_halves.json")))}
def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]: j += 1
        for k in range(i, j + 1): r[s[k]] = (i + j) / 2
        i = j + 1
    return r
def sp(a, b):
    pr = [(x, y) for x, y in zip(a, b) if x == x and y == y]
    a, b = [x for x, _ in pr], [y for _, y in pr]; ra, rb = rank(a), rank(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return (num / den if den else float("nan")), n
f = lambda v: float(v) if v not in ("", None) else float("nan")
out = []; P = out.append
fams = ["cute", "funny", "braincell", "dumb", "smart", "body", "calm", "kin", "love", "grief"]
n_c = sorted(int(r["n_comments"]) for r in cm.values())
P(f"{len(cm)} posts (memorial posts excluded); comments per post: min {n_c[0]}, median {n_c[len(n_c)//2]}, max {n_c[-1]}")
P("\n== How common each family is (per 1,000 comment words), and split-half reliability (Spearman-Brown)")
for k in fams:
    v = sorted(f(r[f"cm_{k}_per1k"]) for r in cm.values())
    rho, n = sp([halves[p][f"_h0_{k}"] for p in cm], [halves[p][f"_h1_{k}"] for p in cm])
    P(f"  {k:10s} median {v[len(v)//2]:6.2f}  p90 {v[9*len(v)//10]:6.2f}  max {v[-1]:6.2f}  % comments using it (median post): {st.median(f(r[f'cm_{k}_pct_comments']) for r in cm.values()):5.1f}  reliability {2*rho/(1+rho):+.2f}")
rho, n = sp([halves[p]["_h0_fvc"] for p in cm], [halves[p]["_h1_fvc"] for p in cm])
P(f"  funny_vs_cute share: reliability {2*rho/(1+rho):+.2f} (n={n})")
P("\n== Internet (comments) vs computer (Spearman, posts with media)")
ids = [p for p in cm if sg.get(p, {}).get("siglip_derp")]
tpf = {p: (f(tp[p]["tp_so_funny_vs_cute"]) + f(tp[p]["tp_whata_funny_vs_cute"])) / 2 for p in tp}
comp = {"qwen funny_vs_cute": tpf, **{f"siglip {k}": {p: f(sg[p][f"siglip_{k}"]) for p in sg} for k in ["derp", "dumb", "cute", "fat", "loaf"]},
        "qwen reasoning_chars": {p: f(rs[p]["reasoning_chars"]) for p in rs}}
for c in ["cm_funny_vs_cute", "cm_funny_vs_cute_upvoted", "cm_funny_per1k", "cm_cute_per1k", "cm_dumb_per1k", "cm_braincell_per1k", "cm_body_per1k", "cm_kin_per1k", "cm_love_per1k", "cm_grief_per1k"]:
    cells = []
    for name, d in comp.items():
        rho, n = sp([f(cm[p][c]) for p in ids], [d.get(p, float("nan")) for p in ids]); cells.append(f"{name.split()[-1]}:{rho:+.2f}")
    P(f"  {c:26s} " + " ".join(cells))
P("  (columns: qwen funny_vs_cute, siglip derp, dumb, cute, fat, loaf, qwen reasoning_chars)")
P("\n== Internet vs post popularity")
for c in ["cm_funny_vs_cute", "cm_dumb_per1k", "cm_braincell_per1k", "cm_grief_per1k", "cm_love_per1k"]:
    a = [f(cm[p][c]) for p in cm]
    P(f"  {c:22s} vs score: {sp(a, [f(H[p]['score']) for p in cm])[0]:+.2f}   vs n_comments: {sp(a, [f(H[p]['comments']) for p in cm])[0]:+.2f}")
P("\n== Most funny-leaning and most cute-leaning comment sections (posts with 30+ comments)")
big = [p for p in cm if int(cm[p]["n_comments"]) >= 30 and cm[p]["cm_funny_vs_cute"] != ""]
big.sort(key=lambda p: -f(cm[p]["cm_funny_vs_cute"]))
for p in big[:5] + ["..."] + big[-5:]:
    P("  ..." if p == "..." else f"  {p} {f(cm[p]['cm_funny_vs_cute']):.2f} qwen {tpf.get(p, float('nan')):.2f}  {H[p]['title'][:70]!r}")
P("\n== Most grief-heavy comment sections")
for p in sorted(cm, key=lambda p: -f(cm[p]["cm_grief_per1k"]))[:5]:
    P(f"  {p} grief {cm[p]['cm_grief_per1k']}/1k  {H[p]['title'][:70]!r}")
P(f"\nBread (wqtzrl): " + json.dumps({k: cm['wqtzrl'][k] for k in ['n_comments', 'cm_funny_vs_cute', 'cm_body_per1k', 'cm_cute_per1k', 'cm_dumb_per1k']}))
open(os.path.join(here, "compare_sources.txt"), "w", encoding="utf-8").write("\n".join(out)); print("\n".join(out))

"""One data file for the cat visualization (heyday, 182 posts, memorial posts excluded).
- groupings: the categories a page can be arranged by (one typical cat per value)
- tailvars: what can sit on a tail (post data, the three sources, and cross-category membership)
- posts: one record per post
- groups[grouping][value]: the typical cat (continuous values + distinctive traits) and its tail values
Sources in this version: AC's hand codes and ratings, the image model's read of how each cat looks, and the
Reddit post data. The SigLIP, language-model and comment measures sit out for now (AC, 2026-10-27).
Typical-cat rule (AC, 2026-10-27): continuous values set amounts (median % white), and each group's most
over-represented traits (lift vs all posts) pick markings and body. Eyes: big-shiny for the highest mean
Cuteness and highest mean Dumb group in a view; other groups get a seeded random set from the other six."""
import csv, json, math, os, random, statistics as st, collections, datetime
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", ".."))
A = lambda *p: os.path.join(root, *p)
rd = lambda p: {r["post_id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}
codes = rd(A("oobc_archive", "final_codes", "final_codes_2026-10-27.csv"))
heyday = rd(A("oobc_heyday_2022-04_08_top40.csv")); meta = rd(A("oobc_archive", "heyday_post_meta.csv"))
cats = {}
for c in csv.DictReader(open(A("oobc_heyday_2022-04_08_top40_cats.csv"), encoding="utf-8-sig")): cats.setdefault(c["post_id"], c)
cats["wqtzrl"] = next(csv.DictReader(open(A("oobc_archive", "bread_rerun", "wqtzrl_cats.csv"), encoding="utf-8-sig")))
f = lambda v: float(v) if v not in ("", None, "NA") else None
ids = list(codes)

# ---- traits per post, in the kit's terms ----
ZONEMAP = {"chin_muzzle": ["chin", "muzzle"], "face_blaze": ["blaze"], "neck_throat": ["locket"], "chest": ["bib"],
           "stomach_belly": ["belly"], "front_paws": ["paws"], "back_paws": ["paws"], "legs": ["stockings"], "back_flank": ["body"]}
KIT_ZONES = ["chin", "locket", "muzzle", "bib", "blaze", "belly", "paws", "stockings", "face", "body"]
def body_class(c):
    if c.get("age_class") == "kitten": return "kitten"
    return {"lean": "slender", "underweight": "slender", "very_thin": "slender", "thin": "slender",
            "overweight": "chunky", "obese": "chunky"}.get(c.get("body_condition", ""), "typical")
def traits(p):
    c = cats.get(p, {})
    kg = f(c.get("est_weight_kg")); kg = kg if kg and kg < 20 else (kg / 1000 if kg else None)  # one grams-for-kg slip
    zones = sorted({z for k, zs in ZONEMAP.items() if c.get("white_" + k) == "1" for z in zs}, key=KIT_ZONES.index)
    return {"body": body_class(c), "kg": kg, "pct_white": f(c.get("pct_white")), "pct_orange": f(c.get("pct_orange")),
            "coat": c.get("coat_pattern", ""), "stripes": c.get("tabby_stripes") in ("True", "TRUE"), "zones": zones,
            "cat_count": int(c.get("cat_count") or 1)}

# ---- groupings ----
def anthro(p):
    k, v = codes[p]["Kin?"] == "1", codes[p]["Voiced?"] == "1"
    return "Kin and voiced" if k and v else "Kin" if k else "Voiced" if v else "Just a cat"
GROUPINGS = {
 "braincell": ("Braincell", ["What braincell?", "Seeking it", "Had it", "Has it", "Not applicable"], lambda p: codes[p]["Braincell Posession"]),
 "failure":   ("Failure mode", ["Self", "Physical", "Object", "Social", "NA"], lambda p: codes[p]["Failure Mode"]),
 "inferred":  ("Braincell status read from", ["Actions", "Expression", "Both", "Post context", "NA"], lambda p: codes[p]["Status Inferred By..."]),
 "anthro":    ("Treated as a person", ["Just a cat", "Kin", "Voiced", "Kin and voiced"], anthro),
 "dumb":      ("Dumbness (AC)", ["1", "2", "3", "4", "5"], lambda p: codes[p]["Dumb"]),
 "cute":      ("Cuteness (AC)", ["1", "2", "3", "4", "5"], lambda p: codes[p]["Cuteness"]),
}
# ---- tail variables (continuous) ----
TAILVARS = {
 "score":       ("Upvotes", "post", lambda p: f(heyday[p]["score"]), True),
 "comments":    ("Comments", "post", lambda p: f(heyday[p]["comments"]), True),
 "score_rel":   ("Upvotes per 1k subscribers", "post", lambda p: f(meta[p]["score_per_1k_subs"]), True),
 "talk":        ("Comments per 100 upvotes", "post", lambda p: f(meta[p]["comments_per_100_upvotes"]), True),
 "crossposts":  ("Crossposts", "post", lambda p: f(meta[p]["num_crossposts"]), False),
 "awards":      ("Awards", "post", lambda p: f(meta[p]["total_awards"]), False),
 "rank":        ("Rank in month", "post", lambda p: f(heyday[p]["rank_in_month"]), False),
 "ac_dumb":     ("Dumbness (AC)", "ac", lambda p: f(codes[p]["Dumb"]), False),
 "ac_cute":     ("Cuteness (AC)", "ac", lambda p: f(codes[p]["Cuteness"]), False),
 "look_white":  ("Share of white fur", "look", lambda p: traits(p)["pct_white"], False),
 "look_kg":     ("Estimated weight", "look", lambda p: traits(p)["kg"], False),
}
def pctl(xs, q):
    xs = sorted(xs); k = (len(xs) - 1) * q; i = int(k); return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)
def pct_rank(xs, v): return (sum(x < v for x in xs) + 0.5 * sum(x == v for x in xs)) / len(xs)
dists = {}
for k, (lab, src, fn, skew) in TAILVARS.items():
    xs = [fn(p) for p in ids if fn(p) is not None]
    d = {"n": len(xs), "p10": pctl(xs, .1), "p50": pctl(xs, .5), "p90": pctl(xs, .9), "min": min(xs), "max": max(xs)}
    if skew and min(xs) > 0:
        L = [math.log(x) for x in xs]; d.update(kind="lognormal", mu=st.mean(L), sd=st.stdev(L))
    else: d.update(kind="empirical")
    dists[k] = d

posts = []
for p in ids:
    h = heyday[p]
    posts.append({"id": p, "month": h["month"], "rank": int(h["rank_in_month"]), "title": h["title"],
                  "groups": {g: fn(p) for g, (_, _, fn) in GROUPINGS.items()},
                  "vals": {k: fn(p) for k, (_, _, fn, _) in TAILVARS.items()},
                  "tails": {k: ("left" if v < dists[k]["p10"] else "right" if v > dists[k]["p90"] else "body") if v is not None else None
                            for k, v in ((k, fn(p)) for k, (_, _, fn, _) in TAILVARS.items())},
                  "traits": traits(p)})
P = {x["id"]: x for x in posts}

# ---- typical cat per group ----
def share(ps, test):
    ps = [p for p in ps if P[p]["traits"]["pct_white"] is not None]; return sum(1 for p in ps if test(P[p]["traits"])) / len(ps) if ps else 0
ALL = [p for p in ids if P[p]["traits"]["pct_white"] is not None]
def typical_cat(ps):
    ps_t = [p for p in ps if P[p]["traits"]["pct_white"] is not None]
    if not ps_t: return None
    T = lambda p: P[p]["traits"]
    # amounts: continuous
    pw = st.median(T(p)["pct_white"] for p in ps_t)
    kg = st.mean(T(p)["kg"] for p in ps_t if T(p)["kg"])
    solid = share(ps_t, lambda t: t["coat"] == "pure_orange")
    stripes = share(ps_t, lambda t: t["stripes"]) >= 0.5
    # distinctiveness: lift of each body class and zone vs all posts
    dist = []
    MIN = 3  # a trait needs at least 3 cats in the group to count as distinctive
    cnt = lambda test: sum(1 for p in ps_t if test(T(p)))
    for b in ["kitten", "slender", "chunky"]:
        test = lambda t, b=b: t["body"] == b
        s, s0 = share(ps_t, test), share(ALL, test)
        if s0 and cnt(test) >= MIN: dist.append(("body", b, s, s / s0))
    for z in KIT_ZONES:
        test = lambda t, z=z: z in t["zones"]
        s, s0 = share(ps_t, test), share(ALL, test)
        if s0 and cnt(test) >= MIN: dist.append(("zone", z, s, s / s0))
    test = lambda t: t["coat"] == "pure_orange"
    if cnt(test) >= MIN: dist.append(("coat", "solid orange", solid, solid / share(ALL, test)))
    body = next((b for kind, b, s, lift in sorted(dist, key=lambda d: -d[3]) if kind == "body" and lift >= 1.5 and s >= 0.25), "typical")
    zones_extra = [z for kind, z, s, lift in dist if kind == "zone" and lift >= 1.3 and s >= 0.3]
    top = sorted([d for d in dist if d[3] > 1], key=lambda d: -d[3])[:2]
    return {"n_drawn": len(ps_t), "body": body, "kg_mean": round(kg, 2), "pct_white_median": pw, "solid_orange_share": round(solid, 3),
            "stripes": stripes, "zones_distinctive": zones_extra, "small_group": len(ps_t) < 10,
            "distinctive": [{"kind": k, "trait": t, "share": round(s, 3), "lift": round(l, 2)} for k, t, s, l in top]}
EYES_OTHER = ["original", "almond", "round", "slit", "half-lidded", "squint"]
groups = {}
for g, (lab, order, fn) in GROUPINGS.items():
    groups[g] = {}
    for v in order:
        ps = [p for p in ids if fn(p) == v]
        if not ps: continue
        tail = {}
        for k, (tl, src, tfn, _) in TAILVARS.items():
            xs_all = [tfn(p) for p in ids if tfn(p) is not None]; xs = [tfn(p) for p in ps if tfn(p) is not None]
            med = st.median(xs) if xs else None
            tail[k] = {"median": med, "pct": round(pct_rank(xs_all, med), 3) if med is not None else None, "n": len(xs)}
        cross = {g2: {v2: round(sum(1 for p in ps if fn2(p) == v2) / len(ps), 3) for v2 in o2}
                 for g2, (_, o2, fn2) in GROUPINGS.items() if g2 != g}
        groups[g][v] = {"n": len(ps), "post_ids": ps, "cat": typical_cat(ps), "tail": tail, "cross": cross,
                        "mean_dumb": round(st.mean(f(codes[p]["Dumb"]) for p in ps), 2), "mean_cute": round(st.mean(f(codes[p]["Cuteness"]) for p in ps), 2)}
    # eyes: big-shiny for top mean cute and top mean dumb in this view; others seeded random
    vals = list(groups[g]); top = {max(vals, key=lambda v: groups[g][v]["mean_cute"]), max(vals, key=lambda v: groups[g][v]["mean_dumb"])}
    for v in vals:
        rng = random.Random(f"{g}:{v}")
        groups[g][v]["eyes"] = "big-shiny" if v in top else rng.choice(EYES_OTHER)
        groups[g][v]["eyes_reason"] = ("highest mean cuteness" if v == max(vals, key=lambda x: groups[g][x]["mean_cute"]) else "") + \
                                      (" / " if v in top and v == max(vals, key=lambda x: groups[g][x]["mean_cute"]) and v == max(vals, key=lambda x: groups[g][x]["mean_dumb"]) else "") + \
                                      ("highest mean dumbness" if v == max(vals, key=lambda x: groups[g][x]["mean_dumb"]) else "")
out = {"meta": {"built": datetime.date.today().isoformat(), "n_posts": len(ids), "set": "heyday top 40 per month, Apr-Aug 2022; memorial posts excluded",
                "typical_cat_rule": __doc__.split("Typical-cat rule")[1].strip()},
       "groupings": {g: {"label": lab, "values": [v for v in order if v in groups[g]]} for g, (lab, order, _) in GROUPINGS.items()},
       "tailvars": {k: {"label": lab, "source": src, "dist": dists[k]} for k, (lab, src, _, _) in TAILVARS.items()},
       "posts": posts, "groups": groups}
json.dump(out, open(os.path.join(here, "oobc_viz_data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", os.path.join(here, "oobc_viz_data.json"), os.path.getsize(os.path.join(here, "oobc_viz_data.json")), "bytes")
for g in out["groupings"]:
    print(f"\n== {g}")
    for v in out["groupings"][g]["values"]:
        G = groups[g][v]; c = G["cat"]
        print(f"  {v:16s} n={G['n']:3d} eyes={G['eyes']:11s} body={c['body']:8s} white={c['pct_white_median']:5.1f}% solid={c['solid_orange_share']:.0%} extra_zones={c['zones_distinctive']} top={[(d['trait'], d['lift']) for d in c['distinctive']]} {G['eyes_reason']}")

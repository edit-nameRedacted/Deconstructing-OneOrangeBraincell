"""Rebuild the InProgress coding sheet: one row per heyday post (200), in heyday order.
Coded rows keep the human coder's values; everything else comes from the heyday + cats source files.
Multi-cat posts keep cat 1. Failure Mode = NA where braincell is Not applicable."""
import csv, collections, sys
SHEET = "Orange Braincell Data - InProgress.csv"
old = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
cols = list(old[0].keys())
idcol = "post_id" if "post_id" in cols else ""
heyday = list(csv.DictReader(open("oobc_heyday_2022-04_08_top40.csv", encoding="utf-8-sig")))
cats = collections.defaultdict(list)
for c in csv.DictReader(open("oobc_heyday_2022-04_08_top40_cats.csv", encoding="utf-8-sig")):
    cats[c["post_id"]].append(c)
CODE = ["Braincell Posession", "Failure Mode", "Kin?", "Voiced?", "Status Inferred By...", "Cuteness", "Dumb"]
TRAIT = cols[cols.index("main_colour"):]
coded = {}
for r in old:
    if any(r[c].strip() for c in CODE):
        pid = r[idcol].strip()
        if pid in coded: sys.exit(f"post {pid} coded twice - stopping")
        coded[pid] = r

def fmt(k, v):
    v = (v or "").strip()
    if v in ("True", "False"): return v.upper()
    if k == "est_weight_lb" and v.endswith(".0"): return v[:-2]
    return v

out_cols = ["post_id", "month", "rank_in_month", "score", "comments", "cat_count"] + CODE + TRAIT
rows = []
for h in heyday:
    pid = h["post_id"]; c = cats.get(pid, [{}])[0]
    r = {"post_id": pid, "month": h["month"], "rank_in_month": h["rank_in_month"],
         "score": h["score"], "comments": h["comments"],
         "cat_count": c.get("cat_count", "") if c.get("error", "") == "" else ""}
    src = coded.get(pid)
    for k in CODE: r[k] = src[k].strip() if src else ""
    for k in TRAIT: r[k] = fmt(k, (src or c).get(k, "")) if src else fmt(k, c.get(k, ""))
    if r["Braincell Posession"] == "Not applicable": r["Failure Mode"] = "NA"
    rows.append(r)
with open(SHEET, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, out_cols); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} rows, {len(coded)} coded kept, {sum(r['Failure Mode']=='NA' for r in rows)} set to NA")

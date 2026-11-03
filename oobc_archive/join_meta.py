"""Add the archive metadata columns to any CSV with a post_id column.
Usage: python oobc_archive/join_meta.py "<your sheet>.csv"
Writes "<your sheet>_with_meta.csv" next to it; the original is untouched."""
import csv, os, sys
here = os.path.dirname(os.path.abspath(__file__))
meta = {r["post_id"]: r for r in csv.DictReader(open(os.path.join(here, "heyday_post_meta.csv"), encoding="utf-8-sig"))}
src = sys.argv[1]
rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
cols = list(rows[0].keys())
idcol = "post_id" if "post_id" in cols else max(cols, key=lambda c: sum(r[c].strip() in meta for r in rows))
print("post id column:", repr(idcol))
add = [c for c in next(iter(meta.values())) if c != "post_id" and c not in cols]
out = os.path.splitext(src)[0] + "_with_meta.csv"
hit = 0
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, cols + add); w.writeheader()
    for r in rows:
        m = meta.get(r.get(idcol, "").strip())
        hit += bool(m)
        w.writerow({**r, **({c: m[c] for c in add} if m else {})})
print(f"{hit}/{len(rows)} rows matched -> {out}")

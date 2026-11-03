"""Build per-post metadata for the heyday 200 from the Arctic Shift pulls.
Outputs:
  oobc_archive/heyday_post_meta.csv          post_id + new columns (join onto any sheet)
  oobc_heyday_2022-04_08_top40_enriched.csv  heyday file + new columns
"""
import csv, json, os, collections, datetime as dt
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.join(here, "..")
heyday = list(csv.DictReader(open(os.path.join(root, "oobc_heyday_2022-04_08_top40.csv"), encoding="utf-8-sig")))
posts = {p["id"]: p for p in map(json.loads, open(os.path.join(here, "heyday_posts_raw.jsonl"), encoding="utf-8"))}
utc = lambda t: dt.datetime.fromtimestamp(int(t), dt.timezone.utc)
clean = lambda s: " ".join((s or "").split())
memorial = {r["post_id"]: r["status"] for r in csv.DictReader(open(os.path.join(here, "memorial_posts.csv"), encoding="utf-8-sig"))}
authors = collections.Counter(p["author"] for p in posts.values() if p["author"] != "[deleted]")

def pct_rank(vals, v):  # percentile of v within vals (0-100, midrank)
    below = sum(x < v for x in vals); eq = sum(x == v for x in vals)
    return round(100 * (below + 0.5 * eq) / len(vals), 1)

by_month = collections.defaultdict(list)
for r in heyday: by_month[r["month"]].append(r["post_id"])

rows = []
for r in heyday:
    pid = r["post_id"]; p = posts[pid]
    posted, captured = utc(p["created_utc"]), utc(p["retrieved_on"])
    subs = p.get("subreddit_subscribers") or 0
    vid = ((p.get("media") or {}).get("reddit_video") or {}) if isinstance(p.get("media"), dict) else {}
    cm = json.load(open(os.path.join(here, "comments", pid + ".json"), encoding="utf-8"))
    live = [c for c in cm if c["body"] not in ("[deleted]", "[removed]")]
    top = sorted([c for c in live if c["parent_id"] == "t3_" + pid and c["author"] != "AutoModerator"], key=lambda c: -(c["score"] or 0))
    op = sorted([c for c in live if c.get("is_submitter")], key=lambda c: c["created_utc"])
    mates = by_month[r["month"]]
    sc = [posts[m]["score"] for m in mates]; nc = [posts[m]["num_comments"] for m in mates]
    acct_age = (posted - utc(p["author_created_utc"])).days if p.get("author_created_utc") else ""
    rows.append({
        "post_id": pid,
        "memorial": memorial.get(pid, ""),
        "posted_utc": posted.strftime("%Y-%m-%d %H:%M"),
        "posted_weekday": posted.strftime("%a"),
        "posted_hour_utc": posted.hour,
        "captured_utc": captured.strftime("%Y-%m-%d %H:%M"),
        "capture_lag_days": round((captured - posted).total_seconds() / 86400, 1),
        "upvote_ratio": round(p["upvote_ratio"], 2),
        "subscribers_at_capture": subs,
        "score_per_1k_subs": round(1000 * p["score"] / subs, 1) if subs else "",
        "score_pct_in_month": pct_rank(sc, p["score"]),
        "comments_pct_in_month": pct_rank(nc, p["num_comments"]),
        "comments_per_100_upvotes": round(100 * p["num_comments"] / p["score"], 2) if p["score"] else "",
        "num_crossposts": p.get("num_crossposts", 0),
        "is_crosspost": int(bool(p.get("crosspost_parent"))),
        "total_awards": p.get("total_awards_received", 0),
        "gilded": p.get("gilded", 0),
        "n_gallery_images": len((p.get("gallery_data") or {}).get("items", [])) if p.get("is_gallery") else "",
        "video_duration_s": vid.get("duration", ""),
        "domain": p.get("domain", ""),
        "locked": int(bool(p.get("locked"))),
        "over_18": int(bool(p.get("over_18"))),
        "selftext": clean(p.get("selftext")),
        "author": p["author"],
        "author_account_age_days": acct_age,
        "author_posts_in_set": authors.get(p["author"], ""),
        "comments_archived": len(cm),
        "op_commented": int(bool(op)),
        "op_first_comment": clean(op[0]["body"])[:500] if op else "",
        "top_comment": clean(top[0]["body"])[:500] if top else "",
        "top_comment_score": top[0]["score"] if top else "",
        "top_comments_2_3": " || ".join(clean(c["body"])[:300] for c in top[1:3]),
    })

cols = list(rows[0].keys())
with open(os.path.join(here, "heyday_post_meta.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
meta = {m["post_id"]: m for m in rows}
hcols = list(heyday[0].keys())
with open(os.path.join(root, "oobc_heyday_2022-04_08_top40_enriched.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, hcols + cols[1:]); w.writeheader()
    for r in heyday: w.writerow({**r, **{k: v for k, v in meta[r["post_id"]].items() if k != "post_id"}})
print("wrote", len(rows), "rows,", len(cols) - 1, "new columns")

"""Fetch all archived comments for the heyday posts from Arctic Shift.
Resumable: one JSON file per post in oobc_archive/comments/. Stops after --max-seconds."""
import csv, json, os, sys, time, requests
API = "https://arctic-shift.photon-reddit.com/api/comments/search"
here = os.path.dirname(os.path.abspath(__file__))
outdir = os.path.join(here, "comments"); os.makedirs(outdir, exist_ok=True)
src = os.path.join(here, "..", "oobc_heyday_2022-04_08_top40.csv")
ids = [r["post_id"] for r in csv.DictReader(open(src, encoding="utf-8-sig"))]
budget = float(sys.argv[1]) if len(sys.argv) > 1 else 150
t0 = time.time(); done = 0
for pid in ids:
    fp = os.path.join(outdir, pid + ".json")
    if os.path.exists(fp): continue
    if time.time() - t0 > budget: break
    allc, after = {}, None
    while True:
        params = {"link_id": pid, "limit": 100, "sort": "asc"}
        if after: params["after"] = after
        r = requests.get(API, params=params, timeout=60); r.raise_for_status()
        d = r.json()["data"]
        new = [c for c in d if c["id"] not in allc]
        for c in new: allc[c["id"]] = c
        if len(d) < 100 or not new: break
        after = max(c["created_utc"] for c in d)
        time.sleep(0.4)
    keep = ["id","parent_id","author","is_submitter","score","created_utc","body","controversiality","total_awards_received"]
    json.dump([{k: c.get(k) for k in keep} for c in allc.values()], open(fp, "w", encoding="utf-8"))
    done += 1; time.sleep(0.4)
left = sum(1 for p in ids if not os.path.exists(os.path.join(outdir, p + ".json")))
print("fetched", done, "remaining", left)

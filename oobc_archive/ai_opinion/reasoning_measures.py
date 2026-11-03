"""Per-post measures of how the trait model (qwen3.5:9b, prompt v4) behaved, from the raw replies.
reasoning_overflowed = 1 when the reasoning ran past the 6,000-token cap and the script re-asked
without reasoning; reasoning length and second-guess counts are blank for those posts."""
import csv, json, os, re
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", ".."))
RAW = os.path.join(root, "oobc_heyday_2022-04_08_top40_cats_raw.jsonl")
OUT = os.path.join(here, "reasoning_measures.csv")
DOUBT = re.compile(r"\b(wait|actually|re-?evaluat\w*|re-?read\w*|let me look|look(ing)? (again|closely|really)|hmm+|on second)\b", re.I)
CONF = {"low": 1, "medium": 2, "high": 3}
rows = []
for line in open(RAW, encoding="utf-8"):
    d = json.loads(line)
    if "result" not in d: continue
    t = d.get("thinking") or ""; over = not d.get("thought")
    cats = d["result"].get("cats") or []
    rows.append({
        "post_id": d["post_id"],
        "model_seconds": d.get("seconds", ""),
        "reasoning_overflowed": int(over),
        "reasoning_chars": "" if over else len(t),
        "second_guesses": "" if over else len(DOUBT.findall(t)),
        "second_guesses_per_1k_chars": "" if over or not t else round(1000 * len(DOUBT.findall(t)) / len(t), 2),
        "model_saw_cat": int(d["result"].get("cat_count", 0) > 0),
        "model_confidence": CONF.get((cats[0].get("confidence") if cats else ""), ""),
    })
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
print("wrote", len(rows), "posts;", sum(r["reasoning_overflowed"] for r in rows), "overflowed")

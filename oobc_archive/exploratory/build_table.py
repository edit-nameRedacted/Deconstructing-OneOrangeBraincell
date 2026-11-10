"""Assemble one row per heyday post (182) with every per-post variable we have.

Usage: python build_table.py <Orange_Braincells folder> <out.csv>

Sources (all already in the project):
  oobc_archive/viz/oobc_viz_data.json         hand-code groups, post values, per-post cat traits (as the viz uses them)
  oobc_archive/final_codes/final_codes_*.csv  Kin? and Voiced? as separate 0/1 codes
  oobc_heyday_2022-04_08_top40_cats.csv       Qwen trait model: age class and body condition (first cat of the post)
  oobc_archive/ai_opinion/ai_opinion.csv      SigLIP 2 caption scores; trait-model reasoning measures
  oobc_archive/ai_opinion/tokenprobs/...      Qwen next-word shares (mean of the two openings)
  oobc_archive/comment_analysis/...           comment word rates per 1,000 words
  oobc_archive/heyday_post_meta.csv           posting time, popularity within month, author, media
  oobc_heyday_2022-04_08_top40.csv            media kind, flair
"""
import csv, json, os, sys
import numpy as np, pandas as pd

root, out = sys.argv[1], sys.argv[2]
P = lambda *p: os.path.join(root, *p)
rd = lambda p: pd.read_csv(p, encoding="utf-8-sig", dtype=str).set_index("post_id")

viz = json.load(open(P("oobc_archive", "viz", "oobc_viz_data.json"), encoding="utf-8"))
rows = []
for p in viz["posts"]:
    t = p.get("traits") or {}
    rows.append(dict(
        post_id=p["id"], month=p["month"],
        braincell=p["groups"]["braincell"], failure=p["groups"]["failure"], inferred=p["groups"]["inferred"],
        anthro=p["groups"]["anthro"], dumb=p["vals"].get("ac_dumb"), cute=p["vals"].get("ac_cute"),
        score=p["vals"].get("score"), n_comments=p["vals"].get("comments"), rank=p["vals"].get("rank"),
        body_type=t.get("body"), kg=t.get("kg"), pct_white=t.get("pct_white"), pct_orange=t.get("pct_orange"),
        coat=t.get("coat"), stripes=t.get("stripes"), n_white_zones=len(t.get("zones") or []) if t else None,
        cat_count=t.get("cat_count"),
    ))
df = pd.DataFrame(rows).set_index("post_id")

codes = rd(P("oobc_archive", "final_codes", "final_codes_2026-10-27.csv"))
df["kin"] = codes["Kin?"].astype(float)
df["voiced"] = codes["Voiced?"].astype(float)

cats = pd.read_csv(P("oobc_heyday_2022-04_08_top40_cats.csv"), encoding="utf-8-sig", dtype=str)
first = cats[cats["cat_n"].isin(["1", "1.0"])].drop_duplicates("post_id").set_index("post_id")
df["age_class"] = first["age_class"].reindex(df.index)
df["body_condition"] = first["body_condition"].reindex(df.index)
df["media_kind"] = rd(P("oobc_heyday_2022-04_08_top40.csv"))["media_kind"].reindex(df.index)

ai = rd(P("oobc_archive", "ai_opinion", "ai_opinion.csv"))
for c in ["siglip_dumb", "siglip_cute", "siglip_fat", "siglip_derp", "siglip_blank", "siglip_loaf",
          "reasoning_chars", "second_guesses", "model_confidence"]:
    df[c] = pd.to_numeric(ai[c].reindex(df.index), errors="coerce")
df.loc[ai["reasoning_overflowed"].reindex(df.index) == "1", ["reasoning_chars", "second_guesses"]] = np.nan

tp = rd(P("oobc_archive", "ai_opinion", "tokenprobs", "tokenprobs_by_post.csv"))
for w in ["cute", "funny", "calm", "body", "mind"]:
    a = pd.to_numeric(tp[f"tp_so_p_{w}"], errors="coerce"); b = pd.to_numeric(tp[f"tp_whata_p_{w}"], errors="coerce")
    df[f"qwen_{w}"] = ((a + b) / 2).reindex(df.index)

cm = rd(P("oobc_archive", "comment_analysis", "comment_lexicon_by_post.csv"))
for w in ["cute", "funny", "braincell", "dumb", "smart", "body", "calm", "kin", "love", "grief"]:
    df[f"cm_{w}"] = pd.to_numeric(cm[f"cm_{w}_per1k"], errors="coerce").reindex(df.index)

meta = rd(P("oobc_archive", "heyday_post_meta.csv"))
num = lambda c: pd.to_numeric(meta[c], errors="coerce").reindex(df.index)
df["score_pct_in_month"] = num("score_pct_in_month")
df["comments_pct_in_month"] = num("comments_pct_in_month")
df["comments_per_100_upvotes"] = num("comments_per_100_upvotes")
df["upvote_ratio"] = num("upvote_ratio")
df["posted_hour_utc"] = num("posted_hour_utc")
df["author_account_age_days"] = num("author_account_age_days")
df["op_commented"] = (meta["op_commented"].reindex(df.index).str.lower().isin(["1", "true", "yes"])).astype(float)
df["crossposts"] = num("num_crossposts")
df["author"] = meta["author"].reindex(df.index)

for c in ["dumb", "cute", "score", "n_comments", "rank", "kg", "pct_white", "pct_orange", "n_white_zones", "cat_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["stripes"] = df["stripes"].map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0})
df.to_csv(out, encoding="utf-8")
print(df.shape)

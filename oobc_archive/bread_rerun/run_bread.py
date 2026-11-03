"""Re-run the trait model on Bread (wqtzrl) with the prompt told there is a cat in the photo."""
import os, sys
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.abspath(os.path.join(here, "..", ".."))
sys.path.insert(0, root)
import oobc_cat_traits as m
OLD = "If there is no cat at all, return cat_count 0 and an empty cats list."
assert OLD in m.PROMPT
m.PROMPT = m.PROMPT.replace(OLD, "A human coder has confirmed there is a cat in this photo. Code it as a cat.")
m.PROMPT_VERSION = "v4-cat-confirmed"
import json
_saved = {d["id"]: d for d in map(json.loads, open(os.path.join(root, "oobc_archive", "heyday_posts_raw.jsonl"), encoding="utf-8"))}
m.archive_lookup = lambda ids: {i: _saved[i] for i in ids if i in _saved}  # use the saved archive record, no network
sys.argv = ["oobc_cat_traits.py", os.path.join(here, "wqtzrl.csv"),
            "--media-dir", os.path.join(root, "oobc_media"),
            "--out", os.path.join(here, "wqtzrl_cats.csv"),
            "--raw", os.path.join(here, "wqtzrl_cats_raw.jsonl")]
m.main()

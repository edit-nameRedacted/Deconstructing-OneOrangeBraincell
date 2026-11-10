# oobc_archive: data pulls, coding and analysis

Scripts run from the project folder (for example `python oobc_archive/join_meta.py ...`).

| Path | What it is |
| --- | --- |
| `heyday_posts_raw.jsonl`, `heyday_post_meta.csv` | The heyday 200 as pulled from Arctic Shift, and 30 metadata columns per post (`build_post_meta.py`) |
| `join_meta.py` | Adds those metadata columns to any CSV with a `post_id` column |
| `clean_inprogress.py` | Rebuilds the hand-coding sheet (`Orange Braincell Data - InProgress.csv`) |
| `memorial_posts.csv` | Posts about cats that had died, excluded everywhere |
| `fetch_comments.py` → `comments/` | Every archived comment, one JSON file per post |
| `final_codes/` | The frozen hand codes, the stage 2 test script and its results |
| `ai_opinion/` | The models' readings: SigLIP scores, Qwen token probabilities (`tokenprobs/`), reasoning measures, the saved predictions |
| `comment_analysis/` | What the comments say: word families per post and how they compare with the models |
| `bread_rerun/` | The trait-model rerun for Bread (`wqtzrl`), the loaf-shaped cat |
| `exploratory/` | Which codes, traits and measures travel together (see its README) |
| `viz/build_viz_data.py` → `viz/oobc_viz_data.json` | **The data file both visualizations read** |

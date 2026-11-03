# r/OneOrangeBraincell — current state

Nov 1, 2026 · @AC

## Summary

The heyday coding is finished (182 posts) and four of five pre-registered predictions held. A working single-file prototype of the typical-cat visualization exists, and the next step is rebuilding it as a native HTML/JS page built mainly on D3. The data-handling detail lives in the earlier [data handling handoff](https://claude.ai/artifact/2UxaRFmaVeTyqhsPLsadTi); this doc is the snapshot as of the date above.

## Data and coding

All 182 heyday posts (top 40 a month, Apr–Aug 2022) are hand-coded, and Sheet5 of the Google Sheet *Orange Braincell Data* is the master copy. A frozen copy is `oobc_archive/final_codes/final_codes_2026-10-27.csv`, checked against the sheet with checksums.

| Item | Status |
| --- | --- |
| Sample | 200 posts, minus 13 with dead media and 5 memorial posts = 182 (Bread kept) |
| Hand codes | Braincell, failure mode, kin, voiced, status inferred by, cuteness 1–5, dumbness 1–5 |
| Cat traits | qwen3.5:9b on all posts; Bread rerun with a "there is a cat" prompt (`oobc_archive/bread_rerun/`) |
| Archive metadata | 30 columns per post (`oobc_archive/heyday_post_meta.csv`), all comments saved |
| Memorial posts | 5, listed in `oobc_archive/memorial_posts.csv`, excluded everywhere |
| 6-month sets | Not coded; not needed for this version |

**Coding rules settled:**

- Failure mode values: Self, Physical, Object, Social, Other; NA when braincell is Not applicable. Has it keeps a failure mode.
- Status inferred by: Actions, Expression, Both, Post context; NA for Not applicable posts, except when the cat is a prop for a title joke, which is Not applicable + Post context.
- "Orange" used to mean dumb counts as dumb talk in comments.

## Analysis

Four of five predictions held on the 147 posts coded after they were saved (one-sided Spearman, Holm-corrected). Full results: `oobc_archive/final_codes/stage2_results.md`; predictions: `oobc_archive/ai_opinion/stage2_predictions.md`.

| # | Source | Measure vs hand code | rho \[95% CI\] | Held |
| --- | --- | --- | --- | --- |
| 1 | Computer | qwen funny-vs-cute vs Dumb | +0.29 \[0.14, 0.43\] | yes |
| 2 | Computer | SigLIP derp vs Dumb | +0.42 \[0.29, 0.54\] | yes |
| 3 | Computer | Reasoning length vs Cuteness | −0.06 \[−0.23, 0.11\] | no |
| 4 | Internet | Comments funny-vs-cute vs Dumb | +0.30 \[0.15, 0.44\] | yes |
| 5 | Internet | Comment dumb-word rate vs Dumb | +0.25 \[0.08, 0.39\] | yes |

AC's Cuteness and Dumb ratings are nearly independent (rho 0.06). The three-source measures (SigLIP, language model, comments) are held out of the visualization for now; AC has a separate plan for presenting them. Upvote ratio (ceiling) and reasoning length (didn't replicate) are dropped.

## Visualization prototype

The prototype is `viz/oobc_cat_viz.html`: one row of typical cats for the chosen category, where clicking a cat or its tail zooms to the tail alone. It is vanilla JS and SVG, built from a template by a Python script; no D3 yet.

**What it does now:**

- Header: the dataset name, and the category name as a switcher (hand codes, or "Tails of" any tail variable).
- Row: one typical cat per group value, all at one scale, rotated 5° to stand straighter. A settings panel behind a sliders icon picks tail items.
- Zoom: the body fades, the frame fits the tail, and segments are labelled with values. Clicking a segment shows a dot strip of all posts (group highlighted, outer 10% shaded), the post list and **Chase this tail**, which regroups into left tail (\<p10), body and right tail (>p90).
- Bristle on hover/select grows outward from the band.

**Design decisions (AC):**

- The body carries only the main category's look; all cross-category and post data lives on the tail.
- Typical cat: amount of white from the group's median % white; extra white zones where a marking is ≥1.3× as common as overall and on ≥30% of the group; body type only at ≥1.5× and ≥25% of the group; 3 cats minimum per trait.
- Eyes: big-shiny for the highest average Cuteness and Dumb groups in the view; every other cat gets a seeded random set.
- Tail: each item its own fixed shade, white → orange → brown, base to tip. Segment length = percentile of the group median among all posts (rank inverted), or the value's share of the group for a mix.
- Default tail: upvotes, comments and the group's mix of failure mode.
- Out of this version: the decline-over-time story and the three-source measures.

## Files

Everything is under `C:\Users\Watcher\Documents\pysandbox\Orange_Braincells` on AC's machine.

| Path | What it is |
| --- | --- |
| `Orange Braincell Data - InProgress.csv` | Local copy of the codes, synced to Sheet5 (182 rows) |
| `oobc_heyday_2022-04_08_top40.csv` / `_cats.csv` | Heyday posts and per-cat model traits |
| `oobc_archive/final_codes/` | Final codes, stage 2 test script and results |
| `oobc_archive/viz/build_viz_data.py` → `oobc_viz_data.json` | Builds the viz data file (posts, groupings, tail vars, distributions) |
| `viz/viz_template.html` | Prototype page template (current); `viz_template_v1.html` = earlier card layout |
| `viz/cat_tail_viz_template.js` | Tail module (weighted segments, own fills, outward bristle) |
| `viz/build_viz.py` → `viz/oobc_cat_viz.html` | Assembles the single-file prototype |
| `SVG/cat_kit.svg` | The cat kit: 4 bodies, 10 white zones, 7 eye sets, CSS switches |
| `SVG/white_stages.json` | Cumulative % white after each zone, per body |
| `SVG/tails/tail_geometry.json` | Tail stroke and stations for the long and short tails |
| `oobc_archive/backups/` | Every pre-change copy of the coding sheet |

Rebuild the prototype: `python oobc_archive/viz/build_viz_data.py` then `python viz/build_viz.py`.

## Open items

- [ ] Rebuild the viz as a native HTML/JS page on D3 (see the D3 rebuild handoff)
- [x] Pounce transition from the storyboard: the cat chases its own tail on "Chase this tail" (viz_d3/js/pounce.js, Nov 2)
- [ ] Mix segments always sum to 100%, so a mix adds the same length to every tail; consider a fixed-width band at the tip
- [ ] AC's plan for presenting the three rating sources (computer, internet, AC)
- [ ] Blind re-code of 40 posts for kappa, a week or more after coding
- [ ] Expression field in the trait prompt, if eyes should ever follow the data
- [ ] Google Drive connector still needs reconnecting (Sheets works)

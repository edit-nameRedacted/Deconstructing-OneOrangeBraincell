# Stage 2 predictions: model measures vs the human hand codes

Saved 2026-10-26, before any of the posts below were hand-coded. Do not edit; add a dated addendum instead.

## Test set
Heyday posts in `Orange Braincell Data - InProgress.csv` that are hand-coded **after** 2026-10-26, i.e. every coded post
except the 35 already coded (listed at the bottom), which were used to find predictions 2 and 3.
Each post counts once. Posts whose Dumb or Cuteness rating is blank are left out of that test.

## Predictions
| # | Measure (file, column) | Hand code | Predicted direction |
|---|---|---|---|
| 1 | Funny-vs-cute share from qwen3.5:9b next-word probabilities, mean of `tp_so_funny_vs_cute` and `tp_whata_funny_vs_cute` (tokenprobs_by_post.csv) | Dumb (1-5) | positive |
| 2 | SigLIP 2 derp score, `siglip_derp` (siglip_scores.csv) | Dumb (1-5) | positive |
| 3 | Trait model reasoning length, `reasoning_chars` (reasoning_measures.csv); posts where reasoning overflowed are blank and left out | Cuteness (1-5) | negative |

## Test
Spearman rank correlation, one-sided in the predicted direction, Holm correction across the three tests at alpha = .05.
Report rho, n and a bootstrap 95% CI (2,000 resamples) for each, whether or not it passes.
A prediction is supported if it passes after correction. If it fails, the measure stays out of the visualization's claims.

## Not predicted (exploratory only)
Whether funny-vs-cute share also predicts lower Cuteness; comparisons with the braincell, failure-mode, kin and voiced codes;
SigLIP's cute, dumb, fat, blank and loaf scores; reasoning measures other than length.

## Measure files at the time of saving (SHA-256, first 16 hex)
- `oobc_archive/ai_opinion/ai_opinion.csv`: aba47ca85957ace5
- `oobc_archive/ai_opinion/siglip_scores.csv`: 3b3b2de52a794736
- `oobc_archive/ai_opinion/reasoning_measures.csv`: 0151baacec82c8cd
- `oobc_archive/ai_opinion/tokenprobs/tokenprobs_by_post.csv`: 78d9b5893ec4eeb6

## Posts already coded when these predictions were saved (excluded from the test)
u9y0e9, u196np, u4x707, u8nf6x, ub1710, ubnfe6, ufar1s, ufmnwt, uaiqan, ud4szr, uc7bo9, u4qc8d, udtuz7, ue93p5, udw7ut, u5ri53, u5uomf, uc41v7, uco2mx, udlakh, ubtzd7, uckzhb, uexnzh, u0mttp, ubl3ik, u5jk13, ue88g6, u4zodi, ubas6r, uej64j, ufct8j, u71kxc, u6oxya, u3vm8m, u9eeg3


---

## Addendum 1 (2026-10-26, same day; still before any new posts were coded)

**Memorial posts are excluded from every test**, including predictions 1-3 above. They are listed in
`oobc_archive/memorial_posts.csv` (4 definite, 1 probable: vykeyl, vf7dmz, vzbcd5, usg5zj, wsdvo1) and were removed
from the coding sheet. None had been coded.

**Two comment-based predictions** ("what the internet thinks"), tested on the same set of newly coded posts:

| # | Measure (file, column) | Hand code | Predicted direction |
|---|---|---|---|
| 4 | Comments' funny-vs-cute share, `cm_funny_vs_cute` (comment_analysis/comment_lexicon_by_post.csv) | Dumb (1-5) | positive |
| 5 | Comments' dumb-word rate per 1,000 words, `cm_dumb_per1k`, including "orange" used to mean dumb | Dumb (1-5) | positive |

Test: as above (one-sided Spearman, bootstrap CI), with Holm correction across predictions 4-5 as their own family,
so the original three-test family is unchanged.

Measure file at the time of saving:
- `oobc_archive/comment_analysis/comment_lexicon_by_post.csv`: 6b5686f531feb45b

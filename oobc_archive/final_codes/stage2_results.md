# Stage 2 results

Run once on 2026-10-27, as written in `oobc_archive/ai_opinion/stage2_predictions.md`.
Confirmatory set: 147 posts coded after the predictions were saved (the 35 earlier posts and 5 memorial posts excluded).
Codes read from the Google Sheet (Sheet5) and checked cell by cell with checksums. Measure files matched their saved hashes.

| # | Measure | Hand code | Predicted | n | Spearman rho | 95% CI | one-sided p | Holm p | Supported |
|---|---|---|---|---|---|---|---|---|---|
| 1 | qwen funny-vs-cute (mean of 2 openings) | Dumb | + | 147 | +0.29 | [+0.14, +0.43] | 0.0002 | 0.0004 | yes |
| 2 | SigLIP derp | Dumb | + | 147 | +0.42 | [+0.29, +0.54] | 0.0000 | 0.0000 | yes |
| 3 | trait-model reasoning length | Cuteness | - | 121 | -0.06 | [-0.23, +0.11] | 0.2586 | 0.2586 | no |
| 4 | comments funny-vs-cute share | Dumb | + | 147 | +0.30 | [+0.15, +0.44] | 0.0001 | 0.0002 | yes |
| 5 | comments dumb words per 1k | Dumb | + | 147 | +0.25 | [+0.08, +0.39] | 0.0011 | 0.0011 | yes |

Holm families: predictions 1-3, and predictions 4-5.

## Exploratory (not predicted; all 182 coded posts, no correction)

- qwen funny-vs-cute (mean of 2 openings) vs Dumb: rho +0.28 (n=182, two-sided p=0.000)
- qwen funny-vs-cute (mean of 2 openings) vs Cuteness: rho -0.18 (n=182, two-sided p=0.017)
- SigLIP derp vs Dumb: rho +0.42 (n=182, two-sided p=0.000)
- SigLIP derp vs Cuteness: rho -0.03 (n=182, two-sided p=0.689)
- trait-model reasoning length vs Dumb: rho -0.15 (n=150, two-sided p=0.068)
- trait-model reasoning length vs Cuteness: rho -0.14 (n=150, two-sided p=0.086)
- comments funny-vs-cute share vs Dumb: rho +0.22 (n=180, two-sided p=0.004)
- comments funny-vs-cute share vs Cuteness: rho -0.29 (n=180, two-sided p=0.000)
- comments dumb words per 1k vs Dumb: rho +0.19 (n=182, two-sided p=0.011)
- comments dumb words per 1k vs Cuteness: rho -0.16 (n=182, two-sided p=0.026)
- hand Cuteness vs Dumb: rho +0.06 (n=182, two-sided p=0.437)

Means by braincell code (all 182):

| Braincell | n | Dumb | Cuteness | qwen funny-vs-cute | SigLIP derp | comments funny-vs-cute |
|---|---|---|---|---|---|---|
| What braincell? | 101 | 3.25 | 2.81 | 0.26 | +3.32 | 0.55 |
| Seeking it | 22 | 2.73 | 2.82 | 0.26 | +2.69 | 0.55 |
| Had it | 15 | 2.07 | 2.87 | 0.14 | +2.84 | 0.45 |
| Has it | 13 | 1.46 | 3.00 | 0.22 | +2.12 | 0.48 |
| Not applicable | 31 | 1.61 | 3.10 | 0.19 | +1.68 | 0.41 |
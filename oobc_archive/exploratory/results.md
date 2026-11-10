# Exploratory structure analysis: results tables

Posts: 182. Measures in the factor analysis: 32. Spearman correlations, pairwise complete (reasoning measures missing for 32 posts where the trait model's reasoning overflowed).

KMO = 0.54 (weak but usable; the measures are mostly loosely related). Parallel analysis (300 permutations, 95th percentile) keeps up to 8 factors:

| Factor | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Observed eigenvalue | 3.51 | 2.66 | 2.57 | 2.09 | 1.93 | 1.61 | 1.54 | 1.40 | 1.32 |
| Random (95th pct) | 2.01 | 1.87 | 1.76 | 1.66 | 1.59 | 1.51 | 1.45 | 1.39 | 1.33 |

Bootstrap stability (200 resamples): median Tucker congruence of each factor with the full-sample solution, and share of resamples ≥ .85.

- 5 factors: median 0.95, 0.91, 0.89, 0.90, 0.83; share ≥ .85: 0.92, 0.81, 0.72, 0.75, 0.43
- 6 factors: median 0.94, 0.93, 0.92, 0.91, 0.86, 0.69; share ≥ .85: 0.81, 0.90, 0.89, 0.77, 0.56, 0.11

The sixth factor does not replicate (median congruence well under .85), so the solution below keeps 5.

## Loadings (|loading| ≥ .30), 5 factors, oblimin

- **F1**: Funny words (Qwen odds) +0.76, Cute words (Qwen odds) -0.75, Cute words (comments) -0.65, Love words (comments) -0.45, Cute vs ugly (SigLIP) -0.40, Funny words (comments) +0.39, Video post +0.34, Cuteness rating (human) -0.32
- **F2**: White zones (Qwen) +0.85, % white fur (Qwen) +0.84
- **F3**: Second guesses (Qwen) +0.82, Reasoning length (Qwen) +0.77, Cuteness rating (human) -0.31, Comments per 100 upvotes +0.30
- **F4**: Weight (Qwen) +0.69, Fat vs skinny (SigLIP) +0.57, Kitten (Qwen) -0.52, Calm words (Qwen odds) +0.31, Loaf vs cat (SigLIP) +0.31
- **F5**: Dumb vs smart (SigLIP) +0.80, Derpy vs dignified (SigLIP) +0.65, Dumb rating (human) +0.32

Factor correlations:

| | F1 | F2 | F3 | F4 | F5 |
|---|---|---|---|---|---|
| F1 | +1.00 | -0.07 | -0.02 | +0.14 | -0.08 |
| F2 | -0.07 | +1.00 | -0.11 | +0.05 | -0.20 |
| F3 | -0.02 | -0.11 | +1.00 | -0.01 | -0.05 |
| F4 | +0.14 | +0.05 | -0.01 | +1.00 | -0.03 |
| F5 | -0.08 | -0.20 | -0.05 | -0.03 | +1.00 |

Measures that load on no factor (all |loading| < .30): Kin (human), Voiced (human), Blank vs thinking (SigLIP), Braincell words (comments), Dumb words (comments), Kin words (comments), Body words (comments), Smart words (comments), Upvote percentile in month, Crossposts, More than one cat.

## Categorical codes: pairs that travel together

Cramér's V with permutation p (2,000) and Benjamini-Hochberg q across all 55 pairs. 'Applicable' repeats the test on the 151 posts where braincell, failure mode and status-inferred-by all apply, so associations that the coding rules force (Not applicable ⇒ NA) drop out.

| Pair | V (all 182) | q | V (applicable) | q |
|---|---|---|---|---|
| braincell × failure | 0.52 | 0.003 | 0.18 | 0.431 |
| braincell × inferred | 0.42 | 0.003 | 0.21 | 0.131 |
| braincell × dumb | 0.38 | 0.003 | 0.32 | 0.007 |
| failure × inferred | 0.50 | 0.003 | 0.36 | 0.007 |
| failure × dumb | 0.29 | 0.003 | 0.15 | 0.638 |
| inferred × media | 0.39 | 0.003 | 0.42 | 0.007 |
| inferred × dumb | 0.35 | 0.003 | 0.26 | 0.023 |
| dumb × media | 0.27 | 0.003 | 0.30 | 0.007 |
| failure × media | 0.26 | 0.012 | 0.28 | 0.016 |
| kin × media | 0.23 | 0.055 | 0.21 | 0.189 |
| braincell × white | 0.25 | 0.135 | 0.27 | 0.090 |

Cells that drive each applicable-post association (adjusted standardized residual ≥ |2.5|, count in brackets):

- **braincell × dumb**: Has it & dumb 1-2 +4.4 (12); Has it & dumb 4-5 -2.6 (0); What braincell? & dumb 1-2 -4.0 (25); What braincell? & dumb 4-5 +3.4 (42)
- **failure × inferred**: Object & Expression -3.4 (0); Self & Actions -4.9 (16); Self & Both -2.7 (4); Self & Expression +6.6 (38); Social & Expression -3.0 (0)
- **dumb × media**: dumb 1-2 & gallery +4.0 (14); dumb 1-2 & video -3.6 (5); dumb 3 & gallery -3.1 (0); dumb 4-5 & video +2.8 (20)
- **inferred × media**: Actions & gallery -3.2 (1); Actions & image -3.6 (27); Actions & video +6.3 (33); Expression & gallery +4.1 (12); Expression & video -4.0 (1); Post context & image +2.9 (26); Post context & video -2.8 (2)
- **failure × media**: Self & gallery +3.0 (15); Self & video -3.7 (10); Social & video +3.2 (12)
- **inferred × dumb**: Actions & dumb 1-2 -3.0 (13); Post context & dumb 1-2 +3.7 (20)

## MCA of the hand codes and media type

Dimension 1 explains 15.22%, dimension 2 10.54% (MCA percentages understate fit). Categories with the largest contributions:

- dim1: braincell: Not applicable (+2.01), failure: NA (+2.01), inferred: NA (+2.31), dumb: dumb 1-2 (+0.70), inferred: Actions (-0.72), braincell: What braincell? (-0.55), dumb: dumb 4-5 (-0.70), inferred: Post context (+0.63)
- dim2: inferred: Expression (+1.38), failure: Self (+0.90), media: video (-1.02), media: gallery (+1.40), inferred: Actions (-0.76), braincell: Had it (+1.03), failure: NA (-0.64), braincell: Not applicable (-0.64)

## Factor scores by hand code

Mean factor score (SD units) by group; Kruskal-Wallis ε² and p. Applicable posts only for failure mode and status inferred by.

**braincell**

| | What braincell? (n=101) | Not applicable (n=31) | Seeking it (n=22) | Had it (n=15) | Has it (n=13) | ε² | p |
|---|---|---|---|---|---|---|---|
| F1 | +0.18 | -0.43 | +0.07 | -0.20 | -0.22 | 0.034 | 0.0391 |
| F2 | +0.07 | +0.11 | -0.11 | -0.31 | -0.27 | 0.000 | 0.5443 |
| F3 | -0.11 | +0.16 | -0.11 | +0.35 | +0.25 | 0.007 | 0.2687 |
| F4 | +0.03 | +0.01 | -0.09 | +0.14 | -0.31 | 0.000 | 0.8366 |
| F5 | +0.22 | -0.44 | -0.11 | +0.09 | -0.57 | 0.059 | 0.0060 |

**inferred**

| | Actions (n=61) | Expression (n=40) | Post context (n=31) | Both (n=19) | ε² | p |
|---|---|---|---|---|---|---|
| F1 | +0.56 | -0.49 | -0.10 | +0.11 | 0.193 | 0.0000 |
| F2 | -0.36 | +0.42 | +0.12 | -0.11 | 0.087 | 0.0012 |
| F3 | -0.17 | +0.20 | +0.26 | -0.56 | 0.055 | 0.0117 |
| F4 | -0.20 | +0.06 | -0.04 | +0.58 | 0.049 | 0.0165 |
| F5 | -0.08 | +0.56 | -0.27 | +0.24 | 0.077 | 0.0025 |

**failure**

| | Self (n=76) | Physical (n=27) | Object (n=26) | Social (n=22) | ε² | p |
|---|---|---|---|---|---|---|
| F1 | -0.19 | +0.71 | +0.19 | +0.15 | 0.112 | 0.0002 |
| F2 | +0.15 | -0.12 | -0.20 | -0.29 | 0.012 | 0.1905 |
| F3 | +0.16 | -0.06 | -0.51 | -0.11 | 0.044 | 0.0244 |
| F4 | +0.03 | -0.04 | -0.02 | -0.06 | 0.000 | 0.8976 |
| F5 | +0.36 | -0.24 | -0.04 | -0.28 | 0.056 | 0.0102 |

**media**

| | image (n=115) | video (n=46) | gallery (n=21) | ε² | p |
|---|---|---|---|---|---|
| F1 | -0.22 | +0.63 | -0.17 | 0.138 | 0.0000 |
| F2 | +0.03 | -0.34 | +0.56 | 0.051 | 0.0037 |
| F3 | +0.09 | -0.36 | +0.27 | 0.040 | 0.0106 |
| F4 | +0.14 | -0.45 | +0.22 | 0.059 | 0.0019 |
| F5 | +0.04 | -0.19 | +0.18 | 0.004 | 0.2501 |

**kin**

| | kin (n=116) | no kin (n=66) | ε² | p |
|---|---|---|---|---|
| F1 | -0.03 | +0.05 | 0.000 | 0.5159 |
| F2 | +0.19 | -0.33 | 0.050 | 0.0016 |
| F3 | +0.10 | -0.18 | 0.013 | 0.0678 |
| F4 | +0.16 | -0.27 | 0.035 | 0.0066 |
| F5 | +0.12 | -0.21 | 0.021 | 0.0301 |

**voiced**

| | not voiced (n=166) | voiced (n=16) | ε² | p |
|---|---|---|---|---|
| F1 | -0.03 | +0.35 | 0.005 | 0.1734 |
| F2 | -0.02 | +0.22 | 0.000 | 0.3685 |
| F3 | +0.04 | -0.36 | 0.004 | 0.1814 |
| F4 | -0.07 | +0.67 | 0.043 | 0.0032 |
| F5 | +0.03 | -0.31 | 0.003 | 0.2105 |

## Multilevel check: does anything vary by month?

Random-intercept model per measure (posts in 5 months). ICC = share of variance between months. Trend = Spearman ρ with month order (Apr = 0 … Aug = 4).

| Measure | ICC (month) | Trend ρ | p |
|---|---|---|---|
| Dumb rating (human) | 0.033 | +0.11 | 0.158 |
| Cuteness rating (human) | 0.005 | +0.03 | 0.662 |
| What braincell? (human) | 0.000 | +0.08 | 0.300 |
| Kin (human) | 0.000 | +0.02 | 0.818 |
| Qwen funny-vs-cute | 0.000 | -0.01 | 0.904 |
| SigLIP derp | 0.000 | -0.08 | 0.276 |
| Comments funny-vs-cute | 0.000 | -0.02 | 0.815 |
| Braincell words (comments) | 0.024 | -0.10 | 0.200 |
| F1 | 0.003 | +0.01 | 0.875 |
| F2 | 0.000 | -0.03 | 0.728 |
| F3 | 0.000 | -0.01 | 0.900 |
| F4 | 0.003 | -0.09 | 0.220 |
| F5 | 0.014 | -0.06 | 0.418 |

Human Dumb rating on the three outside sources together (standardized predictors, random intercept for month, n = 180):

| Predictor | b | 95% CI | p |
|---|---|---|---|
| Qwen funny-vs-cute | +0.10 | [-0.07, +0.28] | 0.2323 |
| SigLIP derp | +0.43 | [+0.27, +0.59] | 0.0000 |
| Comments funny-vs-cute | +0.19 | [+0.03, +0.35] | 0.0210 |

Month variance 0.039 vs residual 1.092.

Repeat posters: 5 authors posted more than once (12 posts), too few to model authors as a level.

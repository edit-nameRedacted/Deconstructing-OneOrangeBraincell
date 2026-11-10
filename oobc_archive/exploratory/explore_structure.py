"""Exploratory structure analysis: which codes, traits and measures travel together?

Usage (from the Orange_Braincells folder):
    python oobc_archive/exploratory/explore_structure.py

Needs: numpy, pandas, scipy, matplotlib, statsmodels, factor_analyzer, prince
    pip install statsmodels factor_analyzer prince

Reads the per-post table built by build_table.py (posts.csv, next to this script; rebuilt if missing)
and writes, next to this script:
    results.md               every table the write-up (README.md) draws on
    loadings.csv             factor loadings (5 factors, oblimin)
    factor_scores.csv        each post's score on each factor
    cramers_v.csv            every pair of categorical codes, all posts and applicable posts only
    fig_loadings.png         which measures load on which factor
    fig_mca.png              map of the categorical codes (multiple correspondence analysis)
    fig_factors_by_code.png  factor scores by braincell code and by how dumbness is shown

Three parts:
  1. Exploratory factor analysis of the numeric and binary measures (Spearman correlations, parallel
     analysis for the number of factors, minres + oblimin, bootstrap stability).
  2. Categorical codes: Cramér's V for every pair with permutation p-values and Benjamini-Hochberg q,
     repeated on the applicable posts only (dropping the NA-by-rule cells); MCA map.
  3. Multilevel check: posts are nested in months, so the month-level share of variance (ICC) of each
     measure, and a random-intercept model of the human Dumb rating on the three outside sources.
Everything here is exploratory: nothing was predicted in advance, so treat it as hypotheses.
"""
import itertools, os, subprocess, sys, warnings
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import linear_sum_assignment
from scipy.stats import kruskal, spearmanr
warnings.filterwarnings("ignore")

import factor_analyzer.factor_analyzer as _fa_mod
from sklearn.utils import check_array as _check_array
# factor_analyzer 0.5 still passes sklearn's old argument name; translate it for sklearn >= 1.6
_fa_mod.check_array = lambda X, force_all_finite=None, **k: _check_array(X, ensure_all_finite=force_all_finite, **k)
from factor_analyzer import FactorAnalyzer
import prince
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = lambda name: os.path.join(HERE, name)
rng = np.random.default_rng(1)
md = []  # lines of results.md
say = lambda s="": md.append(s)

table_path = OUT("posts.csv")
if not os.path.exists(table_path):
    subprocess.run([sys.executable, OUT("build_table.py"), ROOT, table_path], check=True)
d = pd.read_csv(table_path, index_col=0)
d["kitten"] = (d.age_class == "kitten").astype(float)
d["video"] = (d.media_kind == "video").astype(float)
d["multi_cat"] = (d.cat_count > 1).astype(float)
d["qwen_fvc"] = d.qwen_funny / (d.qwen_funny + d.qwen_cute)
d["cm_fvc"] = d.cm_funny / (d.cm_funny + d.cm_cute)

# Readable names and the source of each measure
LABEL = {
    "dumb": "Dumb rating (human)", "cute": "Cuteness rating (human)", "kin": "Kin (human)", "voiced": "Voiced (human)",
    "pct_white": "% white fur (Qwen)", "n_white_zones": "White zones (Qwen)", "kg": "Weight (Qwen)", "kitten": "Kitten (Qwen)",
    "qwen_cute": "Cute words (Qwen odds)", "qwen_funny": "Funny words (Qwen odds)", "qwen_calm": "Calm words (Qwen odds)",
    "reasoning_chars": "Reasoning length (Qwen)", "second_guesses": "Second guesses (Qwen)",
    "siglip_dumb": "Dumb vs smart (SigLIP)", "siglip_cute": "Cute vs ugly (SigLIP)", "siglip_fat": "Fat vs skinny (SigLIP)",
    "siglip_derp": "Derpy vs dignified (SigLIP)", "siglip_blank": "Blank vs thinking (SigLIP)", "siglip_loaf": "Loaf vs cat (SigLIP)",
    "cm_cute": "Cute words (comments)", "cm_funny": "Funny words (comments)", "cm_braincell": "Braincell words (comments)",
    "cm_dumb": "Dumb words (comments)", "cm_love": "Love words (comments)", "cm_kin": "Kin words (comments)",
    "cm_body": "Body words (comments)", "cm_smart": "Smart words (comments)",
    "score_pct_in_month": "Upvote percentile in month", "comments_per_100_upvotes": "Comments per 100 upvotes",
    "crossposts": "Crossposts", "video": "Video post", "multi_cat": "More than one cat",
}
V = list(LABEL)
X = d[V]

# ============================================================== 1. factor analysis
R = X.corr(method="spearman", min_periods=100)
ev = np.sort(np.linalg.eigvalsh(R.values))[::-1]
inv = np.linalg.inv(R.values); Dg = np.diag(1 / np.sqrt(np.diag(inv))); Pc = -Dg @ inv @ Dg
np.fill_diagonal(Pc, 0); r0 = R.values.copy(); np.fill_diagonal(r0, 0)
kmo = (r0 ** 2).sum() / ((r0 ** 2).sum() + (Pc ** 2).sum())

def spearman_eigs(frame):
    return np.sort(np.linalg.eigvalsh(frame.corr(method="spearman", min_periods=100).values))[::-1]
sims = np.array([spearman_eigs(X.apply(lambda c: pd.Series(rng.permutation(c.values), index=c.index))) for _ in range(300)])
pa95 = np.percentile(sims, 95, axis=0)
n_pa = int(np.argmax(ev <= pa95))

def fit(Rm, k):
    fa = FactorAnalyzer(n_factors=k, rotation="oblimin", method="minres", is_corr_matrix=True)
    fa.fit(Rm.values if hasattr(Rm, "values") else Rm)
    return fa

def stability(k, B=200):
    L0 = fit(R, k).loadings_; out = []
    for _ in range(B):
        idx = rng.integers(0, len(X), len(X))
        try: Lb = fit(X.iloc[idx].corr(method="spearman", min_periods=80), k).loadings_
        except Exception: continue
        C = (L0.T @ Lb) / np.sqrt(np.outer((L0 ** 2).sum(0), (Lb ** 2).sum(0)))
        r, c = linear_sum_assignment(-np.abs(C)); out.append(np.abs(C[r, c]))
    return np.array(out)

say("# Exploratory structure analysis: results tables\n")
say(f"Posts: {len(d)}. Measures in the factor analysis: {len(V)}. Spearman correlations, pairwise complete (reasoning measures missing for {d.reasoning_chars.isna().sum()} posts where the trait model's reasoning overflowed).\n")
say(f"KMO = {kmo:.2f} (weak but usable; the measures are mostly loosely related). Parallel analysis (300 permutations, 95th percentile) keeps up to {n_pa} factors:\n")
say("| Factor | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |"); say("|---|" + "---|" * 9)
say("| Observed eigenvalue | " + " | ".join(f"{v:.2f}" for v in ev[:9]) + " |")
say("| Random (95th pct) | " + " | ".join(f"{v:.2f}" for v in pa95[:9]) + " |\n")

stab = {k: stability(k) for k in (5, 6)}
say("Bootstrap stability (200 resamples): median Tucker congruence of each factor with the full-sample solution, and share of resamples ≥ .85.\n")
for k, s in stab.items():
    say(f"- {k} factors: median " + ", ".join(f"{v:.2f}" for v in np.median(s, 0)) + "; share ≥ .85: " + ", ".join(f"{v:.2f}" for v in (s >= .85).mean(0)))
say("\nThe sixth factor does not replicate (median congruence well under .85), so the solution below keeps 5.\n")

K = 5
fa = fit(R, K)
L = pd.DataFrame(fa.loadings_, index=V, columns=[f"F{j+1}" for j in range(K)])
# order factors by variance and flip signs so each factor's biggest loading is positive
order = np.argsort(-(L ** 2).sum().values); L = L.iloc[:, order]
phi = fa.phi_[np.ix_(order, order)]
for j, c in enumerate(L.columns):
    s = np.sign(L[c].iloc[L[c].abs().argmax()]); L[c] *= s; phi[j, :] *= s; phi[:, j] *= s
L.columns = [f"F{j+1}" for j in range(K)]
NAMES = {}
h2 = (L ** 2).sum(1)
L.assign(communality=h2).round(3).to_csv(OUT("loadings.csv"))
say("## Loadings (|loading| ≥ .30), 5 factors, oblimin\n")
for c in L.columns:
    s = L[c][L[c].abs() >= .30].sort_values(key=abs, ascending=False)
    say(f"- **{c}**: " + ", ".join(f"{LABEL[i]} {v:+.2f}" for i, v in s.items()))
say("\nFactor correlations:\n")
say("| | " + " | ".join(L.columns) + " |"); say("|---|" + "---|" * K)
for j, c in enumerate(L.columns): say(f"| {c} | " + " | ".join(f"{v:+.2f}" for v in phi[j]) + " |")
loners = [LABEL[v] for v in V if L.loc[v].abs().max() < .30]
say("\nMeasures that load on no factor (all |loading| < .30): " + ", ".join(loners) + ".\n")

# factor scores (regression method on rank-normalised data; missing values set to the median)
Z = X.rank(pct=True).apply(lambda c: c.fillna(c.median()))
Z = (Z - Z.mean()) / Z.std()
W = np.linalg.solve(R.values, L.values)
S = pd.DataFrame(Z.values @ W, index=X.index, columns=L.columns)
S = (S - S.mean()) / S.std()
S.round(3).to_csv(OUT("factor_scores.csv"))

# ============================================================== 2. categorical codes
C = pd.DataFrame(index=d.index)
C["braincell"] = d.braincell
C["failure"] = d.failure.fillna("NA")
C["inferred"] = d.inferred.fillna("NA")
C["kin"] = d.kin.map({1: "kin", 0: "no kin"})
C["voiced"] = d.voiced.map({1: "voiced", 0: "not voiced"})
C["dumb"] = pd.cut(d.dumb, [0, 2, 3, 5], labels=["dumb 1-2", "dumb 3", "dumb 4-5"]).astype(str)
C["cute"] = pd.cut(d.cute, [0, 2, 3, 5], labels=["cute 1-2", "cute 3", "cute 4-5"]).astype(str)
C["media"] = d.media_kind.replace({"link": "image"})
C["white"] = np.where(d.pct_white >= 20, "white 20%+", "white <20%")
C["age"] = np.where(d.age_class == "kitten", "kitten", "adult/youth")
C["month"] = d.month

def table(a, b):
    ai, bi = pd.factorize(a)[0], pd.factorize(b)[0]
    t = np.zeros((ai.max() + 1, bi.max() + 1)); np.add.at(t, (ai, bi), 1); return t
def chi2(t):
    e = np.outer(t.sum(1), t.sum(0)) / t.sum(); return ((t - e) ** 2 / e).sum()
def cramers(a, b, B=2000):
    t = table(a, b); x = chi2(t); v = np.sqrt(x / (t.sum() * (min(t.shape) - 1)))
    p = (1 + sum(chi2(table(a, rng.permutation(b))) >= x for _ in range(B))) / (B + 1)
    return v, p
def bh(p):
    p = np.asarray(p); o = np.argsort(p); q = p[o] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]; out = np.empty_like(q); out[o] = np.minimum(q, 1); return out
def adj_resid(a, b):
    t = pd.crosstab(a, b); n = t.values.sum(); e = np.outer(t.sum(1), t.sum(0)) / n
    r = (t.values - e) / np.sqrt(e * np.outer(1 - t.sum(1) / n, 1 - t.sum(0) / n))
    return pd.DataFrame(r, index=t.index, columns=t.columns), t

app = C[(C.braincell != "Not applicable") & (C.failure != "NA") & (C.inferred != "NA")]
rows = []
for a, b in itertools.combinations(C.columns, 2):
    v, p = cramers(C[a].values, C[b].values)
    va, pa_ = cramers(app[a].values, app[b].values) if app[a].nunique() > 1 and app[b].nunique() > 1 else (np.nan, np.nan)
    rows.append(dict(a=a, b=b, V_all=v, p_all=p, V_applicable=va, p_applicable=pa_))
CV = pd.DataFrame(rows)
CV["q_all"] = bh(CV.p_all)
m = CV.p_applicable.notna(); CV.loc[m, "q_applicable"] = bh(CV.loc[m, "p_applicable"])
CV.sort_values("p_all").round(4).to_csv(OUT("cramers_v.csv"), index=False)

say("## Categorical codes: pairs that travel together\n")
say(f"Cramér's V with permutation p (2,000) and Benjamini-Hochberg q across all {len(CV)} pairs. 'Applicable' repeats the test on the {len(app)} posts where braincell, failure mode and status-inferred-by all apply, so associations that the coding rules force (Not applicable ⇒ NA) drop out.\n")
say("| Pair | V (all 182) | q | V (applicable) | q |"); say("|---|---|---|---|---|")
for _, r in CV.sort_values("p_all").iterrows():
    if r.q_all < .10 or (r.q_applicable < .10 if pd.notna(r.q_applicable) else False):
        say(f"| {r.a} × {r.b} | {r.V_all:.2f} | {r.q_all:.3f} | {r.V_applicable:.2f} | {r.q_applicable:.3f} |")
say("\nCells that drive each applicable-post association (adjusted standardized residual ≥ |2.5|, count in brackets):\n")
for _, r in CV[CV.q_applicable < .05].sort_values("p_applicable").iterrows():
    A, t = adj_resid(app[r.a], app[r.b])
    cells = [f"{i} & {j} {A.loc[i, j]:+.1f} ({int(t.loc[i, j])})" for i in A.index for j in A.columns if abs(A.loc[i, j]) >= 2.5]
    say(f"- **{r.a} × {r.b}**: " + ("; ".join(cells) if cells else "no single cell over 2.5"))

M = C[["braincell", "failure", "inferred", "dumb", "cute", "media", "kin", "voiced"]]
mca = prince.MCA(n_components=2, random_state=1).fit(M)
cc = mca.column_coordinates(M).iloc[:, :2]; cc.columns = ["dim1", "dim2"]
ctr = mca.column_contributions_.iloc[:, :2]; ctr.columns = ["ctr1", "ctr2"]
pct = mca.eigenvalues_summary["% of variance"].tolist()
say(f"\n## MCA of the hand codes and media type\n\nDimension 1 explains {pct[0]}, dimension 2 {pct[1]} (MCA percentages understate fit). Categories with the largest contributions:\n")
for dim, cn in [("dim1", "ctr1"), ("dim2", "ctr2")]:
    top = ctr[cn].sort_values(ascending=False).head(8).index
    say(f"- {dim}: " + ", ".join(f"{i.replace('__', ': ')} ({cc.loc[i, dim]:+.2f})" for i in top))

# factor scores by category
say("\n## Factor scores by hand code\n\nMean factor score (SD units) by group; Kruskal-Wallis ε² and p. Applicable posts only for failure mode and status inferred by.\n")
def by(code, frame_idx):
    g = C.loc[frame_idx, code]; out = []
    for f in S.columns:
        groups = [S.loc[g[g == lv].index, f] for lv in g.unique()]
        H, p = kruskal(*groups); eps = (H - len(groups) + 1) / (len(g) - len(groups))
        out.append((f, max(eps, 0), p))
    return g, out
for code, idx in [("braincell", C.index), ("inferred", app.index), ("failure", app.index), ("media", C.index), ("kin", C.index), ("voiced", C.index)]:
    g, stats = by(code, idx)
    lv = g.value_counts().index
    say(f"**{code}**\n"); say("| | " + " | ".join(f"{l} (n={int((g == l).sum())})" for l in lv) + " | ε² | p |"); say("|---|" + "---|" * (len(lv) + 2))
    for f, eps, p in stats:
        say(f"| {f} | " + " | ".join(f"{S.loc[g[g == l].index, f].mean():+.2f}" for l in lv) + f" | {eps:.3f} | {p:.4f} |")
    say()

# ============================================================== 3. multilevel check
d["what_bc"] = (d.braincell == "What braincell?").astype(float)
def icc(v, frame=d):
    x = frame[[v, "month"]].dropna().copy(); x["z"] = (x[v] - x[v].mean()) / x[v].std()
    res = smf.mixedlm("z ~ 1", x, groups=x.month).fit(reml=True)
    tau = float(res.cov_re.iloc[0, 0]); return tau / (tau + res.scale)
say("## Multilevel check: does anything vary by month?\n")
say("Random-intercept model per measure (posts in 5 months). ICC = share of variance between months. Trend = Spearman ρ with month order (Apr = 0 … Aug = 4).\n")
say("| Measure | ICC (month) | Trend ρ | p |"); say("|---|---|---|---|")
dm = d.month.str[-2:].astype(int) - 4
for v, lab in [("dumb", "Dumb rating (human)"), ("cute", "Cuteness rating (human)"), ("what_bc", "What braincell? (human)"),
               ("kin", "Kin (human)"), ("qwen_fvc", "Qwen funny-vs-cute"), ("siglip_derp", "SigLIP derp"),
               ("cm_fvc", "Comments funny-vs-cute"), ("cm_braincell", "Braincell words (comments)")] + [(f, f) for f in S.columns]:
    frame = d.join(S) if v in S.columns else d
    r, p = spearmanr(dm, frame[v], nan_policy="omit")
    say(f"| {lab} | {icc(v, frame):.3f} | {r:+.2f} | {p:.3f} |")
x = d[["dumb", "qwen_fvc", "siglip_derp", "cm_fvc", "month"]].dropna().copy()
for c in ["qwen_fvc", "siglip_derp", "cm_fvc"]: x[c] = (x[c] - x[c].mean()) / x[c].std()
mm = smf.mixedlm("dumb ~ qwen_fvc + siglip_derp + cm_fvc", x, groups=x.month).fit(reml=True)
say(f"\nHuman Dumb rating on the three outside sources together (standardized predictors, random intercept for month, n = {len(x)}):\n")
say("| Predictor | b | 95% CI | p |"); say("|---|---|---|---|")
ci = mm.conf_int()
for c, lab in [("qwen_fvc", "Qwen funny-vs-cute"), ("siglip_derp", "SigLIP derp"), ("cm_fvc", "Comments funny-vs-cute")]:
    say(f"| {lab} | {mm.params[c]:+.2f} | [{ci.loc[c, 0]:+.2f}, {ci.loc[c, 1]:+.2f}] | {mm.pvalues[c]:.4f} |")
say(f"\nMonth variance {float(mm.cov_re.iloc[0, 0]):.3f} vs residual {mm.scale:.3f}.")
say(f"\nRepeat posters: {(d.author.value_counts() > 1).sum()} authors posted more than once ({int(d.author.value_counts()[d.author.value_counts() > 1].sum())} posts), too few to model authors as a level.")

open(OUT("results.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")

# ============================================================== figures
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "axes.edgecolor": GRID})
FNAME = {"F1": "F1 Funny, not cute", "F2": "F2 White fur", "F3": "F3 Qwen effort", "F4": "F4 Big cat", "F5": "F5 Derpy look"}

# loadings heatmap: measures that load somewhere, grouped by their main factor
keep = [v for v in V if L.loc[v].abs().max() >= .30]
keep.sort(key=lambda v: (L.loc[v].abs().values.argmax(), -L.loc[v].abs().max()))
Lk = L.loc[keep]
fig, ax = plt.subplots(figsize=(8.4, 0.34 * len(keep) + 1.9))
fig.subplots_adjust(left=0.36, right=0.97, top=1 - 1.15 / (0.34 * len(keep) + 1.9), bottom=0.03)
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("div", [BLUE, "#f3f2ee", ORANGE])
ax.imshow(Lk.values, cmap=cmap, vmin=-.9, vmax=.9, aspect="auto")
for i in range(len(keep)):
    for j in range(K):
        v = Lk.values[i, j]
        if abs(v) >= .30: ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=8.5, color=INK, fontweight="semibold")
ax.set_xticks(range(K), [FNAME[c].replace(" ", "\n", 1) for c in L.columns], fontsize=9)
ax.xaxis.tick_top(); ax.set_yticks(range(len(keep)), [LABEL[v] for v in keep], fontsize=9)
ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
ax.set_xticks(np.arange(-.5, K), minor=True); ax.set_yticks(np.arange(-.5, len(keep)), minor=True)
ax.grid(which="minor", color=SURFACE, linewidth=2); ax.tick_params(which="minor", length=0)
fig.text(0.02, 0.995, "Which measures travel together: factor loadings", fontsize=13, fontweight="semibold", va="top")
fig.text(0.02, 0.995 - 0.3 / (0.34 * len(keep) + 1.9), "5-factor EFA, Spearman, oblimin; orange = positive, blue = negative; values shown where |loading| ≥ .30",
         fontsize=9, color=INK2, va="top")
fig.savefig(OUT("fig_loadings.png"), dpi=200); plt.close(fig)

# MCA map
VAR_COLOR = {"braincell": ORANGE, "inferred": BLUE, "failure": AQUA, "dumb": INK, "cute": MUTED, "media": "#6250d6", "kin": MUTED, "voiced": MUTED}
show = ctr.index[(ctr.ctr1 + ctr.ctr2) >= 0.01]
fig, ax = plt.subplots(figsize=(9, 6.6))
fig.subplots_adjust(left=0.08, right=0.97, top=0.86, bottom=0.09)
ax.axhline(0, color=GRID, lw=1); ax.axvline(0, color=GRID, lw=1)
# label offsets (points) for categories that would otherwise collide
NUDGE = {"failure__Object": (6, 8), "failure__Physical": (-52, 6), "inferred__Both": (6, 6), "dumb__dumb 4-5": (-12, -14),
         "failure__Social": (6, -12), "braincell__Not applicable": (-150, 8), "inferred__NA": (-30, -16)}
for name in show:
    var, lev = name.split("__", 1)
    if name == "failure__NA": continue  # sits exactly on braincell: Not applicable (NA by rule)
    x_, y_ = cc.loc[name, "dim1"], cc.loc[name, "dim2"]
    ax.scatter(x_, y_, s=40, color=VAR_COLOR[var], edgecolor=SURFACE, linewidth=1.2, zorder=3)
    lab = {"braincell__Not applicable": "Not applicable (failure: NA)", "inferred__NA": "inferred: NA"}.get(name, lev)
    ax.annotate(lab, (x_, y_), xytext=NUDGE.get(name, (5, 4)), textcoords="offset points", fontsize=8.6, color=INK)
ax.set_xlim(None, 2.6)
handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=k) for k, c in VAR_COLOR.items() if any(s.startswith(k + "__") for s in show)]
ax.legend(handles=handles, frameon=False, fontsize=8.6, loc="upper right", ncol=2)
ax.set_xlabel(f"Dimension 1 ({pct[0]}): dumb cat in action  ←→  plain cute-cat post", fontsize=9)
ax.set_ylabel(f"Dimension 2 ({pct[1]}): shown in motion  ←→  shown in a face", fontsize=9)
for s in ["top", "right"]: ax.spines[s].set_visible(False)
fig.text(0.02, 0.97, "How the hand-code categories cluster", fontsize=13, fontweight="semibold", va="top")
fig.text(0.02, 0.925, "Multiple correspondence analysis of braincell, failure mode, status inferred by, Dumb and Cuteness bands, media type, kin, voiced (182 posts)",
         fontsize=9, color=INK2, va="top")
fig.savefig(OUT("fig_mca.png"), dpi=200); plt.close(fig)

# factor scores by braincell and by inferred
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True)
fig.subplots_adjust(left=0.16, right=0.98, top=0.78, bottom=0.2, wspace=0.6)
FCOL = {"F1": ORANGE, "F5": BLUE}
FMK = {"F1": "o", "F5": "s"}
for ax, (code, idx, order_) in zip(axes, [("braincell", C.index, ["What braincell?", "Seeking it", "Had it", "Has it", "Not applicable"]),
                                         ("inferred", app.index, ["Actions", "Both", "Expression", "Post context"])]):
    g = C.loc[idx, code]
    ax.axvline(0, color=MUTED, lw=0.9, ls=(0, (3, 3)))
    for k_, f in enumerate(["F1", "F5"]):
        means = [S.loc[g[g == l].index, f].mean() for l in order_]
        ax.scatter(means, np.arange(len(order_)) + (k_ - 0.5) * 0.2, color=FCOL[f], marker=FMK[f], s=46, edgecolor=SURFACE, linewidth=1.2, zorder=3, label=FNAME[f])
    ax.set_yticks(range(len(order_)), [f"{l} (n={int((g == l).sum())})" for l in order_]); ax.invert_yaxis()
    ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
    for s in ["top", "right", "left"]: ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_title({"braincell": "By braincell code", "inferred": "By how dumbness is shown (applicable posts)"}[code], fontsize=10, loc="left", color=INK)
    ax.set_xlabel("Mean factor score (SD units)", fontsize=9)
axes[0].legend(loc="upper center", bbox_to_anchor=(1.05, -0.17), ncol=2, frameon=False, fontsize=9)
fig.text(0.02, 0.97, "Where the hand codes sit on the factors", fontsize=13, fontweight="semibold", va="top")
fig.text(0.02, 0.905, "F1 high = read as funny rather than cute by Qwen and the comments; F5 high = SigLIP sees a dumb, derpy-looking cat", fontsize=9, color=INK2, va="top")
fig.savefig(OUT("fig_factors_by_code.png"), dpi=200); plt.close(fig)
print("wrote results.md, loadings.csv, factor_scores.csv, cramers_v.csv and 3 figures to", HERE)

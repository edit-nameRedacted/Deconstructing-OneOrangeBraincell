"""Charts for the r/OneOrangeBraincell README.

Usage: python make_readme_charts.py <monthly.csv> <archive_dir> <out_dir>

  monthly.csv  one row per month, Feb 2022-Oct 2026 (oobc_monthly.csv from oobc_ecology.py)
  archive_dir  the oobc_archive folder (final codes, SigLIP scores, Qwen token probabilities)
  out_dir      where the PNGs go

Writes:
  posts_per_month.png        how many posts the subreddit got each month, heyday window shaded
  posts_per_year.png         the same, totalled by year
  braincell_framing.png      share of titles framing the cat as dumb or smart, all posts and top 100
  sources_by_braincell.png   Human vs Qwen vs SigLIP, by braincell group, on one percentile scale
  sources_agreement.png      how closely each computer/internet measure tracks the human Dumb rating
"""
import csv, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.stats import rankdata, spearmanr

monthly_path, archive, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)

# --- Look: validated default palette (blue, orange, aqua pass all-pairs CVD checks) ---
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE, BAND = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb", "#f1eee7"
plt.rcParams.update({
    "font.family": "Inter", "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": GRID, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "xtick.major.size": 0,
    "ytick.major.size": 0,
})

def title(fig, main, sub):
    fig.text(0.02, 0.965, main, fontsize=14, fontweight="semibold", va="top")
    fig.text(0.02, 0.905, sub, fontsize=10, color=INK2, va="top")

def save(fig, name):
    fig.savefig(os.path.join(out, name), dpi=200)
    plt.close(fig)
    print("wrote", name)

# =============================================================== the whole history, by month
rows = list(csv.DictReader(open(monthly_path, encoding="utf-8")))
months = [r["month"] for r in rows]
posts = np.array([int(r["posts"]) for r in rows])
wits_all = np.array([float(r["title_wits_all"]) for r in rows])
wits_top = np.array([float(r["title_wits_top100"]) for r in rows])
x = np.arange(len(months))
heyday = [i for i, m in enumerate(months) if "2022-04" <= m <= "2022-08"]
h0, h1 = heyday[0] - 0.5, heyday[-1] + 0.5
year_ticks = [0] + [i for i, m in enumerate(months) if m.endswith("-01")]

def month_axis(ax):
    ax.set_xticks(year_ticks, ["Feb 2022"] + [months[i][:4] for i in year_ticks[1:]])
    ax.set_xlim(-0.8, len(months) - 0.2)
    ax.axvspan(h0, h1, color=BAND, zorder=0)

# --- posts per month ---
fig, ax = plt.subplots(figsize=(10, 4.6))
fig.subplots_adjust(top=0.78, bottom=0.11, left=0.07, right=0.98)
title(fig, "Posts per month, r/OneOrangeBraincell",
      "All 192,113 posts in the Arctic Shift archive, Feb 2022 – Oct 2026 (October 2026 is a partial month)")
month_axis(ax)
ax.bar(x, posts, width=0.78, color=ORANGE, zorder=2)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
peak = int(np.argmax(posts))
ax.annotate(f"Peak: {posts[peak]:,} posts\n({months[peak]})", (peak, posts[peak]), xytext=(peak + 4, posts[peak] + 250),
            fontsize=9.5, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax.text((h0 + h1) / 2, posts.max() * 1.08, "Heyday sample\nApr–Aug 2022", ha="center", va="top", fontsize=9.5, color=INK2)
ax.set_ylim(0, posts.max() * 1.12)
save(fig, "posts_per_month.png")

# --- posts per year ---
years = sorted({m[:4] for m in months})
per_year = [posts[[i for i, m in enumerate(months) if m.startswith(y)]].sum() for y in years]
fig, ax = plt.subplots(figsize=(7, 4.2))
fig.subplots_adjust(top=0.76, bottom=0.1, left=0.11, right=0.97)
title(fig, "Posts per year", "2022 starts in February; 2026 runs to late October")
ax.bar(years, per_year, width=0.6, color=ORANGE, zorder=2)
for yv, n in zip(years, per_year):
    ax.text(yv, n + 600, f"{n:,}", ha="center", fontsize=9.5, color=INK)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.set_ylim(0, max(per_year) * 1.12)
save(fig, "posts_per_year.png")

# --- braincell framing over time ---
fig, ax = plt.subplots(figsize=(10, 4.6))
fig.subplots_adjust(top=0.78, bottom=0.11, left=0.07, right=0.9)
title(fig, "Share of post titles that frame the cat as dumb or smart",
      "Word-list measure, by month. A blind hand-coder found the true level is higher, and confirmed the drop.")
month_axis(ax)
start = 2  # Feb and Mar 2022 have 15 and 101 posts; too few to read as a share
ax.plot(x[start:], wits_top[start:], color=BLUE, lw=1.6, marker="o", ms=3.2, zorder=3)
ax.plot(x[start:], wits_all[start:], color=ORANGE, lw=2.2, zorder=4)
ax.text(x[-1] + 0.8, wits_all[-1] + 1.5, "All posts", color=INK, fontsize=9.5, va="center")
ax.text(x[-1] + 0.8, wits_top[-1] - 2, "Top 100\nposts", color=INK, fontsize=9.5, va="center")
pk = int(np.argmax(wits_all[start:])) + start
ax.annotate(f"Peak {wits_all[pk]:.0f}% ({months[pk]})", (pk, wits_all[pk]), xytext=(pk + 6, 52),
            fontsize=9.5, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax.text((h0 + h1) / 2, 60, "Heyday", ha="center", va="top", fontsize=9.5, color=INK2)
ax.set_ylim(0, 60)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
save(fig, "braincell_framing.png")

# =============================================================== three sources vs human codes
rd = lambda p: {r["post_id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}
codes = rd(os.path.join(archive, "final_codes", "final_codes_2026-10-27.csv"))
sg = rd(os.path.join(archive, "ai_opinion", "siglip_scores.csv"))
tp = rd(os.path.join(archive, "ai_opinion", "tokenprobs", "tokenprobs_by_post.csv"))
f = lambda v: float(v) if v not in ("", None, "NA") else np.nan

ids = list(codes)
dumb = np.array([f(codes[p]["Dumb"]) for p in ids])
qwen = np.array([(f(tp[p]["tp_so_funny_vs_cute"]) + f(tp[p]["tp_whata_funny_vs_cute"])) / 2 if p in tp else np.nan for p in ids])
derp = np.array([f(sg[p]["siglip_derp"]) if p in sg else np.nan for p in ids])
group = [codes[p]["Braincell Posession"] for p in ids]

def pct_rank(v):
    """Percentile rank among the posts that have a value (ties share the average rank)."""
    outp = np.full(len(v), np.nan)
    m = ~np.isnan(v)
    outp[m] = (rankdata(v[m]) - 0.5) / m.sum() * 100
    return outp

P = {"Human (hand-coded Dumb, 1–5)": pct_rank(dumb),
     "Qwen 3.5 9B (funny-vs-cute next-word odds)": pct_rank(qwen),
     "SigLIP 2 (derpy-vs-dignified caption match)": pct_rank(derp)}
COLORS = [ORANGE, BLUE, AQUA]
MARKERS = ["o", "s", "D"]
ORDER = ["What braincell?", "Seeking it", "Had it", "Has it", "Not applicable"]
n_by = {g: sum(1 for x_ in group if x_ == g) for g in ORDER}

fig, ax = plt.subplots(figsize=(10, 4.6))
fig.subplots_adjust(top=0.8, bottom=0.17, left=0.2, right=0.97)
title(fig, "Who reads the cat as dumb? A human, a language model and an image model",
      f"Mean percentile of each source's dumbness score, by the human braincell code ({len(ids)} heyday posts). 50 = middle of the pack.")
ax.grid(axis="x"); ax.grid(axis="y", visible=False)
ax.axvline(50, color=MUTED, lw=0.9, ls=(0, (3, 3)), zorder=1)
offsets = [-0.2, 0, 0.2]
for k, ((name, v), col, mk, off) in enumerate(zip(P.items(), COLORS, MARKERS, offsets)):
    means = []
    for gi, g in enumerate(ORDER):
        sel = np.array([x_ == g for x_ in group]) & ~np.isnan(v)
        means.append(v[sel].mean())
    ys = np.arange(len(ORDER)) + off
    ax.scatter(means, ys, s=58, color=col, marker=mk, edgecolor=SURFACE, linewidth=1.6, zorder=3 + k, label=name)
# light connectors so each group's spread reads as one row
for gi, g in enumerate(ORDER):
    vals = []
    for v in P.values():
        sel = np.array([x_ == g for x_ in group]) & ~np.isnan(v)
        vals.append(v[sel].mean())
    ax.plot([min(vals), max(vals)], [gi, gi], color=GRID, lw=5, solid_capstyle="round", zorder=2)
ax.set_yticks(range(len(ORDER)), [f"{g}  (n={n_by[g]})" for g in ORDER])
ax.invert_yaxis()
ax.set_xlim(15, 75)
ax.set_xlabel("Mean percentile among all heyday posts  (← reads as less dumb · more dumb →)")
ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.16), ncol=3, frameon=False, fontsize=9, handletextpad=0.3, columnspacing=1.4)
save(fig, "sources_by_braincell.png")

# --- agreement with the human codes (stage 2 confirmatory results, from stage2_results.md) ---
res = [  # label, rho, lo, hi, colour, marker
    ("Qwen 3.5 9B\nfunny-vs-cute odds", 0.29, 0.14, 0.43, BLUE, "s"),
    ("SigLIP 2\nderp score", 0.42, 0.29, 0.54, AQUA, "D"),
    ("Reddit comments\nfunny-vs-cute words", 0.30, 0.15, 0.44, MUTED, "o"),
    ("Reddit comments\ndumb-word rate", 0.25, 0.08, 0.39, MUTED, "o"),
]
fig, ax = plt.subplots(figsize=(8.6, 4.4))
fig.subplots_adjust(top=0.76, bottom=0.14, left=0.25, right=0.95)
title(fig, "How closely each source tracks the human Dumb rating",
      "Spearman ρ with 95% bootstrap CI, 147 posts coded after the predictions were saved; all four predictions held")
ax.grid(axis="x"); ax.grid(axis="y", visible=False)
ax.axvline(0, color=INK2, lw=0.9)
for i, (lab, r, lo, hi, col, mk) in enumerate(res):
    ax.plot([lo, hi], [i, i], color=col, lw=2, solid_capstyle="round", zorder=2)
    ax.scatter([r], [i], s=64, color=col, marker=mk, edgecolor=SURFACE, linewidth=1.6, zorder=3)
    ax.text(hi + 0.015, i, f"ρ = {r:+.2f}", va="center", fontsize=9.5, color=INK)
ax.set_yticks(range(len(res)), [r[0] for r in res])
ax.invert_yaxis()
ax.set_xlim(-0.05, 0.7)
ax.set_xlabel("Rank correlation with the human Dumb rating (1–5)")
save(fig, "sources_agreement.png")

# recompute exploratory rhos (all 182) as a check against stage2_results.md
for name, v in P.items():
    m = ~np.isnan(v) & ~np.isnan(dumb)
    print(f"{name}: rho vs Dumb (all coded) = {spearmanr(v[m], dumb[m])[0]:+.2f}, n={m.sum()}")

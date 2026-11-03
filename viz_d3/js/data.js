/*
  data.js — turns the data file into what the views draw.

  Three steps, each a function here:
    1. prepareData(raw, whiteStages): index the posts and pre-sort every tail variable's values,
       so percentile ranks are quick.
    2. arrangement(data, key): split the posts into groups — by a hand code ("braincell"), or by
       where they fall on a tail variable ("tail:score" -> left tail / body / right tail).
    3. describeView(data, arrangement, state): for each group, its typical cat, its tail segments,
       its tail stripes (one per other hand code) and its eyes.

  Takes: the parsed oobc_viz_data.json and white_stages.json.
  Replaces: arrangement(), describe() and the small statistics helpers in the prototype.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { INVERT, UNIT, EYES_DUMB, EYES_CUTE, EYES_OTHER, STRIPE_COLORS, TYPICAL, labelFor, formatValue, ordinal } from "./config.js";
import { typicalCat, hasTraits } from "./typicalCat.js";
import { palette } from "./color.js";
import { DISPLAY_LABELS } from "./text.js";

// ---------------------------------------------------------------------------
// 1. Preparing the data
// ---------------------------------------------------------------------------

export function prepareData(raw, whiteStages) {
  const posts = raw.posts;

  // Swap in the page's own names for a few categories and variables (text.js).
  for (const [key, label] of Object.entries(DISPLAY_LABELS.groupings)) if (raw.groupings[key]) raw.groupings[key].label = label;
  for (const [key, label] of Object.entries(DISPLAY_LABELS.tailvars)) if (raw.tailvars[key]) raw.tailvars[key].label = label;

  // Every tail variable's values across all posts, sorted low to high (missing values dropped).
  const sortedValues = {};
  for (const key of Object.keys(raw.tailvars)) {
    const values = posts.map((p) => p.vals[key]).filter((v) => v != null);
    sortedValues[key] = values.sort(d3.ascending);
  }

  // For every hand code, each value's share of all posts: the baseline a group is compared with.
  const overallShare = {};
  for (const [code, g] of Object.entries(raw.groupings)) {
    overallShare[code] = {};
    for (const value of g.values) overallShare[code][value] = posts.filter((p) => p.groups[code] === value).length / posts.length;
  }

  return {
    meta: raw.meta,
    posts,
    overallShare,
    groupings: raw.groupings,      // hand-code categories and their values, in display order
    tailvars: raw.tailvars,        // tail variables: label, source, distribution
    precomputed: raw.groups,       // the data builder's own groups, used only by checks.js
    sortedValues,
    allTraitPosts: posts.filter(hasTraits),
    whiteStages,
  };
}

// Where a value sits among all posts, from 0 (lowest) to 1 (highest).
// Ties count half: a value equal to 10 posts' values sits in the middle of them.
// (This "midrank" matches the prototype. bisectLeft alone would count only the posts below,
// which matters here because several variables have only a handful of distinct values.)
export function percentileRank(data, varKey, value) {
  const sorted = data.sortedValues[varKey];
  const below = d3.bisectLeft(sorted, value);          // posts with a smaller value
  const belowOrEqual = d3.bisectRight(sorted, value);  // posts with a smaller or equal value
  const equal = belowOrEqual - below;
  return (below + 0.5 * equal) / sorted.length;
}

// ---------------------------------------------------------------------------
// 2. Arrangements: how the posts are split into groups (one cat per group)
// ---------------------------------------------------------------------------

export function isTailArrangement(key) {
  return key.startsWith("tail:");
}

export function arrangement(data, key) {
  // "Tails of <variable>": left tail (below the 10th percentile), body, right tail (above the 90th).
  // Which side each post falls on is precomputed in the data file (posts[].tails), so the
  // split here matches the data builder exactly.
  if (isTailArrangement(key)) {
    const varKey = key.slice("tail:".length);
    const dist = data.tailvars[varKey].dist;
    const unit = UNIT[varKey];
    const low = formatValue(varKey, dist.p10);
    const high = formatValue(varKey, dist.p90);
    const labels = {
      left: `Under ${low}${unit}`,
      body: `${low}–${high}${unit}`,
      right: `Over ${high}${unit}`,
    };
    const byTail = d3.group(data.posts, (p) => p.tails[varKey]);
    const groups = ["left", "body", "right"]
      .filter((side) => byTail.has(side))
      .map((side) => ({ value: side, label: labels[side], posts: byTail.get(side) }));
    return { key, title: `Tails of ${data.tailvars[varKey].label.toLowerCase()}`, category: null, groups };
  }

  // A hand-code category: one group per value, in the category's display order.
  const byValue = d3.group(data.posts, (p) => p.groups[key]);
  const groups = data.groupings[key].values
    .filter((value) => byValue.has(value))
    .map((value) => ({ value, label: labelFor(key, value), posts: byValue.get(value) }));
  return { key, title: data.groupings[key].label, category: key, groups };
}

// ---------------------------------------------------------------------------
// 3. Describing a view: everything needed to draw each cat
// ---------------------------------------------------------------------------

// A stable number from a string (32-bit FNV-1a hash). The same string always gives the same
// number, so a cat's "random" eyes stay the same every time the page is opened.
export function stableHash(text) {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

// One tail segment for one tail variable: its length is the percentile of the group's median
// among all posts (inverted for rank, where lower is better).
function variableSegment(data, group, varKey, fill) {
  const label = data.tailvars[varKey].label;
  const median = d3.median(group.posts, (p) => p.vals[varKey]); // d3.median skips missing values
  const pct = median == null ? 0 : percentileRank(data, varKey, median);
  const weight = INVERT[varKey] ? 1 - pct : pct;
  const valueText = `${formatValue(varKey, median)}${UNIT[varKey]}`;
  return {
    key: varKey,
    label,
    shortLabel: `${label} ${valueText}`,
    fill,
    weight,
    median,
    pct,
    aria: `${label}: group median ${valueText}, ${ordinal(Math.round(pct * 100))} percentile`,
  };
}

// One stripe for one hand code: the group's standout value for that code, drawn as thick as its
// share of the group. "Standout" uses the same idea as the coat markings: the value most
// over-represented in the group compared with all posts (its "lift"), among values held by at
// least TYPICAL.MIN_CATS posts. A group too small for that falls back to its most common value.
// The stripe also carries the full breakdown, for the details panel.
function codeStripe(data, group, code) {
  const breakdown = data.groupings[code].values.map((value) => {
    const count = group.posts.filter((p) => p.groups[code] === value).length;
    const share = count / group.posts.length;
    const overall = data.overallShare[code][value];
    return { value, label: labelFor(code, value), count, share, overall, lift: overall ? share / overall : 0 };
  });

  const eligible = breakdown.filter((b) => b.count >= TYPICAL.MIN_CATS);
  const standout = eligible.length
    ? d3.greatest(eligible, (b) => b.lift)
    : d3.greatest(breakdown, (b) => b.count);

  const codeLabel = data.groupings[code].label;
  // On the tail the code's name is already there, so a rating shows just its number ("Cuteness: 4").
  const shortValue = code === "dumb" || code === "cute" ? standout.value : standout.label;
  const percent = Math.round(standout.share * 100);
  const overallPercent = Math.round(standout.overall * 100);
  return {
    key: "code:" + code,
    code,
    codeLabel,
    color: STRIPE_COLORS[code],
    value: standout.value,
    valueLabel: standout.label,
    share: standout.share,
    overall: standout.overall,
    breakdown,
    shortLabel: `${codeLabel}: ${shortValue} · ${percent}%`,
    aria: `${codeLabel}: ${standout.label} stands out, ${percent}% of this group against ${overallPercent}% of all posts`,
  };
}

export function describeView(data, arr, state) {
  // Tail variables in the order of the data file, so the base-to-tip order never depends on
  // the order the boxes were ticked. Each gets its own fixed shade from the ramp.
  const varKeys = Object.keys(data.tailvars).filter((k) => state.vars.has(k));
  const fills = palette(varKeys.length);

  // Hand codes drawn as stripes, base to tip in the data file's order: those switched on, minus the
  // one the row is grouped by (it would be 100% on every cat).
  const stripeCodes = Object.keys(data.groupings).filter((code) => state.stripes.has(code) && code !== arr.category);

  const cats = arr.groups.map((group) => {
    const segments = varKeys.map((k, i) => variableSegment(data, group, k, fills[i]));
    const rings = stripeCodes.map((code) => codeStripe(data, group, code));
    return {
      // A key that is unique across views: "tails of upvotes / left" and "tails of comments / left"
      // must differ, or the row would reuse the old cat for the new group.
      id: arr.key + ":" + group.value,
      group,
      look: typicalCat(group.posts, data.allTraitPosts, data.whiteStages),
      segments,
      rings,
      total: d3.sum(segments, (s) => s.weight),       // sets the tail's length
      meanCute: d3.mean(group.posts, (p) => p.vals.ac_cute),
      meanDumb: d3.mean(group.posts, (p) => p.vals.ac_dumb),
    };
  });

  // Eyes: wide, wonky eyes for the dumbest group in this view; big shiny eyes for the cutest of
  // the others (so if one group is both, the dumb eyes win and the next-cutest gets the shine).
  // A tie on the mean goes to the first group. Every other cat gets one of the remaining sets,
  // chosen by hashing the view and group value.
  const dumbest = d3.greatest(cats, (c) => c.meanDumb);
  const cutest = d3.greatest(cats.filter((c) => c !== dumbest), (c) => c.meanCute);
  for (const cat of cats) {
    if (cat === dumbest) cat.eyes = EYES_DUMB;
    else if (cat === cutest) cat.eyes = EYES_CUTE;
    else cat.eyes = EYES_OTHER[stableHash(arr.key + ":" + cat.group.value) % EYES_OTHER.length];
  }

  return {
    arr,
    cats,
    maxTotal: d3.max(cats, (c) => c.total) || 0, // the longest tail in the view fills the full drawing
  };
}

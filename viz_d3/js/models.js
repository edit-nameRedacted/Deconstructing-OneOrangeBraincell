/*
  models.js — the two models' readings of a group of posts, as tail stripes.

  The robot button swaps the hand-code stripes for what a model "thinks" of the same posts. The
  upvote and comment segments stay as they are; only the stripes change. Two models, one tail each:

    qwen    one stripe per word family (cute, funny, calm, body, mind). Thickness = how much of the
            model's next-word odds went to that family, averaged over the group's posts (0–100%).
    siglip  one stripe per caption pair (dumb, cute, fat, derp, blank, loaf). Thickness = where the
            group's median score sits among all posts (its percentile, 0–100%), since the raw
            scores have no natural zero-to-one scale.

  Takes: model_data.json (built by build_model_data.py) and the page's posts.
  Gives back: prepareModels(raw, posts), modelStripes(models, group, which).
  Each stripe looks like a hand-code stripe to tail.js: { key, share, color, shortLabel, aria, … }.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { MODEL_STRIPE_SHADES, ordinal } from "./config.js";
import { MODEL_TEXT } from "./text.js";

// Sort SigLIP's scores across all posts once, so a group's percentile is quick to find.
export function prepareModels(raw, posts) {
  if (!raw) return null;
  const sortedSiglip = {};
  for (const score of raw.siglip.scores) {
    sortedSiglip[score] = posts
      .map((p) => raw.siglip.posts[p.id]?.[score])
      .filter((v) => v != null)
      .sort(d3.ascending);
  }
  return { ...raw, sortedSiglip };
}

// Where a value sits among sorted values, 0–1, ties counting half (as in data.js).
function percentile(sorted, value) {
  const below = d3.bisectLeft(sorted, value);
  const equal = d3.bisectRight(sorted, value) - below;
  return (below + 0.5 * equal) / sorted.length;
}

export function modelStripes(models, group, which) {
  const text = MODEL_TEXT[which];

  if (which === "qwen") {
    const readings = group.posts.map((p) => models.qwen.posts[p.id]).filter(Boolean);
    return models.qwen.families.map((family, i) => {
      const share = d3.mean(readings, (r) => r[family]) ?? 0;   // mean next-word odds for the family
      const percent = Math.round(share * 100);
      return {
        key: `qwen:${family}`,
        model: "qwen",
        name: family,
        label: text.stripes[family],
        share,
        valueText: `${percent}% of its next-word odds`,
        color: MODEL_STRIPE_SHADES[i],
        shortLabel: `${text.shortStripes[family]} · ${percent}%`,
        aria: `${text.stripes[family]}: ${percent}% of the model's next-word odds for this group`,
      };
    });
  }

  // SigLIP
  return models.siglip.scores.map((score, i) => {
    const median = d3.median(group.posts, (p) => models.siglip.posts[p.id]?.[score]);
    const pct = median == null ? 0 : percentile(models.sortedSiglip[score], median);
    const nth = ordinal(Math.round(pct * 100));
    return {
      key: `siglip:${score}`,
      model: "siglip",
      name: score,
      label: text.stripes[score],
      share: pct,                                  // the percentile sets the thickness
      valueText: `${nth} percentile of all posts`,
      color: MODEL_STRIPE_SHADES[i],
      shortLabel: `${text.shortStripes[score]} · ${nth} pct`,
      aria: `${text.stripes[score]}: this group's median is at the ${nth} percentile of all posts`,
    };
  });
}

// The words Qwen most often put first for this group, counting each post's top word per opening.
export function qwenTopWords(models, group, howMany = 5) {
  const counts = new Map();
  for (const p of group.posts) {
    const reading = models.qwen.posts[p.id];
    if (!reading) continue;
    for (const words of Object.values(reading.words)) {
      if (words[0]) counts.set(words[0], (counts.get(words[0]) ?? 0) + 1);
    }
  }
  return [...counts].sort((a, b) => b[1] - a[1]).slice(0, howMany);
}

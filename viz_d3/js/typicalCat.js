/*
  typicalCat.js — what the "typical cat" of a group of posts looks like.

  the design rule (2026-10-27), applied to the cat traits the vision model coded for each post:
    - White: the group's median % white fur. White zones are switched on in a fixed order
      (chin, locket, muzzle, …) until the cat's total white is as close as possible to that median.
    - Extra zones: a white zone that is at least 1.3x as common in the group as across all posts,
      and on at least 30% of the group, is added even if the median alone wouldn't reach it.
    - Body: kitten, slender or chunky only if that body is at least 1.5x as common as overall and
      at least 25% of the group (the most over-represented one wins); otherwise "typical".
    - A trait needs at least 3 cats in the group to count at all.
    - Stripes: on if at least half the group has them.

  Takes: the group's posts, all posts that have traits (the baseline), and white_stages.json.
  Gives back: { body, zones, stripes, medianWhite, extraZones, n, small }.
  Pure: no drawing, no page state. Replaces typicalCat() in the prototype.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { ZONES, BODIES_OTHER, TYPICAL } from "./config.js";

// Posts whose image had no usable cat have pct_white = null; they are left out.
export function hasTraits(post) {
  return post.traits.pct_white != null;
}

// Share of posts (0–1) whose traits pass a test, e.g. "has a white locket".
function shareWhere(posts, test) {
  if (posts.length === 0) return 0;
  return posts.filter((p) => test(p.traits)).length / posts.length;
}

// For one trait: how common it is in the group, how common overall, and the ratio (the "lift").
// Returns null when the trait can't count (absent overall, or fewer than MIN_CATS cats have it).
function traitLift(groupPosts, allPosts, test) {
  const countInGroup = groupPosts.filter((p) => test(p.traits)).length;
  const share = shareWhere(groupPosts, test);
  const shareOverall = shareWhere(allPosts, test);
  if (shareOverall === 0 || countInGroup < TYPICAL.MIN_CATS) return null;
  return { share, lift: share / shareOverall };
}

export function typicalCat(posts, allTraitPosts, whiteStages) {
  const cats = posts.filter(hasTraits);

  // No cats to go on: draw a plain typical cat and flag it as a guess.
  if (cats.length === 0) {
    return { body: "typical", zones: [], stripes: true, medianWhite: null, extraZones: [], n: 0, small: true };
  }

  const medianWhite = d3.median(cats, (p) => p.traits.pct_white);
  const stripes = shareWhere(cats, (t) => t.stripes) >= TYPICAL.STRIPES_SHARE;

  // Body: the most over-represented non-typical body that clears both thresholds.
  let body = "typical";
  let bestLift = 0;
  for (const candidate of BODIES_OTHER) {
    const result = traitLift(cats, allTraitPosts, (t) => t.body === candidate);
    if (!result) continue;
    const clears = result.lift >= TYPICAL.BODY_LIFT && result.share >= TYPICAL.BODY_SHARE;
    if (clears && result.lift > bestLift) {
      body = candidate;
      bestLift = result.lift;
    }
  }

  // Extra white zones: every zone that is over-represented enough.
  const extraZones = [];
  for (const zone of ZONES) {
    const result = traitLift(cats, allTraitPosts, (t) => t.zones.includes(zone));
    if (!result) continue;
    if (result.lift >= TYPICAL.ZONE_LIFT && result.share >= TYPICAL.ZONE_SHARE) extraZones.push(zone);
  }

  // How many zones (in order) to switch on so the total white is closest to the median.
  // stages[k] = % white with the first k zones on (k = 0 … 10), for this body.
  // On a tie, the smaller k wins, as in the prototype.
  const stages = whiteStages[body] || whiteStages.typical;
  let zoneCount = 0;
  stages.forEach((pctWhite, k) => {
    if (Math.abs(pctWhite - medianWhite) < Math.abs(stages[zoneCount] - medianWhite)) zoneCount = k;
  });

  // The zones to draw: the first zoneCount in order, plus any extras (without repeats).
  const zones = [...new Set([...ZONES.slice(0, zoneCount), ...extraZones])];

  return { body, zones, stripes, medianWhite, extraZones, n: cats.length, small: cats.length < TYPICAL.SMALL_GROUP };
}

/*
  checks.js — parity checks against the data builder's own numbers.

  Open the page with ?check on the end of the address (index.html?check). The page draws as
  usual; the results print to the browser console as a table, one row per check, and are also
  kept on window.checkResults.

  What is compared:
    - Group sizes and members: each hand-code group's posts vs groups[...] in the data file.
    - Typical cat: body, median % white and extra zones vs groups[...].cat.
    - Tail percentiles: every group's percentile for every tail variable vs groups[...].tail.
    - Chase splits: the size of each "Tails of" group vs the counts expected from posts[].tails.
*/
import { arrangement, percentileRank } from "./data.js";
import { typicalCat } from "./typicalCat.js";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

// Expected left / body / right sizes when chasing each tail variable (counted from the data
// file on 2026-11-01). A side with no posts is left out of the view, so it is listed as 0.
const EXPECTED_SPLITS = {
  score: [19, 144, 19], comments: [19, 144, 19], score_rel: [19, 144, 19], talk: [18, 146, 18],
  crossposts: [0, 171, 11], awards: [0, 167, 15], rank: [18, 146, 18], ac_dumb: [0, 173, 9],
  ac_cute: [4, 175, 3], look_white: [0, 169, 13], look_kg: [13, 152, 11],
};

const sameList = (a, b) => a.length === b.length && [...a].sort().join("|") === [...b].sort().join("|");
const close = (a, b, tolerance) => Math.abs(a - b) <= tolerance;

export function runChecks(data) {
  const rows = [];
  const record = (check, subject, pass, detail = "") => rows.push({ check, subject, pass: pass ? "pass" : "FAIL", detail });

  for (const [categoryKey, groupsByValue] of Object.entries(data.precomputed)) {
    const arr = arrangement(data, categoryKey);
    for (const group of arr.groups) {
      const expected = groupsByValue[group.value];
      const subject = `${categoryKey} = ${group.value}`;

      // Group sizes and members
      const ids = group.posts.map((p) => p.id);
      record("group members", subject, expected.n === ids.length && sameList(ids, expected.post_ids), `n ${ids.length} vs ${expected.n}`);

      // Typical cat
      const look = typicalCat(group.posts, data.allTraitPosts, data.whiteStages);
      const want = expected.cat;
      const ok = look.body === want.body && close(look.medianWhite, want.pct_white_median, 0.01) && sameList(look.extraZones, want.zones_distinctive);
      record("typical cat", subject, ok,
        `body ${look.body}/${want.body}, white ${look.medianWhite}/${want.pct_white_median}, extra [${look.extraZones}]/[${want.zones_distinctive}]`);

      // Tail percentiles (the data file rounds to 3 decimals)
      const misses = [];
      for (const varKey of Object.keys(data.tailvars)) {
        const median = d3.median(group.posts, (p) => p.vals[varKey]);
        const pct = median == null ? 0 : percentileRank(data, varKey, median);
        if (!close(pct, expected.tail[varKey].pct, 0.0006)) misses.push(`${varKey} ${pct.toFixed(3)}/${expected.tail[varKey].pct}`);
      }
      record("tail percentiles", subject, misses.length === 0, misses.join("; ") || "all 11 match");
    }
  }

  // Chase splits
  for (const [varKey, [left, body, right]] of Object.entries(EXPECTED_SPLITS)) {
    const arr = arrangement(data, "tail:" + varKey);
    const size = (side) => (arr.groups.find((g) => g.value === side)?.posts.length ?? 0);
    const got = [size("left"), size("body"), size("right")];
    record("chase split", varKey, got.join("/") === [left, body, right].join("/"), `${got.join(" / ")} vs ${left} / ${body} / ${right}`);
  }

  const failed = rows.filter((r) => r.pass !== "pass").length;
  console.log(`Checks: ${rows.length - failed} passed, ${failed} failed`);
  console.table(rows);
  window.checkResults = { rows, failed };
  return rows;
}

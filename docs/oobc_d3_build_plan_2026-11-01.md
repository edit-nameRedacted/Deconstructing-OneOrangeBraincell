# Typical Orange Cats — D3 build plan

Nov 1, 2026 · @AC · Companion to oobc_d3_rebuild_handoff_2026-11-01.md (live copy: "Build plan" tab of https://claude.ai/artifact/Cv7g6HNWxxBj2UK8q9SGMw)

The rebuild runs in four milestones, from data parity to a polished page, following the handoff's ten steps. This adds the module contracts, where each prototype function moves, eight corrections found in the prototype's code and data, the code style, and the decisions settled with AC, including one change to the tail: the group's mix moves onto tabby rings.

## Code style

Clarity comes first: AC should be able to open any file, read it top to bottom and explain what it does. Where shorter and clearer differ, the code stays clear; the prototype's one-liners get spelled out.

- No build step. Plain ES modules and D3 v7.9.0, served with `python -m http.server`. No bundler, framework or single-file export.
- D3 imported where it is used: `import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm"` at the top of each module that needs it.
- A header comment on every file: what it does, what it takes in, what it gives back, which part of the prototype it replaces.
- A comment on every function saying what it does and why. Where code applies one of AC's rules (typical cat, eyes, tail length), the comment quotes the rule.
- Named constants for every meaningful number (1.3x lift, 30% share, 1.5x, 25%, 3 cats, 0.3 minimum tail, 650 ms) in config.js, each with a one-line comment.
- Short functions with plain names (groupMedian, not gm); one step per line; ordinary loops where they read more clearly than chained calls.
- D3 where it reads better than plain JS, not everywhere. The first use of each D3 pattern (join, transition, scale, axis) gets an explaining comment.
- The tail geometry keeps its maths but gains a comment per step: cutting a band from the drawn tail, pointing bristles outward, placing the tail on each body.

## Milestones

| Milestone | Handoff steps | Done when |
| --- | --- | --- |
| A. Data parity | 1 skeleton, 2 data layer, 3 typical cat | `?check` reports all 29 hand-code groups match `groups` in the data file (n, post ids, body, % white, extra zones), no console errors |
| B. One cat with a tail | 4 static cat, 5 tail module | Cats match the prototype's by eye; segment boundaries match the prototype's (mix set to nothing) to 0.01 of tail length; ring thicknesses follow each group's mix; spikes never cut into the band |
| C. Row and tail view | 6 row with joins, 7 tail view | Switch, settings and zoom behave as in the prototype; tail fills the frame at desktop and 390 px |
| D. Details and polish | 8 details and Chase, 9 polish | Chasing upvotes gives 19 / 144 / 19; light/dark, keyboard, reduced motion, no horizontal scroll at 390 px |
| Stretch | 10 pounce | Cat chases its tail; skipped under reduced motion |

## Files and modules

```text
viz_d3/
  index.html  style.css
  js/ main.js config.js color.js data.js typicalCat.js kit.js tail.js
      state.js controls.js catView.js zoom.js details.js checks.js
```
Serve from the Orange_Braincells root (`python -m http.server`).

| Module | Holds | From the prototype |
| --- | --- | --- |
| config.js | TILT, ZONES, EYES_OTHER, SOURCES, INVERT, UNIT, DIGITS, STOPS; labelFor(key, value) | top-of-script constants; label rule appears twice |
| color.js | shade(t), palette(n) as a d3 interpolator | hex2lab, lab2hex, shade, palette |
| data.js | allVals, pctRank, arrangement(key), describe(arr, state) | median, mean, pctRank, arrangement, describe (d3.group/median/mean) |
| typicalCat.js | typicalCat(posts, allTraits, stages) | typicalCat, share |
| kit.js | loadKit, cloneCat, tilt, boxOf | catSvg, tilt, boxOf + build_viz.py's kit handling |
| tail.js | createTail(geometry) -> draw, HIDDEN, ATTACH | cat_tail_viz_template.js |
| state.js | state, set(patch), subscribe(fn) | state object + scattered render() calls |
| controls.js | switcher, title sizing, settings chips, mix select | sizeTitle, fixMix, option/chip building |
| catView.js | renderRow(view) | render |
| zoom.js | openZoom, closeZoom | openZoom, closeZoom, Esc |
| details.js | showInfo, strip | showInfo, strip |

## State and rendering

state = { arrange: "braincell", vars: Set(score, comments), mix: "failure", zoom: null, sel: null }. `set(patch)` is the only way anything changes.

| Keys changed | What redraws |
| --- | --- |
| arrange | Mix options fixed, title resized, zoom closed, row re-joined (exit/enter fades) |
| vars or mix | Same cats; tails updated in place via controller.update(); viewBox re-measured; open zoom redrawn without animation |
| zoom | Row hidden + 650 ms transition, or closed with focus back on the cat |
| sel | Segment bristles; details redrawn |

Join key: arrange + ":" + value. Measure for the shared viewBox after the join, with all cats visible.

## Tail rings for the mix

The group's mix (failure mode by default) moves off the tail's length and onto tabby rings, so tail length means rank and nothing else (settled by AC, Nov 1; replaces the handoff's mix segments). As segments, the shares added a full unit to every tail, compressing differences between groups by about half and filling about half of each default tail.

Length: variable segments only, max(0.3, HIDDEN + (1 - HIDDEN) x total / maxTotal), total = sum of the group's percentiles. No variables chosen: full-length tail with rings only.

Rings:
- One ring per value of the mix category, in display order base to tip (failure mode: Self, Physical, Object, Social, NA).
- Evenly spaced along the visible tail, from just past the hidden base to just short of the tip, drawn over the segments.
- Thickness = the value's share of the group, one scale for every cat; 100% = RING_MAX in config.js, tuned by eye in milestone B.
- Zero share = thin dashed ring, so absence reads as zero.
- Kit stripe colour, shown even when stripes are off; check contrast on the darkest segment in both themes.

Interaction: tail view labels each ring "Physical 36%"; rings are focusable buttons; a ring thickens on hover/select (bristles stay with segments); selecting opens mix details (group share vs all posts, post list, Chase this tail -> switches the view to the mix category).

Where it lives: tail.js draws rings, reusing the module's ring code (RINGS, rings: true) with data-driven positions and widths; data.js gives each cat a rings list (value, label, share) in place of mix segments; state.sel keeps the mix:<value> key.

## Corrections to the handoff

1. Percentile rank is a midrank (below + 0.5 x equal). Use (bisectLeft + bisectRight) / 2 / n; ties are heavy (Dumbness/Cuteness 5 distinct values, crossposts 7, % white 12).
2. kit.js must do build_viz.py's surgery after d3.xml: strip <metadata>, lift <style>, rewrite the 22 `#cat[` selectors to `.cat-kit[`, swap id for class; inject the style once into the head.
3. Round tail geometry stroke points to 0.1 on load, as the build script does.
4. Tail length = max(0.3, HIDDEN + (1 - HIDDEN) x total / maxTotal), HIDDEN = 0.06.
5. Chase uses precomputed posts[].tails; the strip uses dist.p10/p90. No d3.quantile.
6. 19/144/19 holds for upvotes, comments, upvotes per 1k only. Crossposts, awards, Dumbness, % white have no left tail (two cats). Estimated weight: 13/152/11 (6 posts without weight).
7. config.js also carries INVERT (rank), UNIT, DIGITS, SOURCES (Reddit / Hand ratings / How the cats look), EYES_OTHER.
8. selection.interrupt() replaces the anim counter; the three-pass frame and --lab sizing finishes before the transition.

## Checks (`?check` -> console table)

| Check | Compares | Milestone |
| --- | --- | --- |
| Group sizes and members | n and post ids vs `groups` | A |
| Typical cat | body, median % white, extra zones vs groups[...].cat (29 groups) | A |
| Segment weights | variable segments vs prototype describe() with its mix set to nothing, 4 decimals | B |
| Tail lengths, boundaries, rings | vs prototype (mix set to nothing); ring shares vs the prototype's mix shares | B |
| Eyes | big-shiny rule + hash sets match | C |
| Chase splits | all "Tails of" views vs item 6 | D |

## Decisions settled with AC (Nov 1)

- D3 loads from the pinned CDN.
- Separate files served locally, no single-file export.
- The tail keeps the prototype's OKLab shades, ported as they are.
- The group's mix is shown as tabby rings, not segments (see Tail rings for the mix).

# SVG: the cat kit and the drawings it's built from

Everything the page draws a cat with. The D3 page (`viz_d3/`) reads four files from here:
`cat_kit.svg`, `white_stages.json`, `eye_parts.json` and `tails/tail_geometry.json`.

## Current kit (V2, front-facing)

| Path | What it is |
| --- | --- |
| `cat_kit.svg` | **The kit the page uses**: 4 bodies, 10 white zones, 7 eye sets, coats, ears, mouths, fur edges. Built by `V2/build_kit_v2.py`. |
| `V2/SVG/` | The hand-drawn V2 parts (outline, stripes, ears, fluff, mouths, head turns) the kit is built from |
| `V2/assemble_v2.py`, `V2/build_kit_v2.py` | Assemble the parts, then build `cat_kit.svg` |
| `V2/eye_parts.py` → `eye_parts.json` | Each eye set's opening and pupil, so the eyes can look around |
| `white_stages.json` | How white each body is as white zones are added (from `measure_stages.py`) |
| `V2/head_turn/` | Hand alignment of the five head-turn poses on the V2 body |
| `V2/*preview*`, `V2/sequence_previews/` | Preview images and GIFs |
| `tails/` | The tail: `tail_geometry.py` turns the two tail drawings into `tail_geometry.json`; `cat_tail.js` (from `build_tail_js.py`) is the prototype's tail module |
| `sheet_tools/` | Turns sheets of cat drawings into layered SVG frames and animated sequences (see its README). Its `out/` working folder stays local |

## Source drawings

`source_drawings/` holds the hand drawings the scripts start from (they were Illustrator's `Asset N.svg` exports):

| File | Used by |
| --- | --- |
| `cat_v1_colour_regions.svg` | `regionize.py` (first kit's colour regions) |
| `cat_v1_outline.svg`, `cat_v1_eyes.svg` | `compose_kit.py` (first kit's outline and eyes) |
| `tail_long.svg`, `tail_short.svg` | `tails/tail_geometry.py` |
| `neuron_with_axon.svg`, `neuron_soma.svg` | The page's neuron cursor (`viz_d3/neuron_soma.svg` is the soma with the axon removed) |

## First kit (v1, 3/4 view), superseded

Kept because the V2 build borrows its eye sets. Not needed to run the page.

`regionize.py` → `cat_regions.svg` → `smooth_regions.py` (`smooth_parts.json`) → `trace_eyes.py` (`cat_eyes.svg`) →
`compose_kit.py`, plus `bodies/` (traced body types), `coats/` (coat variants), `region_area_pct.json` (each colour
region's share of the body) and the coat painter page (`build_painter.py`, `painter_template.html` → `cat_coat_painter.html`).

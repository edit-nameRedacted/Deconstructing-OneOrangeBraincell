/*
  tail.js — drawing a data tail on a cat.

  The tail is a hand drawing (SVG/tails/tail_geometry.json), not a generated shape. The file
  stores, per tail type ("long", "short"):
    - stroke:   the tail's outline as one run of points, from one side of the base, around the
                tip, and back down to the other side of the base;
    - stations: pairs of indices into that run. Station k says "at fraction k/(N-1) of the way
                from base to tip, the tail's two edges are at these two points of the outline".
  With stations, any stretch of the tail between two fractions (say 0.30 to 0.45) can be cut
  out as a closed shape — a "band" — by walking up one edge and back down the other.

  What gets drawn, back to front, inside the cat's body group (so it tilts with the body):
    1. the whole tail in coat colour;
    2. one band per tail variable (the segments), base to tip, each in its own shade;
       a segment's length is its weight (the group's percentile) out of the tail's visible length;
    3. the outline;
    4. two hidden "bristle" overlays: one follows the pointer, one marks the selected segment.
       They sit above the outline, so a bristling segment covers its own stretch of outline and
       reads as the tail puffing out, not as spikes growing out of a line;
    5. the stripes ("rings" in this file): one per hand code, each in its own colour, evenly spaced
       along the tail; a stripe's thickness is the share of the group with that code's standout
       value (a share of zero gets a thin dashed ring). Rings are
       on top so a bristling segment never hides them, and are pulled in from the edges by half
       the outline's width so they never cut into it. When a segment bristles, the rings on it
       stretch outward with the fur (clipped to the fur's outline), as a tabby's stripes would.

  Gives back: prepareTailGeometry(raw), tailLength(total, maxTotal), drawTail(svg, options).
  Replaces: viz/cat_tail_viz_template.js (window.CatTail). The geometry maths is unchanged.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { TAIL_MIN, RING_MAX, RING_EMPTY_DASH, OUTLINE_WIDTH } from "./config.js";

// ---------------------------------------------------------------------------
// Constants of the drawing (kit units unless noted)
// ---------------------------------------------------------------------------

// Where the tail enters each body: two points on the outer edge of the haunch, on the cat's left
// (the viewer's right), upper first, and how big the tail is on that body. The V2 cats face the
// viewer, so the tail comes out from behind the bum there; the body is drawn over its base.
// The points come from SVG/V2/build_kit_v2.py, which prints them on every build.
const ATTACH = {
  typical: { up: [232.7, 421.2], low: [216.0, 456.3], size: 1 },
  kitten: { up: [190.7, 446.0], low: [180.2, 467.1], size: 0.7 },
  slender: { up: [214.0, 419.3], low: [200.1, 455.5], size: 0.95 },
  chunky: { up: [264.3, 423.7], low: [243.3, 457.4], size: 1.1 },
};
const LEAD = 14;               // length of a label's leader line, in drawing units
// Fanned labels (a short tail, labels crowded): each leader turns FAN.step radians from the one
// before, and is long enough that neighbouring labels start FAN.gap label-heights apart.
const FAN = { step: 0.38, gap: 1.25 };
const SCALE = 0.62;            // tail-drawing units -> kit units at size 1
const INSET = 7;               // how far the base tucks in behind the body (grows with size)
const BODY_CENTRE = [115, 380];// a point inside every body; "outward" means away from it (checked by build_kit_v2.py)
const LINE = OUTLINE_WIDTH;    // outline width, matching the (slimmed) body outline
const SPIKE = 8;               // bristle length
const SPIKE_GAP = 3.2;         // space between bristles
const BRISTLE_MS = 90;         // how long the fur takes to puff out (short, so it feels immediate)
const SHORT_SPIKE = 0.35;      // the short points between spikes, as a share of SPIKE: far enough out
                               // (2.8 units) to cover the outline (1.9 units each side of the edge)
export const HIDDEN = 0.06;    // the first 6% of the tail is behind the body; segments start after it

// ---------------------------------------------------------------------------
// Geometry helpers (in the tail drawing's own units)
// ---------------------------------------------------------------------------

// The data file's stroke points, rounded to 0.1 as build_viz.py did, so segment boundaries land
// exactly where the prototype's did.
export function prepareTailGeometry(raw) {
  const out = {};
  for (const [type, g] of Object.entries(raw)) {
    out[type] = {
      stroke: g.stroke.map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]),
      stations: g.stations,
    };
  }
  return out;
}

// Helpers for walking one tail type's outline.
function outlineTools(geometry, type) {
  const S = geometry[type].stroke;
  const stations = geometry[type].stations;

  // The point at a fractional index along the outline (index 12.5 = halfway between points 12 and 13).
  const pointAt = (t) => {
    const i = Math.max(0, Math.min(S.length - 1, Math.floor(t)));
    const j = Math.min(S.length - 1, i + 1);
    const u = t - i;
    return [S[i][0] * (1 - u) + S[j][0] * u, S[i][1] * (1 - u) + S[j][1] * u];
  };

  // The outline points between two fractional indices, in either direction, ends included.
  const run = (t0, t1) => {
    const pts = [pointAt(t0)];
    if (t1 >= t0) for (let i = Math.ceil(t0); i < t1; i++) pts.push(S[i]);
    else for (let i = Math.floor(t0); i > t1; i--) pts.push(S[i]);
    pts.push(pointAt(t1));
    return pts;
  };

  // The two edge indices at a fraction q of the tail (0 = base, 1 = tip), between stored stations.
  const station = (q) => {
    const x = q * (stations.length - 1);
    const i = Math.min(stations.length - 2, Math.floor(x));
    const u = x - i;
    return [
      stations[i][0] * (1 - u) + stations[i + 1][0] * u,
      stations[i][1] * (1 - u) + stations[i + 1][1] * u,
    ];
  };

  // Is the outline's first point the upper end of the base? (Decides how it is turned to fit.)
  const startsUpper = S[0][1] < S[S.length - 1][1];
  return { S, pointAt, run, station, startsUpper };
}

// Total length of a polyline.
function polylineLength(pts) {
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return total;
}

// n points spaced evenly along a polyline.
function resample(pts, n) {
  const dist = [0];
  for (let i = 1; i < pts.length; i++) dist.push(dist[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const L = dist[dist.length - 1] || 1;
  const out = [];
  for (let k = 0; k < n; k++) {
    const target = (L * k) / (n - 1);
    let i = 1;
    while (i < dist.length - 1 && dist[i] < target) i++;
    const u = (target - dist[i - 1]) / (dist[i] - dist[i - 1] || 1);
    out.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * u, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * u]);
  }
  return out;
}

// Points -> an SVG path string. Coordinates are rounded to 2 decimals to keep paths short.
const round2 = (v) => +v.toFixed(2);
function pathFrom(pts, close = true) {
  return "M" + pts.map((p) => round2(p[0]) + "," + round2(p[1])).join(" L") + (close ? " Z" : "");
}

// A band of the tail between fractions q0 < q1, as three runs of points: edge A going up the
// tail, the cap C (only when q1 is the rounded-off end of a shortened tail), and edge B coming
// back down. Joined, they make one closed outline.
function band(tools, q0, q1, roundedEnd) {
  const [a0, b0] = tools.station(q0);
  const [a1, b1] = tools.station(q1);
  const A = tools.run(a0, a1);
  const B = tools.run(b1, b0);
  const C = [];
  if (roundedEnd) {
    // A half circle across the end, bulging toward where the tip would have been.
    const pa = A[A.length - 1];
    const pb = B[0];
    const mid = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];
    const towardTip = tools.pointAt((a1 + b1) / 2);
    let dx = towardTip[0] - mid[0], dy = towardTip[1] - mid[1];
    const dl = Math.hypot(dx, dy) || 1;
    dx /= dl; dy /= dl;
    const r = Math.hypot(pa[0] - pb[0], pa[1] - pb[1]) / 2;
    const ux = (pa[0] - mid[0]) / (r || 1), uy = (pa[1] - mid[1]) / (r || 1);
    for (let k = 1; k < 8; k++) {
      const angle = (Math.PI * k) / 8;
      C.push([mid[0] + r * (ux * Math.cos(angle) + dx * Math.sin(angle)), mid[1] + r * (uy * Math.cos(angle) + dy * Math.sin(angle))]);
    }
  }
  return { A, B, C };
}

// A ring's band pulled in from both edges by `d` (half the outline's width), so it sits inside
// the outline rather than over it. Each point moves toward the facing point on the other edge.
function insetBand(bd, d) {
  const toward = (p, q) => {
    const dx = q[0] - p[0], dy = q[1] - p[1], l = Math.hypot(dx, dy) || 1;
    const step = Math.min(d, l / 2);
    return [p[0] + (dx / l) * step, p[1] + (dy / l) * step];
  };
  // A runs base -> tip and B runs tip -> base, so A[i] faces B at the mirrored fraction.
  const facing = (P, Q, i) => Q[Math.round((1 - i / Math.max(1, P.length - 1)) * (Q.length - 1))];
  return {
    A: bd.A.map((p, i) => toward(p, facing(bd.A, bd.B, i))),
    B: bd.B.map((p, i) => toward(p, facing(bd.B, bd.A, i))),
  };
}

// The same band twice: smooth, and with bristles. The bristles point outward, meaning away from
// the facing point on the opposite edge (not by the outline's winding, which made spikes cut into
// the band in an early prototype). Both shapes have the same number of points, so D3 can morph
// one into the other by interpolating the numbers in the path strings.
function bandShapes(bd, scale) {
  const step = SPIKE_GAP / scale;
  const spike = SPIKE / scale;
  const nA = Math.max(6, Math.round(polylineLength(bd.A) / step) | 1);
  const nB = Math.max(6, Math.round(polylineLength(bd.B) / step) | 1);
  const A = resample(bd.A, nA);
  const B = resample(bd.B, nB);
  const unit = (x, y) => { const l = Math.hypot(x, y) || 1; return [x / l, y / l]; };

  // A runs base -> tip and B runs tip -> base, so the point facing P[i] sits at the mirrored
  // fraction of Q. Every other point is a long spike; the rest stay near the edge.
  const zigzag = (P, Q) => P.map((p, i) => {
    if (i === 0 || i === P.length - 1) return p;
    const facing = Q[Math.round((1 - i / (P.length - 1)) * (Q.length - 1))];
    const out = unit(p[0] - facing[0], p[1] - facing[1]);
    const k = i % 2 ? spike : spike * SHORT_SPIKE;
    return [p[0] + out[0] * k, p[1] + out[1] * k];
  });

  // The rounded end (if any) bristles away from its own centre.
  const capCentre = bd.C.length ? [(A[A.length - 1][0] + B[0][0]) / 2, (A[A.length - 1][1] + B[0][1]) / 2] : null;
  const cap = bd.C.map((p, i) => {
    const out = unit(p[0] - capCentre[0], p[1] - capCentre[1]);
    const k = spike * (i % 2 ? 1 : SHORT_SPIKE);
    return [p[0] + out[0] * k, p[1] + out[1] * k];
  });

  return {
    smooth: pathFrom([...A, ...bd.C, ...B]),
    bristled: pathFrom([...zigzag(A, B), ...cap, ...zigzag(B, A)]),
  };
}

// Where the tail sits on a body: scale it, turn it so its base lines up with the gap in the
// haunch, and tuck the base in behind the body. Returns the transform as a matrix, a function
// that applies it to a point, and the overall scale (drawing units -> kit units).
function placement(tools, bodyName, size) {
  const at = ATTACH[bodyName] || ATTACH.typical;
  const scale = SCALE * at.size * size;
  const inset = INSET * size;
  const S = tools.S;
  const upper = tools.startsUpper ? S[0] : S[S.length - 1];
  const lower = tools.startsUpper ? S[S.length - 1] : S[0];

  // Angle that turns the drawing's base (upper -> lower) onto the body's gap (up -> low).
  const baseDir = [lower[0] - upper[0], lower[1] - upper[1]];
  const gapDir = [at.low[0] - at.up[0], at.low[1] - at.up[1]];
  const angle = Math.atan2(gapDir[1], gapDir[0]) - Math.atan2(baseDir[1], baseDir[0]);
  const c = Math.cos(angle) * scale;
  const s = Math.sin(angle) * scale;

  // Base middles, in drawing units and kit units.
  const baseMid = [(upper[0] + lower[0]) / 2, (upper[1] + lower[1]) / 2];
  const gapMid = [(at.up[0] + at.low[0]) / 2, (at.up[1] + at.low[1]) / 2];

  // Unit normal of the gap, pointing into the body (toward BODY_CENTRE): the inset direction.
  let nx = -gapDir[1], ny = gapDir[0];
  const nl = Math.hypot(nx, ny);
  nx /= nl; ny /= nl;
  if ((BODY_CENTRE[0] - gapMid[0]) * nx + (BODY_CENTRE[1] - gapMid[1]) * ny < 0) { nx = -nx; ny = -ny; }

  // Translate so the turned, scaled base middle lands on the gap middle, pushed in by `inset`.
  const tx = gapMid[0] + nx * inset - (c * baseMid[0] - s * baseMid[1]);
  const ty = gapMid[1] + ny * inset - (s * baseMid[0] + c * baseMid[1]);
  const M = [c, s, -s, c, tx, ty];
  const apply = (p) => [M[0] * p[0] + M[2] * p[1] + M[4], M[1] * p[0] + M[3] * p[1] + M[5]];
  return { scale, M, apply };
}

// ---------------------------------------------------------------------------
// Tail length
// ---------------------------------------------------------------------------

// How much of the drawn tail shows (0–1). The longest tail in the view (maxTotal) fills the whole
// drawing; the others are in proportion, past the hidden base, and never shorter than TAIL_MIN.
// With no tail variables chosen, every tail is drawn full length (it then carries only rings).
export function tailLength(total, maxTotal) {
  if (!maxTotal) return 1;
  return Math.max(TAIL_MIN, HIDDEN + (1 - HIDDEN) * (total / maxTotal));
}

// ---------------------------------------------------------------------------
// Styles (added to the page once)
// ---------------------------------------------------------------------------

// --u is one screen-independent "line unit" in the tail's own coordinates (1 / scale), set on
// each tail, so lines keep the same weight on every body size.
const TAIL_CSS = `
.cat-tail .t-coat { fill: var(--cat-coat, #E8913A); }
.cat-tail .t-line { fill: none; stroke: var(--cat-outline, #1B1714); stroke-linecap: round; stroke-linejoin: round; }
.cat-tail .t-seg { stroke: none; cursor: pointer; outline: none; }
.cat-tail .t-cut { fill: none; stroke: var(--cat-outline, #1B1714); stroke-opacity: 0.35; pointer-events: none; }
.cat-tail .t-hl { stroke: var(--cat-outline, #1B1714); stroke-linejoin: round; pointer-events: none; }
.cat-tail .t-ring { fill: var(--tail-ring, #4A2410); stroke: var(--cat-outline, #1B1714);
  stroke-width: calc(var(--u) * 0.9); pointer-events: none; transition: stroke-width 150ms ease-out; }
.cat-tail .t-ring.is-empty { fill: none; stroke-opacity: 0.55; }
.cat-tail .t-ring.is-on { stroke-width: calc(var(--u) * 2.4); }
.cat-tail .t-ring.is-empty.is-on { stroke-opacity: 1; }
.cat-tail .t-ring-hit { fill: transparent; stroke: none; cursor: pointer; outline: none; }
.cat-tail .t-label { font: 500 13px/1 var(--tail-font, system-ui, sans-serif); fill: var(--tail-label, #5C564F); pointer-events: none; }
.cat-tail .t-label.is-on { fill: var(--tail-label-on, #1B1714); font-weight: 700; }
.cat-tail .t-lead { stroke: var(--tail-label, #5C564F); stroke-width: 0.8; stroke-opacity: 0.7; }
.cat-tail .t-key { stroke: var(--cat-outline, #1B1714); stroke-width: calc(var(--lab, 13px) * 0.06); paint-order: stroke; }
@media (prefers-reduced-motion: reduce) { .cat-tail .t-ring { transition: none; } }`;

// Every clip path needs an id that is unique on the page; this counter makes them.
let clipCounter = 0;

function addTailStylesOnce() {
  if (document.getElementById("cat-tail-css")) return;
  d3.select(document.head).append("style").attr("id", "cat-tail-css").text(TAIL_CSS);
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

/*
  drawTail(svg, options) draws a tail on the cat in `svg` and returns a small controller.

  options:
    geometry   prepared tail geometry (prepareTailGeometry)
    type       "long" | "short"
    size       tail scale against the body
    length     how much of the tail shows, 0.3–1 (see tailLength)
    segments   [{ key, label, shortLabel, fill, weight, aria }]   base to tip
    rings      [{ key, shortLabel, share, color, aria }]          base to tip (the stripes)
    labels     true to write labels beside segments and rings (the zoomed view)
    interactive  true to make segments and rings keyboard buttons (the zoomed view). In the row
               they sit inside each cat's <button>, so there they only take mouse clicks.
    onSelect   called with the segment or ring when it is clicked or chosen with Enter / Space

  controller: update(newOptions) redraws with changed options; select(key) marks a segment or
  ring as chosen; layoutLabels() places the labels again (after their size changes; they fan out at
  an angle where they would overlap); remove() takes the tail away.

  The tail never decides by itself what is selected: a click calls onSelect, the page updates its
  state, and the page calls select(key). So the selection has one source of truth: state.sel.
*/
export function drawTail(svg, options) {
  addTailStylesOnce();
  let opts = { type: "long", size: 1.6, length: 1, segments: [], rings: [], labels: false, interactive: false, onSelect: null, ...options };
  let selectedKey = null;
  let tailG = null;       // d3 selection: the tail, inside the body group, behind the body
  let labelsG = null;     // d3 selection: the labels, above everything
  let items = [];         // drawn segments and rings: { key, kind, hit, label, shapes?, ring? }
  let labelSpots = [];    // each label's anchor on the tail: { side, q, edge, n, lead, label } (layoutLabels)
  let hoverOverlay = null, selectOverlay = null;
  let hoveredSegment = null;  // key of the segment under the pointer (its rings puff out too)

  function render() {
    tailG?.remove();
    labelsG?.remove();
    items = [];
    labelSpots = [];
    hoveredSegment = null;

    const bodyName = svg.dataset.body || "typical";
    const bodyG = svg.querySelector(".body");
    const tools = outlineTools(opts.geometry, opts.type);
    const place = placement(tools, bodyName, opts.size);
    const u = 1 / place.scale;                              // one kit unit, in drawing units
    const end = Math.max(TAIL_MIN, Math.min(1, opts.length)); // visible end of the tail
    const shortened = end < 0.999;

    // The tail group goes first inside the body group, so the body is drawn over its base.
    tailG = d3.select(bodyG).insert("g", ":first-child")
      .attr("class", "cat-tail")
      .attr("transform", `matrix(${place.M.map(round2).join(" ")})`)
      .style("--u", `${u}px`);

    // 1. The whole tail in coat colour.
    const whole = band(tools, 0, end, shortened);
    tailG.append("path").attr("class", "t-coat").attr("d", pathFrom([...whole.A, ...whole.C, ...whole.B]));

    if (opts.labels) labelsG = d3.select(bodyG).append("g").attr("class", "cat-tail t-labels");

    // 2. Segments: split the visible tail (past the hidden base) by weight.
    const segG = tailG.append("g").attr("class", "t-segs");
    const totalWeight = d3.sum(opts.segments, (s) => Math.max(0, s.weight)) || 1;
    let before = 0;
    opts.segments.forEach((seg) => {
      const q0 = HIDDEN + ((end - HIDDEN) * before) / totalWeight;
      before += Math.max(0, seg.weight);
      const q1 = HIDDEN + ((end - HIDDEN) * before) / totalWeight;
      if (q1 - q0 < 1e-4) return;                          // a zero-length segment is not drawn
      const isLast = before >= totalWeight - 1e-9;
      const shapes = bandShapes(band(tools, q0, q1, isLast && shortened), place.scale);

      const path = segG.append("path")
        .attr("class", "t-seg")
        .attr("d", shapes.smooth)
        .attr("data-key", seg.key)
        .style("fill", seg.fill);
      makeButton(path, seg.aria);

      // A faint cut line across the tail where this segment starts.
      const [ea, eb] = tools.station(q0);
      tailG.append("path").attr("class", "t-cut").attr("stroke-width", 0.8 * u)
        .attr("d", pathFrom([tools.pointAt(ea), tools.pointAt(eb)], false));

      // The bristled shape as a clip path: rings on this segment are clipped to it when they
      // stretch out with the fur.
      const clipId = `tail-clip-${++clipCounter}`;
      tailG.append("clipPath").attr("id", clipId).append("path").attr("d", shapes.bristled);

      const label = opts.labels ? addLabel(tools, place, (q0 + q1) / 2, "outer", seg.shortLabel) : null;
      items.push({ key: seg.key, kind: "segment", data: seg, hit: path, label, shapes, q0, q1, clipId });
    });

    // 3. The outline: the drawn edges and rounded end, but not the base (it is under the body).
    const line = band(tools, 0, end, shortened);
    tailG.append("path").attr("class", "t-line").attr("stroke-width", LINE * u)
      .attr("d", pathFrom([...line.A, ...line.C, ...line.B], false));

    // 4. Bristle overlays, hidden until a segment is hovered or selected. Their stroke matches the
    // outline's width, so at the first frame the overlay exactly covers the outline it replaces.
    const overlayG = tailG.append("g").attr("class", "t-overlays");
    selectOverlay = overlayG.append("path").attr("class", "t-hl").attr("stroke-width", LINE * u).style("display", "none");
    hoverOverlay = overlayG.append("path").attr("class", "t-hl").attr("stroke-width", LINE * u).style("display", "none");

    // 5. Rings (the stripes): one per hand code, centred in equal slots along the visible tail, inset from the
    // outline by half its width.
    // Each ring has two shapes with the same points: `normal`, inside the outline, and `puffed`,
    // pushed out past the edges by a spike's length, used while its segment bristles.
    const ringInset = (LINE * u) / 2;
    const ringPuff = -SPIKE * u;                             // a negative inset pushes outward
    const segments = items.slice();                          // so far `items` holds only segments
    const ringG = tailG.append("g").attr("class", "t-rings");
    const n = opts.rings.length;
    opts.rings.forEach((ring, i) => {
      const centre = HIDDEN + ((end - HIDDEN) * (i + 0.5)) / n;
      const halfSlot = (end - HIDDEN) / n / 2;
      let visible, normal, puffed;
      if (ring.share > 0) {
        // Thickness along the tail = share of the group x RING_MAX (one scale for every cat).
        const half = Math.min((ring.share * RING_MAX) / 2, halfSlot);
        const bd = band(tools, centre - half, centre + half, false);
        const inner = insetBand(bd, ringInset), outer = insetBand(bd, ringPuff);
        normal = pathFrom([...inner.A, ...inner.B]);
        puffed = pathFrom([...outer.A, ...outer.B]);
        visible = ringG.append("path").attr("class", "t-ring").attr("d", normal).style("fill", ring.color);
      } else {
        // No posts with this value: a dashed line across the tail, so zero reads as zero.
        const [ea, eb] = tools.station(centre);
        const ends = { A: [tools.pointAt(ea)], B: [tools.pointAt(eb)] };
        const inner = insetBand(ends, ringInset), outer = insetBand(ends, ringPuff);
        normal = pathFrom([inner.A[0], inner.B[0]], false);
        puffed = pathFrom([outer.A[0], outer.B[0]], false);
        visible = ringG.append("path").attr("class", "t-ring is-empty").attr("d", normal)
          .attr("stroke-dasharray", RING_EMPTY_DASH.split(" ").map((d) => d * u).join(" "));
      }
      // The segment this ring sits on: the ring is clipped to that segment's bristled outline, which
      // contains the smooth band, so the clip only shows once the ring stretches out.
      const onSegment = segments.find((s) => centre >= s.q0 && centre < s.q1);
      if (onSegment) visible.attr("clip-path", `url(#${onSegment.clipId})`);
      // An invisible, wider band over the ring takes the clicks, so thin rings are easy to hit.
      const hitHalf = Math.min(halfSlot * 0.8, 0.02);
      const hitBand = band(tools, centre - hitHalf, centre + hitHalf, false);
      const hit = ringG.append("path").attr("class", "t-ring-hit").attr("d", pathFrom([...hitBand.A, ...hitBand.B]))
        .attr("data-key", ring.key);
      makeButton(hit, ring.aria);

      const label = opts.labels ? addLabel(tools, place, centre, "inner", ring.shortLabel) : null;
      // The label starts with a small square key in the stripe's shade (the text itself stays in
      // the normal label colour, so white and amber labels still read on a light page).
      if (label) {
        label.text(null);
        label.append("tspan").attr("class", "t-key").style("fill", ring.color).text("■ ");
        label.append("tspan").text(ring.shortLabel);
      }
      items.push({ key: ring.key, kind: "ring", data: ring, hit, label, ring: visible, normal, puffed,
        segmentKey: onSegment?.key ?? null, isPuffed: false });
    });


    // Pointer, focus and keyboard behaviour for every segment and ring.
    for (const item of items) {
      item.hit
        .on("pointerenter focus", () => highlight(item, hoverOverlay))
        .on("pointerleave blur", () => unhighlight(item))
        .on("click", () => choose(item))
        .on("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(item); }
        });
    }

    if (selectedKey) select(selectedKey);
    if (opts.labels) {
      layoutLabels();
      svg._layoutTailLabels = layoutLabels;     // zoom.js reruns it after changing the label size
    }
  }

  // A tooltip on hover, and (in the zoomed view) a keyboard button with a spoken label.
  function makeButton(selection, ariaLabel) {
    selection.append("title").text(ariaLabel);
    if (opts.interactive) selection.attr("tabindex", 0).attr("role", "button").attr("aria-label", ariaLabel);
  }

  // A label beside the tail at fraction q, with a short leader line. Segments are labelled on the
  // outer edge (away from the body), rings on the inner edge, so the two never collide. Where the
  // label goes is worked out by layoutLabels, below; this only records where its leader starts.
  function addLabel(tools, place, q, side, text) {
    const [ea, eb] = tools.station(q);
    const pa = place.apply(tools.pointAt(ea));
    const pb = place.apply(tools.pointAt(eb));
    const distanceFromBody = (p) => Math.hypot(p[0] - BODY_CENTRE[0], p[1] - BODY_CENTRE[1]);
    const outer = distanceFromBody(pa) > distanceFromBody(pb) ? pa : pb;
    const inner = outer === pa ? pb : pa;
    const edge = side === "outer" ? outer : inner;
    const other = side === "outer" ? inner : outer;
    let dx = edge[0] - other[0], dy = edge[1] - other[1];
    const dl = Math.hypot(dx, dy) || 1;
    const lead = labelsG.append("line").attr("class", "t-lead");
    const label = labelsG.append("text").attr("class", "t-label").text(text);
    labelSpots.push({ side, q, edge, n: [dx / dl, dy / dl], lead, label });
    return label;
  }

  // Place every label. Normally each sits straight out from its edge of the tail, level, at the end
  // of a short leader. When a tail is short, the labels on one side crowd onto the same few units of
  // edge and run over each other; then that side's labels fan out instead: each leader turns a
  // little further along the tail than the one before, and its label is written along the leader
  // (turned so it never reads upside down). Run again whenever the label size changes (zoom.js).
  function layoutLabels() {
    for (const side of ["outer", "inner"]) {
      const spots = labelSpots.filter((l) => l.side === side).sort((a, b) => a.q - b.q);
      spots.forEach(placeLevel);
      if (crowded(spots)) fan(spots);
    }
  }

  function placeLevel({ edge, n: [dx, dy], lead, label }) {
    const lx = edge[0] + dx * LEAD, ly = edge[1] + dy * LEAD;
    lead.attr("x1", round2(edge[0] + dx * 2)).attr("y1", round2(edge[1] + dy * 2))
      .attr("x2", round2(lx - dx * 2)).attr("y2", round2(ly - dy * 2));
    label.attr("transform", null).attr("dy", null)
      .attr("x", round2(lx + (dx >= 0 ? 1.5 : -1.5))).attr("y", round2(ly + 4))
      .attr("text-anchor", dx >= 0 ? "start" : "end");
  }

  // Whether any two labels on a side overlap (boxes, with a little air).
  function crowded(spots) {
    const boxes = spots.map((l) => l.label.node().getBBox());
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        if (a.x < b.x + b.width + 1 && b.x < a.x + a.width + 1 && a.y < b.y + b.height + 1 && b.y < a.y + a.height + 1) return true;
      }
    }
    return false;
  }

  function fan(spots) {
    const k = spots.length;
    const size = parseFloat(getComputedStyle(spots[0].label.node()).fontSize) || 13;
    // The fan points the way the labels point on average; it turns base to tip the way the tail runs.
    let mx = d3.sum(spots, (l) => l.n[0]), my = d3.sum(spots, (l) => l.n[1]);
    const ml = Math.hypot(mx, my) || 1;
    mx /= ml; my /= ml;
    const first = spots[0].edge, last = spots[k - 1].edge;
    const turn = Math.sign(mx * (last[1] - first[1]) - my * (last[0] - first[0])) || 1;
    // Leaders long enough that neighbouring labels start a line's height and a bit apart.
    const length = Math.max(LEAD, (FAN.gap * size) / FAN.step);
    spots.forEach(({ edge, lead, label }, i) => {
      const a = turn * (i - (k - 1) / 2) * FAN.step;
      const dx = mx * Math.cos(a) - my * Math.sin(a), dy = mx * Math.sin(a) + my * Math.cos(a);
      const lx = edge[0] + dx * length, ly = edge[1] + dy * length;
      lead.attr("x1", round2(edge[0] + dx * 2)).attr("y1", round2(edge[1] + dy * 2))
        .attr("x2", round2(lx - dx * 2)).attr("y2", round2(ly - dy * 2));
      const tx = lx + dx * 1.5, ty = ly + dy * 1.5;
      const leftward = dx < 0;                                  // turn half round so it reads left to right
      const angle = (Math.atan2(dy, dx) * 180) / Math.PI + (leftward ? 180 : 0);
      label.attr("x", round2(tx)).attr("y", round2(ty)).attr("dy", "0.35em")
        .attr("text-anchor", leftward ? "end" : "start")
        .attr("transform", `rotate(${angle.toFixed(1)} ${round2(tx)} ${round2(ty)})`);
    });
  }

  // Hover / focus: a segment bristles (its overlay morphs from smooth to spiky); a ring thickens.
  function highlight(item, overlay) {
    item.label?.classed("is-on", true);
    if (item.kind === "ring") { item.ring.classed("is-on", true); return; }
    if (overlay === hoverOverlay) { hoveredSegment = item.key; puffRings(); }
    overlay.interrupt()                                // stop any morph still running
      .style("display", null)
      .style("fill", item.data.fill)
      .attr("d", item.shapes.smooth)
      .transition().duration(prefersReducedMotion() ? 0 : BRISTLE_MS).ease(d3.easeCubicOut)
      .attr("d", item.shapes.bristled);                // D3 interpolates the numbers in the path
  }
  function unhighlight(item) {
    if (item.key === selectedKey) return;              // the selected item stays marked
    item.label?.classed("is-on", false);
    if (item.kind === "ring") item.ring.classed("is-on", false);
    else {
      hoverOverlay.interrupt().style("display", "none");
      hoveredSegment = null;
      puffRings();
    }
  }

  // Rings stretch out with the fur while their segment bristles (hovered or selected), and settle
  // back when it stops. Only rings whose state changes are animated.
  function puffRings() {
    for (const item of items) {
      if (item.kind !== "ring") continue;
      const shouldPuff = item.segmentKey != null && (item.segmentKey === hoveredSegment || item.segmentKey === selectedKey);
      if (shouldPuff === item.isPuffed) continue;
      item.isPuffed = shouldPuff;
      item.ring.interrupt()
        .transition().duration(prefersReducedMotion() ? 0 : BRISTLE_MS).ease(d3.easeCubicOut)
        .attr("d", shouldPuff ? item.puffed : item.normal);
    }
  }

  // A click or Enter only reports the choice; the page answers by calling select(key).
  function choose(item) {
    opts.onSelect?.(item.data);
  }

  // Mark one segment or ring as selected (or none, with null). Called by the page.
  function select(key) {
    selectedKey = key;
    selectOverlay?.interrupt().style("display", "none");
    for (const item of items) {
      const on = item.key === key;
      item.label?.classed("is-on", on);
      if (item.kind === "ring") item.ring.classed("is-on", on);
      else if (on) highlight(item, selectOverlay);
    }
    puffRings();
  }

  render();
  return {
    update(newOptions) { opts = { ...opts, ...newOptions }; render(); },
    select,
    layoutLabels,
    remove() { tailG?.remove(); labelsG?.remove(); },
  };
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/*
  kit.js — loading AC's cat kit (SVG/cat_kit.svg) and making one drawable cat from it.

  The kit is one SVG holding four bodies, ten white zones and seven eye sets. Which ones show is
  switched by CSS, from data attributes on the kit's root: data-body, data-white, data-eyes,
  data-stripes. So drawing a typical cat = copy the kit, set four attributes.

  The kit was made to appear once per page: its root has id="cat" and its CSS targets #cat[...].
  With a row of cats, an id can't repeat, so on load this file does what build_viz.py used to do:
    - drops the <metadata> block (a large content-credentials blob the page doesn't need),
    - lifts the kit's <style> out, rewrites "#cat[" to ".cat-kit[" and adds it to the page once,
    - swaps id="cat" for class="cat-kit".
  It also slims the body outline (a filled shape, so it can't just take a thinner stroke): an SVG
  "erode" filter shaves OUTLINE_ERODE units off each side of every line in the kit's .outline groups.

  Each cat's ears vary (look.ears, from earsFor in data.js): the inside of the ear is tinted pinker or
  darker, and each ear's tuft is scaled from its root, kept inside the ear.

  Gives back: loadKit(url) -> the kit as a reusable template; cloneCat(...) -> one cat's <svg>;
  bodyOf(svg); tilt(svg); boxOf(svg, elements).
  Replaces: catSvg(), tilt() and boxOf() in the prototype, and the kit handling in build_viz.py.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { TILT, OUTLINE_ERODE, EARS } from "./config.js";

// Load the kit file and prepare it for repeated use. Call once.
export async function loadKit(url) {
  const doc = await d3.xml(url);           // d3.xml fetches and parses the file as an XML document
  const svg = doc.documentElement;

  svg.querySelector("metadata")?.remove();

  // Move the kit's CSS into the page, retargeted from the single #cat to every .cat-kit.
  const kitStyle = svg.querySelector("style");
  if (kitStyle) {
    const css = kitStyle.textContent.replaceAll("#cat[", ".cat-kit[");
    d3.select(document.head).append("style").attr("id", "cat-kit-css").text(css);
    kitStyle.remove();
  }

  svg.removeAttribute("id");
  svg.classList.add("cat-kit");

  addThinOutlineFilter();
  addEarCss();

  // Bring the parsed node into this page's document, so copies of it can be inserted.
  return document.importNode(svg, true);
}

// The erode filter, defined once in an invisible <svg> on the page, and the CSS that applies it to
// every cat's outline. feMorphology "erode" shrinks a filled shape by `radius` on every edge, so a
// line drawn as a filled shape gets thinner by twice the radius. The radius is in kit units.
function addThinOutlineFilter() {
  const holder = d3.select(document.body).append("svg")
    .attr("width", 0).attr("height", 0).attr("aria-hidden", "true")
    .style("position", "absolute");
  holder.append("filter").attr("id", "thin-outline")
    .append("feMorphology").attr("operator", "erode").attr("radius", OUTLINE_ERODE);
  d3.select(document.head).append("style").attr("id", "thin-outline-css")
    .text(".cat-kit .outline { filter: url(#thin-outline); }");
}

// A cat's ear tone: the coat scheme's ear colour (--cat-ear) mixed toward --ear-toward by --ear-amount,
// both set per cat by applyEars. Covers the sequences' ear insides too.
function addEarCss() {
  d3.select(document.head).append("style").attr("id", "ear-tone-css").text(
    `.cat-kit .k-ear-under { stroke: var(--cat-ear, #C1886A); stroke-width: 5; stroke-linejoin: round; }
     .cat-kit[data-ear-tone] .k-ear, .cat-kit[data-ear-tone] .seq-layer .r-ear {
       fill: color-mix(in oklab, var(--cat-ear, #C1886A), var(--ear-toward, #C1886A) var(--ear-amount, 0%)); }
     .cat-kit[data-ear-tone] .k-ear-under {
       stroke: color-mix(in oklab, var(--cat-ear, #C1886A), var(--ear-toward, #C1886A) var(--ear-amount, 0%)); }`);
}

// One cat: a copy of the kit showing only this cat's body, white zones, eyes and stripes.
// `look` comes from typicalCat(); `eyes` is one of the kit's eye-set names.
export function cloneCat(kitTemplate, look, eyes) {
  const svg = kitTemplate.cloneNode(true);

  // Keep only the body this cat uses (the others would just be hidden by CSS; removing them
  // keeps measurements and the DOM simple).
  for (const body of svg.querySelectorAll(".body")) {
    if (body.dataset.body !== look.body) body.remove();
  }

  svg.dataset.body = look.body;
  svg.dataset.white = look.zones.join(" ");   // e.g. "chin locket paws"
  svg.dataset.eyes = eyes;
  svg.dataset.stripes = look.stripes ? "on" : "off";
  if (look.ears) applyEars(svg, look.ears);
  svg.setAttribute("aria-hidden", "true");     // the button around it carries the spoken label
  return svg;
}

// ---- Ears: tone and tuft size per cat (EARS in config.js; data.js picks the values) ----
let earUid = 0;
const SVGNS = "http://www.w3.org/2000/svg";

// The box of a path drawn with absolute commands only (the kit's ear paths), from its coordinates.
function boxOfD(d) {
  const nums = d.match(/-?\d*\.?\d+(?:e-?\d+)?/g).map(Number);
  const xs = nums.filter((_, i) => i % 2 === 0), ys = nums.filter((_, i) => i % 2 === 1);
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}
const subpaths = (d) => d.split(/(?=M)/).map((s) => s.trim()).filter(Boolean);

function applyEars(svg, ears) {
  // Tone: mix the coat scheme's ear colour toward pinker or darker (CSS in addEarCss).
  svg.dataset.earTone = "";
  svg.style.setProperty("--ear-toward", ears.tone >= 0 ? EARS.pinker : EARS.darker);
  svg.style.setProperty("--ear-amount", `${Math.round(Math.abs(ears.tone) * 100)}%`);

  // Tufts: the cream tuft and its lines, per ear, scaled from the tuft's root (its lowest point on the
  // inner edge of the ear) and masked to the inside of the ear, so a big tuft never spills out.
  const body = svg.querySelector(".body");
  const inside = body?.querySelector(".k-ear");
  const cream = body?.querySelector(".k-ear-cream");
  const lines = body?.querySelector(".k-ear-line");
  if (!inside || !cream) return;
  const sides = subpaths(cream.getAttribute("d")).map(boxOfD).sort((a, b) => a.x0 - b.x0);
  if (sides.length !== 2) return;
  const mid = (sides[0].x1 + sides[1].x0) / 2;
  const roots = [[sides[0].x1, sides[0].y1], [sides[1].x0, sides[1].y1]];     // inner, lowest corner
  const scale = [ears.tuftLeft, ears.tuftRight];
  const id = `ear${++earUid}`;
  const defs = svg.querySelector("defs") || svg.insertBefore(document.createElementNS(SVGNS, "defs"), svg.firstChild);
  // The inside of the ear is the pink shape plus the tuft it leaves room for, widened a little to cover the
  // seam between them (and, for the lines, the ear's edge they sit on). Tufts are masked to it.
  const earInside = `<path d="${inside.getAttribute("d")}" fill="#fff"/><path d="${cream.getAttribute("d")}" fill="#fff"/>`;
  for (const [name, edge] of [["in", 2.5], ["line", 3.5]]) {    // widened over the seam between pink and tuft
    const mask = document.createElementNS(SVGNS, "mask");
    mask.id = `${id}-${name}`;
    mask.setAttribute("maskUnits", "userSpaceOnUse");
    mask.setAttribute("x", "-1000"); mask.setAttribute("y", "-1000"); mask.setAttribute("width", "3000"); mask.setAttribute("height", "3000");
    mask.innerHTML = edge ? earInside.replaceAll('fill="#fff"/>', `fill="#fff" stroke="#fff" stroke-width="${edge}" stroke-linejoin="round"/>`) : earInside;
    defs.append(mask);
  }
  // Where the tuft was drawn, the pink shape has a tuft-shaped gap (the coat shows through it). Fill the
  // gap with the ear colour, so a smaller tuft leaves ear behind, not coat.
  const underlay = cream.cloneNode(false);
  underlay.setAttribute("class", "k-ear k-ear-under");     // drawn a little wider, to cover the seam the tuft lines hid
  const under = document.createElementNS(SVGNS, "g");
  under.setAttribute("mask", `url(#${id}-line)`);
  under.append(underlay);
  cream.parentNode.insertBefore(under, cream);
  ["left", "right"].forEach((side, i) => {
    const clip = document.createElementNS(SVGNS, "clipPath");
    clip.id = `${id}-${side}`;
    clip.innerHTML = i === 0 ? `<rect x="-1000" y="-1000" width="${1000 + mid}" height="3000"/>`
                             : `<rect x="${mid}" y="-1000" width="1000" height="3000"/>`;
    defs.append(clip);
  });
  for (const el of [cream, lines].filter(Boolean)) {
    const parent = el.parentNode, spot = el.nextSibling;    // the tuft goes back where it was (lines keep
    const wrap = document.createElementNS(SVGNS, "g");     // their outline group, and its thinning filter)
    wrap.setAttribute("mask", `url(#${id}-${el === cream ? "in" : "line"})`);
    ["left", "right"].forEach((side, i) => {
      const [rx, ry] = roots[i], s = scale[i];
      const half = document.createElementNS(SVGNS, "g");
      half.setAttribute("clip-path", `url(#${id}-${side})`);
      const g = document.createElementNS(SVGNS, "g");
      g.setAttribute("transform", `translate(${rx} ${ry}) scale(${s}) translate(${-rx} ${-ry})`);
      g.append(i === 0 ? el.cloneNode(true) : el);
      half.append(g);
      wrap.append(half);
    });
    parent.insertBefore(wrap, spot);
  }
}

// The cat's body group (the tail is drawn inside it, so both move together).
export function bodyOf(svg) {
  return svg.querySelector(".body");
}

// Rotate the body a few degrees clockwise about the middle of its base, so the cat stands up a
// little straighter. The svg must already be on the page and visible: getBBox measures nothing
// for hidden elements. Call BEFORE drawing the tail, so the pivot is the base of the body alone
// (as in the prototype); the tail, drawn inside the body group afterwards, rotates with it.
export function tilt(svg) {
  const body = bodyOf(svg);
  body.removeAttribute("transform");          // measure the untilted body
  const box = body.getBBox();
  const baseMiddleX = box.x + box.width / 2;
  const baseY = box.y + box.height;
  body.setAttribute("transform", `rotate(${TILT} ${baseMiddleX.toFixed(1)} ${baseY.toFixed(1)})`);
}

// The bounding box [x, y, width, height] of some elements, in the svg's own units (its viewBox),
// including any rotation. getBBox would ignore the tilt, so instead: take each element's box on
// screen and map its four corners back into svg units with the inverse of the screen matrix.
export function boxOf(svg, elements) {
  const screenToSvg = svg.getScreenCTM().inverse();
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const el of elements) {
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) continue;      // hidden or empty: nothing to measure
    const corners = [[r.left, r.top], [r.right, r.top], [r.left, r.bottom], [r.right, r.bottom]];
    for (const [x, y] of corners) {
      const p = new DOMPoint(x, y).matrixTransform(screenToSvg);
      x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y);
    }
  }
  return [x0, y0, x1 - x0, y1 - y0];
}

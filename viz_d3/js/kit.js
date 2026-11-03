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

  Gives back: loadKit(url) -> the kit as a reusable template; cloneCat(...) -> one cat's <svg>;
  bodyOf(svg); tilt(svg); boxOf(svg, elements).
  Replaces: catSvg(), tilt() and boxOf() in the prototype, and the kit handling in build_viz.py.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { TILT, OUTLINE_ERODE } from "./config.js";

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
  svg.setAttribute("aria-hidden", "true");     // the button around it carries the spoken label
  return svg;
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

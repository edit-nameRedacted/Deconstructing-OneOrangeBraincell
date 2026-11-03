/*
  catView.js — the row of typical cats, one per group.

  Built with a D3 data join: each cat is bound to its group, keyed by cat.id ("<arrangement>:<value>").
  The key is read from each cat's own data, so a cat already on the page keeps the key of the
  view it was drawn for.
    - enter:  a new group gets a new cat (a button holding the cat's svg, its label and its number
              of posts), which fades in;
    - update: a cat whose group is still there keeps its body and only has its tail redrawn
              (this is what happens when the tail settings change);
    - exit:   a cat whose group is gone is removed.
  Switching category changes every key, so every cat is replaced; changing the tail settings
  keeps every key, so only the tails move.

  All cats are drawn at one shared scale: after the join, every cat's body (tail included) is
  measured, and all of them get the same viewBox — the box that fits the largest.

  Takes: the view (from describeView), the kit template, the tail geometry and an onOpen callback.
  Gives back: renderRow(...) -> the shared viewBox, which the zoom starts from; tailOptions(...),
  the tail settings for one cat, which the zoom reuses.
  Replaces: render() in the prototype.
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { TAIL_TYPE, TAIL_SIZE, ROW_PAD } from "./config.js";
import { cloneCat, tilt, boxOf, bodyOf } from "./kit.js";
import { drawTail, tailLength } from "./tail.js";

const FADE_MS = 300;

// The options for one cat's tail in the row (no labels; the zoomed view has those).
export function tailOptions(cat, view, geometry, extra = {}) {
  return {
    geometry,
    type: TAIL_TYPE,
    size: TAIL_SIZE,
    length: tailLength(cat.total, view.maxTotal),
    segments: cat.segments,
    rings: cat.rings,
    labels: false,
    ...extra,
  };
}

export function renderRow(rowElement, view, kit, geometry, onOpen) {
  const row = d3.select(rowElement);
  rowElement.hidden = false;   // the row must be visible to be measured

  row.selectAll("button.cat")
    .data(view.cats, (cat) => cat.id)
    .join(
      // A new cat: button > svg + label. The tail controller is kept on the button element
      // (as .tail) so later updates can redraw just the tail.
      (enter) => enter.append("button")
        .attr("type", "button")
        .attr("class", "cat")
        .style("opacity", 0)
        .each(function (cat) {
          const svg = cloneCat(kit, cat.look, cat.eyes);
          svg.setAttribute("viewBox", kit.getAttribute("viewBox"));
          this.append(svg);
          d3.select(this).append("span").attr("class", "lab").text(cat.group.label);
          d3.select(this).append("span").attr("class", "count").text(`${cat.group.posts.length} posts`);
          tilt(svg);
        })
        .call((enter) => enter.transition().duration(FADE_MS).style("opacity", 1)),
      (update) => update,
      (exit) => exit.remove(),
    )
    // For every cat now in the row: its spoken label, its tail and its click handler.
    .attr("aria-label", (cat) => `${cat.group.label}, ${cat.group.posts.length} posts. Show its tail.`)
    .each(function (cat) {
      const svg = this.querySelector("svg");
      const index = view.cats.indexOf(cat);
      const options = tailOptions(cat, view, geometry, { onSelect: (item) => onOpen(index, item.key) });
      if (this.tail) this.tail.update(options);
      else this.tail = drawTail(svg, options);
    })
    // Clicking the cat (anywhere but a segment or ring) opens its tail with nothing selected.
    .on("click", (event, cat) => {
      if (event.target.closest(".t-seg, .t-ring-hit")) return;
      onOpen(view.cats.indexOf(cat), null);
    });

  return shareViewBox(rowElement, kit);
}

// Give every cat in the row the same viewBox, so they are all drawn at one scale.
function shareViewBox(rowElement, kit) {
  const svgs = [...rowElement.querySelectorAll("svg.cat-kit")];
  // Measure each body (with its tail) in the kit's own frame first.
  for (const svg of svgs) svg.setAttribute("viewBox", kit.getAttribute("viewBox"));
  const boxes = svgs.map((svg) => boxOf(svg, [bodyOf(svg)]));
  const x0 = d3.min(boxes, (b) => b[0]);
  const y0 = d3.min(boxes, (b) => b[1]);
  const x1 = d3.max(boxes, (b) => b[0] + b[2]);
  const y1 = d3.max(boxes, (b) => b[1] + b[3]);
  const shared = [x0 - ROW_PAD, y0 - ROW_PAD, x1 - x0 + 2 * ROW_PAD, y1 - y0 + 2 * ROW_PAD];
  for (const svg of svgs) svg.setAttribute("viewBox", shared.map((v) => v.toFixed(1)).join(" "));
  return shared;
}

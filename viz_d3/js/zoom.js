/*
  zoom.js — the tail view: one cat's tail, enlarged, with its segments and rings labelled.

  Opening it:
    1. The row hides; a fresh copy of the cat is drawn in the zoom stage, framed exactly as it was
       in the row (the row's shared viewBox), with a labelled tail.
    2. The frame that fits just the tail and its labels is measured. Labels are sized in kit units,
       so their size depends on the zoom: the frame is measured, the labels resized to read at
       ZOOM_LABEL_PX on screen, and measured again (three passes settle it).
    3. The body fades out (CSS) while a D3 transition moves the viewBox from the row's frame to
       the tail's frame.
  Closing it shows the row again and puts keyboard focus back on that cat.

  Takes: the view, the cat index, the selected key, the row's viewBox, kit and geometry.
  Gives back: openZoom(...) -> the tail controller (so main.js can select segments); closeZoom().
  Replaces: openZoom() and closeZoom() in the prototype (its requestAnimationFrame loop is now a
  D3 transition).
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { ZOOM_MS, ZOOM_LABEL_PX } from "./config.js";
import { cloneCat, tilt, boxOf, bodyOf } from "./kit.js";
import { watchGaze } from "./gaze.js";
import { drawTail } from "./tail.js";
import { tailOptions } from "./catView.js";

const $ = (id) => document.getElementById(id);

export function openZoom({ view, index, selectedKey, animate, rowViewBox, kit, geometry, onSelect }) {
  // `animate` is true when the view is newly opened, false when it is redrawn after a settings change.
  const cat = view.cats[index];
  $("row").hidden = true;
  $("zoom").hidden = false;
  $("zoom-title").textContent = cat.group.label;
  $("zoom-n").textContent = `${cat.group.posts.length} posts`;

  // 1. A fresh copy of the cat, framed as in the row.
  const stage = $("zoom-stage");
  stage.replaceChildren();
  const svg = cloneCat(kit, cat.look, cat.eyes);
  svg.removeAttribute("aria-hidden");
  svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", `Tail of ${cat.group.label}`);
  svg.setAttribute("viewBox", rowViewBox.join(" "));
  stage.append(svg);
  tilt(svg);
  if (cat.followsPointer) watchGaze(svg);  // the seeking cat keeps following the pointer when zoomed
  const tail = drawTail(svg, tailOptions(cat, view, geometry, { labels: true, interactive: true, onSelect }));
  if (selectedKey) tail.select(selectedKey);

  // 2. The frame that fits the tail and its labels, with labels sized for the zoomed scale.
  const frame = frameForTail(svg, stage);

  // 3. Fade the body and move the frame. d3.interpolate on two arrays of four numbers gives
  // the in-between arrays; attrTween writes each one as the viewBox.
  bodyOf(svg).classList.add("faded");
  const duration = animate && !prefersReducedMotion() ? ZOOM_MS : 0;
  const between = d3.interpolate(rowViewBox, frame);
  d3.select(svg)
    .transition("zoom")
    .duration(duration)
    .ease(d3.easeCubicOut)
    .attrTween("viewBox", () => (t) => between(t).map((v) => v.toFixed(2)).join(" "));

  // Move keyboard focus to the back button only when the view first opens, so ticking a
  // setting while zoomed doesn't pull focus away from the settings panel.
  if (animate) $("back").focus({ preventScroll: true });
  return tail;
}

// The viewBox that fits just the tail and its labels, inside the svg's stage. Labels are sized in
// kit units, so their size depends on the zoom: the frame is measured, the labels resized to read
// at ZOOM_LABEL_PX on screen, and measured again (three passes settle it). Also sets the svg's
// width to the frame's shape. The svg must show its starting viewBox and be visible.
// Used by the zoom here and by the two model tails (modelView.js).
export function frameForTail(svg, stage) {
  const tailParts = () => [svg.querySelector(".cat-tail"), svg.querySelector(".t-labels")];
  const stageHeight = svg.clientHeight;
  const stageWidth = stage.clientWidth;
  let frame = null;
  // Each pass places the labels for the current label size (fanning them if they crowd), frames
  // them, and sets the size for that frame; a last pass places them at the final size.
  for (let pass = 0; pass < 3; pass++) {
    svg._layoutTailLabels?.();
    const box = boxOf(svg, tailParts());
    const pad = Math.max(box[2], box[3]) * 0.05;
    frame = [box[0] - pad, box[1] - pad, box[2] + 2 * pad, box[3] + 2 * pad];
    // The svg is as wide as the frame's shape allows, up to the stage's width.
    const width = Math.min(stageWidth, (stageHeight * frame[2]) / frame[3]);
    const pixelsPerUnit = Math.min(width / frame[2], stageHeight / frame[3]);
    svg.style.width = Math.round(width) + "px";
    svg.style.setProperty("--lab", (ZOOM_LABEL_PX / pixelsPerUnit).toFixed(2) + "px");
  }
  if (svg._layoutTailLabels) {
    svg._layoutTailLabels();
    const box = boxOf(svg, tailParts());
    const pad = Math.max(box[2], box[3]) * 0.05;
    frame = [box[0] - pad, box[1] - pad, box[2] + 2 * pad, box[3] + 2 * pad];
  }
  return frame;
}

export function closeZoom(index) {
  d3.select("#zoom-stage svg").interrupt("zoom");   // stop a zoom still in motion
  $("zoom").hidden = true;
  $("row").hidden = false;
  // Put keyboard focus back on the cat that was zoomed.
  if (index != null) $("row").querySelectorAll("button.cat")[index]?.focus({ preventScroll: true });
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

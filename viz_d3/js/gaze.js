/*
  gaze.js — a cat's pupils follow the pointer, a little. Which cats: GAZE.who in config.js (the cat
  seeking the braincell; the pointer is the braincell).

  The kit draws each eye as one or two filled shapes, often with the pupil and the lid line as one shape,
  so the pupil can't simply be picked out and moved. SVG/eye_parts.json (built by SVG/V2/eye_parts.py)
  says, per eye set and eye, which region is the opening and which is the pupil. With that, each eye of a
  watched cat is redrawn in three layers, inside its eye set's group (so it turns and tilts with the head):
    - the eye whites, as drawn (left in place);
    - the pupil: the drawing clipped to the pupil region, slid toward the pointer, and kept inside the opening;
    - the lid line: the drawing with the pupil region cut out, staying put.
  The original dark shapes are hidden (class gaze-off) rather than removed, so blink.js still measures the
  eyes from them, and sequence.js still copies them whole.

  Where a pupil looks: it starts where it is drawn (each set has its own look: sideways, up, half-lidded)
  and drifts part of the way (GAZE.amount in config.js) toward where it would sit if the cat looked
  straight at the pointer. So the cat glances toward the pointer without losing its expression. A pointer
  close to a cat gets a smaller glance than one across the page (GAZE.reach). When the pointer leaves the
  window, the pupils go back to where they are drawn.

  Eye sets without a pupil to move (squint: shut eyes) are left alone. The lids from blink.js stay on top.
  Only cats on screen are updated, only while the pointer moves or a pupil is still settling. Mouse only,
  and nothing under prefers-reduced-motion. A cat playing a sequence (sequence.js) has its own eyes, so
  it's skipped while it plays.

  Gives back: watchGaze(svg) to make a cat's pupils follow the pointer.
*/
import { GAZE } from "./config.js";
import { loadEyeParts } from "./sequence.js";

const SVGNS = "http://www.w3.org/2000/svg";
const SHAPES = "path, polygon, polyline, ellipse, circle, rect, line";
let uid = 0;
let parts = null;                   // eye_parts.json's sets, once loaded
const watched = new Set();
let pointer = null;                 // {x, y} in client pixels, or null when the pointer is off the page
let frame = null, lastTime = 0;

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function el(name, attrs = {}, parent = null) {
  const e = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.append(e);
  return e;
}

function addCss() {
  if (document.getElementById("gaze-css")) return;
  const s = document.createElement("style");
  s.id = "gaze-css";
  s.textContent = ".cat-kit .gaze-off { visibility: hidden; }";
  document.head.append(s);
}

// ---- Building one cat's moving pupils (for the eye set it is showing) ----
// The eye set's drawing without its whites and without the lids or another gaze layer.
function eyeDrawing(eyes) {
  const g = el("g");
  for (const c of eyes.children) {
    if (c.classList.contains("blink") || c.classList.contains("gaze")) continue;
    g.append(c.cloneNode(true));
  }
  g.querySelectorAll(".k-eye-white").forEach((w) => w.remove());
  return g;
}

function build(svg, set) {
  const eyes = svg.querySelector(`.eyes[data-set="${set}"]`);
  const part = parts?.[set];
  if (!eyes || !part || !Object.values(part).some((p) => p.pupil)) return { set, eyes: [] };
  const layer = el("g", { class: "gaze" });
  const drawing = eyeDrawing(eyes);
  const defs = el("defs", {}, layer);
  const list = [];
  for (const p of Object.values(part)) {
    const id = `gaze${++uid}`;
    const o = p.opening_box, e = p.eye_box;
    let shift = null;
    if (p.pupil) {
      el("path", { d: p.opening }, el("clipPath", { id: `${id}-open` }, defs));
      el("path", { d: p.pupil }, el("clipPath", { id: `${id}-pupil` }, defs));
      shift = el("g", {}, el("g", { "clip-path": `url(#${id}-open)` }, layer));
      el("g", { "clip-path": `url(#${id}-pupil)` }, shift).append(drawing.cloneNode(true));
    }
    // the lid line: this eye's drawing with the pupil cut out (a little wider, so no hairline is left behind)
    const pad = Math.max(e.w, e.h);
    const mask = el("mask", { id: `${id}-line`, maskUnits: "userSpaceOnUse",
      x: e.cx - pad, y: e.cy - pad, width: 2 * pad, height: 2 * pad }, defs);
    el("rect", { x: e.cx - e.w / 2 - 2, y: e.cy - e.h / 2 - 2, width: e.w + 4, height: e.h + 4, fill: "#fff" }, mask);
    if (p.pupil) el("path", { d: p.pupil, fill: "#000", stroke: "#000", "stroke-width": 0.8, "stroke-linejoin": "round" }, mask);
    el("g", { mask: `url(#${id}-line)` }, layer).append(drawing.cloneNode(true));
    if (shift) list.push({ shift, o, p: p.pupil_box, x: 0, y: 0 });
  }
  // under the lids from blink.js, over the whites
  eyes.insertBefore(layer, eyes.querySelector(":scope > .blink"));
  for (const c of eyes.children) {
    if (c === layer || c.classList.contains("blink")) continue;
    for (const s of [c, ...c.querySelectorAll(SHAPES)]) {
      if (s.matches(SHAPES) && !s.classList.contains("k-eye-white")) s.classList.add("gaze-off");
    }
  }
  return { set, eyes: list, group: eyes };
}

// ---- Following the pointer ----
function onScreen(svg) {
  const r = svg.getBoundingClientRect();
  return r.width > 0 && r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth;
}

// Move every watched cat's pupils one step toward where they should look. Returns whether any still moves.
function update(dt) {
  const k = 1 - Math.exp(-dt / GAZE.ease);
  let moving = false;
  for (const svg of watched) {
    if (!svg.isConnected) { watched.delete(svg); continue; }
    if (svg._sequence || !onScreen(svg)) continue;
    if (!svg._gaze || svg._gaze.set !== svg.dataset.eyes) svg._gaze = build(svg, svg.dataset.eyes);
    const g = svg._gaze;
    if (!g.eyes.length) continue;
    const ctm = g.group.getScreenCTM();
    if (!ctm) continue;
    const toEyes = ctm.inverse();
    for (const e of g.eyes) {
      let tx = 0, ty = 0;
      if (pointer) {
        const at = new DOMPoint(pointer.x, pointer.y).matrixTransform(toEyes);    // the pointer, in eye-set units
        const vx = at.x - e.o.cx, vy = at.y - e.o.cy, len = Math.hypot(vx, vy) || 1;
        const centre = new DOMPoint(e.o.cx, e.o.cy).matrixTransform(ctm);
        const strength = Math.min(1, Math.hypot(pointer.x - centre.x, pointer.y - centre.y) / GAZE.reach);
        // where the pupil's centre would be, looking straight at the pointer (kept inside the opening)
        const fx = e.o.cx + (vx / len) * strength * Math.max(0, e.o.w / 2 - e.p.w / 2);
        const fy = e.o.cy + (vy / len) * strength * Math.max(0, e.o.h / 2 - e.p.h / 2) * GAZE.vertical;
        tx = GAZE.amount * (fx - e.p.cx);
        ty = GAZE.amount * (fy - e.p.cy);
      }
      e.x += (tx - e.x) * k;
      e.y += (ty - e.y) * k;
      if (Math.abs(tx - e.x) > 0.02 || Math.abs(ty - e.y) > 0.02) moving = true;
      e.shift.setAttribute("transform", `translate(${e.x.toFixed(2)} ${e.y.toFixed(2)})`);
    }
  }
  return moving;
}

function step(now) {
  const dt = Math.min(100, now - lastTime);
  lastTime = now;
  frame = update(dt) ? requestAnimationFrame(step) : null;
}

function wake() {
  if (frame || document.hidden) return;
  lastTime = performance.now();
  frame = requestAnimationFrame(step);
}

let listening = false;
function listen() {
  if (listening) return;
  listening = true;
  window.addEventListener("pointermove", (ev) => {
    if (ev.pointerType !== "mouse") return;
    pointer = { x: ev.clientX, y: ev.clientY };
    wake();
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => { pointer = null; wake(); });
  window.addEventListener("scroll", wake, { passive: true });      // the cats move under a still pointer
}

// Make a cat's pupils follow the pointer.
export function watchGaze(svg) {
  if (reducedMotion()) return;
  addCss();
  watched.add(svg);
  listen();
  loadEyeParts().then((p) => { parts = p; wake(); });
}

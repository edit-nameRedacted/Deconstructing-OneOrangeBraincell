/*
  blink.js — the cats blink.

  Each eye gets a pair of eyelids laid over it: an upper lid (fur coloured, with a dark lid line along
  its edge) and a lower lid, both clipped to an oval just bigger than the eye. At rest both lids sit
  outside the oval, so nothing shows. A blink slides the upper lid down and the lower lid up until
  they meet on a curve, which leaves the closed eye drawn as one curved line, then slides them back.

  This works for every eye set in the kit without drawing anything per set: where each eye is, and
  how big, is measured from the eye whites (.k-eye-white) of the set the cat is showing. The lids go
  inside that set's group, so they turn with the head and tilt with the body. If a cat's eye set
  changes (the pounce switches sets), the lids are rebuilt for the new set at its next blink.

  The lids are fur coloured: the coat, or the white when the cat has a white face.

  When cats blink (times in config.js, BLINK):
    - each cat blinks once every 10–30 seconds, the wait picked at random each time, and each blink is
      at random either quick or slow (a cat's friendly "I trust you");
    - never two cats at once: a cat whose turn comes while another is mid-blink waits until that blink
      is over (plus a short gap);
    - a slow blink when the pointer rests on a cat in the row, unless another cat is mid-blink.
  Blinks only play for cats on screen, and not at all under prefers-reduced-motion.

  Gives back: watchBlinks(svg) to make a cat blink on its own; blink(svg, {slow}) for one blink;
  closeEyes(svg, amount) to hold the lids part way (0 open, 1 shut), e.g. for a sleepy cat.
*/
import { BLINK } from "./config.js";

const SVGNS = "http://www.w3.org/2000/svg";
let clipCount = 0;

// ---- Where the eyes are ----
// Boxes of the visible eye set's whites, in the eye group's own units, split into left and right eye.
function eyeBoxes(eyes) {
  const toEyes = eyes.getCTM().inverse();
  let shapes = [...eyes.querySelectorAll(".k-eye-white")];
  if (shapes.length < 2) shapes = [...eyes.querySelectorAll("path, polygon, ellipse, circle")];
  const boxes = shapes.map((el) => {
    const b = el.getBBox();
    if (!b.width || !b.height) return null;
    const m = toEyes.multiply(el.getCTM());
    const pts = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
  }).filter(Boolean).sort((a, b) => (a.x0 + a.x1) - (b.x0 + b.x1));
  if (boxes.length === 0) return [];
  // Split at the widest gap between neighbouring shapes: everything left of it is one eye.
  let cut = 1, widest = -Infinity;
  for (let i = 1; i < boxes.length; i++) {
    const gap = boxes[i].x0 - Math.max(...boxes.slice(0, i).map((b) => b.x1));
    if (gap > widest) { widest = gap; cut = i; }
  }
  const union = (list) => ({
    x0: Math.min(...list.map((b) => b.x0)), x1: Math.max(...list.map((b) => b.x1)),
    y0: Math.min(...list.map((b) => b.y0)), y1: Math.max(...list.map((b) => b.y1)),
  });
  return boxes.length === 1 ? [union(boxes)] : [union(boxes.slice(0, cut)), union(boxes.slice(cut))];
}

// ---- Building the lids ----
function el(name, attrs, parent) {
  const e = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.append(e);
  return e;
}

// The lids of one eye. All lengths scale with the eye's height, so a small eye gets thin lids.
export function lidsFor(box, group, furColour) {
  const w = box.x1 - box.x0, h = box.y1 - box.y0;
  const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2;
  const pad = BLINK.pad * h;                   // the oval reaches over the eye's own outline
  const rx = w / 2 + pad, ry = h / 2 + pad;
  const sag = BLINK.curve * h;                 // how far the middle of the lid edge hangs below its ends
  const lw = Math.max(BLINK.lineMin, BLINK.line * h);
  const L = cx - rx - lw, R = cx + rx + lw;

  const id = `blink-clip-${++clipCount}`;
  const defs = el("defs", {}, group);
  el("ellipse", { cx, cy, rx, ry }, el("clipPath", { id }, defs));
  const clipped = el("g", { "clip-path": `url(#${id})`, class: "blink-lids" }, group);
  // Each lid is drawn with its edge's ends at y = 0 and moved into place by a CSS transform.
  const edge = `M${L},0 Q${cx},${2 * sag} ${R},0`;
  const lower = el("path", { d: `${edge} L${R},${3 * h} L${L},${3 * h} Z`, fill: furColour }, clipped);
  const upper = el("g", {}, clipped);
  el("path", { d: `M${L},${-3 * h} L${R},${-3 * h} L${R},0 Q${cx},${2 * sag} ${L},0 Z`, fill: furColour }, upper);
  el("path", { d: edge, fill: "none", stroke: "var(--cat-outline, #462E29)", "stroke-width": lw, "stroke-linecap": "round" }, upper);

  const shutAt = cy + BLINK.shut * ry - sag;   // where the edge's ends are when the eye is shut
  return {
    upper, lower,
    upperOpen: cy - ry - sag - lw, upperShut: shutAt,
    lowerOpen: cy + ry + lw, lowerShut: shutAt,
  };
}

function ensureLids(svg) {
  const set = svg.dataset.eyes;
  if (svg._lids && svg._lids.set === set) return svg._lids;
  const eyes = svg.querySelector(`.eyes[data-set="${set}"]`);
  if (!eyes || !eyes.getBBox().width) return null;    // not on the page yet, or hidden
  svg._lids?.group.remove();                           // lids built for another eye set
  const white = (svg.dataset.white || "").split(" ").includes("face");
  const fur = white ? "var(--cat-white, #F5F4F3)" : "var(--cat-coat, #D78E34)";
  const group = el("g", { class: "blink" }, eyes);
  const lids = eyeBoxes(eyes).map((b) => lidsFor(b, group, fur));
  svg._lids = { set, lids, group };
  setLids(svg._lids, 0);
  return svg._lids;
}

// Place one eye's lids (from lidsFor): 0 = open, 1 = shut.
export function setLid(l, amount) {
  l.upper.style.transform = `translate(0px, ${l.upperOpen + amount * (l.upperShut - l.upperOpen)}px)`;
  l.lower.style.transform = `translate(0px, ${l.lowerOpen + amount * (l.lowerShut - l.lowerOpen)}px)`;
}

// Place every lid: 0 = open, 1 = shut.
function setLids(state, amount) {
  for (const l of state.lids) {
    l.upper.style.transform = `translate(0px, ${l.upperOpen + amount * (l.upperShut - l.upperOpen)}px)`;
    l.lower.style.transform = `translate(0px, ${l.lowerOpen + amount * (l.lowerShut - l.lowerOpen)}px)`;
  }
}

// ---- Blinking ----
// One blink. The keyframes are the lids' closedness over time; returns the running animations.
export function blink(svg, { slow = false } = {}) {
  const state = ensureLids(svg);
  if (!state) return [];
  const t = slow ? BLINK.slow : BLINK.quick;
  const total = t.close + t.hold + t.open;
  const keys = [[0, 0], [t.close / total, 1], [(t.close + t.hold) / total, 1], [1, 0]];
  const anims = [];
  for (const l of state.lids) {
    for (const [part, open, shut] of [[l.upper, l.upperOpen, l.upperShut], [l.lower, l.lowerOpen, l.lowerShut]]) {
      anims.push(part.animate(keys.map(([offset, a]) => ({
        offset, transform: `translate(0px, ${open + a * (shut - open)}px)`,
        easing: a ? "cubic-bezier(.4,0,.6,1)" : "cubic-bezier(.3,0,.2,1)",
      })), { duration: total }));
    }
  }
  return anims;
}

// Hold the lids part way shut (0 open, 1 shut).
export function closeEyes(svg, amount) {
  const state = ensureLids(svg);
  if (state) setLids(state, amount);
}

// ---- Blinking on their own ----
const watched = new Set();
let timer = null;
let busyUntil = 0;                 // when the blink now playing (any cat's) ends

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const nextIn = () => BLINK.every[0] + Math.random() * (BLINK.every[1] - BLINK.every[0]);
const length = (slow) => { const t = slow ? BLINK.slow : BLINK.quick; return t.close + t.hold + t.open; };

function onScreen(svg) {
  const r = svg.getBoundingClientRect();
  return r.width > 0 && r.bottom > 0 && r.right > 0 && r.top < window.innerHeight && r.left < window.innerWidth;
}

// Start one cat's blink, if no other cat is blinking. Returns whether it started.
function startBlink(svg, slow) {
  const now = performance.now();
  if (now < busyUntil || holding) return false;
  if (!blink(svg, { slow }).length) return false;
  busyUntil = now + length(slow) + BLINK.gap;
  return true;
}

function tick() {
  if (document.hidden) return;
  const now = performance.now();
  for (const svg of watched) {
    if (!svg.isConnected) { watched.delete(svg); continue; }
    if (now < svg._nextBlink) continue;
    if (svg._sequence) { svg._nextBlink = now + nextIn(); continue; }   // a sequence is playing: its eyes follow the drawing
    if (now < busyUntil) {                          // another cat is blinking: go right after it
      svg._nextBlink = busyUntil + Math.random() * 400;
      continue;
    }
    if (onScreen(svg)) startBlink(svg, Math.random() < BLINK.slowShare);
    svg._nextBlink = performance.now() + nextIn();
  }
  if (watched.size === 0) { clearInterval(timer); timer = null; }
}

// Whether a blink is playing now (sequence.js waits for it before starting a sequence).
export const blinkBusy = () => performance.now() < busyUntil;

// While a sequence plays, no cat starts a blink: the playing cat's eyes follow its drawing, and the
// others wait, so there is only ever one thing moving at a time.
let holding = 0;
export function holdBlinks(svg, on) {
  holding = Math.max(0, holding + (on ? 1 : -1));
  svg._sequence = on;
}

// Make a cat blink now and then. `hoverTarget` (e.g. the cat's button) gets a slow blink on hover.
export function watchBlinks(svg, hoverTarget = null) {
  if (reducedMotion()) return;
  svg._nextBlink = performance.now() + 1500 + Math.random() * BLINK.every[1];   // first blinks spread out
  watched.add(svg);
  if (!timer) timer = setInterval(tick, 100);
  if (hoverTarget && BLINK.slowOnHover) {
    hoverTarget.addEventListener("pointerenter", (ev) => {
      if (ev.pointerType !== "mouse" || svg._sequence) return;
      if (startBlink(svg, true)) svg._nextBlink = performance.now() + nextIn();
    });
  }
}

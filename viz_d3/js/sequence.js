/*
  sequence.js — a cat plays an animated sequence (grooming, a head turn) with its own eyes.

  The frames come from SVG/sheet_tools: drawn by Wan 2.2 between hand-drawn keyframes, then traced with the
  drawn eyes painted out, and packed into one file per sequence by build_sequences.py. With them comes the
  eye track: where each eye is in every frame (centre, size, tilt, how far the lid is shut, which way the
  pupil looks), in kit units, so the frames sit on the kit's typical body.

  Playing a sequence on a cat:
    - The cat's own drawing (inside its .body group) is hidden, its tail stays, and the frames are shown in
      its place, in the cat's coat colours. Frames are fitted to the kit's typical body, so a kitten,
      slender or chunky cat gets them stretched to its own body's size.
    - The cat's own eye set is drawn on every frame, one eye at a time, moved, sized and tilted to the
      track. Each eye has three layers: the opening in white; the pupil, slid toward where the drawn
      pupil looked and kept inside the opening; and the lid line, which stays put. Which part of the
      drawing is pupil and which is lid line comes from SVG/eye_parts.json (built by SVG/V2/eye_parts.py).
    - Each eye has its own lids (from blink.js), shut by the track's `lid`, so the cat blinks and squints
      where the drawing did. The cat's own random blinks pause while it plays.
    - Fixes from config.js (SEQUENCES[...].fix) hide eyes covered by a paw, drop made-up blinks, and for
      long shut-eye runs show the drawing's own shut eyes instead (the track can only guess there).
  Stopping puts the cat back as it was.

  What it can't do: the frames are one orange tabby. A cat keeps its coat colours, stripes on/off, a white
  bib and a white muzzle, but its other white patches don't show while it plays.

  Idle playing (watchSequences): now and then one cat in the row plays a sequence once through, then goes
  back to sitting; one cat at a time, never while a cat is blinking, only cats on screen (IDLE in config.js).
  A sequence's file (about 1 MB gzipped) is only fetched when a cat first needs it.

  Gives back: loadSequence(key) -> the frames and track (cached); playSequence(svg, seq, kit, opts)
  -> a controller {play(), pause(), seek(frame), stop(), frames, playing}; watchSequences(svg, kit) to let
  a row cat play idly; stopSequences() to stop any that are playing (before the row is redrawn);
  loadEyeParts() -> SVG/eye_parts.json's sets (also used by gaze.js).
*/
import { PATHS, SEQUENCES, IDLE } from "./config.js";
import { lidsFor, setLid, blinkBusy, holdBlinks } from "./blink.js";

const SVGNS = "http://www.w3.org/2000/svg";
const FADE_MS = 180;      // the sitting cat and the sequence crossfade, as their drawings don't quite match
let uid = 0;
const cache = new Map();
let eyePartsPromise = null;

// ---- Loading ----
export function loadEyeParts() {
  eyePartsPromise ??= fetch(PATHS.eyeParts).then((r) => r.json()).then((j) => j.sets);
  return eyePartsPromise;
}

// One frame's markup -> its drawing as a <g> in kit units, ready to insert.
function frameNode(markup) {
  const doc = new DOMParser().parseFromString(`<svg xmlns="${SVGNS}">${markup}</svg>`, "image/svg+xml");
  const g = doc.documentElement.firstElementChild;
  g.setAttribute("class", "seq-frame");
  return document.importNode(g, true);
}

// Gaze is read off a few pixels of pupil, so it jitters: average it over three frames.
function smoothGaze(frames) {
  for (const side of ["left", "right"]) {
    const g = frames.map((f) => [f[side].gaze_x, f[side].gaze_y]);
    frames.forEach((f, i) => {
      const near = [g[i - 1], g[i], g[i + 1]].filter(Boolean);
      f[side].gx = near.reduce((s, v) => s + v[0], 0) / near.length;
      f[side].gy = near.reduce((s, v) => s + v[1], 0) / near.length;
    });
  }
}

export function loadSequence(key) {
  if (cache.has(key)) return cache.get(key);
  const fix = SEQUENCES[key]?.fix || {};
  const [a, b] = fix.drawnShut || [0, -1];
  const inShut = (n) => n >= a && n <= b;
  const p = Promise.all([fetch(`${PATHS.sequences}${key}.json`).then((r) => r.json()), loadEyeParts()])
    .then(([pack, parts]) => {
      const nodes = pack.frames.map((m, i) => frameNode(inShut(i + 1) && pack.drawnShut[i + 1] ? pack.drawnShut[i + 1] : m));
      for (const f of pack.track) {
        for (const side of ["left", "right"]) {
          if (fix.hide?.[side]?.includes(f.frame)) f[side].visible = false;
          if (fix.lid && f.frame in fix.lid) f[side].lid = fix.lid[f.frame];
          if (inShut(f.frame) && pack.drawnShut[f.frame]) f[side].visible = false;
        }
      }
      smoothGaze(pack.track);
      // The front frame: the first keyframe with both eyes showing. Eye sizes are measured against it.
      const front = pack.track.find((f) => f.keyframe && f.left.visible && f.right.visible) || pack.track[0];
      return { key, fps: pack.fps, nodes, track: pack.track, front, parts };
    });
  cache.set(key, p);
  return p;
}

// ---- Building one cat's eyes ----
function el(name, attrs = {}, parent = null) {
  const e = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.append(e);
  return e;
}
const mstr = (m) => `matrix(${m.a} ${m.b} ${m.c} ${m.d} ${m.e} ${m.f})`;

// The eye set's drawing without its whites (each eye's opening is drawn white instead).
function eyeDrawing(eyesGroup) {
  const g = el("g");
  for (const c of eyesGroup.children) {
    if (c.classList.contains("blink") || c.classList.contains("gaze")) continue;   // lids (blink.js), moving pupils (gaze.js)
    g.append(c.cloneNode(true));
  }
  g.querySelectorAll(".k-eye-white").forEach((w) => w.remove());
  g.querySelectorAll(".gaze-off").forEach((w) => w.classList.remove("gaze-off"));   // hidden by gaze.js in the sitting cat
  return g;
}

// One eye: wrapper (moved per frame, kit units) > eye-set units > opening, pupil, lid line, lids.
function buildEye(layer, defs, eyesGroup, toBody, part, fur) {
  const id = `seq${++uid}`;
  const o = part.opening_box, p = part.pupil_box, e = part.eye_box;
  const wrap = el("g", { class: "seq-eye" }, layer);
  const inner = el("g", { transform: mstr(toBody) }, wrap);
  const padE = Math.max(e.w, e.h);
  // the opening, filled white, under everything
  el("path", { d: part.opening, class: "k-eye-white" }, inner);
  // the pupil: the drawing clipped to the pupil region, slid by the gaze, kept inside the opening
  let pupilShift = null;
  if (part.pupil) {
    el("path", { d: part.opening }, el("clipPath", { id: `${id}-open` }, defs));
    el("path", { d: part.pupil }, el("clipPath", { id: `${id}-pupil` }, defs));
    const inOpening = el("g", { "clip-path": `url(#${id}-open)` }, inner);
    pupilShift = el("g", {}, inOpening);
    el("g", { "clip-path": `url(#${id}-pupil)` }, pupilShift).append(eyeDrawing(eyesGroup));
  }
  // the lid line: the drawing of this eye only, with the pupil cut out
  const mask = el("mask", { id: `${id}-line`, maskUnits: "userSpaceOnUse",
    x: e.cx - padE, y: e.cy - padE, width: 2 * padE, height: 2 * padE }, defs);
  el("rect", { x: e.cx - e.w / 2 - 2, y: e.cy - e.h / 2 - 2, width: e.w + 4, height: e.h + 4, fill: "#fff" }, mask);
  // (a little wider than the pupil, so no hairline of the pupil's edge is left behind when it moves)
  if (part.pupil) el("path", { d: part.pupil, fill: "#000", stroke: "#000", "stroke-width": 0.8, "stroke-linejoin": "round" }, mask);
  el("g", { mask: `url(#${id}-line)` }, inner).append(eyeDrawing(eyesGroup));
  // lids over the opening
  const lids = lidsFor({ x0: o.cx - o.w / 2, x1: o.cx + o.w / 2, y0: o.cy - o.h / 2, y1: o.cy + o.h / 2 }, inner, fur);
  // the opening's centre in body units, which the track's centre replaces
  const c = new DOMPoint(o.cx, o.cy).matrixTransform(toBody);
  return { wrap, pupilShift, lids, centre: c, o, p };
}

// ---- Fitting the frames to this cat's body ----
// The kit's typical body, measured once (frames are fitted to it).
let typicalBox = null;
function typicalCoatBox(kit) {
  if (typicalBox) return typicalBox;
  const svg = kit.cloneNode(true);
  for (const b of svg.querySelectorAll(".body")) if (b.dataset.body !== "typical") b.remove();
  svg.dataset.body = "typical";
  Object.assign(svg.style, { position: "absolute", visibility: "hidden", left: "-9999px", width: "400px" });
  document.body.append(svg);
  const b = svg.querySelector(".body .k-coat").getBBox();
  svg.remove();
  typicalBox = { x: b.x, y: b.y, w: b.width, h: b.height };
  return typicalBox;
}

function addCss() {
  if (document.getElementById("sequence-css")) return;
  const s = document.createElement("style");
  s.id = "sequence-css";
  s.textContent = `
.seq-layer .r-coat { fill: var(--cat-coat, #D78E34); }
.seq-layer .r-stripe { fill: var(--cat-stripes, #9D5224); }
.seq-layer .r-cream { fill: var(--cat-cream, #F5DAB5); }
.seq-layer .r-ear { fill: var(--cat-ear, #C1886A); }
.seq-layer .r-nose { fill: var(--cat-nose, #CF9389); }
.seq-layer .r-white { fill: var(--cat-white, #F5F4F3); }
.seq-layer .r-line { fill: var(--cat-outline, #462E29); }
.seq-layer [class^="r-"] { fill-rule: evenodd; }
.seq-layer .seq-eyes { fill: var(--cat-outline, #462E29); }
.seq-layer.white-chest .r-chest, .seq-layer.white-muzzle .r-muzzle { fill: var(--cat-white, #F5F4F3); }
.cat-kit[data-stripes="off"] .seq-layer .r-stripe { display: none; }
.cat-kit .body > :not(.seq-layer):not(.cat-tail) { transition: opacity ${FADE_MS}ms ease; }
.cat-kit.seq-on .body > :not(.seq-layer):not(.cat-tail) { opacity: 0; }
.seq-layer { transition: opacity ${FADE_MS}ms ease; }`;
  document.head.append(s);
}

// ---- Playing ----
export function playSequence(svg, seq, kit, { loop = true, repeats = 1, onFrame = null, onEnd = null } = {}) {
  addCss();
  const body = svg.querySelector(".body");
  const eyesGroup = svg.querySelector(`.eyes[data-set="${svg.dataset.eyes}"]`);
  const part = seq.parts[svg.dataset.eyes];
  const toBody = body.getScreenCTM().inverse().multiply(eyesGroup.getScreenCTM());
  const coat = body.querySelector(".k-coat").getBBox();

  // frames fitted to the typical body; stretch them to this cat's body (centre and floor kept)
  const t = typicalCoatBox(kit);
  const sx = coat.width / t.w, sy = coat.height / t.h;
  const tcx = t.x + t.w / 2, tfloor = t.y + t.h;
  const layer = el("g", { class: "seq-layer",
    transform: `translate(${coat.x + coat.width / 2} ${coat.y + coat.height}) scale(${sx} ${sy}) translate(${-tcx} ${-tfloor})` });
  const tail = body.querySelector(":scope > .cat-tail");
  body.insertBefore(layer, tail);                       // under the tail, as the body is
  const frameSlot = el("g", {}, layer);
  const defs = el("defs", {}, layer);
  const eyesLayer = el("g", { class: "seq-eyes" }, layer);
  const fur = "var(--cat-coat, #D78E34)";              // the frames' faces are always coat coloured
  // A white bib and a white muzzle keep their white: the frames' cream chest / muzzle is drawn white instead
  // (build_sequences.py marks which cream shape is which). Other white patches (chin, locket, blaze, paws,
  // socks, a white face) have no place in the frames and don't show.
  const zones = (svg.dataset.white || "").split(" ");
  layer.classList.toggle("white-chest", zones.includes("bib"));
  layer.classList.toggle("white-muzzle", zones.includes("muzzle"));
  const eyes = {};
  for (const side of ["left", "right"]) eyes[side] = buildEye(eyesLayer, defs, eyesGroup, toBody, part[side], fur);

  // size: the track's eye spacing on the front frame vs this eye set's spacing
  const F = seq.front;
  const k = Math.hypot(F.right.cx - F.left.cx, F.right.cy - F.left.cy) /
            Math.hypot(eyes.right.centre.x - eyes.left.centre.x, eyes.right.centre.y - eyes.left.centre.y);
  const nodes = seq.nodes.map((n) => n.cloneNode(true));

  let frame = 0, timer = null, last = 0;
  const gazeHold = { left: [0, 0], right: [0, 0] };

  function show(i) {
    frame = i;
    frameSlot.replaceChildren(nodes[i]);
    const f = seq.track[i];
    for (const side of ["left", "right"]) {
      const e = eyes[side], tr = f[side], s = tr, fr = F[side];
      e.wrap.style.display = tr.visible ? "" : "none";
      if (!tr.visible) continue;
      const ex = k * s.w / fr.w, ey = k * s.h / fr.h;
      e.wrap.setAttribute("transform",
        `translate(${s.cx} ${s.cy}) rotate(${s.angle}) scale(${ex} ${ey}) translate(${-e.centre.x} ${-e.centre.y})`);
      // where the drawn pupil looked (held while the lid is mostly shut, when it can't be read)
      if (tr.lid < 0.5) gazeHold[side] = [tr.gx, tr.gy];
      if (e.pupilShift) {
        const [gx, gy] = gazeHold[side];
        const dx = e.o.cx + gx * Math.max(0, e.o.w / 2 - e.p.w / 2) - e.p.cx;
        const dy = e.o.cy + gy * Math.max(0, e.o.h / 2 - e.p.h / 2) - e.p.cy;
        e.pupilShift.setAttribute("transform", `translate(${dx} ${dy})`);
      }
      setLid(e.lids, tr.lid);
    }
    onFrame?.(i);
  }

  let rounds = 0;
  function step(now) {
    if (!timer) return;
    if (!svg.isConnected) { ctl.stop(); return; }      // the row was redrawn
    if (now - last >= 1000 / seq.fps) {
      last = now;
      let next = frame + 1;
      if (next >= nodes.length) {
        rounds++;
        if (!loop && rounds >= repeats) { ctl.pause(); onEnd?.(); return; }
        next = 0;
      }
      show(next);
    }
    timer = requestAnimationFrame(step);
  }

  svg._sequence = true;
  show(0);
  layer.style.opacity = 0;
  layer.getBoundingClientRect();                       // so the fade starts from 0
  svg.classList.add("seq-on");
  layer.style.opacity = 1;

  const ctl = {
    frames: nodes.length,
    get frame() { return frame; },
    get playing() { return !!timer; },
    play() { if (!timer) { last = performance.now(); timer = requestAnimationFrame(step); } },
    pause() { if (timer) cancelAnimationFrame(timer); timer = null; },
    seek(i) { show(Math.max(0, Math.min(nodes.length - 1, i))); },
    stop({ fade = true } = {}) {
      ctl.pause();
      playing.delete(ctl);
      svg.classList.remove("seq-on");
      svg._sequence = false;
      if (fade && svg.isConnected && !reducedMotion()) {
        layer.style.opacity = 0;
        setTimeout(() => layer.remove(), FADE_MS);
      } else layer.remove();
    },
  };
  playing.add(ctl);
  return ctl;
}

// ---- Playing idly, in the row ----
const playing = new Set();          // controllers now running (any page)
const watched = new Map();          // row cat svg -> kit
let idleTimer = null, nextAt = 0, busy = false;

const rand = ([a, b]) => a + Math.random() * (b - a);
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function onScreen(svg) {
  const r = svg.getBoundingClientRect();
  return r.width > 0 && r.top >= 0 && r.left >= 0 && r.bottom <= window.innerHeight && r.right <= window.innerWidth;
}

function pickSequence() {
  const keys = Object.keys(SEQUENCES);
  let r = Math.random() * keys.reduce((s, k) => s + (SEQUENCES[k].weight ?? 1), 0);
  for (const k of keys) { r -= SEQUENCES[k].weight ?? 1; if (r <= 0) return k; }
  return keys[0];
}

async function idleTick() {
  for (const svg of watched.keys()) if (!svg.isConnected) watched.delete(svg);
  if (watched.size === 0) { clearInterval(idleTimer); idleTimer = null; return; }
  if (busy || document.hidden || performance.now() < nextAt || blinkBusy()) return;
  const cats = [...watched.keys()].filter(onScreen);
  if (!cats.length) return;
  const svg = cats[Math.floor(Math.random() * cats.length)];
  busy = true;
  try {
    const seq = await loadSequence(pickSequence());
    if (!svg.isConnected || !onScreen(svg)) { busy = false; return; }
    const done = () => {
      ctl.stop();
      busy = false;
      nextAt = performance.now() + rand(IDLE.every);
    };
    const ctl = playSequence(svg, seq, watched.get(svg), { loop: false, repeats: IDLE.repeats, onEnd: done });
    holdBlinks(svg, true);
    const stop = ctl.stop;
    ctl.stop = (opts) => { stop(opts); holdBlinks(svg, false); busy = false; };
    ctl.play();
  } catch (err) {
    console.warn("sequence: couldn't play", err);
    busy = false;
    nextAt = performance.now() + rand(IDLE.every);
  }
}

// Let a cat in the row play sequences now and then (with all the others, one at a time).
export function watchSequences(svg, kit) {
  if (reducedMotion()) return;
  watched.set(svg, kit);
  if (!idleTimer) {
    if (!nextAt) nextAt = performance.now() + rand(IDLE.first);
    idleTimer = setInterval(idleTick, 250);
  }
}

// Stop every sequence now playing (e.g. before the row is redrawn), putting the cats back as they were.
export function stopSequences() {
  for (const ctl of [...playing]) ctl.stop({ fade: false });
}

/*
  neuronCursor.js — the mouse pointer as a neuron (the one orange braincell, following you around).

  The cell body is a hand-drawn neuron icon with its axon removed (neuron_soma.svg), centred on the
  pointer. Out of the gap where the axon was grows a new, physical axon that trails behind, and at
  its end a small arbor of branching terminals with a bulb (bouton) on each tip.
  The trailing is real physics from d3-force:
    - every point along the axon and terminals is a node in a d3.forceSimulation;
    - d3.forceLink holds neighbouring nodes at a set distance, so the chain behaves like a string;
    - the axon's first node is pinned (fx / fy) to the gap in the cell body, so moving the mouse
      drags the chain;
    - d3.forceManyBody pushes nodes slightly apart, which splays the terminals;
    - a small custom "droop" force pulls everything gently down, so the axon hangs when you stop;
    - the cell body turns, smoothly, so its gap faces the trailing axon;
    - and, outside d3-force, a hard cap on how far any link may stretch, so the axon never gets
      longer than about MAX_STRETCH × its resting length, however fast the mouse moves.
  Clicking sends a pulse down the axon (an action potential) and lights the terminals. Over
  anything clickable the cell body swells a little, standing in for the pointer hand that the
  hidden cursor no longer shows.

  It turns itself off on touch screens (no pointer to follow) and when the system asks for reduced
  motion; the settings panel has a toggle, remembered in this browser.

  Gives back: setupNeuronCursor().
*/
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

// ---- The cell-body icon (neuron_soma.svg, in the icon's own units) ----
const SOMA_FILE = "neuron_soma.svg";       // relative to index.html
const SOMA_CENTRE = [1183, 1166];          // the nucleus: this point sits on the pointer
const SOMA_NUCLEUS_R = 164;                // nucleus radius (filled pale behind the icon)
const SOMA_GAP = [1405, 1690];             // middle of the gap the original axon came out of
const SOMA_GAP_ANGLE = Math.atan2(0.91, 0.42);   // the direction the original axon left in
const SOMA_ICON_WIDTH = 2281;              // the icon's width, for scaling

// ---- Shape and feel (pixels on screen) ----
const SOMA_SIZE = 38;          // cell body width on screen
const SOMA_READY = 1.2;        // cell body scale over something clickable
const AXON_NODES = 7;          // points along the axon, after the pinned first one
const AXON_STEP = 6;           // distance between neighbouring axon points (axon ≈ 42px long)
const BRANCHES = 3;            // primary terminal branches at the axon's end…
const BRANCH_NODES = 2;        //   …each this many points long,
const BRANCH_STEP = 6;
const TWIGS = 2;               // …each splitting into this many twigs,
const TWIG_NODES = 2;          //   …each this many points long, ending in a bouton
const TWIG_STEP = 4.5;
const MAX_STRETCH = 1.25;      // no link stretches past this × its length, however fast you move
const DROOP = 0.12;           // how strongly the axon hangs down when the pointer stops
const TURN = 0.2;              // how quickly the cell body turns to face its axon (0–1 per tick)
const PULSE_MS = 300;          // how long a click's pulse takes to run down the axon
const SLEEP_MS = 3000;         // pause the physics this long after the pointer stops
const STORAGE_KEY = "oobc-neuron-cursor";

// What counts as clickable, for the swelling cell body.
const CLICKABLE = "a, button, select, input, label, summary, [role='button'], .t-seg, .t-ring-hit";

export function setupNeuronCursor() {
  const toggle = document.getElementById("neuron-toggle");
  const touchOnly = !window.matchMedia("(pointer: fine)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Not offered at all where it can't work: hide the toggle.
  if (touchOnly || reducedMotion) {
    toggle?.closest(".vargroup")?.setAttribute("hidden", "");
    return;
  }

  const neuron = createNeuron();
  const wanted = readPreference();
  if (toggle) {
    toggle.checked = wanted;
    toggle.addEventListener("change", () => {
      savePreference(toggle.checked);
      toggle.checked ? neuron.start() : neuron.stop();
    });
  }
  if (wanted) neuron.start();
}

// ---------------------------------------------------------------------------
// The neuron: nodes, links, simulation and drawing
// ---------------------------------------------------------------------------

function createNeuron() {
  // ---- Nodes and links ----
  // Node 0 is pinned to the gap in the cell body; 1…AXON_NODES the axon. The arbor hangs off the
  // axon's last node: primary branches, each splitting into twigs. Each drawn line is a list of
  // node indices starting at the node it grows from; twigs also get a bouton on their tip.
  const nodes = [{ kind: "hillock" }];
  const links = [];
  const addChain = (from, count, step, kind) => {
    const chain = [from];
    for (let k = 0; k < count; k++) {
      nodes.push({ kind });
      const index = nodes.length - 1;
      links.push({ source: chain.at(-1), target: index, length: step });
      chain.push(index);
    }
    return chain;
  };
  const axon = addChain(0, AXON_NODES, AXON_STEP, "axon");
  const branches = [];
  const twigs = [];
  for (let b = 0; b < BRANCHES; b++) {
    const branch = addChain(axon.at(-1), BRANCH_NODES, BRANCH_STEP, "branch");
    branches.push(branch);
    for (let t = 0; t < TWIGS; t++) twigs.push(addChain(branch.at(-1), TWIG_NODES, TWIG_STEP, "twig"));
  }
  const hillock = nodes[0];

  // Where the pointer is, and which way the cell body faces (radians; 0 = as drawn).
  const pointer = { x: 0, y: 0 };
  let turn = 0;
  let ready = false;
  const scale = SOMA_SIZE / SOMA_ICON_WIDTH;

  // The gap in the cell body, in screen coordinates, for the current pointer and turn.
  function gapOnScreen() {
    const dx = (SOMA_GAP[0] - SOMA_CENTRE[0]) * scale * (ready ? SOMA_READY : 1);
    const dy = (SOMA_GAP[1] - SOMA_CENTRE[1]) * scale * (ready ? SOMA_READY : 1);
    const c = Math.cos(turn), s = Math.sin(turn);
    return { x: pointer.x + dx * c - dy * s, y: pointer.y + dx * s + dy * c };
  }

  // ---- The drawing layer: a page-sized svg above everything, ignoring the mouse ----
  const layer = d3.select(document.body).append("svg")
    .attr("class", "neuron-layer")
    .attr("aria-hidden", "true")
    .style("display", "none");
  const arbor = layer.append("g");
  const axonPath = arbor.append("path").attr("class", "neuron-axon");
  const myelinPath = arbor.append("path").attr("class", "neuron-myelin");     // sheath segments
  const branchPaths = arbor.selectAll(".neuron-branch").data([...branches, ...twigs]).join("path")
    .attr("class", "neuron-branch");
  const boutons = arbor.selectAll(".neuron-bouton").data(twigs).join("circle")
    .attr("class", "neuron-bouton").attr("r", 1.8);                           // terminal bulbs
  const pulse = layer.append("circle").attr("class", "neuron-pulse").attr("r", 2.6).style("display", "none");

  // The cell body: a pale nucleus behind the icon. A plain circle stands in until the icon loads
  // (or if it can't be loaded).
  const somaG = layer.append("g").attr("class", "neuron-soma");
  const somaInner = somaG.append("g").attr("transform", `translate(${-SOMA_CENTRE[0]},${-SOMA_CENTRE[1]})`);
  somaInner.append("circle").attr("class", "neuron-nucleus")
    .attr("cx", SOMA_CENTRE[0]).attr("cy", SOMA_CENTRE[1]).attr("r", SOMA_NUCLEUS_R);
  const standIn = somaInner.append("circle").attr("class", "neuron-body")
    .attr("cx", SOMA_CENTRE[0]).attr("cy", SOMA_CENTRE[1]).attr("r", 380);
  d3.xml(SOMA_FILE).then((doc) => {
    const d = doc.querySelector("path")?.getAttribute("d");
    if (!d) return;
    standIn.remove();
    somaInner.append("path").attr("class", "neuron-body").attr("d", d);
  }).catch(() => { /* keep the stand-in circle */ });

  // A smooth curve through a list of node indices.
  const curve = d3.line().x((i) => nodes[i].x).y((i) => nodes[i].y).curve(d3.curveCatmullRom.alpha(0.5));

  // ---- Physics ----
  // Custom force 1: turn the cell body towards its axon, then pin the axon's first node to the
  // body's gap. (Forces run before nodes move, so the pin takes effect on this very tick.)
  function attach() {
    const first = nodes[axon[1]];
    const want = Math.atan2(first.y - pointer.y, first.x - pointer.x) - SOMA_GAP_ANGLE;
    let diff = want - turn;
    diff = Math.atan2(Math.sin(diff), Math.cos(diff));      // the short way round
    turn += diff * TURN;
    const gap = gapOnScreen();
    hillock.fx = gap.x;
    hillock.fy = gap.y;
  }
  // Custom force 2: a gentle constant pull downward on every free node.
  function droop() {
    for (const n of nodes) if (n !== hillock) n.vy += DROOP;
  }
  // A force layout normally "cools" (its alpha falls toward 0) and every force weakens with it.
  // A cursor never should, so alpha is held at 1 (no decay) and the simulation is simply paused
  // once the pointer has been still for SLEEP_MS; friction (velocityDecay) does the settling.
  const simulation = d3.forceSimulation(nodes)
    .alpha(1).alphaDecay(0)
    .velocityDecay(0.35)     // friction: higher is more sluggish, lower is more swingy
    .force("attach", attach)
    .force("link", d3.forceLink(links).distance((l) => l.length).strength(1).iterations(4))
    .force("charge", d3.forceManyBody().strength(-8).distanceMax(18))
    .force("droop", droop)
    .on("tick", () => { limitStretch(); draw(); })
    .stop();

  // d3-force links are springs, so a fast-moving pointer stretches the chain out behind it. After
  // each step, any point further than MAX_STRETCH × its link length from the point it hangs off is
  // pulled back to that distance. Links are in tree order (parents first), so one pass settles it.
  function limitStretch() {
    for (const { source, target, length } of links) {
      const dx = target.x - source.x, dy = target.y - source.y;
      const d = Math.hypot(dx, dy), max = length * MAX_STRETCH;
      if (d > max) {
        target.x = source.x + (dx / d) * max;
        target.y = source.y + (dy / d) * max;
      }
    }
  }

  function draw() {
    axonPath.attr("d", curve(axon));
    myelinPath.attr("d", curve(axon.slice(1, -1)));        // the sheath starts after the hillock
    branchPaths.attr("d", curve);
    boutons.attr("cx", (twig) => nodes[twig.at(-1)].x).attr("cy", (twig) => nodes[twig.at(-1)].y);
    const k = scale * (ready ? SOMA_READY : 1);
    somaG.attr("transform", `translate(${pointer.x},${pointer.y}) rotate(${turn * 180 / Math.PI}) scale(${k})`);
  }

  // ---- Following the pointer ----
  let placed = false;
  let sleepTimer = null;
  function onMove(event) {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    if (!placed) {
      // First sighting: lay the whole neuron out below the gap, hanging straight down.
      const gap = gapOnScreen();
      nodes.forEach((n, i) => { n.x = gap.x + (i % 3) - 1; n.y = gap.y + 2 + Math.min(i, AXON_NODES + 3) * AXON_STEP; });
      placed = true;
    }
    const target = event.target instanceof Element ? event.target : null;
    ready = !!target?.closest(CLICKABLE);
    somaG.classed("is-ready", ready);
    layer.style("display", null);
    simulation.restart();                                            // wake the physics
    clearTimeout(sleepTimer);
    sleepTimer = setTimeout(() => simulation.stop(), SLEEP_MS);      // rest once it has hung still
  }
  function onLeave() { layer.style("display", "none"); }

  // ---- A click fires a pulse down the axon, and the terminals light up when it arrives ----
  function onDown() {
    const node = axonPath.node();
    if (!node.getAttribute("d")) return;          // nothing drawn yet
    pulse.style("display", null);
    const timer = d3.timer((elapsed) => {
      const t = Math.min(1, elapsed / PULSE_MS);
      // The axon keeps moving while the pulse runs, so measure it afresh each frame.
      const p = node.getPointAtLength(t * node.getTotalLength());
      pulse.attr("cx", p.x).attr("cy", p.y);
      if (t >= 1) {
        timer.stop();
        pulse.style("display", "none");
        boutons.classed("is-firing", true);
        setTimeout(() => boutons.classed("is-firing", false), 220);
      }
    });
  }

  return {
    start() {
      document.documentElement.classList.add("neuron-cursor");    // hides the normal cursor (CSS)
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerdown", onDown);
      document.documentElement.addEventListener("pointerleave", onLeave);
    },
    stop() {
      document.documentElement.classList.remove("neuron-cursor");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      simulation.stop();
      clearTimeout(sleepTimer);
      layer.style("display", "none");
      placed = false;
    },
  };
}

// ---- Remembering the toggle (this browser only; any storage error just means "on") ----
function readPreference() {
  try { return localStorage.getItem(STORAGE_KEY) !== "off"; } catch { return true; }
}
function savePreference(on) {
  try { localStorage.setItem(STORAGE_KEY, on ? "on" : "off"); } catch { /* not saved; fine */ }
}
